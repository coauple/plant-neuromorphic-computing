# T-AMP — K→P3 Faz Kimliği Taşıma Karşılaştırması (PRE-REGISTERED)

Tarih: 2026-09-16. P0/P0b/P0c donuk; verilerine dokunulmaz.
Çözüm SEÇİLMEZ; öğrenme YOK; C++ değişikliği YOK; minimal float
prototip. Soru: K1'de ayrışmış faz kimliği P3'e elektriksel
olarak taşınabiliyor mu, hangi fiziksel değişkenle?

## 1. Ortak zemin (iki prototipte aynı)

Girdi: P0b treni (5 darbe, ISI=12, amp=1.0, t0=50, ufuk 200).
K katmanı: P0b ring aynısı (ortak sürücü, faz başına aynı iz).
K2/K3 ortak-kipli (doğrudan, ekstra gecikmesiz). Nöron
parametreleri P0b ile aynı; besleme genliği her yerde 1.0 —
TEK İSTİSNA B röle bağlantıları (2.0, gerekçe §3).

## 2. Prototip A — spatial (yer-kodu)

12 readout nöronu (standart 3-kompartıman morfolojisi, P0b P3
parametreleri). Readout-s: Dal-A ← k1A[s] spike'ları, Dal-B ←
k1B[s] spike'ları (+ K2/K3 ortak-kip). Gözlenen durum = 12
readout soma izi + ateş matrisi. Etiket YOK: hatlar anatomik,
merkezi faz karşılaştırması yok. Maliyet/ölçek raporlanır
(N slot → N readout; 12-sınırı §5).

## 3. Prototip B — temporal (yol-gecikmesi)

Dal başına 12 röleli zincir (entegratör morfoloji — FIKRA:
"standart" gerekçesi ölçüyle çürütüldü: tek@2.0 K1 0.871/K2
0.723 sessiz, K3 1.017 ateşler. Röle çevirme-görevi gereği
K3-usulü düşük-sızıntılıdır; bu bileşen kararıdır, faz-sonucu
ayarlaması değil — 1-girdi-1-çıktı assert'i aynen durur). Slot-s,
zincirin s konumuna anatomik tap'lanır (tonotopi emsali §9.15 —
CPU `delay=f(phase)` YOK, gecikme spike'ların hop'lamasından
doğar); sinyal s→…→11→P3-Dal akar. Röle önkoşulu (b_start
assert'i): izole tek-darbe → tam 1 spike, L tick gecikme
(gerekçe: P0b-E6 tek@2.0 standart nöronu ateşledi; tren
sonucu DEĞİL bileşen şartı). Öngörü (kilitli): slot2/slot8
P3-varış farkı = 6L. K2/K3 doğrudan P3'e (ortak-kip).

## 4. Matris (prototip başına 26 koşul ×2 tekrar)

φ_B∈{60,240}×Δt∈{5,10,30} AB (6) + BA aynı (6) + 12-slot
süpürme Δt=10 (12) + genlik-kontrolü φ60 amp{1.0,1.25} (2).

## 5. T-AMP kriteri (kilitli)

(i) Aynı Δt/sırada φ60 vs φ240 sistematik + tekrarlanabilir
elektriksel ayrışma (EŞİT spike-count şartı aranır, yoksa
"sayıyla ayrışma" diye raporlanır). (ii) Fazlar-arası mesafe >
aynı-φ genlik-varyantı mesafesi (kimlik > genlik). Biri kalırsa
hüküm "yeni genlik farkı"dır. Yalnız `fire_tick` farkı PASS
sayılmaz. 10 ölçüm (§6) iki prototipte de raporlanır.

## 6. Ölçümler (her prototipte)

1 determinizm · 2 φ60/240 durum ayrımı · 3 spike zamanları ·
4 max soma/eff_g · 5 aynı-Δt ayrışma · 6 Δt-boyu korunma ·
7 sıra asimetrisi · 8 faz-sayısı ölçeklenmesi (12-süpürme:
kaç ayrı durum) · 9 karmaşıklık (nöron/yol sayısı, O(N)) ·
10 taşıyıcı değişken (A: hangi-readout, B: varış-zamanı).

## 7. Kilitler

Tek koşu; analizör manifest-prototip parametre eşitliğini
assert'ler; P0b-içi ayar yasağı burada da geçerli (P0c fıkrası
emsali). Kazanan ilanı ZORUNLU DEĞİL; ikisi de yetersizse
raporlanır. T-AMP negatifse hipotez düşer, sürüşle oynanmaz.
