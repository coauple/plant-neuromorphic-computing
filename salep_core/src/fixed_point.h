#ifndef FIXED_POINT_H
#define FIXED_POINT_H

#include <cstdint>

// ---------------------------------------------------------------------------
// Q16.16 sabit nokta aritmetiği
//
// Üst 16 bit: tam sayı kısmı (işaretli → aralık yaklaşık ±32 767)
// Alt  16 bit: kesir kısmı   (çözünürlük ≈ 1.5e-5)
//
// NEDEN: ARCHITECTURE.md §2.1 — FPGA/HLS float desteklemez.
//        PC'deki prototipi de aynı kısıtla geliştiriyoruz ki
//        ileride "float→fixed taşıma" sorunu yaşanmasın.
// ---------------------------------------------------------------------------

using fixed_t = int32_t;

constexpr int     FIXED_SHIFT = 16;
constexpr fixed_t FIXED_ONE   = 1 << FIXED_SHIFT;          // 1.0  = 0x0001_0000
constexpr fixed_t FIXED_HALF  = FIXED_ONE >> 1;             // 0.5  = 0x0000_8000

// --- Dönüşüm yardımcıları ---------------------------------------------------

// Tam sayıdan fixed'e: fixed_from_int(3) → 3.0
inline constexpr fixed_t fixed_from_int(int v) {
    return static_cast<fixed_t>(v) << FIXED_SHIFT;
}

// Ondalıklı sabiti derleme zamanında fixed'e çevir.
// Çalışma zamanında KULLANILMAZ — sadece sabit tanımlamak için.
inline constexpr fixed_t fixed_from_double(double v) {
    return static_cast<fixed_t>(v * (1 << FIXED_SHIFT));
}

// fixed'den float'a — YALNIZCA CSV/debug çıktısında kullan.
// Simülasyon döngüsünde ÇAĞIRMA.
inline float fixed_to_float(fixed_t v) {
    return static_cast<float>(v) / static_cast<float>(FIXED_ONE);
}

// --- Aritmetik işlemler (overflow-safe çarpma) -------------------------------

// Çarpma: (a * b) >> 16.
// Ara sonucu 64 bite genişletiyoruz — 32×32 çarpma 32 bite sığmaz.
inline fixed_t fixed_mul(fixed_t a, fixed_t b) {
    return static_cast<fixed_t>((static_cast<int64_t>(a) * b) >> FIXED_SHIFT);
}

// Bölme: (a << 16) / b.
// Böleni sıfır kontrolü yok — çağıran sorumluluk taşır.
inline fixed_t fixed_div(fixed_t a, fixed_t b) {
    return static_cast<fixed_t>((static_cast<int64_t>(a) << FIXED_SHIFT) / b);
}

// Tamsayı üs alma: base^exp (base sabit nokta, exp tam sayı).
// Tekrarlı kare alma (repeated squaring) ile O(log exp) çarpmada hesaplar.
// Kullanım: gating sönüm hızlı-ileri sarma — (1−decay)^elapsed_ticks.
// base < FIXED_ONE ise sonuç üstel sönüm, base > FIXED_ONE ise üstel büyüme.
inline fixed_t fixed_pow_int(fixed_t base, int exp) {
    fixed_t result = FIXED_ONE;
    while (exp > 0) {
        if (exp & 1) {
            result = fixed_mul(result, base);
        }
        base = fixed_mul(base, base);
        exp >>= 1;
    }
    return result;
}

// --- Sıkça kullanılan sabitler -----------------------------------------------

// Nöron dinlenme potansiyeli: 0 = dinlenme sözleşmesi.
// Gerçek biyolojik −70 mV'u normalize edip 0 kabul ediyoruz;
// eşik ve sıfırlama değerleri buna göre göreceli.
constexpr fixed_t V_REST  = 0;

// Ateşleme eşiği — dinlenmeye göre +1.0 birim.
constexpr fixed_t V_THRESHOLD = FIXED_ONE;  // 1.0

// Ateşleme sonrası sıfırlama — dinlenmenin biraz altı (−0.2).
constexpr fixed_t V_RESET = fixed_from_double(-0.2);

#endif // FIXED_POINT_H
