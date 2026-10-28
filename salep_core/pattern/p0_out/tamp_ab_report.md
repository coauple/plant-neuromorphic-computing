# T-AMP A/B Karşılaştırma Raporu (2026-09-16)

Hüküm: A=KORUMAZ, B=KORUMAZ (kilitli T-AMP kriteri; tamp_metrics.json).
Kazanan ilanı YOK. Sürüşle oynanmadı.

## Kriter uygulaması

- A: çapraz-faz (dt10: 2 readout + Linf 1.81) < genlik-kontrol
  (12 readout + Linf 2.35). n_in eşit (11/11) ama ortak-kip
  (K2/K3) kazancı kimliği boğuyor: %25 sürüş değişimi 12 readout'u
  da oynatıyor, faz değişimi 2'sini. Yapı VAR (12/12 ölçek-durumu,
  eşleşen readout), sağlamlık YOK.
- B: çapraz-faz dt30'da kontrolü geçiyor (2.04 > 1.76) ama dt5/dt10'da
  kalıyor; sistematiklik şartı düşer. Ek konfounder: n_in eşitsiz
  (9 vs 10 — sayı-konfoundu) ve varış öngörüsü tutmadı (48 ≠ 42).

## 10 ölçüm özeti

1 Determinizm: ikisi de OK (2× bit-eşit). 2 Ayrım: A kısmi
(2 readout), B kısmi (ateş-kümesi+eff_g). 3 Zamanlar: B varış
farkı 48 tick (öngörü 42 — hop gecikmesi sürüş-bağımlı). 4 Soma:
yukarıda. 5 Aynı-Δt: A dt10/30'da, B dt30'da ayrışıyor. 6 Δt-boyu:
ikisinde de korunmuyor (sistematik değil). 7 Asimetri: ikisinde
de >0 (A'da büyük: 12 readout — sıra ortak-kipi taşıyor). 8 Ölçek:
12/12 ikisinde de (durum sayısı; A'da hangi-readout, B'de
varış+zaman). 9 Karmaşıklık: A 41 nöron (12 readout), B 54 nöron
(24 röle) — ikisi O(N). 10 Taşıyıcı: A mekân, B zaman (öngörülen).

## Mekanik hüküm

Faz kimliği K1'de indeks-olarak var; A onu mekâna, B zamana
çevirmeye çalıştı. İkisi de kimliği YALNIZ taşıyamadı: A'da
ortak-kip kazancı, B'de sayı-konfoundu + durum-bağımlı gecikme
kimliğe bindi. T-AMP kriteri işini yaptı: yalnız `fire_tick`
farkını başarı saymadı. Sonraki hipotez ya ortak-kip yalıtımı
(A-yönü) ya sayaçtan-bağımsız zaman imzası (B-yönü) hedeflemeli —
ikisi de bu turun dışı.
