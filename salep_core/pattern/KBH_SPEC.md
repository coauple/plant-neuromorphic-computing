# KBH — Kayıp Bütçesi Harcama (Dondurulmuş Plan, 2026-09-16)

**Statü: teşhis modu.** Çözüm SEÇİLMEZ, implemente EDİLMEZ. C++ değişikliği YOK.
`pl_core.py`, `pattern_lobe.h`, `pattern_unit_v2.h`, P0/P0b/P0c/T-AMP/IDEN
dosya+verileri **dokunulmaz ve donuk**. Taşıyıcı seçimi ve kazanan ilanı zorunlu değil.
`CMakeLists.txt` değişmiyor. Yeni C++ dosyası yok. Deterministik, sıfır RNG.

Soru: *"fan-in mi, K2/K3 masking mi, spike quantization mı — ne kadar?"*
Tavan analizi iki mimariyi ters kutuplara koyar (aynı matris, iki mimari):

```
legacy (pattern_lobe.h)     : 12/12 slot kapsama  ×  1 soma   → tavan = 1 temporal kanal
v2     (pattern_unit_v2.h)  :  6/12 slot kapsama  × 29 soma   → tavan = 6 paralel kanal
```

## Donuk manifest (8 dosya — Faz 0 K0e'de SHA256 before/after)

1. `src/pattern_lobe.h`
2. `src/pattern_unit_v2.h`
3. `pattern/pl_core.py`
4. `pattern/P0_SPEC.md`
5. `pattern/P0B_SPEC.md`
6. `pattern/P0C_SPEC.md`
7. `pattern/T_AMP_SPEC.md`
8. `pattern/IDEN_SPEC.md`

Ayrıca `pattern/p0_out/` ve `encoder/out/` altına YENİ dosya yazılamaz
(liste-snapshot ile denetlenir; kbh çıktıları `p0_out/kbh_*` ADIYLA YAZILIR —
bu dizin zaten çıktı dizinidir, istisna buradadır ve SPEC'te kilitlidir).

## Faz 0 — Sadakat kapısı (geçmezse KBH durur)

uj/us çift-sürüş kusurunu yakalayan kapının aynısı: enstrümante sürücü,
ablasyonlardan önce referansla eşleşmek zorunda.

| Kapı | Test | Ölçüt |
|---|---|---|
| K0a | enstrümante-legacy ⇄ `pl_core.run_condition` | `fire_ticks`, `n_coinc`, `max_soma`, `max_eff_g` bit-eşit |
| K0b | enstrümante-v2 ⇄ `pl_core.v2_drive` | `fires[29]` bit-eşit |
| K0c | enstrümante-v2 ⇄ `npu_pattern_unit_v2` | ateş kümeleri eşit (P3a–f canlı, P3g–ac sessiz); sayılar ±2 (fixed-kuantalama, belgeli) |
| K0d | enstrümante-legacy ⇄ `npu_pattern_lobe` | `OZET-PATTERN` (olay/k_atis/p3_atis/mem) ±2 |
| K0e | `frozen_before` ⇄ `frozen_after` | 8 dosya SHA256 aynı + p0_out/encoder-out yeni-dosya yok (kbh_* hariç) |
| K0f | determinizm | 2× koşu bit-eşit |

K0 probu: legacy `run_condition("ring", 0, 120, 210, 30)` (UAC emsali çift);
v2 K0b/K0c kablosu: `testb_afferent.csv` ilk 2000 tick (hız için kırpılmış,
SPEC'te kilitli — tam kablo değil, sadakat probu).

## Faz 1 — Tap haritası (ablasyonsuz, salt-ölçüm)

**Kilitli uyaran:** 8 darbeli tren, ISI=10 tick, horizon=200, amp ∈ {1.0, 4.0},
slot 0..11, iki dala aynı slot (üretim `main_pattern_lobe.cpp` aynası),
`w_ring`=0.2 (A1a değiştirir). v2: kablo-olayı olarak S5 kablolamasıyla 29 birim.
**48 koşu** = 12 slot × 2 amp × 2 mimari.

| Tap | İçerik | Ölçtüğü |
|---|---|---|
| T0 | enjekte edilen slot (indeks referansı) | zemin |
| T1 | K1 sürülen-kompartman V, g analog izleri | L0 |
| T2 | K1 ateş bitmap'i / dal | — |
| T3 | projeksiyon yükü (darbe sayısı, Σgenlik, varış tick vektörü) | L1 |
| T4 | P3/K spike-öncesi analog durum (V₀, g₀, eff_g) | L2 |
| T5 | soma spike treni (sayı, tick'ler, ISI'ler) | L3 |

**Metrik (kanal başına AYRI, birleştirilmez):**
- `N_sayı(T5)`: spike treninden ayırt edilebilen slot sayısı
- `N_magnitüd(T4)`: analog durumdan ayırt edilebilen slot sayısı
- `N_zaman(T5)`: tick/ISI örüntüsünden ayırt edilebilen slot sayısı
- `M_amp`: aynı φ'de amp 1.0 vs 4.0 iz-mesafesi (kimliği genlikle satın almadık kanıtı)

**Ayırt edilebilirlik:** ikili iz-mesafesi (L2 norm) > 1e-9 → ayrı; N = tam-ayrık
kümeleme ile farklı imza sayısı (deterministik twin, exact-eşitlik).
**Tavan:** `N_tavan = min(kapsanan_slot, aktif_soma)` → legacy 1, v2 6.
Hiçbir L0–L3 tavanı aşamaz → hüküm daima tavanla yazılır.

**Ön-kayıtlı bütçe:** `L_total = 12 − N(T5)`; `L0 = 12 − N(T1)`; `L1 = N(T1) − N(T3)`;
`L2 = N(T3) − N(T4)`; `L3 = N(T4) − N(T5)`. `L4 = 1 − P(coinc)` (doygunluk;
bağımsız, bütçeye katılmaz, koşullandırır). Zincir monotonik değilse
**"yaratıcı nonlineerlik"** etiketiyle ayrı raporlanır.
ε=2: mekanizma TEK BAŞINA YETERLİ sayılır ⟺ kapatılınca N(T5) ≥ 10/12.

## Faz 2 — Ablasyon merdiveni (OFAT → greedy, ~650 koşu)

| Eksen | Kapatır | Knob + aralık | Koşu hesabı |
|---|---|---|---|
| A0 | L0 | slot → varış gecikmesi δ(φ)=slot×d_step; d_step ∈ {0,1,2,3} (0=kontrol) | 4×12×2=96 |
| A1a | L1 | w_ring ∈ {0, 0.2, 0.4} | 3×12×2=72 |
| A1b | L1 | w_K1/w_K2K3 oranı ∈ {0.25, 0.5, 1, 2, 4} (oran 1=kontrol; ölçülen r/k'nin taraması) | 5×12×2=120 |
| A1c | L1 | readout ∈ {1, 12}; 1=soma-treni-tekil, 12=12-slot K1-ateş-bitmapi (T-AMP-A klonu) | 2×12×2=48 |
| A2 | L2+L4 | K2/K3 ∈ {off, blind, selective, asymmetric}; off=sessiz, blind=dal-geneli sürüş + SİMETRİK parametre (brB:=brA), selective=sadece-merkez-slot sürüş (öntanım parametre), asymmetric=dal-geneli + A≠B öntanım (üretim aynası); v2'de kablolama asimetrisi YOK — B-K1 yapısal kablosuz, bu sınır raporlanır. **A2 uyaran notu:** selective/off anlamlı ayrışsın diye A2 koşuları ÇİFT uyaranlıdır (tren slotu + (slot+6) distraktor, alterne 8+8 darbe); tap'ler tren-slotu kanalını izler | 4×12×2=96 |
| A3 | L3 | analog ∈ {0,1} × leak ∈ {0.02,0.06,0.10}; temsilci slotlar {1,4,7,5} (S5 merkezleri) | 2×3×4×2=48 |
| G | greedy | en iyi iki eksen birleşir | ~120 |

Toplam ≈ 600 + Faz 1 48 ≈ 650 koşu × 200 tick (twin'de ~1–2 dk).

## Faz 3 — Kilitli hüküm

```
pay(m) = L_m / L_total → düzeltilecek mekanizma = argmax pay(m)
m kapatılınca N(T5) ≥ 10/12 ise TEK BAŞINA YETERLİ; değilse greedy, katkı tablosu
L4 doygunken A1/A2/A3 KOŞULLU raporlanır ("dejenere rejimde ölçüldü")
Ayar yasağı (P0c emsali) · tek koşu · kazanan ilanı zorunlu değil
```

## Dosyalar (hepsi YENİ, pattern/ altında; C++ yok)

```
pattern/KBH_SPEC.md      ← bu dosya
pattern/kbh_taps.py      ← enstrümante sürücü (legacy + v2); pl_core IMPORT-only
pattern/kbh_run.py       ← Faz 0 → Faz 1 → Faz 2 (~650 koşu)
pattern/kbh_analyze.py   ← N kanalları, L0–L4, tavan, taşıyıcı tablosu
pattern/p0_out/kbh_fidelity.json, kbh_taps.csv, kbh_runs.csv, kbh_budget.json
pattern/p0_out/KBH_REPORT.md
```

## Ön-kayıtlı uyarılar

1. L0 ≈ 11/12 çıkabilir (12 K1 nöronu aynı parametre+amp → yapısal null); cevap
   "üç mekanizmadan biri" değil "önce A0" olabilir. Hipotezdir, test edilir.
2. A0 donanım-maliyetlidir (slot-başına gecikme elemanı); twin'de bedava, raporda maliyet satırı.
3. İki rejim ayrı raporlanır: tek-slot tren (IDEN6/K3-no-op rejimi) vs gerçek kablo
   (~0.028 olay/tick, K3-birikim rejimi).
4. N_distinct monotonik olmayabilir → kazanç etiketi, kayıp değil.
5. T-AMP yönü (ortak-kip yalıtımı vs sayaçsız zaman imzası) aynı metrikle yarışır; seçimi veri yapar.
