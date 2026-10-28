# IDEN2 — WTA mı Seçiyor, A-Treni mi Biniyor? (PRE-REGISTERED)

Tarih: 2026-09-16. IDEN donuk (dosya+veri); IDEN2 ayrı tanı deneyi.
Soru: 4.0'da 90°/150° kazananının readout-4'e kayması WTA'nın
seçimi mi, A-treni+coincidence bonusunun üzerine binmesi mi?
K2/K3 YOK (ayrıştırma bozulmasın). Öğrenme/C++ YOK.

## 1. Ayrıştırma (INH × A-treni, φ∈{60,90,150}, amp∈{1,4})

- INH∈{0, 1.0}: WTA kapalı/açık. Aynı kazanan → seçimi
  feedforward etiketli hat yapıyor; farklı → WTA seçime katılıyor.
- A-treni var/yok (yok = yalnız B-treni; bonus imkânsız).
  24 koşul ×2 tekrar. φ_A=120, trenler IDEN ile aynı.

## 2. Atıf kuralları (koşudan önce kilitli)

R1 (WTA rolü): INH0 vs INH1 @1.0 — aynıysa "feedforward seçer",
  farklıysa "WTA katılır".
R2 (A-baskınlığı): A-yok @4.0 φ90/150 — kayma düzelirse suçlu
  A-treni+bonus; sürerse B-tarafı/yüksek-amp içsel.
R3 (B-yeterliliği): A-yok @1.0 — eşleşirse B-tek-başına yeter;
  değilse bonus gerekli.
Kazanan kuralı IDEN ile aynı (raporlama). HÜKÜM: atıf tablosu;
  KORUR/KORUMAZ yok (tanı deneyi).

## 3. Kilitler

Tek koşu; analizör manifest (INH seti, A-modu, amp seti, tren)
eşitliğini assert'ler. iden.py'ye dokunulmaz (iden2.py ayrı).
