# US — Dal-Ayrışmalı Selektif Entegrasyon (PRE-REGISTERED)

Tarih: 2026-09-16. Hipotez: mevcut bonus nonlineerliği (NMDA-emsali)
doğru kablolanırsa joint-selektivite üretir. Teşhis: K3, k3[0]+k3[1]
ile iki dalı birden sürüp bonusu tek başına kapıyor. Yapısal çözüm:
sınıf→dal eşlemesi — K3→Dal-A (bağlam kapısı), K1+K2→Dal-B (sürüş).
Bonus yalnız bağlam+sürüş çakışınca uygulanır. Yeni parametre YOK,
eşik oynaması YOK, INH YOK (UJ kaydı durur), dinamik değişikliği YOK.

## 1. Kablolama (kilitli)

P3 Dal-A ← K3 spike'ları; Dal-B ← K1+K2 spike'ları (besleme:
episode-özgü UPL-son-ağırlıklar, donuk; öğrenme KAPALI).
Ablasyon izdüşümde (koşul-dışı sınıf spike'ları P3'e gitmez).
Sıra: K-tick → P3-enjekte → P3-tick.

## 2. Dört koşul (episode başına; UPU 3 episode'u)

K1 → 0 · K2 → 0 · K3 → 0 · JOINT → >0. Hepsi buysa
SELECTIVE-JOINT (entegrasyon prensibi bulundu). Aksi →
NON-SELECTIVE + tablo.

## 3. Kilitler

Tek koşu; analizör manifest (dal-eşlemesi, ağırlık-kaynağı,
episode'lar, koşullar) eşitliğini assert'ler. upl.py/pl_core
değişmez.

## 4. Fıkra — çift-sürüş kusuru (UN sadakat kapısı yakaladı, 2026-09-16)

us.py, UJ ile aynı kalıptan P3'ü tick başına 2× sürer + 2× tick
eder. Hüküm (NON-SELECTIVE) çift-sürüş rejimindedir → COMPROMISED.
Düzeltilmiş rerun: us2.py (tek-sürüş; UN sadakat hedefi us2 olur).
