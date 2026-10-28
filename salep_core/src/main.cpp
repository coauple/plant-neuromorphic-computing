#include "neuron.h"

#include <cstdio>

// ---------------------------------------------------------------------------
// Uyaran (stimulus) programı
//
// Sinaps olmadığı için akım enjeksiyonuyla test ediyoruz.
// Üç faz:
//   1) Tick 50–69  : periyodik pulslar (her 10 tick'te 0.4 birim)
//                    → difüzyon + leak + gating birikimini gözlemle
//   2) Tick 100–119: daha güçlü pulslar (her 5 tick'te 0.6 birim)
//                    → ateşleme olmalı, gating yükselmiş olmalı
//   3) Tick 200–219: ilk fazla aynı pulslar (her 10 tick'te 0.4 birim)
//                    → gating hâlâ aktifse, bu sefer de ateşleyebilir
//                    (kısa vadeli hafıza etkisi)
//
// Enjeksiyon hedefi: çocuk kompartıman (indeks 1, distal).
// Neden distal: sinyalin difüzyonla köke yayılmasını ve yol boyunca
// sızıntıyla azalmasını görmek istiyoruz.
// ---------------------------------------------------------------------------

static bool should_inject(int32_t tick, fixed_t& out_current) {
    // Faz 1: orta şiddet, sık pulslar — eşiğe yaklaşmalı, belki ateşlemeli
    if (tick >= 50 && tick < 80 && (tick % 5 == 0)) {
        out_current = fixed_from_double(0.5);
        return true;
    }
    // Faz 2: güçlü, çok sık pulslar — kesinlikle ateşlemeli
    if (tick >= 150 && tick < 180 && (tick % 3 == 0)) {
        out_current = fixed_from_double(0.8);
        return true;
    }
    // Faz 3: Faz 1 ile aynı şiddet ve sıklık — ama gating birikmiş olmalı.
    // Faz 2→3 arası 40 tick: gating_decay_rate=0.005 ile kök gating'in
    // ~%82'si, child gating'in ~%89'u hayatta kalır.
    if (tick >= 220 && tick < 250 && (tick % 5 == 0)) {
        out_current = fixed_from_double(0.5);
        return true;
    }
    out_current = 0;
    return false;
}

// ---------------------------------------------------------------------------
// Ana döngü — 500 tick simülasyon
//
// CSV formatı (ilk satır başlık):
//   tick, root_v, child_v, root_gating, child_gating, soma_v, fired, injected
//
// Voltajlar float olarak yazılıyor — SADECE çıktı amaçlı.
// Simülasyon döngüsünde float işlemi YOK.
// ---------------------------------------------------------------------------

int main() {
    // --- Nöron oluştur ---
    DendriticNeuron neuron;
    neuron_init(neuron, /*id=*/0);

    // --- CSV dosyası aç ---
    FILE* csv = std::fopen("neuron_trace.csv", "w");
    if (!csv) {
        std::fprintf(stderr, "HATA: neuron_trace.csv açılamadı\n");
        return 1;
    }

    // Başlık satırı
    std::fprintf(csv,
        "tick,root_v,child_v,root_gating,child_gating,soma_v,fired,injected\n");

    // --- Simülasyon döngüsü ---
    constexpr int32_t TOTAL_TICKS = 500;
    int fire_count = 0;

    for (int32_t t = 0; t < TOTAL_TICKS; ++t) {

        // Akım enjeksiyonu (tick başında, nöron güncellemesinden önce)
        fixed_t injection = 0;
        bool injected = should_inject(t, injection);
        if (injected) {
            neuron_inject_current(neuron, /*compartment_id=*/1, injection, t);
        }

        // Bir tick simüle et
        bool fired = neuron_tick(neuron, t);
        if (fired) {
            ++fire_count;
        }

        // CSV satırı yaz
        std::fprintf(csv, "%d,%.6f,%.6f,%.6f,%.6f,%.6f,%d,%d\n",
            t,
            fixed_to_float(neuron.compartments[0].local_voltage),
            fixed_to_float(neuron.compartments[1].local_voltage),
            fixed_to_float(neuron.compartments[0].gating_state),
            fixed_to_float(neuron.compartments[1].gating_state),
            fixed_to_float(neuron.soma_voltage),
            fired ? 1 : 0,
            injected ? 1 : 0);
    }

    std::fclose(csv);

    // --- Özet ---
    std::printf("Simülasyon tamamlandı: %d tick, %d ateşleme\n",
                TOTAL_TICKS, fire_count);
    std::printf("Çıktı: neuron_trace.csv\n");

    return 0;
}
