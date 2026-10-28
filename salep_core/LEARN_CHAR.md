# REV-LEARN Karakterizasyon (A/B/C/D) — dondurulmuş gözlem

Kod değişikliği YOK. Tek sinaps + kontrollü oran çiftleri, gerçek
`synapse_apply_learning`, eta=0.30. Ham eğriler: `/tmp/learnchar/`
(`A_*_early.csv`, `B_sleep.csv`), problar `/tmp/learn_char*.cpp` (throwaway).

Mekanizma (kaynak: `src/synapse.h:227-240`):
- Potansiyasyonda `w += dw·(1+T)`, `T += MU·(1−T)` — iz yalnızca büyür, asla sönmez.
- Kullanım-dışında `w −= LAM·(w − T·WMAX)` — tabana **iki yönlü** gevşeme (zayıflama var, sıfıra unutma yok).
- Yarılanma ömrü ln2/0.005 ≈ 139 tick.

## A — Öğrenme (güçlü 30,30 vs zayıf 8,8)

| | güçlü | zayıf |
|---|---|---|
| ilk-tick dw | 0.9000 | 0.0171 (≈53x fark — kuadratik avantaj + G) |
| doygunluğa (2.0) tick | 2 | 76 |
| doygunlukta T | 0.2344 | 0.9999 |

`T = 1−(1−MU)^n` tam doğrulanıyor (2 tick → 0.234375; 76 tick → ~1).
**Bulgu:** iz derinliğini maruziyet SAYISI belirler — hızlı öğrenme sığ iz,
tekrarlı/uzun öğrenme derin iz bırakır.

## B — Uyku (öğren → 3000 tick (0,0))

- Zayıf-öğrenilmiş (w=1.50, T=0.947, taban=1.894): w **yükselerek** 1.894'e
  asimtot (~1200 tickte), T bit-identical sabit. Taban alttan da çekiyor (L235).
- Güçlü-doygun (w=2.0, T=0.234, taban=0.469): w 20000 tickte 0.4718'e iner =
  taban. T sabit. Sığ izin bedeli: düşük taban.
- Sonuç: `w → T·WMAX` her iki yönden; `T` uykuda değişmez.

## C — Yeniden karşılaşma (22t zayıf-öğren → gap → 1.99'a dönüş yarışı)

Saf (init 1.0 → 1.99): **91 tick**.

| gap | gap-sonu w | T | yeniden tick | tasarruf |
|---|---|---|---|---|
| 100 | 1.657 | sabit | 61 | 1.5x |
| 1000 | 1.893 | sabit | 37 | 2.5x |
| 10000 | 1.894 | sabit | 37 | 2.5x |

1000 vs 10000 **bit-identical (37=37)** — tasarruf boşluk uzunluğundan bağımsız,
yani artık-w'dan değil kalıcı izden geliyor. İki mekanizma: tabandan başlama +
`(1+T)` hızlandırmalı yeniden-güç (L230).

## D — Uzun süreli hafıza (22t öğren → 20000 uyku → A tekrar)

- T gap-öncesi/sonrası **bit-equal** (iz bütün).
- w tabanda park etmiş: 1.8939 = T·WMAX (öğrenme-sonu 1.50'nin ÜSTÜNDE).
- 30 tick yeniden-maruziyet: 1.98 vs saf-30-tick 1.64.

## Hüküm cümlesi — kurulabilir

"Pattern Lobe korelasyonları yalnızca güçlendirmiyor; onları kalıcı bir iz (T,
20000 tick boyunca bit-identical) olarak saklıyor, aktif bağlantı gücünü zaman
içinde bu ize göre düzenliyor (w→T·WMAX, τ≈140 tick, iki yönlü) ve gerektiğinde
yeniden erişilebilir hale getiriyor (boşluktan bağımsız ~2.5x tasarruf)."

Dürüst sınırlar: tasarruf sayısı zayıf rejimde ölçüldü (güçlü-A ~2 tickte
doyuyor, sayım anlamsız); B'de taban-üstü-sıçrama (1.50→1.89) kuralın çift
yönlü olduğunun kanıtı, anomali değil; doygun-LSB kör-bandı ayrı TODO.
