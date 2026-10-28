# Salep Sibernetiği — C++ SNN Çekirdeği: Mimari Yönerge

Bu doküman, bu projede C++ kodu yazacak bir kodlama ajanının (Claude Code veya
benzeri) her oturumda uyması gereken mimari kararları ve kısıtları tanımlar.
Amaç: bitki biyoelektrik sinyalini işleyen, ileride Zynq FPGA'ya (HLS üzerinden)
taşınacak bir Spiking Neural Network (SNN) çekirdeği — klasik nokta-nöron
modeli DEĞİL, çok bölmeli (multi-compartment) dendritik mimari.

## 0. Ajan için davranış kuralları

- **Asla doğrulanmamış sayısal iddiaları sabit kod olarak gömme.** Bu projenin
  geçmişinde "14 nöron popülasyonu 36 faz alanını sıfır hatayla okur" gibi
  iddialar, gerçek bir simülasyonla test edilmeden mimariye sabitlenmişti. Her
  "N nöron X doğrulukla Y'yi ayırt eder" türü iddia, kod yazılmadan önce küçük
  bir Python/NumPy Monte Carlo denemesiyle doğrulanmalı. Doğrulanmamışsa,
  kodda `// TODO: DOĞRULANMADI — bkz. deney X` yorumuyla işaretlenmeli.
- **Süslü/metaforik isimlendirmeden kaçın.** "Bilinç katmanı", "meta dil",
  "evrensel çevirmen" gibi isimler kod tabanına GİRMEZ. Bunun yerine teknik
  isimler kullan: `HostController` (CPU tarafı), `NeuromorphicCore` (FPGA/NPU
  tarafı), `PhaseEncoder`, `CompartmentTree` gibi.
- **Küçük, test edilebilir adımlarla ilerle.** Önce tek bir nöron + 2 dal,
  CSV çıktısıyla doğrula, sonra genişlet. Bkz. Bölüm 6.
- **DSL/compiler/code-generator yazma — henüz değil.** En az 3-4 farklı nöron
  tipi elle yazılıp çalıştırılmadan bir konfigürasyon dili veya kod üreteci
  tasarlanmayacak. Bkz. Bölüm 7.

## 1. Genel Mimari — Üç Katman

```
[Sensörler/Bitki sinyali]
        │
        ▼
┌───────────────────────────┐
│ Katman 1: Faz-Çözümleme    │  ← Frekans bandına duyarlı nöronlar (tau'ya göre ayarlı)
│ (Sensory / Phase Decode)   │     Her nöronun ≥2 dalı var:
│                            │       Dal A: ham/karışık sinyal hattı → rezonans filtresi (demux)
│                            │       Dal B: aynı olayın sensör-türevi spike kodlaması
│                            │     Soma: iki dalın zamansal çakışmasına göre ateşler
└───────────┬────────────────┘
            │ (spike + faz bilgisi)
            ▼
┌───────────────────────────┐
│ Katman 2: Rekabetçi        │  ← Yanal engelleme (lateral inhibition) + WTA
│ Kümeleme (WTA)             │     Aynı bant/faz bölgesindeki nöronlar birbirini
│                            │     güçlendirir, farklı bölgeler birbirini bastırır.
│                            │     AYRI bir "kümeleme algoritması" değil — saf
│                            │     nöron/sinaps dinamiği (STDP + lateral inhibition).
└───────────┬────────────────┘
            │ (kümeler arası çıktı)
            ▼
┌───────────────────────────┐
│ Katman 3: Çapraz-Bant       │  ← Convergence/birleşim nöronları. Dendritleri
│ Nedensellik (Convergence)  │     birden fazla Katman-2 kümesinden girdi alır.
│                            │     Eşzamanlılık (coincidence detection) ile
│                            │     "bunlar birlikte oluyor" ilişkisini kurar.
│                            │     NEDENSELLİK VE ÖNGÖRÜ BURADA — CPU'da değil.
└───────────┬────────────────┘
            │ (özet makro-durum)
            ▼
      [HostController / CPU]
      Sadece özet durumu okur, eşik/parametre günceller (top-down),
      spike'larla tek tek uğraşmaz.
```

**Kritik kural:** CPU asla ham sensör verisini "yorumlamaz" veya nöronlara
"bu budur" diye etiket fısıldamaz. Anlamlandırma ve nedensellik NPU'nun
(nöron/dendrit ağının) kendi dinamiğinden ortaya çıkar (emergence). CPU sadece
NPU'nun ürettiği özet çıktıyı okur ve parametre ayarı yapar.

## 2. Temel Veri Yapıları

### 2.1 Sabit Nokta Aritmetiği (ZORUNLU)

`float` / `double` çekirdek simülasyon döngüsünde YASAK (HLS/FPGA uyumluluğu
için). Şimdiden sabit nokta kullan:

```cpp
using fixed_t = int32_t;  // Q16.16 formatı: üst 16 bit tam sayı, alt 16 bit kesir
constexpr int FIXED_SHIFT = 16;
constexpr fixed_t FIXED_ONE = 1 << FIXED_SHIFT;

inline fixed_t fixed_mul(fixed_t a, fixed_t b) {
    return static_cast<fixed_t>((static_cast<int64_t>(a) * b) >> FIXED_SHIFT);
}
```

PC'deki geliştirme/doğrulama aşamasında bile bu tipi kullan — "önce float
yazıp sonra fixed-point'e çeviririz" YAPMA, baştan bu kısıtla geliştir (bkz.
önceki konuşmalarda kararlaştırılan 5 kısıt: sabit nokta, sabit boyutlu
diziler, saf fonksiyonlar, ring buffer olay kuyruğu, tick-sayaçlı zamanlama).

### 2.2 Dinamik Bellek YASAK

`std::vector`, `new`, `std::map`, `std::unique_ptr` çekirdek veri
yapılarında KULLANILMAZ (HLS dinamik heap tahsisini desteklemez). Sabit
boyutlu diziler kullan:

```cpp
constexpr int MAX_COMPARTMENTS_PER_BRANCH = 5;
constexpr int MAX_CHILDREN_PER_COMPARTMENT = 3;  // dallanma faktörü

struct Compartment {
    fixed_t local_voltage;
    fixed_t leak_rate;
    fixed_t gating_state;      // "genişleme durumu" — NMDA-benzeri kısa vadeli hafıza
    fixed_t gating_decay_tau;
    int child_ids[MAX_CHILDREN_PER_COMPARTMENT];  // -1 = boş
    int num_children;
    int parent_id;             // -1 = kök (somaya bağlı)
};
```

### 2.3 Sinaps (rezonans filtresi + kuadratik öğrenme)

```cpp
struct Synapse {
    fixed_t weight;             // sabit nokta ağırlık
    fixed_t tau_resonance;      // "kova deliği çapı" — hangi ritme duyarlı
    int32_t last_spike_time_ms; // son ateşleme zaman damgası
    int target_compartment_id;  // hangi kompartımana bağlı (konum = kimlik)
    int source_neuron_id;       // hangi nörondan geliyor (pointer/AER adresi)
};
```

Öğrenme kuralı (kuadratik, mevcut Python koddan miras): `dw = G * Q * S`
biçiminde, `exp()`/`log()` yerine önceden hesaplanmış LUT (Look-Up Table)
üzerinden. LUT'lar nöron içine GÖMÜLMEZ — ortak/paylaşımlı salt-okunur bir
tablo (`static const fixed_t LUT_WEIGHT_UPDATE[TABLE_SIZE]`) olarak dışarıda
durur, tüm nöronlar aynı tabloyu okur.

### 2.4 Nöron (soma + dendrit ağacı)

```cpp
struct DendriticNeuron {
    int neuron_id;
    fixed_t threshold;
    fixed_t soma_voltage;
    Compartment compartments[MAX_COMPARTMENTS_PER_BRANCH * MAX_BRANCHES];
    int num_compartments;
    int root_compartment_id;   // somaya en yakın kök
    int32_t last_fire_time_ms;
};
```

## 3. Katman 1 — Faz Çözümleme Nöronları (somutluk)

Her Katman-1 nöronunun en az 2 dalı vardır:
- **Dal A (faz/rezonans dalı):** Tek hattan gelen karışık frekans paketini
  alır. Kendi `tau_resonance` değerine uyan ritmi geçirir (rezonans),
  uymayanı sönümler.
- **Dal B (sensör-spike dalı):** Sensörden (CPU tarafında) faz koduna
  çevrilmiş spike dizisini alır — ham sayısal değer DEĞİL, zamanlanmış
  spike.
- **Soma:** İki dalın belirli bir zaman penceresi (`COINCIDENCE_WINDOW_MS`)
  içinde çakışıp çakışmadığına bakar; çakışırsa ateşler.

Dal sayısı ve dallanma derinliği başlangıçta 2 dal / 1-2 kompartıman ile
tutulmalı — genişletme, Katman-3 tasarımı netleşince yapılır.

**Rezonatör notu (PLIR, §9.8):** Dal A giriş kapısı iki kipte çalışır —
klasik ISI kapısı (ardışık-pencere TDM) ve opt-in PLIR (`plir_mode=1`):
ISI hafızası yalnız kabul edilen darbede güncellenir, yabancı darbe
reddedilir; böylece iki ritim aynı tele SÜPERPOZE binebilir (simültane
FDM). Bant başına küçük popülasyon (aynı tau, leak jitter'lı) + faz
histogramı ile kilit kalitesi ve giriş fazı ölçülür. Boş Dal B'nin kökü
emen bir yük gibi davrandığı (difüzyon sırası) Monte Carlo ikizinde
doğrulanmıştır — ölçüm toleransları `validate_fdm.py` D17/D13/D14'ten
gelir, gömülü varsayım yok.

## 4. Katman 2 — WTA / Yanal Engelleme (AYRI kümeleme algoritması YAZMA)

Önceki Python prototipindeki dict-tabanlı k-means kümeleme buraya
TAŞINMAYACAK. Bunun yerine:
- Aynı frekans bandındaki nöronlar arasında **yanal uyarıcı** bağlantılar.
- Farklı bandlardaki/kümelerdeki nöronlar arasında **yanal engelleyici**
  bağlantılar.
- Kazanan nöronun girdi sinapsları güçlenir (STDP/kuadratik kural), kaybeden
  zayıflar.

Bu, saf nöron/sinaps mekanizmasıyla, ayrı bir "kümeleme modülü" olmadan
gerçekleşir.

## 5. Katman 3 — Convergence / Nedensellik

Bu katmanın nöronları, Katman 2'den gelen birden fazla kümenin çıktısını
kendi dendrit dallarının farklı kollarına alır. Eşzamanlılık algılama
(coincidence detection — Bölüm 2.2'deki `gating_state` mekanizması) burada
"A kümesi ve B kümesi birlikte oluyor" ilişkisini kurar. Bu katmanın çıktısı,
CPU'ya giden özet makro-durumdur.

### 5.1 AFFERENT Kablo — Duyusal Lob → Nedensellik/Öngörü Sınırı (2026-09-09)

Birinci yarı (duyusal lob, FAZ3/FAZ4) donduruldu; ikinci yarı bu kabloyu
tüketir. Kablo proses-içidir (CSV boruhattı değil — CSV'ler çevrimdışı
kanıt olarak kalır).

- Olay yapısı `AfferentEvent{tick: int32, post_id: 0-63, tau_b: 4-60}`:
  `sensory_tick` çıktısı `SensoryTickResult{p1_fired, p2_fired[64],
  coinc[64]}` + banka tau listesinden üretilir. Her P2 ateşi bir olaydır.
- Saat alanı: iki lob aynı `t` sayacında koşar (tek tick döngüsü).
- Sahiplik: olayları lob üretir, adaptör (`causal_afferent.h`) tüketir;
  adaptör `sensory_lobe.h` ve `causality.h`'yi çağırır, ikisini de
  değiştirmez. Dal korunumu: P2-Dal A kaynaklı olaylar pre Dal A
  tarafına, P2-Dal B kaynaklı olaylar pre Dal B tarafına düşer.
- Öngörü çıkışı: hedef/coincidence durumundan "sonraki P2 kümesi"
  tahmini (tek adım); iskelet `predict.h`.
- Dosya öneki kuralı: yarı-1 `sensory_*`, yarı-2 `causal_*`/`predict_*`.
  Dizin taşınmaz (runner/plot yolları düz CORE_DIR varsayar).

## 6. Geliştirme/Doğrulama Akışı (Yol 1 — önce bu)

1. Tek bir `DendriticNeuron` + 2 kompartıman, tick döngüsü, çıktıyı CSV'ye
   yaz.
2. Python/matplotlib ile CSV'yi görselleştirip membran potansiyeli + spike
   zamanlarını doğrula.
3. Doğru çalıştığından emin olunca Katman 1'i (2-3 nöron) kur, aynı şekilde
   doğrula.
4. Ancak bundan sonra Qt arayüzü / pybind11 entegrasyonuna geç.

Derleme: `cmake` + `g++` (C++17), `-Wall -Wextra` açık, sanitizer'lar
(`-fsanitize=address,undefined`) geliştirme sırasında açık tutulmalı.

## 7. Ne zaman DSL/code-generator yazılır

En az 3-4 farklı nöron tipi (farklı `tau_resonance`, farklı dallanma yapısı)
elle yazılıp test edildikten SONRA, hangi alanların gerçekten tekrar eden/
parametrik olduğu netleşince bir YAML/JSON konfigürasyon şeması + üretici
script (Python) yazılabilir. Bu aşamadan önce YAZMA.

## 8. Terminoloji sözlüğü (kod ↔ konuşma karşılığı)

| Konuşmadaki isim              | Kod/teknik karşılığı                          |
|-------------------------------|------------------------------------------------|
| Akıllı musluk / kova deliği   | `tau_resonance` (rezonans zaman sabiti)         |
| Genişleme durumu / ısınma     | `gating_state` (NMDA-benzeri kısa vadeli hafıza)|
| Kimlik etiketi                | `source_neuron_id` + `target_compartment_id`    |
| Bilinç katmanı                | `HostController` (ARM/CPU tarafı)               |
| Alt beyin / refleks            | `NeuromorphicCore` (FPGA/NPU tarafı)            |
| Duyusal örüntü lobu            | Katman 1 (Phase Decode)                         |
| Anlamlandırma bloğu            | Katman 2 (WTA / Lateral Inhibition)             |
| Nedensellik/öngörü bloğu       | Katman 3 (Convergence)                          |
