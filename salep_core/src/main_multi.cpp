// ===========================================================================
// main_multi.cpp — Çoklu Nöron Karşılaştırma Testi
//
// SKILL.md §3: "Faz Çözümleme Nöronları: tau değerine göre ayarlı"
// SKILL.md §6: "2-3 farklı nöron tipi oluştur, aynı uyaranla test et"
//
// 3 nöron, aynı uyaran (Faz 1/2/3), iki dala birden enjekte.
// Her nöronun farklı leak_rate / gating_decay_rate seti var.
//
// Beklenen sonuç: farklı nöronlar aynı uyarana farklı tepki verir.
//
// Sinaps yok. Öğrenme kuralı yok. Kümeleme yok.
// ===========================================================================

#include "neuron.h"
#include <cstdio>
#include <cstring>

// ---------------------------------------------------------------------------
// 3 Nöron Tipi — Parametre Setleri
//
// SKILL.md §3: "Dal A ham veya karışık sinyal hattını alır ve rezonans
// filtresiyle çözümler (demux). tau_resonance değerine göre ayarlıdır."
//
// tau_resonance burada henüz sinaps seviyesinde uygulanmıyor (sinaps yok),
// ama etkisini leak_rate üzerinden modelliyoruz:
//   - Düşük leak → voltaj uzun yaşar → yavaş/sürekli sinyallere duyarlı
//   - Yüksek leak → voltaj hızlı söner → hızlı/güçlü darbelere duyarlı
//
// gating_decay_rate ise hafıza süresini belirler:
//   - Düşük decay → uzun hafıza → tekrarlayan örüntüleri biriktirir
//   - Yüksek decay → kısa hafıza → sadece anlık güce tepki verir
//
// N0 (Hızlı ritim nöronu):
//   - DÜŞÜK leak: voltaj uzun yaşar → sık darbelerin birikimine duyarlı
//   - YÜKSEK gating decay: kısa hafıza → sadece hızlı ritimde (Faz 2)
//     yeterli gating birikir, yavaş ritimde (Faz 1/3) birikim yetersiz kalır
//   - Beklenti: Faz 2'de çok ateşlesin, Faz 1/3'te az/hiç
//
// N1 (Yavaş ritim nöronu):
//   - YÜKSEK leak: voltaj hızlı söner → tek tek darbeler etkisiz
//   - DÜŞÜK gating decay: uzun hafıza → yavaş biriken gating zamanla
//     eşiği aşmasını kolaylaştırır (ama voltaj hızlı sönüyor!)
//   - Beklenti: erken fazlarda AZ ateşlesin, geç fazlarda HAFIZA
//     sayesinde biraz ateşlesin (ama N0'dan farklı profil)
//
// N2 (Dengeli / mevcut varsayılan):
//   - Orta leak, orta gating decay → genel amaçlı tepki
//   - Beklenti: her fazda orta seviye tepki
// ---------------------------------------------------------------------------

// Nöron parametre tanımları
static constexpr NeuronParams NEURON_TYPES[3] = {
    // N0: Hızlı ritim — çok düşük leak (voltaj çok uzun birikir),
    //     yüksek gating decay (hafıza kısa → sadece SIK darbeler biriktirir)
    //     Beklenti: Faz 2 (sık, güçlü) için en iyi; Faz 1/3 (seyrek) için de
    //     iyi ama gating biriktirmez.
    //   root_leak  brA_leak  brB_leak  root_gdecay  brA_gdecay  brB_gdecay
    {    0.02,      0.015,    0.015,    0.03,        0.035,      0.03    },

    // N1: Yavaş ritim — çok yüksek leak (voltaj hızlı söner, tek darbe etkisiz),
    //     çok düşük gating decay (hafıza çok uzun → ama voltaj tutmak zor)
    //     Beklenti: Faz 1'de neredeyse hiç ateşlemez (voltaj hemen söner).
    //     Faz 2'de güçlü darbeler zar zor ateşler. Faz 3'te gating birikimi
    //     sayesinde biraz daha kolay ateşler — ama yine de az.
    //   root_leak  brA_leak  brB_leak  root_gdecay  brA_gdecay  brB_gdecay
    {    0.20,      0.18,     0.15,     0.001,       0.001,      0.001   },

    // N2: Dengeli — mevcut varsayılan parametreler (neuron_init ile aynı)
    //   root_leak  brA_leak  brB_leak  root_gdecay  brA_gdecay  brB_gdecay
    {    0.08,      0.06,     0.04,     0.005,       0.004,      0.003   },
};

// Nöron isimleri (tablo ve dosya için)
static const char* NEURON_NAMES[3] = {
    "N0_hizli_ritim",
    "N1_yavas_ritim",
    "N2_dengeli",
};

// Kısa Türkçe açıklama
static const char* NEURON_DESC[3] = {
    "Hızlı ritim (düşük leak, yüksek gating decay)",
    "Yavaş ritim (yüksek leak, düşük gating decay)",
    "Dengeli (mevcut varsayılan)",
};

// ---------------------------------------------------------------------------
// Uyaran programı — Faz 1/2/3, main_branch.cpp ile aynı
//
// Faz 1 (tick 50-80):  her 5 tick, akım=0.5 — orta şiddet
// Faz 2 (tick 150-180): her 3 tick, akım=0.8 — güçlü, sık
// Faz 3 (tick 220-250): her 5 tick, akım=0.5 — Faz 1 tekrarı (hafıza testi)
// ---------------------------------------------------------------------------

static bool should_inject(int32_t t, fixed_t& current_out) {
    // Faz 1
    if (t >= 50 && t <= 80 && (t - 50) % 5 == 0) {
        current_out = fixed_from_double(0.5);
        return true;
    }
    // Faz 2
    if (t >= 150 && t <= 180 && (t - 150) % 3 == 0) {
        current_out = fixed_from_double(0.8);
        return true;
    }
    // Faz 3
    if (t >= 220 && t <= 250 && (t - 220) % 5 == 0) {
        current_out = fixed_from_double(0.5);
        return true;
    }
    current_out = 0;
    return false;
}

// ---------------------------------------------------------------------------
// Tek nöronun simülasyonunu çalıştır, CSV'ye yaz, sonuçları döndür
// ---------------------------------------------------------------------------

struct NeuronResult {
    int fire_count;
    int32_t first_fire_tick;
    // Faz bazlı ateşleme sayıları
    int phase1_fires;  // tick 50-130  (faz 1 + sonrası)
    int phase2_fires;  // tick 150-219 (faz 2 + sonrası)
    int phase3_fires;  // tick 220-350 (faz 3 + sonrası)
};

static NeuronResult run_neuron(int neuron_index) {
    NeuronResult result = {0, -1, 0, 0, 0};

    DendriticNeuron neuron;
    neuron_init_with_params(neuron, neuron_index, NEURON_TYPES[neuron_index]);

    // CSV dosyası aç
    char csv_path[128];
    std::snprintf(csv_path, sizeof(csv_path), "multi_%s.csv",
                  NEURON_NAMES[neuron_index]);

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
        // Enjeksiyon — iki dala birden
        fixed_t injection = 0;
        bool injected = should_inject(t, injection);
        if (injected) {
            neuron_inject_current(neuron, neuron.branch_A_id, injection, t);
            neuron_inject_current(neuron, neuron.branch_B_id, injection, t);
        }

        // Tick
        bool fired = neuron_tick(neuron, t);

        if (fired) {
            result.fire_count++;
            if (result.first_fire_tick < 0) {
                result.first_fire_tick = t;
            }
            // Faz bazlı sayım
            if (t >= 50 && t < 150)       result.phase1_fires++;
            else if (t >= 150 && t < 220) result.phase2_fires++;
            else if (t >= 220 && t < 350) result.phase3_fires++;
        }

        // Eşzamanlılık durumu (CSV için)
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
    return result;
}

// ---------------------------------------------------------------------------
// main — 3 nöronu çalıştır, karşılaştır
// ---------------------------------------------------------------------------

int main() {
    std::printf("=== Çoklu Nöron Karşılaştırma Testi ===\n\n");
    std::printf("Uyaran: Faz 1 (50-80, 5/tick, 0.5), "
                "Faz 2 (150-180, 3/tick, 0.8), "
                "Faz 3 (220-250, 5/tick, 0.5)\n");
    std::printf("Her nörona iki dala birden enjekte ediliyor.\n\n");

    NeuronResult results[3];

    for (int i = 0; i < 3; ++i) {
        results[i] = run_neuron(i);
        std::printf("  %s: %d ateşleme, ilk tick=%d → multi_%s.csv\n",
                    NEURON_DESC[i],
                    results[i].fire_count,
                    results[i].first_fire_tick,
                    NEURON_NAMES[i]);
    }

    // Karşılaştırma tablosu
    std::printf("\n");
    std::printf("╔════════════════════════════╦══════════╦══════════╦══════════════╦══════════════╦══════════════╗\n");
    std::printf("║ Nöron tipi                 ║ Toplam   ║ İlk tick ║ Faz 1 fires  ║ Faz 2 fires  ║ Faz 3 fires  ║\n");
    std::printf("╠════════════════════════════╬══════════╬══════════╬══════════════╬══════════════╬══════════════╣\n");
    for (int i = 0; i < 3; ++i) {
        std::printf("║ %-26s ║  %3d     ║  %4d    ║    %3d       ║    %3d       ║    %3d       ║\n",
                    NEURON_DESC[i],
                    results[i].fire_count,
                    results[i].first_fire_tick,
                    results[i].phase1_fires,
                    results[i].phase2_fires,
                    results[i].phase3_fires);
    }
    std::printf("╚════════════════════════════╩══════════╩══════════╩══════════════╩══════════════╩══════════════╝\n");

    // Doğrulama
    std::printf("\n");
    bool all_same = (results[0].fire_count == results[1].fire_count) &&
                    (results[1].fire_count == results[2].fire_count);
    if (all_same) {
        std::printf("⚠  UYARI: Tüm nöronlar aynı sayıda ateşledi — parametreler yeterince farklı değil!\n");
    } else {
        std::printf("✓ DOĞRULANDI: Farklı nöron tipleri aynı uyarana farklı tepki veriyor.\n");
    }

    // Profil karşılaştırma
    bool different_profiles = false;
    for (int i = 0; i < 3; ++i) {
        for (int j = i + 1; j < 3; ++j) {
            // Faz bazlı sıralama farklı mı?
            if ((results[i].phase1_fires > results[i].phase2_fires) !=
                (results[j].phase1_fires > results[j].phase2_fires)) {
                different_profiles = true;
            }
        }
    }
    if (different_profiles) {
        std::printf("✓ DOĞRULANDI: Nöronlar farklı fazlara farklı güçte tepki veriyor (seçicilik).\n");
    }

    return 0;
}
