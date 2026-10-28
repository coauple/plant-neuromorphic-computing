#ifndef COMPARTMENT_H
#define COMPARTMENT_H

#include "fixed_point.h"

// ---------------------------------------------------------------------------
// Kompartıman sabitleri
//
// ARCHITECTURE.md §2.2'den: sabit boyutlu diziler, dinamik bellek yasak.
// Bu prototipte MAX_CHILDREN = 3, ama sadece 1 çocuk kullanacağız.
// ---------------------------------------------------------------------------

constexpr int MAX_CHILDREN_PER_COMPARTMENT = 3;

// ---------------------------------------------------------------------------
// Compartment yapısı
//
// Bir dendrit dalının tek bir bölmesi. local_voltage o bölmenin
// anlık membran potansiyelini, gating_state ise NMDA-benzeri
// "kısa vadeli hafıza" durumunu tutar.
//
// parent_id = -1 → bu kompartıman dendrit ağacının köküdür (somaya bağlı).
// child_ids[i] = -1 → o slot boş.
// ---------------------------------------------------------------------------

struct Compartment {
    fixed_t local_voltage;       // bu bölmenin membran potansiyeli
    fixed_t leak_rate;           // sızıntı katsayısı (0..1 arası, tick başına)
    fixed_t gating_state;        // NMDA-benzeri kısa vadeli hafıza (0..∞)
    fixed_t gating_decay_rate;   // gating sönümlenme hızı (= 1/tau, tick başına)

    int child_ids[MAX_CHILDREN_PER_COMPARTMENT];  // çocuk kompartıman indeksleri
    int num_children;
    int parent_id;               // ebeveyn kompartıman indeksi (-1 = kök)
};

// ---------------------------------------------------------------------------
// Kompartıman başlatma
//
// Tüm alanları güvenli varsayılan değerlere ayarlar.
// leak_rate ve gating_decay_rate çağıran tarafça üzerine yazılır.
// ---------------------------------------------------------------------------

inline void compartment_init(Compartment& c) {
    c.local_voltage    = V_REST;
    c.leak_rate        = 0;
    c.gating_state     = 0;
    c.gating_decay_rate = 0;
    c.num_children     = 0;
    c.parent_id        = -1;
    for (int i = 0; i < MAX_CHILDREN_PER_COMPARTMENT; ++i) {
        c.child_ids[i] = -1;
    }
}

// ---------------------------------------------------------------------------
// 1) Sızıntı (Leak)
//
// Biyolojik karşılık: iyon kanallarından pasif akım kaçışı.
// Voltaj her tick'te dinlenme potansiyeline doğru çekilir:
//
//   V_new = V - leak_rate × (V − V_REST)
//
// leak_rate = 0.05 ise, voltaj her tick'te farkın %5'i kadar azalır
// → yaklaşık 20 tick'lik zaman sabitiyle üstel sönüm.
// ---------------------------------------------------------------------------

inline void compartment_apply_leak(Compartment& c) {
    fixed_t delta = c.local_voltage - V_REST;       // dinlenmeden sapma
    fixed_t decay = fixed_mul(c.leak_rate, delta);   // bu tick'te kaybedilecek miktar
    c.local_voltage -= decay;
}

// ---------------------------------------------------------------------------
// 2) Difüzyon (Diffusion)
//
// Biyolojik karşılık: dendrit boyunca aksoplazmik akım akışı.
// İki komşu kompartıman arasında voltaj farkına orantılı akım akar:
//
//   V_this += diffusion_coeff × (V_neighbor − V_this)
//
// BU FONKSİYON TEK YÖNLÜ: sadece "this" kompartımanı günceller.
// Çağıran, karşı kompartıman için de simetrik çağrı yapmalı.
//
// NEDEN ayrı fonksiyon: saf (pure) fonksiyon olarak tutuyoruz —
// yan etkisi yok, sadece c'yi değiştiriyor. HLS sentezi için ideal.
//
// diffusion_coeff tipik olarak 0.1–0.3 arası; çok yüksek olursa
// iki kompartıman fiilen tek bir nokta gibi davranır (uzaysal ayrım kaybolur).
// ---------------------------------------------------------------------------

inline void compartment_apply_diffusion(Compartment& c,
                                         fixed_t neighbor_voltage,
                                         fixed_t diffusion_coeff) {
    fixed_t diff = neighbor_voltage - c.local_voltage;
    c.local_voltage += fixed_mul(diffusion_coeff, diff);
}

// ---------------------------------------------------------------------------
// 3) Gating State Güncellemesi
//
// Biyolojik karşılık: NMDA reseptörlerinin voltaja bağlı Mg²⁺ bloğunun
// kalkması. Voltaj yeterince yüksekse gating artar, değilse söner.
//
// Mekanik:
//   - Voltaj > GATING_ACTIVATE_THRESH ise:
//       gating += GATING_INCREMENT   (kapı açılıyor)
//   - Her tick'te:
//       gating -= gating_decay_rate × gating   (üstel sönüm)
//
// Sonuç: Tekrarlayan uyarım gating'i biriktirir → sonraki ateşleme
// daha kolay olur (kısa vadeli hafıza / fasilitasyon).
//
// gating_state hiçbir zaman negatif olmamalı — negatife düşerse 0'a çekiyoruz.
// ---------------------------------------------------------------------------

// Gating'in aktive olması için gereken minimum voltaj.
// 0.15: eşiğin (1.0) %15'i — root kompartımanın difüzyonla aldığı
// düşük voltajlarda bile gating birikmeye başlar. Önceki 0.5 değerinde
// root_gating çok az birikiyordu çünkü kök voltajı nadiren 0.5'i aşıyordu.
constexpr fixed_t GATING_ACTIVATE_THRESH = fixed_from_double(0.15);

// Her aktif tick'te gating'e eklenen miktar.
// 0.2: önceki 0.1'den daha agresif birikim — kısa uyaran
// pencerelerinde bile anlamlı gating oluşur.
constexpr fixed_t GATING_INCREMENT = fixed_from_double(0.2);

inline void compartment_update_gating(Compartment& c) {
    // Voltaj yeterli mi? Evet → gating artsın
    if (c.local_voltage > GATING_ACTIVATE_THRESH) {
        c.gating_state += GATING_INCREMENT;
    }

    // Üstel sönüm: gating -= decay_rate × gating
    fixed_t decay = fixed_mul(c.gating_decay_rate, c.gating_state);
    c.gating_state -= decay;

    // Negatife düşmeyi engelle
    if (c.gating_state < 0) {
        c.gating_state = 0;
    }
}

#endif // COMPARTMENT_H
