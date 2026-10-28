#ifndef SYNAPSE_H
#define SYNAPSE_H

#include "fixed_point.h"

// ---------------------------------------------------------------------------
// Sinaps — kuadratik spike-rate öğrenme kuralı
//
// CLAUDE.md §9: dw = eta * G(r_pre,r_post) * Q(r_pre,r_post) * S(w)
//
// Üç bileşen ayrı ayrı test edilebilir fonksiyonlar olarak yazılıyor,
// tek bir dev formül değil. Her biri kendi LUT'undan okur — exp()/log()
// yerine önceden hesaplanmış tablo (ARCHITECTURE.md §2.3 kısıtı).
//
// Sinaps artık presinaptik ateşlemede N0→N1'e gerçek akım aktarır:
// I_syn = weight × SYNAPSE_CURRENT_SCALE, target_compartment_id'ye enjekte edilir.
// L0 koşusu (açık döngü) transfer kapalıdır — §9.3'ün tarihsel plastisite
// referansıdır. Transferli öğrenme L1'de ve aktarım testleri T1/T2'dedir
// (bkz. main_synapse.cpp, CLAUDE.md §9.4).
// ---------------------------------------------------------------------------

struct Synapse {
    fixed_t weight;               // sabit nokta ağırlık (erişilebilir güç)
    fixed_t trace;                // öğrenilmiş iz 0..1 (varlık; ASLA sönmez)
    fixed_t tau_resonance;        // rezonans zaman sabiti (bu adımda kullanılmıyor)
    int32_t last_spike_time_ms;   // son ateşleme zaman damgası
    int     target_compartment_id;
    int     source_neuron_id;
};

inline void synapse_init(Synapse& s, int source_neuron_id,
                          int target_compartment_id, fixed_t initial_weight) {
    s.weight                = initial_weight;
    s.trace                 = 0;
    s.tau_resonance          = 0;
    s.last_spike_time_ms     = -1;
    s.target_compartment_id  = target_compartment_id;
    s.source_neuron_id       = source_neuron_id;
}

// Presinaptik nöron ateşlendiğinde postsinaptik tarafa aktarılacak akım.
inline fixed_t synapse_transmission_current(const Synapse& s);

// Sinaptik akım ölçeği: I_syn = weight * SYNAPSE_CURRENT_SCALE.
// Float Monte-Carlo ile kalibre edildi (CLAUDE.md §0): w=0.05 -> I=0.025
// (N1'i asla ateşletmez), w~1.9 (öğrenilmiş) -> I~0.95 (N1'i gating
// birikimiyle güvenle ateşletir). N1'in sinaptik ateşleme eşiği ~0.68
// akımdır (kök gating eşiği 0.15'in aşılması gerekir); scale 0.5 bu
// eşiğin altı ile üstü arasında maksimum marjı bırakır. w=W_MAX=2.0
// iken I=1.0 (doğrudan uyaran azamisi 0.8'e yakın).
constexpr fixed_t SYNAPSE_CURRENT_SCALE = fixed_from_double(0.5);

inline fixed_t synapse_transmission_current(const Synapse& s) {
    return fixed_mul(s.weight, SYNAPSE_CURRENT_SCALE);
}

// ---------------------------------------------------------------------------
// Ateşleme oranı sayacı — kayan pencere, tam sayı, exp/float yok
//
// RATE_WINDOW tick'lik bir halka (ring) tamponunda son ateşlemeleri tutar.
// r_pre / r_post, bu pencere içindeki toplam ateşleme SAYISIDIR (0..RATE_WINDOW).
// ---------------------------------------------------------------------------

constexpr int RATE_WINDOW = 30;

struct SpikeRateCounter {
    bool fired_history[RATE_WINDOW];
    int  head;   // sıradaki yazılacak slot
    int  count;  // pencere içindeki toplam ateşleme sayısı
};

inline void rate_counter_init(SpikeRateCounter& rc) {
    for (int i = 0; i < RATE_WINDOW; ++i) {
        rc.fired_history[i] = false;
    }
    rc.head  = 0;
    rc.count = 0;
}

// Her tick bir kez çağrılır (nöron ateşlendi mi ateşlenmedi mi).
inline void rate_counter_update(SpikeRateCounter& rc, bool fired) {
    if (rc.fired_history[rc.head]) {
        rc.count--;
    }
    rc.fired_history[rc.head] = fired;
    if (fired) {
        rc.count++;
    }
    rc.head = (rc.head + 1) % RATE_WINDOW;
}

// ---------------------------------------------------------------------------
// LUT'lar — bir kere kurulur (init), sonra sadece okunur
//
// Gerçek FPGA/HLS hedefinde bu tablolar derleme zamanında üretilip ROM
// olarak gömülür; burada PC prototipinde tek seferlik bir init fonksiyonuyla
// dolduruluyor (çalışma zamanı tick döngüsünde ASLA yeniden hesaplanmaz).
//
// G_LUT / Q_LUT: [r_pre][r_post] indeksli, 0..RATE_WINDOW aralığında.
// S_LUT: ağırlık kovasına (bucket) göre indekslenir, 0..N_W_BUCKETS.
// ---------------------------------------------------------------------------

constexpr fixed_t W_MAX        = fixed_from_double(2.0);  // ağırlık tavanı
constexpr int     N_W_BUCKETS  = 64;

static fixed_t G_LUT[RATE_WINDOW + 1][RATE_WINDOW + 1];
static fixed_t Q_LUT[RATE_WINDOW + 1][RATE_WINDOW + 1];
static fixed_t S_LUT[N_W_BUCKETS + 1];
static bool    g_synapse_luts_built = false;

// G — "bilgi kazancı": iki oranın ORTAK açıklanan kısmı (min-overlap).
// p = r_pre/RATE_WINDOW, q = r_post/RATE_WINDOW (ikisi de 0..1).
// Biri hiç ateşlemediyse G=0 → aralarında bilgi bağlantısı kurulamaz.
// İkisi de maksimumdaysa G=1 → tam örtüşme.
inline fixed_t synapse_lut_compute_G(fixed_t p, fixed_t q) {
    return (p < q) ? p : q;
}

// Q — kuadratik etkileşim: p^2 + q^2 + 2pq = (p+q)^2
// İkinci dereceden terimler (p^2, q^2, çapraz terim 2pq) içerir.
// Basit doğrusal korelasyon (p*q) sadece çapraz terimi yakalar; burada
// bireysel oranların karesi de katkı yapıyor, yani düşük ama EŞİT
// oranlarda bile (p=q=0.1) doğrusal korelasyondan (0.01) daha güçlü bir
// sinyal üretir (0.04) — seyrek ateşlemede bile öğrenme sinyali sıfıra
// çökmüyor.
inline fixed_t synapse_lut_compute_Q(fixed_t p, fixed_t q) {
    fixed_t pp = fixed_mul(p, p);
    fixed_t qq = fixed_mul(q, q);
    fixed_t pq2 = 2 * fixed_mul(p, q);
    return pp + qq + pq2;
}

// S — istikrar/regularizasyon: yumuşak tavan.
// S(w) = 1 - (w/W_MAX)^2, w → W_MAX iken S → 0 → öğrenme durur.
// Runaway potentiation'ı (ağırlığın sınırsız büyümesini) önler.
inline fixed_t synapse_lut_compute_S(fixed_t w) {
    if (w < 0)     w = 0;
    if (w > W_MAX) w = W_MAX;
    fixed_t x  = fixed_div(w, W_MAX);      // 0..FIXED_ONE
    fixed_t x2 = fixed_mul(x, x);
    fixed_t s  = FIXED_ONE - x2;
    return (s < 0) ? 0 : s;
}

inline void synapse_build_luts() {
    if (g_synapse_luts_built) return;

    for (int rp = 0; rp <= RATE_WINDOW; ++rp) {
        fixed_t p = fixed_div(fixed_from_int(rp), fixed_from_int(RATE_WINDOW));
        for (int rq = 0; rq <= RATE_WINDOW; ++rq) {
            fixed_t q = fixed_div(fixed_from_int(rq), fixed_from_int(RATE_WINDOW));
            G_LUT[rp][rq] = synapse_lut_compute_G(p, q);
            Q_LUT[rp][rq] = synapse_lut_compute_Q(p, q);
        }
    }

    for (int b = 0; b <= N_W_BUCKETS; ++b) {
        fixed_t w = fixed_div(fixed_mul(fixed_from_int(b), W_MAX),
                               fixed_from_int(N_W_BUCKETS));
        S_LUT[b] = synapse_lut_compute_S(w);
    }

    g_synapse_luts_built = true;
}

// ---------------------------------------------------------------------------
// G, Q, S — dışa açık, LUT'tan okuyan, ayrı ayrı test edilebilir fonksiyonlar
// ---------------------------------------------------------------------------

inline fixed_t synapse_G(int r_pre, int r_post) {
    if (r_pre  < 0) r_pre  = 0;
    if (r_pre  > RATE_WINDOW) r_pre  = RATE_WINDOW;
    if (r_post < 0) r_post = 0;
    if (r_post > RATE_WINDOW) r_post = RATE_WINDOW;
    return G_LUT[r_pre][r_post];
}

inline fixed_t synapse_Q(int r_pre, int r_post) {
    if (r_pre  < 0) r_pre  = 0;
    if (r_pre  > RATE_WINDOW) r_pre  = RATE_WINDOW;
    if (r_post < 0) r_post = 0;
    if (r_post > RATE_WINDOW) r_post = RATE_WINDOW;
    return Q_LUT[r_pre][r_post];
}

inline fixed_t synapse_S(fixed_t w) {
    if (w < 0)     w = 0;
    if (w > W_MAX) w = W_MAX;
    fixed_t frac     = fixed_div(w, W_MAX);                  // 0..FIXED_ONE
    fixed_t idx_fixed = fixed_mul(frac, fixed_from_int(N_W_BUCKETS));
    int idx = idx_fixed >> FIXED_SHIFT;                      // 0..N_W_BUCKETS
    if (idx < 0) idx = 0;
    if (idx > N_W_BUCKETS) idx = N_W_BUCKETS;
    return S_LUT[idx];
}

// ---------------------------------------------------------------------------
// Öğrenme kuralı — dw = eta * G * Q * S, ve ağırlığa uygulanması
// (çekirdek formül DEĞİŞMEDİ; iz + erişilebilirlik uzantısı REV-LEARN)
// ---------------------------------------------------------------------------

inline fixed_t synapse_compute_dw(int r_pre, int r_post, fixed_t w, fixed_t eta) {
    fixed_t g   = synapse_G(r_pre, r_post);
    fixed_t q   = synapse_Q(r_pre, r_post);
    fixed_t s   = synapse_S(w);
    fixed_t gq  = fixed_mul(g, q);
    fixed_t gqs = fixed_mul(gq, s);
    return fixed_mul(gqs, eta);
}

// TODO: DOGRULANMADI (anayasa S0) — REV-LEARN iz/erişilebilirlik ritimleri.
// TRACE_MU=1/8 (iliski kuantumu ritim birligi; iz ~17 potansiyasyonda %90).
// AVAIL_LAMBDA: erisilebilirlik yari-omru ~140 tick (gating hafiza ritmi).
static const fixed_t TRACE_MU = fixed_from_double(0.125);
static const fixed_t AVAIL_LAMBDA = fixed_from_double(0.005);

// REV-LEARN dinamigi (minimal uzanti; G*Q*S cekirdegi aynen korunur):
//  - Potansiyasyon (dw_pot>0): w += dw_pot*(1+T) (iz-hizlandirmali yeniden
//    guc; T=0 saf durumda mevcut kuralla birebir ayni) + T += MU*(1-T)
//    (iz edinimi; doyar, ASLA sonmez — ogrenilmis varligin korunmasi).
//  - Kullanim-disi (dw_pot==0, T>0): w, T*WMAX tabanina gevser
//    (w -= LAM*(w-taban); iki yonde — zayiflama var, sifira UNUTMA YOK;
//    klasik weight-decay DEGIL).
//  - T==0 iken bozulma yok (saf sinaps mevcut davranista kalir).
//  - eta==0 iken dw_pot==0 ve T hep 0 kalir -> frozen yol bit-identical (J).
// Donus: potansiyasyon dw (>=0; onceki anlamiyla ayni — alt telemetri korunur).
inline fixed_t synapse_apply_learning(Synapse& syn, int r_pre, int r_post, fixed_t eta) {
    fixed_t dw = synapse_compute_dw(r_pre, r_post, syn.weight, eta);
#ifdef ABL_NO_TRACE
    syn.weight += dw;
    if (syn.weight < 0)     syn.weight = 0;
    if (syn.weight > W_MAX) syn.weight = W_MAX;
    return dw;
#else
    if (dw > 0) {
        syn.weight += fixed_mul(dw, FIXED_ONE + syn.trace);
        syn.trace += fixed_mul(TRACE_MU, FIXED_ONE - syn.trace);
        if (syn.trace > FIXED_ONE) syn.trace = FIXED_ONE;
    } else if (syn.trace > 0) {
        fixed_t floor = fixed_mul(syn.trace, W_MAX);
        syn.weight -= fixed_mul(AVAIL_LAMBDA, syn.weight - floor);
    }
    if (syn.weight < 0)     syn.weight = 0;
    if (syn.weight > W_MAX) syn.weight = W_MAX;
    return dw;
#endif
}

#endif // SYNAPSE_H
