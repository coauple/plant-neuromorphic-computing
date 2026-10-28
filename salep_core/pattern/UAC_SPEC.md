# UAC — Birleşik-Koşul Kabul Testi (PRE-REGISTERED)

Tarih: 2026-09-16. Soru: P3, K1+K2+K3'ün zamansal-elektriksel
birleşik konfigürasyonuna seçici mi, tek-kanal da ateşletiyor mu?
Kural: birleşik koşul gerekli (yeterli-değil değil) olmalı —
solo-K3 P3'ü ateşletirse seçicilik YOKTUR. Beklenti (açık):
UPL ölçümü solo-K3 ateşlemesi gösterdi; FAIL şaşırtıcı olmaz.

## 1. Prosedür (kilitli)

UPU episode'ları (salt-okunur), episode başına: sıfır UplUnit
(w0) → 20 tur sürekli maruziyet, öğrenme AÇIK (UPL rejimi aynen)
→ HER P3 spike'ı için geriye-30-tick K-konfigürasyonu: K1/K2/K3
sınıflarından hangileri ateşledi? Sınıflar: JOINT (üçü de),
K3-alone (K1&K2 sessiz), diğer-kısmi.

## 2. Hüküm (kilitli)

SELECTIVE ⟺ ≥1 JOINT spike VAR VE solo-K3 spike YOK.
Aksi → NON-SELECTIVE + profil tablosu (sınıf başına sayı).
Eşik-tartışması YOK (sıfır-tolerans kuralı yukarıda).

## 3. Kilitler

Tek koşu; analizör manifest (UPL parametreleri + tur + pencere
30) eşitliğini assert'ler. upl.py/UPU değişmez.
