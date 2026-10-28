# KBHP v2.1 — Dondurulmuş Uygulama Sözleşmesi (2026-09-16)

**Statü: teşhis modu.** Çözüm SEÇİLMEZ, implemente EDİLMEZ. C++ değişikliği YOK.
`neuron.h` (satır 518/524 legacy eff_g dahil), `pattern_unit_v2.h`,
`pattern_lobe.h`, `pl_core.py` (import-only), P0/P0b/P0c/T-AMP/IDEN dosya+veri
**dokunulmaz**. `CMakeLists.txt` açılmaz, yeni C++ dosyası YOK. Deterministik,
sıfır RNG. Yeni `frozen` ilan YOK (Faz 0 SHA bir bekçi, kilit değil).

Soru: *"K1'in bilgisi somaya nasıl ve neyle taşınıyor?"*

## Dokunulmazlar + G-A bekçisi

Faz 0 SHA256 (K0e listesi): `src/pattern_lobe.h`, `src/pattern_unit_v2.h`,
`pattern/pl_core.py`, `pattern/P0_SPEC.md`, `pattern/P0B_SPEC.md`,
`pattern/P0C_SPEC.md`, `pattern/T_AMP_SPEC.md`, `pattern/IDEN_SPEC.md`.

## Uyaran (ön-kayıtlı, sentetik — kablo koşusu yok)

- tek-slot: 8 darbe · ISI=10 · t0=5 · H=160 · slot s=0..11 · amp 1.0 (kilitli;
  genlik-konfounder yapısal dışlanır) · birim merkezi c=4 (S5 P3b; tüm birimler
  aynı kablolamayla koşar, tap'ler birim-başına ayrışır).
- iki-slot: `p0_out/kbp_pairs.json` 6 D-A çifti (X→A-dalı, Y→B-dalı), aynı tren.
- A0: darbe varışı `t + slot × d_step`.

## Dört eksen (kilitli operasyonel tanımlar)

| Eksen | Seviyeler | Ölçtüğü |
|---|---|---|
| `okuma` (3) | `R0` = g[0] (mevcut eff_g) · `R1` = g[0]+Σg[A-K1..A-K3] · `R2` = g[0]+Σg[6K] — yerel step'te yaşar, legacy formüle dokunulmaz | ① K1→soma okuma |
| `parite` (2) | `id` = iki dal sürülür (olay-başına 5 komp: A-K1+A-K2+A-K3+B-K2+B-K3; B-K1 yapısal kablosuz) · `sep` = yalnız A-dalı sürülür (3 komp: A-K1+A-K2+A-K3; B sessiz) — dal-parite katkısını izole eder | ② dal-paritesi |
| `zaman` (5) | `d_step ∈ {0,1,2,4,6}` (`0` = kapalı) | ④ temporal ayrışma |
| `topoloji` (2) | `T0` mevcut S5 kablolama · `T1` D-A çift-kablolama = test çifti (X,Y) için sahip birimin K1A-merkezi X, K2/K3'leri {X,Y}-seçici (dal-geneli yerine); 나머지 S5 aynen | ③ çift-seçicilik |
| `coinc` (2) | doğal · SABİT-açık (yerel step bonusu hep ekler; bonus confound'unu izole eder) | kontrol |
| `legacy` (2) | v2 (7 komp) · legacy (3 komp, twin-yerel okuma kolu; kaynak dosyaya dokunmadan) | karşılaştırma |

## Metrikler (iki katmanlı)

| Metrik | Katman | Tanım |
|---|---|---|
| `N_sig / 12` | tek-slot | okuma-düzeyine göre 12 slotun ayrı imza sayısı. İmza: R0=(g0-izi, soma-treni); R1=+A-K V-izleri; R2=+6K V-izleri (yuvarlama 1e-9, tam-ayrık kümeleme) |
| `N_pair / 6` | iki-slot | çift imzası = popülasyon-vektör demeti (6 birim atış sayıları + dominant vektör). Çift `p` seçici ⟺ imzası diğer 5 çiftinkinden farklı VE sahip-birimler (merkezi X veya Y olan kablolu birimler) dominant. N_pair = seçici çift / 6 |
| `N_pv` | popülasyon | koşudaki ayrı 6-bit birim-ateş vektörü sayısı (sıfır-dışı tickler) |
| `L4 = P(coinc)` | tüm | coinc-doğru tick oranı (v2: kablolu birim ortalaması) |
| `S_share` | teşhis | K1'in kök sürüş payı, mimariye-göre işlemsel: v2 = koşu-içi birikimli Σpozitif-sızıntı(A-K1→root) / Σpozitif-sızıntı(tüm-K→root), I=DIFF×(snap_K−snap_root); legacy = P3'e K1-kaynaklı enjeksiyon / tüm-K enjeksiyonu (ateş sayaçları). Farklı formüller, aynı soru; yan yana, birleştirilmez |

## Ön-kayıtlı kapılar

- G-A SADAKAT: yerel step === `pl_core.p3x_tick` (reset dahil, bit-eşit) VE
  R0·id·d0 kolu kabloda `v2_drive`'ı yeniden üretir (ateş kümeleri eşit, sayı ±2).
- G-B TAŞINMA: ∃ kol `N_sig ≥ 10/12` → "K1 soma'ya taşınıyor".
- G-C SEÇİCİLİK: D-A çift kolu `N_pair ≥ 5/6` → "çift seçiciliği var".
- G-D NEGATİF: kazanan kol genlikle elde edilemez. KBHP'nin kendi kontrolü:
  tüm kollar amp=1.0 kilitli → genlik-konfounder yapısal dışlanır. (16× iddiası
  plan-aslî iddia-defterindedir; KBHP matrisinde genlik ekseni YOKTUR —
  bkz. iddia defteri notu.)
- HÜKÜM: hangi eksen GEREKLİ / YETERLİ; `okuma` (①) `zaman` (④) üstüne EK katkı
  veriyor mu — veri söyler, ilan edilmez.

## Koşu sayısı (≈57 v2-matrisi + 18 legacy-karşılaştırma)

`okuma(3) × parite(2) × zaman(5)` = 30 · `coinc-sabit` yalnız `parite=sep`
kollarında +15 · `topoloji(2) × okuma(3) × coinc(2)` iki-slot +12 = **57**.
Legacy karşılaştırma 2 kol (12+6 sim). Toplam ~630 sim (twin; KBH ölçeği).
`kbp_axes.csv` = 59 kol-satırı (57 v2 + 2 legacy).
`kbp_run.py` kolları SPEC'ten enumerate eder, `kbp_manifest.json`'a tam koşu
listesi + SHA256 yazar.

## Dosyalar

```
pattern/KBHP_SPEC.md, kbp_drive.py, kbp_run.py, kbp_analyze.py
p0_out/kbp_fidelity.json, kbp_pairs.json, kbp_axes.csv, kbp_manifest.json,
p0_out/KBHP_REPORT.md (iddia defteriyle + kapanış belgesi)
```

## İddia Defteri şablonu (rapor aynen girer; etiket + KBHP notu)

G-A..G-D hükümleri + "okuma katkısı var/yok" + legacy kolu yan yana.
Sonrası: rapor yazılır, tablo basılır, DURULUR. Mimari fazı, S6 tablosu,
B-K1 alan kararı AÇILMAZ.
