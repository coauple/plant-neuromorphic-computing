# P0c A/B Karşılaştırması (tanı-sonrası değerlendirme, 2026-09-16)

Kısıt: kavramsal; implementasyon YOK, C++ değişikliği YOK.
Karşılaştırma ölçütü: P0C_SPEC §2 tanı sonucu.

## Tanı özeti (p0c_diag.json)

- R1: K1B ateş örüntüsü φ'ya göre farklı (t=68: slot2 vs slot8);
  R1a/R2 aynı (beklenen: A-tarafı ve K2/K3 faz-kör).
- Sürülen-slot V + referans-slot V iki koşuda birebir aynı →
  nöron-başına elektriksel büyüklükte kimlik YOK.
- R3-ELEKTRİK (dal başına sayı/genlik) hep aynı → projeksiyon
  kanalı (tick, dal, sayı) taşır, slot taşımaz.
- R4 (P3 V/soma) hep aynı.
- HÜKÜM: KAYIP-PROJEKSIYONDA, alt-tip index-only identity.

## Aile değerlendirmesi

İki aile de doğru noktayı hedefliyor (projeksiyon); ayrım,
kimliğin HANGİ fiziksel boyuta taşınacağında:

A) Faz-seçici dendrit projeksiyonu — kimlik MEKÂNa taşınır
(ayrı kompartıman). Maliyet: Neuron 3 kompartıman kullanır ama
tavan 12 slottur (MAX_COMPARTMENTS) — sabit-boyut disiplini
içinde kompartıman eklenebilir, ancak soma denklemi (kök-odaklı)
ve topoloji kurulumu genellenmek zorunda. Öngörü: R3-elec
kompartıman-bazında ayrışır, R4 ayrışır, T-AMP geçer.

B) K1 alt-popülasyonuna ayrı yollar — kimlik ZAMANa taşınır
(yol-bağımlı gecikme; yakınsama somada). Maliyet: yol/nöron
sayısı + zamanlama kırılganlığı. Kritik not: izde slot ateş
ZAMANLARI da aynı (t=68 iki koşuda) — B, zaman farkını yoldan
ÜRETMEK zorunda, hazır bulmuyor. Öngörü: aynı R3/R4 ayrışması
+ T-AMP; başarısızlık kipi gecikme çakışmasıdır.

## Karar için gerekli ikinci-kanıt (henüz yok)

Mevcut tanı A ile B'yi ayıramaz (ikisi de R3/R4 ayrışması
öngörür). Ayıracak kanıt: T-AMP'yi geçen minimal prototipin
maliyet/gerçeklenebilirlik karşılaştırması — bu P0c kapsamı
DIŞIdır (ayrı hipotez ister). Tanı "HİÇ-İŞLENMEDİ" deseydi
ikisi de yetersiz kalırdı (koşul kaydı).
