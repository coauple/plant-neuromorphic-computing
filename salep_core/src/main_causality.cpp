// ---------------------------------------------------------------------------
// Nedensellik Koprusu — Katman 1 demux + coincidence + kuadratik ogrenme
//
// Kalibrasyon: validate_causality.py (2026-09-07).
//   PULSE=0.8, ETA=0.2, N_SUPER=20 (30.000 tick).
//   w0: MC 0.5 onerdi (2.00x) ama ilk C++ kosusu 1.88x verdi (MC'nin
//   kucuk-sayi iyimserligi); 0.4'e cekildi -> 2.11x, ogrenme canli.
//   Kalibrasyon dongusu, esik oynama degil (bkz. anayasa §0).
// Super-dongu = Faz1(500) + Faz2(500) + Faz3(500); blok arasi sessizlik
// RATE_WINDOW=30 sayaclarini sifirlar (faz izolasyonu).
// Faz1: 4'luk ritim -> P0 -> yalniz Dal A. Faz2: 12'lik -> P2 -> yalniz
// Dal B. Faz3: ikisi senkron -> Dal A + Dal B -> COINCIDENCE_BONUS.
// P1/P3 negatif kontrol (uyarilmaz, dw=0 beklenir).
// ---------------------------------------------------------------------------

#include <cmath>
#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include "causality.h"

// Kalibre sabitler (validate_causality.py)
constexpr int32_t CAUS_TAUS[CAUS_NUM_PRE] = {4, 8, 12, 16};
constexpr int32_t CAUS_BW = 2;
constexpr int BLOCK_LEN = 500;
constexpr int N_SUPER = 20;
constexpr fixed_t CAUS_ETA = fixed_from_double(0.2);
constexpr fixed_t CAUS_PULSE = fixed_from_double(0.8);
constexpr fixed_t CAUS_W0 = fixed_from_double(0.4);

// Runtime parametreleri (dashboard §9.9, yalniz harness). Varsayilanlar
// kalibre sabitlere esit -> argumansiz kosu onceki CSV ile bayt-bayt aynidir.
static fixed_t g_w0 = CAUS_W0;
static fixed_t g_pulse = CAUS_PULSE;
static int32_t g_d12 = 0;
static bool g_custom = false;

// CLI: --w0 W --pulse V --d12 D [--help]. --key=val ve --key val desteklenir.
static bool parse_cli(int argc, char** argv) {
    for (int i = 1; i < argc; ++i) {
        char* a = argv[i];
        const char* val = nullptr;
        char key[32];
        const char* eq = strchr(a, '=');
        if (eq != nullptr) {
            size_t kl = (size_t)(eq - a);
            if (kl == 0 || kl >= sizeof(key)) {
                fprintf(stderr, "HATA: bozuk arguman '%s'\n", a);
                return false;
            }
            memcpy(key, a, kl);
            key[kl] = '\0';
            val = eq + 1;
        } else {
            if (strlen(a) >= sizeof(key)) {
                fprintf(stderr, "HATA: bozuk arguman '%s'\n", a);
                return false;
            }
            strcpy(key, a);
            if (strcmp(key, "--help") == 0) {
                printf("kullanim: salep_causality [--w0 W] [--pulse V] "
                       "[--d12 D]\n"
                       "  --w0 W   : baslangic agirligi, [0.05,2.0] "
                       "(varsayilan 0.4)\n"
                       "  --pulse V: darbe genligi, (0,2] (varsayilan 0.8)\n"
                       "  --d12 D  : 12'lik ritim faz kaymasi 0-31 "
                       "(Faz2+Faz3)\n"
                       "  argumansiz = kalibre davranis birebir\n");
                exit(0);
            }
            if (i + 1 >= argc) {
                fprintf(stderr, "HATA: '%s' deger bekliyor\n", key);
                return false;
            }
            val = argv[++i];
        }
        char* end = nullptr;
        if (strcmp(key, "--w0") == 0) {
            double v = strtod(val, &end);
            if (*end != '\0' || v < 0.05 || v > 2.0) {
                fprintf(stderr, "HATA: --w0 [0.05,2.0] olmali\n");
                return false;
            }
            g_w0 = fixed_from_double(v);
            g_custom = true;
        } else if (strcmp(key, "--pulse") == 0) {
            double v = strtod(val, &end);
            if (*end != '\0' || !(v > 0.0) || v > 2.0) {
                fprintf(stderr, "HATA: --pulse (0,2] olmali\n");
                return false;
            }
            g_pulse = fixed_from_double(v);
            g_custom = true;
        } else if (strcmp(key, "--d12") == 0) {
            long v = strtol(val, &end, 10);
            if (*end != '\0' || v < 0 || v > 31) {
                fprintf(stderr, "HATA: --d12 0-31 olmali\n");
                return false;
            }
            g_d12 = (int32_t)v;
            g_custom = true;
        } else {
            fprintf(stderr, "HATA: bilinmeyen arguman '%s' (--help)\n", key);
            return false;
        }
    }
    return true;
}

// Aktif pencereler: F1 40-180 (p4 -> P0), F2 40-220 (p12 -> P2),
// F3 40-220 (p4 -> P0 ve p12 -> P2, senkron baslangic).
// g_d12: 12'lik ritmin faz kaymasi (0 = kalibre davranis birebir).
static void causality_stimulus(int phase, int32_t bt,
                               fixed_t stim[CAUS_NUM_PRE]) {
    for (int i = 0; i < CAUS_NUM_PRE; ++i) stim[i] = 0;
    if (phase == 0) {
        if (bt >= 40 && bt <= 180 && (bt - 40) % 4 == 0) {
            stim[0] = g_pulse;
        }
    } else if (phase == 1) {
        if (bt >= 40 && bt <= 220 && (bt - 40 - g_d12) % 12 == 0) {
            stim[2] = g_pulse;
        }
    } else {
        if (bt >= 40 && bt <= 220) {
            if ((bt - 40) % 4 == 0) stim[0] = g_pulse;
            if ((bt - 40 - g_d12) % 12 == 0) stim[2] = g_pulse;
        }
    }
}

static NeuronParams make_pre_params(int idx) {
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
    p.tau_isi = CAUS_TAUS[idx];
    p.resonance_bw = CAUS_BW;
    return p;
}

int main(int argc, char** argv) {
    if (!parse_cli(argc, argv)) return 1;
    synapse_build_luts();

    printf("=== NEDENSELLIK KOPRUSU: demux + coincidence + ogrenme ===\n");
    printf("w0=%.1f eta=0.2 pulse=%.1f, %d super-dongu x 1500 tick\n",
           fixed_to_float(g_w0), fixed_to_float(g_pulse), N_SUPER);
    // Parametre satiri yalniz ozel kosuda -> argumansiz stdout ve CSV
    // onceki kosularla birebir aynidir (regresyon).
    if (g_custom) {
        printf("param: w0=%.3f pulse=%.3f d12=%d\n", fixed_to_float(g_w0),
               fixed_to_float(g_pulse), (int)g_d12);
    }

    CausalityNetwork cn;
    NeuronParams pre_params[CAUS_NUM_PRE];
    for (int i = 0; i < CAUS_NUM_PRE; ++i) pre_params[i] = make_pre_params(i);
    // Target: hafif sizintili entegrator (MC: tek kanali bastirir,
    // cift kanali gecirir -> kontrast).
    NeuronParams target_params = {0.04, 0.04, 0.04, 0.005, 0.004, 0.003};
    causality_init(cn, pre_params, target_params, g_w0, CAUS_ETA);

    FILE* csv = fopen("causality_learning.csv", "w");
    if (!csv) {
        fprintf(stderr, "HATA: causality_learning.csv acilamadi\n");
        return 1;
    }
    fprintf(csv,
            "tick,super,phase,p0_fired,p1_fired,p2_fired,p3_fired,"
            "target_fired,coincidence,w0,w1,w2,w3,dw0,dw2,g0,q0,g2,q2,"
            "t_root_v,t_A_v,t_B_v,t_soma_v\n");

    // --- Istatistikler (faz turune gore birikir) ---
    long tgt_fires[3] = {0, 0, 0};
    long coinc_ticks[3] = {0, 0, 0};
    long pre_fires[3][CAUS_NUM_PRE] = {{0}};
    double dw_sum[3][CAUS_NUM_SYNAPSES] = {{0.0}};
    long dw_cnt[3] = {0, 0, 0};
    // Blok kazanclari: her faz blogunun bas/son agirligi
    double gain[3][CAUS_NUM_SYNAPSES] = {{0.0}};
    fixed_t w_block_start[CAUS_NUM_SYNAPSES];

    for (int sup = 0; sup < N_SUPER; ++sup) {
        for (int phase = 0; phase < 3; ++phase) {
            for (int i = 0; i < CAUS_NUM_SYNAPSES; ++i) {
                w_block_start[i] = cn.syn[i].weight;
            }
            for (int bt = 0; bt < BLOCK_LEN; ++bt) {
                int32_t abs_t =
                    (int32_t)((sup * 3 + phase) * BLOCK_LEN + bt);
                fixed_t stim[CAUS_NUM_PRE];
                causality_stimulus(phase, bt, stim);
                fixed_t dw[CAUS_NUM_SYNAPSES] = {0, 0, 0, 0};

                CausalityTickResult r = causality_tick(cn, abs_t, stim, dw);
                bool coinc = causality_has_coincidence(cn, abs_t);

                for (int i = 0; i < CAUS_NUM_PRE; ++i) {
                    if (r.pre_fired[i]) pre_fires[phase][i]++;
                }
                if (r.target_fired) tgt_fires[phase]++;
                if (coinc) coinc_ticks[phase]++;
                for (int i = 0; i < CAUS_NUM_SYNAPSES; ++i) {
                    dw_sum[phase][i] += std::fabs(fixed_to_float(dw[i]));
                }
                dw_cnt[phase]++;

                fixed_t g0 = synapse_G(cn.rc_pre[0].count, cn.rc_post[0].count);
                fixed_t q0 = synapse_Q(cn.rc_pre[0].count, cn.rc_post[0].count);
                fixed_t g2 = synapse_G(cn.rc_pre[2].count, cn.rc_post[2].count);
                fixed_t q2 = synapse_Q(cn.rc_pre[2].count, cn.rc_post[2].count);

                fprintf(csv,
                        "%d,%d,%d,%d,%d,%d,%d,%d,%d,"
                        "%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,"
                        "%.6f,%.6f,%.6f,%.6f,"
                        "%.6f,%.6f,%.6f,%.6f\n",
                        abs_t, sup, phase + 1, r.pre_fired[0] ? 1 : 0,
                        r.pre_fired[1] ? 1 : 0, r.pre_fired[2] ? 1 : 0,
                        r.pre_fired[3] ? 1 : 0, r.target_fired ? 1 : 0,
                        coinc ? 1 : 0, fixed_to_float(cn.syn[0].weight),
                        fixed_to_float(cn.syn[1].weight),
                        fixed_to_float(cn.syn[2].weight),
                        fixed_to_float(cn.syn[3].weight),
                        fixed_to_float(dw[0]), fixed_to_float(dw[2]),
                        fixed_to_float(g0), fixed_to_float(q0),
                        fixed_to_float(g2), fixed_to_float(q2),
                        fixed_to_float(
                            cn.target.compartments[cn.target.root_compartment_id]
                                .local_voltage),
                        fixed_to_float(
                            cn.target.compartments[cn.target.branch_A_id]
                                .local_voltage),
                        fixed_to_float(
                            cn.target.compartments[cn.target.branch_B_id]
                                .local_voltage),
                        fixed_to_float(cn.target.soma_voltage));
            }
            for (int i = 0; i < CAUS_NUM_SYNAPSES; ++i) {
                gain[phase][i] += fixed_to_float(cn.syn[i].weight -
                                                 w_block_start[i]);
            }
        }
    }
    fclose(csv);
    printf("CSV yazildi: causality_learning.csv\n");

    const char* pname[3] = {"Faz1(A)", "Faz2(B)", "Faz3(A+B)"};

    // --- (A) Coincidence bonusu ---
    printf("\n=== (A) COINCIDENCE BONUSU ===\n");
    for (int ph = 0; ph < 3; ++ph) {
        printf("%s: target ates=%ld coinc tick=%ld pre=[%ld %ld %ld %ld]\n",
               pname[ph], tgt_fires[ph], coinc_ticks[ph], pre_fires[ph][0],
               pre_fires[ph][1], pre_fires[ph][2], pre_fires[ph][3]);
    }
    double base = (double)(tgt_fires[0] + tgt_fires[1]);
    double ratio =
        (base > 0) ? (double)tgt_fires[2] / base : -1.0;
    printf("F3/(F1+F2) = %.2fx\n", ratio);
    bool a_ok = (tgt_fires[2] >= 2 * (tgt_fires[0] + tgt_fires[1])) &&
                (coinc_ticks[2] > 0) &&
                (coinc_ticks[0] + coinc_ticks[1] == 0 ||
                 coinc_ticks[2] >= 5 * (coinc_ticks[0] + coinc_ticks[1]));
    printf("%s (A): F3 >= 2x(F1+F2), C1=C2=0, C3>>0\n", a_ok ? "OK" : "UYARI");

    // --- (B) dw ivmesi + (D) blok kazanclari ---
    printf("\n=== (B/D) DW IVMESI + BLOK KAZANCLARI ===\n");
    printf("faz-turu basina ortalama |dw|/tick:\n");
    for (int ph = 0; ph < 3; ++ph) {
        printf("%s: s0=%.6f s1=%.6f s2=%.6f s3=%.6f\n", pname[ph],
               dw_sum[ph][0] / dw_cnt[ph], dw_sum[ph][1] / dw_cnt[ph],
               dw_sum[ph][2] / dw_cnt[ph], dw_sum[ph][3] / dw_cnt[ph]);
    }
    printf("toplam blok kazanclari (20 super x faz):\n");
    for (int ph = 0; ph < 3; ++ph) {
        printf("%s: s0=%+.6f s1=%+.6f s2=%+.6f s3=%+.6f\n", pname[ph],
               gain[ph][0], gain[ph][1], gain[ph][2], gain[ph][3]);
    }
    bool b_ok = (gain[2][0] > gain[0][0]) && (gain[2][2] > gain[1][2]);
    bool d_ok = (gain[2][0] + gain[2][2]) >
                (gain[0][0] + gain[0][2] + gain[1][0] + gain[1][2]);
    printf("%s (B): Faz3 kazanci > tek-kanal faz kazanci (s0: F3>F1, s2: F3>F2)\n",
           b_ok ? "OK" : "UYARI");
    printf("%s (D): Faz3 toplam kazanc > F1+F2 toplami\n", d_ok ? "OK" : "UYARI");

    // --- (C) Negatif kontrol ---
    printf("\n=== (C) NEGATIF KONTROL (P1/P3) ===\n");
    double wstart = fixed_to_float(CAUS_W0);
    double wend[CAUS_NUM_SYNAPSES];
    for (int i = 0; i < CAUS_NUM_SYNAPSES; ++i) {
        wend[i] = fixed_to_float(cn.syn[i].weight);
    }
    printf("P1 ates=%ld P3 ates=%ld (beklenen 0)\n",
           pre_fires[0][1] + pre_fires[1][1] + pre_fires[2][1],
           pre_fires[0][3] + pre_fires[1][3] + pre_fires[2][3]);
    printf("w1: %.6f -> %.6f  w3: %.6f -> %.6f\n", wstart, wend[1], wstart,
           wend[3]);
    bool c_ok = (std::fabs(wend[1] - wstart) < 1e-9) &&
                (std::fabs(wend[3] - wstart) < 1e-9);
    printf("%s (C): s1/s3 sabit (dw=0)\n", c_ok ? "OK" : "UYARI");

    printf("\n=== OZET: A=%s B=%s C=%s D=%s ===\n", a_ok ? "OK" : "UYARI",
           b_ok ? "OK" : "UYARI", c_ok ? "OK" : "UYARI", d_ok ? "OK" : "UYARI");
    return 0;
}
