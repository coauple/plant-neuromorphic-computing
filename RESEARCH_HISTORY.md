# Araştırma Geçmişi (Research History)

Bu belge kısa kronolojidir; ayrıntılı ve yorumlu anlatım için [README.md](README.md) §1 ve §7.

Bu belge, projenin nasıl geliştiğini yalnız mevcut kayıtlardan
(`salep_core/CLAUDE.md`, `CONTRACT_EVIDENCE.md`,
`DENETIM_RAPORU_2026-10-14.md`, `bench/REPORT.md`, test dosyaları) özetler.
Tarihi belgede yazmayan olay tarihsiz aktarılır; doğrulanamayan iddia
"doğrulanmadı" diye işaretlenir.

## 1. Problemin ortaya çıkışı ve hedef

Eylül 2026 geliştirme kayıtlarının başlangıcında, bitki biyoelektrik
olaylarını işlemeye yönelik, çok kompartımanlı ve ileride FPGA'ya taşınması
hedeflenen bir nöromorfik hesaplama çekirdeği tanımlanmıştır
(`CLAUDE.md` §1–2). Üç katmanlı şema kayıtların başında
kuruldu: faz çözümleme → rekabetçi
kümeleme → çapraz-bant nedensellik; CPU yalnız özet okur, ham veriyi yorumlamaz.

Kurucu yöntem dersi de erken yazıldı (§0): geçmişte "14 nöron 36 faz alanını
sıfır hatayla okur" gibi iddialar test edilmeden mimariye sabitlenmişti. Kural:
sayısal iddia önce küçük bir Monte Carlo denemesiyle doğrulanır, yoksa koda
`TODO: DOĞRULANMADI` yazılır. Donanım kısıtları da baştan kondu: Q16.16 sabit
nokta, dinamik bellek yok, LUT tabloları, deterministik tick.

## 2. İlk mekanizmalar: tek nöron → sinaps → küçük ağ (Eylül başı)

Geliştirme "önce tek nöron + iki dal, CSV ile doğrula, sonra büyüt" akışıyla
yürüdü (§6). Sıra kayıtlardan izleniyor: kompartıman/nöron çekirdeği
(`compartment.h`, `neuron.h`), kuadratik sinaps kuralı `dw = eta·G·Q·S`
(§9; `synapse.h`, `main_synapse.cpp`), açık/kapalı döngü ve akım aktarımı
testleri (§9.4: L0/L1/T1/T2), üç-sinapslı Katman-1 ağı (§9.5: monoton öğrenme,
1.71× davranış değişimi, 2.26× multiplex kazancı). Bu bölümlerin kayıtlarında
tarih yazmaz; incelenen teknik geliştirme kayıtlarındaki ilk tarihli kayıt
2026-09-08'dir (§9.9). Doğrulama disiplini her
adımda aynıydı: Monte Carlo önce, C++ sonra, CSV + matplotlib ile görsel kanıt.

## 3. Faz seçiciliği: TDM deneyi, dürüst sınır, PLIR/FDM kararı

Dört tau-ayarlı nöron + birleştiriciyle ardışık-pencere ayrıştırma (TDM)
denendi: bant-içi ≥%98,8, rakip oranı ≥80× (§9.6, `main_phase_group.cpp`).
Kayıt bu başarının yanına sınırı da yazdı: bu TDM'dir, simultane FDM değil.
Ardından nedensellik köprüsü (§9.7) ve Q(Δt) taraması (§9.10) geldi; tarama
"~düz" çıktı ve hız-eşzamanlılığı devresi olarak dürüstçe yorumlandı.

Kırılma §9.8'de: kök neden bulundu — eski ISI kapısı teli vuran her darbeyle
tazeleniyor, yavaş bant yabancı darbede boğuluyordu. Çözüm PLIR oldu (yalnız
kabul edilen darbede güncellenen rezonans hafızası) + bant başına 8 üyeli
popülasyon; iki ritim aynı tele süperpoze edildi (`main_fdm.cpp`). Sonuçlar
ölçüldü (kilit, kapsama, faz kayması ≤0.03 tick) ve beş dürüst sınır yazıldı:
harmonik-faz takibi yok, alt-harmonik sürüklenme, 3. bant yok, tohum-duyarlılık,
deterministik-ızgara koşulu.

## 4. Duyusal lob ve bitki simülatörüyle bütünleşme (8–15 Eylül)

8 Eylül'de koşul öğrenme (Pavlov/grounding) eklendi: frekans bandı + sensör
çifti, negatif kontrollü (§9.11, `main_plant_npu.cpp`). 9 Eylül'de kritik bir
olumsuz sonuç mimariyi değiştirdi: 7 kanalın tek tele süperpoze edilmesi §9.8
sınırlarına takıldı; karar **dual-rail** oldu — frekans Rail-F'de, kanal kimliği
Rail-C sayaçlarında (§9.12). Aynı gün canlı terminal ve akış modu yazıldı.

Sonra duyusal lob v2 (P1 faz hatları + 10 üyeli P2 koşul bankası, §9.14),
öz-örgütlenen banka (§9.15) ve stres testi (§9.16) geldi. 11 Eylül'de kullanıcı
onayıyla büyük yeniden yapılanma: Godot/Qt/Streamlit yolları emekli edildi,
simülasyon `sim/` paketine taşındı, web katmanı kuruldu (§9.19–9.21).
11–14 Eylül'de web panelleri, gerçek Aydın hava verisi, UV/şema-v2, fiziksel su
modeli (9 adım, §9.36–9.44), pertürbasyon bataryası ve simülatör doğrulaması
eklendi. 14–15 Eylül'de TEST B zinciri (fizik→elektro→duyusal→afferent, §9.59),
ilişki/çıkarım çekirdekleri ve tanı deneyleri koşuldu; 15 Eylül'de v1 donduruldu
(§9.85, `V1_BASELINE.md`).

## 5. Örüntü lobu ve koşul temsilleri (16–23 Eylül)

16 Eylül'de lob sözleşmesi yazıldı (`CONTRACT_EVIDENCE.md`): 11 iddia B1–B11
olarak etiketlendi (kanıtlandı/kısmen/hipotez/gözlenmedi). Örüntü lobu v2
(K1/K2/K3 yolları, 29 birim) deneylerle karakterize edildi; 19–20 Eylül'de K4
ilişkisel yolu eklendi (REV3 bataryaları → REV4 gerçek K4, §9.90–9.97) ve lob
donduruldu (§9.102/9.109/9.114). 21 Eylül'de canlı zincir
(sim→duyusal→koşul→örüntü) yayına bağlandı (§9.110–9.113); 24–28 Eylül'de sinyal
paneli eklendi (§9.115–9.116).

Koşul temsillerinin bilançosu karışıktır ve öyle kaydedildi: sentetik uyaranla
koşullanma + sensörsüz yanıt gösterildi; ama örüntü belleği üzerinden çıkarım
duyusal tabanı geçemedi (0.310/0.356'ya karşı 0.554, B10 "gözlenmedi").
Sınıflandırma skorları ile faz-seçiciliği değerlendirmeleri ayrı tutuldu (bkz.
README'deki yöntem notu).

## 6. Başarısız deneylerin tasarıma etkisi (seçki)

- TDM sınırı → PLIR + simultane FDM (§9.6 → §9.8).
- Tek-tel 7-bant imkânsızlığı → dual-rail (§9.12).
- Monte Carlo ile çürütülen değerler (`burst 2`, decoy yerleşimi, `w0≥0.3`)
  elendi; eşikler veriden önce sabitlendi, oynanmadı (§9.14).
- Ortanca-hayaleti (olmayan tonun işe alınması) → doğrudan-kanıt şartı,
  iki motora da eklendi, eski CSV değişmedi (§9.16).
- Kuadratik varyantların tabanı geçememesi → kural donduruldu, tanı kollarına
  dönüldü (§9.71–9.72, §9.76–9.84).
- TEST B'de CR üretilememesi (CR_YOK) → kapalı çevrime geçilmedi, hüküm olarak
  yazıldı (§9.59, denetim raporu §6).
- Ekim bağımsız değerlendirmesinde KALDI hükümleri (demux D1/D2, seyrek
  nedensellikte sessizlik, PLIR ablasyon sürprizi) rapora aynen girdi;
  yumuşatılmadı (`bench/REPORT.md`, `TEST_PLAN.md` G5 kuralı).
- 28 Ekim'de taze derlemenin Eylül CSV'leriyle bit-bit tutmaması, kanonik
  sayıların "kayıtlı binary" koşuluna bağlanmasına yol açtı
  (Ekim 2026 yeniden-üretim denetimi, yerel arşivde).

## 7. Ulaşılan aşama (Ekim 2026)

Erken prototipler aşaması. Taze derlemeden tam üretilenler: örüntü lobu
`mem/log`, nöron izi; kısmi: bitki NPU (özet 4/4 OK, CSV bit-farklı); taze
derlemede üretilemeyen: duyusal lob `A=OK` (yerine `A=UYARI`). Tek-yörünge,
döngüsel-etiket ve sessizlik-kararı sınırları denetim raporunda açık (§4–7).
Sistem tamamlanmış bir stres-tanılama, kavramsal-çıkarım veya öngörü mimarisi
**değildir**.

## 8. Gelecek hedefler

Öğrenilmiş koşul temsillerinden **kavram oluşturma ve türetme**, **kavramsal
çıkarım**, **nedensel modelleme** ve **öngörü** — henüz bütünleşik ve
doğrulanmış biçimde geliştirilmedi. Önkoşul borçları kayıtlarda duruyor:
bağımsız yörüngelerde tekrar, sessizliğin karar olması, örüntü belleğinin
çıkarıma katkısının ölçülmesi, gerçek bitki kaydıyla temas.

## Üretim notu

Kodların yazımında yapay zekâ araçları yoğun kullanıldı; araştırma soruları,
deney tasarımları ve mimari kararlar kullanıcı tarafından yönlendirildi
(kayıtlardaki "kullanıcı onayı/isteği/kararı" notları). Bağımsız doğrulama
sürüyor: kör plan, denetim raporu, yeniden-üretim kontrolü.
