# RAKİP DENEYLER A/B/C/D — TEK RAPOR

Tarih: 2026-09-22. 4 paralel deney grubu; repo salt-okunur, derleme yok.
Ham veriler /tmp/gA..gD, grup raporları /tmp/rpt_ra..rd.md.
Ayna `/tmp/rival/mirror.py`: binary `--k4 0` ile bayt-bayt doğrulanmış
(eta 0 + eta 19660; mem/log cmp temiz), deneyler kopyalarla koştu.
D-yenilik iddiası bağımsız doğrulandı (TEST-B'de 5+6 birlikteliği 0/249).

## A — STDP varyantı vs REV-LEARN (F1, K4 kapalı, eta=19660)

STDP varyantı (çocuğun tasarımı, tek parametre seti): ateş+yükte w+=1310,
ateşsiz+yük+son-ateş≤30 tickte w-=1310. Aynı TEST-B aff'i.

- Öğrenme hızı: ilk ateş ikisinde de tick 335 (aynı başlangıç ağırlıkları).
  Toplam ateş REV 536, STDP 11. REV wsum 34.21M→41.85M (potansiyasyon);
  STDP →31.30M ( yoğun girişte LTD baskın, net depresyon).
  wkdev: REV 0.435→1.0 monoton; STDP 0.52'de tamamen düz (donma).
- Unutma (2000 idle): uzun eğitim sonrası ikisinde de dsum=0 (doymuş
  ağırlıklar; REV drift terimi sabit-noktada sıfıra yuvarlanıyor).
  Kısa eğitim sonrası: REV dsum=+1129966 (iz-tabanına gevşeme, koruyucu),
  STDP dsum=-431048 (bir ağırlık ~0'a iner, gerçek silme).
- Geri-dönüş (A→1000 idle→A): REV gecikme 5→2 tick, ateş 1662→1708;
  STDP faz3'te sıfır ateş (dönemiyor).
- İnterferens (A→B→A): REV retention 1.0, Jaccard(A1,A3)=0.9375;
  STDP retention 0.0, Jaccard 0.0 (B, cılız A izini siler).
- Seçicilik: A–B Jaccard iki kuralda da 0.56, çapraz-öğrenici Jaccard 1.0 —
  birim kimliği kablolama/drive'dan gelir, kural yalnız ateş sayısını
  ölçekler (REV 1662/2532, STDP 54/80).

HÜKÜM: REV-LEARN öğrenme hızı, geri-dönüş ve interferens-dayanımında üstün;
seçicilik kuraldan bağımsız. Sınır: tek STDP parametrelemesi (A±=1310),
bu aff yoğunluğunda aşırı LTD'ye girip susuyor — genelleme "bu varyant"
ile sınırlı, "tüm STDP" değil.

## B — Dal ablasyonu (TEST-B, eta=19660, K4 kapalı)

7 hücre: full / K1 / K2 / K3 / K1+K2 / K1+K3 / K2+K3.

| hücre | toplam ateş | aktif birim | wkdev |
|---|---|---|---|
| full | 536 | 11 | 0.9998 |
| K1, K2, K3, K1+K2, K1+K3 | 0 | 0 | 0.0000 |
| K2+K3 | 113 | 3 | 0.9989 |

Dayanıklılık (shift+5 / jit±3 / noise Jaccard): full 1.0/1.0/0.909
(335 ateş); K2+K3 1.0/1.0/0.25 (58 ateş). Etiket-bazında full yalnız
p2b(p2e)'de güçlü (96 ateş, birim 6,23,24), p2a(p2c,p2d)'de zayıf
(6 ateş, birim 9); K2+K3'te yalnız birim 9'un zayıf yanıtı kalır.

HÜKÜM: K2+K3 ateş için gerekli+yeterli çekirdek; K1 yükseltici (~5x ateş,
3→11 birim) ve gürültü sağlamlığı katkısı (0.25→0.909); tek dallar ve
K1'li ikililer TEST-B eşiğinde sessiz.

## C — 80 desen stres sonrası A korunumu (binary, eta=0.30, K4=1)

A/B/C/D blokları ayrık post kümeleri ({0,1}/{2,3}/{4,5}/{6,7}), 20'şer
tekrar + 3 A-son probu = 83 uyarım, 166 olay.

- A-ilk: rep0 sessiz, ilk ateş rep1 (30 tick öğrenme gecikmesi), 19/20
  tekrar, 70 ateş; çekirdek {6,23}→{6,17,23,24,26}.
- A-son (60 yabancı desen sonrası): rep0 ANINDA ateş (0 gecikme), 3/3,
  15 ateş (5.0/tekrar, A-ilk bandında); mem kümesi birebir aynı,
  Jaccard 1.000 ({0,5,6,17,20,23,24,26}).
- wsum monoton arttı (çökme yok); tsum D sonrası doydu (iz doyumu);
  rsum dalgalı (C'de tepe, A-son'da sönüm — K4 ilişkileri geçici,
  kalıcı ağırlıklar korunur). k4_kfires=128, k4_spikes=0.
- B/C/D blokları kendi ayrık kümelerini buldu, A'nın kümesini ezmedi.

HÜKÜM: A bozulmadı, korundu. Sınır: A-son probu yalnız 3 tekrar;
daha uzun stres sonrası unutma test edilmedi.

## D — Görülmemiş örüntü (binary; A,B,C öğret → yeni D={5+6})

D'nin yeniliği TEST-B'ye karşı doğrulandı (bağımsız: 0/249 tick'te
5+6 birlikteliği). k4=0/1 ayrı koşular; eğitim A/B/C 20'şer tekrar,
sonda checkpoint --load ile.

- D eğitimli ağda hiçbir öğrenilmiş kümeye indirgenmiyor: J(D,A)=0.33,
  J(D,B)=0.50, J(D,C)=0.42; 12 birimlik bileşke + D-seçici 9/19/22.
- D kimliği eğitimden gelmiyor: taze ağ aynı kümeyi üretiyor,
  J(eğitimli,taze)=0.92 (k4=0) / 1.00 (k4=1).
- Eğitim şiddeti ~3x artırıyor (sunum başına 9.4 vs 3.2 ateş), kimliği
  değiştirmiyor. k4 sonucu değiştirmez (D'de S4≤0.036, N-kapısı içi).

HÜKÜM: gerçekten farklı durum, zorla-indirgeme yok.

## GENEL HÜKÜM

REV-LEARN bu rejimde STDP varyantına üstün (hız, geri-dönüş, interferens);
seçicilik kablolamada. Üç dalın rolü asimetrik: K2+K3 çekirdek, K1
yükseltici+sağlamlık. Öğrenilmiş temsiller yabancı bloklara dayanıklı
(C: Jaccard 1.0), yeni kombinasyonlar ezber kümeye indirgenmiyor (D).
Açık sınırlar: A'da tek STDP parametrelemesi; C'de 3 tekrarlı prob;
deney tohumları tek (B: jitter seed 7, noise seed 11).
