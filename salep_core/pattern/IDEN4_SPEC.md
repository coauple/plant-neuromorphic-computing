# IDEN4 — K1 Identity İzolasyonu (PRE-REGISTERED)

Tarih: 2026-09-16. IDEN/IDEN2/IDEN3 donuk. Hipotez: K1 identity
readout, K2/K3 temporal bilgisi olmadan fazı doğru ve genlikten
bağımsız seçer. A-treni YOK (B taşır → bonus imkânsız, saf
feedforward kimlik testi). K2/K3 YOK.
Mekanizma: iden2.Iden2Unit aynen (import; B-only sched). Yeni
mekanizma dosyası YOK.

## 1. Matris (144 koşul ×2 tekrar)

φ_B 12 slot × amp{1.0,2.0,4.0} × onset{50,70} × INH{0,1.0}.
Tren: 5 darbe ISI=12 (B-yalnız). φ_A tanımsız (A kapalı).

## 2. Metrikler

Kazanan kuralı IDEN ile aynı. M1 determinizm · M2' φ başına
6 hücrede (amp×onset) aynı kazanan · M3 ayrışma · M4 hücre
bazında 12/12 kapsama · M5 WTA-etkisi (OFF vs ON kazanan
tablosu — aynıysa WTA seçime girmiyor) · kontroller (enerji/
darbe eşitliği, K-girdi raporu).

## 3. Hüküm (kilitli)

Tüm φ'de M2' + tüm hücrelerde M4 → KORUR (K1 kanalı temiz).
Kısmi → KISMEN. Aksi → KORUMAZ.
Kapı: KORUR ise IDEN5 (K2 ekle); değilse IDEN5 YOK (önce kayıp
noktası).

## 4. Kilitler

Tek koşu; analizör manifest eşitliğini assert'ler. iden2.py
değişmez.
