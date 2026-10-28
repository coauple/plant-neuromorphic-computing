# bench/REPORT.md — Bağımsız değerlendirme raporu

Tarih: 2026-10-15. Kapsam: Aşama 0–9. Kriterler: `TEST_PLAN.md` (kör, dondurulmuş).
Komut: `bash bench/run_all.sh` (tahmini süre ~2 saat; her aşama tek tek koşuldu,
regresyonlar geçti; temiz-sıfırdan tam koşu bu oturumda yapılmadı — bkz. Sınırlar).

Atıf (gerçek veri): DesRosiers vd., "A library of electrophysiological
responses in plants", figshare DOI 10.6084/m9.figshare.25425920.v2, CC BY 4.0.

## Yönetici özeti — en önemli 5 bulgu (olduğu gibi)

1. **Demux'ta S, basit yöntemlerle başabaş ya da geride.** Temiz dünyada
   tau4: S 0.942, baseline'lar 1.000; tau12: S 0.799, B1/B2 0.800, B3 1.000.
   Farkın sebebi ölçüldü: harmonik yakalama (4|12 alt-harmonik PLIR kabulu;
   S-12 combo ile 4-only'yi ayıramıyor: alt-küme AUC 0.505 = şans).
2. **S seyrek-nedensellik dünyasında tamamen sessiz.** 12/12 hücrede
   precision=recall=0: neden-kanalı (pre0) izole 2-darbeli patlamalarla hiç
   ateşlemiyor. Şablon (periyodik) pre0=218 ile port sadakati doğrulandı;
   başarısızlık seyrekliğin, portun değil. Denetimli N2 kısmi skorla görevin
   çözülebilir olduğunu gösteriyor.
3. **PLIR her yerde faydalı değil; popülasyon bu metrikte gereksiz.**
   PLIR kapalıyken (eski-ISI) tau4 AUC 0.942→1.000'e ÇIKTI (FRESH-her-darbe
   yabancı-reddi kirletiyormuş); N_POP 8→1 AUC'yi değiştirmedi (0.9426/0.7973);
   coincidence bonusu demux'ta bit-bit etkisiz (Dal B boş — kod-kanıtlı).
4. **Genelleme şaşırtıcı iyi, gürültü tau4'e yarıyor.** Kalibre-dışı 9 tau'da
   ayarsız AUC ~1.0 (çiftlerde 0.885–1.0). Ekstra-darbe gürültüsü S-tau4'ü
   0.942→0.999'a yükseltti (hipotez: gürültü, yavaş-yabancıların FRESH
   yakalamasını bozuyor). Yarı-AUC noktası ızgara-dışında (çökme yok).
5. **Gerçek veride kimse ayrıştıramadı.** 36 Ocimum kaydında havuzlanmış AUC:
   S 0.493, varyans 0.455, HF-enerji 0.412 (n=483 pencere). Zayıf-etiket payı
   büyük (literatür: ~%60 yanıt + 3–6 sn gecikme). Bu bir çekirdek-hükmü değil,
   bir ölçüm-sınırı kaydıdır.

## Aşama sonuçları (kriter karşılıkları)

| Aşama | Kriter | Hüküm |
|---|---|---|
| 1 Harness/üreteç | H1–H4 | GEÇTİ (4/4) |
| 2 Demux | D1 | KALDI (0.871<0.90; tau4 0.942 GEÇTİ / tau12 0.799 KALDI) |
| 2 | D2 | KALDI (tüm medyanlar 3·tau üstü; kısmen cetvel-kusuru, metinde) |
| 2 | D3 | raporlandı (kritersiz): 12\|4 S=0.505, 4\|12 S=0.86 |
| 2 | D4 | GEÇTİ (ön-hesap; Aşama 8'de ölçüldü) |
| 3 Gürültü | N1 | GEÇTİ (24/24 hücre × 30 seed) |
| 3 | N2 | GEÇTİ ("çökmedi" raporu) |
| 4 Ablasyon | A1 | GEÇTİ (3 eşdeğerlik kanıtı bit-bit) |
| 4 | A2 | GEÇTİ (tablo eksiksiz + nedensellik sütunu taban-etkili) |
| 4 | A3 | GEÇTİ (etkisizler açıkça yazıldı) |
| 5 Genelleme | J1–J3 | GEÇTİ (12/12; bozuk yok; ayarsız) |
| 6 Nedensellik | C1 | KALDI (S 0±0 vs N3 0±0 çakışıyor) |
| 6 | C2 | raporlandı (0.0, sessizlikten triviyal) |
| 6 | C3 | GEÇTİ (12/12 hücre) |
| 7 Gerçek veri | R1–R3 | GEÇTİ (süreç kriterleri; sonuç zayıf) |
| 8 Maliyet | W1–W4 | GEÇTİ (ölçüldü; sentez yok→kağıt-üstü) |
| 9 Rapor | F1–F3 | GEÇTİ (7 şekil + bu rapor; run_all kablolu) |

## Aşama 2 — Demux (şekil 1)

Yöntem: 100-tick pencereler, 7 segment tipi (4/12/4+12/6/8/10/sessiz),
eşikler kalibrasyondan (Youden J), test n=30. Skor: S bant-ateşi, B1
gecikme-coincidence, B2 otokorelasyon, B3 Goertzel, B4 ISI-histogramı.

- AUC (test ort±std): yukarıda (bulgu 1). S-tau12'nin 0.7994'ü B1/B2'nin
  0.8000'iyle aynı harmonik tavan (4-only ve 6-only, 12-only'nin üstünde).
- Gecikme medyanı: S tau4 71 (292/352 yakalama), tau12 40 (341/341).
  D2 barı (12/36) tutmadı — hiçbir yöntemde: Youden eşiği ayrışmış veride en
  katı uca oturuyor (ölçülen patoloji) + 100-tick trailing tanımı. Dondurulmuş
  kritere göre KALDI; cetvel revizyonu yapılmadı (sonradan gevşetme yok).
- Ek: S tau4 60/352 başlangıcı hiç yakalayamadı (kilit güvenilirliği);
  baseline'lar %100 (geç de olsa).

## Aşama 3 — Gürültü (şekil 3)

24 hücre (pextra×jit) × 30 seed, grid_auc.csv eksiksiz. Yarı-AUC hiçbir
eksen/yöntem/hedefte ızgara-içinde değil. B4 en kırılgan (p30j30'da tau4
0.851, tau12 0.524). S-tau4 artışı (0.942→0.999) hipotez-etiketli (bulgu 4).

## Aşama 4 — Ablasyon (şekil 4)

Altyapı: bench/ablate/src tam-kopya + 3 #ifdef (bonus/trace/count);
makrosuz kopya 3 probda bit-bit aynı (A1). Demux tablosu
(results/stage4/ablation_demux.csv):

- noplir: tau4 1.0000±0.0000 (d−0.0577 İYİLEŞME), tau12 0.7500±0.0041 (d+0.0494).
  Not: plir_mode=0 eski-ISI kapısıdır, kapısızlık değil.
- npop1: 0.9426±0.0313 / 0.7973±0.0065 (~etkisiz).
- nobonus: bit-bit aynı (etkisiz, kod-kanıtlı).
- notrace: demux'ta yapısal N/A.
- Nedensellik sütunu (ablation_causal.csv): tüm düşüler +0.0000 — TABAN ETKİSİ
  (baz zaten 0); "mekanizma önemsiz" okunamaz, "ölçülemez" okunur.

## Aşama 5 — Genelleme (şekil 5)

Kalibre-dışı 9 tekil + 3 çift, parametre değişmeden. Tekiller ≈1.0;
çiftlerde harmonik alt-skorlar (tau10 0.902 @5+10, tau14 0.885 @6+14).
Bozuk (<0.7) YOK. Ayarlı sütun yok — ayarlama yapılmadı.

## Aşama 6 — Seyrek nedensellik (şekil 6)

Kablo: main_causal_afferent birebir (sabitler dahil), olaylar seyrek-dünya.
12 hücre × 30 seed + X-yok kontrol + ablasyon. S tüm hücrelerde 0/0
(neden-kanalı sessizliği; teşhis metinde). C1 KALDI. N2 kısmi başarılı
(görev çözülebilir). Eşit-bütçe eşitleme S hızına (0) çapalandığı için
N1/N3 dejenere — aynen raporlandı, sonradan çapa değiştirilmedi.

## Aşama 7 — Gerçek veri (şekil 7)

Arama günlüğü REAL_DATA_SEARCH.md'de. figshare 25425920 (CC BY 4.0, md5
doğrulandı). Boru hattı: 10 kHz→100 Hz (tick=10 ms, açık) →
delta-modülasyon (THETA=16, 2 kalibrasyon kaydından) → tau12 tek-bant S +
varyans/HF baseline'ları; 36 test kaydı, zayıf pre/post etiketleri.
Havuz: S 0.493, B-var 0.455, B-hf 0.412 (n=483). Kayıt-bazında saçılım var
(Munich_3 B-hf 0.9) ama havuz şans seviyesinde. Hüküm: ayrışma iddiası YOK.

## Aşama 8 — Donanım maliyeti (ölçülen)

- sizeof: Nöron 516 B (çoğu double parametre+padding; GERÇEK durum ~50 B),
  Sinaps 24 B, FDM-2×8 ağı 21.7 KB, LUT G/Q 3844+3844 B, S 260 B (toplam 7.9 KB).
- Gözlenen durum aralıkları (temiz demux, 16800 tick): V [−0.20, 0.98],
  gating [0, 36.05] (KAPAKSIZ — HW'de doyum şart, bu bir üst-sınır DEĞİL),
  soma [−1.31, 1.00]; ağırlık [0.4, 2.0] (W_MAX'ta doyuyor).
- Asgari bit (marjlı öneri, 16-bit sınıfı): V S1I1F14, gating U6I10 (+doyum),
  soma S1I2F13, ağırlık U2I14, iz U1I15. Mevcut: 32-bit Q16.16.
- İşlem (FDM 2×8, sayaçla): 176.8 mul + 0.80 div /tick (init hariç; init
  fixed-op içermiyor — fdm_init double kullanır). Toplama/karşılaştırma
  statik tahmin ~224/tick (ölçülmedi, etiketli).
- Baseline yan-yana: B1 0 mul/~20 b; B2 1 mul/1.6 Kb; B3 2 mul/~100 B;
  B4 karşılaştırma+sayaçlar. S en pahalısı (16 nöron × ~11 mul).
- Sentez: araç YOK (vitis/vivado/yosys/nextpnr/openlane/qflow) → tüm HW
  sayıları kağıt-üstü/ölçümsel; sentez sonucu ÜRETİLMEDİ.

## Sınırlar ve dürüst notlar

- Tohum disiplini: eşikler/kalibrasyon yalnız seed 1000–1009 veya ayrı
  kalibrasyon kayıtları; rapor sayıları test kümelerinden. İhlal yok.
- Sentetik sınırı: Aşama 2–6 dünyaları üreteç-yapımı (LCG); sonuçlar bu
  dünyaların içinde geçerli, tarla/klinik iddiası yok.
- Zayıf noktalar: D2 cetvel patolojisi; Aşama 6 bütçe-çapası dejenereliği;
  gerçek-veri zayıf etiketleri; gating kapaksızlığı; div/tick mekanizması
  atfedilmedi (0.80 ölçüldü); fdm_init double kullanıyor (P1).
- Yapay zeka notu: bench/ altındaki harness/üreteç/analiz/şekil kodları yapay
  zeka yardımıyla yazıldı; çekirdek (src/) önceden mevcuttu ve hiç
  değiştirilmedi (9/9 regresyon geçti). Tüm sayılar deterministik
  yeniden-üretimle (`run_all.sh`) doğrulanabilir.
- Doğrulanmamış iddialar: stokastik-maskeleme hipotezi (A3); pre2-ateşleme
  sızıntı-asimetrisi açıklaması (A6, el-hesabı); bit-genişliği önerileri
  (tek iş-yükünden); sentez sayıları (araç yok).

## Beklenmedik bulgular ve belirsizlikler

Beklenmedik: gürültü-tau4 artışı; noplir-tau4 1.0; npop1 etkisizliği;
ayarsız genellemenin mükemmelliği; S'nin seyrek-nedensellikte tam sessizliği;
gerçek-veride tüm yöntemlerin şans-seviyesi. Belirsiz: yukarıdaki zayıf
noktalar + ağırlık doyumu (2.0) tasarım-mı/doygunluk-mu sorusu (Cevaplanmadı:
tasarım-dışı gözlem olarak duruyor).
