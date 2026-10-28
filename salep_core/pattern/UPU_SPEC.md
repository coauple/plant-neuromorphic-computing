# UPU — Birleşik Pattern Unit, Gerçek Afferent (PRE-REGISTERED)

Tarih: 2026-09-16. Soru: P3, faz+zaman ilişkisine farklı elektriksel
davranış üretiyor mu? Girdi: donuk E0 kablosu
(encoder/out/aff300_afferent.csv — OKUNUR, değişmez). K1/K2/K3 +
P3, P0b ring kablolaması aynen. Öğrenme/C++ YOK.

## 1. Episode tanımı (P0 dersi: tekil spike sürmez)

Sıralı çift (X→Y): t0 = X olayı; X-treni = [t0,t0+60] arası TÜM X
olayları (≥2 olmalı); Y-treni = [t0,t0+120] arası TÜM Y olayları
(≥2 olmalı). Δt_episode = ilk-Y − t0. Besleme: gerçek tick/slot/
sayılar (göreli), amp=1.0 (gerçeklik korunur, yükseltme YOK).
Birim episode-başı SIFIRLANIR (yanıt yalnız (çift,Δt)'nin
fonksiyonudur). Rol: X→A-hattı, Y→B-hattı. Çift-dışı olaylar
YOK (minimalizm; tam-kablo sürekli-sürüş follow-up'tır).

## 2. Madencilik (kilitli prosedür, upu_mine.py)

Çift önceliği: (4,7) [φ120/φ210]; yoksa en çok episode'lu çift.
Kimlik çifti: (4,8) [φ120/φ240]; yoksa (4, en-çok-B).
Bin önceliği: tam {5} ve {20}; yoksa en-kalabalık iki bin
(|Δt1−Δt2|≥10 şartıyla), o da yoksa ABORT (rapor, ayar YOK).
Bin başına ilk 5 episode (tick sırası). Madencilik tren
istatistiğini raporlar (sayı/genişlik/ISI); seyrekse P3 sessiz
kalabilir — bu da bulgudur.

## 3. İmza + mesafe (kilitli)

İmza: göreli ateş tick'leri, sayı, max soma, max eff, n_coinc.
d = (ateş-kümesi farklı?1:0) + |Δsayı|/10 + |Δmax_soma| + |Δmax_eff|.
Aynı-bin içi yayılım (farklı gerçek episode'lar) GERÇEK ölçümdür
(sıfır-değil); eşikler: Δt-ayrışma ⟺ binler-arası merkez mesafesi
> bin-içi yayılım; kimlik-ayrışma ⟺ çiftler-arası > yayılım.

## 4. Kilitler

Tek koşu; madencilik+koşu+analiz manifest-hash ile bağlı;
analizör eşitliği assert'ler. Resonant yok (ring baz; follow-up).
