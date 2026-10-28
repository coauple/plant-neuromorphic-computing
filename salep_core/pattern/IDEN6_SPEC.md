# IDEN6 — K3 Bozuyor mu? (PRE-REGISTERED, minimal)

Tarih: 2026-09-16. IDEN5 BOZMUYOR → kapı açık. Tek soru: K3
(history-kanalı) eklenince K1'in doğru kimlik seçimi değişiyor
mu? K3[B] B-trenini alır, ateşleri tüm readout'lara ortak-kip
girer (amp 1.0). k3[A] yapısal (girdisiz). A-treni KAPALI.
INH=1.0. Öğrenme/C++ YOK.

## 1. Matris (24 koşul ×2 tekrar)

φ∈{60,150,240} × amp{1.0,4.0} × onset{50,70} × konfig{K1+K2, K1+K2+K3}.

## 2. Hüküm (kilitli)

12 hücrenin 12'sinde iki konfigürasyon da sürülen slotu seçerse
→ BOZMUYOR (IDEN serisi kapanır: K1✓/K1+K2✓/K1+K2+K3✓).
Aksi → BOZUYOR + tablo.

## 3. Kilitler

Tek koşu; analizör manifest eşitliğini assert'ler. iden5.py
değişmez (iden6.py ayrı).
