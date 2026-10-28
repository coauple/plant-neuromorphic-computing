# bench/TEST_PLAN.md — Kör başarı kriterleri (AŞAMA 0, sonuçlar görülmeden yazıldı)

Tarih: 2026-10-15. Bu dosya dondurulmuştur: kriter değişikliği ancak yeni bir
"REVİZYON" bölümüyle (gerekçeli, eski metin silinmeden) yapılabilir.

## Genel kurallar (tüm aşamalar)

- G1 Determinizm: aynı komut iki kez koşunca `results/` çıktıları bit-bit aynı.
- G2 Regresyon: her aşama sonunda `snapshot.sh` yeniden koşulur, tüm CSV/stdout
  SHA256'ları `baseline_snapshot/MANIFEST.sha256` ile eşleşir.
- G3 Tohum disiplini: ayar gerekiyorsa yalnız seed 1000–1009 (kalibrasyon);
  raporlanan sayılar seed 2000–2029 (test, n=30). Test kümesine bakarak ayar YOK.
- G4 İstatistik: noktasal sonuç YOK; her metrikte ortalama ± std ve %95 GA (n=30).
- G5 Kötü sonuç raporlanır, yumuşatılmaz. "Baseline bizden iyi" geçerli sonuçtur.

## Aşama 1 — Harness + üreteçler (GEÇTİ kriterleri)

- H1: Aynı seed → bit-bit aynı üreteç CSV'si (demux + seyrek dünya).
- H2: Etiket bütünlüğü %100 (her pencere/olay etiketli; boş/NaN yok).
- H3: Seyrek dünyada 30 seed ortalamasında gerçekleşen Y|X oranı, hedef p'nin
  ±0.1 bandında; sahte-Y oranı q'nun ±%50 bandında (üreteç öz-kontrolü).
- H4: Çekirdek dosyalarına dokunulmadığı `find -newer` ile gösterilir.

## Aşama 2 — Demux baseline karşılaştırması

Görev: 100-tick pencere başına "tau=k ritmi mevcut mu?" (S + B1..B4, aynı girdi).
Metrik: AUC (ritim-var vs yok + yabancı-ritim tau∈{6,8,10}) ve kilitlenme
gecikmesi (ritim başlangıcından ilk doğru tespite tick).

- D1 (temiz, p_extra=0, jitter=0, harmonik-harici çiftler): S AUC ≥ 0.90
  (30-seed ortalaması; gerekçe: mevcut FDM R1 cov≈0.98 iddiasının bağımsız
  tekrarında makul alt sınır).
- D2: Kilitlenme gecikmesi medyanı ≤ 3·tau tick (gerekçe: PLIR lock=2·tau+bw
  sonrası en geç ~1 periyotta ateşleme beklenir).
- D3: Harmonik satırı (4+12): KRİTERSİZ — bilinen sınır (§9.8), sayı raporlanır,
  GEÇTİ/KALDI verilmez.
- D4: Maliyet tablosu (işlem/tick + durum-biti, 5 yöntem) eksiksiz.
- S'nin baseline'ları geçmesi ŞART DEĞİL; sıralama neyse o yazılır.

## Aşama 3 — Gürültü taraması

- N1: p_extra×jitter ızgarasının TÜM hücreleri S+B1..B4 × 30 seed ile dolu.
- N2: S için yarı-AUC noktası (AUC'nin temiz-değerin yarısına düştüğü ilk
  gürültü seviyesi) GA ile raporlanır; düşmüyorsa "ızgara aralığında çökmedi".
- Performans barı YOK (karakterizasyon aşaması).

## Aşama 4 — Ablasyon

Mekanizmalar: PLIR kapısı, coincidence bonusu, trace/erişilebilirlik,
popülasyon (N_POP 8→1). Metrikler: demux AUC (Aşama 2) + nedensellik
recall/precision (Aşama 6).

- A1: Kopya-yöntemi kullanılan her mekanizmada, makrosuz derlenen kopya ile
  orijinal aynı girdide bit-bit aynı çıktıyı verir (eşdeğerlik kanıtı zorunlu).
- A2: Tablo eksiksiz: satır=mekanizma, hücre=metrik düşüşü (ort±std, n=30).
- A3: Etkisi ~0 çıkan mekanizma "etkisiz" diye açıkça yazılır (bulgu sayılır).
- Çekirdek dosyasında diff YOK (Aşama 4 istisnası yalnız bench/ablate kopyası).

## Aşama 5 — Genelleme (kalibre-dışı ritimler)

tau∈{5,6,7,9,10,11,13,14,15}, çiftler 6+14, 5+10, 7+15.

- J1: Parametre DEĞİŞMEDEN tüm tau/çiftlerde AUC+gecikme raporlanır.
- J2: Hangi tau'larda bozulduğu (AUC<0.7 eşiğiyle) listelenir.
- J3: "Ayarlı" sütun ancak kalibrasyon-kümesi ayarıyla ve "ayarlandı" etiketiyle
  verilir; ayarsız sütun her zaman yanında durur.
- Genelleme barı YOK (bozulma beklenir ve raporlanır).

## Aşama 6 — Seyrek dünya nedensellik/öngörü

Metrikler: recall, precision, yanlış-alarm oranı, ortalama lead; baseline N1/N2/N3
eşit alarm bütçesinde (alarm/tick eşit).

- C1: Eşit alarm bütçesinde precision(S) > precision(N3) (%95 GA çakışmadan).
  Gerekçe: rastgele-alarmı geçemeyen sistem "öngörü" iddia edemez — asgari bar.
- C2: "X yok iken Y" kontrolünde yanlış-alarm oranı raporlanır (bar yok).
- C3: p×jitter×q ızgarası eksiksiz (her hücre n=30).

## Aşama 7 — Gerçek veri

- R1: Arama günlüğü eksiksiz: bulunan her aday için URL + lisans + neden
  uygun/uygun-değil; bulunamazsa "bulunamadı" + REAL_DATA_PROTOCOL.md (kayıt
  protokolü önerisi).
- R2: Veri varsa: kalibrasyon-kaydı/test-kaydı ayrımı + AUC vs baseline'lar;
  etiket yoksa YALNIZ betimleyici sonuç + "iddia kurulamaz" notu.
- R3: tick-eşleme (dt) ve spike-kodlama parametreleri açıkça yazılır.
- Performans barı YOK.

## Aşama 8 — Donanım maliyeti

- W1: Nöron/kompartıman/durum-değişkeni sayıları + sizeof + ölçülen min/max'tan
  bit-genişliği önerisi tablosu eksiksiz (çekirdek + baseline yan yana).
- W2: Tick-başına işlem sayıları sayaçla ölçülür (tahmin değil).
- W3: LUT boyutları (G,Q,S) + baseline bellekleri tabloda.
- W4: Sentez aracı yoksa sentez sonucu ÜRETİLMEZ, "kağıt-üstü tahmin" yazılır.

## Aşama 9 — Şekiller ve rapor

- F1: 7 şekil 300 dpi Türkçe eksenlerle üretilir; üretilemeyen şekil için
  gerekçe REPORT.md'de yazar ("atlandı" gizlenmez).
- F2: REPORT.md: 1-sayfa yönetici özeti (5 bulgu) + aşama başına yöntem/tablo/
  şekil/GEÇTİ-KALDI + "Sınırlar ve dürüst notlar" (tohum ayrımı, sentetik
  sınırı, YZ-desteği notu, doğrulanmamış iddialar).
- F3: `bash bench/run_all.sh` sıfırdan tümünü üretir; bu dosyadaki her kriterin
  GEÇTİ/KALDI karşılığı raporda bulunur.

## Bilinen ön-bulgular (kriter değil, bağlam; Aşama 0 gözlemi)

- P0: Anlık görüntü güncel kaynaktan alındı; `causality` koşusu tarihsel 2.11x
  kapısını tutturamıyor (1.04x + UYARI) — REV-LEARN sonrası rejim değişimi,
  bench öncesi mevcut durum. Regresyon, BU anlık görüntüye göre yapılır.
- P1: `fdm.h:93-95` init-sırasında double kullanıyor (tick-döngüsü değil) —
  Aşama 8'de "çekirdekte float yok" iddiasının istisnası olarak raporlanacak.
