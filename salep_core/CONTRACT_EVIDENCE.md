# Lob Sözleşmesi + Kanıt Haritası + Geçiş Kriteri (2026-09-16)

Deney yok; kapı-önü defteri. Her iddia etiketlidir:
KANITLANDI / KISMEN / HİPOTEZ / TEST EDİLMEDİ / GÖZLENMEDİ (test edildi, çıkmadı).

## A — Mimari sözleşme (Input → Transformation → Output → Responsibility)

### WORLD → Sensory
- Input: bitki + çevre durumu (dış sistem).
- Transformation: `sim/plant_sim.py` + `sim/electro.py` ile sinyal üretimi.
- Output: electrical iz.
- Responsibility: gerçekçi girdi üretmek (lob değil, zemin).
- Kanıt: `OZET-PLANT-VALID: M1..M5` (21 sim + 11 web GEÇTİ) — KANITLANDI.

### Sensory Lobe
- Input: electrical iz.
- Transformation: PLIR + P1 + P2 (faz çözümleme, seyreklik, sadakat kapıları).
- Output: signature + P2 spike'ları + `testb_*` kabloları.
- Responsibility: sıkıştırılmış ama sadık temsil.
- Kanıt: v1 baseline kilidi (§9.85, `V1_BASELINE.md` hash'leri) — KANITLANDI.

### Afferent / Encoder v0.1
- Input: P2 olayları (`tick,post_id,tau_b`).
- Transformation: `phi_id = post*3000`, `phi_tau = ((tau-4)*36000)//57` (tamsayı, SPEC v0.1).
- Output: afferent kablo (1 olay → 1 spike, kimlik korunur).
- Responsibility: kimlik-koruyan faz adresleme (12 slot).
- Kanıt: T1–T12, donduruldu — KANITLANDI.

### Pattern Lobe (v2 = deneysel yol; legacy = kontrol)
- Input: afferent kablo.
- Transformation:
  - WHAT → K1: merkez slot + halka ±1 (0.2x), birim-özgül merkez (S5).
  - WHEN → K2: dal-geneli slot-kör hızlı iz (leak 0.10).
  - HISTORY → K3: dal-geneli slot-kör yavaş iz (leak 0.02).
  - P3x soma: root × (1+gating+coinc-bonusu), 29 birim (P3a–f kablolu, P3g–ac sessiz kapasite).
  - Plasticity: soma-as-post, aynı kural/sayaç/eta; `--eta 0` frozen, `--eta 0.30` öğrenen.
- Output: Pattern Memory (`tick,unit,soma,eff_g,coinc,6×K-voltajı`).
- Responsibility: afferent akışı tekrar-kullanılabilir temporal/spatial temsil + korunum.
- Kanıt: legacy V1–V8; v2 V1–V8+M1+V8L; davranış deneyleri — aşağıda B.

### Inference (sonraki katman — girilmedi)
- Input (BUGÜN): sensory-repr pencereleri. Input (HEDEF): Pattern Memory kayıtları.
- Transformation (bugün): aptal nearest-sequence, k=3, öğrenme/parametre yok.
- Output: koşul etiketi (6x6 confusion).
- Responsibility: geçmişle eşleştirme.
- Kanıt: `OZET-INFER-1: I1 I2` (acc 0.554), K5 0.412, donduruldu — ancak SENSORY
  temsil üzerinden; Pattern Memory tüketimi TEST EDİLMEDİ.

### Causal / Prediction / Action (iskelet)
- Responsibility: nedensel okuma → öngörü → aksiyon. Afferent-düzeyi nedensellik
  kapıları mevcut (`validate_causality.py`, `validate_causal_afferent.py`) — KISMEN
  (afferent düzeyi). Pattern-sürümlü nedensellik/öngörü/aksiyon TEST EDİLMEDİ.

## B — Kanıt haritası (Pattern Lobe iddiaları)

| # | İddia | Etiket | Kanıt / not |
|---|-------|--------|-------------|
| B1 | v2 mimarisi kabloyu alır, kompartmanları işletir, ateş üretir | KANITLANDI | V1–V8-v2 + M1 OK |
| B2 | Öğrenme ağırlıkları değiştirir (wkdev>0) | KANITLANDI | V8L: wkdev=0.2607, deterministik |
| B3 | K1 yolu uyanık (farklılaşmaya katkısı var) | KISMEN | Birim-farklarının tek kaynağı K1-merkez (marj analizi); ateş-anı K-voltajı reset nedeniyle doğrudan izlenemedi |
| B4 | Temsiller arayla korunur (retention) | KISMEN | Sentetik A1==A2; ama frozen'da da aynı → sürüş-açıklamalı, plastisiteye atfedilemez |
| B5 | Yeni örüntü eskiyi bozmaz (enterferans-direnci) | KISMEN | B sonrası A2==A1 (küçük-n: A2 4 episod) |
| B6 | Varyantlar ortak çekirdek + ayrık marj üretir (transfer) | KISMEN | Düşük-şiddette çekirdek {P3a} + farklı dominantlar; paylar düşük (0.28–0.42) |
| B7 | Yeni stabil ara temsil C üretilir (emergans) | GÖZLENMEDİ | AB stabil ama A ile aynı / yenilik boş-küme (iki şiddet ucunda da) |
| B8 | 29 kapasitenin fazlası sessiz kalır | KANITLANDI | P3g–ac ateş 0 + ağırlık sapması 0 (tüm koşular) |
| B9 | Öğrenme faydalı organizasyon üretir | HİPOTEZ | Tekrar güçlenmesi var (altılı 61→78x) ama transfer/emergans yok; iddia düzeyi |
| B10 | Memory, Inference'in kullanabileceği formda korunur | GÖZLENMEDİ | Şema stabil + belgeli; tüketim denendi: 0.310/0.356 vs 0.554 (C-sonucu). frozen > öğrenen |
| B11 | K1 faz bilgisi soma/spike'a taşınır (forensik) | KISMEN | [1] temiz (DK1 0.64/0.78); [2] seyrelir (r/k ~0.09–0.16, yelpaze-seyreltme); [3] zayıf-K1 maskelenir (C-zayıf≡B), güçlü-K1 marjinal geçer (+1 spike); [4] aktif (B faz-kör ateşler). K1 tek-başına ateşletemez — modülatör, K2/K3 izin-verici |

## C — Sonraki katmana geçiş kriteri

"Pattern tamam" ≠ "29 nöron çalışıyor". Tanım:

> Pattern Lobe, afferent spike stream'i tekrar kullanılabilir temporal/spatial
> representations'a dönüştürüyor (a) ve Memory bu representations'ları sonraki
> Inference katmanının kullanabileceği şekilde koruyor (b).

Alt-kriter durumu:

- (a1) Dönüşüm çalışıyor (kablo → P3x ateş örüntüleri): KANITLANDI (B1).
- (a2) Dönüşüm plastisiteye açık (ağırlık dinamiği): KANITLANDI (B2, V8L).
- (a3) Dönüşüm farklılaştırıyor (birimler ayrışıyor): KISMEN (B3, B6-zayıf).
- (b1) Memory şeması stabil + belgeli: KANITLANDI (v2 mem şeması, V4-v2).
- (b2) Temsil aralıkta korunuyor: KISMEN (B4).
- (b3) Memory Inference tarafından tüketiliyor: TEST EDİLDİ, sonuç C (2026-09-16,
  `validate_infer_pattern.py`): öğrenen 0.310 (n=174), frozen 0.356 (n=174),
  sensory-ref 0.554 (n=175). Deterministik + sızıntısız kapılar OK.

Karar: Pattern kapısı (a1,a2,b1) ile geçilir; (a3,b2) kısmi-borç olarak taşınır;
(b3) Inference katmanının İLK deneyi olur (öneri: dondurulmuş k=3 nearest-sequence
yöntemi v2 mem kayıtlarına aynen uygulanır, skor sensory baseline 0.554 ile
karşılaştırılır — koşulmadı, onay bekler). B7/B9 mimari borç olarak kayda geçti;
Pattern içinde daha fazla pattern-avı AÇILMAZ.
