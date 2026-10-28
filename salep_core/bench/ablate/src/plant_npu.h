#ifndef PLANT_NPU_H
#define PLANT_NPU_H

#include "fdm.h"
#include "synapse.h"

// ---------------------------------------------------------------------------
// Bitki NPU — Duyusal Lob (pre frekans cozuculer) + Kosul Ogrenme Lobu
// (post grounding). Pavlov deneyi topolojisi. FAZ 2: dual-rail genisletme.
//
//   Rail-F (frekans raili): ORTAK TEL (4+12 superpoze + gurultu, D_b=0)
//    |- bant-4  pop (8 uye, PLIR) -- temsilci m=0 -- syn --> grounding/capraz postlar
//    |- bant-12 pop (8 uye, PLIR) -- temsilci m=0 -- syn --> grounding/capraz postlar
//   Rail-C (kanal raili): sensor kanali tasiyici sayaclari
//    (channel_carrier[7]: her sensor kanalinin spike bayrak sayaci).
//
// Post dizilimi (9 aktif + 1 slot headroom):
//   p0..p6 grounding (7 sensorun her biri bir (bant, sensor) ciftine bagli)
//   p7..p8 capraz (baska kanalin sensoru + baska bandin temsilcisi)
//   Ilk 3 post FAZ 1 ile birebir aynidir (NEM/EC/SIC) -> batch CSV geriye uyumlu.
//
// Sensor kanallari (7):
//   0=HN (hava nem, eski --nem)  1=EC  2=HS (hava sicaklik, eski --sicaklik)
//   3=TS (toprak sicaklik)  4=TN (toprak nem)  5=PH  6=NPK
//
// Anayasa: CPU yalniz harici spike bayragi verir (sensor degeri/esik
// CEKIRDEKTE bilinmez); ogrenme/karar tumuyle dendritlerde. Ogrenme kurali
// mevcut synapse.h kuadratik kuralidir (yeni kural YOK). Cekirdekte
// float/double, dinamik bellek YOK. Kalibrasyon: validate_plant_npu.py
// (S_b=1.0, w0=0.2, eta=0.2).
//
// Kapsam disi: ongoru/nedensellik ust lobu bu dosyaya GIRMEZ.
// ---------------------------------------------------------------------------

constexpr int PNP_MAX_SENSORS = 7;  // Rail-C kanal sayisi
constexpr int PNP_MAX_POST = 10;    // 9 aktif + 1 slot headroom
constexpr int PNP_NUM_POST = 9;     // aktif post sayisi (7 grounding + 2 capraz)
constexpr int PNP_NUM_GROUNDING = 7;
constexpr int PNP_NUM_BASE = 3;  // FAZ 1 batch CSV uyumlulugu: ilk 3 post

// Sensor kanal kimlikleri (Rail-C indeksi).
constexpr int PNP_CH_HN = 0;   // hava nem (eski NEM)
constexpr int PNP_CH_EC = 1;   // EC (negatif kontrol)
constexpr int PNP_CH_HS = 2;   // hava sicaklik (eski SICAKLIK)
constexpr int PNP_CH_TS = 3;   // toprak sicaklik
constexpr int PNP_CH_TN = 4;   // toprak nem
constexpr int PNP_CH_PH = 5;   // pH
constexpr int PNP_CH_NPK = 6;  // NPK

constexpr int32_t PNP_TAUS[2] = {4, 12};  // FDM 2-bant siniri (§9.8)
constexpr int PNP_POPS[2] = {FDM_N_POP, FDM_N_POP};
constexpr uint32_t PNP_SEED = 7001;  // deterministik cekirdek tohumu

// Kalibre sabitler (validate_plant_npu.py, Kural 0).
constexpr fixed_t PNP_SENSOR_AMP = fixed_from_double(1.0);  // S_b
constexpr fixed_t PNP_ETA = fixed_from_double(0.2);         // eta
constexpr fixed_t PNP_W0 = fixed_from_double(0.2);          // w0

// Post -> bant / sensor eslesmesi (derleme-zamani sabiti, sabit dizi).
// Ilk 3: FAZ 1 ile ayni (NEM/EC<-12, SIC<-4; nem, ec, sic).
// p3..p6: yeni grounding (TS<-4, TN<-12, PH<-4, NPK<-12).
// p7..p8: capraz (bant-4 temsilci + HN sensoru; bant-12 temsilci + HS sensoru).
constexpr int32_t PNP_POST_BAND[PNP_NUM_POST] = {1, 1, 0, 0, 1, 0, 1, 0, 1};
constexpr int PNP_POST_CHAN[PNP_NUM_POST] = {
    PNP_CH_HN, PNP_CH_EC, PNP_CH_HS, PNP_CH_TS,
    PNP_CH_TN, PNP_CH_PH, PNP_CH_NPK, PNP_CH_HN, PNP_CH_HS};

struct PlantNpu {
    FdmNetwork sensory;  // Rail-F: frekans raili (2 bant x 8 uye)

    DendriticNeuron post[PNP_MAX_POST];
    Synapse syn[PNP_MAX_POST];

    SpikeRateCounter rc_pre[PNP_MAX_POST];
    SpikeRateCounter rc_post[PNP_MAX_POST];

    // Rail-C: kanal tasiyici sayaclari (her sensor kanali icin spike sayaci).
    SpikeRateCounter channel_carrier[PNP_MAX_SENSORS];

    int32_t band_of_post[PNP_MAX_POST];        // post -> duyusal bant indeksi
    int sensor_channel_of_post[PNP_MAX_POST];  // post -> sensor kanali 0..6

    fixed_t sensor_amp;
    fixed_t eta;
    int num_post;
};

inline NeuronParams plant_post_params() {
    // Causality target ile ayni: hafif sizintili entegrator.
    NeuronParams p = {0.04, 0.04, 0.04, 0.005, 0.004, 0.003};
    return p;
}

inline void plant_init(PlantNpu& net, fixed_t sensor_amp, fixed_t eta,
                       fixed_t initial_w) {
    fdm_init(net.sensory, PNP_TAUS, PNP_POPS, 2, 1, PNP_SEED);

    NeuronParams tp = plant_post_params();
    for (int k = 0; k < PNP_NUM_POST; ++k) {
        neuron_init_with_params(net.post[k], 100 + k, tp);
        net.band_of_post[k] = PNP_POST_BAND[k];
        net.sensor_channel_of_post[k] = PNP_POST_CHAN[k];
        int rep_id = PNP_POST_BAND[k] * FDM_MAX_POP + 0;  // temsilci uye m=0
        synapse_init(net.syn[k], rep_id, net.post[k].branch_A_id, initial_w);
        rate_counter_init(net.rc_pre[k]);
        rate_counter_init(net.rc_post[k]);
    }

    for (int c = 0; c < PNP_MAX_SENSORS; ++c) {
        rate_counter_init(net.channel_carrier[c]);
    }

    net.sensor_amp = sensor_amp;
    net.eta = eta;
    net.num_post = PNP_NUM_POST;
}

struct PlantTickResult {
    FdmTickFires pre;
    bool rep_fired[PNP_MAX_POST];
    bool post_fired[PNP_MAX_POST];
    bool coinc[PNP_MAX_POST];
};

// Tick sirasi (causality_tick disiplini):
//   1) fdm_tick ile pre katmani (Rail-F)  2) atesleyen temsilci -> I_syn Dal A'ya
//   3) sensor_spike[k] ise sensor_amp Dal B'ye (B dali kapisiz, dogrudan)
//   4) post tick  5) rate counter + kuadratik ogrenme.
// Rail-C: grounding postlarin (k<7) sensor bayraklari ayni zamanda ilgili
// kanal tasiyici sayacina yazilir (capraz postlar cift sayim yapmaz).
inline PlantTickResult plant_tick(PlantNpu& net, int32_t t, fixed_t wire,
                                 const bool sensor_spike[PNP_MAX_POST],
                                 fixed_t dw_out[PNP_MAX_POST]) {
    PlantTickResult r;
    r.pre = fdm_tick(net.sensory, t, wire);

    for (int k = 0; k < net.num_post; ++k) {
        int32_t b = net.band_of_post[k];
        r.rep_fired[k] = r.pre.fired[b][0];
        if (r.rep_fired[k]) {
            fixed_t cur = synapse_transmission_current(net.syn[k]);
            neuron_inject_current(net.post[k],
                                 net.syn[k].target_compartment_id, cur, t);
        }
        if (sensor_spike[k]) {
            neuron_inject_current(net.post[k], net.post[k].branch_B_id,
                                  net.sensor_amp, t);
        }
    }

    for (int k = 0; k < net.num_post; ++k) {
        r.post_fired[k] = neuron_tick(net.post[k], t);
        bool ba = (net.post[k].branch_A_last_input_tick >= 0) &&
                  ((t - net.post[k].branch_A_last_input_tick) <=
                   COINCIDENCE_WINDOW_MS);
        bool bb = (net.post[k].branch_B_last_input_tick >= 0) &&
                  ((t - net.post[k].branch_B_last_input_tick) <=
                   COINCIDENCE_WINDOW_MS);
        r.coinc[k] = ba && bb;
    }

    for (int k = 0; k < net.num_post; ++k) {
        rate_counter_update(net.rc_pre[k], r.rep_fired[k]);
        rate_counter_update(net.rc_post[k], r.post_fired[k]);
        dw_out[k] = synapse_apply_learning(net.syn[k], net.rc_pre[k].count,
                                           net.rc_post[k].count, net.eta);
    }
    // Rail-C kanal sayaclari: yalniz grounding postlar (k<7) yazar.
    for (int k = 0; k < PNP_NUM_GROUNDING && k < net.num_post; ++k) {
        int c = net.sensor_channel_of_post[k];
        if (c >= 0 && c < PNP_MAX_SENSORS) {
            rate_counter_update(net.channel_carrier[c], sensor_spike[k]);
        }
    }
    return r;
}

#endif  // PLANT_NPU_H
