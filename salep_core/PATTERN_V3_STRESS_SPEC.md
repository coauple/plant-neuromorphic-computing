# PATTERN LOBE v3 FULL-SYSTEM STRESS — ÖN-KAYIT (PRE-REG, DONDURULDU)

Soru: v3 karmasik ve gecmise-bagli bitki dunyasinin YAPISAL oruntulerini
cikarabiliyor mu? (Beklenen: ayni-yapi->benzer-pattern,
farkli-yapi->farkli-pattern, gorulmemis-varyasyon->ayni-aile.)

## Kural
Sonuc kotu ciksa yeni test icat EDILMEZ; asagidaki metriklerle raporlanir.
Harness crash'i duzeltilebilir (deney degisikligi degil); senaryo/metrik/
tohum listesi calisma BASLAMADAN sabittir. Degisiklik = SPEC revizyonu + gerekce.

## Kapsam disi (sim destegi yok, bahane degil eksik)
- HASTALIK: patojen dugmesi yok (borc kutugu). Yerine G7 adversarial.
- Dogrudan EC/pH/isik dugmesi yok -> VEKILLER (asagida), raporda etiketli:
  EC-soku = agir fert (ec_mass += fert, plant_sim L720); pH = fert dozu;
  isik = UV dosyalari (uv_index_max/clear, 0..25).

## Sabitler
- Gun=130 (G6-uzun=260), plant cond=10/test=3 (260: 20/6), eta=0.30
  (G10'da 0 / 0.15 / 0.30), K=3 retrieval, tohumlar asagida.
- Hava dosyalari (salep_core/weather_v3/, 130 gun, 2025-01-01+):
  W-base (12->27C + yagmur gunleri 20,21,50,80,110 x8mm),
  W-hot (+6C), W-cold (-6C, min sinirli degil), W-wet (base yagmur x3 +
  ekstra 30,31,90,91), W-wetcold (cold + wet-yagmur),
  U-hi (uv=clear=9), U-lo (uv=1.5, clear=9).
- G3/G6-kablo: 500-tick bloklar.

## Gruplar (case: on-ek + parametre + tohum)
- G1 tek: base, irrig20, fert30, kumlu, hot, cold, drought[60,60] (s42)
- G2 komb: drought+hot, drought+fert80, wet+cold, dogal-toparlanma
  (drought[40,40] + sonrasi hicbirsey) (s42)
- G3 sira: base-afferent blok sirasi ABC / CBA-ters / rotasyon (kablo)
- G4 gecmis: normal, drought-erken[0,70], irrig-erken[0,70]+20mm
  (final-30gun karsilastir, s42)
  REV1 (gerekce: 100.gunden sonra dunya DORMANT, hat sessiz; aktif
  donem 47-99 oldugundan final = 70-100 pencereleri):
- G5 komsu: drought yuzde 40/45/50 (gun40'tan len 52/58/65) + 45-tekrar
  s43 (within icin) (s42)
- G6 uzun: 260gun base + kablo-tekrar (10gunluk dilim x6) (s42)
- G7 nadir: hot+saganak (irrig[90,2] 60mm), EC-sok+sonra-su
  (fert[90,5] 120 + irrig[95,35] 25mm), sok-toparlanma
  (drought[40,60] + irrig[100,30] 30mm) (s42)
- G8 tohum: base x s42/43/44 (ayni hava W-base)
- G9 dunya: drought[60,60] x W-base/W-hot/W-cold (s42)
- G10 eta: 0 / 0.15 / 0.30 (base afferent; cesitlilik+stabilite+retrieval+
  yanlis-birlesme)
- G11 unseen: ref {base,drought[60,60],irrig20} s42 -> sorgu {ayni-3 s101,
  drought47 s42} (aile-uyumu)
- G12 neden: drought[40,40]+irrig[80,50]30mm vs normal+irrig[80,50]30mm
  (final-10gun + sensor-mesafe) (s42)
  REV1 (G4 ile ayni gerekce: 70-100 pencereleri):

## Metrikler (her case; formuller pattern_stress_v3.py basliginda)
N_sig, N_pv, repetition, ISI-ort/std, stabilite (split-half Jaccard),
within (varsa tohum-tekrari gun-hizali Jaccard), retrieval-acc (yalniz
etiketli grup, LOO infer), between (gun-hizali gunluk-Jaccard ort; bos-bos=1,
bos-dolu=0). G11: aile-uyumu. G12/G4: final-pencere benzerligi + sensor
Oklid-mesafe (rapor).

## Kapilar (BATTI=cikis 1) vs rapor
KAPI: crash-yok (adversarial dahil exit 0; bos-girdi temiz-dur),
determinizm (v3 cift-kosu sha; capraz-kosu T10-esdegeri), encoder 1:1,
adapter bit-esit. RAPOR: yukaridaki tum metrikler + skorlar (dogruluk
kapisi YOK).

## REV2 (2026-09-16): v3d karsilastirmasi
Deneysel degisken YALNIZ binary (NPU_V3_EXE=npu_pattern_unit_v3d;
ONAYLI 29-P3 haritasi). Senaryo/tohum/metrik/kapi listesi aynen;
sonuclar /tmp/pstress_d/'ye. Karsilastirma: G5 drought%, retrieval,
G12, diversity/selectivity. REV1 aynen gecerli.

## REV3 (2026-09-17): G1-drought GECERSIZ UYARAN (SILINMEDI)
Bayrakli drought ([60,60)) base ile ayni yasam seyrini uretiyor
(FLOWERING@89 ikisinde de) ve kabloyu degistirmiyor (76=76, md5-esit).
Fiziksel kuraklik (W-dry: yagmur yalniz [20,21] +6C) kabloyu 76->169
tasir; base-vs-drynew eff_g 0.9914 (n=348). Eski G1-drought sonuclari
tarih olarak kalir; aile/ayrim sorularinda KULLANILMAZ. Gecerli hat:
STIMULUS_SNR_SPEC.md (A0/A1/A2).
