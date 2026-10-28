# IDEN3 — Coincidence-Duration → Identity Nedensel Testi (PRE-REGISTERED)

Tarih: 2026-09-16. IDEN/IDEN2 donuk. Test edilen teşhis: "A,
coincidence penceresini daha uzun açık tuttuğu için seçimi
kazanıyor" (iz-kanıtı: ro4 21 tick vs ro3 10 tick açık-pencere).

## 1. İzolasyon (tek değişken)

Sabit: φ_A=120, φ_B=90, amp=4.0, INH=1.0, trenler (5 darbe ISI=12),
A/B spike sayıları, toplam enjekte enerji (yapı gereği aynı —
analizör assert'ler).
Değişken: B-treni başlangıç ofseti dt ∈ {0,2,5,8,10,15,20,30}.
8 koşul ×2 tekrar. dt yalnız çakışma-süre desenini oynatır.

## 2. Kayıt (readout başına)

Kazanan (IDEN kuralı) + coinc-tick sayısı (ro3/ro4) + dal başına
girdi sayıları (kontrol: dt-boyu eşit olmalı).

## 3. Hüküm kuralları (kilitli)

- Kazanan dt ile DEĞİŞİYORSA (kontroller tutarken) → teşhis
  DOĞRULANDI (süre→seçim nedensel).
- Kazanan SABİTSE → teşhis ÇÜRÜTÜLDÜ (seçimi başka şey sürüyor).
- Karışık → KISMEN (tablo; hangi dt'de ne).
Kontroller: toplam darbe/enjekte-enerji dt-boyu eşit (assert);
eşit değilse koşu GEÇERSİZ (hüküm yok).

## 4. Kilitler

Tek koşu; analizör manifest (dt seti, sabitler) eşitliğini
assert'ler. iden.py/iden2.py'ye dokunulmaz.
