// ---------------------------------------------------------------------------
// Bitki NPU — Duyusal Lob + Kosul Ogrenme Lobu (Pavlov deneyi) harness.
// FAZ 2: dual-rail (Rail-F frekans + Rail-C kanal sayaclari), 7 sensor,
// batch (varsayilan) + stream (--stream) calisma kipleri.
//
// Kalibrasyon: validate_plant_npu.py (Kural 0).
//   S_b=1.0, w0=0.2, eta=0.2 -> 5/5 kriter OK (MC ongoru).
// Topoloji: ortak tel (4+12, D_b=0) -> bant-4/12 pop (8, PLIR) ->
//   temsilci m=0 -> 7 grounding post (her sensor bir (bant, sensor) cifti)
//   + 2 capraz post (X1: bant-4 x HN; X2: bant-12 x HS).
//   Ilk 3 post FAZ 1 ile birebir (NEM/HN<-12, EC<-12 neg, SIC/HS<-4).
// Senaryo (batch): Asama 1 KOSULLANMA (10 x 500 tick, sensorler acik) +
//   Asama 2 KOSUL TESTI (3 x 500 tick, sensorler CPU tarafindan 0'a cekilir).
// Ogrenme tum oturum boyunca aktiftir.
//
// Cekirdek (plant_npu.h) sensor degeri/esik BILMEZ: bu dosya (HostController
// tarafi, harness) degeri spike'a cevirir:
//   US: v>=50 ON (aktif), v<50 OFF (susturulur);
//   CS: aktifse periyot = postun bant tau'su, burst'lu
//     (tau<16 burst=1; tau=16 burst=2; tau>=24 burst=3), genlik S_b,
//     gecikme D_s (--d_sens).
// Tel ureteci + LCG: main_fdm deseni (seed sabit, deterministik).
// Olcum double'i YALNIZ bu dosyada (cekirdekte float/double YOK).
//
// Kipler:
//   batch (varsayilan, --batch): klasik kosu; plant_learning.csv +
//     plant_conditions.csv FAZ 1 ile bit-bit ayni + plant_dualrail.csv
//     (9 post + Rail-C) + OZET.
//   stream (--stream): stdin komutlar (SET <sensor> <0-100> / RESET / QUIT),
//     stdout her 25 tick telemetri + kapanis OZETi.
// ---------------------------------------------------------------------------

#include <cmath>
#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include "plant_npu.h"

#if defined(__unix__) || defined(__APPLE__)
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#define PNP_HAVE_SELECT 1
#else
#define PNP_HAVE_SELECT 0
#endif

namespace {

constexpr int BLOCK_LEN = 500;
constexpr int N_COND = 10;
constexpr int N_TEST = 3;
constexpr int T_TOTAL = (N_COND + N_TEST) * BLOCK_LEN;  // 6500
constexpr int32_t WIRE_TAUS[2] = {4, 12};

constexpr fixed_t WIRE_PULSE = fixed_from_double(0.8);
constexpr int SENS_THRESH = 50;

// Runtime parametreleri (dashboard, yalniz harness). Varsayilanlar kalibre
// davranisa esit -> argumansiz kosu deterministik referanstir.
// hn=eski nem(60), ec=40, hs=eski sicaklik(75); yeni kanallar susturulu(40).
int g_hs = 75;
int g_ts = 40;
int g_hn = 60;
int g_tn = 40;
int g_ph = 40;
int g_npk = 40;
int g_ec = 40;
int g_noise_pct = FDM_NOISE_PCT;  // 2
int32_t g_d_sens = 0;
bool g_custom = false;
bool g_stream = false;

uint32_t g_stim = 0;

fixed_t stim_jittered(fixed_t base) {
    int32_t j = (int32_t)(fdm_lcg_next(g_stim) % 401u) - 200;  // [-200,200]
    fixed_t mult = fixed_div(fixed_from_int(1000 + j), fixed_from_int(1000));
    return fixed_mul(base, mult);
}

// Superpoze tel: 4+12, D_b=0 (ortak tel deseni main_fdm'den).
fixed_t super_wire(int32_t t, bool noisy) {
    fixed_t w = 0;
    for (int b = 0; b < 2; ++b) {
        if (t % WIRE_TAUS[b] == 0) {
            w += noisy ? stim_jittered(WIRE_PULSE) : WIRE_PULSE;
        }
    }
    if (noisy && (fdm_lcg_next(g_stim) % 100u) < (uint32_t)g_noise_pct) {
        w += stim_jittered(fixed_mul(WIRE_PULSE, fixed_from_double(0.7)));
    }
    return w;
}

// CS burst kurali (seyrek-bant telafisi, yalniz harness):
// tau 6/8 -> 1, tau 16 -> 2, tau 24/32 -> 3. Aktif bantlar (4/12) burst=1
// -> FAZ 1 davranisiyla birebir.
int sensor_burst(int32_t tau) {
    if (tau >= 24) return 3;
    if (tau >= 16) return 2;
    return 1;
}

// Sensor degeri -> spike bayragi (CPU cevirici, yalniz harness):
// US: v>=50 ON, v<50 OFF; ON ise CS periyodu = postun bant tau'su (burst'lu),
// D_s gecikme.
bool sensor_to_spike(int value, int32_t tau, int32_t t) {
    if (value < SENS_THRESH) return false;
    if (t < g_d_sens) return false;
    int b = sensor_burst(tau);
    return ((t - g_d_sens) % tau) < b;
}

// Afferent kapi (yalniz stream): 1=acik, 0=kapali (donanim kesmesi).
// Batch bu diziye hic dokunmaz (hepsi 1) -> CSV'ler bit-bit ayni.
int g_sensor_gate[PNP_MAX_SENSORS] = {1, 1, 1, 1, 1, 1, 1};

// Kanal indisini isme gore dondurur (stream SENSOR_OFF/ON icin).
int chan_index_by_name(const char* name) {
    if (strcmp(name, "hs") == 0 || strcmp(name, "sicaklik") == 0)
        return PNP_CH_HS;
    if (strcmp(name, "ts") == 0) return PNP_CH_TS;
    if (strcmp(name, "hn") == 0 || strcmp(name, "nem") == 0)
        return PNP_CH_HN;
    if (strcmp(name, "tn") == 0) return PNP_CH_TN;
    if (strcmp(name, "ph") == 0) return PNP_CH_PH;
    if (strcmp(name, "npk") == 0) return PNP_CH_NPK;
    if (strcmp(name, "ec") == 0) return PNP_CH_EC;
    return -1;
}

// Kanal degerini isme gore dondurur (stream SET icin).
int* sensor_ptr_by_name(const char* name) {
    if (strcmp(name, "hs") == 0 || strcmp(name, "sicaklik") == 0) return &g_hs;
    if (strcmp(name, "ts") == 0) return &g_ts;
    if (strcmp(name, "hn") == 0 || strcmp(name, "nem") == 0) return &g_hn;
    if (strcmp(name, "tn") == 0) return &g_tn;
    if (strcmp(name, "ph") == 0) return &g_ph;
    if (strcmp(name, "npk") == 0) return &g_npk;
    if (strcmp(name, "ec") == 0) return &g_ec;
    return nullptr;
}

void print_help() {
    printf("kullanim: salep_plant_npu [sensorler] [--noise P] [--d_sens D] "
           "[--batch|--stream]\n"
           "  --hs V --ts V --hn V --tn V --ph V --npk V --ec V (0-100)\n"
           "    varsayilan: hs=75 ts=40 hn=60 tn=40 ph=40 npk=40 ec=40\n"
           "    eski adlar: --nem (=--hn), --sicaklik (=--hs)\n"
           "  --noise P   : ekstra darbe yuzdesi (varsayilan 2, 0-10)\n"
           "  --d_sens D  : sensor spike gecikmesi (varsayilan 0, 0-11)\n"
           "  --batch     : batch kosu (varsayilan)\n"
           "  --stream    : stream kosu (stdin: SET/RESET/QUIT, "
           "stdout her 25 tick telemetri)\n"
           "  esik 50: v>=50 ON, v<50 OFF; "
           "test asamasinda sensorler 0'a cekilir\n"
           "  argumansiz = kalibre davranis birebir\n");
}

// CLI: 7 sensor + --noise + --d_sens + --batch/--stream + --help.
// Eski --nem/--sicaklik adlari da kabul edilir (ayni kanal).
bool parse_cli(int argc, char** argv) {
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
                print_help();
                exit(1);
            }
            if (strcmp(key, "--batch") == 0) {
                g_stream = false;
                continue;
            }
            if (strcmp(key, "--stream") == 0) {
                g_stream = true;
                continue;
            }
            if (i + 1 >= argc) {
                fprintf(stderr, "HATA: '%s' deger bekliyor\n", key);
                return false;
            }
            val = argv[++i];
        }
        char* end = nullptr;
        int* dst = sensor_ptr_by_name(key[0] == '-' && key[1] == '-'
                                          ? key + 2
                                          : key);
        if (dst != nullptr) {
            long v = strtol(val, &end, 10);
            if (*end != '\0' || v < 0 || v > 100) {
                fprintf(stderr, "HATA: %s 0-100 olmali\n", key);
                return false;
            }
            *dst = (int)v;
            g_custom = true;
        } else if (strcmp(key, "--noise") == 0) {
            long v = strtol(val, &end, 10);
            if (*end != '\0' || v < 0 || v > 10) {
                fprintf(stderr, "HATA: --noise 0-10 olmali\n");
                return false;
            }
            g_noise_pct = (int)v;
            g_custom = true;
        } else if (strcmp(key, "--d_sens") == 0) {
            long v = strtol(val, &end, 10);
            if (*end != '\0' || v < 0 || v > 11) {
                fprintf(stderr, "HATA: --d_sens 0-11 olmali\n");
                return false;
            }
            g_d_sens = (int32_t)v;
            g_custom = true;
        } else if (strcmp(key, "--batch") == 0 || strcmp(key, "--stream") == 0) {
            // '--batch=..' / '--stream=..' bicimi anlamsiz.
            fprintf(stderr, "HATA: '%s' deger almaz\n", key);
            return false;
        } else {
            fprintf(stderr, "HATA: bilinmeyen arguman '%s' (--help)\n", key);
            return false;
        }
    }
    return true;
}

// Kanal sira duzeni: [HN, EC, HS, TS, TN, PH, NPK] (PNP_CH_* ile ayni).
void chan_values(int out[PNP_MAX_SENSORS]) {
    out[PNP_CH_HN] = g_hn;
    out[PNP_CH_EC] = g_ec;
    out[PNP_CH_HS] = g_hs;
    out[PNP_CH_TS] = g_ts;
    out[PNP_CH_TN] = g_tn;
    out[PNP_CH_PH] = g_ph;
    out[PNP_CH_NPK] = g_npk;
}

int run_batch();
int run_stream();

int run_batch() {
    synapse_build_luts();

    printf("=== BITKI NPU: duyusal lob + kosul ogrenme (Pavlov) ===\n");
    printf("S_b=1.0 w0=0.2 eta=0.2, %d kosullanma + %d test blogu x %d tick\n",
           N_COND, N_TEST, BLOCK_LEN);
    if (g_custom) {
        printf("param: hs=%d ts=%d hn=%d tn=%d ph=%d npk=%d ec=%d "
               "noise=%d%% d_sens=%d\n",
               g_hs, g_ts, g_hn, g_tn, g_ph, g_npk, g_ec, g_noise_pct,
               (int)g_d_sens);
    }

    PlantNpu net;
    plant_init(net, PNP_SENSOR_AMP, PNP_ETA, PNP_W0);

    FILE* tick_csv = fopen("plant_learning.csv", "w");
    FILE* cond_csv = fopen("plant_conditions.csv", "w");
    FILE* rail_csv = fopen("plant_dualrail.csv", "w");
    if (!tick_csv || !cond_csv || !rail_csv) {
        fprintf(stderr, "HATA: plant CSV acilamadi\n");
        if (tick_csv) fclose(tick_csv);
        if (cond_csv) fclose(cond_csv);
        if (rail_csv) fclose(rail_csv);
        return 1;
    }
    fprintf(tick_csv,
            "tick,block,stage,wire,fire_b4,fire_b12,s_nem,s_ec,s_sic,"
            "p0_fired,p1_fired,p2_fired,w0,w1,w2\n");
    fprintf(cond_csv, "stage,block,post,w_start,w_end,dw,fires,coinc\n");
    fprintf(rail_csv,
            "tick,block,stage,p3_fired,p4_fired,p5_fired,p6_fired,p7_fired,"
            "p8_fired,w3,w4,w5,w6,w7,w8,"
            "cc_hn,cc_ec,cc_hs,cc_ts,cc_tn,cc_ph,cc_npk\n");

    g_stim = 7002u;  // tel + gurultu LCG tohumu (sabit)

    // Kilit istatistigi: kosullanma asamasinda bant havuz atesleri.
    long hist_b4[12] = {0}, hist_b12[12] = {0};
    long n_b4 = 0, n_b12 = 0;
    static bool fired_b4[T_TOTAL] = {false};
    static bool fired_b12[T_TOTAL] = {false};

    // 9 postun bant tau'su (Rail-F) + kanal eslesmesi (cekirdek tablosundan).
    int32_t post_tau[PNP_NUM_POST];
    for (int k = 0; k < PNP_NUM_POST; ++k) {
        post_tau[k] = (PNP_POST_BAND[k] == 0) ? 4 : 12;
    }
    const char* post_name[PNP_NUM_POST] = {"NEM", "EC", "SIC", "TS", "TN",
                                           "PH",  "NPK", "X1",  "X2"};

    double cond_dw[PNP_NUM_BASE] = {0.0, 0.0, 0.0};
    long cond_fires[PNP_NUM_BASE] = {0, 0, 0};
    long test_fires[PNP_NUM_BASE] = {0, 0, 0};
    fixed_t w_after_cond[PNP_NUM_BASE];

    int chan_val[PNP_MAX_SENSORS];
    chan_values(chan_val);

    int32_t t = 0;
    int block_id = 0;
    for (int stage = 0; stage < 2; ++stage) {
        int nblocks = (stage == 0) ? N_COND : N_TEST;
        for (int blk = 0; blk < nblocks; ++blk, ++block_id) {
            fixed_t w_start[PNP_MAX_POST];
            for (int k = 0; k < PNP_NUM_POST; ++k) {
                w_start[k] = net.syn[k].weight;
            }
            long blk_fires[PNP_NUM_POST] = {0, 0, 0, 0, 0, 0, 0, 0, 0};
            long blk_coinc[PNP_NUM_POST] = {0, 0, 0, 0, 0, 0, 0, 0, 0};

            for (int bt = 0; bt < BLOCK_LEN; ++bt, ++t) {
                fixed_t w = super_wire(t, true);
                bool sspike[PNP_MAX_POST] = {false};
                int sflag[PNP_NUM_BASE] = {0, 0, 0};
                if (stage == 0) {
                    // KOSULLANMA: sensorler acik (v>=50 ON).
                    for (int k = 0; k < PNP_NUM_POST; ++k) {
                        int c = PNP_POST_CHAN[k];
                        sspike[k] =
                            sensor_to_spike(chan_val[c], post_tau[k], t);
                    }
                    for (int k = 0; k < PNP_NUM_BASE; ++k) {
                        sflag[k] = sspike[k] ? 1 : 0;
                    }
                }
                // TEST: sensorler CPU tarafindan 0'a cekili -> sspike hepsi false.

                fixed_t dw[PNP_MAX_POST] = {0};
                PlantTickResult r = plant_tick(net, t, w, sspike, dw);

                long fb4 = 0, fb12 = 0;
                for (int m = 0; m < net.sensory.pop[0]; ++m) {
                    if (r.pre.fired[0][m]) {
                        fb4++;
                        if (stage == 0) {
                            hist_b4[t % 4]++;
                            n_b4++;
                            fired_b4[t] = true;
                        }
                    }
                }
                for (int m = 0; m < net.sensory.pop[1]; ++m) {
                    if (r.pre.fired[1][m]) {
                        fb12++;
                        if (stage == 0) {
                            hist_b12[t % 12]++;
                            n_b12++;
                            fired_b12[t] = true;
                        }
                    }
                }
                for (int k = 0; k < PNP_NUM_POST; ++k) {
                    if (r.post_fired[k]) {
                        blk_fires[k]++;
                        if (k < PNP_NUM_BASE) {
                            if (stage == 0) cond_fires[k]++;
                            else test_fires[k]++;
                        }
                    }
                    if (r.coinc[k]) blk_coinc[k]++;
                }

                fprintf(tick_csv,
                        "%d,%d,%d,%.6f,%ld,%ld,%d,%d,%d,%d,%d,%d,"
                        "%.6f,%.6f,%.6f\n",
                        t, block_id, stage, fixed_to_float(w), fb4, fb12,
                        sflag[0], sflag[1], sflag[2],
                        r.post_fired[0] ? 1 : 0, r.post_fired[1] ? 1 : 0,
                        r.post_fired[2] ? 1 : 0,
                        fixed_to_float(net.syn[0].weight),
                        fixed_to_float(net.syn[1].weight),
                        fixed_to_float(net.syn[2].weight));
                fprintf(rail_csv,
                        "%d,%d,%d,%d,%d,%d,%d,%d,%d,"
                        "%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,"
                        "%d,%d,%d,%d,%d,%d,%d\n",
                        t, block_id, stage,
                        r.post_fired[3] ? 1 : 0, r.post_fired[4] ? 1 : 0,
                        r.post_fired[5] ? 1 : 0, r.post_fired[6] ? 1 : 0,
                        r.post_fired[7] ? 1 : 0, r.post_fired[8] ? 1 : 0,
                        fixed_to_float(net.syn[3].weight),
                        fixed_to_float(net.syn[4].weight),
                        fixed_to_float(net.syn[5].weight),
                        fixed_to_float(net.syn[6].weight),
                        fixed_to_float(net.syn[7].weight),
                        fixed_to_float(net.syn[8].weight),
                        net.channel_carrier[0].count,
                        net.channel_carrier[1].count,
                        net.channel_carrier[2].count,
                        net.channel_carrier[3].count,
                        net.channel_carrier[4].count,
                        net.channel_carrier[5].count,
                        net.channel_carrier[6].count);
            }

            // FAZ 1 kosul tablosu: yalniz ilk 3 post (bit-bit uyumluluk).
            for (int k = 0; k < PNP_NUM_BASE; ++k) {
                double ws = fixed_to_float(w_start[k]);
                double we = fixed_to_float(net.syn[k].weight);
                fprintf(cond_csv, "%d,%d,%d,%.6f,%.6f,%+.6f,%ld,%ld\n", stage,
                        blk, k, ws, we, we - ws, blk_fires[k], blk_coinc[k]);
            }
            (void)blk_coinc;
        }
        if (stage == 0) {
            for (int k = 0; k < PNP_NUM_BASE; ++k) {
                w_after_cond[k] = net.syn[k].weight;
                cond_dw[k] =
                    fixed_to_float(w_after_cond[k] - PNP_W0);
            }
        }
    }
    fclose(tick_csv);
    fclose(cond_csv);
    fclose(rail_csv);
    printf("CSV yazildi: plant_learning.csv plant_conditions.csv "
           "plant_dualrail.csv\n");

    // --- (A) Kilit: FDM disiplini. Varsayilan tel gurultuludur (S2) ->
    // kapi cov>=0.40 (§9.8: S2 conc tohum-duyarli, yalniz bilgi). conc
    // raporlanir ama kapi degildir.
    long mx4 = 0, mx12 = 0;
    for (int i = 0; i < 4; ++i) {
        if (hist_b4[i] > mx4) mx4 = hist_b4[i];
    }
    for (int i = 0; i < 12; ++i) {
        if (hist_b12[i] > mx12) mx12 = hist_b12[i];
    }
    double conc4 = n_b4 > 0 ? (double)mx4 / (double)n_b4 : 0.0;
    double conc12 = n_b12 > 0 ? (double)mx12 / (double)n_b12 : 0.0;
    const int T_COND = N_COND * BLOCK_LEN;
    long pulses4 = 0, ok4 = 0, pulses12 = 0, ok12 = 0;
    for (int32_t p = 0; p < T_COND; p += 4) {
        pulses4++;
        for (int32_t o = -2; o <= 2; ++o) {
            if (p + o >= 0 && p + o < T_COND && fired_b4[p + o]) {
                ok4++;
                break;
            }
        }
    }
    for (int32_t p = 0; p < T_COND; p += 12) {
        pulses12++;
        for (int32_t o = -2; o <= 2; ++o) {
            if (p + o >= 0 && p + o < T_COND && fired_b12[p + o]) {
                ok12++;
                break;
            }
        }
    }
    double cov4 = pulses4 > 0 ? (double)ok4 / (double)pulses4 : 0.0;
    double cov12 = pulses12 > 0 ? (double)ok12 / (double)pulses12 : 0.0;
    printf("\n=== (A) KILIT (coverage + konsantrasyon) ===\n");
    printf("bant-4: cov=%.2f conc=%.2f(bilgi) ates=%ld | "
           "bant-12: cov=%.2f conc=%.2f(bilgi) ates=%ld\n",
           cov4, conc4, n_b4, cov12, conc12, n_b12);
    bool a_ok = (cov4 >= 0.40) && (cov12 >= 0.40);
    printf("%s (A): cov >= 0.40 iki bantta (gurultulu tel, §9.8 S2 kapisi)\n",
           a_ok ? "OK" : "UYARI");

    // --- (B/D) Kosul tablosu ---
    printf("\n=== (B/D) KOSUL KAZANIMI + NEGATIF KONTROL ===\n");
    for (int k = 0; k < PNP_NUM_BASE; ++k) {
        printf("%s: w 0.2 -> %.4f (dw=%+.4f) cond_ates=%ld test_ates(CR)=%ld\n",
               post_name[k], fixed_to_float(w_after_cond[k]), cond_dw[k],
               cond_fires[k], test_fires[k]);
    }
    bool b_ok = (cond_dw[0] >= 0.3) && (cond_dw[2] >= 0.3);
    printf("%s (B): NEM/SIC dw >= +0.3\n", b_ok ? "OK" : "UYARI");
    double ec_drift =
        fabs(fixed_to_float(net.syn[1].weight - PNP_W0));
    bool d_ok = (ec_drift < 0.02) && (test_fires[1] == 0);
    printf("%s (D): EC |dw|=%.6f (<0.02), TEST EC ates=%ld (=0)\n",
           d_ok ? "OK" : "UYARI", ec_drift, test_fires[1]);

    // --- (C) CR ---
    bool c_ok = (test_fires[0] > 0) && (test_fires[2] > 0);
    printf("%s (C): CR NEM=%ld SIC=%ld (>0, sensorsuz)\n",
           c_ok ? "OK" : "UYARI", test_fires[0], test_fires[2]);

    printf("\n=== OZET: KILIT=%s KAZANIM=%s NEGATIF=%s CR=%s ===\n",
           a_ok ? "OK" : "UYARI", b_ok ? "OK" : "UYARI",
           d_ok ? "OK" : "UYARI", c_ok ? "OK" : "UYARI");

    // --- (R) Rail-C + genis post ozeti (FAZ 2, bilgi; kapilari degistirmez).
    printf("\n=== (R) DUAL-RAIL (7 grounding + 2 capraz) ===\n");
    for (int k = PNP_NUM_BASE; k < PNP_NUM_POST; ++k) {
        double dwx = fixed_to_float(net.syn[k].weight - PNP_W0);
        printf("%s: w=%.4f (dw=%+.4f)\n", post_name[k],
               fixed_to_float(net.syn[k].weight), dwx);
    }
    printf("Rail-C tasiyici sayac (son pencere): hn=%d ec=%d hs=%d ts=%d "
           "tn=%d ph=%d npk=%d\n",
           net.channel_carrier[0].count, net.channel_carrier[1].count,
           net.channel_carrier[2].count, net.channel_carrier[3].count,
           net.channel_carrier[4].count, net.channel_carrier[5].count,
           net.channel_carrier[6].count);
    return 0;
}

// Stream satiri isle: SET <sensor> <0-100> / RESET / QUIT.
// Donus: 0=devam, 1=QUIT, 2=RESET istendi.
int handle_stream_line(char* line, PlantNpu& net, int32_t& t, long* fires) {
    while (*line == ' ' || *line == '\t') ++line;
    size_t n = strlen(line);
    while (n > 0 && (line[n - 1] == '\n' || line[n - 1] == '\r' ||
                     line[n - 1] == ' ' || line[n - 1] == '\t')) {
        line[--n] = '\0';
    }
    if (n == 0 || line[0] == '#') return 0;
    if (strcmp(line, "QUIT") == 0) {
        printf("OK QUIT t=%d\n", (int)t);
        fflush(stdout);
        return 1;
    }
    if (strcmp(line, "RESET") == 0) {
        plant_init(net, PNP_SENSOR_AMP, PNP_ETA, PNP_W0);
        g_stim = 7002u;
        t = 0;  // stream saati basa sarar
        for (int k = 0; k < PNP_NUM_POST; ++k) fires[k] = 0;
        printf("OK RESET\n");
        fflush(stdout);
        return 2;
    }
    char gname[16];
    if (sscanf(line, "SENSOR_OFF %15s", gname) == 1) {
        int c = chan_index_by_name(gname);
        if (c < 0) {
            printf("ERR SENSOR_OFF kullanim: "
                   "SENSOR_OFF <hs|ts|hn|tn|ph|npk|ec>\n");
            fflush(stdout);
            return 0;
        }
        g_sensor_gate[c] = 0;
        printf("OK SENSOR_OFF %s\n", gname);
        fflush(stdout);
        return 0;
    }
    if (sscanf(line, "SENSOR_ON %15s", gname) == 1) {
        int c = chan_index_by_name(gname);
        if (c < 0) {
            printf("ERR SENSOR_ON kullanim: "
                   "SENSOR_ON <hs|ts|hn|tn|ph|npk|ec>\n");
            fflush(stdout);
            return 0;
        }
        g_sensor_gate[c] = 1;
        printf("OK SENSOR_ON %s\n", gname);
        fflush(stdout);
        return 0;
    }
    char name[16];
    int val = -1;
    if (sscanf(line, "SET %15s %d", name, &val) == 2) {
        int* dst = sensor_ptr_by_name(name);
        if (dst == nullptr || val < 0 || val > 100) {
            printf("ERR SET kullanim: SET <hs|ts|hn|tn|ph|npk|ec> <0-100>\n");
            fflush(stdout);
            return 0;
        }
        *dst = val;
        if (strcmp(name, "nem") == 0 || strcmp(name, "sicaklik") == 0) {
            printf("OK SET %s=%d (eski ad)\n", name, val);
        } else {
            printf("OK SET %s=%d\n", name, val);
        }
        fflush(stdout);
        return 0;
    }
    printf("ERR bilinmeyen komut (SET/RESET/QUIT/SENSOR_OFF/SENSOR_ON)\n");
    fflush(stdout);
    return 0;
}

int run_stream() {
    synapse_build_luts();
    printf("=== BITKI NPU stream (dual-rail) ===\n");
    printf("komut: SET <hs|ts|hn|tn|ph|npk|ec> <0-100> | RESET | QUIT | "
           "SENSOR_OFF/ON <sensor> (stdin), telemetri her 25 tick "
           "(stdout)\n");
    fflush(stdout);

    PlantNpu net;
    plant_init(net, PNP_SENSOR_AMP, PNP_ETA, PNP_W0);
    g_stim = 7002u;

    int32_t post_tau[PNP_NUM_POST];
    for (int k = 0; k < PNP_NUM_POST; ++k) {
        post_tau[k] = (PNP_POST_BAND[k] == 0) ? 4 : 12;
    }
    long fires[PNP_NUM_POST] = {0};

    bool stdin_eof = false;
    int32_t t = 0;
    bool quit = false;
    // Canli terminal: QUIT gelene kadar sonsuz dongu; T_TOTAL siniri yok.
    // Batch kosusu run_batch'tedir, bu fonksiyona asla dusulmez.
#if PNP_HAVE_SELECT
    // select()+fgets() karisimi YASAK: tek read() iki satiri birden stdio
    // tamponuna cekip select'i kor birakir (QUIT yutulurdu). Ham
    // non-blocking read() + el yapimi satir biriktirici kullanilir.
    int sfl = fcntl(STDIN_FILENO, F_GETFL, 0);
    if (sfl != -1) fcntl(STDIN_FILENO, F_SETFL, sfl | O_NONBLOCK);
    char line_acc[256];
    size_t line_len = 0;
#endif
    while (!quit) {
        // Stdin komut yoklamasi (bloklamaz). EOF serbest kosuya dusurur
        // ama donguyu KIRMAZ; tek cikis QUIT'tir.
        if (!stdin_eof) {
#if PNP_HAVE_SELECT
            bool do_reset = false;
            for (;;) {
                char chunk[128];
                ssize_t n = read(STDIN_FILENO, chunk, sizeof(chunk));
                if (n < 0) {
                    if (errno == EAGAIN || errno == EWOULDBLOCK) break;
                    stdin_eof = true;  // gercek hata -> serbest kosu
                    break;
                }
                if (n == 0) {
                    stdin_eof = true;  // EOF -> serbest kosu, cikis degil
                    break;
                }
                for (ssize_t i = 0; i < n; ++i) {
                    if (chunk[i] == '\n') {
                        char line[128];
                        size_t cp = line_len < sizeof(line) - 1
                                        ? line_len
                                        : sizeof(line) - 1;
                        memcpy(line, line_acc, cp);
                        line[cp] = '\0';
                        line_len = 0;
                        int rc = handle_stream_line(line, net, t, fires);
                        if (rc == 1) {
                            quit = true;
                            break;
                        }
                        if (rc == 2) do_reset = true;
                    } else if (line_len < sizeof(line_acc) - 1) {
                        line_acc[line_len++] = chunk[i];
                    }
                }
                if (quit) break;
            }
            if (quit) break;
            if (do_reset) continue;  // RESET: sayaclar sifirlandi, tick atla
#else
            stdin_eof = true;  // select yoksa serbest kosu
#endif
        }

        int chan_val[PNP_MAX_SENSORS];
        chan_values(chan_val);
        fixed_t w = super_wire(t, true);
        bool sspike[PNP_MAX_POST] = {false};
        for (int k = 0; k < PNP_NUM_POST; ++k) {
            int c = PNP_POST_CHAN[k];
            // Afferent kapi (yalniz stream): kapali kanal spike uretmez.
            sspike[k] = g_sensor_gate[c] &&
                        sensor_to_spike(chan_val[c], post_tau[k], t);
        }
        fixed_t dw[PNP_MAX_POST] = {0};
        PlantTickResult pr = plant_tick(net, t, w, sspike, dw);
        for (int k = 0; k < PNP_NUM_POST; ++k) {
            if (pr.post_fired[k]) fires[k]++;
        }

        if (t % 25 == 0) {
            printf("T %d wire=%.4f f=", (int)t, fixed_to_float(w));
            for (int k = 0; k < PNP_NUM_POST; ++k) {
                printf("%d", pr.post_fired[k] ? 1 : 0);
            }
            printf(" w=");
            for (int k = 0; k < PNP_NUM_POST; ++k) {
                printf("%.3f%c", fixed_to_float(net.syn[k].weight),
                       k + 1 < PNP_NUM_POST ? ',' : ' ');
            }
            printf("cc=%d,%d,%d,%d,%d,%d,%d\n",
                   net.channel_carrier[0].count,
                   net.channel_carrier[1].count,
                   net.channel_carrier[2].count,
                   net.channel_carrier[3].count,
                   net.channel_carrier[4].count,
                   net.channel_carrier[5].count,
                   net.channel_carrier[6].count);
            fflush(stdout);
        }
        ++t;
#if PNP_HAVE_SELECT
        usleep(20000);  // canli tempo: ~50 tick/s -> telemetri ~2 Hz
#endif
    }
    printf("=== OZET: t=%d fires=%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld ===\n",
           (int)t, fires[0], fires[1], fires[2], fires[3], fires[4], fires[5],
           fires[6], fires[7], fires[8]);
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    if (!parse_cli(argc, argv)) return 1;
    if (g_stream) return run_stream();
    return run_batch();
}
