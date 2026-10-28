# PATTERN MEMORY USE SPEC — Asama A (ON-KAYIT)

Soru: eff_g-bilgisini okuyan readout fam_qd >= 0.40'a ulasir mi?
Cekirdek/frozen/encoder/sensory/C++ DEGISTIRILMEZ. Salt-okunur mem.
Yeni: pattern/memory_readouts.py + phase1_memory.py (additive).
readout_v3d.py + phase0_margin.py DEGISTIRILMEZ (sha kilitli).

## Dogrulanmis zemin (2026-09-16, 36 case)
- Dolu 34 case'de soma/coinc/aK1/aK2/aK3/bK1/bK2/bK3 SABIT (tek deger);
  2 istisna = BOS cold mem'ler. Sebep: mem ates-sonrasi yaziliyor
  (main_pattern_unit_v3d.cpp tick-sonrasi kayit; voltajlar V_RESET'li).
- eff_g TEK bilgi tasiyici (16684 distinct, 0.397-4.887).
- phi-join olu (ateslerin %2-4'u); kapida KULLANILMAZ.

## Readout ailesi (gun -> frozenset(token); mevcut S0..S3 + yeni)
- E1: (birim, effbin); effbin = o gun birimin ORTALAMA eff_g'si,
  kenar [0,1.5,2.5,3.5,inf) -> 0..3; ateslemeyen birim YOK.
- E2: gun-ozu: tum-gun ortalama eff_g'nin bini, tekil token
  {("MEAN", bin)} + E1 birlesimi? HAYIR — E2 = YALNIZ {("MEAN", bin)}
  (tek ozet; dejenerelik gozlemlenir, raporlanir).
- X1: S3 birlesim E1 (token-birlesimi).
- X2: iki-asamali: asama-1 S3 ile en-iyi-3 aday; asama-2 E1 benzerligi
  ile secim (k=3 on-kayitli).
- S0n sahteleme: tum readoutlar icin DEGIL, yalniz kazanan + S0 icin
  rapor (p=0.05, seed=7).

## Alt-makine (V3D_READOUT_SPEC ile ayni)
T (mem vs chk), N (G8 uclusu), B (G1 altilisi, md5-farkli), ret_acc
(G1 havuzu), fam (G11: qb/qd/qi/qd47; kapi qd47 = qd).

## Kapilar
fam_qd >= 0.40, margin > 0, B < N, T ~= 1.0 (0.99-1.0),
ret >= 0.2301 (S0 referansi). S0n: kazanan readout'u GECMEMELI.

## A4 anatomisi (kanal-sokum, rapor)
E1-tek, S3-tek (mevcut), X1, X2 + E1/E2 ayri; hangi kanal suclu gosterir.

## On-kayitli sonuc dallari (ikisi de raporlanir)
- GECERSE: A kanitlanir; kazanan readout Inference baglantisina aday
  (ayri onay; bu turda baglanti YOK).
- GECMEZSE: A4 sucluyu gosterir; B (ogrenme/gating) veya C (mem yazim
  semasi: ates-oncesi tepe snapshot, opt-in bayrak, kapaliyken bit-esit)
  gerekcesi kanitli hale gelir; ikisi de AYRI onay ister.

## Regresyon kilidi
C++/binary/frozen degisikligi YOK; readout_v3d.py + phase0_margin.py
sha-ayni; phase0 F1 tablosu bit-bit ayni (tekrar kosulmaz, sha karsilastirilir).
Ciktilar: stress_out_v2/memory_readouts.csv + memory_column_audit.csv.
