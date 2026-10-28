#ifndef SENSORY_LOBE_H
#define SENSORY_LOBE_H

#include "neuron.h"
#include "synapse.h"

// ---------------------------------------------------------------------------
// Duyusal Lob v2 (FAZ 3, §9.14) — P1 PRE faz hatlari + P2 POST kosul bankasi.
//
//   P1 (faz hatti): her P1 kendi hattina PLIR-A ile kilitlenir (tau_isi_A).
//     Temsilci atesi -> sinaps -> P2 Dal A (ogrenir).
//   P2 (kosul bankasi): Dal A <- P1 (bitki fazi); Dal B <- sensor faz hatti
//     (B-PLIR kendi tau_B'sini secer; yabanci periyot reddedilir).
//
// Cekirdek kurallari (anayasa §2): float/double YOK, dinamik bellek YOK,
// sabit boyutlu diziler (P1_MAX/P2_MAX tavan; aktif sayi dinamik <= tavan).
// fdm.h / synapse.h / neuron.h davranisi degismedi; yalniz yeni kod.
// ---------------------------------------------------------------------------

constexpr int P1_MAX = 16;
constexpr int P2_MAX = 64;

// B-PLIR kapi bant genisligi (FDM_BW disiplini: deterministik izgara -> 1).
constexpr int32_t SL_BW = 1;

struct SensoryLobe {
    DendriticNeuron p1[P1_MAX];
    int32_t p1_tau[P1_MAX];  // hat periyodu (PLIR-A tau_isi ile ayni)
    int num_p1;

    DendriticNeuron p2[P2_MAX];
    Synapse syn[P2_MAX];
    SpikeRateCounter rc_pre[P2_MAX];
    SpikeRateCounter rc_post[P2_MAX];
    int p1_src[P2_MAX];      // P2 Dal A'yi suren P1 indeksi
    int sensor_ch[P2_MAX];   // P2 Dal B sensor kanali (harness esler)
    int32_t tau_b[P2_MAX];   // B-PLIR tau'su
    int num_p2;

    fixed_t sensor_amp;    // P2 Dal B darbe genligi
    fixed_t p1_amp[P1_MAX];  // hat bazinda P1 surusu (yavas hat telafisi)
    fixed_t eta;
};

// --- Kanonik etiket: bijective base-26 --------------------------------------
// idx 0->a ... 25->z, 26->a/a, 27->a/b ... 51->a/z, 52->b/a ...
// "p2a(p2c)" formati: kosul adi + ayni tick atesleyenler (sirali).
// is_p2=false -> "p1.." öneki. Saf fonksiyon (donanim yok).
inline void sl_render_label(int idx, bool is_p2, char* out, int cap) {
    if (cap <= 0) return;
    char digits[16];
    int nd = 0;
    int v = idx + 1;  // bijective: 1-based
    while (v > 0 && nd < 15) {
        v -= 1;
        digits[nd++] = (char)('a' + (v % 26));
        v /= 26;
    }
    int pos = 0;
    out[pos++] = 'p';
    if (pos < cap) out[pos++] = is_p2 ? '2' : '1';
    for (int i = nd - 1; i >= 0 && pos < cap - 1; --i) {
        if (i != nd - 1) {
            out[pos++] = '/';
            if (pos >= cap - 1) break;
        }
        out[pos++] = digits[i];
    }
    out[pos < cap ? pos : cap - 1] = '\0';
}

// Ayni tick atesleyen P2'ler -> kosul etiketi: tek "p2a", coklu
// "p2a(p2b,p2d)" (sirali). Harness sonuna " kosul" ekler.
inline void sl_condition_label(const bool fired[], int num, char* out,
                               int cap) {
    if (cap <= 0) return;
    int first = -1;
    for (int k = 0; k < num; ++k) {
        if (fired[k]) {
            first = k;
            break;
        }
    }
    if (first < 0) {
        out[0] = '\0';
        return;
    }
    char tmp[32];
    sl_render_label(first, true, tmp, sizeof(tmp));
    int pos = 0;
    for (int i = 0; tmp[i] != '\0' && pos < cap - 1; ++i) {
        out[pos++] = tmp[i];
    }
    bool multi = false;
    for (int k = first + 1; k < num; ++k) {
        if (fired[k]) {
            multi = true;
            break;
        }
    }
    if (multi) {
        if (pos < cap - 1) out[pos++] = '(';
        bool need_comma = false;
        for (int k = first + 1; k < num; ++k) {
            if (!fired[k]) continue;
            if (need_comma && pos < cap - 1) out[pos++] = ',';
            sl_render_label(k, true, tmp, sizeof(tmp));
            for (int i = 0; tmp[i] != '\0' && pos < cap - 1; ++i) {
                out[pos++] = tmp[i];
            }
            need_comma = true;
        }
        if (pos < cap - 1) out[pos++] = ')';
    }
    out[pos < cap ? pos : cap - 1] = '\0';
}

// --- P1 parametresi (fdm_band_params disiplini) ------------------------------
// Buyuk tau -> dusuk leak (seyrek bant ates firsati esitlenir); PLIR-A
// opt-in, bw=SL_BW, lock=2*tau+bw.
inline NeuronParams sl_p1_params(int32_t tau) {
    NeuronParams p = {0.08, 0.06, 0.04, 0.005, 0.004, 0.003};
    if (tau >= 16) {
        p.root_leak = 0.01;
        p.brA_leak = 0.01;
        p.brB_leak = 0.01;
    } else if (tau >= 11) {
        p.root_leak = 0.02;
        p.brA_leak = 0.015;
        p.brB_leak = 0.015;
    } else if (tau >= 7) {
        p.root_leak = 0.04;
        p.brA_leak = 0.03;
        p.brB_leak = 0.03;
    }
    p.tau_isi = tau;
    p.resonance_bw = SL_BW;
    p.plir_mode = 1;
    p.plir_lock_lost = 2 * tau + SL_BW;
    return p;
}

// --- P2 parametresi -----------------------------------------------------------
// Hafif sizintili entegrator (plant_post disiplini). A/B ASIMETRISI:
// Dal A yogun surulur (P1 her ~8-24 tick atesler) -> brA yuksek (0.08),
// A-tek-basina ates bastirilir. Dal B seyrek gelir -> brB tau_B'ye gore
// tier'li (seyrek faz hatti sonumu; tau_B>=32 -> 0.01, plan disiplini).
// B-PLIR her zaman acik (bu lobun isi).
inline NeuronParams sl_p2_params(int32_t tau_b) {
    NeuronParams p = {0.04, 0.12, 0.04, 0.005, 0.004, 0.003};
    if (tau_b >= 32) {
        p.root_leak = 0.01;
        p.brB_leak = 0.01;
    }
    p.plir_mode_B = 1;
    p.tau_isi_B = tau_b;
    p.resonance_bw_B = SL_BW;
    p.plir_lock_lost_B = 2 * tau_b + SL_BW;
    return p;
}

struct SlPostCfg {
    int p1_src;      // Dal A'yi suren P1 indeksi
    int sensor_ch;   // Dal B sensor kanali (harness esler)
    int32_t tau_b;   // B-PLIR tau'su
    fixed_t w0;      // baslangic agirligi
};

// Buyume ilkeli (FAZ 4, §9.15): yedek slottan ise alim. Yeni post
// sifirdan baslar (taze kilit, w0 agirligi, sifirlanmis sayaclar) ve
// num_p2 bir artar. Sabit silikonda malloc yok; buyume = ihtiyacta
// yedekten atama (P2_MAX donanim tavani). Donus: false = banka dolu.
inline bool sl_add_post(SensoryLobe& lobe, const SlPostCfg& cfg,
                        fixed_t p1_amp) {
    if (lobe.num_p2 >= P2_MAX) return false;
    int k = lobe.num_p2++;
    if (cfg.p1_src >= 0 && cfg.p1_src < lobe.num_p1) {
        lobe.p1_amp[cfg.p1_src] = p1_amp;
    }
    neuron_init_with_params(lobe.p2[k], 100 + k,
                            sl_p2_params(cfg.tau_b));
    lobe.p1_src[k] = cfg.p1_src;
    lobe.sensor_ch[k] = cfg.sensor_ch;
    lobe.tau_b[k] = cfg.tau_b;
    synapse_init(lobe.syn[k], cfg.p1_src, lobe.p2[k].branch_A_id, cfg.w0);
    rate_counter_init(lobe.rc_pre[k]);
    rate_counter_init(lobe.rc_post[k]);
    return true;
}

inline void sl_init(SensoryLobe& lobe, const int32_t p1_taus[], int num_p1,
                    const SlPostCfg posts[], int num_p2, fixed_t sensor_amp,
                    const fixed_t p1_amp[], fixed_t eta) {
    lobe.num_p1 = (num_p1 > P1_MAX) ? P1_MAX : num_p1;
    for (int i = 0; i < lobe.num_p1; ++i) {
        lobe.p1_tau[i] = p1_taus[i];
        lobe.p1_amp[i] = p1_amp[i];
        neuron_init_with_params(lobe.p1[i], i, sl_p1_params(p1_taus[i]));
    }
    lobe.num_p2 = 0;
    int n = (num_p2 > P2_MAX) ? P2_MAX : num_p2;
    for (int k = 0; k < n; ++k) {
        sl_add_post(lobe, posts[k], p1_amp[posts[k].p1_src]);
    }
    lobe.sensor_amp = sensor_amp;
    lobe.eta = eta;
}

// --- Banka boyutlandirma kurali (dinamik sayi, sabit tavan) ------------------
// Her sensor kanali -> 1 grounding postu (kendi tau_B'si); + replika ve
// decoy ispat hatlari; capraz postlar SIMDI 0 (OFF-US kodlamasi olmadan
// OFF-kosulu temsil edilemez; ust lobun isi, §9.14 notu).
// Varsayilan banka: 7 grounding + 1 replika + 2 decoy = 10 <= 64.
// Yeni sensor eklenirse +1 grounding (+1 decoy opsiyonel); tavan asilirsa
// kirpilir (P2_MAX donanim siniri).
inline int sl_bank_size(int n_sensors, int n_replica, int n_decoy) {
    int n = n_sensors + n_replica + n_decoy;
    return (n > P2_MAX) ? P2_MAX : n;
}

struct SensoryTickResult {
    bool p1_fired[P1_MAX];
    bool p2_fired[P2_MAX];
    bool coinc[P2_MAX];
};

// Tick sirasi:
//   1) P1 hat darbeleri -> Dal A enjekte (PLIR-A kendi hattina kilitli)
//   2) P1 tick
//   3) atesleyen P1 -> synapse akimi P2 Dal A'ya
//   4) sensor hatti darbesi -> P2 Dal B'ye (B-PLIR kabul/red)
//   5) P2 tick + rate counter + kuadratik ogrenme (plant disiplini).
inline SensoryTickResult sensory_tick(SensoryLobe& lobe, int32_t t,
                                      const bool p1_pulse[],
                                      const bool sensor_pulse[],
                                      fixed_t dw_out[]) {
    SensoryTickResult r;
    for (int i = 0; i < lobe.num_p1; ++i) {
        r.p1_fired[i] = false;
        if (p1_pulse[i]) {
            neuron_inject_current(lobe.p1[i], lobe.p1[i].branch_A_id,
                                  lobe.p1_amp[i], t);
        }
    }
    for (int k = 0; k < lobe.num_p2; ++k) {
        r.p2_fired[k] = false;
        r.coinc[k] = false;
        dw_out[k] = 0;
    }
    for (int i = 0; i < lobe.num_p1; ++i) {
        r.p1_fired[i] = neuron_tick(lobe.p1[i], t);
    }
    for (int k = 0; k < lobe.num_p2; ++k) {
        int src = lobe.p1_src[k];
        bool pre = (src >= 0 && src < lobe.num_p1) && r.p1_fired[src];
        if (pre) {
            fixed_t cur = synapse_transmission_current(lobe.syn[k]);
            neuron_inject_current(lobe.p2[k],
                                  lobe.syn[k].target_compartment_id, cur, t);
        }
        if (sensor_pulse[k]) {
            neuron_inject_current(lobe.p2[k], lobe.p2[k].branch_B_id,
                                  lobe.sensor_amp, t);
        }
    }
    for (int k = 0; k < lobe.num_p2; ++k) {
        r.p2_fired[k] = neuron_tick(lobe.p2[k], t);
        bool ba = (lobe.p2[k].branch_A_last_input_tick >= 0) &&
                  ((t - lobe.p2[k].branch_A_last_input_tick) <=
                   COINCIDENCE_WINDOW_MS);
        bool bb = (lobe.p2[k].branch_B_last_input_tick >= 0) &&
                  ((t - lobe.p2[k].branch_B_last_input_tick) <=
                   COINCIDENCE_WINDOW_MS);
        r.coinc[k] = ba && bb;
    }
    for (int k = 0; k < lobe.num_p2; ++k) {
        int src = lobe.p1_src[k];
        bool pre = (src >= 0 && src < lobe.num_p1) && r.p1_fired[src];
        rate_counter_update(lobe.rc_pre[k], pre);
        rate_counter_update(lobe.rc_post[k], r.p2_fired[k]);
        dw_out[k] = synapse_apply_learning(lobe.syn[k], lobe.rc_pre[k].count,
                                           lobe.rc_post[k].count, lobe.eta);
    }
    return r;
}

#endif  // SENSORY_LOBE_H
