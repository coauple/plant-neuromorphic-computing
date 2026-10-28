# REV-LEARN Baseline Entegrasyonu — 6 deney (k4plastic donduruldu)

Entegrasyon durumu: öğrenme kablosu zaten vardı (`--eta` → `p3x3unit_learn`,
`main_pattern_lobe.cpp:290`); bu işte eklenen TEK şey salt-okunur
`--tracecsv/--traceevery` iz telemetrisi (verilmezse çıktı/davranış değişmez,
J korunur). Yeni mekanizma YOK. Baseline: **k4plastic = K4 ON + eta 0.30**.
Karşılaştırma koşulu k4static (K4 ON + eta 0) saklı.

Kapılar: validator full-yeşil (J-bit-identical `2f3811e3/0942be1f`, D, P, R8,
M, N, S) + yeni `check_learn_baseline.cpp` LB1-LB4 OK (OFF/ON determinism,
ON-öğrenir/OFF-donuk wmove=102, K4-sızması-yok). Deney kodları throwaway:
`/tmp/learnbase/exp15.py`, `exp56.py`. Ham çıktılar `/tmp/learnbase/e*/`.

## 1 — OFF/ON aynı-girdi (TEST-B, K4 ON)

Çift-koşu mem/log sha eşit (OFF ve ON). İlk sapma tick 467, 251 tick'te
farklı firemask. mem 140→562 ama **birim kümesi birebir aynı** (13 birim);
wkdev 0→0.9998. Fark yalnızca öğrenmeden.

## 2 — A→sessizlik(1000)→A

ON: A1-son50 12.00 → A2-ilk50 9.42 (%78 ani dönüş) → A2-son 12.06.
OFF: 7.78 → 6.08 → 7.78. İz t=200/1200/1500'de aynı (102 sinapsta T>0.5,
meanT 0.1951): sessizlikte T donuk, w tabanda park.

## 3 — A→B→A

A-izi B sonrası 102/102 korunuyor. ON A2-ilk 10.54 (OFF 6.86), A2-son A1
seviyesinde (12.00). B yanıtı da ON'da yüksek (9.30 vs 6.00).

## 4 — Proliferasyon (A,B,C)

Birim kümeleri OFF/ON birebir aynı (27 birim). Öğrenme yeni küme ÜRETMİYOR;
mevcut temsili güçlendiriyor (mem 3843→4096-cap).

## 5 — Temporal selectivity (seyrek; S1 eşzamanlı vs S2 alterne, eşit sayı)

OFF ayrımı EVET (hizalı-eşitlik 0.297). ON ayrımı EVET ve daha keskin
(0.196). Öğrenme zaman-organizasyonu ayırtını bulanıklaştırmıyor.

## 6 — Uzun koşu (20000 tick, 40 blok + 40 sessizlik probu)

- Sessizlikte kazara ateş: OFF 50/8000, ON 78/8000 (küçük artış, dürüst kayıt).
- Blok oranları stabil: OFF 6.53→6.59, ON 10.05→10.39 (patlama/çöküş yok).
- İz birikimi PLATO yapıyor: meanT 0.38→0.58, sonra t=10000=t=19800
  bit-eşit (304/522 sinaps). Deneyim çeşitliliğiyle doyuyor, sistemi
  doldurmuyor. meanW de 1.58'de plato.
- Kullanıcının korkusu çürütüldü: "trace kalıyor" → "her şey birikiyor"
  OLMUYOR; iz yalnızca tekrarlayan korelasyonlarda doyuyor.

## Hüküm

REV-LEARN = Pattern Lobe baseline öğrenme mekanizması (freeze).
Sonraki iş kuadratik kuralı kurcalamak DEĞİL; temsil + loblar-arası iletişim.
Uyarı: mem 4096-cap deney 2-4'te doldu (oranlar log'dan, etkilenmedi);
uzun-koşu tek desen-ailesiyle yapıldı, yeni desen-ailesi plato-seviyeyi
değiştirebilir (açık kapı).
