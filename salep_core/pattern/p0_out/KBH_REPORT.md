# KBH_REPORT — Kilitli Hüküm (2026-09-16, teşhis modu)

Soru: *fan-in mi, K2/K3 masking mi, spike quantization mı — ne kadar?*
Cevap: kayıp bütçesi tablosuyla. Çözüm seçilmedi, implemente edilmedi,
kazanan ilan edilmedi. C++ değişikliği yok.

## Faz 0 — Sadakat: HEPSİ OK

K0a, K0a2, K0b (`_ptick` bit-eşit dahil), K0c (küme eşit, sayı ±2),
K0d (binary `[40,0,9,12,6,6]` vs enstrümante `[40,0,9,12,5,5]`), K0f, K0e.
Kanıt: `p0_out/kbh_fidelity.json`.

## Faz 1 — Tap haritası (kontrol knob'ları, 48 sim)

```
mimari   tavan  N_T1  N_T3  N_T4  N_T5  N_zaman  L_total = 12−N(T5)
legacy     1      1     1     1     1      1        11
v2         6      3     1     3     3      3         9
```

- legacy: L0 = 11/11 (%100). 12 K1 nöronu aynı parametre + eşzamanlı giriş →
  T1'de zaten 1 kanal (yapısal null, ön-kayıtlı uyarı §1 doğrulandı).
- v2: L0 = 9/9 (%100); L1 = +2, **L2 = −2 → yaratıcı nonlineerlik** (projeksiyon
  yükü tekdüze iken soma-analog ıraksıyor: K-dinamikleri + coincidence kazanç
  üretiyor, kayıp değil). L3 = 0.
- M_amp (genlik-konfounder): legacy 6.83, v2 1.32 → v2 genliğe daha değişmez;
  legacy'de kimlik genlikle daha çok satın alınıyor.
- L4 doygunluk: legacy 0.78, v2 0.60 → A1/A2/A3 legacy-düzlükleri KOŞULLU
  ("dejenere rejimde ölçüldü").

## Faz 2 — Ablasyon merdiveni (OFAT)

```
eksen  legacy              v2
A0     1 → 12 (d≥1)        3 → 12 (d≥1)
A1a    1,1,1               2,3,3
A1b    1,1,1,1,1           2,2,3,3,3
A2     1,1,1,1             1,1,1,2(selective)
A1c    r1=1 r12=1          r1=3 r12=11
A3     1,1,0*              3/4,3/4,0*  (*leak .10 = dejenere, 0 ates)
```

- **A0 tek başına yeterli (ε=2: N≥10/12):** iki mimaride de d_step≥1 → 12/12.
- A1c v2'de 3→11 (full-readout kazancı); legacy'de 12-kanal bitmap bile 1
  (yapısal null: iki dal özdeş + tüm K1'ler özdeş).
- A2 legacy'de tamamen düz (K2/K3 oynamak hiçbir şeyi değiştirmiyor —
  doygun rejim); v2 selective=2 (merkez-eşleşme +1 kanal).
- A3 leak=.10 iki mimaride de öldürür (0 ateş — koşullu rapor).

## Greedy (A0 × readout, 48 sim)

d_step ∈ {1,2} × readout ∈ {1,12} × 2 mimari → **12/12 her hücrede**.
A0 + tam okuma her şeyi kapatır.

## Faz 3 — Hüküm (kilitli kural)

- `pay(L0)`: legacy %100, v2 %100 → **düzeltilecek mekanizma = L0
  (eşzamanlı varış)**. A0 kapatınca N(T5) ≥ 10/12 → **TEK BAŞINA YETERLİ**.
- Tavanla birlikte: legacy N_seq=12 ama paralel tavan 1 (zaman-çoğullamalı);
  v2 N_seq=11, 6 paralel kanal (S5: {2,3,8,9,10,11} ulaşılamaz — tavan bildirimi).
- Donanım maliyeti: A0 slot-başına fiziksel gecikme ister (twin'de bedava).
- T-AMP rekabeti: ortak-kip yalıtımı (A-yönü) A0'da, sayaçsız zaman imzası
  (B-yönü) N_zaman'da — ikisi de aynı metrikte kazandı (A0 kapatınca);
  seçim veriye bırakıldı, ilan edilmedi.
- Rejim ayrımı: yukarıdaki tüm sayılar tek-slot tren rejimidir; gerçek-kablo
  rejimi (~0.028 olay/tick) ayrı rapordur (bu KBH'nin dışı).

## Dosyalar

`pattern/KBH_SPEC.md`, `pattern/kbh_taps.py`, `pattern/kbh_run.py`,
`pattern/kbh_analyze.py`, `pattern/p0_out/kbh_fidelity.json`,
`kbh_taps.csv`, `kbh_traces.json`, `kbh_runs.csv`, `kbh_budget.json`,
`pattern/p0_out/KBH_REPORT.md` (bu dosya).
