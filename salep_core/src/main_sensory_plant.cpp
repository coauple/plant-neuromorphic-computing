// ---------------------------------------------------------------------------
// Duyusal Lob v2 — BITKI SÜRÜCÜLÜ harness (§9.57).
//
// Donuk Yarı-1 çekirdeği (sensory_lobe.h) salt-okunur kullanılır;
// main_sensory_lobe.cpp'ye DOKUNULMAZ. Fark: P1 faz hatları sabit iç
// tren yerine bitki elektrofizyoloji spike'larıyla (sim/electro.py
// çıktısı) sürülür; Dal B aynı faz kuralıyla sim sensörlerinden gelir.
// P2 koşul bankası, genlikler ve öğrenme disiplini varsayılan senaryoyla
// birebir aynıdır (§9.14 sayıları karşılaştırılabilir kalır).
//
// Girdi CSV'leri (başlık satırı atlanır):
//   spikes:  day,line,tick   (line 0/1, tick 0-49 — 1 gün = 50 tick)
//   sensors: day,hn,ec,hs,ts,tn,ph,npk  (0-100 ham kanal)
// Blok: 500 tick = 10 gün; koşullama N blok (sensör AÇIK) + test M blok
// (sensör KAPALI → CR). Toplam gün = (N+M)*10 olmalıdır.
//
// Çıktı: stdout'da `K t=.. p2a(p2c) kosul` (afferent kablo günlüğü) +
// OZET (koşul sayısı, post ateşleri, decoy/gerçek, CR); --out CSV'si
// varsayılan senaryoyla aynı sütun düzenindedir.
// ---------------------------------------------------------------------------

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include "sensory_lobe.h"

namespace plant_ns {

constexpr int DAY_TICKS = 50;
constexpr int BLOCK_LEN = 500;  // 10 gün
constexpr int NP1 = 2;
constexpr int NP2 = 10;
constexpr int NCH = 7;

constexpr fixed_t SL_AMP = fixed_from_double(1.0);
constexpr fixed_t SL_P1_AMPS[2] = {fixed_from_double(0.7),
                                   fixed_from_double(4.0)};
// Öntanım eta (§9.14): SL_ETA yerine CLI --eta (öntanım 0.30).

struct BankCfg {
    int p1_src;
    int sensor_ch;
    int32_t tau_b;
    fixed_t w0;
};

// §9.14 varsayılan banka (salt-okunur kopya — sayılar donuk dosyadandır).
BankCfg* bank_cfg() {
    static BankCfg cfg[NP2];
    static bool built = false;
    if (!built) {
        cfg[0] = {0, 0, 35, fixed_from_double(0.2)};  // p2a HN
        cfg[1] = {1, 2, 45, fixed_from_double(0.2)};  // p2b HS
        cfg[2] = {0, 0, 35, fixed_from_double(0.1)};  // p2c replika
        cfg[3] = {0, 0, 36, fixed_from_double(0.0)};  // p2d decoy
        cfg[4] = {1, 2, 46, fixed_from_double(0.0)};  // p2e decoy
        cfg[5] = {0, 1, 26, fixed_from_double(0.2)};  // p2f EC negatif
        cfg[6] = {0, 3, 37, fixed_from_double(0.2)};  // p2g TS
        cfg[7] = {1, 4, 37, fixed_from_double(0.2)};  // p2h TN
        cfg[8] = {0, 5, 37, fixed_from_double(0.2)};  // p2i PH
        cfg[9] = {1, 6, 37, fixed_from_double(0.2)};  // p2j NPK
        built = true;
    }
    return cfg;
}

int32_t sl_tau_of_value(int v) {
    return 4 + (v * 56) / 100;
}

// --- CSV okuma (başlık satırı kendiliğinden atlanır) -------------------------
bool split7(const char* line, int out[8]) {
    char* end = nullptr;
    for (int i = 0; i < 8; ++i) {
        if (i) {
            if (*end != ',') return false;
            ++end;
        } else {
            end = const_cast<char*>(line);
        }
        long v = strtol(end, &end, 10);
        if (end == line) return false;
        out[i] = (int)v;
    }
    return *end == '\0' || *end == '\n' || *end == '\r';
}

bool split3(const char* line, int out[3]) {
    char* end = nullptr;
    for (int i = 0; i < 3; ++i) {
        if (i) {
            if (*end != ',') return false;
            ++end;
        } else {
            end = const_cast<char*>(line);
        }
        long v = strtol(end, &end, 10);
        if (end == line) return false;
        out[i] = (int)v;
    }
    return *end == '\0' || *end == '\n' || *end == '\r';
}

int main(int argc, char** argv) {
    const char* spikes_path = nullptr;
    const char* sensors_path = nullptr;
    const char* out_path = nullptr;
    const char* diag_path = nullptr;
    // Afferent kablo + baglam: P2 ateslerinde A-gecmisi ve B-paterni
    // kaydedilir (persistence'a DOKUNULMAZ — yalniz gozlem).
    const char* aff_path = nullptr;
    int n_cond = 10, n_test = 3;
    // P1 hat kazanci (elektrot kazancı): öntanım §9.14 ile aynı;
    // seyrek bitki sürüşü daha yüksek kazanç ister (P1b 2→4 emsali).
    double amp0 = 0.7, amp1 = 4.0;
    // A-only sozlesme: B hatti tamamen kapali; --w0 ile tum postlar
    // ayni agirliktan baslar (kalibrasyon probu emsali).
    bool b_off = false;
    double w0_all = -1.0;
    // Öğrenme hızı: öntanım §9.14 (0.30); seyrek çakışma rejiminde
    // kalibrasyon probu (çekirdek donuk, harness katsayısı).
    double eta = 0.30;
    for (int i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "--spikes") == 0 && i + 1 < argc) {
            spikes_path = argv[++i];
        } else if (strcmp(argv[i], "--sensors") == 0 && i + 1 < argc) {
            sensors_path = argv[++i];
        } else if (strcmp(argv[i], "--out") == 0 && i + 1 < argc) {
            out_path = argv[++i];
        } else if (strcmp(argv[i], "--cond") == 0 && i + 1 < argc) {
            n_cond = atoi(argv[++i]);
        } else if (strcmp(argv[i], "--test") == 0 && i + 1 < argc) {
            n_test = atoi(argv[++i]);
        } else if (strcmp(argv[i], "--amp0") == 0 && i + 1 < argc) {
            amp0 = atof(argv[++i]);
        } else if (strcmp(argv[i], "--amp1") == 0 && i + 1 < argc) {
            amp1 = atof(argv[++i]);
        } else if (strcmp(argv[i], "--eta") == 0 && i + 1 < argc) {
            eta = atof(argv[++i]);
        } else if (strcmp(argv[i], "--b-off") == 0) {
            b_off = true;
        } else if (strcmp(argv[i], "--w0") == 0 && i + 1 < argc) {
            w0_all = atof(argv[++i]);
        } else if (strcmp(argv[i], "--diag") == 0 && i + 1 < argc) {
            diag_path = argv[++i];
        } else if (strcmp(argv[i], "--aff") == 0 && i + 1 < argc) {
            aff_path = argv[++i];
        } else {
            fprintf(stderr, "kullanim: %s --spikes F --sensors F --out F "
                            "[--cond N] [--test M] [--amp0 X] [--amp1 Y]\n",
                    argv[0]);
            return 2;
        }
    }
    if (!spikes_path || !sensors_path || !out_path) {
        fprintf(stderr, "kullanim: %s --spikes F --sensors F --out F "
                        "[--cond N] [--test M]\n",
                argv[0]);
        return 2;
    }
    const int need_days = (n_cond + n_test) * (BLOCK_LEN / DAY_TICKS);

    // Sensör tablosu: gün -> 7 kanal.
    std::vector<std::vector<int> > sens;
    int first_day = -1, last_day = -1;
    {
        FILE* f = fopen(sensors_path, "r");
        if (!f) {
            fprintf(stderr, "HATA: sensor dosyasi acilmadi\n");
            return 1;
        }
        char line[256];
        while (fgets(line, sizeof(line), f)) {
            if (line[0] == '#' || line[0] == '\n') continue;
            int r[8];
            if (!split7(line, r)) continue;  // baslik satiri duser
            int day = r[0];
            if (first_day < 0) first_day = day;
            last_day = day;
            std::vector<int> row;
            // CSV sirasi hn,ec,hs,ts,tn,ph,npk (plant disiplini).
            for (int k = 0; k < 7; ++k) row.push_back(r[1 + k]);
            sens.push_back(row);
        }
        fclose(f);
    }
    if (first_day < 0 || (int)sens.size() != need_days ||
        last_day - first_day + 1 != need_days) {
        fprintf(stderr, "HATA: sensor gunu %d olmali (bulunan %d)\n",
                need_days, (int)sens.size());
        return 1;
    }

    // Bitki spike tablosu: gun -> hat -> 50 tick maskesi.
    std::vector<unsigned long long> mask(
        (size_t)need_days * NP1, 0ULL);
    {
        FILE* f = fopen(spikes_path, "r");
        if (!f) {
            fprintf(stderr, "HATA: spike dosyasi acilmadi\n");
            return 1;
        }
        char line[256];
        long nsp = 0;
        while (fgets(line, sizeof(line), f)) {
            if (line[0] == '#' || line[0] == '\n') continue;
            int r[3];
            if (!split3(line, r)) continue;  // baslik satiri duser
            int di = r[0] - first_day;
            if (di < 0 || di >= need_days || r[1] < 0 || r[1] >= NP1 ||
                r[2] < 0 || r[2] >= DAY_TICKS) {
                fprintf(stderr, "HATA: spike araligi taştı\n");
                return 1;
            }
            mask[(size_t)di * NP1 + r[1]] |= (1ULL << r[2]);
            ++nsp;
        }
        fclose(f);
        printf("bitki spike: %ld darbe, %d gun\n", nsp, need_days);
    }

    synapse_build_luts();
    printf("=== DUYUSAL LOB v2 bitki-suruculu: P1 spike + B sensor fazi ===\n");
    printf("topoloji: P1 bitki h0/h1 (spike); P2 bankasi §9.14 ile ayni\n");
    fflush(stdout);

    SensoryLobe lobe;
    int32_t p1_taus[2] = {4, 12};
    fixed_t p1_amps[2] = {fixed_from_double(amp0),
                          fixed_from_double(amp1)};
    fixed_t eta_f = fixed_from_double(eta);
    printf("p1 kazanci: %.2f %.2f eta: %.2f\n", amp0, amp1, eta);
    BankCfg* bc = bank_cfg();
    SlPostCfg* bank = new SlPostCfg[NP2];
    for (int k = 0; k < NP2; ++k) {
        bank[k].p1_src = bc[k].p1_src;
        bank[k].sensor_ch = bc[k].sensor_ch;
        bank[k].tau_b = bc[k].tau_b;
        bank[k].w0 = (w0_all >= 0.0) ? fixed_from_double(w0_all)
                                     : bc[k].w0;
    }
    if (b_off) printf("B hatti KAPALI (A-only sozlesme)\n");
    sl_init(lobe, p1_taus, NP1, bank, NP2, SL_AMP, p1_amps, eta_f);

    FILE* csv = fopen(out_path, "w");
    if (!csv) {
        fprintf(stderr, "HATA: cikti acilmadi\n");
        return 1;
    }
    // Tani: her tick zincir ici-hali (donuk cekirdekten YALNIZ okuma).
    // Odak postlar: p2a (gercek/HN) + p2f (ogrenen/EC).
    FILE* dg = nullptr;
    if (diag_path) {
        dg = fopen(diag_path, "w");
        if (!dg) {
            fprintf(stderr, "HATA: tani dosyasi acilmadi\n");
            return 1;
        }
        fprintf(dg, "t,stage,pin0,pin1,p1f0,p1f1,p1V0,p1V1,bA,bF,"
                    "brBa,brBf,somaA,somaF,p2A,p2F,nfire\n");
    }
    const double f2d = 1.0 / 65536.0;
    // Afferent kablo: AfferentEvent{tick, post_id, tau_b} + baglam.
    // a0lag/a1lag = ilgili P1 hattinin son atesinden beri tick
    // (pencere disiysa -1); bmask = o tick B darbe paterni (10 bit);
    // label = ayni tick kosul etiketi; w = ilk atesleyen post agirligi.
    FILE* af = nullptr;
    int32_t p1_last[NP1];
    for (int i = 0; i < NP1; ++i) p1_last[i] = -1000000;
    // B-baglam penceresi: cakisma penceresiyle ayni (10 tick).
    int32_t b_last[NP2];
    for (int k = 0; k < NP2; ++k) b_last[k] = -1000000;
    if (aff_path) {
        af = fopen(aff_path, "w");
        if (!af) {
            fprintf(stderr, "HATA: afferent dosyasi acilmadi\n");
            return 1;
        }
        fprintf(af, "tick,post_id,tau_b,a0lag,a1lag,bmask,bwin,label,w\n");
    }

    long cond_fires[NP2] = {0};
    long test_fires[NP2] = {0};
    long p1_pulses[NP1] = {0, 0};
    std::vector<std::string> cond_labels;
    int block_id = 0;
    int32_t t = 0;
    for (int stage = 0; stage < 2; ++stage) {
        int nblocks = (stage == 0) ? n_cond : n_test;
        for (int blk = 0; blk < nblocks; ++blk, ++block_id) {
            for (int bt = 0; bt < BLOCK_LEN; ++bt, ++t) {
                int di = t / DAY_TICKS;  // 0-based gun indisi
                int tick = t % DAY_TICKS;
                bool p1p[NP1];
                for (int i = 0; i < NP1; ++i) {
                    p1p[i] = (mask[(size_t)di * NP1 + i] >>
                              tick) & 1ULL;
                    if (p1p[i]) p1_pulses[i]++;
                }
                bool sp[NP2] = {false};
                if (stage == 0 && !b_off) {
                    for (int k = 0; k < NP2; ++k) {
                        int v = sens[di][bank[k].sensor_ch];
                        if (v >= 50) {
                            sp[k] = (t % sl_tau_of_value(v)) == 0;
                        }
                    }
                }
                fixed_t dw[P2_MAX] = {0};
                SensoryTickResult r =
                    sensory_tick(lobe, t, p1p, sp, dw);
                bool any = false;
                for (int k = 0; k < NP2; ++k) {
                    if (r.p2_fired[k]) {
                        any = true;
                        if (stage == 0) cond_fires[k]++;
                        else test_fires[k]++;
                    }
                }
                for (int i = 0; i < NP1; ++i) {
                    if (r.p1_fired[i]) p1_last[i] = t;
                }
                for (int k = 0; k < NP2; ++k) {
                    if (sp[k]) b_last[k] = t;
                }
                if (any) {
                    char lbl[64];
                    bool fired[NP2];
                    for (int k = 0; k < NP2; ++k) fired[k] = r.p2_fired[k];
                    sl_condition_label(fired, NP2, lbl, sizeof(lbl));
                    printf("K t=%d %s kosul\n", (int)t, lbl);
                    if (af) {
                        char bm[NP2 + 1], bw[NP2 + 1];
                        for (int k = 0; k < NP2; ++k) {
                            bm[k] = sp[k] ? '1' : '0';
                            bw[k] = (t - b_last[k] <= 10) ? '1' : '0';
                        }
                        bm[NP2] = '\0';
                        bw[NP2] = '\0';
                        int lag0 = t - p1_last[0];
                        int lag1 = t - p1_last[1];
                        for (int k = 0; k < NP2; ++k) {
                            if (!r.p2_fired[k]) continue;
                            fprintf(af, "%d,%d,%d,%d,%d,%s,%s,\"%s\","
                                        "%.6f\n",
                                    (int)t, k,
                                    (int)bank[k].tau_b,
                                    lag0 <= 10 ? lag0 : -1,
                                    lag1 <= 10 ? lag1 : -1, bm, bw, lbl,
                                    (double)lobe.syn[k].weight / 65536.0);
                        }
                    }
                    bool seen = false;
                    for (size_t li = 0; li < cond_labels.size(); ++li) {
                        if (cond_labels[li] == lbl) {
                            seen = true;
                            break;
                        }
                    }
                    if (!seen) cond_labels.push_back(lbl);
                }
                if (dg) {
                    int ba = lobe.p2[0].branch_B_id;
                    int bf = lobe.p2[5].branch_B_id;
                    int nf = 0;
                    for (int k = 0; k < NP2; ++k) {
                        if (r.p2_fired[k]) ++nf;
                    }
                    fprintf(dg, "%d,%d,%d,%d,%d,%d,%.4f,%.4f,%d,%d,"
                                "%.4f,%.4f,%.4f,%.4f,%d,%d,%d\n",
                            t, stage, p1p[0] ? 1 : 0, p1p[1] ? 1 : 0,
                            r.p1_fired[0] ? 1 : 0,
                            r.p1_fired[1] ? 1 : 0,
                            lobe.p1[0].soma_voltage * f2d,
                            lobe.p1[1].soma_voltage * f2d,
                            sp[0] ? 1 : 0, sp[5] ? 1 : 0,
                            lobe.p2[0].compartments[ba].local_voltage *
                                f2d,
                            lobe.p2[5].compartments[bf].local_voltage *
                                f2d,
                            lobe.p2[0].soma_voltage * f2d,
                            lobe.p2[5].soma_voltage * f2d,
                            r.p2_fired[0] ? 1 : 0,
                            r.p2_fired[5] ? 1 : 0, nf);
                }
                fprintf(csv, "%d,%d,%d,%d,%d,", t, block_id, stage,
                        r.p1_fired[0] ? 1 : 0, r.p1_fired[1] ? 1 : 0);
                for (int k = 0; k < NP2; ++k) {
                    fprintf(csv, "%d", r.p2_fired[k] ? 1 : 0);
                }
                for (int k = 0; k < NP2; ++k) {
                    fprintf(csv, ",%.6f",
                            (double)lobe.syn[k].weight / 65536.0);
                }
                fprintf(csv, "\n");
            }
        }
    }
    fclose(csv);
    if (dg) fclose(dg);
    if (af) fclose(af);
    delete[] bank;

    // Afferent raporu: kosul sayisi + atesler + etkililik.
    long cond_tot = 0, test_tot = 0;
    for (int k = 0; k < NP2; ++k) {
        cond_tot += cond_fires[k];
        test_tot += test_fires[k];
    }
    long real_c = cond_fires[0] + cond_fires[1] + cond_fires[2];
    long decoy_c = cond_fires[3] + cond_fires[4];
    printf("OZET-PLANT: p1darbesi=%ld/%ld kosul_sayisi=%d "
           "cond_atis=%ld test_atis=%ld\n",
           p1_pulses[0], p1_pulses[1], (int)cond_labels.size(), cond_tot,
           test_tot);
    printf("OZET-PLANT: post_atis:");
    for (int k = 0; k < NP2; ++k) printf(" %ld", cond_fires[k]);
    printf("\nOZET-PLANT: test_atis:");
    for (int k = 0; k < NP2; ++k) printf(" %ld", test_fires[k]);
    printf("\nOZET-PLANT: decoy_gercek=%.3f CR_a=%.3f CR_b=%.3f\n",
           real_c > 0 ? (double)decoy_c / (double)real_c : -1.0,
           cond_fires[0] > 0 ? (double)test_fires[0] / cond_fires[0] : -1.0,
           cond_fires[1] > 0 ? (double)test_fires[1] / cond_fires[1] : -1.0);
    return 0;
}

}  // namespace plant_ns

int main(int argc, char** argv) {
    return plant_ns::main(argc, argv);
}
