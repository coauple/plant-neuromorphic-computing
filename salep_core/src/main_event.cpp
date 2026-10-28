#include "event_neuron.h"

#include <cstdio>

// ---------------------------------------------------------------------------
// Uyaran programı — main.cpp ile AYNI (karşılaştırılabilirlik için)
// ---------------------------------------------------------------------------

static bool should_inject(int32_t tick, fixed_t& out_current) {
    // Faz 1: orta şiddet, sık pulslar
    if (tick >= 50 && tick < 80 && (tick % 5 == 0)) {
        out_current = fixed_from_double(0.5);
        return true;
    }
    // Faz 2: güçlü, çok sık pulslar
    if (tick >= 150 && tick < 180 && (tick % 3 == 0)) {
        out_current = fixed_from_double(0.8);
        return true;
    }
    // Faz 3: Faz 1 ile aynı (gating hafızası testi)
    if (tick >= 220 && tick < 250 && (tick % 5 == 0)) {
        out_current = fixed_from_double(0.5);
        return true;
    }
    out_current = 0;
    return false;
}

// ---------------------------------------------------------------------------
// Olay-güdümlü simülasyon döngüsü — 500 tick
//
// Dense (main.cpp) ile aynı uyaran programını kullanır.
// Fark: nöron uyuyorken hesap yapılmaz.
//
// CSV çıktısı aynı formatta — karşılaştırılabilir.
// Uyku sırasında CSV'ye voltaj=0 ve analitik olarak sönümlenmiş gating yazılır.
//
// "display_gating" değişkenleri: CSV için uyku sırasında gating'i
// her tick'te (1−decay) ile çarparak takip eder. Bu sadece görüntüleme
// amaçlı — nöronun kendisi hiçbir hesap yapmıyor.
// ---------------------------------------------------------------------------

int main() {
    EventDrivenNeuron en;
    event_neuron_init(en, /*id=*/0);

    FILE* csv = std::fopen("neuron_trace_event.csv", "w");
    if (!csv) {
        std::fprintf(stderr, "HATA: neuron_trace_event.csv açılamadı\n");
        return 1;
    }

    std::fprintf(csv,
        "tick,root_v,child_v,root_gating,child_gating,soma_v,"
        "fired,injected,awake\n");

    constexpr int32_t TOTAL_TICKS = 500;
    int fire_count   = 0;
    int sleep_ticks  = 0;

    // Uyku sırasında CSV'ye yazılacak gating değerleri (incremental decay)
    fixed_t display_gating[2] = {0, 0};

    // Uykudaki gating sönüm çarpanları: (1 − decay_rate)
    // neuron_init'ten alıyoruz — header'daki sabit değerlerle uyumlu olmalı
    fixed_t gating_retain[2] = {
        FIXED_ONE - en.core.compartments[0].gating_decay_rate,
        FIXED_ONE - en.core.compartments[1].gating_decay_rate
    };

    for (int32_t t = 0; t < TOTAL_TICKS; ++t) {

        // --- 1. Olay var mı? ---
        fixed_t injection = 0;
        bool has_event = should_inject(t, injection);

        // --- 2. Olay varsa ve uyuyorsa → uyandır ---
        if (has_event && !en.awake) {
            event_neuron_wake(en, t);
        }

        // --- 3. Uyanıksa: olay işle + tick hesapla ---
        bool fired = false;
        if (en.awake) {
            if (has_event) {
                neuron_inject_current(en.core, /*compartment_id=*/1, injection, t);
            }
            fired = neuron_tick(en.core, t);
            en.active_tick_count++;

            if (fired) {
                ++fire_count;
            }

            // display_gating'i güncelle (uyanıkken gerçek değerler)
            display_gating[0] = en.core.compartments[0].gating_state;
            display_gating[1] = en.core.compartments[1].gating_state;

            // Uyku koşulunu kontrol et
            if (event_neuron_can_sleep(en)) {
                event_neuron_enter_sleep(en, t);
            }
        } else {
            // --- 4. Uyuyorsa: sadece display_gating'i sönümle (CSV için) ---
            display_gating[0] = fixed_mul(display_gating[0], gating_retain[0]);
            display_gating[1] = fixed_mul(display_gating[1], gating_retain[1]);
            if (display_gating[0] < 0) display_gating[0] = 0;
            if (display_gating[1] < 0) display_gating[1] = 0;
            ++sleep_ticks;
        }

        // --- 5. CSV satırı ---
        std::fprintf(csv, "%d,%.6f,%.6f,%.6f,%.6f,%.6f,%d,%d,%d\n",
            t,
            fixed_to_float(en.awake ? en.core.compartments[0].local_voltage : V_REST),
            fixed_to_float(en.awake ? en.core.compartments[1].local_voltage : V_REST),
            fixed_to_float(display_gating[0]),
            fixed_to_float(display_gating[1]),
            fixed_to_float(en.awake ? en.core.soma_voltage : V_REST),
            fired ? 1 : 0,
            has_event ? 1 : 0,
            en.awake ? 1 : 0);
    }

    std::fclose(csv);

    // --- İstatistikler ---
    int active = en.active_tick_count;
    std::printf("=== Olay-Güdümlü Simülasyon Tamamlandı ===\n");
    std::printf("Toplam tick    : %d\n", TOTAL_TICKS);
    std::printf("Aktif tick     : %d (%%%.1f)\n",
                active, 100.0f * active / TOTAL_TICKS);
    std::printf("Uyku tick      : %d (%%%.1f)\n",
                sleep_ticks, 100.0f * sleep_ticks / TOTAL_TICKS);
    std::printf("Ateşleme       : %d\n", fire_count);
    std::printf("Çıktı          : neuron_trace_event.csv\n");

    return 0;
}
