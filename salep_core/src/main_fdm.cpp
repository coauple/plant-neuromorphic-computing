// ---------------------------------------------------------------------------
// FDM Ana Kosu — simultane demux: PLIR + populasyon + faz kilidi
//
// Kalibrasyon: validate_fdm.py (19 deney; MC tick C++ neuron_tick birebir
//   ikizi — tek-noron probu ayni ates dizisini verir; tablo ~0.01 ortusur).
//   FDM_BW=1, LOCK=2*tau+bw, PULSE=0.8, N_POP=8, jitter +-150/1000.
// Kriterler (MC D17/D13/D14 sayilarindan):
//   (A) kilit: S1'de conc+cov>=0.40; S2'de conc bilgi, kapi cov>=0.40;
//   (A2) mutlak faz: C++ merkezi MC tahmininden +-0.5 icinde
//     (R1: 1.50/2.18; R3: 1.16/0.65);
//   (B) S1 conc>=0.40 bilgi olarak A'nin icinde (ayri blokta rapor);
//   (C) {4,9} D9-kaydirma hatasi<=1 tick;
//   (D) (i) S2 merkezi S1'den +-0.5 icinde, (ii) uye yayilimi<=1.5 tick;
//   (E) regresyon (ayri kapida, 7 CSV bayt-bayt).
// Mutlak-izgara hit KAPI DEGIL (tani ciktisi): ates L~1-2 tick gecikmeli,
// izgara+-1 isabeti gecikme-karisik. Kilit=conc+cov, faz=A2+C.
// Kosular: R1 S1{4,12}, R2 S2{4,12}, R3 S1{4,9}, R4 S2{4,9},
//   R5-R8 {4,9} D9={0,2,4,6} faz-sifreleme, R9 R1'in eski-ISI karsitligi.
// Ortak tel: wire(t)=Σ A_b*pulse_b(t)+gurultu; ayni tick darbeleri toplanir.
// Gurultu S2: %2 ekstra darbe (genlik 0.7*PULSE) + +-%20 genlik jitter;
// tumu tamsayi LCG (cekirdekte float/double YOK).
// CSV: fdm_simultaneous.csv (R1-R4 tick), fdm_events.csv (ates olaylari),
//   fdm_dshift.csv (D9 taramasi). Olcum (double) yalniz bu dosyada.
// CLI (dashboard §9.9, yalniz harness): --noise PCT --pulse V --locklost N
//   --d4 D --d12 D (R1/R2/R9 {4,12} kosularini etkiler). Argumansiz =
//   kalibre davranis birebir (regresyon; param satiri bile basilmaz).
// ---------------------------------------------------------------------------

#include <cmath>
#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include "fdm.h"

namespace {

constexpr int T_HARM = 2400;   // {4,12} kosu uzunlugu (MC D17)
constexpr int T_COPRIME = 3600;  // {4,9} kosu uzunlugu (MC D17)

// Runtime parametreleri (dashboard §9.9). Varsayilanlar kalibre sabitlere
// esit -> argumansiz kosu onceki CSV'lerle bayt-bayt aynidir.
fixed_t g_pulse = FDM_PULSE;
int g_noise_pct = FDM_NOISE_PCT;
int32_t g_locklost = 0;  // 0 = kalibre 2*tau+bw (fdm_band_params)
int32_t g_d4 = 0;
int32_t g_d12 = 0;
bool g_custom = false;  // herhangi bir CLI bayragi verildiyse true

uint32_t g_stim = 0;

fixed_t stim_jittered(fixed_t base) {
    int32_t j = (int32_t)(fdm_lcg_next(g_stim) % 401u) - 200;  // [-200,200]
    fixed_t mult = fixed_div(fixed_from_int(1000 + j), fixed_from_int(1000));
    return fixed_mul(base, mult);
}

// Superpoze tel akimi. delays[]: bant faz kaymalari (D_b).
fixed_t super_wire(int32_t t, const int32_t taus[], const int32_t delays[],
                   int nbands, bool noisy) {
    fixed_t w = 0;
    for (int b = 0; b < nbands; ++b) {
        if (t >= delays[b] && (t - delays[b]) % taus[b] == 0) {
            w += noisy ? stim_jittered(g_pulse) : g_pulse;
        }
    }
    if (noisy && (fdm_lcg_next(g_stim) % 100u) < (uint32_t)g_noise_pct) {
        w += stim_jittered(fixed_mul(g_pulse, fixed_from_double(0.7)));
    }
    return w;
}

// CLI: --noise PCT --pulse V --locklost N --d4 D --d12 D [--help].
// --key=val ve --key val bicimleri desteklenir. Hatali deger -> 1.
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
                printf("kullanim: salep_fdm [--noise 0-100] [--pulse V] "
                       "[--locklost N] [--d4 0-3] [--d12 0-11]\n"
                       "  --noise PCT : S2 ekstra darbe yuzdesi (varsayilan "
                       "2)\n"
                       "  --pulse V   : darbe genligi, (0,2] (varsayilan "
                       "0.8)\n"
                       "  --locklost N: PLIR kilit esigi tick; 0 = kalibre "
                       "2*tau+bw\n"
                       "  --d4 D      : 4'luk bant faz kaymasi 0-3\n"
                       "  --d12 D     : 12'lik bant faz kaymasi 0-11\n"
                       "  (R1/R2/R9 {4,12} kosularini etkiler; R3-R8 sabit)\n"
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
        if (strcmp(key, "--noise") == 0) {
            long v = strtol(val, &end, 10);
            if (*end != '\0' || v < 0 || v > 100) {
                fprintf(stderr, "HATA: --noise 0-100 olmali\n");
                return false;
            }
            g_noise_pct = (int)v;
            g_custom = true;
        } else if (strcmp(key, "--pulse") == 0) {
            double v = strtod(val, &end);
            if (*end != '\0' || !(v > 0.0) || v > 2.0) {
                fprintf(stderr, "HATA: --pulse (0,2] olmali\n");
                return false;
            }
            g_pulse = fixed_from_double(v);
            g_custom = true;
        } else if (strcmp(key, "--locklost") == 0) {
            long v = strtol(val, &end, 10);
            if (*end != '\0' || v < 0 || v > 1000) {
                fprintf(stderr, "HATA: --locklost 0-1000 olmali\n");
                return false;
            }
            g_locklost = (int32_t)v;
            g_custom = true;
        } else if (strcmp(key, "--d4") == 0) {
            long v = strtol(val, &end, 10);
            if (*end != '\0' || v < 0 || v > 3) {
                fprintf(stderr, "HATA: --d4 0-3 olmali\n");
                return false;
            }
            g_d4 = (int32_t)v;
            g_custom = true;
        } else if (strcmp(key, "--d12") == 0) {
            long v = strtol(val, &end, 10);
            if (*end != '\0' || v < 0 || v > 11) {
                fprintf(stderr, "HATA: --d12 0-11 olmali\n");
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

struct BandStats {
    long n;
    long hist[FDM_TAU_MAX];
    double sum_cos;
    double sum_sin;
    double member_cos[FDM_MAX_POP];
    double member_sin[FDM_MAX_POP];
    long member_n[FDM_MAX_POP];
};

void stats_init(BandStats& s) {
    s.n = 0;
    for (int i = 0; i < FDM_TAU_MAX; ++i) s.hist[i] = 0;
    s.sum_cos = 0.0;
    s.sum_sin = 0.0;
    for (int m = 0; m < FDM_MAX_POP; ++m) {
        s.member_cos[m] = 0.0;
        s.member_sin[m] = 0.0;
        s.member_n[m] = 0;
    }
}

void stats_add(BandStats& s, int32_t t, int member, int32_t tau) {
    int bin = (int)(t % tau);
    s.hist[bin]++;
    s.n++;
    double ang = 2.0 * 3.141592653589793 * (double)bin / (double)tau;
    s.sum_cos += cos(ang);
    s.sum_sin += sin(ang);
    s.member_cos[member] += cos(ang);
    s.member_sin[member] += sin(ang);
    s.member_n[member]++;
}

double stats_conc(const BandStats& s, int32_t tau) {
    if (s.n == 0) return 0.0;
    long mx = 0;
    for (int i = 0; i < tau; ++i) {
        if (s.hist[i] > mx) mx = s.hist[i];
    }
    return (double)mx / (double)s.n;
}

double stats_center(const BandStats& s, int32_t tau) {
    if (s.n == 0) return 0.0;
    double a = atan2(s.sum_sin, s.sum_cos);
    double c = a / (2.0 * 3.141592653589793) * (double)tau;
    while (c < 0) c += tau;
    while (c >= tau) c -= tau;
    return c;
}

// Izgara isabet orani: |wrap(t-D,tau)|<=1 ateslerin orani.
double stats_hit(const BandStats& s, int32_t tau, int32_t delay,
                 const long* hist) {
    (void)s;
    long tot = 0, ok = 0;
    for (int i = 0; i < tau; ++i) {
        tot += hist[i];
        int d = (i - delay) % tau;
        if (d < 0) d += tau;
        if (d > tau / 2) d = tau - d;
        if (d <= 1) ok += hist[i];
    }
    return tot > 0 ? (double)ok / (double)tot : 0.0;
}

}  // namespace

// Uye-bazinda faz toplamlari BandStats icinde (member_cos/sin/n).
namespace {

struct RunResult {
    BandStats st[FDM_MAX_BANDS];
    long fast_fires;
    long slow_fires;
    double cov[FDM_MAX_BANDS];
    double spread[FDM_MAX_BANDS];
};

// Kapsama: kendi darbelerinin kacinda +-tol icinde (havuz) ates var.
double run_coverage(const int32_t* firet, long n, int32_t tau, int32_t delay,
                    int32_t T, int tol) {
    long pulses = 0, ok = 0;
    for (int32_t p = delay; p < T; p += tau) {
        pulses++;
        for (long k = 0; k < n; ++k) {
            int32_t d = firet[k] - p;
            if (d < 0) d = -d;
            if (d <= tol) {
                ok++;
                break;
            }
        }
    }
    return pulses > 0 ? (double)ok / (double)pulses : 0.0;
}

// Uye yayilimi: uye-merkezlerinin dairesel standart sapmasi (tick).
double member_spread(const BandStats& s, int pop, int32_t tau) {
    double sc = 0.0, ss = 0.0;
    int nm = 0;
    for (int m = 0; m < pop; ++m) {
        if (s.member_n[m] > 0) {
            double a = atan2(s.member_sin[m], s.member_cos[m]);
            sc += cos(a);
            ss += sin(a);
            nm++;
        }
    }
    if (nm < 2) return 0.0;
    double rb = sqrt(sc * sc + ss * ss) / nm;
    if (rb < 1e-9) rb = 1e-9;
    return sqrt(-2.0 * log(rb)) / (2.0 * 3.141592653589793) * (double)tau;
}

// Tek kosu: teli sur, tick CSV + olay CSV yaz, istatistik dondur.
RunResult do_run(const char* run_tag, const int32_t taus[],
                 const int32_t delays[], int nbands, int T, bool noisy,
                 int32_t plir_mode, uint32_t seed, FILE* tick_csv,
                 FILE* events_csv, int run_id) {
    RunResult rr;
    for (int b = 0; b < FDM_MAX_BANDS; ++b) {
        stats_init(rr.st[b]);
        rr.cov[b] = 0.0;
        rr.spread[b] = 0.0;
    }
    rr.fast_fires = 0;
    rr.slow_fires = 0;

    int pops[FDM_MAX_BANDS] = {FDM_N_POP, FDM_N_POP, FDM_N_POP};
    FdmNetwork net;
    fdm_init(net, taus, pops, nbands, plir_mode, seed);
    // CLI kilit-esigi override (--locklost): yalniz harness alani yazilir,
    // fdm.h/cekirdek degismez. 0 = kalibre deger (override yok).
    if (g_locklost > 0) {
        for (int b = 0; b < net.num_bands; ++b) {
            for (int m = 0; m < net.pop[b]; ++m) {
                net.band[b][m].plir_lock_lost = g_locklost;
            }
        }
    }
    g_stim = seed ^ 0x9e3779b9u;

    // Ates-tick kaydi (kapsama olcumu; main-tarafi, cekirdek degil).
    static int32_t firet[FDM_MAX_BANDS][8192];
    long firen[FDM_MAX_BANDS] = {0, 0, 0};

    for (int32_t t = 0; t < T; ++t) {
        fixed_t w = super_wire(t, taus, delays, nbands, noisy);
        FdmTickFires f = fdm_tick(net, t, w);
        long fb = 0, sb = 0;
        for (int b = 0; b < nbands; ++b) {
            for (int m = 0; m < net.pop[b]; ++m) {
                if (f.fired[b][m]) {
                    int bin = (int)(t % taus[b]);
                    stats_add(rr.st[b], t, m, taus[b]);
                    if (firen[b] < 8192) firet[b][firen[b]++] = t;
                    if (events_csv) {
                        fprintf(events_csv, "%d,%d,%d,%d,%d\n", t, run_id,
                                (int)taus[b], m, bin);
                    }
                    if (b == 0) fb++;
                    else sb++;
                }
            }
        }
        rr.fast_fires += fb;
        rr.slow_fires += sb;
        if (tick_csv) {
            fprintf(tick_csv, "%d,%s,%.6f,%ld,%ld\n", t, run_tag,
                    fixed_to_float(w), fb, sb);
        }
    }
    for (int b = 0; b < nbands; ++b) {
        rr.cov[b] = run_coverage(firet[b], firen[b], taus[b], delays[b], T, 2);
        rr.spread[b] = member_spread(rr.st[b], net.pop[b], taus[b]);
    }
    return rr;
}

double wrap_err_tick(double a, double b, int32_t tau) {
    double d = fmod(a - b, (double)tau);
    if (d < 0) d += tau;
    if (d > tau / 2.0) d -= tau;
    return d;
}

}  // namespace

int main(int argc, char** argv) {
    if (!parse_cli(argc, argv)) return 1;
    printf("=== FDM: simultane demux (PLIR + populasyon + faz kilidi) ===\n");
    printf("bw=1 lock=2tau+1 pulse=0.8 N_POP=8 (validate_fdm.py)\n");
    // Parametre satiri yalniz ozel kosuda basilir -> argumansiz stdout
    // ve CSV'ler onceki kosularla birebir aynidir (regresyon).
    if (g_custom) {
        printf("param: noise=%d%% pulse=%.3f locklost=%d d4=%d d12=%d\n",
               g_noise_pct, fixed_to_float(g_pulse), (int)g_locklost,
               (int)g_d4, (int)g_d12);
    }

    FILE* tick_csv = fopen("fdm_simultaneous.csv", "w");
    FILE* events_csv = fopen("fdm_events.csv", "w");
    FILE* dshift_csv = fopen("fdm_dshift.csv", "w");
    if (!tick_csv || !events_csv || !dshift_csv) {
        fprintf(stderr, "HATA: FDM CSV acilamadi\n");
        return 1;
    }
    fprintf(tick_csv, "tick,run,wire,fast_fires,slow_fires\n");
    fprintf(events_csv, "tick,run,band_tau,member,bin\n");
    fprintf(dshift_csv, "D,center,conc,hit,nfires,member_spread\n");

    // --- Ana kosular ---
    // R1/R2/R9 {4,12} gecikmeleri CLI'dan (--d4/--d12); R3-R8 sabit kalir.
    const int32_t harm[2] = {4, 12};
    const int32_t cop[2] = {4, 9};
    const int32_t d0[2] = {0, 0};
    const int32_t dharm[2] = {g_d4, g_d12};

    RunResult r1 = do_run("R1", harm, dharm, 2, T_HARM, false, 1, 1001,
                          tick_csv, events_csv, 1);
    RunResult r2 = do_run("R2", harm, dharm, 2, T_HARM, true, 1, 1002,
                          tick_csv, events_csv, 2);
    RunResult r3 =
        do_run("R3", cop, d0, 2, T_COPRIME, false, 1, 1003, tick_csv,
               events_csv, 3);
    RunResult r4 =
        do_run("R4", cop, d0, 2, T_COPRIME, true, 1, 1004, tick_csv,
               events_csv, 4);
    // --- R9: eski-ISI karsitligi (plir_mode=0; R1 ayarlarini aynalar) ---
    RunResult r9 = do_run("R9", harm, dharm, 2, T_HARM, false, 0, 1001,
                          nullptr, nullptr, 9);

    // --- (A) Kilit: S1'de conc+cov>=0.40; S2'de conc tohum-duyarli
    // (MC D6: %2 gurultude conc4 0.36-0.41) -> yalniz rapor, kapi cov>=0.40.
    printf("\n=== (A) KILIT (conc + coverage) ===\n");
    struct ACfg {
        const char* tag;
        RunResult* r;
        int32_t tau_f, tau_s;
        bool s1;
    };
    ACfg acfgs[4] = {{"R1 S1{4,12}", &r1, 4, 12, true},
                     {"R2 S2{4,12}", &r2, 4, 12, false},
                     {"R3 S1{4,9}", &r3, 4, 9, true},
                     {"R4 S2{4,9}", &r4, 4, 9, false}};
    bool a_ok = true;
    for (int i = 0; i < 4; ++i) {
        double cf = stats_conc(acfgs[i].r->st[0], acfgs[i].tau_f);
        double cs = stats_conc(acfgs[i].r->st[1], acfgs[i].tau_s);
        double vf = acfgs[i].r->cov[0];
        double vs = acfgs[i].r->cov[1];
        bool ok = (vf >= 0.40) && (vs >= 0.40);
        if (acfgs[i].s1) ok = ok && (cf >= 0.40) && (cs >= 0.40);
        if (!ok) a_ok = false;
        printf("%s: conc=(%.2f,%.2f)%s cov=(%.2f,%.2f) ates=(%ld,%ld) %s\n",
               acfgs[i].tag, cf, cs, acfgs[i].s1 ? "" : " (bilgi)", vf, vs,
               acfgs[i].r->fast_fires, acfgs[i].r->slow_fires,
               ok ? "OK" : "UYARI");
    }
    printf("R9 karsitlik (eski-ISI): yavas ates R1=%ld R9=%ld\n",
           r1.slow_fires, r9.slow_fires);

    // --- (A2) Mutlak faz tahmini: MC merkezleri (D17) ---
    printf("\n=== (A2) MUTLAK FAZ (MC tahmini +-0.5) ===\n");
    bool a2_ok = true;
    struct A2Cfg {
        const char* tag;
        RunResult* r;
        int32_t tau_f, tau_s;
        double pred_f, pred_s;
    };
    A2Cfg a2[2] = {{"R1{4,12}", &r1, 4, 12, 1.50, 2.18},
                   {"R3{4,9}", &r3, 4, 9, 1.16, 0.65}};
    for (int i = 0; i < 2; ++i) {
        double cf = stats_center(a2[i].r->st[0], a2[i].tau_f);
        double cs = stats_center(a2[i].r->st[1], a2[i].tau_s);
        double ef = fabs(wrap_err_tick(cf, a2[i].pred_f, a2[i].tau_f));
        double es = fabs(wrap_err_tick(cs, a2[i].pred_s, a2[i].tau_s));
        bool ok = (ef <= 0.5) && (es <= 0.5);
        if (!ok) a2_ok = false;
        printf("%s: merkez=(%.2f,%.2f) tahmin=(%.2f,%.2f) sapma=(%.2f,%.2f) "
               "%s\n",
               a2[i].tag, cf, cs, a2[i].pred_f, a2[i].pred_s, ef, es,
               ok ? "OK" : "UYARI");
    }

    // --- (B) Tani ciktilari: mutlak-izgara hit + S2 conc ---
    printf("\n=== (B) TANI (hit: gecikme-karisik, kapisiz) ===\n");
    for (int i = 0; i < 4; ++i) {
        double hf = stats_hit(acfgs[i].r->st[0], acfgs[i].tau_f, 0,
                              acfgs[i].r->st[0].hist);
        double hs = stats_hit(acfgs[i].r->st[1], acfgs[i].tau_s, 0,
                              acfgs[i].r->st[1].hist);
        printf("%s: hit_fast=%.2f hit_slow=%.2f\n", acfgs[i].tag, hf, hs);
    }

    // --- (C) Faz sifreleme: {4,9} D9 kaydirma ---
    printf("\n=== (C) FAZ SIFRELEME (D9 -> merkez kaymasi) ===\n");
    bool c_ok = true;
    double base = 0.0;
    const int32_t dvals[4] = {0, 2, 4, 6};
    for (int i = 0; i < 4; ++i) {
        int32_t dd[2] = {0, dvals[i]};
        RunResult rd = do_run("RD", cop, dd, 2, T_COPRIME, false, 1,
                              (uint32_t)(2000 + i), nullptr, nullptr, 10 + i);
        double c = stats_center(rd.st[1], 9);
        double hf = stats_hit(rd.st[1], 9, dvals[i], rd.st[1].hist);
        if (i == 0) base = c;
        double err = fabs(wrap_err_tick(c - base, (double)dvals[i], 9));
        bool ok = (err <= 1.0);
        if (!ok) c_ok = false;
        double mspread = member_spread(rd.st[1], FDM_N_POP, 9);
        fprintf(dshift_csv, "%d,%.3f,%.3f,%.3f,%ld,%.3f\n", dvals[i], c,
                stats_conc(rd.st[1], 9), hf, rd.st[1].n, mspread);
        printf("D9=%d: merkez=%.2f kayma_hatasi=%.2f yayilim=%.2f %s\n",
               dvals[i], c, err, mspread, ok ? "OK" : "UYARI");
    }

    // --- (D) Populasyon: (i) S2 merkezi S1'den +-0.5 icinde,
    // (ii) uye yayilimi<=1.5 tick ---
    printf("\n=== (D) POPULASYON (S2 kararlilik + uye birligi) ===\n");
    bool d_ok = true;
    struct DCfg {
        const char* tag;
        RunResult* s1;
        RunResult* s2;
        int32_t tf, ts;
    };
    DCfg dcfgs[2] = {{"S1/S2{4,12}", &r1, &r2, 4, 12},
                     {"S1/S2{4,9}", &r3, &r4, 4, 9}};
    for (int i = 0; i < 2; ++i) {
        for (int b = 0; b < 2; ++b) {
            int32_t tau = (b == 0) ? dcfgs[i].tf : dcfgs[i].ts;
            double c1 = stats_center(dcfgs[i].s1->st[b], tau);
            double c2 = stats_center(dcfgs[i].s2->st[b], tau);
            double shift = fabs(wrap_err_tick(c2 - c1, 0.0, tau));
            double sp1 = dcfgs[i].s1->spread[b];
            double sp2 = dcfgs[i].s2->spread[b];
            bool ok = (shift <= 0.5) && (sp1 <= 1.5) && (sp2 <= 1.5);
            if (!ok) d_ok = false;
            printf("%s bant%d(tau=%d): S1->S2 kayma=%.2f yayilim=(%.2f,%.2f) "
                   "%s\n",
                   dcfgs[i].tag, b, (int)tau, shift, sp1, sp2,
                   ok ? "OK" : "UYARI");
        }
    }

    fclose(tick_csv);
    fclose(events_csv);
    fclose(dshift_csv);
    printf("\nCSV: fdm_simultaneous.csv fdm_events.csv fdm_dshift.csv\n");
    printf("\n=== OZET: A=%s A2=%s C=%s D=%s ===\n", a_ok ? "OK" : "UYARI",
           a2_ok ? "OK" : "UYARI", c_ok ? "OK" : "UYARI",
           d_ok ? "OK" : "UYARI");
    return 0;
}
