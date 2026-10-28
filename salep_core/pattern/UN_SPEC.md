# UN — Doyan Dal İletimi (PRE-REGISTERED)

Tarih: 2026-09-16. Hipotez: yerel dendrit dinamiği (dal-başına
sonlu-kaynak iletimi) tek başına joint-selektivite üretir.
K1/K2/K3 AYNI, P3 girdileri (spike örüntüleri) AYNI; değişen
yalnız P3 entegrasyon fiziği (prototip-sapma; C++ dokunulmaz,
port notu §4).

## 1. Mekanizma (yerel, merkezi matematik YOK)

P3 Dal-A/Dal-B'nin her birinde kaynak R∈[0,1] (başlangıç 1.0).
Girdi darbesi (genlik a): iletilen = a×R; R ← max(0, R−k·a),
k=0.5 (kilitli: birim-darbe kaynağın yarısını tüketir → dal
birkaç güçlü darbe üst üste alınca doyar). Toparlanma tick-başı
+r, r=0.05 (kilitli: ~20 tick'te tam toparlanma mertebesi).
Sayılar yapısal-mertebe gerekçeli, sonuçtan bağımsız, tek seçim.
US dal-eşlemesi aynen (K3→A, K1+K2→B); ağırlıklar donuk UPL-son.

## 2. Sadakat kapısı (kilit — önce bu)

k=0 (tüketim yok, R≡1) koşusu US tablosunu BİT-EŞİT üretmeli.
Tutmazsa implementasyon hatasıdır (DUR, sonuç-değerlendirme YOK).
Tutarsa k=0.5 TEK test koşusudur (süpürme YOK).

## 3. Dört koşul + hüküm (US ile aynı katılık)

K1/K2/K3-only → 0 · JOINT → >0 (3 episode). Hepsi buysa
SELECTIVE-JOINT (prensip bulundu). Aksi → NON-SELECTIVE +
R-min kayıtları (solo doydu mu? joint taze mi?).

## 4. Kilitler + port notu

Tek test koşusu (+1 sadakat). Analizör manifest (k, r, dal-eşemesi,
ağırlık-kaynağı, koşullar) eşitliğini assert'ler. upl.py/pl_core
değişmez. C++ portu (ileride, ayrı onay): compartment'a R alanı
+ inject'e tüketim; neuron_tick aynen.

## 5. Fıkra — sadakat hedefi us2 (çift-sürüş kusuru sonrası)

İlk sadakat denemesi us_runs.csv'ye karşı BATTI; araştırma
us.py'deki çift-sürüş kusurunu buldu (UJ/US §4 fıkraları).
Sadakat hedefi us2_runs.csv'dir (tek-sürüş düzeltilmiş taban).
un_run.py referansı buna göre güncellenir (ilk başarılı koşu
henüz YOK — kilit temiz).
