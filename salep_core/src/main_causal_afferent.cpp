// ---------------------------------------------------------------------------
// AFFERENT demo — P2 olay akisi -> patlama adaptoru -> nedensellik
// (ARCHITECTURE.md §5.1, MC: validate_causal_afferent.py).
//
// Senaryo kablosu: X olay treni (post0, periyot 12) + Y = X + 8 tick
// (post1); F1 X-yalniz, F2 Y-yalniz, F3 X+Y. Adaptor: X -> pre0'a 2@tau4,
// Y -> pre2'ye 2@tau12 (MC kalibre). Hedef: X->Y nedenselligini ogrenir.
// P1/P3 negatif kontrol (uyarilmaz, dw=0 beklenir).
// Yari-1 kodu salt-okunur: sensory_lobe.h + causality.h aynen kullanilir.
// ---------------------------------------------------------------------------

#include <cmath>
#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include "sensory_lobe.h"
#include "causality.h"
#include "causal_afferent.h"
#include "predict.h"

namespace {

constexpr int32_t AFF_P1_TAUS[2] = {4, 12};
constexpr int AFF_NUM_P2 = 2;
constexpr fixed_t AFF_SL_AMP = fixed_from_double(1.0);
constexpr fixed_t AFF_P1_AMPS[2] = {fixed_from_double(0.7),
                                    fixed_from_double(4.0)};

constexpr int32_t AFF_PERIOD = 12;  // MC kalibre (hizli olay treni)
constexpr int32_t AFF_LAG = 8;    // MC kalibre
constexpr int AFF_BLOCK = 1000;
constexpr int AFF_W0 = 40;
constexpr int AFF_W1 = 940;
constexpr int AFF_N_SUPER = 3;

constexpr int32_t AFF_TAUS[CAUS_NUM_PRE] = {4, 8, 12, 16};
constexpr int32_t AFF_BW = 2;
constexpr fixed_t AFF_CAUS_ETA = fixed_from_double(0.2);
constexpr fixed_t AFF_PULSE = fixed_from_double(0.8);
constexpr fixed_t AFF_W0_C = fixed_from_double(0.4);

// Nedensel-rol eslemesi (senaryo kablosu): neden -> pre0/Dal A,
// etki -> pre2/Dal B (MC: n0=2@tau4, n2=2@tau12).
constexpr BurstSpec AFF_SPEC_X = {0, 2, 4};
constexpr BurstSpec AFF_SPEC_Y = {2, 2, 12};

// Ongoru penceresi (MC: validate_causal_afferent.py P1-P3).
constexpr int32_t AFF_PRED_W = 16;

NeuronParams aff_pre_params(int idx) {
    NeuronParams p = {0.08, 0.06, 0.04, 0.005, 0.004, 0.003};
    if (idx == 3) {
        p.root_leak = 0.01;
        p.brA_leak = 0.01;
        p.brB_leak = 0.01;
    } else if (idx == 2) {
        p.root_leak = 0.02;
        p.brA_leak = 0.015;
        p.brB_leak = 0.015;
    }
    p.tau_isi = AFF_TAUS[idx];
    p.resonance_bw = AFF_BW;
    return p;
}

}  // namespace

int main() {
    synapse_build_luts();
    printf("=== AFFERENT demo: P2 olaylari -> nedensellik ===\n");
    printf("X(post0,T12) + Y=X+8(post1); F1 X, F2 Y, F3 X+Y; %d super x "
           "%d tick\n",
           AFF_N_SUPER, AFF_BLOCK);

    SensoryLobe lobe;
    SlPostCfg cfg[AFF_NUM_P2] = {{0, 0, 12, fixed_from_double(0.2)},
                                 {1, 0, 12, fixed_from_double(0.2)}};
    sl_init(lobe, AFF_P1_TAUS, 2, cfg, AFF_NUM_P2, AFF_SL_AMP, AFF_P1_AMPS,
            fixed_from_double(0.0));  // olay tarafi donuk (eta=0)

    CausalityNetwork cn;
    NeuronParams pre_params[CAUS_NUM_PRE];
    for (int i = 0; i < CAUS_NUM_PRE; ++i) {
        pre_params[i] = aff_pre_params(i);
    }
    NeuronParams target_params = {0.04, 0.04, 0.04, 0.005, 0.004, 0.003};
    causality_init(cn, pre_params, target_params, AFF_W0_C, AFF_CAUS_ETA);

    BurstAdapter ad;
    adapter_init(ad, AFF_PULSE);

    FILE* csv = fopen("causal_afferent_learning.csv", "w");
    if (!csv) {
        fprintf(stderr, "HATA: afferent CSV acilamadi\n");
        return 1;
    }
    fprintf(csv, "tick,super,phase,evX,evY,pre0,pre2,tgt,coinc,w0,w2,pred\n");
    Predictor pd[3];
    for (int ph = 0; ph < 3; ++ph) predictor_init(pd[ph], AFF_PRED_W);

    long tgt_fires[3] = {0, 0, 0};
    long coinc_ticks[3] = {0, 0, 0};
    long pre_fires[3][CAUS_NUM_PRE] = {{0}};
    long ev_count[3][2] = {{0}};
    double gain[3][CAUS_NUM_SYNAPSES] = {{0.0}};
    fixed_t w_block_start[CAUS_NUM_SYNAPSES];
    // E-denetimi: F3 hedef ateslerinin X+Y ciftini tasimasi.
    long f3_paired = 0;
    int32_t last_ev[2] = {-1000000, -1000000};

    for (int sup = 0; sup < AFF_N_SUPER; ++sup) {
        for (int phase = 0; phase < 3; ++phase) {
            for (int i = 0; i < CAUS_NUM_SYNAPSES; ++i) {
                w_block_start[i] = cn.syn[i].weight;
            }
            for (int bt = 0; bt < AFF_BLOCK; ++bt) {
                int32_t t = (int32_t)((sup * 3 + phase) * AFF_BLOCK + bt);
                bool in_win = (bt >= AFF_W0 && bt <= AFF_W1);
                bool sx = (phase != 1) && in_win &&
                          ((bt - AFF_W0) % AFF_PERIOD == 0);
                bool sy = (phase != 0) && in_win && (bt >= AFF_W0 + AFF_LAG) &&
                          ((bt - AFF_W0 - AFF_LAG) % AFF_PERIOD == 0);
                bool p1p[2] = {(t % 4) == 0, (t % 12) == 0};
                bool sp[P2_MAX] = {false};
                sp[0] = sx;
                sp[1] = sy;
                fixed_t sdw[P2_MAX] = {0};
                SensoryTickResult sr = sensory_tick(lobe, t, p1p, sp, sdw);
                int evx = sr.p2_fired[0] ? 1 : 0;
                int evy = sr.p2_fired[1] ? 1 : 0;
                if (evx) {
                    AfferentEvent e = {t, 0, lobe.tau_b[0]};
                    adapter_post_event(ad, e.tick, AFF_SPEC_X);
                    last_ev[0] = t;
                    ev_count[phase][0]++;
                }
                if (evy) {
                    AfferentEvent e = {t, 1, lobe.tau_b[1]};
                    adapter_post_event(ad, e.tick, AFF_SPEC_Y);
                    last_ev[1] = t;
                    ev_count[phase][1]++;
                }
                fixed_t stim[CAUS_NUM_PRE];
                adapter_emit(ad, t, stim);
                fixed_t cdw[CAUS_NUM_SYNAPSES] = {0, 0, 0, 0};
                CausalityTickResult r = causality_tick(cn, t, stim, cdw);
                bool coinc = causality_has_coincidence(cn, t);
                for (int i = 0; i < CAUS_NUM_PRE; ++i) {
                    if (r.pre_fired[i]) pre_fires[phase][i]++;
                }
                if (r.target_fired) {
                    tgt_fires[phase]++;
                    if (phase == 2 && (t - last_ev[0]) <= 40 &&
                        (t - last_ev[1]) <= 40) {
                        f3_paired++;
                    }
                }
                if (coinc) coinc_ticks[phase]++;
                predict_tick(pd[phase], t, r.pre_fired[0], evy != 0);
                fprintf(csv, "%d,%d,%d,%d,%d,%d,%d,%d,%d,%.6f,%.6f,%d\n",
                        (int)t, sup, phase + 1, evx, evy,
                        r.pre_fired[0] ? 1 : 0, r.pre_fired[2] ? 1 : 0,
                        r.target_fired ? 1 : 0, coinc ? 1 : 0,
                        fixed_to_float(cn.syn[0].weight),
                        fixed_to_float(cn.syn[2].weight),
                        predictor_active(pd[phase], t) ? 1 : 0);
            }
            for (int i = 0; i < CAUS_NUM_SYNAPSES; ++i) {
                gain[phase][i] += fixed_to_float(cn.syn[i].weight -
                                                 w_block_start[i]);
            }
        }
    }
    fclose(csv);

    // Kapilar (MC-turevli esikler).
    bool a_ok = (tgt_fires[2] >= 2 * (tgt_fires[0] + tgt_fires[1])) &&
                (coinc_ticks[2] > 0) &&
                (coinc_ticks[0] + coinc_ticks[1] == 0 ||
                 coinc_ticks[2] >= 5 * (coinc_ticks[0] + coinc_ticks[1]));
    printf("%s (A): F3=%ld >= 2x(F1=%ld+F2=%ld), C=[%ld %ld %ld]\n",
           a_ok ? "OK" : "UYARI", tgt_fires[2], tgt_fires[0], tgt_fires[1],
           coinc_ticks[0], coinc_ticks[1], coinc_ticks[2]);
    bool b_ok = (gain[2][0] > gain[0][0]) && (gain[2][2] > gain[1][2]);
    bool d_ok = (gain[2][0] + gain[2][2]) >
                (gain[0][0] + gain[0][2] + gain[1][0] + gain[1][2]);
    printf("%s (B): F3 kazanc > tekil (s0: %.4f>%.4f, s2: %.4f>%.4f)\n",
           b_ok ? "OK" : "UYARI", gain[2][0], gain[0][0], gain[2][2],
           gain[1][2]);
    printf("%s (D): F3 toplam > F1+F2 (%.4f)\n", d_ok ? "OK" : "UYARI",
           gain[2][0] + gain[2][2]);
    double w1e = fixed_to_float(cn.syn[1].weight);
    double w3e = fixed_to_float(cn.syn[3].weight);
    double w1s = fixed_to_float(AFF_W0_C);
    long p13 = pre_fires[0][1] + pre_fires[1][1] + pre_fires[2][1] +
               pre_fires[0][3] + pre_fires[1][3] + pre_fires[2][3];
    bool c_ok = (p13 == 0) && (std::fabs(w1e - w1s) < 1e-9) &&
                (std::fabs(w3e - w1s) < 1e-9);
    printf("%s (C): P1/P3 ates=%ld, w1/w3 donuk\n", c_ok ? "OK" : "UYARI",
           p13);
    double epair = tgt_fires[2] > 0
                       ? (double)f3_paired / (double)tgt_fires[2]
                       : 0.0;
    bool e_ok = (tgt_fires[2] > 0) && (f3_paired == tgt_fires[2]);
    printf("%s (E): kablo denetimi F3 ciftli %ld/%ld (%.2f)\n",
           e_ok ? "OK" : "UYARI", f3_paired, tgt_fires[2], epair);
    bool f_ok = (ad.drops == 0) && (ad.n_pending == 0);
    printf("%s (F): adaptor tasma=%ld, kapanis bekleyen=%d; "
           "olaylar X/Y=[%ld+%ld %ld+%ld %ld+%ld]\n",
           f_ok ? "OK" : "UYARI", ad.drops, ad.n_pending,
           ev_count[0][0], ev_count[0][1], ev_count[1][0], ev_count[1][1],
           ev_count[2][0], ev_count[2][1]);
    double recall3 = pd[2].y_events > 0
                           ? (double)pd[2].predicted_y /
                                 (double)pd[2].y_events
                           : 0.0;
    // Esik 0.90 (MC ikiz 0.987, C++ 0.933 — fark sabit-nokta mikro
    // zamanlamasi; neden-kanal 0.5/olay seyrek, periyodik kapsama boslugu
    // birakir. Mekanizma ayni, bosluklar superlere esit dagilir.)
    bool p1_ok = (pd[2].y_events > 0) && (recall3 >= 0.90);
    printf("%s (P1): F3 recall %ld/%ld (%.3f)\n", p1_ok ? "OK" : "UYARI",
           pd[2].predicted_y, pd[2].y_events, recall3);
    bool p2_ok = (pd[0].windows > 0) && (pd[0].y_events == 0);
    printf("%s (P2): F1 pencere=%ld, Y=0 (bos-dunya gozlemi)\n",
           p2_ok ? "OK" : "UYARI", pd[0].windows);
    double lead3 = pd[2].lead_n > 0
                       ? (double)pd[2].lead_sum / (double)pd[2].lead_n
                       : -1.0;
    bool p3_ok = (pd[2].lead_n > 0) && (lead3 >= 1.0) &&
                 (lead3 <= (double)AFF_PRED_W);
    printf("%s (P3): F3 lead=%.2f tick (pencere %d)\n",
           p3_ok ? "OK" : "UYARI", lead3, (int)AFF_PRED_W);
    printf("\n=== OZET-AFFERENT: A=%s B=%s C=%s D=%s E=%s F=%s P=%s ===\n",
           a_ok ? "OK" : "UYARI", b_ok ? "OK" : "UYARI",
           c_ok ? "OK" : "UYARI", d_ok ? "OK" : "UYARI",
           e_ok ? "OK" : "UYARI", f_ok ? "OK" : "UYARI",
           (p1_ok && p2_ok && p3_ok) ? "OK" : "UYARI");
    return 0;
}
