# bench/STAGE_NOTES.md — aşama hükümleri (ham notlar; nihai REPORT.md Aşama 9'da)

## Aşama 2 (demux, temiz)
- D1 KALDI: S AUC ortalaması (0.9423+0.7994)/2=0.871 < 0.90.
  Alt-kırılım: tau4 0.9423±0.0315 GEÇTİ; tau12 0.7994±0.0074 KALDI.
- Mekanizma (ölçüldü): harmonik yakalama. tau12 bandı 4-only pencerelerinde
  de ateşliyor (31.6 vs 12-only 31.2): 4-trenin her 3. darbesi ISI=12 ile
  rezonans-kabul görüyor (4|12 alt-harmonik). B1/B2 de aynı sebeple 0.8000
  (4-only ve 6-only, 12-only'nin ÜSTÜNDE skorlanır). B3 (spektral) bağışık: 1.0.
- Harmonik alt-küme (D3, kritersiz): 12|4'te S=0.505 (şans!), B1/B2/B3=1.0;
  4|12'te S=0.86, baseline'lar 1.0. S combo ile 4-only'yi ayıramıyor.
- D2 KALDI: tüm medyanlar 3·tau üstünde (S tau4 med=71, tau12 med=40).
  KISMEN YANLIŞ cetvel: Youden eşiği ayrışmış veride en katı uçta seçiliyor
  (örn. B1-4 eşiği ~22 → 97 tick gecikme) + 100-tick trailing tanımı. D2 dondurulmuş
  metne göre KALDI; cetvel patolojisi REPORT'ta açıklanacak.
  Ek gözlem: S tau4 60/352 başlangıcı 300 tick içinde hiç yakalayamadı (kilit
  güvenilirliği sorunu); baseline'lar %100 yakaladı (geç de olsa).
- D4: cost_prelim.csv yazıldı (kağıt-üstü; Aşama 8'de ölçülecek).

## Aşama 3 (gürültü)
- N1 GEÇTİ: 24/24 hücre × 30 seed eksiksiz (grid_auc.csv).
- N2 GEÇTİ ("çökmedi" raporu): hiçbir yöntem/hedefte yarı-AUC ızgara içinde
  değil (tümü None). En gürültülü hücrede (p30,j30): S 0.997/0.749,
  B1 1.0/0.738, B2 1.0/0.783, B3 1.0/0.966, B4 0.851/0.524.
- Beklenmedik (hipotez olarak işaretli): S tau4 AUC gürültüyle ARTTI
  (0.942→0.999). Hipotez: ekstra darbeler yavaş-yabancı ritimlerin FRESH
  yakalamasını bozup negatif skorları düşürürken 4-rezonans korunuyor
  (stokastik maskeleme). B4 en kırılgan (ISI-tabanlı, beklendiği gibi).

## Aşama 4 (ablasyon, demux kolu)
- A1 GEÇTİ: makrosuz kopyalar bit-bit aynı (neuron + synapse probları).
- nobonus: demux'ta bit-bit AYNI (A3: etkisiz mekanizma — Dal B boş, bonus
  hiç ateşlenmiyor; kod-kanıtlı).
- npop1: AUC ~aynı (tau4 0.9426, tau12 0.7973): 8-üyeli popülasyon bu metrikte
  gereksiz (jitter fazlalığı).
- noplir (plir_mode=0 => ESKİ ISI kapısı, kapısız DEĞİL): tau4 1.0000
  (İYİLEŞTİ! eski-ISI'da FRESH-her-darbe yok → yabancı-red daha temiz),
  tau12 0.7500 (kötüleşti). PLIR tau4-seçiciliğe ZARAR veriyor.
- notrace: demux'ta yapısal N/A (synapse çağrısı yok).
- Nedensellik sütunu Aşama 6 metriğiyle eklenecek.

## Aşama 5 (genelleme, ayarsız)
- J1 GEÇTİ: 12/12 konfigürasyon koştu. J2: BOZUK YOK (tümü >0.7).
  Tekiller ~1.0; çiftler: 5+10'da tau10=0.902, 6+14'te tau14=0.885/tau6=0.984,
  7+15'te tau15=0.937/tau7=1.0 ( harmonik alt-skorlar yine bölünebilirlikten).
- J3: ayarlı sütun YOK — ayarlama yapılmadı (gerekmedi).

## Aşama 6 (seyrek nedensellik)
- S TÜM 12 hücrede P=0/R=0: pre0 hiç ateşlemiyor (neden-kanalı ölü).
  Mekanizma: 148 X -> 123 evx (P2 geçiriyor) -> adaptör 2@tau4 patlamaları
  pre0 eşiğine yetmiyor (hızlı sızıntı + 2-darbe yetersizliği); pre2 (yavaş
  sızıntı) 72 ateşliyor — neden/etki kanalı asimetrisi. Şablon (periyodik)
  pre0=218: port sadık, seyrek-sessizlik gerçek (yoğun tekrarlama gerekli).
- C1 KALDI: S(0±0) vs N3(0±0) GA'ları çakışıyor. Not: N1/N3, S hızına (0)
  eşlendiği için dejenere; N2 (denetimli lag tablosu) kısmi skorla görevin
  çözülebilir olduğunu gösteriyor (S'nin başarısızlığı görevin değil).
  Eşleştirme katı-eşitsizlikli (predict.h ile aynı): tam-isabet alarmlar
  sayılmaz — tüm yöntemlerde eşit uygulandı.
- C2: X-yok alarm hızı 0.000000±0 (sessizlikten triviyal).
- Ablasyon-nedensellik: tüm düşüler +0.0000 ama TABAN ETKİSİ (baz zaten 0) —
  "mekanizma önemsiz" DEĞİL, "ölçülemez" olarak raporlanacak.
- C3 GEÇTİ: 12/12 hücre × 30 seed.

## Aşama 7 (gerçek veri)
- Veri: figshare 25425920 (CC BY 4.0, DOI+md5 doğrulandı), Ocimum 38 kayıt.
  kal=2 (theta), test=36. Kodlama: 10kHz->100Hz (tick=10ms), delta-modülasyon.
- THETA=16 (floor 4.0, kalibrasyondan).
- Havuzlanmış AUC (n=483 pencere): S=0.493, B-var=0.455, B-hf=0.412.
  S kayıt-başına 35/36'da 0.500 (ateşliyor ~59/kayıt ama pre/post'ta tekdüze).
  Bazıları kayıt-bazında sinyal taşıyor (Munich_3: B-hf 0.9) ama havuz şans
  seviyesinde. ZAYIF SONUÇ aynen raporlanacak; zayıf-etiket payı büyük
  (~%60 yanıt oranı + 3-6 sn gecikme vs 0-5 sn post-penceresi).
- R1/R2/R3: arama günlüğü + kal/test kayıt ayrımı + dt açık. Bar yoktu.
