// ===========================================================================
// main_synapse.cpp — Sinaps Öğrenme Kuralı + Gerçek Akım Aktarımı Testi
//
// CLAUDE.md §9: dw = eta * G(r_pre,r_post) * Q(r_pre,r_post) * S(w)
//
// Artık sinaps N0'dan N1'e gerçek akım aktarır: I_syn = weight × 0.5.
// Doğrulama 4 fazda:
//   L0 — açık döngü öğrenme (referans, transfer kapalı)
//   L1 — kapalı döngü öğrenme (transfer açık, pozitif geri besleme testi)
//   T1 — düşük weight ile aktarım (kontrol)
//   T2 — öğrenilmiş weight ile aktarım (test)
// ===========================================================================

#include "neuron.h"
#include "synapse.h"
#include <cstdio>
#include <cmath>

// ---------------------------------------------------------------------------
// N0 / N1 parametreleri — main_multi.cpp ile aynı
// ---------------------------------------------------------------------------

static constexpr NeuronParams N0_PARAMS = {
    0.02, 0.015, 0.015, 0.03, 0.035, 0.03
};
static constexpr NeuronParams N1_PARAMS = {
    0.20, 0.18, 0.15, 0.001, 0.001, 0.001
};

// ---------------------------------------------------------------------------
// Uyaran programı
// ---------------------------------------------------------------------------

constexpr int32_t CYCLE_LEN = 500;
constexpr int     N_CYCLES  = 20;
constexpr int     N_CYCLES_TX = 40;   // aktarım fazları için

static bool should_inject(int32_t cycle_t, fixed_t& current_out) {
    if (cycle_t >= 50 && cycle_t <= 80 && (cycle_t - 50) % 5 == 0) {
        current_out = fixed_from_double(0.5);
        return true;
    }
    if (cycle_t >= 150 && cycle_t <= 180 && (cycle_t - 150) % 3 == 0) {
        current_out = fixed_from_double(0.8);
        return true;
    }
    if (cycle_t >= 220 && cycle_t <= 250 && (cycle_t - 220) % 5 == 0) {
        current_out = fixed_from_double(0.5);
        return true;
    }
    current_out = 0;
    return false;
}

// ---------------------------------------------------------------------------
// Faz konfigürasyonu ve sonuç istatistikleri
// ---------------------------------------------------------------------------

struct PhaseConfig {
    bool        learn_on;          // L0,L1: true; T1,T2: false
    bool        drive_n1;          // L0,L1: true; T1,T2: false (yalnız sinaptik)
    bool        transmit;          // L0: false; L1,T1,T2: true
    bool        transfer_csv_col;  // L0: false; L1,T1,T2: true
    int         n_cycles;          // L0,L1: N_CYCLES; T1,T2: N_CYCLES_TX
    fixed_t     weight;            // başlangıç weight
    const char* csv_path;
    const char* label;
};

struct PhaseStats {
    int    n0_fires = 0, n1_fires = 0;
    int    first_n1_fire_cycle = -1;   // -1 = hiç ateşlemedi
    fixed_t weight_end;
    bool   monotonic_ok = false;
    bool   saturation_ok = false;
    double first_cycle_mean_abs_dw = 0.0;
    double last_cycle_mean_abs_dw  = 0.0;
    int    first_half_weight_cycle = -1;  // ilk w >= 0.5*W_MAX döngüsü (1-bazlı)
};

// ---------------------------------------------------------------------------
// run_phase — tek faz simülasyonu
// ---------------------------------------------------------------------------

PhaseStats run_phase(const PhaseConfig& cfg) {
    PhaseStats stats;

    DendriticNeuron n0, n1;
    neuron_init_with_params(n0, 0, N0_PARAMS);
    neuron_init_with_params(n1, 1, N1_PARAMS);

    SpikeRateCounter rc_pre, rc_post;
    rate_counter_init(rc_pre);
    rate_counter_init(rc_post);

    Synapse syn;
    synapse_init(syn, /*source=*/0, /*target_compartment=*/n1.branch_A_id,
                 cfg.weight);

    fixed_t eta = fixed_from_double(0.2);

    FILE* csv = std::fopen(cfg.csv_path, "w");
    if (!csv) {
        std::fprintf(stderr, "HATA: %s acilamadi\n", cfg.csv_path);
        return stats;
    }

    // CSV başlığı
    if (cfg.learn_on) {
        // L0, L1: 11 sütun + transfer varsa injected_current_to_n1
        if (cfg.transfer_csv_col) {
            std::fprintf(csv,
                "tick,cycle,r_pre,r_post,G,Q,S,dw,weight,n0_fired,n1_fired,injected_current_to_n1\n");
        } else {
            std::fprintf(csv,
                "tick,cycle,r_pre,r_post,G,Q,S,dw,weight,n0_fired,n1_fired\n");
        }
    } else {
        // T1, T2: 6 sütun
        std::fprintf(csv,
            "tick,cycle,weight,injected_current_to_n1,n0_fired,n1_fired\n");
    }

    const int32_t TOTAL_TICKS = CYCLE_LEN * cfg.n_cycles;

    fixed_t weight_at_cycle_end[std::max(N_CYCLES, N_CYCLES_TX)];
    double  mean_abs_dw_per_cycle[std::max(N_CYCLES, N_CYCLES_TX)];
    double  cycle_dw_sum = 0.0;
    int     cycle_dw_count = 0;

    for (int32_t t = 0; t < TOTAL_TICKS; ++t) {
        int32_t cycle_t = t % CYCLE_LEN;
        int     cycle_idx = t / CYCLE_LEN;

        // 1. Uyaran enjeksiyonu
        fixed_t injection = 0;
        bool injected = should_inject(cycle_t, injection);
        if (injected) {
            neuron_inject_current(n0, n0.branch_A_id, injection, t);
            neuron_inject_current(n0, n0.branch_B_id, injection, t);
            if (cfg.drive_n1) {
                neuron_inject_current(n1, n1.branch_A_id, injection, t);
                neuron_inject_current(n1, n1.branch_B_id, injection, t);
            }
        }

        // 2. N0 tick
        bool n0_fired = neuron_tick(n0, t);
        if (n0_fired) stats.n0_fires++;

        // 3. Sinaptik aktarım (N0→N1 gerçek akım)
        fixed_t syn_current = 0;
        if (cfg.transmit && n0_fired) {
            syn_current = synapse_transmission_current(syn);
            neuron_inject_current(n1, syn.target_compartment_id, syn_current, t);
        }

        // 4. N1 tick
        bool n1_fired = neuron_tick(n1, t);
        if (n1_fired) {
            stats.n1_fires++;
            if (stats.first_n1_fire_cycle < 0) {
                stats.first_n1_fire_cycle = cycle_idx;
            }
        }

        // 5. Öğrenme (L0/L1)
        if (cfg.learn_on) {
            rate_counter_update(rc_pre,  n0_fired);
            rate_counter_update(rc_post, n1_fired);

            int r_pre  = rc_pre.count;
            int r_post = rc_post.count;

            fixed_t g = synapse_G(r_pre, r_post);
            fixed_t q = synapse_Q(r_pre, r_post);
            fixed_t s = synapse_S(syn.weight);
            fixed_t dw = synapse_apply_learning(syn, r_pre, r_post, eta);

            cycle_dw_sum += std::fabs(fixed_to_float(dw));
            cycle_dw_count++;

            // 6. Döngü sonu — ağırlık kaydet
            if (cycle_t == CYCLE_LEN - 1) {
                weight_at_cycle_end[cycle_idx] = syn.weight;
                mean_abs_dw_per_cycle[cycle_idx] = cycle_dw_sum / cycle_dw_count;

                // İlk yarı-weight döngüsünü kaydet
                fixed_t half_w_max = fixed_from_double(1.0);  // W_MAX/2
                if (stats.first_half_weight_cycle < 0 && syn.weight >= half_w_max) {
                    stats.first_half_weight_cycle = cycle_idx;
                }

                cycle_dw_sum = 0.0;
                cycle_dw_count = 0;
            }

            // 7. CSV satırı (öğrenme)
            if (cfg.transfer_csv_col) {
                std::fprintf(csv, "%d,%d,%d,%d,%.6f,%.6f,%.6f,%.6f,%.6f,%d,%d,%.6f\n",
                    t, cycle_idx, r_pre, r_post,
                    fixed_to_float(g), fixed_to_float(q), fixed_to_float(s),
                    fixed_to_float(dw), fixed_to_float(syn.weight),
                    n0_fired ? 1 : 0, n1_fired ? 1 : 0,
                    cfg.transmit ? fixed_to_float(syn_current) : 0.0);
            } else {
                std::fprintf(csv, "%d,%d,%d,%d,%.6f,%.6f,%.6f,%.6f,%.6f,%d,%d\n",
                    t, cycle_idx, r_pre, r_post,
                    fixed_to_float(g), fixed_to_float(q), fixed_to_float(s),
                    fixed_to_float(dw), fixed_to_float(syn.weight),
                    n0_fired ? 1 : 0, n1_fired ? 1 : 0);
            }
        } else {
            // Döngü sonu — ağırlık kaydet (T1/T2)
            if (cycle_t == CYCLE_LEN - 1) {
                weight_at_cycle_end[cycle_idx] = syn.weight;
            }

            // 7. CSV satırı (aktarım)
            std::fprintf(csv, "%d,%d,%.6f,%.6f,%d,%d\n",
                t, cycle_idx,
                fixed_to_float(syn.weight),
                fixed_to_float(syn_current),
                n0_fired ? 1 : 0, n1_fired ? 1 : 0);
        }
    }

    std::fclose(csv);

    // İstatistikleri doldur
    stats.weight_end = syn.weight;
    if (cfg.learn_on) {
        stats.first_cycle_mean_abs_dw = mean_abs_dw_per_cycle[0];
        stats.last_cycle_mean_abs_dw  = mean_abs_dw_per_cycle[cfg.n_cycles - 1];

        // Monotonluk
        stats.monotonic_ok = true;
        for (int c = 1; c < cfg.n_cycles; ++c) {
            if (weight_at_cycle_end[c] < weight_at_cycle_end[c - 1]) {
                stats.monotonic_ok = false;
                break;
            }
        }

        // Doygunluk
        double last_rate = stats.last_cycle_mean_abs_dw;
        double first_rate = stats.first_cycle_mean_abs_dw;
        stats.saturation_ok = (last_rate < first_rate * 0.5) &&
                              (fixed_to_float(syn.weight) < fixed_to_float(W_MAX));
    }

    return stats;
}

// ---------------------------------------------------------------------------
// Doğrulama (a) — büyüme
// ---------------------------------------------------------------------------

void verify_growth(const PhaseStats& stats, int n_cycles, const char* label) {
    std::printf("\n--- (a) Buyume dogrulamasi (%s) ---\n", label);
    if (stats.monotonic_ok) {
        std::printf("OK BUYUME DOGRULANDI: weight monoton artiyor.\n");
    } else {
        std::printf("UYARI: weight beklenen sekilde monoton artmadi.\n");
    }
}

// ---------------------------------------------------------------------------
// Doğrulama (b) — doygunluk
// ---------------------------------------------------------------------------

void verify_saturation(const PhaseStats& stats, int n_cycles, const char* label) {
    std::printf("\n--- (b) Doygunluk (S regularizasyon) dogrulamasi (%s) ---\n", label);
    double w_max_f = fixed_to_float(W_MAX);
    double final_w = fixed_to_float(stats.weight_end);
    std::printf("  Ilk dongu ortalama |dw|/tick : %.8f\n", stats.first_cycle_mean_abs_dw);
    std::printf("  Son  dongu ortalama |dw|/tick : %.8f\n", stats.last_cycle_mean_abs_dw);
    std::printf("  Son weight: %.6f  (W_MAX = %.6f, oran = %.1f%%)\n",
                final_w, w_max_f, 100.0 * final_w / w_max_f);
    if (stats.saturation_ok) {
        std::printf("OK DOYGUNLUK DOGRULANDI: dw buyuklugu belirgin sekilde kuculdu.\n");
    } else {
        std::printf("UYARI: doygunluk beklendigi kadar net degil.\n");
    }
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------

int main() {
    std::printf("=== Sinaps Ogrenme Kurali + Gercek Akim Aktarimi Testi ===\n\n");
    std::printf("Dört faz: L0 (acik dongu ogrenmesi), L1 (kapali dongu), ");
    std::printf("T1/T2 (transfer).\n");
    std::printf("Uyaran dongusu %d tick, ogrenmede %d kez, transferde %d kez.\n\n",
                CYCLE_LEN, N_CYCLES, N_CYCLES_TX);

    synapse_build_luts();

    // =====================================================================
    // L0 — AÇIK DÖNGÜ ÖĞRENMESİ (transfer kapalı, referans)
    // =====================================================================
    std::printf(">>> L0 OGRENME (ACIK DONGU, transfer=false)\n");
    PhaseConfig cfg_l0 = {};
    cfg_l0.learn_on = true;
    cfg_l0.drive_n1 = true;
    cfg_l0.transmit = false;
    cfg_l0.transfer_csv_col = false;
    cfg_l0.n_cycles = N_CYCLES;
    cfg_l0.weight = fixed_from_double(0.05);
    cfg_l0.csv_path = "synapse_learning.csv";
    cfg_l0.label = "L0";
    PhaseStats s0 = run_phase(cfg_l0);
    verify_growth(s0, N_CYCLES, "L0");
    verify_saturation(s0, N_CYCLES, "L0");

    // =====================================================================
    // L1 — KAPALI DÖNGÜ ÖĞRENMESİ (transfer açık, geri besleme testi)
    // =====================================================================
    std::printf("\n>>> L1 OGRENME (KAPALI DONGU, transfer=true)\n");
    PhaseConfig cfg_l1 = {};
    cfg_l1.learn_on = true;
    cfg_l1.drive_n1 = true;
    cfg_l1.transmit = true;
    cfg_l1.transfer_csv_col = true;
    cfg_l1.n_cycles = N_CYCLES;
    cfg_l1.weight = fixed_from_double(0.05);
    cfg_l1.csv_path = "synapse_learning_closedloop.csv";
    cfg_l1.label = "L1";
    PhaseStats s1 = run_phase(cfg_l1);
    verify_growth(s1, N_CYCLES, "L1");
    verify_saturation(s1, N_CYCLES, "L1");

    // =====================================================================
    // C1–C5 KAPALI DÖNGÜ KONTROLLERI (L1 vs L0)
    // =====================================================================
    std::printf("\n--- (c) Kapali dongu kararliligi (L1 vs L0) ---\n");

    bool c1_ok = s1.monotonic_ok;
    std::printf("%s C1: L1 weight monoton artiyor\n", c1_ok ? "OK" : "UYARI");

    bool c2_ok = s1.last_cycle_mean_abs_dw < (s1.first_cycle_mean_abs_dw * 0.5);
    std::printf("%s C2: L1 dw buyuklugu yarisina dustu\n", c2_ok ? "OK" : "UYARI");

    double ratio = (s0.n1_fires > 0) ? (double)s1.n1_fires / (double)s0.n1_fires : 1.0;
    bool c3_ok = s1.n1_fires <= (3 * s0.n1_fires);
    std::printf("%s C3: L1 N1 ateş sayisi kontrol icinde (oran=%.2fx: %d vs %d)\n",
                c3_ok ? "OK" : "UYARI", ratio, s1.n1_fires, s0.n1_fires);

    bool c4_ok = s1.saturation_ok && (s1.first_half_weight_cycle >= N_CYCLES/5);
    std::printf("%s C4: L1 weight tavana ulasti ve tavan calisiyor\n", c4_ok ? "OK" : "UYARI");

    double n1_fire_rate = (double)s1.n1_fires / (double)(CYCLE_LEN * N_CYCLES);
    bool c5_ok = n1_fire_rate < 0.30;
    std::printf("%s C5: L1 N1 fire rate kontrol icinde (%.2f%% < 30%%)\n",
                c5_ok ? "OK" : "UYARI", 100.0 * n1_fire_rate);

    int c_ok_count = (c1_ok ? 1 : 0) + (c2_ok ? 1 : 0) + (c3_ok ? 1 : 0) +
                     (c4_ok ? 1 : 0) + (c5_ok ? 1 : 0);
    if (c_ok_count == 5) {
        std::printf("OK KAPALI DONGU KARARLI (5/5 kontrol gecti)\n");
    } else {
        std::printf("UYARI: KAPALI DONGU KARSIZ — %d/5 gecti\n", c_ok_count);
    }

    // Geri besleme görünürlüğü
    std::printf("(Geri besleme goru: L0 n1/dongu ~%d, L1 n1/dongu ~%d)\n",
                s0.n1_fires / N_CYCLES, s1.n1_fires / N_CYCLES);

    // =====================================================================
    // T1 — DÜŞÜK WEIGHT AKTARIMı (kontrol, L1 öncesi weight)
    // =====================================================================
    std::printf("\n>>> T1 AKTARIM (dusuk weight=0.05, ogrenmesiz)\n");
    PhaseConfig cfg_t1 = {};
    cfg_t1.learn_on = false;
    cfg_t1.drive_n1 = false;
    cfg_t1.transmit = true;
    cfg_t1.transfer_csv_col = true;
    cfg_t1.n_cycles = N_CYCLES_TX;
    cfg_t1.weight = fixed_from_double(0.05);
    cfg_t1.csv_path = "synapse_transfer_low.csv";
    cfg_t1.label = "T1";
    PhaseStats st1 = run_phase(cfg_t1);

    // =====================================================================
    // T2 — ÖĞRENILMIŞ WEIGHT AKTARIMı (test, L1 sonrası weight)
    // =====================================================================
    std::printf("\n>>> T2 AKTARIM (ogrenmis weight=%.6f, ogrenmesiz)\n",
                fixed_to_float(s1.weight_end));
    PhaseConfig cfg_t2 = {};
    cfg_t2.learn_on = false;
    cfg_t2.drive_n1 = false;
    cfg_t2.transmit = true;
    cfg_t2.transfer_csv_col = true;
    cfg_t2.n_cycles = N_CYCLES_TX;
    cfg_t2.weight = s1.weight_end;
    cfg_t2.csv_path = "synapse_transfer_high.csv";
    cfg_t2.label = "T2";
    PhaseStats st2 = run_phase(cfg_t2);

    // =====================================================================
    // (d) AKIM AKTARIMI DOĞRULAMASI (T1 vs T2)
    // =====================================================================
    std::printf("\n--- (d) Akim aktarimi dogrulamasi ---\n");
    std::printf("N0 atesler: T1=%d, T2=%d ", st1.n0_fires, st2.n0_fires);
    bool n0_equal = (st1.n0_fires == st2.n0_fires);
    std::printf("(kontrol: %s)\n", n0_equal ? "esit" : "FARKLI");

    std::printf("N1 atesler: T1=%d (beklenen ~0), T2=%d (beklenen >=10)\n",
                st1.n1_fires, st2.n1_fires);
    std::printf("T2 ilk N1 ates dongusu: %d\n", st2.first_n1_fire_cycle);

    bool akim_ok = (st1.n0_fires == st2.n0_fires) && (st1.n1_fires == 0) && (st2.n1_fires >= 10);
    if (akim_ok) {
        std::printf("OK AKIM AKTARIMI DOGRULANDI: N1, N0'in sinaptik girdisiyle ");
        std::printf("atesliyor (low:%.2f*%d=~0 ates, high:%.2f*%d=%d ates).\n",
                    fixed_to_float(st1.weight_end) * 0.5, st1.n0_fires,
                    fixed_to_float(st2.weight_end) * 0.5, st2.n0_fires, st2.n1_fires);
    } else {
        std::printf("UYARI: AKIM AKTARIMI BEKLENDIGINI KARSILAMADI.\n");
        std::printf("  Kontrol: n0_T1==n0_T2: %s\n", n0_equal ? "OK" : "HATA");
        std::printf("  T1 N1 ates: %s (bekenen 0)\n", st1.n1_fires == 0 ? "OK" : "HATA");
        std::printf("  T2 N1 ates: %s (bekenen >=10)\n", st2.n1_fires >= 10 ? "OK" : "HATA");
    }

    // =====================================================================
    // ÖZET
    // =====================================================================
    std::printf("\n=== ÖZET ===\n");
    std::printf("L0 CSV: synapse_learning.csv (%d satir)\n", CYCLE_LEN * N_CYCLES);
    std::printf("L1 CSV: synapse_learning_closedloop.csv (%d satir)\n", CYCLE_LEN * N_CYCLES);
    std::printf("T1 CSV: synapse_transfer_low.csv (%d satir)\n", CYCLE_LEN * N_CYCLES_TX);
    std::printf("T2 CSV: synapse_transfer_high.csv (%d satir)\n", CYCLE_LEN * N_CYCLES_TX);

    bool all_ok = (c_ok_count == 5) && akim_ok && s0.monotonic_ok && s1.monotonic_ok;
    if (all_ok) {
        std::printf("\nOK TUM DOGRULMALAR BASARILI!\n");
    } else {
        std::printf("\nUYARI: Bazı doğrulmalar başarısız veya sınırda.\n");
    }

    return 0;
}
