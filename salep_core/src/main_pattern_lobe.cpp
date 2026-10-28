// ---------------------------------------------------------------------------
// PATTERN LOB binary — REV4 GERCEK K4.
//
// Zincir: afferent.csv -> V4cUnit[29] (v3e F1 + 58 gercek K4 node) ->
// mem/log.csv (+k4_branch.csv +k4_matrix.csv) + OZET-PATTERN-LOB (+ W).
//
// --k4 0 (varsayilan): K4 kapali -> mem/log/W stdout v3e ile bayt-bayt ayni
//   (J kapisi; mem semasi kapaliyken 11 kolon, v3e ile ayni).
//   --k4csv/--k4paircsv/--k4idcsv verilse bile kapali kosuda YAZILMAZ.
// --k4 1: K4 acik -> mem +2 kolon (soma_k4,k4spk) + ek telemetri:
//   k4_branch.csv (tick,birim,dal,act,rtop,toppartner,drive,spk;
//     act=K4 kapili voltaji, rtop=max r (matris), topartner=MEKANIK argmax,
//     drive=dal S4 salimi; satir sarti act>0 veya spike)
//   k4_matrix.csv (58x58 final iliski matrisi) + k4idcsv (a-bit + q imza)
//   + OZET'e k4 ozeti (spike, s4max, k4-kaynakli ates).
// --eta: v3e ile ayni (0 frozen | 0.30 ogrenen); kural/sayac degismedi.
// Ogrenme/post-sayac/mem/log, fired_final (F1 + K4-kaynakli) uzerinden.
// --tracecsv F [--traceevery N]: salt-okunur iz telemetrisi (MEKANIZMA
//   DEGIL; duruma etkisi YOK): bagli+baglantisiz tum 522 sinapsin (w,T)
//   dokumu; kosu sonunda her zaman, N>0 ise her N tick'te bir (learn
//   sonrasi durum). Verilmezse HICBIR cikti/davranis degismez (J korunur).
//
// Kullanim: npu_pattern_lobe --aff F --mem F --log F [--eta X]
//   [--k4 0|1] [--k4csv F] [--k4paircsv F] [--k4idcsv F]
//   [--tracecsv F] [--traceevery N]
// ---------------------------------------------------------------------------

#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include "pattern_lobe.h"
#include "pattern_state.h"  // persistence katmani (§9.113; cekirdek disi)

namespace {

struct AffEv {
    int32_t tick;
    int post;
    int tau;
};

bool parse_aff_line(const char* line, AffEv& e) {
    return sscanf(line, "%d,%d,%d", &e.tick, &e.post, &e.tau) == 3;
}

struct V3MemRecord {
    int32_t tick;
    int32_t unit;
    fixed_t soma;
    fixed_t eff_g;
    int32_t coinc;
    fixed_t kv[6];
    fixed_t soma_k4;  // karar anindaki S4 (F1 atesinde 0; kapali kosuda 0)
    int32_t k4spk;    // K4 spike bitleri (A=1,B=2; kapali kosuda 0)
};

}  // namespace

int main(int argc, char** argv) {
    const char* aff_path = nullptr;
    const char* mem_path = nullptr;
    const char* log_path = nullptr;
    const char* k4_path = nullptr;
    const char* k4pair_path = nullptr;
    const char* k4id_path = nullptr;  // telemetri: dal kimlik aktif-bitleri
    const char* trace_path = nullptr;  // telemetri: (w,T) dokumu
    int trace_every = 0;
    double eta_d = 0.0;
    int k4_on = 0;
    int stream_on = 0;
    const char* load_path = nullptr;   // baslangic state (yoksa temiz)
    const char* save_path = nullptr;   // batch sonu kayit
    const char* autosave_path = nullptr;  // stream QUIT kaydi
    for (int i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "--aff") == 0 && i + 1 < argc) {
            aff_path = argv[++i];
        } else if (strcmp(argv[i], "--mem") == 0 && i + 1 < argc) {
            mem_path = argv[++i];
        } else if (strcmp(argv[i], "--log") == 0 && i + 1 < argc) {
            log_path = argv[++i];
        } else if (strcmp(argv[i], "--k4csv") == 0 && i + 1 < argc) {
            k4_path = argv[++i];
        } else if (strcmp(argv[i], "--k4paircsv") == 0 && i + 1 < argc) {
            k4pair_path = argv[++i];
        } else if (strcmp(argv[i], "--k4idcsv") == 0 && i + 1 < argc) {
            k4id_path = argv[++i];
        } else if (strcmp(argv[i], "--tracecsv") == 0 && i + 1 < argc) {
            trace_path = argv[++i];
        } else if (strcmp(argv[i], "--traceevery") == 0 && i + 1 < argc) {
            trace_every = atoi(argv[++i]);
        } else if (strcmp(argv[i], "--eta") == 0 && i + 1 < argc) {
            eta_d = atof(argv[++i]);
        } else if (strcmp(argv[i], "--k4") == 0 && i + 1 < argc) {
            k4_on = atoi(argv[++i]) != 0 ? 1 : 0;
        } else if (strcmp(argv[i], "--stream") == 0) {
            stream_on = 1;
        } else if (strcmp(argv[i], "--load") == 0 && i + 1 < argc) {
            load_path = argv[++i];
        } else if (strcmp(argv[i], "--save") == 0 && i + 1 < argc) {
            save_path = argv[++i];
        } else if (strcmp(argv[i], "--autosave") == 0 && i + 1 < argc) {
            autosave_path = argv[++i];
        }
    }
    if (!mem_path || !log_path || (!stream_on && !aff_path)) {
        fprintf(stderr,
                "kullanim: npu_pattern_lobe --aff F --mem F --log F "
                "[--eta X] [--k4 0|1] [--k4csv F] [--k4paircsv F] "
                "[--tracecsv F] [--traceevery N]\n"
                "   veya: npu_pattern_lobe --stream --mem F --log F "
                "[--eta X] [--k4 0|1] [--k4csv F] [--k4paircsv F] "
                "[--k4idcsv F] [--tracecsv F] [--traceevery N]\n"
                "   stream komutlari: AFF tick,post,tau | TICK n | "
                "OZET | STATE | SAVE yol | QUIT\n"
                "   durum: --load F (baslangic) --save F (batch sonu) "
                "--autosave F (stream kapanis)\n");
        return 2;
    }
    fixed_t eta = fixed_from_double(eta_d);
    // Batch: afferent dosyasi bir kez okunur. Stream: olaylar stdin'den
    // gelir, dosya okunmaz (instance oturum boyunca yasar).
    std::vector<AffEv> evs;
    int32_t max_tick = 0;
    if (!stream_on) {
        FILE* f = fopen(aff_path, "r");
        if (!f) {
            fprintf(stderr, "HATA: afferent dosyasi acilmadi\n");
            return 1;
        }
        char line[1024];
        if (!fgets(line, sizeof(line), f)) {
            fprintf(stderr, "HATA: bos afferent\n");
            return 1;
        }
        while (fgets(line, sizeof(line), f)) {
            AffEv e;
            if (!parse_aff_line(line, e)) continue;
            evs.push_back(e);
            if (e.tick > max_tick) max_tick = e.tick;
        }
        fclose(f);
    }

    synapse_build_luts();
    V4cUnit u[P3X3_N];
    for (int i = 0; i < P3X3_N; ++i) v4c_init(u[i], i);
    V4cK4Net net;
    v4c_net_init(net);
    // Baslangic state: dosya gecerliyse yukle, degilse temiz basla
    // (sessiz yanlis yukleme YOK; zaman episodic — tcur yine 0'dan).
    if (load_path) {
        plstate::StateMeta meta;
        int lr = plstate::state_load(load_path, u, net, k4_on, &meta);
        if (lr == plstate::LOAD_OK) {
            plstate::Sums s = plstate::state_sums(u, net, k4_on);
            printf("OK LOAD %s tick=%u wsum=%lld tsum=%lld rsum=%lld\n",
                   load_path, meta.last_tick, (long long)s.wsum,
                   (long long)s.tsum, (long long)s.rsum);
            fflush(stdout);
        } else {
            fprintf(stderr, "WARN LOAD %s: %s; temiz baslangic\n",
                    load_path, plstate::load_error_str(lr));
        }
    }

    FILE* logf = fopen(log_path, "w");
    if (!logf) {
        fprintf(stderr, "HATA: log acilmadi\n");
        return 1;
    }
    fprintf(logf, "tick,phi_id,phi_tau,fires_hex\n");

    // K4 telemetrisi akisli yazilir (tampon tavani YOK; kesilme olmaz).
    FILE* k4f = nullptr;
    if (k4_on && k4_path) {
        k4f = fopen(k4_path, "w");
        if (!k4f) {
            fprintf(stderr, "HATA: k4csv acilmadi\n");
            return 1;
        }
        fprintf(k4f, "tick,birim,dal,act,rtop,toppartner,drive,spk\n");
    }
    // Kimlik telemetrisi: salt-okunur snapshot yazimi (duruma etkisi YOK).
    FILE* idf = nullptr;
    if (k4_on && k4id_path) {
        idf = fopen(k4id_path, "w");
        if (!idf) {
            fprintf(stderr, "HATA: k4idcsv acilmadi\n");
            return 1;
        }
        fprintf(idf, "tick,bid,birim,dal,a0,a1,a2,q0,q1,q2\n");
    }
    // Iz telemetrisi: salt-okunur (w,T) dokumu (duruma etkisi YOK).
    FILE* tracef = nullptr;
    if (trace_path) {
        tracef = fopen(trace_path, "w");
        if (!tracef) {
            fprintf(stderr, "HATA: tracecsv acilmadi\n");
            return 1;
        }
        fprintf(tracef, "tick,unit,k,w,T\n");
    }

    static V3MemRecord mem[V4C_MEM_CAP];
    int mem_count = 0;
    long unit_fires[P3X3_N] = {};
    long n_events = 0;
    // K4 ozet sayaçlari (k4 kapali iken hepsi 0 kalir).
    long k4_nz_units = 0;   // act>0 dal-satir sayisi
    long k4_nz_ticks = 0;   // en az bir act>0 iceren tick sayisi
    long k4_spikes = 0;     // toplam K4 spike olayi
    long k4_kfires = 0;     // K4-kaynakli soma atesi
    fixed_t k4_max_act = 0;
    fixed_t k4_s4_max = 0;
    // --- Tick cekirdegi (batch + stream ORTAK; mekanizma tek kaynak) ----
    // Batch davranisi birebir korunur (J kapisi); cagiran olay besler.
    auto pl_validate = [&](const AffEv& e) -> bool {
        return pl_phi_id_of(e.post) >= 0 && pl_phi_tau_of(e.tau) >= 0;
    };
    auto pl_tick = [&](int32_t t, const std::vector<AffEv>& at) {
        int32_t phi_id = -1, phi_tau = -1;
        uint32_t firemask = 0;
        bool injected[P3X3_N][P3X3_NSYN] = {};
        for (size_t ai = 0; ai < at.size(); ++ai) {
            int32_t pi = pl_phi_id_of(at[ai].post);
            int32_t pt = pl_phi_tau_of(at[ai].tau);
            if (phi_id < 0) {
                phi_id = pi;
                phi_tau = pt;
            }
            int s = at[ai].post;
            for (int i = 0; i < P3X3_N; ++i) {
                p3x3unit_drive(u[i].base, s, t, injected[i]);
            }
            n_events++;
        }
        V4cIdentity ids[V4C_NB];
        V4cSig sigs[V4C_NB];
        int32_t evts[V4C_NB];
        if (k4_on) {
            // 58 kimlik snapshot'i (pre-reset, drive-sonrasi) + dal-olay
            // saati + nicemlenmis imza. Koke drive YOK (REV4: seri degil).
            for (int i = 0; i < P3X3_N; ++i) {
                for (int d = 0; d < V4C_NDAL; ++d) {
                    int b = i * V4C_NDAL + d;
                    v4c_snapshot_branch(u[i].base, d, ids[b]);
                    v4c_quantize(ids[b], sigs[b]);
                    if (v4c_branch_event(injected[i], d)) {
                        u[i].k4_last_evt[d] = t;
                    }
                    evts[b] = u[i].k4_last_evt[d];
                    if (idf) {
                        fprintf(idf, "%d,%d,%d,%d,%d,%d,%d,%d,%d,%d\n", t, b,
                                i, d,
                                (ids[b].v[0] > GATING_ACTIVATE_THRESH) ? 1
                                                                       : 0,
                                (ids[b].v[1] > GATING_ACTIVATE_THRESH) ? 1
                                                                       : 0,
                                (ids[b].v[2] > GATING_ACTIVATE_THRESH) ? 1
                                                                       : 0,
                                (int)sigs[b].q[0], (int)sigs[b].q[1],
                                (int)sigs[b].q[2]);
                    }
                }
            }
        }
        bool fired[P3X3_N] = {};
        for (int i = 0; i < P3X3_N; ++i) {
            fired[i] = p3x3_tick(u[i].base.n, t);  // S123 (frozen)
        }
        if (k4_on) {
            v4c_net_update(net, sigs, evts, t);
            // Partner spike gorunurlugu: yalniz GECMIS tick spike'lari
            // surumu kapilar (nedensellik; bu tick spike'i dahil DEGIL).
            bool pspk[V4C_NB];
            for (int b = 0; b < V4C_NB; ++b) {
                int32_t st = u[b / V4C_NDAL].k4_spike_tick[b % V4C_NDAL];
                pspk[b] = (st >= 0) && ((t - st) <= COINCIDENCE_WINDOW_MS);
            }
            // Max-secimli surum (deger + MEKANIK argmax).
            for (int b = 0; b < V4C_NB; ++b) {
                int top = -1;
                fixed_t rel = v4c_branch_rel(net, sigs, pspk, b, top);
                u[b / V4C_NDAL].k4_rel[b % V4C_NDAL] = rel;
                u[b / V4C_NDAL].k4_top[b % V4C_NDAL] = top;
            }
            // K4 tick: lokal sarj + iliskisel sarj.
            for (int i = 0; i < P3X3_N; ++i) {
                for (int d = 0; d < V4C_NDAL; ++d) {
                    bool ev = (u[i].k4_last_evt[d] == t);
                    fixed_t loc = ev ? V4C_K4_LOC : 0;
                    bool sp = v4c_k4_tick(u[i].k4[d], loc, u[i].k4_rel[d],
                                          t, u[i].k4_spike_tick[d]);
                    u[i].k4_spiked[d] = sp;
                    if (sp) k4_spikes++;
                    if (u[i].k4[d].local_voltage > k4_max_act)
                        k4_max_act = u[i].k4[d].local_voltage;
                }
            }
            // Soma ikinci asama: S123 + S4 (F1 ateslediyse eslesik reset).
            bool tick_nz = false;
            for (int i = 0; i < P3X3_N; ++i) {
                if (fired[i]) {
                    v4c_k4_coupled_reset(u[i].k4);
                    u[i].k4_s4 = 0;
                    u[i].k4_s4d[0] = u[i].k4_s4d[1] = 0;
                    continue;
                }
                fixed_t s123 = u[i].base.n.soma_voltage;
                u[i].k4_s4d[0] = v4c_k4_release(u[i].k4[0]);
                u[i].k4_s4d[1] = v4c_k4_release(u[i].k4[1]);
                fixed_t s4 =
                    v4c_soma_s4(u[i].k4_s4d[0], u[i].k4_s4d[1]);
                u[i].k4_s4 = s4;
                if (s4 > k4_s4_max) k4_s4_max = s4;
                if (v4c_soma_fire(u[i].base, u[i].k4, s123, s4, t)) {
                    fired[i] = true;  // K4-kaynakli ates
                    k4_kfires++;
                }
                for (int d = 0; d < V4C_NDAL; ++d) {
                    int b = i * V4C_NDAL + d;
                    fixed_t act = v4c_k4_release(u[i].k4[d]);
                    if (act > k4_max_act) k4_max_act = act;
                    if (act > 0 || u[i].k4_spiked[d]) {
                        if (act > 0) tick_nz = true;
                        k4_nz_units++;
                        // rtop: matris-seviyesi max r (suregelen iliski).
                        fixed_t rtop = 0;
                        for (int c = 0; c < V4C_NB; ++c) {
                            if (c == b) continue;
                            if (net.r[b][c] > rtop) rtop = net.r[b][c];
                        }
                        if (k4f) {
                            fprintf(k4f, "%d,%d,%d,%.6f,%.6f,%d,%.6f,%d\n",
                                    t, i, d, (double)fixed_to_float(act),
                                    (double)fixed_to_float(rtop),
                                    u[i].k4_top[d],
                                    (double)fixed_to_float(u[i].k4_s4d[d]),
                                    u[i].k4_spiked[d] ? 1 : 0);
                        }
                    }
                }
            }
            if (tick_nz) k4_nz_ticks++;
        }
        for (int i = 0; i < P3X3_N; ++i) {
            p3x3unit_learn(u[i].base, injected[i], fired[i], eta);
            if (fired[i]) {
                firemask |= (i < 32) ? (1u << i) : 0u;
                unit_fires[i]++;
                if (mem_count < V4C_MEM_CAP) {
                    V3MemRecord& m = mem[mem_count++];
                    m.tick = t;
                    m.unit = i;
                    m.soma = u[i].base.n.soma_voltage;
                    m.eff_g = u[i].base.n.c[P3X3_ROOT].gating_state;
                    bool ba = (u[i].base.n.dalA_last_input_tick >= 0) &&
                              ((t - u[i].base.n.dalA_last_input_tick) <=
                               COINCIDENCE_WINDOW_MS);
                    bool bb = (u[i].base.n.dalB_last_input_tick >= 0) &&
                              ((t - u[i].base.n.dalB_last_input_tick) <=
                               COINCIDENCE_WINDOW_MS);
                    m.coinc = (ba && bb) ? 1 : 0;
                    for (int k = 0; k < 6; ++k)
                        m.kv[k] = u[i].base.n.c[P3X3_A_K1 + k].local_voltage;
                    m.soma_k4 = k4_on ? u[i].k4_s4 : 0;
                    m.k4spk = 0;
                    if (k4_on) {
                        if (u[i].k4_spiked[0]) m.k4spk |= 1;
                        if (u[i].k4_spiked[1]) m.k4spk |= 2;
                    }
                }
            }
        }
        if (tracef && trace_every > 0 && (t % trace_every) == 0) {
            for (int i = 0; i < P3X3_N; ++i)
                for (int k = 0; k < P3X3_NSYN; ++k) {
                    const Synapse* sn = p3x3_syn(u[i].base, k);
                    fprintf(tracef, "%d,%d,%d,%.6f,%.6f\n", t, i, k,
                            (double)fixed_to_float(sn->weight),
                            (double)fixed_to_float(sn->trace));
                }
        }
        fprintf(logf, "%d,%d,%d,%08x\n", t, phi_id, phi_tau, firemask);
    };  // pl_tick (TEK instance, TEK mekanizma; batch + stream ortak)

    // OZET yazimi (batch epilogu + stream OZET komutu ORTAK).
    auto pl_ozet = [&]() {
        double wkdev = 0.0;
        for (int i = 0; i < P3X3_N; ++i) {
            for (int k = 0; k < P3X3_NSYN; ++k) {
                double d = (double)fixed_to_float(p3x3_syn(u[i].base, k)->weight)
                           - 1.0;
                if (d < 0) d = -d;
                if (d > wkdev) wkdev = d;
            }
        }
        printf("OZET-PATTERN-LOB: k4=%d olay=%ld mem=%d ates=[", k4_on, n_events,
               mem_count);
        for (int i = 0; i < P3X3_N; ++i)
            printf("%s%ld", i ? "," : "", unit_fires[i]);
        printf("] wkdev=%.4f eta=%.2f", wkdev, eta_d);
        if (k4_on) {
            printf(" k4_nztick=%ld k4_nzcell=%ld k4_spikes=%ld k4_kfires=%ld "
                   "k4_maxact=%.6f k4_s4max=%.6f",
                   k4_nz_ticks, k4_nz_units, k4_spikes, k4_kfires,
                   (double)fixed_to_float(k4_max_act),
                   (double)fixed_to_float(k4_s4_max));
        }
        printf("\n");
        static const char* kname[P3X3_NSYN] = {"k1c", "k1m", "k1p",
                                               "k2a0", "k2a1",
                                               "k3aA0", "k3aA1",
                                               "k3aF0", "k3aF1",
                                               "k1bc", "k1bm", "k1bp",
                                               "k2b0", "k2b1",
                                               "k3bA0", "k3bA1",
                                               "k3bF0", "k3bF1"};
        for (int i = 0; i < P3X3_N; ++i)
            for (int k = 0; k < P3X3_NSYN; ++k)
                printf("W %d %s %.6f\n", i, kname[k],
                       (double)fixed_to_float(p3x3_syn(u[i].base, k)->weight));
        fflush(stdout);
    };

    // Kapanis: iz dokumu + dosyalar + matris + mem + OZET (batch + QUIT ORTAK).
    auto pl_finalize = [&](int32_t last_tick) -> int {
        if (tracef) {
            for (int i = 0; i < P3X3_N; ++i)
                for (int k = 0; k < P3X3_NSYN; ++k) {
                    const Synapse* sn = p3x3_syn(u[i].base, k);
                    fprintf(tracef, "%d,%d,%d,%.6f,%.6f\n", last_tick + 1, i, k,
                            (double)fixed_to_float(sn->weight),
                            (double)fixed_to_float(sn->trace));
                }
            fclose(tracef);
        }
        fclose(logf);
        if (k4f) fclose(k4f);
        if (idf) fclose(idf);

        if (k4_on && k4pair_path) {
            FILE* pf = fopen(k4pair_path, "w");
            if (!pf) {
                fprintf(stderr, "HATA: k4paircsv acilmadi\n");
                return 1;
            }
            fprintf(pf, "b1,b2,r\n");
            for (int a = 0; a < V4C_NB; ++a) {
                for (int b = 0; b < V4C_NB; ++b) {
                    if (net.r[a][b] != 0) {
                        fprintf(pf, "%d,%d,%.6f\n", a, b,
                                (double)fixed_to_float(net.r[a][b]));
                    }
                }
            }
            fclose(pf);
        }

        FILE* mf = fopen(mem_path, "w");
        if (!mf) {
            fprintf(stderr, "HATA: mem acilmadi\n");
            return 1;
        }
        // J kapisi: kapaliyken sema v3e ile ayni 11 kolon; acikken +2 kolon.
        if (k4_on)
            fprintf(mf, "tick,unit,soma,eff_g,coinc,aK1,aK2,aK3,bK1,bK2,"
                        "bK3,soma_k4,k4spk\n");
        else
            fprintf(mf, "tick,unit,soma,eff_g,coinc,aK1,aK2,aK3,bK1,bK2,bK3\n");
        for (int i = 0; i < mem_count; ++i) {
            const V3MemRecord& m = mem[i];
            fprintf(mf, "%d,%d,%.6f,%.6f,%d,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f",
                    m.tick, m.unit, (double)fixed_to_float(m.soma),
                    (double)fixed_to_float(m.eff_g), m.coinc,
                    (double)fixed_to_float(m.kv[0]),
                    (double)fixed_to_float(m.kv[1]),
                    (double)fixed_to_float(m.kv[2]),
                    (double)fixed_to_float(m.kv[3]),
                    (double)fixed_to_float(m.kv[4]),
                    (double)fixed_to_float(m.kv[5]));
            if (k4_on)
                fprintf(mf, ",%.6f,%d",
                        (double)fixed_to_float(m.soma_k4), m.k4spk);
            fprintf(mf, "\n");
        }
        fclose(mf);

        pl_ozet();
        return 0;
    };

    // --- Stream surucu: TEK init yukarida yapildi; instance yasar. ----
    // Pencere siniri yalniz cagiranin tamponudur (w/T/r sifirlanmaz).
    if (stream_on) {
        auto is_cmd = [](const char* l, const char* w) -> bool {
            size_t n = strlen(w);
            if (strncmp(l, w, n) != 0) return false;
            char c = l[n];
            return c == '\n' || c == '\r' || c == '\0';
        };
        printf("PATTERN-LOB stream (k4=%d)\nREADY stream\n", k4_on ? 1 : 0);
        fflush(stdout);
        int32_t tcur = 0;
        std::vector<AffEv> pend;
        std::vector<char> used;
        char sline[1024];
        bool done = false;
        while (!done && fgets(sline, sizeof(sline), stdin)) {
            if (strncmp(sline, "AFF ", 4) == 0) {
                AffEv e;
                if (sscanf(sline + 4, "%d,%d,%d", &e.tick, &e.post,
                           &e.tau) != 3) {
                    printf("ERR AFF kullanim: AFF tick,post,tau\n");
                    fflush(stdout);
                    continue;
                }
                if (!pl_validate(e)) {
                    printf("ERR aralik disi: post=%d tau=%d\n",
                           e.post, e.tau);
                    fflush(stdout);
                    continue;
                }
                if (e.tick < tcur) {
                    printf("ERR monoton: tick=%d < tcur=%d\n",
                           (int)e.tick, (int)tcur);
                    fflush(stdout);
                    continue;
                }
                pend.push_back(e);
                used.push_back(0);
            } else if (strncmp(sline, "TICK ", 5) == 0) {
                int n = -1;
                if (sscanf(sline + 5, "%d", &n) != 1 || n < tcur) {
                    printf("ERR TICK kullanim: TICK n (n>=%d)\n", (int)tcur);
                    fflush(stdout);
                    continue;
                }
                for (int32_t t = tcur; t <= (int32_t)n; ++t) {
                    std::vector<AffEv> at;
                    for (size_t k = 0; k < pend.size(); ++k) {
                        if (!used[k] && pend[k].tick == t) {
                            at.push_back(pend[k]);
                            used[k] = 1;
                        }
                    }
                    pl_tick(t, at);
                }
                tcur = (int32_t)n + 1;
            } else if (is_cmd(sline, "OZET")) {
                pl_ozet();
            } else if (is_cmd(sline, "STATE")) {
                // Test-only telemetri: w/T/r ham toplamlari (duruma etkisi YOK).
                long long wsum = 0, tsum = 0, rsum = 0;
                for (int i = 0; i < P3X3_N; ++i) {
                    for (int k = 0; k < P3X3_NSYN; ++k) {
                        const Synapse* sn = p3x3_syn(u[i].base, k);
                        wsum += (long long)sn->weight;
                        tsum += (long long)sn->trace;
                    }
                }
                if (k4_on) {
                    for (int a = 0; a < V4C_NB; ++a)
                        for (int b = 0; b < V4C_NB; ++b)
                            rsum += (long long)net.r[a][b];
                }
                printf("STATE tick=%d wsum=%lld tsum=%lld rsum=%lld "
                       "events=%ld\n",
                       (int)tcur, wsum, tsum, rsum, n_events);
                fflush(stdout);
            } else if (strncmp(sline, "SAVE ", 5) == 0) {
                // Kontrollu checkpoint: ogrenme hesabina etkisi YOK.
                char spath[768];
                size_t sl = strlen(sline);
                while (sl > 0 && (sline[sl - 1] == '\n' ||
                                  sline[sl - 1] == '\r' ||
                                  sline[sl - 1] == ' '))
                    sl--;
                size_t cp = sl > 5 ? sl - 5 : 0;
                if (cp == 0 || cp >= sizeof(spath)) {
                    printf("ERR SAVE kullanim: SAVE <yol>\n");
                    fflush(stdout);
                    continue;
                }
                memcpy(spath, sline + 5, cp);
                spath[cp] = '\0';
                if (plstate::state_save(spath, u, net, (uint32_t)tcur)
                    == 0) {
                    printf("OK SAVE %s tick=%d\n", spath, (int)tcur);
                } else {
                    printf("ERR SAVE %s: yazma basarisiz\n", spath);
                }
                fflush(stdout);
            } else if (is_cmd(sline, "QUIT")) {
                done = true;
            } else {
                printf("ERR bilinmeyen "
                       "(AFF/TICK/OZET/STATE/SAVE/QUIT)\n");
                fflush(stdout);
            }
        }
        if (autosave_path) {
            if (plstate::state_save(autosave_path, u, net,
                                    (uint32_t)tcur) == 0) {
                printf("OK SAVE %s tick=%d\n", autosave_path, (int)tcur);
            } else {
                printf("ERR SAVE %s: yazma basarisiz\n", autosave_path);
            }
            fflush(stdout);
        }
        return pl_finalize(tcur);
    }

    // --- Batch surucu (J-donuk davranis; olay dogrulamali besleme) ----
    {
        size_t ei = 0;
        for (int32_t t = 0; t <= max_tick; ++t) {
            std::vector<AffEv> at;
            while (ei < evs.size() && evs[ei].tick == t) {
                if (!pl_validate(evs[ei])) {
                    fprintf(stderr,
                            "HATA: aralik disi (SPEC v0.1): post=%d tau=%d\n",
                            evs[ei].post, evs[ei].tau);
                    return 1;
                }
                at.push_back(evs[ei]);
                ++ei;
            }
            pl_tick(t, at);
        }
        int brc = pl_finalize(max_tick);
        if (brc == 0 && save_path) {
            if (plstate::state_save(save_path, u, net,
                                    (uint32_t)max_tick) == 0) {
                printf("OK SAVE %s tick=%d\n", save_path, (int)max_tick);
            } else {
                printf("ERR SAVE %s: yazma basarisiz\n", save_path);
            }
            fflush(stdout);
        }
        return brc;
    }
}
