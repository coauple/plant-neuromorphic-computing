// ---------------------------------------------------------------------------
// PATTERN LOB — REV4 GERCEK K4 (58 node; nihai mimari, 2026-09-19 onayli).
// NIHAI PATTERN LOB: v2/v3/v3c/v3d/v3e silindi; v3e govdesi asagida
// dondurulmus kopya olarak gomulu (V3E VENDORED BOLGE, F1). Degismez:
// neuron.h, compartment.h, synapse.h, CMakeLists.txt, encoder/,
// frozen artefaktlar, kanonik CSV'ler.
//
// Mimari (REV4 prensibi): K4, diger K4'lerden aldigi relational coincidence
// bilgisini kendi elektriksel durumuna entegre eden, K1-K3 ile soma uzerinde
// PARALEL calisan gercek bir compartment'tir. K1-K3 = "ne oldu?";
// K4 = "baska nerede/ney ile birlikte oldu?"; soma = "ateslemeye deger mi?".
//
//   BRANCH --+-- K1 --+
//            +-- K2 --+-- S123 --+
//            +-- K3 --+          +--> SOMA (iki asamali: S123 frozen, +S4)
//            +-- K4 --+-- S4 ----+      ^
//                   ↕                (S123+S4 > esik -> ates + eslesik reset)
//              diger K4'ler
//
// K4 seri DEGIL (koke drive YOK; v4c_apply_drive silindi). K4'un voltaji,
// leak'i, gating'i, esik davranisi, spike/event durumu gercek (Compartment).
// Yerel giris: kendi dalinin K1,K2,K3 voltajlari (pre-reset snapshot) ->
// nicemlenmis imza q[3] (-3..+3, GATING_ACTIVATE_THRESH merdiveni).
// K4<->K4 kanali: r[b1][b2] (58x58 simetrik, 1653 cift; A-A, A-B, B-B dahil).
// Dal olayi mevcut bilgiden turetilir: injected[]'te o dalin sinapsi
// isaretliyse dal olay aldi (YENI kaynak yok).
//
// Iliski kurali (coincidence + kademeli kimlik kapisi; taban-kontrast yok):
//   sim = SUM(6-|dq|)/18 -> pay 0..18 (birebir 18, yakin-kacirma 13..17)
//   coin = iki dal da son 10 tick'te olay aldi (COINCIDENCE_WINDOW_MS)
//   r <- clip(r + ETA*[sim>=13]*coin - LEAK*r, 0, REL_MAX)  // simetrik
// Surum (spike-kapili max-secimi; partnerin SPIKE'i okunur):
//   rel_b = max_{c}(r[b][c] * [sim(b,c)>=13] * [c son 10 tick'te spike])
//   top_b = argmax (esitlikte kucuk indis; sifirsa -1) — mekanizma.
//   rel_b <= 1 yapisal (r<=1, kapi/spike ikili).
// K4 tick: V4 += LOC*(kendi-dal-olayi) + rel; leak; gating; V4>esik ->
//   spike + V4=V_RESET (F1 reset aynasi; gating'e dokunulmaz).
// Soma: S123 frozen (p3x3_tick); S4 = min(S4_CAP, GAIN*(VgA+VgB)).
//   F1 ateslediyse K4 eslesik resetlenir (V4=V_RESET). Ateslemediyse
//   S123+S4 > esik -> K4-kaynakli ates (frozen resetin aynasi + K4 reset).
//
// N kapisi yapisal: S4 <= S4_CAP (min) ve S4_CAP < V_THRESHOLD oldugundan
// K4 tek basina somayi atesletemez (kazanc degerinden bagimsiz).
// V4 siniri yapisal: girdi <= LOC + 1 (rel<=1) -> V4* <= 1.125/0.08 = 14.0625
// (M kapisi 15 marjiyla dener).
//
// S4_CAP = 0.25 N-turetilmis BASLANGIC siniridir (FROZEN DEGIL; U6 pilotu
// mekanik dogrular, revizyon onaya tabi). Basari olcutu S4 buyuklugu DEGIL,
// K4 state + argmax kimligin somaya nedensel yansimasidir (S kapisi).
// TODO: DOGRULANMADI (anayasa S0) — SIM_MIN_NUM, SOMA_GAIN; KUCUK pilot
// disi genelleme YOK.
// ---------------------------------------------------------------------------

#ifndef PATTERN_LOBE_H
#define PATTERN_LOBE_H

#include <cstdint>
#include "fixed_point.h"
#include "compartment.h"
// ---- V3E VENDORED BOLGE BASI (dondurulmus kopya, 2026-09-19 kabul) ----
// v3e (pattern_unit_v3e.h, 2026-09-17) dosyasi kabulde silindiginden, F1 +
// gorev-matrisi + ogrenme portu buraya VERBATIM gomuldu (davranis degisikligi
// YOK; J kapisi kayitli v3e hash'leriyle yeniden kanitlanir). Yalniz v3e'nin
// kendi include-guard satirlari dustu (ic-ice guard kargasasi olmasin diye);
// icerik satirlari birebir aynidir. Bu bolgeye mudahale YOK (donuk).
#include <cstdint>
#include "fixed_point.h"
#include "compartment.h"
#include "neuron.h"    // salt-okunur: V_THRESHOLD/V_REST/V_RESET/DIFFUSION_COEFF/
                       // COINCIDENCE_WINDOW_MS/COINCIDENCE_BONUS
#include "synapse.h"   // salt-okunur: Synapse + init/transmission/learning

constexpr int P3X3_NCOMP = 7;
constexpr int P3X3_N     = 29;   // kapasite (pattern sayisi DEGIL)
constexpr int P3X3_NSYN  = 18;   // kompartman-basina-tek degil, slot-basina-ayri

constexpr int P3X3_ROOT = 0;
constexpr int P3X3_A_K1 = 1;
constexpr int P3X3_A_K2 = 2;
constexpr int P3X3_A_K3 = 3;
constexpr int P3X3_B_K1 = 4;
constexpr int P3X3_B_K2 = 5;
constexpr int P3X3_B_K3 = 6;

constexpr int P3X3_OPEN = -1;

// Sinaps indis haritasi (18):
// 0-2 K1A(c/m/p), 3-4 K2A, 5-6 K3A-anchor, 7-8 K3A-follower,
// 9-11 K1B(c/m/p), 12-13 K2B, 14-15 K3B-anchor, 16-17 K3B-follower.
constexpr int P3X3_I_K1A = 0;
constexpr int P3X3_I_K2A = 3;
constexpr int P3X3_I_K3AA = 5;
constexpr int P3X3_I_K3AF = 7;
constexpr int P3X3_I_K1B = 9;
constexpr int P3X3_I_K2B = 12;
constexpr int P3X3_I_K3BA = 14;
constexpr int P3X3_I_K3BF = 16;

static const fixed_t P3X3_G_ROOT = fixed_from_double(0.30);
static const fixed_t P3X3_D_CHILD = fixed_from_double(0.15);
static const fixed_t P3X3_RING = fixed_from_double(0.2);    // K1 halka (v3d ayni)
static const fixed_t P3X3_FOLLOW = fixed_from_double(0.5);  // K3 follower

struct P3x3Neuron {
    int neuron_id;
    int unit_index;             // 0..28 (P3a=0 .. P3ac=28)
    Compartment c[P3X3_NCOMP];
    fixed_t soma_voltage;
    fixed_t threshold;
    int32_t last_fire_time_ms;
    int32_t dalA_last_input_tick;
    int32_t dalB_last_input_tick;
};

inline void p3x3_set_params(P3x3Neuron& n, int k,
                            double leak, double gdecay) {
    compartment_init(n.c[k]);
    n.c[k].leak_rate         = fixed_from_double(leak);
    n.c[k].gating_decay_rate = fixed_from_double(gdecay);
    n.c[k].parent_id         = P3X3_ROOT;
}

inline void p3x3_init(P3x3Neuron& n, int id, int unit_index) {
    n.neuron_id   = id;
    n.unit_index  = unit_index;
    n.threshold   = V_THRESHOLD;
    n.soma_voltage = V_REST;
    n.last_fire_time_ms   = -1;
    n.dalA_last_input_tick = -1;
    n.dalB_last_input_tick = -1;
    p3x3_set_params(n, P3X3_ROOT, 0.08, 0.005);
    p3x3_set_params(n, P3X3_A_K1, 0.06, 0.004);
    p3x3_set_params(n, P3X3_B_K1, 0.04, 0.003);
    p3x3_set_params(n, P3X3_A_K2, 0.10, 0.010);
    p3x3_set_params(n, P3X3_B_K2, 0.04, 0.003);
    p3x3_set_params(n, P3X3_A_K3, 0.02, 0.002);
    p3x3_set_params(n, P3X3_B_K3, 0.04, 0.003);
}

inline void p3x3_inject(P3x3Neuron& n, int k, fixed_t current,
                        int32_t current_time_ms) {
    n.c[k].local_voltage += current;
    if (k >= P3X3_A_K1 && k <= P3X3_A_K3) {
        n.dalA_last_input_tick = current_time_ms;
    } else if (k >= P3X3_B_K1 && k <= P3X3_B_K3) {
        n.dalB_last_input_tick = current_time_ms;
    }
}

// F1 tick: v3d ile birebir (snapshot kok + snapshot cocuk + sizinti/gating/
// soma/ates-reset sirasi). Dokunulmadi.
inline bool p3x3_tick(P3x3Neuron& n, int32_t current_time_ms) {
    fixed_t snap[P3X3_NCOMP];
    for (int i = 0; i < P3X3_NCOMP; ++i) {
        snap[i] = n.c[i].local_voltage;
    }
    for (int k = P3X3_A_K1; k < P3X3_NCOMP; ++k) {
        fixed_t diff = snap[k] - snap[P3X3_ROOT];
        n.c[P3X3_ROOT].local_voltage +=
            fixed_mul(fixed_mul(P3X3_G_ROOT, fixed_from_double(1.0 / 6.0)),
                      diff);
    }
    for (int k = P3X3_A_K1; k < P3X3_NCOMP; ++k) {
        fixed_t diff = snap[P3X3_ROOT] - snap[k];
        n.c[k].local_voltage += fixed_mul(P3X3_D_CHILD, diff);
    }
    for (int i = 0; i < P3X3_NCOMP; ++i) {
        compartment_apply_leak(n.c[i]);
    }
    for (int i = 0; i < P3X3_NCOMP; ++i) {
        compartment_update_gating(n.c[i]);
    }
    bool a_in = (n.dalA_last_input_tick >= 0) &&
                ((current_time_ms - n.dalA_last_input_tick)
                 <= COINCIDENCE_WINDOW_MS);
    bool b_in = (n.dalB_last_input_tick >= 0) &&
                ((current_time_ms - n.dalB_last_input_tick)
                 <= COINCIDENCE_WINDOW_MS);
    fixed_t eff_g = n.c[P3X3_ROOT].gating_state;
    if (a_in && b_in) {
        eff_g += COINCIDENCE_BONUS;
    }
    n.soma_voltage = fixed_mul(n.c[P3X3_ROOT].local_voltage,
                               FIXED_ONE + eff_g);
    bool fired = false;
    if (n.soma_voltage > n.threshold) {
        fired = true;
        n.last_fire_time_ms = current_time_ms;
        for (int i = 0; i < P3X3_NCOMP; ++i) {
            n.c[i].local_voltage = V_RESET;
        }
        n.soma_voltage = V_RESET;
    }
    return fired;
}

struct P3x3Wiring {
    int k1a_center;       // P3X3_OPEN veya 0..11
    bool k1a_confirmed;
    int k1b_center;       // P3X3_OPEN veya 0..11 (B-dali yoksa OPEN)
    bool k1b_confirmed;
    bool has_b;           // false: B-K1/K2/K3 hicsbiri kablolu degil
    int k2a_slot[2];      // secici K2 kumesi (yok: P3X3_OPEN)
    int k3a_anchor[2];    // anchor: tam genlik (yok: P3X3_OPEN)
    int k3a_follow[2];    // follower: 0.5x (yok: P3X3_OPEN)
    int k2b_slot[2];
    int k3b_anchor[2];
    int k3b_follow[2];
};

struct P3x3Unit {
    P3x3Neuron n;
    P3x3Wiring w;
    Synapse wk1c, wk1m, wk1p;
    Synapse wk2a[2];
    Synapse wk3aA[2], wk3aF[2];
    Synapse wk1bc, wk1bm, wk1bp;
    Synapse wk2b[2];
    Synapse wk3bA[2], wk3bF[2];
    SpikeRateCounter rc_pre[P3X3_NSYN];
    SpikeRateCounter rc_post[P3X3_NSYN];
};

inline Synapse* p3x3_syn(P3x3Unit& u, int k) {
    Synapse* ws[P3X3_NSYN] = {&u.wk1c, &u.wk1m, &u.wk1p,
                              &u.wk2a[0], &u.wk2a[1],
                              &u.wk3aA[0], &u.wk3aA[1],
                              &u.wk3aF[0], &u.wk3aF[1],
                              &u.wk1bc, &u.wk1bm, &u.wk1bp,
                              &u.wk2b[0], &u.wk2b[1],
                              &u.wk3bA[0], &u.wk3bA[1],
                              &u.wk3bF[0], &u.wk3bF[1]};
    return ws[k];
}

// Sinaps k BAGLI mi (kablosuz sinaps ogrenmeye girmez, agirlik w0'da kalir)?
inline bool p3x3_k_wired(const P3x3Unit& u, int k) {
    if (k < 3) return u.w.k1a_center != P3X3_OPEN;
    if (k < 5) return u.w.k2a_slot[k - P3X3_I_K2A] != P3X3_OPEN;
    if (k < 7) return u.w.k3a_anchor[k - P3X3_I_K3AA] != P3X3_OPEN;
    if (k < 9) return u.w.k3a_follow[k - P3X3_I_K3AF] != P3X3_OPEN;
    if (k < 12) return u.w.has_b && u.w.k1b_center != P3X3_OPEN;
    if (k < 14) return u.w.k2b_slot[k - P3X3_I_K2B] != P3X3_OPEN;
    if (k < 16) return u.w.k3b_anchor[k - P3X3_I_K3BA] != P3X3_OPEN;
    return u.w.k3b_follow[k - P3X3_I_K3BF] != P3X3_OPEN;
}

inline void p3x3unit_init(P3x3Unit& u, int unit_index,
                          int k1a_center, bool k1a_confirmed,
                          int k1b_center, bool k1b_confirmed, bool has_b,
                          const int k2a[2], const int k3aa[2],
                          const int k3af[2], const int k2b[2],
                          const int k3ba[2], const int k3bf[2]) {
    p3x3_init(u.n, 6000 + unit_index, unit_index);
    u.w.k1a_center    = k1a_center;
    u.w.k1a_confirmed = k1a_confirmed;
    u.w.k1b_center    = k1b_center;
    u.w.k1b_confirmed = k1b_confirmed;
    u.w.has_b         = has_b;
    for (int j = 0; j < 2; ++j) {
        u.w.k2a_slot[j]   = k2a[j];
        u.w.k3a_anchor[j] = k3aa[j];
        u.w.k3a_follow[j] = k3af[j];
        u.w.k2b_slot[j]   = k2b[j];
        u.w.k3b_anchor[j] = k3ba[j];
        u.w.k3b_follow[j] = k3bf[j];
    }
    synapse_init(u.wk1c, 6000 + unit_index, 1, fixed_from_double(1.0));
    synapse_init(u.wk1m, 6100 + unit_index, 1, fixed_from_double(1.0));
    synapse_init(u.wk1p, 6200 + unit_index, 1, fixed_from_double(1.0));
    for (int j = 0; j < 2; ++j) {
        synapse_init(u.wk2a[j], 6300 + unit_index * 2 + j, 1,
                     fixed_from_double(1.0));
        synapse_init(u.wk3aA[j], 6400 + unit_index * 2 + j, 1,
                     fixed_from_double(1.0));
        synapse_init(u.wk3aF[j], 6500 + unit_index * 2 + j, 1,
                     fixed_from_double(1.0));
        synapse_init(u.wk2b[j], 6600 + unit_index * 2 + j, 1,
                     fixed_from_double(1.0));
        synapse_init(u.wk3bA[j], 6700 + unit_index * 2 + j, 1,
                     fixed_from_double(1.0));
        synapse_init(u.wk3bF[j], 6800 + unit_index * 2 + j, 1,
                     fixed_from_double(1.0));
    }
    synapse_init(u.wk1bc, 6700 + unit_index, 1, fixed_from_double(1.0));
    synapse_init(u.wk1bm, 6800 + unit_index, 1, fixed_from_double(1.0));
    synapse_init(u.wk1bp, 6900 + unit_index, 1, fixed_from_double(1.0));
    for (int k = 0; k < P3X3_NSYN; ++k) {
        rate_counter_init(u.rc_pre[k]);
        rate_counter_init(u.rc_post[k]);
    }
}

// ONAYLI TAM GOREV MATRISI (2026-09-17; A dali 27 birim + B dali).
// P3ab/ac (27,28): OPEN/sessiz. P3a,b,c,e,f (0,1,2,4,5): B-dali YOK.
inline void p3x3unit_init_table(P3x3Unit& u, int unit_index) {
    static const int kA[27] = {1, 4, 7, 5, 6, 0,
                               1, 4, 2, 3, 6, 4, 6, 4, 5, 5, 7, 6, 6, 7, 1,
                               6, 5, 1, 4, 7, 5};
    static const int k2A[27][2] = {{0,1},{1,3},{4,6},{2,4},{3,5},{0,1},
                                   {0,1},{1,3},{1,2},{0,2},{3,5},{1,3},{3,5},
                                   {1,3},{2,4},{2,4},{4,6},{3,5},{3,5},{4,6},
                                   {0,1},{3,5},{2,4},{0,1},{1,3},{4,6},{2,4}};
    static const int k3Aa[27][2] = {{4,-1},{1,7},{4,-1},{2,-1},{3,-1},{3,-1},
                                    {4,-1},{1,7},{5,-1},{0,6},{3,-1},{1,7},
                                    {3,-1},{1,7},{2,-1},{2,-1},{4,-1},{3,-1},
                                    {3,-1},{4,-1},{4,-1},{3,-1},{2,-1},{4,-1},
                                    {1,7},{4,-1},{2,-1}};
    static const int k3Af[27][2] = {{0,2},{3,5},{6,-1},{4,6},{5,7},{1,-1},
                                    {0,2},{3,5},{1,3},{2,4},{5,7},{3,5},
                                    {5,7},{3,5},{4,6},{4,6},{6,-1},{5,7},
                                    {5,7},{6,-1},{0,2},{5,7},{4,6},{0,2},
                                    {3,5},{6,-1},{4,6}};
    // B dali: YOK (0,1,2,4,5); VAR (3,6..26). B degerleri onayli matristen.
    static const int kHasB[27] = {0,0,0,1,0,0,
                                  1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,
                                  1,1,1,1,1,1};
    static const int kB[27] = {-1,-1,-1,6,-1,-1,
                               4,7,5,6,7,5,5,6,4,7,6,1,4,5,6,
                               6,5,1,4,7,1};
    static const int k2B[27][2] = {{-1,-1},{-1,-1},{-1,-1},{3,5},{-1,-1},
                                   {-1,-1},
                                   {1,3},{4,6},{2,4},{3,5},{4,6},{2,4},{2,4},
                                   {3,5},{1,3},{4,6},{3,5},{0,1},{1,3},{2,4},
                                   {3,5},{3,5},{2,4},{0,1},{1,3},{4,6},{0,1}};
    static const int k3Ba[27][2] = {{-1,-1},{-1,-1},{-1,-1},{3,-1},{-1,-1},
                                    {-1,-1},
                                    {1,7},{4,-1},{2,-1},{3,-1},{4,-1},{2,-1},
                                    {2,-1},{3,-1},{1,7},{4,-1},{3,-1},{4,-1},
                                    {1,7},{2,-1},{3,-1},{3,-1},{2,-1},{4,-1},
                                    {1,7},{4,-1},{4,-1}};
    static const int k3Bf[27][2] = {{-1,-1},{-1,-1},{-1,-1},{5,7},{-1,-1},
                                    {-1,-1},
                                    {3,5},{6,-1},{4,6},{5,7},{6,-1},{4,6},
                                    {4,6},{5,7},{3,5},{6,-1},{5,7},{0,2},
                                    {3,5},{4,6},{5,7},{5,7},{4,6},{0,2},
                                    {3,5},{6,-1},{0,2}};
    if (unit_index < 0 || unit_index >= 29) return;
    if (unit_index >= 27) {
        static const int none[2] = {P3X3_OPEN, P3X3_OPEN};
        p3x3unit_init(u, unit_index, P3X3_OPEN, false, P3X3_OPEN, false,
                      false, none, none, none, none, none, none);
        return;
    }
    bool hb = kHasB[unit_index] != 0;
    p3x3unit_init(u, unit_index, kA[unit_index], true,
                  kB[unit_index], hb && kB[unit_index] >= 0, hb,
                  k2A[unit_index], k3Aa[unit_index], k3Af[unit_index],
                  k2B[unit_index], k3Ba[unit_index], k3Bf[unit_index]);
}

// Tek afferent olayin (post slot s) birim-ici dagitimi: gorev kumesi-disi
// slotlar ilgili kompartmana akim VERMEZ. injected[] ogrenme sayaclarina
// birebir girer (slot-basina-ayri sinaps + sayac).
inline void p3x3unit_drive(P3x3Unit& u, int s, int32_t t,
                           bool injected[P3X3_NSYN]) {
    int c = u.w.k1a_center;
    if (c != P3X3_OPEN) {
        if (s == c) {
            p3x3_inject(u.n, P3X3_A_K1,
                        synapse_transmission_current(u.wk1c), t);
            injected[P3X3_I_K1A] = true;
        } else if (s == (c + 11) % 12) {
            p3x3_inject(u.n, P3X3_A_K1,
                        fixed_mul(synapse_transmission_current(u.wk1m),
                                  P3X3_RING), t);
            injected[P3X3_I_K1A + 1] = true;
        } else if (s == (c + 1) % 12) {
            p3x3_inject(u.n, P3X3_A_K1,
                        fixed_mul(synapse_transmission_current(u.wk1p),
                                  P3X3_RING), t);
            injected[P3X3_I_K1A + 2] = true;
        }
    }
    for (int j = 0; j < 2; ++j) {
        if (u.w.k2a_slot[j] == s) {
            p3x3_inject(u.n, P3X3_A_K2,
                        synapse_transmission_current(u.wk2a[j]), t);
            injected[P3X3_I_K2A + j] = true;
        }
        if (u.w.k3a_anchor[j] == s) {
            p3x3_inject(u.n, P3X3_A_K3,
                        synapse_transmission_current(u.wk3aA[j]), t);
            injected[P3X3_I_K3AA + j] = true;
        }
        if (u.w.k3a_follow[j] == s) {
            p3x3_inject(u.n, P3X3_A_K3,
                        fixed_mul(synapse_transmission_current(u.wk3aF[j]),
                                  P3X3_FOLLOW), t);
            injected[P3X3_I_K3AF + j] = true;
        }
    }
    if (!u.w.has_b) return;
    int cb = u.w.k1b_center;
    if (cb != P3X3_OPEN) {
        if (s == cb) {
            p3x3_inject(u.n, P3X3_B_K1,
                        synapse_transmission_current(u.wk1bc), t);
            injected[P3X3_I_K1B] = true;
        } else if (s == (cb + 11) % 12) {
            p3x3_inject(u.n, P3X3_B_K1,
                        fixed_mul(synapse_transmission_current(u.wk1bm),
                                  P3X3_RING), t);
            injected[P3X3_I_K1B + 1] = true;
        } else if (s == (cb + 1) % 12) {
            p3x3_inject(u.n, P3X3_B_K1,
                        fixed_mul(synapse_transmission_current(u.wk1bp),
                                  P3X3_RING), t);
            injected[P3X3_I_K1B + 2] = true;
        }
    }
    for (int j = 0; j < 2; ++j) {
        if (u.w.k2b_slot[j] == s) {
            p3x3_inject(u.n, P3X3_B_K2,
                        synapse_transmission_current(u.wk2b[j]), t);
            injected[P3X3_I_K2B + j] = true;
        }
        if (u.w.k3b_anchor[j] == s) {
            p3x3_inject(u.n, P3X3_B_K3,
                        synapse_transmission_current(u.wk3bA[j]), t);
            injected[P3X3_I_K3BA + j] = true;
        }
        if (u.w.k3b_follow[j] == s) {
            p3x3_inject(u.n, P3X3_B_K3,
                        fixed_mul(synapse_transmission_current(u.wk3bF[j]),
                                  P3X3_FOLLOW), t);
            injected[P3X3_I_K3BF + j] = true;
        }
    }
}

// Ogrenme portu (soma-as-post; v3d ile birebir KURAL/sayac; yalniz BAGLI
// sinapslar; kablosuz sinaps agirligi w0'da kalir).
inline void p3x3unit_learn(P3x3Unit& u, const bool injected[P3X3_NSYN],
                           bool fired, fixed_t eta) {
    for (int k = 0; k < P3X3_NSYN; ++k) {
        if (!p3x3_k_wired(u, k)) continue;
        rate_counter_update(u.rc_pre[k], injected[k]);
        rate_counter_update(u.rc_post[k], fired);
        synapse_apply_learning(*p3x3_syn(u, k), u.rc_pre[k].count,
                               u.rc_post[k].count, eta);
    }
}

// ---- V3E VENDORED BOLGE SONU ----
#include "neuron.h"            // salt-okunur: COINCIDENCE_WINDOW_MS

constexpr int V4C_NDAL = 2;                 // dal: 0=A, 1=B
constexpr int V4C_NB = P3X3_N * V4C_NDAL;   // 58 K4 node; bid = unit*2+dal
constexpr int V4C_MEM_CAP = 4096;  // Pattern Memory tavani (eski PL_MEM_CAP)

// SPEC_v0_1 portu (pattern_lobe.h'den VERBATIM vendored kopya, 2026-09-19):
// post_id 0..11 disi -> -1; tau_b 4..60 disi -> -1. Sessiz %12 sarmasi YOK.
constexpr int32_t PL_PHASE_SLOTS = 12;
constexpr int32_t PL_PHI_FULL_X100 = 36000;
constexpr int32_t PL_PHI_ID_STEP_X100 = 3000;  // 36000/12
constexpr int32_t PL_TAU_LO = 4;
constexpr int32_t PL_TAU_HI_EXCL = 61;
constexpr int32_t PL_TAU_SPAN = 57;

inline int32_t pl_phi_id_of(int post_id) {
    if (post_id < 0 || post_id >= PL_PHASE_SLOTS) return -1;
    return post_id * PL_PHI_ID_STEP_X100;
}

inline int32_t pl_phi_tau_of(int tau_b) {
    if (tau_b < PL_TAU_LO || tau_b >= PL_TAU_HI_EXCL) return -1;
    return ((tau_b - PL_TAU_LO) * PL_PHI_FULL_X100) / PL_TAU_SPAN;
}

// TODO: DOGRULANMADI, bkz. pilot v4c-02 (anayasa S0) + REV4 TEST-B pilotu.
// SIM_MIN_NUM=13/18 (birebir 18, yakin-kacirma 13..17 gecer; R6-capraz 12
// ve uzak <=12 gecemez). REL_ETA=REL_LEAK=1/8 ritmi korunur (denge 1;
// coin kesilince yari-omur ~5 tick). V4C_K4_LOC=1/8 ayni 1/8 kuantumdur
// (ritim birligi; yeni sayi degil). V4C_SOMA_GAIN=0.125 (TODO) +
// V4C_S4_CAP=0.25 N-turetilmis BASLANGIC siniridir (FROZEN DEGIL).
static const fixed_t V4C_REL_ETA = fixed_from_double(0.125);
static const fixed_t V4C_REL_LEAK = fixed_from_double(0.125);
static const fixed_t V4C_REL_MAX = FIXED_ONE;
static const fixed_t V4C_K4_LOC = fixed_from_double(0.125);
static const fixed_t V4C_SOMA_GAIN = fixed_from_double(0.125);
static const fixed_t V4C_S4_CAP = fixed_from_double(0.25);

constexpr int V4C_SIM_MIN_NUM = 13;  // kademeli uyum payi esigi (0..18)
constexpr int V4C_SIM_DEN = 18;

// Dal kimligi (ham): o dalin 3 K-kompartman voltaji (drive-sonrasi snapshot).
struct V4cIdentity {
    fixed_t v[3];
};

inline void v4c_snapshot_branch(const P3x3Unit& u, int dal, V4cIdentity& id) {
    if (dal == 0) {
        id.v[0] = u.n.c[P3X3_A_K1].local_voltage;
        id.v[1] = u.n.c[P3X3_A_K2].local_voltage;
        id.v[2] = u.n.c[P3X3_A_K3].local_voltage;
    } else {
        id.v[0] = u.n.c[P3X3_B_K1].local_voltage;
        id.v[1] = u.n.c[P3X3_B_K2].local_voltage;
        id.v[2] = u.n.c[P3X3_B_K3].local_voltage;
    }
}

// Nicemlenmis dal imzasi: slot-basina -3..+3 (GATING_ACTIVATE_THRESH
// merdiveni; mevcut esikten baska esik YOK).
struct V4cSig {
    int8_t q[3];
};

inline void v4c_quantize(const V4cIdentity& id, V4cSig& s) {
    fixed_t t1 = GATING_ACTIVATE_THRESH;
    fixed_t t2 = t1 + t1;
    fixed_t t3 = t2 + t1;
    for (int k = 0; k < 3; ++k) {
        fixed_t v = id.v[k];
        int8_t m = 0;
        if (v < 0) {
            fixed_t a = -v;
            if (a > t1) m = -1;
            if (a > t2) m = -2;
            if (a > t3) m = -3;
        } else {
            if (v > t1) m = 1;
            if (v > t2) m = 2;
            if (v > t3) m = 3;
        }
        s.q[k] = m;
    }
}

// Kademeli uyum payi 0..18 (slot-basina 6-|dq|; birebir=18).
inline int v4c_sim_num(const V4cSig& a, const V4cSig& b) {
    int n = 0;
    for (int k = 0; k < 3; ++k) {
        int dq = (int)a.q[k] - (int)b.q[k];
        if (dq < 0) dq = -dq;
        n += 6 - dq;
    }
    return n;
}

// K4<->K4 iliski agi: 58x58 simetrik matris (1653 cift). Sabit dizi,
// dinamik bellek yok. Ogrenme K1/K2/K3 portuna GIRMEZ (kural bozulmaz).
struct V4cK4Net {
    fixed_t r[V4C_NB][V4C_NB];
};

inline void v4c_net_init(V4cK4Net& net) {
    for (int a = 0; a < V4C_NB; ++a)
        for (int b = 0; b < V4C_NB; ++b) net.r[a][b] = 0;
}

// Bir tick'in iliski asamasi: 1653 cift, deterministik sira (a<b).
// evt[bid] = o dalin son olay tick'i (-1 = henuz yok).
inline void v4c_net_update(V4cK4Net& net, const V4cSig* sigs,
                           const int32_t* evt, int32_t t) {
    for (int a = 0; a < V4C_NB; ++a) {
        bool ea = (evt[a] >= 0) && ((t - evt[a]) <= COINCIDENCE_WINDOW_MS);
        for (int b = a + 1; b < V4C_NB; ++b) {
            bool eb = (evt[b] >= 0) && ((t - evt[b]) <= COINCIDENCE_WINDOW_MS);
            bool coin = ea && eb;
            bool gate = coin &&
                        (v4c_sim_num(sigs[a], sigs[b]) >= V4C_SIM_MIN_NUM);
            fixed_t rij = net.r[a][b];
            if (gate) rij += V4C_REL_ETA;
            rij -= fixed_mul(V4C_REL_LEAK, rij);
            if (rij < 0) rij = 0;
            if (rij > V4C_REL_MAX) rij = V4C_REL_MAX;
            net.r[a][b] = rij;
            net.r[b][a] = rij;
        }
    }
}

// Surum: spike-kapili max-secimi — K4'ler birbirinin SPIKE'ini okur, siddet
// ogrenilmis r x guncel uyumdur. rel_b <= 1 yapisal (r<=1, kapi/spike ikili).
// top_b = argmax (esitlikte kucuk indis; sifirsa -1) — mekanizma, telemetri
// degil. pspk[c] = c dalinin son 10 tick'te K4 spike'i (COINCIDENCE_WINDOW).
inline fixed_t v4c_branch_rel(const V4cK4Net& net, const V4cSig* sigs,
                              const bool* pspk, int b, int& top) {
    fixed_t m = 0;
    top = -1;
    for (int c = 0; c < V4C_NB; ++c) {
        if (c == b || !pspk[c]) continue;
        if (v4c_sim_num(sigs[b], sigs[c]) < V4C_SIM_MIN_NUM) continue;
        if (net.r[b][c] > m) {
            m = net.r[b][c];
            top = c;
        }
    }
    return m;
}

// K4 kompartmanli birim: v3e birimi (F1, donuk) + dal-basina GERCEK K4
// compartment (voltaj/leak/gating/esik/spike). p3x3_tick K4'lere dokunamaz
// (ayri dizi); K4 kapaliyken butun K4 alanlari init degerinde kalir (J).
struct V4cUnit {
    P3x3Unit base;
    Compartment k4[V4C_NDAL];
    int32_t k4_last_evt[V4C_NDAL];    // dal son-olay tick'i (-1 = yok)
    int32_t k4_spike_tick[V4C_NDAL];  // son K4-spike tick'i (-1 = yok)
    bool k4_spiked[V4C_NDAL];         // bu tick K4 spike'i
    fixed_t k4_rel[V4C_NDAL];         // max-secimli iliski girdisi
    int k4_top[V4C_NDAL];             // argmax partner (-1 = yok)
    fixed_t k4_s4d[V4C_NDAL];         // dal S4 salimi (kapili voltaj)
    fixed_t k4_s4;                    // birim S4 toplami (cap'li)
};

inline void v4c_init(V4cUnit& u, int unit_index) {
    p3x3unit_init_table(u.base, unit_index);
    for (int d = 0; d < V4C_NDAL; ++d) {
        compartment_init(u.k4[d]);
        u.k4[d].leak_rate = fixed_from_double(0.08);  // kok ile ayni
        u.k4[d].gating_decay_rate = fixed_from_double(0.005);
        u.k4[d].parent_id = P3X3_ROOT;
        u.k4_last_evt[d] = -1;
        u.k4_spike_tick[d] = -1;
        u.k4_spiked[d] = false;
        u.k4_rel[d] = 0;
        u.k4_top[d] = -1;
        u.k4_s4d[d] = 0;
    }
    u.k4_s4 = 0;
}

// Dal olay bayragi: injected[]'te o dalin K1/K2/K3 sinapslarindan biri
// isaretliyse dal olay aldi. A: 0..8, B: 9..17 (v3e sinaps haritasi).
inline bool v4c_branch_event(const bool injected[P3X3_NSYN], int dal) {
    int lo = (dal == 0) ? 0 : 9;
    for (int k = lo; k < lo + 9; ++k) {
        if (injected[k]) return true;
    }
    return false;
}

// K4 tick: lokal sarj (kendi-dal-olayi) + iliskisel sarj -> leak -> gating ->
// esik/spike. Spike'ta V4=V_RESET (F1 reset aynasi; gating'e dokunulmaz).
// Donus: bu tick spike'i (spike_tick yalniz spike'ta yazilir).
inline bool v4c_k4_tick(Compartment& k, fixed_t local_charge, fixed_t rel_drive,
                        int32_t t, int32_t& spike_tick) {
    k.local_voltage += local_charge + rel_drive;
    compartment_apply_leak(k);
    compartment_update_gating(k);
    bool sp = (k.local_voltage > V_THRESHOLD);
    if (sp) {
        spike_tick = t;
        k.local_voltage = V_RESET;
    }
    return sp;
}

// K4 salimi: kapili voltaj (soma formuluyle ayni yapi V*(1+g)), negatif
// kirpilir. S4'un dal girdisidir.
inline fixed_t v4c_k4_release(const Compartment& k) {
    fixed_t vg = fixed_mul(k.local_voltage, FIXED_ONE + k.gating_state);
    return (vg < 0) ? 0 : vg;
}

// S4: min(CAP, GAIN*(vgA+vgB)) <= S4_CAP < V_THRESHOLD (N yapisal; kazanc
// degerinden bagimsiz — min cap'i garanti eder).
inline fixed_t v4c_soma_s4(fixed_t vgA, fixed_t vgB) {
    fixed_t s = fixed_mul(V4C_SOMA_GAIN, vgA + vgB);
    if (s < 0) s = 0;
    return (s > V4C_S4_CAP) ? V4C_S4_CAP : s;
}

// Eslesik reset: F1 ateslediginde K4'ler de V_RESET'e (gating'e dokunulmaz;
// frozen aynasi).
inline void v4c_k4_coupled_reset(Compartment k4[V4C_NDAL]) {
    for (int d = 0; d < V4C_NDAL; ++d) k4[d].local_voltage = V_RESET;
}

// K4-kaynakli soma atesi: frozen p3x3_tick resetinin birebir aynasi
// (last_fire + 7 bolme V_RESET + soma V_RESET; karsilastirma '>' frozenla
// ayni, esik b.n.threshold) + K4 eslesik reset. Yalniz fired_F1==false
// iken cagrilir (S123 hazir, s4 cap'li).
inline bool v4c_soma_fire(P3x3Unit& b, Compartment k4[V4C_NDAL], fixed_t s123,
                          fixed_t s4, int32_t t) {
    if (s123 + s4 > b.n.threshold) {
        b.n.last_fire_time_ms = t;
        for (int i = 0; i < P3X3_NCOMP; ++i) b.n.c[i].local_voltage = V_RESET;
        b.n.soma_voltage = V_RESET;
        v4c_k4_coupled_reset(k4);
        return true;
    }
    return false;
}

#endif  // PATTERN_LOBE_H
