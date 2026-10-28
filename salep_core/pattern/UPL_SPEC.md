# UPL — Öğrenme-Açık Uyanış Testi (PRE-REGISTERED)

Tarih: 2026-09-16. Soru: mevcut quadratic kural, P3 bağlantılarını
gerçek afferent örüntülerle güçlendirip çalışma noktasına getirir
mi; getirirse K1 kimliği sürer mi? Kural DEĞİŞMEZ (§9.1 aynen).

## 1. Ağırlıklar (yeni olan yalnız topoloji; sayılar anayasadan)

30 sinaps: 28 girdi-ağırlığı (hedef K birimi başına: pre = dalına
gelen darbeler, post = birimin spike'ları) + 2 P3-besleme ağırlığı
(wP3A/wP3B: pre = dala gelen K-spike'ları, post = P3 spike'ları).
Başlangıç 1.0 = mevcut rejim ("öğrenmeyi buradan açıyoruz").
eta=0.3 (§9.14), W_MAX=2.0 (§9.1), RATE_WINDOW=30 (§9.1).
Kural: dw = eta·min(p,q)·(p+q)²·(1−(w/W_MAX)²), p,q 30-tick halka
sayaç oranları. Tick-başı güncelleme (sensory_tick disiplini).

## 2. Maruziyet (kilitli)

UPU episode'ları (salt-okunur): 20 tur art-arda (30 tick boşluk),
durum SÜREKLİ (reset yok — hız sürekliliği şart), sonra ağırlıklar
DONDURULUR, episode'lar sıfır-birimde yeniden ölçülür.
Önkoşul riski (açık): r_post=0 iken G=0 → P3-ağırlıkları donuk
kalır; uyanış ancak girdi-ağırlığı büyümesi K-hızını eşiğe taşırsa
olur. İki yön de bulgudur.

## 3. Metrik + hüküm (kilitli)

Ağırlık yörüngeleri (başlangıç→son, 30 sinaps) · P3 ateş
önce/sonra · uyanırsa imza-ayrışması (UPU mesafesi) + K1-slot
ateş örüntüleri (kimlik sürüyor mu?).
UYTANIYOR (donmuş-ağırlıkla P3 ateşler) vs SESSİZ. Uyanırsa:
kimlik-hükmü (çiftler-arası mesafe > 0 ?). Sessizse: atıf (hangi
ağırlıklar oynadı/oynamadı + G/S analizi) — "motoru çalıştırma"
reçetesi DEĞİL, mekanik rapor.

## 4. Kilitler

Tek koşu; analizör manifest (eta/W_MAX/w0/tur/episode-hash)
eşitliğini assert'ler. pl_core/UPU dosyaları değişmez.
(b)/(c) bu turda YOK.

## 5. Fıkra — uyanış yolu (ölçüm-sonrası, hükmü daraltır, değiştirmez)

Kilitli "kimlik-korunuyor" hükmü mesafe-kuralıyla tetiklendi;
ancak donmuş-ölçümde K1 slotları SESSİZ (k1a/k1b boş), ateşleyen
yalnız k3[0]+k3[1] (ölçüldü). Yani uyanış faz-kör K3 kanalından
geldi; K1 kimliği readout'a TAŞINMADI (kullanıcının 2. sorusu:
HAYIR). Eğitimde K1 nadiren ateşledi (6/24 ağırlık +0.001 üstü,
gating-birikimli geç turlar); sıfır-durum ölçümde sustu. Sonuç:
öğrenme P3'ü uyandırır ama kimlik yolunu değil — kimlik yolunu
uyandırmak ayrı hipotez ister.
