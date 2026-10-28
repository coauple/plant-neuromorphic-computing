# Bilimsel Deney Hazırlığı — Sistem Denetim Raporu

Tarih: 2026-10-14. Kapsam: salt-okunur denetim, kod/test değiştirilmedi.
Anayasa: `salep_core/CLAUDE.md` (§0–§9.116, 3058 satır).
Yöntem: kaynak okuma + mevcut CSV'lerin `/tmp`'de salt-okunur sayımı.
Hiçbir `validate_*.py` çalıştırılmadı (CSV'leri ezerdi).

## 1. Zincir haritası (kod üzerinde takip)

Akış: bitki fiziği → elektro → duyusal lob → afferent kablo → association → çıkarım → örüntü lobu → canlı zincir.

### Katman girdileri, çıktıları, etiketler

- **Fizik** — `sim/plant_sim.py::run_population`
  Girdi: `seed=1`, `scripted_events` (TEST B).
  Çıktı: DataFrame (temp, rain, soil_moisture, soil_ec, water_balance, leaf/root, stage, tuber_mass) + `ground_truth_events` (rebirth vb).
  Etiket: `ground_truth` NPU'ya gitmez (K6). Kanıt: `sim/frame.py` şema v2'de bu anahtarlar yok.

- **Sensör eşleme** — `sim/sensor_map.py::SensorMapper.update`
  Girdi: fizik snapshot (temp, rain_mm, soil_moisture, soil_ec, tuber_mass).
  Çıktı: 7 kanal hs/ts/hn/tn/ph/npk/ec (0–100).
  Etiket: yok. Not: hn/ph/npk `TODO: DOĞRULANMADI` türetme; `noise_std=0` → deterministik.

- **Elektro** — `sim/electro.py::ElectroState`
  Girdi: temp, rain, irrig, water_balance, leaf/root, stage, master_seed, day.
  Çıktı: `V_mV`, `rate0`, `burst1` → `spikes_for_day` → hat0/hat1 tick listeleri (gün=50 tick).
  Etiket: yok (K7: yalnız darbe bayrağı). RNG: `master+gün+hat` deterministik.

- **Duyusal lob** — `src/main_sensory_plant.cpp` + `src/sensory_lobe.h`
  Girdi: `testb_spikes.csv` (day,line,tick) + `testb_sensors.csv` (day,hn,ec,hs,ts,tn,ph,npk).
  P1: bitki darbesi → PLIR-A (tau 4/12, bw=1) → P1 ateşi.
  B: koşullamada `v>=50` ve `t%tau(v)==0` → Dal B; testte B=0.
  Öğrenme: kuadratik `dw=eta*G*Q*S`, eta=0.30, RATE_WINDOW=30.
  Çıktı: `testb_conditions.csv` (12500 satır: tick,blok,kademe,p1a,p1b,p2bits,w) + `testb_afferent.csv` (300 kayıt: tick,post_id,tau_b,a0lag,a1lag,bmask,bwin,label,w).
  Etiket ÜRETİMİ: `label` burada doğar — `sl_condition_label` ateşleyen kümeden yazar (örn. `p2a(p2c,p2d)`). Dünya koşulu DEĞİL, temsil-etiketidir.

- **Association** — `sim/assoc.py`, test `validate_assoc.py`
  Girdi: afferent kablo. Pencere: `tick//50` → gün imzası {posts,blines,a}.
  Benzerlik: ağırlıklı Jaccard 0.5/0.3/0.2. Sınıflama: LOO 1-NN.
  Etiket: `window_label(posts)` → true/decoy/mixed (REALS={0,1,2,5,6,7,8,9}, DECOY={3,4}). Banka tanımından, öğrenmesiz.
  Çıktı: komşu gün + benzerlik + tahmin.

- **Çıkarım** — `validate_inference.py` (+k5, quadratic, temporal-window varyantları)
  Girdi: aynı imzalar, k=3 sıra-koruyan pencere.
  Etiket: dünya koşulu WINDOWS (normal/kurak/şiddetli/sulama/recovery/yaz). Yalnız skorda, modele girmez.
  Çıktı: 6x6 confusion.

- **Örüntü lobu** — `src/pattern_lobe.h`, `src/main_pattern_lobe.cpp` (donuk §9.114)
  Girdi: AFF (tick,post,tau). Çıktı: mem/log + `OZET-PATTERN-LOB`.
  Etiket: girmez. Testler: determinizm/sınır, doğruluk yok.

- **Canlı zincir** — `sim/sensory_chain.py`, test `validate_sensory_chain.py`
  Girdi: sim karesi → SET → sensory `--stream` → T satırı → AFF → pattern `--stream`.
  Çıktı: pencere dosyaları + OZET/STATE + `chain.log` + panel snapshot.
  Etiket: yok. Pencereler-arası w/T/r yaşar (E-1); batch'te tazeydi.

Görsel: `denetim_grafik.html` (bu klasörde, çevrimdışı tek dosya).

## 2. Etiket akışı özeti

- Dünya etiketi (kurak/normal/...) hiçbir sim girdisine ve NPU'ya girmez. Kanıt: `validate_sensory_repr.py::WINDOWS` yalnız analizde; B kuralı sensör değerinden (`main_sensory_plant.cpp:306-311`); P1 yalnız spike'tan.
- Banka etiketi (true/decoy/mixed) temsilden türetilir ve aynı temsille test edilir → döngüsel (Bölüm 4).
- Koşul etiketi (`p2a(...)`) ateş kümesinden yazılır, yorumdur.
- Gizli etiket sızması BULUNAMADI; döngüsel etiket VAR (farklı şeyler).

## 3. Test envanteri (ne test ediliyor, ne edilmiyor)

Bağımsızlık notu: aşağıdaki hiçbir doğruluk testi bağımsız koşu kullanmaz. Hepsi tek TEST B yörüngesi (seed 1, 1 bitki, 250 gün) üstünde LOO veya determinizm bakışlıdır.

### Çekirdek zincir testleri

- **validate_testb.py** — B1 sürüş>1500, B2 şiddetli>8x normal, B3 recovery düşüşü, B4 afferent>200, B6 dw>0.02 → GEÇTİ. B5 CR → BULGU (CR_YOK, test ateşi 0). Etmez: CR başarısı, bağımsız senaryo.
- **validate_assoc.py** — S1–S5 → 163/165. Etmez: dünya-koşulu sınıflama, bağımsız veri (Bölüm 4).
- **validate_inference.py** — k=3, 97/175=0.554, kurak→N 28/28. I1 determinizm + I2 sızıntısız-örtüşme. Etmez: bağımsız koşu (aynı yörünge, örtüşmesiz pencere).
- **validate_quadratic_assoc.py** — 70/175=0.400, baseline'ı geçemedi. Etmez: bağımsız veri; tek eta/w0.
- **validate_temporal_window.py** — k=1/3/5/10/20 eğrisi, zirve k=3–5. Etmez: bağımsız veri.
- **validate_sensory_repr.py** — 67 exact imza / 165 ateşli gün; within 0.520 / between 0.277; LOO saflık 0.473. Salt-okuma karakterizasyon. Etmez: genelleme.
- **validate_condition_sweep.py / electro_sweep / plir** — koşul imzaları, 20 koşulda 16 imza, PLIR kabul/red sayımı. Karakterizasyon, genelleme değil.

### Öğrenme varyantları (hepsi baseline altı)

- **quad_mc** — 5 tohumda acc 0.400 sabit, std 0 → sabit nokta.
- **rownorm_quad** — 0.366 (daha kötü).
- **ltd_family** — 0.400→0.326→0.337→0.371 (monoton değil, hepsi kontrol altı).
- **retrieval / metric_limits / synergy / silence_mask / forensic / repr_ceiling** — tanı kolları; temsil ~0.92 saf ama metrik 0.55'te; kurak/normal ayırt-edilemezlik (34 pencere birebir aynı imza); B-sıkışması.

### Seyreklik / kalıcılık

- **validate_fdm_sweep.py** — F1–F6: L1==L320, W4==W80, G4==G800 (bit-eşit, yoğun rejim dahil). A-capture 303/1981=%15.3. SONUÇ: süreklilik makinesi bu rejimde katılmıyor.
- **validate_aonly.py** — C1–C4: yoğun+w0.5 → cond 700 + test 165 (kapasite VAR); seyrek hiçbir ağırlıkta ateşlemez (0); yoğun banka-ağırlığında ateşlemez (tavuk-yumurta). SONUÇ: A yolu doğru, persistence yetersiz.
- **validate_null_shuffle / rate_surrogate / ablation_boff** — P1a 286→285 (zaman-duyarsız), rate 0.446 vs temporal 0.554 (+0.108 mimari kazanç), B-off → P2 0.

### Örüntü lobu + canlı zincir

- **validate_pattern_lobe.py** — B/J/R/P/D/M/N/S: derleme + bit-identical + sentetik R1–R8 + determinizm + sınırlar. Doğruluk kapısı YOK; aynı TEST-B kablosu.
- **validate_chain_lobe.py** — C1–C4: k4 açık/kapalı çalışır + determinizm + varsayılan. Çökme/determinizm testi, doğruluk yok.
- **validate_sensory_chain.py** — SET eşleme + SPEC + smoke + mini-batch + 2 pencere + T monoton + akış + PLST A–E. Tesisat/determinizm testi, koşul-doğruluğu yok.

### Erken katman kalibrasyonları (sentetik uyaran)

causality, causal_afferent, fdm, plant_npu, sensory_lobe, sensory_plant, resonance — sentetik trenlerde mekanizma kanıtı (amplifikasyon, kilit, CR). Bitki-sürücülü genelleme iddia etmez.

## 4. 163/165 nasıl hesaplanıyor (doğrulandı)

Yöntem: `sim/assoc.py::classify` — LOO 1-NN, benzerlik=ağırlıklı Jaccard.

- Payda n=165: ateşli gün sayısı (250 günden 85 sessiz gün DIŞARIDA). Sessizlerin 30'u test fazının tamamı (CR_YOK rejimi skora girmez).
- Pay 163: doğru komşu-etiket sayısı. Kırılım: true 105/106, mixed 54/55, decoy 4/4.
- 2 hata (salt-okunur sayımla doğrulandı): gün 137 true→mixed (komşu 117, s=0.875) ve gün 172 mixed→true (komşu 160, s=0.875). İkisi de true/mixed sınırında, zıt yönlü (biri FP-benzeri, biri FN-benzeri; dosyada açık FP/FN sayımı YOK, yalnız sınıf-recall var).
- Etiket döngüselliği: `window_label` posts kümesinden, benzerlik de posts (+blines+a) kümesinden. Yani test, temsilin kendi tutarlılığını ölçer; dünya koşulunu değil. Komşu uzaklık ortalaması ~30 gün, 4 eşleşme bitişik gün (zaman-komşuluğu baskın değil ama aynı yörünge).
- Eğitim/test bağımsız DEĞİL: her sorguda referanslar aynı kablonun diğer günleri; ağırlık yörüngesi tüm katlara ortak (testb_conditions.csv 12500 satırda w evrimi tek koşu).

## 5. Sızma, gizli etiket, ezber, rastgelelik

- **Aynı dizi sızması: VAR (yapısal).** Assoc LOO aynı koşudan; inference örtüşmesiz pencere kullanır ama aynı koşudan; quadratic her sorguda aynı koşunun referanslarından öğrenir. Ağırlıklar, bitki hali ve sensör korelasyonu katlar arasında paylaşılır. Bağımsız koşu (farklı seed/senaryo) ile tekrar YOK.
- **Gizli etiket: YOK (dünya etiketi anlamında).** Sim girdileri etiketsiz; harness B/P1 kuralları fiziksel değerden; loblara etiket girmez. Döngüsel etiket (banka etiketi) VAR ama bu sızma değil, ölçüm-tasarımıdır.
- **Senaryo ezberi riski: YÜKSEK.** Tek script (`validate_testb.py`: MASTER=1, STAGES sabit, gübre 130 gün 60'ta, sulama 170/174/178'de). Skorların senaryo-dışı geçerliliği test edilmedi. Isı şoku bu çekirdekte düşmedi (stokastik), ısı ekseni ayrı TEST A'da.
- **Rastgelelik kaynakları (tümü deterministik):** `plant_sim` numpy RNG (seed); `electro` stabil RNG (master+gün+hat, PYTHONHASH bağımsız); `sensor_map` gürültü RNG (TEST B'de kapalı, std=0); C++ tarafında RNG yok. Sonuç: verilen seed'de bit-eşit tekrar; tohum-duyarlılık (seed sweep) ana skorlarda YOK. Bilinmeyen: farklı seed'de 163/165 ve 0.554 ne olur.

## 6. Seyrek olaylar ve FDM kalıcılığı (ölçülebilir açıklar)

- A-capture %15.3 (303/1981). Kayıp PLIR-A kilidinde + soma entegrasyonunda.
- P2 olaylarında B-bağlamı 291/300, A-geçmişi 103/300. Temsil B-baskın.
- FDM süpürme: sızıntı/pencere/gating eksenleri TÜMÜ bit-eşit (seyrek + yoğun). Ateşleme aynı-tick kombinasyonel; kalıcılık donanımı sonuca katılmıyor.
- A-only: seyrek 0 ateş (w0=banka ve 0.5); yoğun+w0.5 ateşler + CR üretir. Mimari kapasite ispatlı, seyrek rejim kapalı.
- TEST B: test fazı 0 olay (30 gün sessiz). CR kapısı kapalı; kapalı çevrime geçilmez hükmü (§9.59) geçerli.
- Başarısızlık örnekleri: kuraklık P1'siz temsil (19 olayın 19'u saf-B); 6 `neither` olay (A-yok B-yok ateş, gating kalıntısı); sulama=recovery kaba-imza çakışması; kurak⊂normal alt-küme yapısı.

## 7. Uçtan uca bağımsız test var mı?

HAYIR. Mevcut uçtan uca testler tesisat/determinizm testidir:

- `validate_sensory_chain.py`: sentetik SET + sentetik mini-AFF + pencere kapanışı + T monotonluğu. Dünya-koşulu doğruluğu yok.
- `validate_chain_lobe.py`: aynı TEST-B kablosuyla k4 açık/kapalı çalışırlık + sha eşitliği. Genelleme yok.
- `validate_pattern_lobe.py`: aynı kablo, eta=0, determinizm + sınırlar. Held-out yok.
- Canlı zincir ek sınırları: pattern pencereleri stream'de w/T/r taşır ama üretim eta=0 (ağırlık öğrenmesi donuk, r aktif); sensory 50 Hz serbest saat (sim-günüyle kilitli değil); T 25 tick'te bir örneklenir (ara atımlar panelde yok); resume dinamik hali sıfırlar (yörünge mikro-sapar).

Eksik olan: görülmemiş bitki yörüngesi (farklı seed/senaryo/yıl) → tüm zincir → dünya-koşulu tahmini, ön-kayıtlı metrikle.

## 8. İddia sınıflandırması

### Gerçek veriyle doğrulanmış

- Aydın Open-Meteo hava dosyaları gerçek gözlemdir (366 gün, boşluksuz). Sıcaklık/yağış/UV sütunları kullanılır. NOT: TEST B zinciri bunları kullanmaz (sentetik WorldDriver); gerçek hava yalnız web/canlı + G28/G28e kapılarında.
- Güneş geometrisi, takvim, determinizm/bit-eşitlik kapıları gerçek-kod kanıtıdır (fizik iddiası değil).

### Sentetik simülasyon sonucu (geçerli, ama tarla değil)

- Tüm NPU sayıları (163/165, 0.554, 0.400, kilit oranları, CR sayıları, FDM metrikleri). Hepsi sentetik bitki + sentetik elektro + deterministik senaryo ürünü.
- Bitki fizyolojisi parametreleri model seçimidir (kök iyileşmesi yok, tuz/UV katsayıları TODO, hn/ph/npk türetme).
- Elektro katmanı taklittir (dinlenim -120 mV, oran kodlaması, patlama kuralları). Gerçek bitki elektrot kaydıyla karşılaştırma YOK.

### Henüz test edilmemiş varsayımlar (bilinmeyenler)

- Gerçek bitki elektriksel verisiyle hiçbir iddia test edilmedi. Kayıt düzeneği yok.
- Farklı tohum/senaryo/yıl-tiplerinde skorların ne olduğu bilinmiyor (tek seed).
- Sessiz günler (85/250) ve test fazı (30 gün) skor-dışı; gerçek operasyonda sessizlik de karar olmalı.
- Işık/rüzgar/patojen-don/pH gerçek dinamiği yok veya TODO.
- Pattern lobunun dünya-koşulu doğruluğuna katkısı ölçülmedi (yalnız determinizm).
- Kapalı çevrim (NPU→sim geri besleme) bağlanmadı; açık onay ister (§9.21/§9.44).
- Uzun-kayıt drift, korkuluk-dışı EC=130 çökelme eksiği, 5-ton üstü yoğunluk, eşzamanlı çift yenilik test edilmedi.

## Deney tasarımına not (iddia değil, hazırlık)

Ön-kayıt önerisi (bu raporda test edilmedi): farklı seed'lerde (örn. 5 tohum) aynı TEST B protokolü → assoc + inference skorlarının dağılımı; ardından farklı senaryo (gübre/sulama günleri kaydırılmış) held-out → skor düşüşü. Sessiz günleri skora dahil eden ayrı metrik (abstain vs hata). Gerçek bitki verisi gelmeden tarla iddiası kurulmamalı.

---
*Bu dosya denetim ürünüdür; `src/`, `sim/`, `validate_*`, CSV/PNG değiştirilmedi.*
