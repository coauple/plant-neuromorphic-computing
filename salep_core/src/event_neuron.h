#ifndef EVENT_NEURON_H
#define EVENT_NEURON_H

#include "neuron.h"

// ---------------------------------------------------------------------------
// Olay-güdümlü (event-driven) nöron sarmalayıcısı
//
// DendriticNeuron'un temel fiziği değişmiyor — aynı tick fonksiyonu.
// Bu katman, nöronun ne zaman hesap yapacağını kontrol eder:
//
//   UYANIK (awake): her tick'te neuron_tick çalışır (dense mod)
//   UYUYOR (sleep): hiçbir hesap yapılmaz
//
// Geçiş kuralları:
//   Uyku → Uyanış: dışarıdan olay geldiğinde (akım enjeksiyonu)
//     - Gating durumu analitik olarak hızlı-ileri sarılır:
//       gating = gating_sleep × (1 − decay)^elapsed
//     - O(log elapsed) çarpma — tüm tick'leri iterate etmekten çok ucuz
//     - Voltajlar zaten eşik altındaydı → V_REST'e sıfırlanır
//
//   Uyanış → Uyku: tüm kompartıman voltajları SLEEP_THRESH altına düştüğünde
//     - Gating snapshot'ı alınır (uyandığında hızlı-ileri sarmak için)
//     - Voltajlar V_REST'e sıfırlanır (eşik altında zaten ihmal edilebilir)
//
// NEDEN uyku eşiğinde gating kontrol edilmiyor:
//   Gating analitik olarak takip ediliyor (fixed_pow_int ile O(log n)).
//   Uyku sırasında gating "bedava" sönümleniyor. Voltaj ise difüzyon + sızıntı
//   etkileşimi nedeniyle analitik formülü karmaşık — onu iterate etmek lazım.
//   Bu yüzden uyku kararı SADECE voltaja bakıyor.
// ---------------------------------------------------------------------------

// Uyku eşiği: voltajın mutlak değeri bunun altına düşünce nöron uyuyabilir.
// 0.02 = eşiğin (1.0) %2'si — fiziksel olarak ihmal edilebilir.
constexpr fixed_t SLEEP_VOLTAGE_THRESH = fixed_from_double(0.02);

struct EventDrivenNeuron {
    DendriticNeuron core;           // alt nöron (aynı struct)
    int32_t         last_active_tick; // son hesaplama yapılan tick
    bool            awake;           // şu an uyanık mı
    int32_t         active_tick_count; // istatistik: kaç tick'te hesap yapıldı

    // Uyku anında gating'in snapshot'ı (uyanınca hızlı-ileri sarmak için)
    fixed_t sleep_gating[MAX_COMPARTMENTS];
};

// ---------------------------------------------------------------------------
// Başlatma — nöron UYUYOR başlar (tick 0'da olay yoksa hesap yapmaz)
// ---------------------------------------------------------------------------

inline void event_neuron_init(EventDrivenNeuron& en, int id) {
    neuron_init(en.core, id);
    en.last_active_tick  = 0;
    en.awake             = false;
    en.active_tick_count = 0;
    for (int i = 0; i < MAX_COMPARTMENTS; ++i) {
        en.sleep_gating[i] = 0;
    }
}

// ---------------------------------------------------------------------------
// Uyku koşulu: tüm kompartıman voltajları eşik altında mı?
// ---------------------------------------------------------------------------

inline bool event_neuron_can_sleep(const EventDrivenNeuron& en) {
    for (int i = 0; i < en.core.num_compartments; ++i) {
        fixed_t v = en.core.compartments[i].local_voltage;
        // Mutlak değer: negatif voltajlar da (reset sonrası) kontrol edilmeli
        fixed_t abs_v = (v < 0) ? -v : v;
        if (abs_v > SLEEP_VOLTAGE_THRESH) {
            return false;
        }
    }
    return true;
}

// ---------------------------------------------------------------------------
// Uykuya geçiş
//
// Gating snapshot'ını al, voltajları sıfırla (zaten eşik altında).
// ---------------------------------------------------------------------------

inline void event_neuron_enter_sleep(EventDrivenNeuron& en, int32_t tick) {
    en.awake = false;
    en.last_active_tick = tick;
    for (int i = 0; i < en.core.num_compartments; ++i) {
        en.sleep_gating[i] = en.core.compartments[i].gating_state;
        en.core.compartments[i].local_voltage = V_REST;
    }
    en.core.soma_voltage = V_REST;
}

// ---------------------------------------------------------------------------
// Uyanma — gating'i analitik hızlı-ileri sar
//
// Gating sönümü: gating(t+dt) = gating(t) × (1−decay)^dt
// fixed_pow_int ile O(log dt) çarpmada hesaplanır.
//
// Voltajlar: uyku anında zaten ~0 idi → V_REST olarak bırak.
// ---------------------------------------------------------------------------

inline void event_neuron_wake(EventDrivenNeuron& en, int32_t tick) {
    int32_t elapsed = tick - en.last_active_tick;
    if (elapsed > 0) {
        for (int i = 0; i < en.core.num_compartments; ++i) {
            Compartment& c = en.core.compartments[i];
            // retention = (1 − decay_rate) ^ elapsed
            fixed_t retention = fixed_pow_int(FIXED_ONE - c.gating_decay_rate,
                                               elapsed);
            c.gating_state = fixed_mul(en.sleep_gating[i], retention);
            if (c.gating_state < 0) c.gating_state = 0;
            // Voltaj zaten V_REST — dokunma
        }
    }
    en.awake = true;
}

#endif // EVENT_NEURON_H
