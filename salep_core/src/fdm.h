#ifndef FDM_H
#define FDM_H

#include "neuron.h"

// ---------------------------------------------------------------------------
// FDM — Simultane frekans-bolu paylasim: dal-seviyesi PLIR + populasyon
//
// Topoloji: her bant icin N_POP uyeli populasyon (hepsi ayni tau; yalniz
// leak jitter farki). Ortak superpoze tel -> tum uyelerin Dal A'si.
// Sinaptik ogrenme YOK (kapsam disi; saf Katman-1 rezonator + populasyon
// kaniti). Kalibrasyon: validate_fdm.py (FDM_BW=1, LOCK=2*tau+bw,
// PULSE=0.8, N_POP=8, jitter +-150/1000, S2=%2+-%20).
//
// Anayasa §2: sabit boyutlu diziler (FDM_MAX_POP=14 tavan, aktif N ayri),
// cekirdekte float/double YOK (olcum main_fdm.cpp'de, HostController tarafi),
// dinamik bellek YOK. Tum rastgelelik tamsayi LCG ile deterministik.
//
// DURUST SINIRLAR (MC D7/D19/D17): harmonik cifte yavas-bant faz takibi
// bilgi-teorik belirsiz (ilk-darbe capasi); seyrek-yabanci tele
// alt-harmonik suruklenme (yeniden-kilit bedeli); 3. bant es-zamanli
// baslangicta capalanamiyor -> yalniz 2 bant aktif (3. slot headroom).
// ---------------------------------------------------------------------------

constexpr int FDM_MAX_BANDS = 3;   // tahsis tavani; aktif bant sayisi ayri
constexpr int FDM_MAX_POP   = 14;  // MC tarama tavani (D5: 4..14 duz)
constexpr int FDM_TAU_MAX   = 16;  // faz histogrami tavan boyu

// Kalibre sabitler (validate_fdm.py D11/D17/D4/D5).
constexpr int32_t FDM_BW    = 1;    // PLIR rezonans bandi (tick)
constexpr fixed_t FDM_PULSE = fixed_from_double(0.8);
constexpr int FDM_N_POP     = 8;    // varsayilan populasyon
constexpr int FDM_JITTER_PM = 150;  // leak jitter +-150/1000 (+-%15, D5/D9)

// S2 gurultu (D6): %2 ekstra darbe + +-%20 genlik jitter (tamsayi LCG).
constexpr int FDM_NOISE_PCT = 2;
constexpr int FDM_AMPJIT_PM = 200;  // +-200/1000

struct FdmNetwork {
    DendriticNeuron band[FDM_MAX_BANDS][FDM_MAX_POP];
    int num_bands;
    int32_t tau[FDM_MAX_BANDS];
    int pop[FDM_MAX_BANDS];
};

// --- Deterministik tamsayi LCG (stimulus + jitter; cekirdek-ici) -----------
inline uint32_t fdm_lcg_next(uint32_t& state) {
    state = 1664525u * state + 1013904223u;
    return state;
}

// --- Bant bazinda noron parametresi (MC BAND_LEAK ikizi) -------------------
// Hizli bant = yuksek leak (C++ make_pre_params ile ayni kural); yavas
// bant = dusuk leak. Bu BAND TERCiHi DEGiL: bant-disi girdi PLIR kapisinda
// mu=0 ile silinir; leak yalniz bant-ici ates firsatini esitler (§9.6'daki
// kalibrasyon disiplini). PLIR opt-in: plir_mode=1, bw=FDM_BW,
// lock=2*tau+bw (acikca; neuron.h fallback'i emniyet).
inline NeuronParams fdm_band_params(int32_t tau, int32_t plir_mode) {
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
    p.resonance_bw = FDM_BW;
    p.plir_mode = plir_mode;
    p.plir_lock_lost = 2 * tau + FDM_BW;
    return p;
}

inline void fdm_init(FdmNetwork& net, const int32_t taus[],
                     const int pops[], int nbands, int32_t plir_mode,
                     uint32_t lcg_seed) {
    net.num_bands = nbands;
    uint32_t st = lcg_seed;
    for (int b = 0; b < nbands; ++b) {
        net.tau[b] = taus[b];
        net.pop[b] = pops[b];
        NeuronParams base = fdm_band_params(taus[b], plir_mode);
        for (int m = 0; m < pops[b]; ++m) {
            NeuronParams p = base;
            // Leak jitter: +-150/1000, uye basina deterministik (tamsayi).
            int32_t r = (int32_t)(fdm_lcg_next(st) % 301u) - 150;  // [-150,150]
            p.root_leak *= (1000.0 + r) / 1000.0;
            p.brA_leak *= (1000.0 + r) / 1000.0;
            p.brB_leak *= (1000.0 + r) / 1000.0;
            neuron_init_with_params(net.band[b][m],
                                    b * FDM_MAX_POP + m, p);
        }
    }
}

struct FdmTickFires {
    bool fired[FDM_MAX_BANDS][FDM_MAX_POP];
};

// Tick sirasi: tel>0 ise tum aktif uyelerin Dal A'sina enjekte et, hepsini
// tick'le, ates bayraklarini dondur. Ogrenme YOK (saf rezonator olcumu).
inline FdmTickFires fdm_tick(FdmNetwork& net, int32_t t, fixed_t wire) {
    FdmTickFires out;
    for (int b = 0; b < FDM_MAX_BANDS; ++b) {
        for (int m = 0; m < FDM_MAX_POP; ++m) {
            out.fired[b][m] = false;
        }
    }
    if (wire > 0) {
        for (int b = 0; b < net.num_bands; ++b) {
            for (int m = 0; m < net.pop[b]; ++m) {
                neuron_inject_current(net.band[b][m],
                                      net.band[b][m].branch_A_id, wire, t);
            }
        }
    }
    for (int b = 0; b < net.num_bands; ++b) {
        for (int m = 0; m < net.pop[b]; ++m) {
            out.fired[b][m] = neuron_tick(net.band[b][m], t);
        }
    }
    return out;
}

#endif  // FDM_H
