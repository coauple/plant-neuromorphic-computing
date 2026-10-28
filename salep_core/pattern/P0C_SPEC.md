# P0c — K→P3 Projection Bottleneck Tanısı (PRE-REGISTERED, 2026-09-16)

Statü: analiz/diagnostic modu. Mimari çözüm SEÇİLMEZ, implemente
EDİLMEZ, C++ değişikliği YOK, P0/P0b dosya+verisi donuk.
Amaç: P0b bulgusunun (φ60≡φ240 P3 girişinde) çöküş noktasını
mekanik olarak bulmak.

## 1. Referans zinciri (kayıt noktaları, φ60 vs φ240)

R0 FDM-çıktısı referansı = enjekte edilen faz slotu (s2 vs s8;
P0b tren rejimi: n=5, ISI=12, amp=1.0, φ_A=120 sabit, ring mod).
R1 K1 A/B-bank 12-bit ateş vektörleri + sürülen-slot V/g izi.
R2 K2/K3 ateş bitleri (faz-kör kontrol).
R3 Projeksiyon: P3'e giren darbe vektörü (tick, dal, kaynak slot).
R4 P3 V[0..2], g0, soma, coinc, ateş.

## 2. Karar kuralları (koşudan önce kilitli)

- K1 örüntüleri (hangi slot) φ'ya göre farklı, R3 vektörleri aynı
  → KAYIP PROJEKSİYONDA (aile B'nin hedefi).
- R3 vektörleri farklı ama R4 izleri aynı → KAYIP P3
  ENTEGRASYONUNDA (ortak-reset/difüzyon şüphesi).
- R1 örüntüleri bile aynı → HİÇ İŞLENMEDİ (şüphe K1/enjeksiyona
  kayar; projeksiyon aklanır).
- Eşik-altı V farkı var ama spike örüntüsü aynı → bilgi spike
  öncesi var, spike-projeksiyonu kaybediyor (kayıp-alt-tipi).
- Yasaklar: merkezi `if phase == ...`, etiket taşıma, CPU
  phase-distance — tanı bile bunları kullanmaz (slot karşılaştırma
  yalnız raporda, bit-dizisi eşitliği olarak).

## 3. Kabul testi tasarımı T-AMP (gelecek çözüm adayları için,
P0c'de KOŞULMAZ — koşulacak aday yok)

Aday çözüm "P3-gözlenen durum φ'ya göre ayrışıyor" iddiasıyla
gelirse: (i) φ60 vs φ240 aynı spike-count'ta ayrışmalı; (ii) aynı-φ
amp-varyantları (adaya eşit spike-count verecek ölçekte) arası
mesafe, fazlar-arası mesafeden KÜÇÜK olmalı (kimlik > genlik).
Biri kalırsa aday "yeni genlik farkı"dır, faz kimliği değil.

## 2b. Fıkra — R3 düzeltmesi (tanı-kod incelemesi, sonuçtan bağımsız)

R3 "darbe vektörü (tick, dal, kaynak slot)" kaydında kaynak slotu
tanı-etiketidir, kanal içeriği değildir (§2 yasakları gereği).
Hüküm girdisi R3-ELEKTRİK'tir (dal başına darbe sayısı/genlik);
kaynak-slot karşılaştırması R3-ETİKET adıyla yalnız raporlanır.
İlk koşudaki "KAYIP-P3-ENTEGRASYONUNDA" çıktısı bu karışımın
eseriydi; düzeltilmiş kural aynı izde yeniden koşulur.

## 4. Aday aileler (kavramsal; implementasyon YOK)

A) Faz-seçici dendrit projeksiyonu: FDM-çıktısı faz, ayrı
dendritik yollara elektriksel ayrışır; K bilgisi faz
kompartımanlarında korunur. Kısıtlarla gerilim: Neuron 3
kompartımanlıdır — A, kompartıman sayısını veya nöron sayısını
artırmadan ifade edilemez; maliyeti dürüstçe yazılır.

B) K1 faz-alt-popülasyonuna ayrı elektriksel yollar: slot kimliği
ortak toplamada çökmeden soma-öncesine ulaşır (örn. faz-başına
ara-nöron/gecikme çizgisi, yakınsama yalnız somada + zaman imzasıyla).
Maliyeti: nöron/yol sayısı, zamanlama kırılganlığı.

İkisi için de: merkezi faz karşılaştırma yok, etiket yok, aynı
spike/tick mekanizması, Neuron morfolojisi azami korunur.
Karşılaştırma, §2 tanı sonucuna karşı yapılır (çöküş neredeyse
orayı hedefleyen aile öne geçer; tanı "hiç işlenmedi" derse
ikisi de YETERSİZ kalır — bu da raporlanır).
