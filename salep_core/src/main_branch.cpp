#include "neuron.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>

// ---------------------------------------------------------------------------
// Üç-senaryolu dallanma testi
//
// ARCHITECTURE.md §3 doğrulaması: iki dalın eşzamanlılığı ateşlemeyi
// kolaylaştırıyor mu?
//
// Senaryo 1 (-s1): Sadece Dal A'ya enjeksiyon (faz dalı)
// Senaryo 2 (-s2): Sadece Dal B'ye enjeksiyon (sensör dalı)
// Senaryo 3 (-s3): Her iki dala da eşzamanlı enjeksiyon
//
// Uyaran programı (her senaryo için aynı zaman penceresi):
//   Tick 50–80: her 5 tick'te 0.5 birim akım
//   Tick 150–180: her 3 tick'te 0.8 birim akım
//   Tick 220–250: her 5 tick'te 0.5 birim akım (hafıza testi)
//
// Kullanım:
//   ./salep_branch -s1    → branch_s1.csv
//   ./salep_branch -s2    → branch_s2.csv
//   ./salep_branch -s3    → branch_s3.csv
//   ./salep_branch -all   → üç senaryoyu sırayla çalıştır + özet tablo
// ---------------------------------------------------------------------------

// Enjeksiyon hedefi flag'leri
static bool inject_branch_A = false;
static bool inject_branch_B = false;

// Uyaran programı — hedef dallara göre enjekte eder
static bool should_inject(int32_t tick, fixed_t& out_current) {
    // Faz 1: orta şiddet
    if (tick >= 50 && tick < 80 && (tick % 5 == 0)) {
        out_current = fixed_from_double(0.5);
        return true;
    }
    // Faz 2: güçlü, sık
    if (tick >= 150 && tick < 180 && (tick % 3 == 0)) {
        out_current = fixed_from_double(0.8);
        return true;
    }
    // Faz 3: Faz 1 ile aynı (hafıza testi)
    if (tick >= 220 && tick < 250 && (tick % 5 == 0)) {
        out_current = fixed_from_double(0.5);
        return true;
    }
    out_current = 0;
    return false;
}

// ---------------------------------------------------------------------------
// Tek senaryo simülasyonu
//
// CSV sütunları:
//   tick, root_v, branchA_v, branchB_v,
//   root_gating, branchA_gating, branchB_gating,
//   soma_v, fired, injected, coincidence
// ---------------------------------------------------------------------------

struct ScenarioResult {
    int fire_count;
    int first_fire_tick;  // -1 = hiç ateşlemedi
    char csv_path[128];
};

static ScenarioResult run_scenario(const char* csv_path, int scenario_num) {
    ScenarioResult result;
    result.fire_count     = 0;
    result.first_fire_tick = -1;
    std::strncpy(result.csv_path, csv_path, sizeof(result.csv_path) - 1);
    result.csv_path[sizeof(result.csv_path) - 1] = '\0';

    DendriticNeuron neuron;
    neuron_init(neuron, /*id=*/0);

    FILE* csv = std::fopen(csv_path, "w");
    if (!csv) {
        std::fprintf(stderr, "HATA: %s açılamadı\n", csv_path);
        return result;
    }

    std::fprintf(csv,
        "tick,root_v,branchA_v,branchB_v,"
        "root_gating,branchA_gating,branchB_gating,"
        "soma_v,fired,injected,coincidence\n");

    constexpr int32_t TOTAL_TICKS = 500;

    for (int32_t t = 0; t < TOTAL_TICKS; ++t) {
        // Enjeksiyon
        fixed_t injection = 0;
        bool injected = should_inject(t, injection);
        if (injected) {
            if (inject_branch_A) {
                neuron_inject_current(neuron, neuron.branch_A_id, injection, t);
            }
            if (inject_branch_B) {
                neuron_inject_current(neuron, neuron.branch_B_id, injection, t);
            }
        }

        // Tick
        bool fired = neuron_tick(neuron, t);
        if (fired) {
            result.fire_count++;
            if (result.first_fire_tick < 0) {
                result.first_fire_tick = t;
            }
        }

        // Eşzamanlılık durumu (CSV için tekrar hesapla — girdi tabanlı)
        bool branch_A_input = (neuron.branch_A_last_input_tick >= 0) &&
                               ((t - neuron.branch_A_last_input_tick)
                                 <= COINCIDENCE_WINDOW_MS);
        bool branch_B_input = (neuron.branch_B_last_input_tick >= 0) &&
                               ((t - neuron.branch_B_last_input_tick)
                                 <= COINCIDENCE_WINDOW_MS);
        bool coincidence = branch_A_input && branch_B_input;

        // CSV satırı
        std::fprintf(csv,
            "%d,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%d,%d,%d\n",
            t,
            fixed_to_float(neuron.compartments[0].local_voltage),
            fixed_to_float(neuron.compartments[neuron.branch_A_id].local_voltage),
            fixed_to_float(neuron.compartments[neuron.branch_B_id].local_voltage),
            fixed_to_float(neuron.compartments[0].gating_state),
            fixed_to_float(neuron.compartments[neuron.branch_A_id].gating_state),
            fixed_to_float(neuron.compartments[neuron.branch_B_id].gating_state),
            fixed_to_float(neuron.soma_voltage),
            fired ? 1 : 0,
            injected ? 1 : 0,
            coincidence ? 1 : 0);
    }

    std::fclose(csv);

    std::printf("  Senaryo %d: %d ateşleme, ilk ateşleme tick=%d → %s\n",
                scenario_num,
                result.fire_count,
                result.first_fire_tick,
                csv_path);

    return result;
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::fprintf(stderr,
            "Kullanım:\n"
            "  %s -s1     Sadece Dal A\n"
            "  %s -s2     Sadece Dal B\n"
            "  %s -s3     Her iki dal (eşzamanlı)\n"
            "  %s -all    Üç senaryo + karşılaştırma tablosu\n",
            argv[0], argv[0], argv[0], argv[0]);
        return 1;
    }

    bool run_all = (std::strcmp(argv[1], "-all") == 0);

    if (run_all) {
        std::printf("=== Dallanma Testi: 3 Senaryo ===\n\n");

        // Senaryo 1: Sadece Dal A
        inject_branch_A = true;  inject_branch_B = false;
        ScenarioResult r1 = run_scenario("branch_s1.csv", 1);

        // Senaryo 2: Sadece Dal B
        inject_branch_A = false; inject_branch_B = true;
        ScenarioResult r2 = run_scenario("branch_s2.csv", 2);

        // Senaryo 3: İkisi birden
        inject_branch_A = true;  inject_branch_B = true;
        ScenarioResult r3 = run_scenario("branch_s3.csv", 3);

        // --- Karşılaştırma tablosu ---
        std::printf("\n╔══════════════════════╦══════════════╦════════════════════╗\n");
        std::printf("║ Senaryo              ║ Ateşleme     ║ İlk ateşleme tick  ║\n");
        std::printf("╠══════════════════════╬══════════════╬════════════════════╣\n");
        std::printf("║ 1: Sadece Dal A      ║ %4d         ║ %4d               ║\n",
                    r1.fire_count, r1.first_fire_tick);
        std::printf("║ 2: Sadece Dal B      ║ %4d         ║ %4d               ║\n",
                    r2.fire_count, r2.first_fire_tick);
        std::printf("║ 3: İkisi birden      ║ %4d         ║ %4d               ║\n",
                    r3.fire_count, r3.first_fire_tick);
        std::printf("╚══════════════════════╩══════════════╩════════════════════╝\n");

        // --- Sonuç yorumu ---
        std::printf("\n");
        if (r3.fire_count > r1.fire_count && r3.fire_count > r2.fire_count) {
            std::printf("✓ Beklenen sonuç DOĞRULANDI: Senaryo 3 (eşzamanlı) daha "
                        "fazla ateşleme üretiyor.\n");
        } else {
            std::printf("✗ UYARI: Senaryo 3 beklenen avantajı göstermiyor!\n"
                        "  Parametre ayarlaması gerekebilir.\n");
        }
        if (r3.first_fire_tick >= 0 && r3.first_fire_tick < r1.first_fire_tick
            && r3.first_fire_tick < r2.first_fire_tick) {
            std::printf("✓ Beklenen sonuç DOĞRULANDI: Senaryo 3 daha erken "
                        "ateşliyor (tick %d vs %d / %d).\n",
                        r3.first_fire_tick, r1.first_fire_tick, r2.first_fire_tick);
        } else if (r3.first_fire_tick >= 0) {
            std::printf("△ İlk ateşleme sıralaması beklentiden farklı olabilir — "
                        "grafikte kontrol et.\n");
        }
    } else {
        int scenario = 0;
        const char* csv_path = nullptr;

        if (std::strcmp(argv[1], "-s1") == 0) {
            scenario = 1;
            inject_branch_A = true;  inject_branch_B = false;
            csv_path = "branch_s1.csv";
        } else if (std::strcmp(argv[1], "-s2") == 0) {
            scenario = 2;
            inject_branch_A = false; inject_branch_B = true;
            csv_path = "branch_s2.csv";
        } else if (std::strcmp(argv[1], "-s3") == 0) {
            scenario = 3;
            inject_branch_A = true;  inject_branch_B = true;
            csv_path = "branch_s3.csv";
        } else {
            std::fprintf(stderr, "Bilinmeyen argüman: %s\n", argv[1]);
            return 1;
        }

        run_scenario(csv_path, scenario);
    }

    return 0;
}
