# STIMULUS SNR SPEC — uyaran merdiveni + aile kimligi (ON-KAYIT)

Soru: zincir hangi siddetteki kurakligi kablo->lob->eff_g hattinda tasir?
Kapsam: A0 formalizasyon, A1 kanonik aile, A2 siddet merdiveni.
DEGISTIRILMEZ: src/, sim/, kanonik CSV/PNG, encoder, sensory, v3d C++.
Yeni (additive): weather_v3/W-dry.csv (+W-s1/W-s2), bu spec, 4 script,
stress_out_snr/ cikti. A3 KAPALI (ayri onay).

## Topluluk (hepsi icin gecerli)
- Tohumlar {42,43,44,101,102} (hepsi onceden olculmus; kiraz-yok).
- gun=130, plant cond=10/test=3, eta=0.30, v3d binary, deterministik.
- A0: {base, dry-old, dry-new} x 5 (merdiven; dry-old = bayrakli [60,60)
  BOS referans, REV3 gecerisiz-uyaran).
- A1: {base, dry(W-dry), irrig20, hot(W-hot), fert30} x 5 (A0'dan
  base+dry-new reuse; deterministik aynilik).
- A2: S0=base, S1=yagmur[20,21,50]+0C, S2=yagmur[20,21]+3C, S3=W-dry
  x 5 (S0/S3 A0-A1'den reuse). Basamaklar SONUCA BAKILMADAN sabit;
  hepsi raporlanir (esik-oynama yok).

## 7 ozellik (senaryo x tohum; sensor = sensors.csv gun-ortalamasi)
ec_mean, tn_mean, ch0_n, ch1_bdays (ch1 atesli gun sayisi), cable_n,
lob_n (mem satiri), effD (distinct eff_g).
SNR_f(X) = |ort_X - ort_base| / std_X (tohumlar arasi; std=0+fark!=0
=> +inf, gecerli olcum; std=0+fark=0 => 0).

## Kapilar
- G-SNR0: cable_n SNR >= 10. G-SNR1: lob_n SNR >= 10.
- G-SNR2: withinJ - betweenJ > 0 (eff_g gun-imzalari).
- G-ABL: NOPOS (post_id:=mod, tick/tau aynen) ve NOCNT (tick-basi ilk
  olay; sayi silinir) ablasyonlari; beklenti = aile coker (rapor;
  cokmezse bulgu). V0: ablasyon-kapali tekrar == kanonik mem sha
  (bit-esitlik kontrolu, KAPI).
- G-FAM: eff_g 5-sinif LOO >= 0.90 (sans 0.20); W-dry->base karisma
  <= %5 (KAPI).
- G-DOSE: doz = hava-yagmur-toplami + sulama-toplami (mm); gorece fark
  <= %2 eslesen ciftlerde aile-uyumu; >=1 cift varsa KAPI (>=0.90),
  yoksa n/a-rapor.
- G-BIN: uc kova yan-yana (B1 [1.5,2.5,3.5]; B2 havuz-ceyrekler;
  B3 esit-genislik 4) — fam her kovada rapor, kapi YOK.
- non-separable: B>=N cikan readout isaretlenir, kazanan-disi birakilir.

## A1 hedef (on-kayitli)
eff_g >= 0.90 (5 sinif); beklenti (tek-atis): 4-sinif 0.982, W-dry 0.994.
## A2 cikti
SNR(siddet) + eff_g-aile(siddet) egrisi (S0..S3); transfer fonksiyonu.
## REV3 (PATTERN_V3_STRESS_SPEC'e eklenecek)
G1-drought (bayrakli) GECERSIZ UYARAN (base ile ayni yasam seyri +
kablo 76=76). SILINMEZ; isaretlenir.
