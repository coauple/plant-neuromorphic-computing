// ---------------------------------------------------------------------------
// Duyusal Lob v2 (FAZ 3) harness — P1 faz hatlari + P2 kosul bankasi.
//
// Varsayilan senaryo (MC: validate_sensory_lobe.py):
//   P1 hatlari: p1a tau4, p1b tau12 (her biri kendi hatti, tek darbe).
//   P2 bankasi (10 aktif, kural: 7 grounding + 1 replika + 2 decoy):
//     p2a (A4,HN,tau35,w0.2) + p2b (A12,HS,tau45,w0.2) + p2c (p2a replika,
//     w0.1, eszamanli kosul ispati) + decoy p2d (HN,tau36) & p2e (HS,tau44)
//     + negatif p2f (EC, deger 40/OFF) + grounding p2g..p2j (TS/TN/PH/NPK,
//     deger 60 ON, tau37).
//   Kosullanma (10x500, sensorler acik) + test (3x500, sensorler 0 -> CR).
//
// Faz sifreleme (CPU cevirici, yalniz harness): tau_b(v)=4+v*56/100
// (v>=50 ON; HN=56->35, HS=74->45); hat darbesi t%tau==0, burst 1
// (burst 2 decoy kabullerini %50 artirir, gercege yaramaz — MC karari).
// Cekirdek (sensory_lobe.h) deger/esik BILMEZ: yalniz darbe bayraklari.
// Olcum double'i YALNIZ bu dosyada (cekirdekte float/double YOK).
// ---------------------------------------------------------------------------

#include <cmath>
#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#if defined(__unix__) || defined(__APPLE__)
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#define SL_HAVE_POSIX 1
#else
#define SL_HAVE_POSIX 0
#endif
#include "sensory_lobe.h"

namespace {

constexpr int BLOCK_LEN = 500;
constexpr int N_COND = 10;
constexpr int N_TEST = 3;

// Kanal sirasi: HN,EC,HS,TS,TN,PH,NPK (plant_npu disiplini).
int g_hn = 56;
int g_ec = 40;
int g_hs = 74;
int g_ts = 60;
int g_tn = 60;
int g_ph = 60;
int g_npk = 60;
bool g_stream = false;
bool g_selforg = false;
bool g_stress = false;

constexpr fixed_t SL_AMP = fixed_from_double(1.0);
// Kalibrasyon (grid + A-alone esik haritasi, bkz. §9.14):
// P1a 0.7 (HN hizi kisilir, oran korunur), P1b 4.0 (yavas hat doygun
// surus; 2.0->4.0 arasi eşiğe kadar etkisiz, 4.0'da her darbede ates).
constexpr fixed_t SL_P1_AMPS[2] = {fixed_from_double(0.7),
                                         fixed_from_double(4.0)};
constexpr fixed_t SL_ETA = fixed_from_double(0.30);
// Kalibrasyon probu: --w0 ile tum postlar ayni w0'dan baslar.
bool g_w0_override = false;
fixed_t g_w0_value = fixed_from_double(0.2);

int32_t sl_tau_of_value(int v) {
    return 4 + (v * 56) / 100;
}

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

void chan_values(int out[7]) {
    out[0] = g_hn;
    out[1] = g_ec;
    out[2] = g_hs;
    out[3] = g_ts;
    out[4] = g_tn;
    out[5] = g_ph;
    out[6] = g_npk;
}

void print_help() {
    printf("kullanim: npu_sensory_lobe [sensorler] [--stream] [--w0 W] "
           "[--selforg] [--stress]\n"
           "  --hs/--ts/--hn/--tn/--ph/--npk/--ec V (0-100)\n"
           "    varsayilan: hs=74 ts=60 hn=56 tn=60 ph=60 npk=60 ec=40\n"
           "  --w0 W: tum postlarin baslangic agirligi (kalibrasyon probu)\n"
           "  --selforg: FAZ 4 oz-orgutlenme gostergesi (ortak yol + havuz)\n"
           "  --stress: genis-bant stres (hizli yenilik + tabana donus)\n"
           "  --stream: stdin SET/RESET/QUIT, stdout telemetri\n");
}

bool parse_cli(int argc, char** argv) {
    for (int i = 1; i < argc; ++i) {
        char* a = argv[i];
        if (strcmp(a, "--help") == 0) {
            print_help();
            exit(1);
        }
        if (strcmp(a, "--stream") == 0) {
            g_stream = true;
            continue;
        }
        if (strcmp(a, "--selforg") == 0) {
            g_selforg = true;
            continue;
        }
        if (strcmp(a, "--stress") == 0) {
            g_stress = true;
            continue;
        }
        const char* eq = strchr(a, '=');
        char key[32];
        const char* val = nullptr;
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
            if (i + 1 >= argc) {
                fprintf(stderr, "HATA: '%s' deger bekliyor\n", key);
                return false;
            }
            val = argv[++i];
        }
        if (strcmp(key, "--w0") == 0) {
            char* end2 = nullptr;
            double wv = strtod(val, &end2);
            if (*end2 != '\0' || wv < 0.0 || wv > 2.0) {
                fprintf(stderr, "HATA: --w0 0-2 arasi olmali\n");
                return false;
            }
            g_w0_override = true;
            g_w0_value = fixed_from_double(wv);
            continue;
        }
        int* dst = sensor_ptr_by_name(key[0] == '-' && key[1] == '-'
                                          ? key + 2
                                          : key);
        if (dst == nullptr) {
            fprintf(stderr, "HATA: bilinmeyen arguman '%s' (--help)\n", key);
            return false;
        }
        char* end = nullptr;
        long v = strtol(val, &end, 10);
        if (*end != '\0' || v < 0 || v > 100) {
            fprintf(stderr, "HATA: %s 0-100 olmali\n", key);
            return false;
        }
        *dst = (int)v;
    }
    return true;
}

// Varsayilan P2 bankasi (10 aktif). Dondurulen dizi harness omrunce yasar.
constexpr int SL_NUM_P2 = 10;
SlPostCfg* default_bank() {
    static SlPostCfg cfg[SL_NUM_P2];
    static bool built = false;
    if (!built) {
        // p2a..p2f: plan senaryosu (HN=56->35, HS=74->45, EC=40->26 OFF).
        cfg[0] = {0, 0, 35, fixed_from_double(0.2)};  // p2a HN
        cfg[1] = {1, 2, 45, fixed_from_double(0.2)};  // p2b HS
        cfg[2] = {0, 0, 35, fixed_from_double(0.1)};  // p2c replika
        cfg[3] = {0, 0, 36, fixed_from_double(0.0)};  // p2d decoy HN
        cfg[4] = {1, 2, 46, fixed_from_double(0.0)};  // p2e decoy HS (tau+1)
        cfg[5] = {0, 1, 26, fixed_from_double(0.2)};  // p2f EC negatif
        // p2g..p2j: kalan sensorler (60->37 ON, paylasilan P1 hatti).
        cfg[6] = {0, 3, 37, fixed_from_double(0.2)};  // p2g TS
        cfg[7] = {1, 4, 37, fixed_from_double(0.2)};  // p2h TN
        cfg[8] = {0, 5, 37, fixed_from_double(0.2)};  // p2i PH
        cfg[9] = {1, 6, 37, fixed_from_double(0.2)};  // p2j NPK
        if (g_w0_override) {
            for (int k = 0; k < SL_NUM_P2; ++k) cfg[k].w0 = g_w0_value;
        }
        built = true;
    }
    return cfg;
}

void print_topology() {
    static const char* ch_name[7] = {"HN", "EC", "HS", "TS",
                                     "TN", "PH", "NPK"};
    printf("topoloji: P1 p1a(tau4) p1b(tau12); P2 bankasi:\n");
    SlPostCfg* cfg = default_bank();
    for (int k = 0; k < SL_NUM_P2; ++k) {
        char lbl[16];
        sl_render_label(k, true, lbl, sizeof(lbl));
        char plbl[16];
        sl_render_label(cfg[k].p1_src, false, plbl, sizeof(plbl));
        printf("  %s: A<-%s B<-%s(tau%+d) w0=%.1f\n", lbl, plbl,
               ch_name[cfg[k].sensor_ch], (int)cfg[k].tau_b,
               (double)cfg[k].w0 / 65536.0);
    }
}

int run_batch();
int run_stream();

int run_batch() {
    synapse_build_luts();
    printf("=== DUYUSAL LOB v2: P1 faz hatlari + P2 kosul bankasi ===\n");
    print_topology();

    SensoryLobe lobe;
    int32_t p1_taus[2] = {4, 12};
    sl_init(lobe, p1_taus, 2, default_bank(), SL_NUM_P2, SL_AMP, SL_P1_AMPS, SL_ETA);

    FILE* csv = fopen("sensory_lobe_learning.csv", "w");
    if (!csv) {
        fprintf(stderr, "HATA: sensory CSV acilamadi\n");
        return 1;
    }
    fprintf(csv, "tick,block,stage,p1a,p1b,p2fires,w0,w1,w2,w3,w4,w5,w6,w7,"
                 "w8,w9\n");

    int chan_val[7];
    chan_values(chan_val);

    // B-kabul sayaci (ilk darbe haric): last_input degisimi izlenir.
    int32_t prev_b_in[SL_NUM_P2];
    bool had_b[SL_NUM_P2] = {false};
    long b_acc[SL_NUM_P2] = {0};
    for (int k = 0; k < SL_NUM_P2; ++k) {
        prev_b_in[k] = lobe.p2[k].branch_B_last_input_tick;
    }
    // P1 kilit: hat darbesi +-2 tick icinde ates kapsama.
    long p1_pulses[2] = {0, 0};
    long p1_cover[2] = {0};
    static bool p1_fired_at[2][(N_COND + N_TEST) * BLOCK_LEN];
    for (int i = 0; i < 2; ++i) {
        for (int t = 0; t < (N_COND + N_TEST) * BLOCK_LEN; ++t) {
            p1_fired_at[i][t] = false;
        }
    }

    double cond_dw[SL_NUM_P2] = {0};
    long cond_fires[SL_NUM_P2] = {0};
    long test_fires[SL_NUM_P2] = {0};
    const int T_TOTAL = (N_COND + N_TEST) * BLOCK_LEN;

    int32_t t = 0;
    int block_id = 0;
    fixed_t w_cond_start[SL_NUM_P2];  // kosullanma BASI agirliklari
    for (int k = 0; k < SL_NUM_P2; ++k) {
        w_cond_start[k] = lobe.syn[k].weight;
    }
    for (int stage = 0; stage < 2; ++stage) {
        int nblocks = (stage == 0) ? N_COND : N_TEST;
        for (int blk = 0; blk < nblocks; ++blk, ++block_id) {
            for (int bt = 0; bt < BLOCK_LEN; ++bt, ++t) {
                bool p1p[2] = {(t % 4) == 0, (t % 12) == 0};
                bool sp[SL_NUM_P2] = {false};
                if (stage == 0) {
                    SlPostCfg* cfg = default_bank();
                    for (int k = 0; k < SL_NUM_P2; ++k) {
                        int v = chan_val[cfg[k].sensor_ch];
                        if (v >= 50) {
                            sp[k] = (t % sl_tau_of_value(v)) == 0;
                        }
                    }
                }
                fixed_t dw[P2_MAX] = {0};
                SensoryTickResult r =
                    sensory_tick(lobe, t, p1p, sp, dw);
                for (int i = 0; i < 2; ++i) {
                    if (p1p[i]) p1_pulses[i]++;
                    if (r.p1_fired[i]) {
                        p1_fired_at[i][t] = true;
                        if (stage == 0) {
                            // kapsama asagida toplu hesaplanir
                        }
                    }
                }
                for (int k = 0; k < SL_NUM_P2; ++k) {
                    int32_t bi = lobe.p2[k].branch_B_last_input_tick;
                    if (bi != prev_b_in[k]) {
                        if (had_b[k] && stage == 0) b_acc[k]++;
                        had_b[k] = true;
                        prev_b_in[k] = bi;
                    }
                    if (r.p2_fired[k]) {
                        if (stage == 0) cond_fires[k]++;
                        else test_fires[k]++;
                    }
                }
                bool any = false;
                for (int k = 0; k < SL_NUM_P2; ++k) {
                    if (r.p2_fired[k]) {
                        any = true;
                        break;
                    }
                }
                if (any) {
                    char lbl[64];
                    bool fired[SL_NUM_P2];
                    for (int k = 0; k < SL_NUM_P2; ++k) {
                        fired[k] = r.p2_fired[k];
                    }
                    sl_condition_label(fired, SL_NUM_P2, lbl, sizeof(lbl));
                    printf("K t=%d %s kosul\n", (int)t, lbl);
                }
                fprintf(csv, "%d,%d,%d,%d,%d,", t, block_id, stage,
                        r.p1_fired[0] ? 1 : 0, r.p1_fired[1] ? 1 : 0);
                for (int k = 0; k < SL_NUM_P2; ++k) {
                    fprintf(csv, "%d", r.p2_fired[k] ? 1 : 0);
                }
                for (int k = 0; k < SL_NUM_P2; ++k) {
                    fprintf(csv, ",%.6f",
                            (double)lobe.syn[k].weight / 65536.0);
                }
                fprintf(csv, "\n");
            }
            if (stage == 0 && blk == N_COND - 1) {
                for (int k = 0; k < SL_NUM_P2; ++k) {
                    cond_dw[k] = ((double)lobe.syn[k].weight -
                                  (double)w_cond_start[k]) / 65536.0;
                }
            }
        }
    }
    fclose(csv);

    // P1 kapsama: her hat darbesi +-2 tick icinde ates gordu mu.
    for (int i = 0; i < 2; ++i) {
        int32_t tau = (i == 0) ? 4 : 12;
        for (int32_t p = 0; p < N_COND * BLOCK_LEN; p += tau) {
            for (int32_t o = -2; o <= 2; ++o) {
                if (p + o >= 0 && p + o < T_TOTAL &&
                    p1_fired_at[i][p + o]) {
                    p1_cover[i]++;
                    break;
                }
            }
        }
    }

    static const char* pname[SL_NUM_P2] = {
        "p2a", "p2b", "p2c", "p2d", "p2e",
        "p2f", "p2g", "p2h", "p2i", "p2j"};
    printf("\n=== KOSUL KAZANIMI ===\n");
    for (int k = 0; k < SL_NUM_P2; ++k) {
        printf("%s: dw=%+.4f cond=%ld test(CR)=%ld B Kabul(ilk-haric)=%ld\n",
               pname[k], cond_dw[k], cond_fires[k], test_fires[k],
               b_acc[k]);
    }
    double cov0 = p1_pulses[0] > 0
                      ? (double)p1_cover[0] /
                            (double)(N_COND * BLOCK_LEN / 4)
                      : 0.0;
    double cov1 = p1_pulses[1] > 0
                      ? (double)p1_cover[1] /
                            (double)(N_COND * BLOCK_LEN / 12)
                      : 0.0;
    printf("P1 kilit: cov4=%.2f cov12=%.2f\n", cov0, cov1);

    // (A) secicilik: MUTLAK sifir degil ORAN kapisi. Gerekce: B-PLIR
    // yeniden-kilit kabulleri kacinilmaz (MC: decoy/gercek ~0.33-0.34,
    // FDM §9.8 sinir-ii ile ayni fizik). Ayrica decoy agirligi olculmus
    // A-alone sessizlik siniri (<=0.3) altinda kalmali (--w0 haritasi).
    bool a_acc_ok = (b_acc[3] * 2 <= b_acc[0] + 2) &&
                    (b_acc[4] * 2 <= b_acc[1] + 2);
    bool a_w_ok = (lobe.syn[3].weight <= fixed_from_double(0.3)) &&
                  (lobe.syn[4].weight <= fixed_from_double(0.3));
    bool a_ok = a_acc_ok && a_w_ok &&
                (test_fires[3] == 0) && (test_fires[4] == 0);
    printf("%s (A): decoy kabul<=0.5x (MC 0.33), w<=0.3 (A-alone sinir), "
           "CR=0\n",
           a_ok ? "OK" : "UYARI");
    bool b_ok = (cond_dw[0] >= 0.3) && (cond_dw[1] >= 0.3) &&
                (test_fires[0] > 0) && (test_fires[1] > 0);
    printf("%s (B): p2a/p2b dw>=+0.3, CR>0\n", b_ok ? "OK" : "UYARI");
    double neg = fabs(((double)lobe.syn[5].weight -
                       fixed_from_double(0.2)) / 65536.0);
    bool c_ok = (neg < 0.02) && (test_fires[5] == 0);
    printf("%s (C): p2f |dw|=%.6f (<0.02), CR=0\n", c_ok ? "OK" : "UYARI",
           neg);
    bool d_ok = (cov0 >= 0.40) && (cov1 >= 0.40);
    printf("%s (D): P1 cov>=0.40\n", d_ok ? "OK" : "UYARI");
    printf("\n=== OZET: A=%s B=%s C=%s D=%s ===\n", a_ok ? "OK" : "UYARI",
           b_ok ? "OK" : "UYARI", c_ok ? "OK" : "UYARI",
           d_ok ? "OK" : "UYARI");
    return 0;
}

int handle_stream_line(char* line, SensoryLobe& lobe, int32_t& t) {
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
        int32_t p1_taus[2] = {4, 12};
        sl_init(lobe, p1_taus, 2, default_bank(), SL_NUM_P2, SL_AMP, SL_P1_AMPS,
                SL_ETA);
        t = 0;
        printf("OK RESET\n");
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
        printf("OK SET %s=%d\n", name, val);
        fflush(stdout);
        return 0;
    }
    printf("ERR bilinmeyen komut (SET/RESET/QUIT)\n");
    fflush(stdout);
    return 0;
}

int run_stream() {
    synapse_build_luts();
    printf("=== DUYUSAL LOB v2 stream ===\n");
    print_topology();
    fflush(stdout);

    SensoryLobe lobe;
    int32_t p1_taus[2] = {4, 12};
    sl_init(lobe, p1_taus, 2, default_bank(), SL_NUM_P2, SL_AMP, SL_P1_AMPS, SL_ETA);

    bool stdin_eof = false;
    int32_t t = 0;
    bool quit = false;
#if SL_HAVE_POSIX
    int sfl = fcntl(STDIN_FILENO, F_GETFL, 0);
    if (sfl != -1) fcntl(STDIN_FILENO, F_SETFL, sfl | O_NONBLOCK);
    char line_acc[256];
    size_t line_len = 0;
#endif
    while (!quit) {
        if (!stdin_eof) {
#if SL_HAVE_POSIX
            for (;;) {
                char chunk[128];
                ssize_t n = read(STDIN_FILENO, chunk, sizeof(chunk));
                if (n < 0) {
                    if (errno == EAGAIN || errno == EWOULDBLOCK) break;
                    stdin_eof = true;
                    break;
                }
                if (n == 0) {
                    stdin_eof = true;
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
                        if (handle_stream_line(line, lobe, t) == 1) {
                            quit = true;
                            break;
                        }
                    } else if (line_len < sizeof(line_acc) - 1) {
                        line_acc[line_len++] = chunk[i];
                    }
                }
                if (quit) break;
            }
            if (quit) break;
#else
            stdin_eof = true;
#endif
        }
        int chan_val[7];
        chan_values(chan_val);
        bool p1p[2] = {(t % 4) == 0, (t % 12) == 0};
        bool sp[SL_NUM_P2] = {false};
        SlPostCfg* cfg = default_bank();
        for (int k = 0; k < SL_NUM_P2; ++k) {
            int v = chan_val[cfg[k].sensor_ch];
            if (v >= 50) sp[k] = (t % sl_tau_of_value(v)) == 0;
        }
        fixed_t dw[P2_MAX] = {0};
        SensoryTickResult r = sensory_tick(lobe, t, p1p, sp, dw);
        bool any = false;
        for (int k = 0; k < SL_NUM_P2; ++k) {
            if (r.p2_fired[k]) {
                any = true;
                break;
            }
        }
        if (any) {
            char lbl[64];
            bool fired[SL_NUM_P2];
            for (int k = 0; k < SL_NUM_P2; ++k) {
                fired[k] = r.p2_fired[k];
            }
            sl_condition_label(fired, SL_NUM_P2, lbl, sizeof(lbl));
            printf("K t=%d %s kosul\n", (int)t, lbl);
        }
        if (t % 25 == 0) {
            printf("T %d p1=%d%d p2=", (int)t, r.p1_fired[0] ? 1 : 0,
                   r.p1_fired[1] ? 1 : 0);
            for (int k = 0; k < SL_NUM_P2; ++k) {
                printf("%d", r.p2_fired[k] ? 1 : 0);
            }
            printf(" w=");
            for (int k = 0; k < SL_NUM_P2; ++k) {
                printf("%.3f%c", (double)lobe.syn[k].weight / 65536.0,
                       k + 1 < SL_NUM_P2 ? ',' : ' ');
            }
            printf("\n");
            fflush(stdout);
        }
        ++t;
#if SL_HAVE_POSIX
        usleep(20000);
#endif
    }
    return 0;
}

// --- FAZ 4 oz-orgutlenme (--selforg) ----------------------------------------
// Etiketsiz havuz (14 slot, tau dagilimi) ORTAK yolu dinler; atanmis hat
// YOK. Kimlik rezonanstan cikar: kabul ISI medyani -> "p2@tau<M>".
// Yenilik: sahipsiz nabizlarin ardisik fark medyani yeni periyodu olcer;
// esik (7 nabiz, kumelenme, 400 tick soguma) tutarsa sl_add_post ile
// yedekten ise alim. Secim-fazi: eta=0 (agirliklar donuk, yalniz kilit).

// Havuz davranis araligini kapsar (26..60 sensor bandi). Kucuk tau'lar
// (4..16) DIŞARIDA: kilitleri kisa (2*tau+1) oldugu icin karisik yolda
// her boslukta taze-kabul yapip SAHIPSIZ nabiz sinyalini bogarlar;
// secim ispatina katkilari yok (sunulan bilesen en kisa 35).
constexpr int SF_POOL = 12;
constexpr int32_t SF_SPREAD[SF_POOL] = {20, 24, 28, 32, 35, 36,
                                        40, 44, 48, 52, 56, 60};
constexpr int SF_F1_END = 1500;   // bus {35}
constexpr int SF_F2_END = 3500;   // bus {35,37}
constexpr int SF_T_END = 5500;    // bus {35,37,45}
constexpr int SF_BUS_CH = 7;      // ortak yol isareti (harness icin)
constexpr int SF_HIST = 24;       // slot basina kabul gecmisi

int sf_median_label(const int32_t* hist, int n) {
    if (n < 3) return -1;
    int32_t d[SF_HIST];
    int nd = 0;
    for (int i = 1; i < n && nd < SF_HIST; ++i) {
        d[nd++] = hist[i] - hist[i - 1];
    }
    for (int i = 0; i < nd; ++i) {
        for (int j = i + 1; j < nd; ++j) {
            if (d[j] < d[i]) {
                int32_t tmp = d[i];
                d[i] = d[j];
                d[j] = tmp;
            }
        }
    }
    return (nd % 2 == 1) ? d[nd / 2] : (d[nd / 2 - 1] + d[nd / 2]) / 2;
}

int run_selforg() {
    synapse_build_luts();
    printf("=== FAZ 4 oz-orgutlenme: ortak yol + etiketsiz havuz ===\n");
    printf("havuz(%d):", SF_POOL);
    for (int i = 0; i < SF_POOL; ++i) printf(" tau%d", (int)SF_SPREAD[i]);
    printf("\n faz: [0,1500) bus{35} [1500,3500) +37 [3500,5500) +45\n");

    SensoryLobe lobe;
    int32_t p1_taus[2] = {4, 12};
    SlPostCfg pool[SF_POOL];
    for (int i = 0; i < SF_POOL; ++i) {
        pool[i].p1_src = i % 2;
        pool[i].sensor_ch = SF_BUS_CH;
        pool[i].tau_b = SF_SPREAD[i];
        pool[i].w0 = fixed_from_double(0.2);
    }
    sl_init(lobe, p1_taus, 2, pool, SF_POOL, SL_AMP, SL_P1_AMPS,
            fixed_from_double(0.0));  // secim-fazi: ogrenme kapali

    FILE* csv = fopen("sensory_selforg.csv", "w");
    if (!csv) {
        fprintf(stderr, "HATA: selforg CSV acilamadi\n");
        return 1;
    }
    fprintf(csv, "tick,phase,bus,n_posts,acc35\n");

    int32_t prev_b[P2_MAX];
    int32_t hist[P2_MAX][SF_HIST];
    int hist_n[P2_MAX] = {0};
    long acc_total[P2_MAX] = {0};  // hic kirpilmaz (kapilar icin)
    // Rezonans-kabul ayirimi (FAZ 4 dersi): yogun yolda HER slot
    // kilit-suresi dolunca taze-kabul yapar (kabul != kilit!).
    // Yenilik SADECE rezonans kabullere (ISI==tau) bakar; taze-kabuller
    // sayilir ama sahiplenmez.
    int32_t last_acc[P2_MAX];
    for (int k = 0; k < P2_MAX; ++k) {
        prev_b[k] = -2;
        last_acc[k] = -1;
    }
    int acc35_f1snap = 0;
    int32_t unclaimed[12];
    int unclaimed_n = 0;
    int32_t last_hire = -10000;
    int hire_tau[8];
    int hire_tick[8];
    long hire_acc0[8] = {0};
    int n_hire = 0;
    int idx35 = -1;
    for (int i = 0; i < SF_POOL; ++i) {
        if (SF_SPREAD[i] == 35) idx35 = i;
    }

    for (int32_t t = 0; t < SF_T_END; ++t) {
        int phase = (t < SF_F1_END) ? 1 : ((t < SF_F2_END) ? 2 : 3);
        bool bus = (t % 35) == 0;
        if (phase >= 2) bus = bus || ((t % 37) == 0);
        if (phase >= 3) bus = bus || ((t % 45) == 0);
        bool p1p[2] = {(t % 4) == 0, (t % 12) == 0};
        bool sp[P2_MAX] = {false};
        for (int k = 0; k < lobe.num_p2; ++k) sp[k] = bus;
        fixed_t dw[P2_MAX] = {0};
        sensory_tick(lobe, t, p1p, sp, dw);

        int claimed = 0;
        for (int k = 0; k < lobe.num_p2; ++k) {
            int32_t bi = lobe.p2[k].branch_B_last_input_tick;
            if (bi != prev_b[k]) {
                prev_b[k] = bi;
                if (bi == t) {
                    bool res = (last_acc[k] >= 0) &&
                               ((t - last_acc[k]) == lobe.tau_b[k]);
                    last_acc[k] = t;
                    if (res) claimed++;
                    acc_total[k]++;
                    if (hist_n[k] < SF_HIST) {
                        hist[k][hist_n[k]++] = t;
                    } else {
                        for (int i = 1; i < SF_HIST; ++i) {
                            hist[k][i - 1] = hist[k][i];
                        }
                        hist[k][SF_HIST - 1] = t;
                    }
                }
            }
        }
        if (t == SF_F1_END && idx35 >= 0) acc35_f1snap = (int)acc_total[idx35];
        if (bus && claimed == 0) {
            if (unclaimed_n < 12) {
                unclaimed[unclaimed_n++] = t;
            } else {
                for (int i = 1; i < 12; ++i) unclaimed[i - 1] = unclaimed[i];
                unclaimed[11] = t;
            }
            // Ise-alim karari: 7 sahipsiz, SIKI kumelenme (6'da 5),
            // soguma 400 + faz-yerlesme 300 (faz gecisi karisikliginda
            // alt-harmonik hayalet ise-alim olur — gozlemlendi, §9.15).
            int32_t phase_start = (t < SF_F1_END)      ? 0
                                  : ((t < SF_F2_END) ? SF_F1_END : SF_F2_END);
            if (unclaimed_n >= 7 && n_hire < 8 &&
                (t - last_hire) > 400 && (t - phase_start) > 300) {
                int32_t d[6];
                for (int i = 0; i < 6; ++i) {
                    d[i] = unclaimed[unclaimed_n - 7 + i + 1] -
                           unclaimed[unclaimed_n - 7 + i];
                }
                for (int i = 0; i < 6; ++i) {
                    for (int j = i + 1; j < 6; ++j) {
                        if (d[j] < d[i]) {
                            int32_t tmp = d[i];
                            d[i] = d[j];
                            d[j] = tmp;
                        }
                    }
                }
                // Harmonik kontrol (perde-duyusu oktav kurali): medyan m
                // bir katin periyodu da olabilir (komsu kapilar her
                // ikinci nabzi yer, farklar 2m'ye cikar). Adaylar m,
                // m/2, m/3 (tamsayi); aciklayan + tekrarsiz ilk aday
                // ise alinir.
                int32_t cands[3] = {(d[2] + d[3]) / 2, -1, -1};
                if (cands[0] % 2 == 0) cands[1] = cands[0] / 2;
                if (cands[0] % 3 == 0) cands[2] = cands[0] / 3;
                for (int ci = 0; ci < 3; ++ci) {
                    int32_t c = cands[ci];
                    if (c < 4 || c > 60) continue;
                    int explained = 0;
                    int direct = 0;
                    for (int i = 0; i < 6; ++i) {
                        int32_t q = (d[i] + c / 2) / c;
                        if (q >= 1) {
                            int32_t df = d[i] - q * c;
                            if (df < 0) df = -df;
                            if (df <= 3) explained++;
                        }
                        int32_t dd = d[i] - c;
                        if (dd < 0) dd = -dd;
                        if (dd <= 3) direct++;
                    }
                    bool dup = false;
                    for (int k = 0; k < lobe.num_p2; ++k) {
                        if (lobe.tau_b[k] == c) {
                            dup = true;
                            break;
                        }
                    }
                    // Dogrudan-kanit sarti (§9.16): farklar yalnizca
                    // katlarda kumeleniyorsa (ortanca-hayaleti) aday
                    // reddedilir; gercel ton kendi periyodunda da
                    // gozlenir (direct>=2).
                    if (explained >= 5 && direct >= 2 && !dup) {
                        SlPostCfg nc;
                        nc.p1_src = lobe.num_p2 % 2;
                        nc.sensor_ch = SF_BUS_CH;
                        nc.tau_b = c;
                        nc.w0 = fixed_from_double(0.0);
                        if (sl_add_post(lobe, nc, SL_P1_AMPS[nc.p1_src])) {
                            prev_b[lobe.num_p2 - 1] = -2;
                            last_acc[lobe.num_p2 - 1] = -1;
                            hire_acc0[n_hire] = acc_total[lobe.num_p2 - 1];
                            hire_tau[n_hire] = (int)c;
                            hire_tick[n_hire] = (int)t;
                            n_hire++;
                            last_hire = t;
                            unclaimed_n = 0;
                            printf("RECRUIT t=%d tau=%d slot=%d "
                                   "(medyan %d)\n",
                                   (int)t, (int)c, lobe.num_p2 - 1,
                                   (int)cands[0]);
                        }
                        break;
                    }
                }
            }
        }
        if (t % 25 == 0) {
            int a35 = (idx35 >= 0 && hist_n[idx35] > 0) ? hist_n[idx35] : 0;
            fprintf(csv, "%d,%d,%d,%d,%d\n", (int)t, phase, bus ? 1 : 0,
                    lobe.num_p2, a35);
        }
    }
    fclose(csv);

    printf("\n--- olculen etiketler (kabul ISI medyani) ---\n");
    for (int k = 0; k < lobe.num_p2; ++k) {
        int m = sf_median_label(hist[k], hist_n[k]);
        char plbl[16];
        sl_render_label(k, true, plbl, sizeof(plbl));
        // Sikilik: medyan cevresi diff'lerin cogu mu (kilitli mi, gezgin mi)
        bool tight = false;
        if (m > 0 && hist_n[k] >= 4) {
            int in_tol = 0, nd = 0;
            for (int i = 1; i < hist_n[k]; ++i) {
                int32_t df = (hist[k][i] - hist[k][i - 1]) - m;
                if (df < 0) df = -df;
                if (df <= 3) in_tol++;
                nd++;
            }
            tight = (nd > 0) && (in_tol * 2 >= nd);
        }
        if (m > 0 && tight) {
            printf("  %s (tau%+d): p2@tau%d (kabul %d)\n", plbl,
                   (int)lobe.tau_b[k], m, hist_n[k]);
        } else if (m > 0) {
            printf("  %s (tau%+d): gezgin-medyan%d (kabul %d)\n", plbl,
                   (int)lobe.tau_b[k], m, hist_n[k]);
        } else {
            printf("  %s (tau%+d): sessiz (kabul %d)\n", plbl,
                   (int)lobe.tau_b[k], hist_n[k]);
        }
    }

    // Kapilar (MC-turevli esikler; kirpilmamis toplamlar).
    int pulses35_f1 = 0;
    for (int t = 0; t < SF_F1_END; t += 35) pulses35_f1++;
    bool s1 = (idx35 >= 0) && (acc35_f1snap == pulses35_f1);
    printf("%s (S1): tau35 tam kilit %d/%d\n", s1 ? "OK" : "UYARI",
           acc35_f1snap, pulses35_f1);
    int idx36 = -1;
    for (int i = 0; i < SF_POOL; ++i) {
        if (SF_SPREAD[i] == 36) idx36 = i;
    }
    long a35t = (idx35 >= 0) ? acc_total[idx35] : 0;
    long a36t = (idx36 >= 0) ? acc_total[idx36] : 0;
    bool s2 = (a35t >= 2 * a36t);
    printf("%s (S2): komsu orani %ld>=2x%ld\n", s2 ? "OK" : "UYARI", a35t,
           a36t);
    bool s3 = (n_hire == 2) && (hire_tau[0] == 37) &&
              (hire_tau[1] == 45);
    printf("%s (S3): ise-alim sirasi [37,45], olusan [", s3 ? "OK" : "UYARI");
    for (int i = 0; i < n_hire; ++i) {
        printf("%d%s", hire_tau[i], i + 1 < n_hire ? "," : "");
    }
    printf("]\n");
    bool s3b = true;
    for (int h = 0; h < n_hire; ++h) {
        int m = hire_tau[h], ht = hire_tick[h];
        int comp = 0;
        for (int t = ht; t < SF_T_END; ++t) {
            int ph = (t < SF_F1_END) ? 1 : ((t < SF_F2_END) ? 2 : 3);
            bool on = (m == 37 && ph >= 2) || (m == 45 && ph >= 3) ||
                      (m != 37 && m != 45);
            if (on && (t % m) == 0) comp++;
        }
        int slot = SF_POOL + h;
        long got = acc_total[slot] - hire_acc0[h];
        double ratio = comp > 0 ? (double)got / (double)comp : 0.0;
        printf("  hire%d tau%d: %ld/%d (%.2f) %s\n", h, m, got, comp, ratio,
               ratio >= 0.8 ? "OK" : "UYARI");
        if (ratio < 0.8) s3b = false;
    }
    bool s4 = false;
    for (int i = 0; i < hist_n[idx35]; ++i) {
        if (hist[idx35][i] >= SF_T_END - 500) {
            s4 = true;
            break;
        }
    }
    printf("%s (S4): tau35 kilidi son 500 tick'te suruyor\n",
           s4 ? "OK" : "UYARI");
    printf("\n=== OZET-SELFORG: S1=%s S2=%s S3=%s S3b=%s S4=%s ===\n",
           s1 ? "OK" : "UYARI", s2 ? "OK" : "UYARI", s3 ? "OK" : "UYARI",
           s3b ? "OK" : "UYARI", s4 ? "OK" : "UYARI");
    return 0;
}

// --- STRES: genis-bant (--stress) ------------------------------------------
// run_selforg motorunun bagimsiz kopyasi (dogrulanmis yola dokunulmaz).
// Fark: faz tablosu genis (4 hizli yenilik + tabana donus) ve bus birikimli
// (F5'te 5 eszamanli ton). Hizli faz (1200 tick) soguma(400)+yerlesme(300)
// sonrasi hire'a ~500 tick pay birakir; yetismezse faz uzatilir (olculur).
struct st_phase {
    int end;
    int n_tones;
    int tones[6];
};
constexpr int ST_NPH = 10;
constexpr st_phase ST_PH[ST_NPH] = {
    {1000, 1, {35}},                    // F1 taban kilit
    {2200, 2, {35, 26}},                // F2 +alt kenar yenilik
    {3400, 3, {35, 26, 59}},            // F3 +ust kenar yenilik
    {4600, 4, {35, 26, 59, 43}},        // F4 +orta yenilik
    {5800, 5, {35, 26, 59, 43, 50}},    // F5 +orta yenilik (5 ton!)
    {6800, 1, {35}},                    // F6 tabana donus (dropout)
    {7800, 1, {26}},                    // F7 sonda-26 (seyrek dogrulama)
    {8800, 1, {59}},                    // F8 sonda-59
    {9800, 1, {43}},                    // F9 sonda-43
    {10800, 1, {50}},                   // F10 sonda-50
};
constexpr int ST_T_END = 10800;

int run_stress() {
    synapse_build_luts();
    printf("=== STRES: genis-bant (4 yenilik + tabana donus) ===\n");
    printf("havuz(%d):", SF_POOL);
    for (int i = 0; i < SF_POOL; ++i) printf(" tau%d", (int)SF_SPREAD[i]);
    printf("\n");
    for (int p = 0; p < ST_NPH; ++p) {
        int st = (p == 0) ? 0 : ST_PH[p - 1].end;
        printf(" F%d [%d,%d) bus{", p + 1, st, ST_PH[p].end);
        for (int i = 0; i < ST_PH[p].n_tones; ++i) {
            printf("%d%s", ST_PH[p].tones[i],
                   i + 1 < ST_PH[p].n_tones ? "," : "");
        }
        printf("}");
    }
    printf("\n");

    SensoryLobe lobe;
    int32_t p1_taus[2] = {4, 12};
    SlPostCfg pool[SF_POOL];
    for (int i = 0; i < SF_POOL; ++i) {
        pool[i].p1_src = i % 2;
        pool[i].sensor_ch = SF_BUS_CH;
        pool[i].tau_b = SF_SPREAD[i];
        pool[i].w0 = fixed_from_double(0.2);
    }
    sl_init(lobe, p1_taus, 2, pool, SF_POOL, SL_AMP, SL_P1_AMPS,
            fixed_from_double(0.0));

    FILE* csv = fopen("sensory_stress.csv", "w");
    if (!csv) {
        fprintf(stderr, "HATA: stress CSV acilamadi\n");
        return 1;
    }
    fprintf(csv, "tick,phase,bus,n_posts,acc35\n");
    FILE* hcsv = fopen("sensory_stress_hires.csv", "w");
    if (!hcsv) {
        fprintf(stderr, "HATA: stress hire CSV acilamadi\n");
        return 1;
    }
    fprintf(hcsv, "tick,tau,slot\n");
    // Faz-duyarli kapilar icin faz-sonu + yerlesme-sonrasi kabul kopyalari.
    // (Yerlesme: ise-alimdaki ayni 300 tick kurali; sonda basindaki tasinan
    // kilit ilk nabizlari reddeder — sinir-gecis fizigi, kapisiz birakilmaz,
    // yerlesme-sonrasi tam esitlik istenir.)
    long acc_snap[ST_NPH][P2_MAX] = {};
    long acc_set[ST_NPH][P2_MAX] = {};

    int32_t prev_b[P2_MAX];
    int32_t hist[P2_MAX][SF_HIST];
    int hist_n[P2_MAX] = {0};
    long acc_total[P2_MAX] = {0};
    int32_t last_acc[P2_MAX];
    for (int k = 0; k < P2_MAX; ++k) {
        prev_b[k] = -2;
        last_acc[k] = -1;
    }
    int32_t unclaimed[12];
    int unclaimed_n = 0;
    int32_t last_hire = -10000;
    int hire_tau[8];
    int hire_tick[8];
    long hire_acc0[8] = {0};
    int n_hire = 0;
    int idx35 = -1;
    for (int i = 0; i < SF_POOL; ++i) {
        if (SF_SPREAD[i] == 35) idx35 = i;
    }

    for (int32_t t = 0; t < ST_T_END; ++t) {
        int phase = ST_NPH;
        for (int p = 0; p < ST_NPH; ++p) {
            if (t < ST_PH[p].end) {
                phase = p + 1;
                break;
            }
        }
        if (phase > 1 && t == ST_PH[phase - 2].end) {
            for (int k = 0; k < P2_MAX; ++k) {
                acc_snap[phase - 2][k] = acc_total[k];
            }
        }
        {
            int pst = (phase == 1) ? 0 : ST_PH[phase - 2].end;
            if (t == pst + 300) {
                for (int k = 0; k < P2_MAX; ++k) {
                    acc_set[phase - 1][k] = acc_total[k];
                }
            }
        }
        bool bus = false;
        const st_phase& ph = ST_PH[phase - 1];
        for (int i = 0; i < ph.n_tones; ++i) {
            if ((t % ph.tones[i]) == 0) bus = true;
        }
        bool p1p[2] = {(t % 4) == 0, (t % 12) == 0};
        bool sp[P2_MAX] = {false};
        for (int k = 0; k < lobe.num_p2; ++k) sp[k] = bus;
        fixed_t dw[P2_MAX] = {0};
        sensory_tick(lobe, t, p1p, sp, dw);

        int claimed = 0;
        for (int k = 0; k < lobe.num_p2; ++k) {
            int32_t bi = lobe.p2[k].branch_B_last_input_tick;
            if (bi != prev_b[k]) {
                prev_b[k] = bi;
                if (bi == t) {
                    bool res = (last_acc[k] >= 0) &&
                               ((t - last_acc[k]) == lobe.tau_b[k]);
                    last_acc[k] = t;
                    if (res) claimed++;
                    acc_total[k]++;
                    if (hist_n[k] < SF_HIST) {
                        hist[k][hist_n[k]++] = t;
                    } else {
                        for (int i = 1; i < SF_HIST; ++i) {
                            hist[k][i - 1] = hist[k][i];
                        }
                        hist[k][SF_HIST - 1] = t;
                    }
                }
            }
        }
        if (bus && claimed == 0) {
            if (unclaimed_n < 12) {
                unclaimed[unclaimed_n++] = t;
            } else {
                for (int i = 1; i < 12; ++i) unclaimed[i - 1] = unclaimed[i];
                unclaimed[11] = t;
            }
            int32_t phase_start =
                (phase == 1) ? 0 : ST_PH[phase - 2].end;
            if (unclaimed_n >= 7 && n_hire < 8 &&
                (t - last_hire) > 400 && (t - phase_start) > 300) {
                int32_t d[6];
                for (int i = 0; i < 6; ++i) {
                    d[i] = unclaimed[unclaimed_n - 7 + i + 1] -
                           unclaimed[unclaimed_n - 7 + i];
                }
                for (int i = 0; i < 6; ++i) {
                    for (int j = i + 1; j < 6; ++j) {
                        if (d[j] < d[i]) {
                            int32_t tmp = d[i];
                            d[i] = d[j];
                            d[j] = tmp;
                        }
                    }
                }
                int32_t cands[3] = {(d[2] + d[3]) / 2, -1, -1};
                if (cands[0] % 2 == 0) cands[1] = cands[0] / 2;
                if (cands[0] % 3 == 0) cands[2] = cands[0] / 3;
                for (int ci = 0; ci < 3; ++ci) {
                    int32_t c = cands[ci];
                    if (c < 4 || c > 60) continue;
                    int explained = 0;
                    int direct = 0;
                    for (int i = 0; i < 6; ++i) {
                        int32_t q = (d[i] + c / 2) / c;
                        if (q >= 1) {
                            int32_t df = d[i] - q * c;
                            if (df < 0) df = -df;
                            if (df <= 3) explained++;
                        }
                        int32_t dd = d[i] - c;
                        if (dd < 0) dd = -dd;
                        if (dd <= 3) direct++;
                    }
                    bool dup = false;
                    for (int k = 0; k < lobe.num_p2; ++k) {
                        if (lobe.tau_b[k] == c) {
                            dup = true;
                            break;
                        }
                    }
                    // Dogrudan-kanit sarti (§9.16): ortanca-hayaleti reddi.
                    if (explained >= 5 && direct >= 2 && !dup) {
                        SlPostCfg nc;
                        nc.p1_src = lobe.num_p2 % 2;
                        nc.sensor_ch = SF_BUS_CH;
                        nc.tau_b = c;
                        nc.w0 = fixed_from_double(0.0);
                        if (sl_add_post(lobe, nc, SL_P1_AMPS[nc.p1_src])) {
                            prev_b[lobe.num_p2 - 1] = -2;
                            last_acc[lobe.num_p2 - 1] = -1;
                            hire_acc0[n_hire] = acc_total[lobe.num_p2 - 1];
                            hire_tau[n_hire] = (int)c;
                            hire_tick[n_hire] = (int)t;
                            n_hire++;
                            last_hire = t;
                            unclaimed_n = 0;
                            printf("RECRUIT t=%d tau=%d slot=%d "
                                   "(medyan %d)\n",
                                   (int)t, (int)c, lobe.num_p2 - 1,
                                   (int)cands[0]);
                        }
                        break;
                    }
                }
            }
        }
        if (t % 25 == 0) {
            int a35 = (idx35 >= 0 && hist_n[idx35] > 0) ? hist_n[idx35] : 0;
            fprintf(csv, "%d,%d,%d,%d,%d\n", (int)t, phase, bus ? 1 : 0,
                    lobe.num_p2, a35);
        }
    }
    fclose(csv);

    printf("\n--- olculen etiketler (kabul ISI medyani) ---\n");
    for (int k = 0; k < lobe.num_p2; ++k) {
        int m = sf_median_label(hist[k], hist_n[k]);
        char plbl[16];
        sl_render_label(k, true, plbl, sizeof(plbl));
        bool tight = false;
        if (m > 0 && hist_n[k] >= 4) {
            int in_tol = 0, nd = 0;
            for (int i = 1; i < hist_n[k]; ++i) {
                int32_t df = (hist[k][i] - hist[k][i - 1]) - m;
                if (df < 0) df = -df;
                if (df <= 3) in_tol++;
                nd++;
            }
            tight = (nd > 0) && (in_tol * 2 >= nd);
        }
        if (m > 0 && tight) {
            printf("  %s (tau%+d): p2@tau%d (kabul %d)\n", plbl,
                   (int)lobe.tau_b[k], m, hist_n[k]);
        } else if (m > 0) {
            printf("  %s (tau%+d): gezgin-medyan%d (kabul %d)\n", plbl,
                   (int)lobe.tau_b[k], m, hist_n[k]);
        } else {
            printf("  %s (tau%+d): sessiz (kabul %d)\n", plbl,
                   (int)lobe.tau_b[k], hist_n[k]);
        }
    }

    for (int h = 0; h < n_hire; ++h) {
        fprintf(hcsv, "%d,%d,%d\n", hire_tick[h], hire_tau[h], SF_POOL + h);
    }
    fclose(hcsv);
    for (int k = 0; k < P2_MAX; ++k) {
        acc_snap[ST_NPH - 1][k] = acc_total[k];  // son faz kapanisi
    }

    // Kapilar (T-serisi). Yogun-faz kilit orani KAPILANMAZ: B-PLIR kilidi
    // rezonans durumudur (2*tau+bw); yogun yolda kilit dusunce yanlis-ton
    // nabiz slotu yanlis ritme yakalar, oz nabizlar reddedilir (olculdu:
    // 0.53-0.91, yogunlukla duser). Kilit ispatini SEYREK sonda fazlari
    // (F7-F10, S1 fizigi) verir; karar ispatini sira+pencere (T2) verir.
    int p35_f1 = 0;
    for (int t = 0; t < ST_PH[0].end; t += 35) p35_f1++;
    long a35_f1 = (idx35 >= 0) ? acc_snap[0][idx35] : -1;
    bool t1 = (a35_f1 == p35_f1);
    printf("%s (T1): F1 taban tam kilit %ld/%d\n", t1 ? "OK" : "UYARI",
           a35_f1, p35_f1);
    const int exp_tau[4] = {26, 59, 43, 50};
    bool t2 = (n_hire == 4);
    for (int h = 0; h < 4 && t2; ++h) {
        int fidx = h + 1;  // F2..F5
        int fstart = ST_PH[fidx - 1].end;
        int fend = ST_PH[fidx].end;
        if (h >= n_hire || hire_tau[h] != exp_tau[h] ||
            hire_tick[h] < fstart + 300 || hire_tick[h] >= fend) {
            t2 = false;
        }
    }
    printf("%s (T2): ise-alim [26,59,43,50] kendi fazinda "
           "(yerlesme300+), olusan [", t2 ? "OK" : "UYARI");
    for (int i = 0; i < n_hire; ++i) {
        printf("%d@%d%s", hire_tau[i], hire_tick[i],
               i + 1 < n_hire ? "," : "");
    }
    printf("]\n");
    // Gozlem (kapisiz): yogun-faz kilit orani, yanlis-ritim yakalanma.
    for (int h = 0; h < n_hire && h < 4; ++h) {
        int m = hire_tau[h], ht = hire_tick[h];
        int fidx = h + 1;
        int comp = 0;
        for (int t = ht; t < ST_PH[fidx].end; ++t) {
            if ((t % m) == 0) comp++;
        }
        int slot = SF_POOL + h;
        long got = acc_snap[fidx][slot] - hire_acc0[h];
        double ratio = comp > 0 ? (double)got / (double)comp : 0.0;
        printf("  gozlem hire%d tau%d yogun-faz kilit: %ld/%d (%.3f)\n",
               h, m, got, comp, ratio);
    }
    // T3: seyrek sonda fazlarinda YERLESME-SONRASI tam kilit (S1 sinifi).
    // Sonda index: 26->6, 59->7, 43->8, 50->9 (ST_PH); slot=12+h.
    const int probe_idx[4] = {6, 7, 8, 9};
    bool t3 = true;
    for (int h = 0; h < 4; ++h) {
        int pi = probe_idx[h];
        int m = exp_tau[h];
        int pstart = ST_PH[pi - 1].end + 300;  // yerlesme-sonrasi
        int pend = ST_PH[pi].end;
        int comp = 0;
        for (int t = pstart; t < pend; ++t) {
            if ((t % m) == 0) comp++;
        }
        int slot = SF_POOL + h;
        long got = 0;
        if (h < n_hire && hire_tau[h] == m) {
            got = acc_snap[pi][slot] - acc_set[pi][slot];
        } else {
            got = -1;
        }
        printf("  sonda%d tau%d: %ld/%d %s\n", h, m, got, comp,
               got == comp ? "OK" : "UYARI");
        if (got != comp) t3 = false;
    }
    printf("%s (T3): 4 sonda-faz yerlesme-sonrasi tam kilit\n",
           t3 ? "OK" : "UYARI");
    int p35_f6 = 0;
    for (int t = ST_PH[4].end; t < ST_PH[5].end; ++t) {
        if ((t % 35) == 0) p35_f6++;
    }
    long a35_f6 =
        (idx35 >= 0) ? acc_snap[5][idx35] - acc_snap[4][idx35] : -1;
    int hires_rest = 0;
    for (int h = 0; h < n_hire; ++h) {
        if (hire_tick[h] >= ST_PH[4].end) hires_rest++;
    }
    bool t4 = (a35_f6 == p35_f6) && (hires_rest == 0);
    printf("%s (T4): F6 tabana donus %ld/%d + F6-F10 hire=0 (olusan %d)\n",
           t4 ? "OK" : "UYARI", a35_f6, p35_f6, hires_rest);
    printf("\n=== OZET-STRESS: T1=%s T2=%s T3=%s T4=%s ===\n",
           t1 ? "OK" : "UYARI", t2 ? "OK" : "UYARI", t3 ? "OK" : "UYARI",
           t4 ? "OK" : "UYARI");
    printf("n_hire=%d n_posts=%d\n", n_hire, lobe.num_p2);
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    if (!parse_cli(argc, argv)) return 1;
    if (g_selforg) return run_selforg();
    if (g_stress) return run_stress();
    if (g_stream) return run_stream();
    return run_batch();
}
