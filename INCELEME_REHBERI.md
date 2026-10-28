# İnceleme Rehberi (10–15 dakikalık ilk tur)

Araştırma sorusu ve dürüst durum özeti için önce [README.md](README.md).
Bu belge yalnız **nasıl bakılacağını** anlatır. `[KOŞULDU]` = 28 Eki 2026'da
bu paketin kopyasında gerçekten çalıştırıldı; `[KODDAN]` = koşulmadı, kaynak
koddan okundu; `[KOŞULMADI]` = ne koşuldu ne doğrulandı.

Önerilen tur: 0–3 dk belgeler, 3–8 dk canlı site, 8–15 dk bir deney.

Kapsam: bu paket erken prototipler içerir (faz seçiciliği, dendritik hesaplama,
sinaptik mekanizmalar, duyusal/örüntü işleme); kavram oluşturma, kavramsal
çıkarım, nedensel modelleme ve öngörü henüz bütünleşik ve doğrulanmış değil.
Tamamlanmış bir stres tanılama sistemi gibi değerlendirilmemelidir
(ayrıntı README'de).

## 1. Üç parça nedir?

- **Python bitki simülatörü** (`salep_core/sim/`): salep bitkisinin fizik + elektrik
  taklidi; 20 Hz fizik işletir, 5 Hz kare yayınlar. Girdi: `weather_v3/` hava
  dosyaları. NPU'suz tek başına koşar (`sim/run.py`).
- **C++ nöromorfik çekirdek** (`salep_core/src/`): `*.h` = sabit noktalı nöron/
  sinaps/lob çekirdeği; `main_*.cpp` = her biri ayrı deney programı (15 adet).
  Python ile bağlantısı yalnız alt-süreç + metin satırlarıdır (`SET ...` /
  `T ...`); ortak bellek yok.
- **Web sunucusu** (`salep_core/web/`): simülasyonu alt-süreç başlatır, kareleri
  tarayıcıya (`/ws/world`), NPU telemetrisini ayrı hatta (`/ws/npu`) akıtır.

## 2. Sıfırdan kurulum (sırayla)

```bash
cd salep_core

# 1) Python ortamı [KODDAN yazıldı, bu makinede KOŞULMADI: pip ağa erişemedi]
python3 -m venv .venv            # bu makinede ek paket istedi: apt install python3.10-venv
.venv/bin/pip install -r requirements.txt

# 2) C++ derleme [KOŞULDU: 15/15 + 3 kapı testi, 0 uyarı; cmake yok, g++ ile]
g++ -std=c++17 -O2 -Isrc src/main_plant_npu.cpp -o npu_plant_npu
g++ -std=c++17 -O2 -Isrc src/main_sensory_lobe.cpp -o npu_sensory_lobe
g++ -std=c++17 -O2 -Isrc src/main_pattern_lobe.cpp -o npu_pattern_lobe
g++ -std=c++17 -O2 -Isrc src/main_sensory_plant.cpp -o npu_sensory_plant
g++ -std=c++17 -O2 -Isrc src/main_fdm.cpp -o npu_fdm
g++ -std=c++17 -O2 -Isrc src/main_synapse.cpp -o npu_synapse
# kalan main_*.cpp aynı kalıpla (bkz. bench/snapshot.sh)
```

## 3. Canlı web simülasyonu [KOŞULDU]

```bash
cd salep_core
.venv/bin/python -m web.server --port 8001 --pub-port 41793
# Tarayıcı: http://127.0.0.1:8001
```

NPU bağlantı doğrulaması (ikinci uçbirimde) [KOŞULDU]:

```bash
curl -s http://127.0.0.1:8001/healthz
# beklenen: {"ok":true,...,"has_lobes":true,"npu_present":true}
```

`npu_present:false` ise site yine açılır ama `/ws/npu` hattı
`{"status":"offline"}` döner; NPU'suz çalışma normaldir (G22).
Tarayıcıda görülenler [KODDAN: `web/static/index.html` okundu, ekran
görüntüsü alınmadı]: 2B terraryum kesiti / 3B görünüm, Canlı Veriler
(tarih, dönem, hava, toprak, UV...), Bitki Sensörleri (7 kanal + sağlık),
Müdahaleler (sulama/gübre/toprak/hız düğmeleri), Sinyal Yayılımı paneli
(Zincir / Son afferent / Pattern / NPU göstergeleri).

Not: arayüz deneyseldir; NPU iç durumlarının grafikleri eksik veya güvenilmez
olabilir. Hüküm için telemetri satırlarına ve kayıtlı CSV/OZET çıktılarına
bakın (ayrıntı README'de).

## 4. Üç temsilî deney (hepsi [KOŞULDU], boş dizinde)

Genel kural: programlar CSV'yi **çalışılan dizine** yazar. Kayıtlı sonuçların
yanında koşmayın — §5'teki güvenli yöntemi kullanın.

### Deney A — PLIR/FDM (çift ritmi aynı telde ayırma)

- Program: `src/main_fdm.cpp` → `npu_fdm`
- Komut: `mkdir /tmp/fdm && cd /tmp/fdm && /yol/npu_fdm`
- Çıktı: `fdm_simultaneous.csv`, `fdm_events.csv`, `fdm_dshift.csv`
- Özet satırı: `OZET: A=OK A2=OK C=OK D=OK` (28 Eki taze derleme)
- İncelenen: iki ritim üst üste bindiğinde her bandın kendi ritmine kilitlenmesi
  (PLIR kapısı + 8 üyeli popülasyon) ve faz kaydırma doğruluğu.
- Sınırlar: harmonik çiftte yavaş bant ilk-darbe çapasıyla çalışır; 3. bant yok;
  yavaş kilit tohum-duyarlı; test ızgarası deterministik (`bw=1`). Bağımsız
  tekrarda harmonik yakalanma ölçüldü (`bench/REPORT.md` Aşama 2).

### Deney B — Kuadratik sinaps öğrenmesi (büyüme + doygunluk + aktarım)

- Program: `src/main_synapse.cpp` → `npu_synapse`
- Komut: `mkdir /tmp/syn && cd /tmp/syn && /yol/npu_synapse`
- Çıktı: `synapse_learning.csv`, `synapse_learning_closedloop.csv`,
  `synapse_transfer_low.csv`, `synapse_transfer_high.csv`
- Özet (28 Eki taze derleme): büyüme OK (ağırlık monoton artar); **doygunluk
  sınırda (UYARI)**; kapalı-döngü 4/5 (C4 UYARI); akım aktarımı OK
  (düşük ağırlıkta N1=0, yüksekte N1=79 ateş).
- İncelenen: `dw = eta·G·Q·S` kuralıyla birlikte-ateşleyen sinapsın güçlenmesi,
  tavanda durması ve öğrenilmiş ağırlığın akım taşıması.
- Sınırlar: `S` yalnız ağırlık tavanıdır, zaman/eskime terimi yok (tasarım
  kararı, `CLAUDE.md` §9.1). Kayıtlı Eylül sayılarıyla birebir aynı değil
  (taze derlemede T2=79, kayıtta 78).

### Deney C — Örüntü lobu (afferent → örüntü birimleri)

- Program: `src/main_pattern_lobe.cpp` → `npu_pattern_lobe`
- Komut: `mkdir /tmp/pl && cd /tmp/pl && /yol/npu_pattern_lobe --aff
  <salep_core>/testb_afferent.csv --mem mem.csv --log log.csv --eta 0 --k4 0`
- Çıktı: `mem.csv`, `log.csv`
- Özet: `OZET-PATTERN-LOB: k4=0 olay=300 mem=116` (28 Eki; snapshot ile bit-bit aynı)
- İncelenen: 300 afferent olayın 29 örüntü birimine deterministik dağılımı.
- Sınırlar: `eta=0` (öğrenme donuk); doğruluk kapısı yok, yalnız
  determinizm/sınır testi; hep aynı TEST-B kablosu. Bellek üzerinden çıkarım
  duyusal tabanı geçemedi (olumsuz sonuç, `CONTRACT_EVIDENCE.md` B10).

## 5. Güvenli koşma (kayıtların üzerine yazmadan)

Testler varsayılan çıktıyı kaynak dizine yazar. İki güvenli yoldan biri:

```bash
# Yöntem 1 (önerilir): paketin kopyasında çalış
cp -a plant-neuromorphic-computing /tmp/inceleme && cd /tmp/inceleme/salep_core
# ... derle, koş, boz; asıl paket temiz kalır

# Yöntem 2: C++ deneyleri için boş dizin + mutlak girdi yolu (Deney A–C yukarıda)
```

Üzerine yazanlar [KODDAN doğrulandı, koşulmadı]: `validate_testb.py` →
`testb_*.csv` dosyalarını ezer; `bench/snapshot.sh` → `bench/build/` ve
`bench/baseline_snapshot/` içeriğini ezer; `plot_*.py` → dizindeki `*.png`
dosyalarını ezer. `sim/selftest.py`, `web/gates_web.py`, `bench/run_all.sh`
komutları belgede yazdığı gibidir ancak bu denetimde **koşulmadı**.

## 6. İlk turda okunacaklar (öncelik sırası)

1. `README.md` (doğruluk durumu) → 2. `salep_core/CONTRACT_EVIDENCE.md` (B1–B11)
   → 3. `salep_core/bench/REPORT.md`
   yönetici özeti → 4. `salep_core/CLAUDE.md` (asıl araştırma günlüğü: kurallar, mimari ve her deney).
