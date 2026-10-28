# IDEN5 — K2 Bozuyor mu? (PRE-REGISTERED, minimal)

Tarih: 2026-09-16. IDEN4 KORUR → kapı açık. Tek soru: K2 eklenince
K1 kimliği bozuluyor mu? A-treni KAPALI (coincidence karıştırılmasın);
K2[B] B-trenini alır, ateşleri tüm readout'lara ortak-kip girer
(amp 1.0). k2[A] yapısal durur (girdisiz). INH=1.0 (gerçek konfig).
Öğrenme/C++ YOK.

## 1. Matris (24 koşul ×2 tekrar)

φ∈{60,150,240} × amp{1.0,4.0} × onset{50,70} × konfig{K1, K1+K2}.
(IDEN4'teki "Δt" onset-zamanlamasıdır; A kapalı olduğundan A-B
gecikmesi yoktur — eşleme kaydı.)

## 2. Hüküm (kilitli)

12 hücrenin 12'sinde (K1+K2 kazananı == K1-only kazananı ==
sürülen slot) → BOZMUYOR. Aksi → BOZUYOR + tablo (hangi hücre).
Kazanan kuralı IDEN ile aynı. Determinizm sert.

## 3. Kilitler

Tek koşu; analizör manifest eşitliğini assert'ler. iden2.py
değişmez (iden5.py ayrı).
