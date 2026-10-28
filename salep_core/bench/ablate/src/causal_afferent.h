#ifndef CAUSAL_AFFERENT_H
#define CAUSAL_AFFERENT_H

#include <cstdint>
#include "fixed_point.h"

// ---------------------------------------------------------------------------
// AFFERENT kablo — Duyusal Lob -> Nedensellik (ARCHITECTURE.md §5.1)
//
// Olay yapisi + patlama adaptoru. Adaptor sensory_lobe.h ve causality.h'yi
// CAGIRIR, ikisini de degistirmez (yari-1 salt-okunur).
//
// Fizik: P2 olaylari yavas ritimlidir (tau 26..60); nedensellik pre'leri
// hizli calisir (tau 4/8/12/16). Adaptor her olayi hedef pre'nin kendi
// tau'sunda KISA PATLAMAYA cevirir (olay->patlama); patlama olay tick'inde
// baslar, olay periyodunu ASMAZ (zamanlama korunumu — MC kapisi).
// Nedensel-rol eslemesi (senaryo kablosu, harness tanimlar): once-gelen
// akim (neden) -> pre Dal A tarafi, sonra-gelen (etki) -> pre Dal B.
// ---------------------------------------------------------------------------

struct AfferentEvent {
    int32_t tick;     // lob saati (iki lob ayni t'de kosar)
    int32_t post_id;  // 0..63 (p2 index)
    int32_t tau_b;    // 4..60 (olculen periyot)
};

// Senaryo kablosu: hangi post, hangi pre'yi, nasil surer.
struct BurstSpec {
    int pre_idx;    // hedef pre (0..3)
    int n_pulse;    // patlama boyu (MC kalibre: 5@tau4, 2@tau12)
    int32_t step;   // pre tau adimi
};

constexpr int AFF_MAX_BURST = 8;  // eszamanli patlama tavani (malloc yok)

struct BurstAdapter {
    int pending_pre[AFF_MAX_BURST];
    int pending_left[AFF_MAX_BURST];
    int32_t pending_next[AFF_MAX_BURST];
    int32_t pending_step[AFF_MAX_BURST];
    fixed_t amp;      // patlama darbe genligi (kalibre 0.8)
    int n_pending;
    long drops;      // tampon tasmasi sayaci (kapi: 0 olmali)
};

inline void adapter_init(BurstAdapter& a, fixed_t amp) {
    a.amp = amp;
    a.n_pending = 0;
    a.drops = 0;
    for (int i = 0; i < AFF_MAX_BURST; ++i) {
        a.pending_pre[i] = -1;
        a.pending_left[i] = 0;
        a.pending_next[i] = 0;
        a.pending_step[i] = 0;
    }
}

// P2 atesi -> patlama cizelgele (ilk darbe bu tick'te).
inline void adapter_post_event(BurstAdapter& a, int32_t t,
                               const BurstSpec& spec) {
    if (a.n_pending >= AFF_MAX_BURST) {
        a.drops++;
        return;
    }
    int i = a.n_pending++;
    a.pending_pre[i] = spec.pre_idx;
    a.pending_left[i] = spec.n_pulse;
    a.pending_next[i] = t;
    a.pending_step[i] = spec.step;
}

// Bu tick'in uyaranini uret (causality_tick girdisi). Vadesi gelen
// darbe verilir, cizelge ilerletilir, biten duser.
inline void adapter_emit(BurstAdapter& a, int32_t t, fixed_t stim[4]) {
    for (int i = 0; i < 4; ++i) stim[i] = 0;
    for (int i = 0; i < a.n_pending;) {
        if (a.pending_next[i] <= t) {
            int p = a.pending_pre[i];
            // Biriktirmeli (+=): patlama sinirinda cakisan nabizlar MC
            // ikizdeki gibi cift genlik olur (iki taraf deterministik).
            if (p >= 0 && p < 4) stim[p] += a.amp;
            a.pending_left[i]--;
            a.pending_next[i] += a.pending_step[i];
            if (a.pending_left[i] <= 0) {
                int last = --a.n_pending;
                a.pending_pre[i] = a.pending_pre[last];
                a.pending_left[i] = a.pending_left[last];
                a.pending_next[i] = a.pending_next[last];
                a.pending_step[i] = a.pending_step[last];
                continue;
            }
        }
        ++i;
    }
}

#endif  // CAUSAL_AFFERENT_H
