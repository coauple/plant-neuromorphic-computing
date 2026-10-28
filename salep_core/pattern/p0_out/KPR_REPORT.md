# KPR_REPORT — Aşama 1–4 Hükmü + Kapanış (2026-09-16)

Teşhis modu: çözüm seçilmedi, implemente edilmedi. C++ yok.
Faz 0: step-equiv OK · KBHP tái-üretim 7/12/0.0272 OK · determinizm OK ·
8-hash bekçisi OK (aşağıda). 36 kol + amp/imuls probu ≈ 450 sim.

## Sonuç (C0 vs F1 vs F1+sep vs TAM)

```
konfig   d0/d1  amp(0.25/0.5/1.0/2.0)  S_merkez  simetri  K3/K2
C0       7/12   7/7/7/1                0.197     0.444*   1.73
F1       11/12  11/11/11/11            0.195     1.000    1.65
F1sep    11/12  1/11/11/7              0.328     1.000    —
F1sepF4  11/12  7/11/11/11             0.382     1.000    —
F1sepF8  11/12  1/11/11/11             0.326     1.000    —
FULL     10/12  7/11/10/11             0.379     1.000    1.69
```
\* min/maks (6 komp); A_K1/B_K1 = 0.6141 → türetim BİREBİR doğrulandı.
İmpuls ağırlıklar: 0.0612, 0.0720, 0.0848, 0.0997, 0.1173, 0.1380
(adım-oran ~1.175 = 1/(1−D) — geometrik teori).

## Hükümler

- F1 (simetrik kök) d0'ı 7→11 kapatır, d1 12 kalır, amp-kırılması YOK
  (16× bandın tamamında ≥10), simetri 1.0. Aşama-1 hedefi TUTTU.
- F4 (K1 bağımsız referans) düşük-amp kırılganlığını onarır (0.25: 1→7);
  S_merkez 0.328→0.382.
- F8 (additive soma) tek başına düşük-amp'a dokunmaz (0.25: 1).
- FULL etkileşimi NEGATİF: d0 11→10 (kontrol genliğinde 1 kanal kaybı).
  **TAM ≠ en iyi; F1 tek başına en sağlam profil.**
- K2/K3 rol koruması: oran 1.73→1.65/1.69 (bant içinde, K3>K2 korunuyor) — GEÇTİ.
- parite=sep: S_merkez 0.195→0.328 (+13pp); N_sig d0'da değişmez (11).

## İddia defteri (güncel etiketler)

- ① sıra artefaktı: KANITLANDI (impuls geometrisi + F1 7→11).
- ② kapsama artefaktı: KANITLANDI (merkez %19.7–38, ortalama %2.7).
- ③ dışa-akı: KANITLANDI (negatif gradyan ölçüldü; sep +13pp).
- "K1 %2.7 → çok zayıf": KISMEN (merkezde %20–38).
- "F1 doğru düzeltme": KISMEN-GÜÇLÜ — sentetikte tuttu (11/12, kırılmaz,
  simetrik); gerçek-kablo TEST EDİLMEDİ (Aşama-dışı, onay bekler).
- Plan-aslî "TAM 11/12 + 0.25→11" iddiası: KISMEN ÇÜRÜTÜLDÜ (TAM d0=10,
  0.25→7). F4/F8 bileşimi kontrol-genliğinde kaybettiriyor.

## Sonrası (kapalı)

Gerçek-kablo doğrulaması + C++ geçişi AÇILMADI. DURULDU.

## EK — KPR3 tek-doğrulama (2026-09-16, E0 407-event, twin, C++ yok)

F1 aday-projeksiyonun sentetik kazancı gerçek kabloda test edildi (C0 kontrol):
distinct 19→39, jaccard 0.90→0.64, repeats 354→449, determinizm 2×.
Ön-kayıtlı kriter (distinct≥ VE jaccard≤): **GEÇTİ**.
Nihai mimari ilanı YOK; C++ v3 ayrı onaya bağlı. Prob: `/tmp/kpr3_validate.py`.

## EK2 — C++ v3 implementasyon (2026-09-16, ONAYLI)

`src/pattern_unit_v3.h` + `src/main_pattern_unit_v3.cpp` (YENİ; legacy donuk).
F1: snapshot kök (G_ROOT/6 uniform), D_CHILD aynı, soma F8'siz, eşik/reset aynı;
S5 kablolama + soma-as-post öğrenme portu v2 ile birebir (--eta 0/0.30).
Doğrulama: determinizm 2× bit-eşit; TEST-B eta0 mem=514 (v2: 950);
E0 eta0 v3 (45, 237, 0.40) vs v2 (40, 357, 0.56) — aynı-ölçek zincir içi
karşılaştırma (ikisi de weight×0.5); twin↔C++ ölçek farkı not edildi
(twin 1.0, zincir 0.5; F1 amp-bandında 11/12 sağlam). E0 eta.30: mem=849,
wkdev=0.2144, P3g–ac sessiz. Legacy V1–V8 OK, hash'ler aynı.
