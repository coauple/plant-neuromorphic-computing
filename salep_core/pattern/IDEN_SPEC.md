# IDEN — K1→Identity-Preserving Competitive Readout (PRE-REGISTERED)

Tarih: 2026-09-16. P0/P0b/P0c/T-AMP donuk; dosya+verilerine dokunulmaz.
Hipotez: K1'deki indeks-faz-kimliği, genlikten bağımsız readout'a taşınır.
Aşama 1: yalnız K1→readout (K2/K3 YOK). Öğrenme YOK, C++ YOK.

## 1. Mekanizma (dağıtık WTA; merkezi seçim YOK)

12 readout (standart 3-kompartıman, P0b P3 parametreleri).
Readout-s: Dal-A ← k1A[s], Dal-B ← k1B[s] (besleme 1.0 sabit).
Yanal inhibisyon: readout-s ateşleyince diğer 11 readout'un
KÖKüne −1.0 enjekte edilir (aynı spike mekanizması; INH=1.0
gerekçesi: uyarım genliğiyle simetrik, sonuçtan bağımsız sabit).
Tick sırası 0..11 sabit, deterministik (sıra-yanlılığı amp
koşullarında ortak-kiptir, metriği bozmaz).
YASAKLAR (mekanizmada): etiket, classifier, merkezi
phase-distance/argmax/normalize. Kimlik "kazanan"ı yalnız
analizör raporlar (raporlama kuralı, mekanizma değil):
en çok spike; eşitlikte en erken ilk-spike; onda da düşük indeks.

## 2. Matris (50 koşul ×2 tekrar, tren: 5 darbe ISI=12 t0=50 ufuk 200)

12 slot × amp{0.5,1,2,4} (48; amp = K-girdi tren genliği) +
rekabet (60+240), (60+90) eşzamanlı (2). φ_A=120 sabit (A-tarafı
kontrol — değişmiyor).

## 3. Metrikler + başarı kriteri

Kazanan=None (sessizlik) açık sonuçtur. Voltaj değişimi
başarısızlık DEĞİL; kazanan-değişimi EVET.
M1 determinizm · M2 koruma (φ başına 4 amp'ta aynı kazanan) ·
M3 ayrışma (φ_i≠φ_j → farklı kazanan) · M4 12/12 kapsama ·
M5 amp-kararlılık tablosu · M6 WTA-kazanan amp ile dönmüyor ·
rekabet davranışı (rapor).
HÜKÜM: tüm φ'de M2+M3+M4 → KORUR; kısmi → KISMEN (tablo);
aksi → KORUMAZ. "A kazandı" ilanı YOK; yalnız ölçü.

## 4. Kilitler

Tek koşu; analizör manifest (amp seti, INH, tren, tick-sırası)
eşitliğini assert'ler; P0-içi ayar yasağı geçerli. K2/K3 ikinci
aşama yalnız M2+M3+M4 tam-pass ise (ayrı hipotez).
