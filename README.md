# Salep Sibernetiği

## Araştırma sorusu

Zamanı sinyalin içine gömmüş bir duyusal mimari — faz seçici rezonans,
zamansal örüntü ayrıştırma ve öğrenilmiş koşul temsilleri — bitki
elektrofizyolojisi gibi yavaş, gürültülü ve seyrek sinyallerde neyi,
hangi sınırlarla temsil edebilir?

Bu paket, o soruyu araştıran **deneysel bir mimari prototip** sunar; genel
amaçlı bir SNN sınıflandırıcısı değildir. Çekirdek: çok bölmeli dendritik
nöronlardan oluşan C++ nöromorfik çekirdek + Python bitki simülatörü + web
arayüzü. FPGA'ya taşıma hedefi tasarım kısıtıdır (sabit nokta, sabit diziler),
henüz gerçekleşmemiştir.

## Mevcut aşama ve kapsam sınırı

Mevcut olan, **erken prototiplerdir**: zamansal faz seçiciliği (PLIR/FDM
deneyleri), dendritik hesaplama (çok bölmeli nöron çekirdeği), sinaptik
mekanizmalar (kuadratik kural, akım aktarımı) ve duyusal/örüntü işleme
(koşul bankası, örüntü lobu). Her biri ayrı deneylerle kısmen doğrulandı;
sınırlar belgelerde açık.

Henüz **bütünleşik ve doğrulanmış biçimde geliştirilmedi**: öğrenilmiş koşul
temsilinden kavram oluşturma ve türetme, kavramsal çıkarım, nedensel
modelleme ve öngörü. Bunlar gelecek araştırma hedefleridir, mevcut paket
bunları içeriyor gibi okunmamalıdır.

Bu sistem tamamlanmış bir **stres tanılama** veya **kavramsal çıkarım** sistemi
olarak tanıtılmaz. Bitki stresi/sağlık durumları hakkında operasyonel hüküm
vermez; tarla verisiyle doğrulanmamıştır.

Giriş noktaları:

- [INCELEME_REHBERI.md](INCELEME_REHBERI.md) — 10–15 dakikalık ilk teknik tur
- [CLAUDE.md](salep_core/CLAUDE.md) — mimari ve tasarım kısıtları
- [CONTRACT_EVIDENCE.md](salep_core/CONTRACT_EVIDENCE.md) — hangi iddia
  kanıtlı, hangisi hipotez (B1–B11 tablosu)
- [bench/REPORT.md](salep_core/bench/REPORT.md) — bağımsız değerlendirme
  (olumsuz sonuçlar dahil, değiştirilmedi)
- [YENIDEN_URETIM_KONTROLU.md](YENIDEN_URETIM_KONTROLU.md) — 28 Eki 2026
  yeniden-üretim denetimi

Bu paket GitHub'da yayınlanmıştır:
[coauple/plant-neuromorphic-computing](https://github.com/coauple/plant-neuromorphic-computing).
Kaynak kodlar ve sonuçlar değiştirilmeden alınmıştır.

## Yöntem notu: skorlar neyi ölçer, neyi ölçmez?

`bench/REPORT.md` içindeki klasik sınıflandırma skorları (AUC, doğruluk)
mimarinin bütün amaçlarını ölçmez. Aşağıdaki boyutlar ayrıca değerlendirilmelidir:

- **Faz seçiciliği:** ardışık-pencere deneyinde bant-içi ≥%98,8 ayrım (TDM;
  simultane değil) ve simultane çift-ritim deneyinde kilit/kapsama metrikleri
  ölçüldü; bağımsız tekrarda harmonik yakalanma sınır olarak belgelendi
  (bkz. `CLAUDE.md` §9.6/§9.8, `bench/REPORT.md` Aşama 2).
- **Kabul/ret kararları:** PLIR kapısının darbe kabul/ret sayımları
  karakterize edildi (`plir_decisions.csv`, `validate_plir.py`); ablasyonda
  kapı kapalıyken skorun yükselmesi şaşırtıcı bulgu olarak raporlandı, yorumu açık.
- **Yanıt kapsaması:** faz-kilit kapsama (cov) değerleri deney raporlarında
  verildi; tohum-duyarlı yoğunlaşma (conc) değerleri kapı değil bilgi
  değeridir (bkz. §9.8 disiplini).
- **Sessizlik davranışı:** test fazında ateş üretememe (CR_YOK) bulgu olarak
  kaydedildi; sessizliğin karar olarak kullanılması **doğrulanmadı** (açık iş,
  bkz. denetim raporu §6–7).
- **Öğrenilmiş koşul temsilleri:** sentetik uyaranla koşullanma ve
  sensörsüz yanıt gösterildi; örüntü belleği üzerinden çıkarım duyusal
  tabanı geçemedi (0.310/0.356'ya karşı 0.554) — olumsuz sonuç gizlenmedi
  (bkz. `CONTRACT_EVIDENCE.md` B10).

Yukarıda "ölçüldü" denenler bu paketteki betik ve CSV'lerle izlenebilir;
"açık" denenler doğrulanmış gibi sunulmaz.

Faz seçiciliği testleri ile klasik sınıflandırma testleri farklı şeyleri ölçer
ve birbirine karıştırılmamalıdır. Sınıflandırma başarısızlıkları gizlenmemiştir
(örn. demux D1/D2 KALDI, örüntü çıkarımının tabanı geçememesi); ancak AUC/doğruluk
türü metrikler tek başına faz seçiciliğini, doğru reti, sessizliği ve kapsamayı
ölçmez. Bir sınıflandırma skorunun düşük olması bir mekanizmanın yokluğunu, yüksek
olması da doğruluğunu tek başına kanıtlamaz; her boyut kendi deneyi ve sınırıyla
birlikte okunmalıdır (bkz. `bench/REPORT.md`, `CONTRACT_EVIDENCE.md`).

## Web arayüzü notu (deneyseldir)

Web arayüzü bir izleme kolaylığıdır, ölçüm aracı değildir. Özellikle NPU iç
durumlarının (kompartıman voltajları, kapı/bellek alanları, bant-popülasyon
ateşleri) grafiksel görselleştirilmesi **eksik veya güvenilir değildir**:
telemetride taşınmayan alanlar panelde ya yoktur ya da türetilmiş gösterimdir.
Teknik değerlendirmede esas alınacaklar: kaynak kod (`salep_core/src/`),
doğrudan telemetri satırları (`T ...` / `K ...` çıktıları) ve kayıtlı deney
çıktıları (CSV + OZET satırları).

## Üretim ve yazım notu

Kodların yazımında yapay zekâ araçları yoğun kullanıldı; araştırma soruları,
deney tasarımları ve mimari kararlar kullanıcı tarafından yönlendirildi.
Bağımsız doğrulama sürüyor: kör kriterli değerlendirme (`bench/TEST_PLAN.md`),
salt-okunur denetim (`DENETIM_RAPORU_2026-10-14.md`) ve yeniden-üretim kontrolü
(`YENIDEN_URETIM_KONTROLU.md`) pakete dahildir.

## Klasörler

| Yol | Görev |
|---|---|
| `salep_core/src/` | C++ NPU kaynakları (`*.h` çekirdek, `main_*.cpp` deney programları) |
| `salep_core/sim/` | Python bitki simülatörü (fizik, elektro, yayıncı, canlı zincir) |
| `salep_core/web/` | Web sunucusu + tarayıcı arayüzü |
| `salep_core/bench/` | Değerlendirme (plan, rapor, betikler, anlık görüntü, özet dosyalar) |
| `salep_core/encoder/`, `salep_core/pattern/` | Kodlayıcı ve örüntü deneyleri |
| `salep_core/f0_baseline/` | Dondurulmuş referans skorlar |
| `salep_core/validate_*.py`, `plot_*.py` | Deney ve grafik betikleri |
| `salep_core/*.csv`, `*.png` | Kayıtlı referans sonuçlar |
| `salep_core/requirements.txt` | Python bağımlılıkları |

## Çalıştırma (Ubuntu 22.04, Python 3.10)

```bash
cd salep_core

# 1) Python ortamı
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt   # numpy, pandas, matplotlib,
                                            # starlette, uvicorn, websockets, rich

# 2) C++ derleme (cmake yoksa doğrudan g++ ile; her main ayrı programdır)
g++ -std=c++17 -O2 -Isrc src/main_plant_npu.cpp -o npu_plant_npu
g++ -std=c++17 -O2 -Isrc src/main_sensory_lobe.cpp -o npu_sensory_lobe
g++ -std=c++17 -O2 -Isrc src/main_pattern_lobe.cpp -o npu_pattern_lobe
g++ -std=c++17 -O2 -Isrc src/main_sensory_plant.cpp -o npu_sensory_plant  # TEST B için şart
# ... diğer main_*.cpp dosyaları aynı kalıpla derlenir (bkz. bench/snapshot.sh)

# 3) Web sunucusu (tarayıcıda http://127.0.0.1:8001)
.venv/bin/python -m web.server --port 8001 --pub-port 41793

# 4) Doğrulamalar (UYARI: alttaki kutuyu okumadan koşmayın)
.venv/bin/python -m sim.selftest        # simülatör kapıları
.venv/bin/python validate_testb.py      # TEST B zinciri (npu_sensory_plant ister)
bash bench/snapshot.sh                  # C++ determinizm anlık görüntüsü
```

Not: sanitizer ile derlenen programlar bazı ortamlarda `ASAN_OPTIONS=detect_leaks=0`
ile koşulmalıdır (bkz. `CLAUDE.md` §9.9). `web/g24_parity.mjs` için `node`
gereklidir. Gerçek-veri adımı (`bench` Aşama 7) bu paketten koşulamaz: kaynak arşiv
yeniden-dağıtım izni doğrulanmadığı için paylaşıma alınmadı (altta).

> **ÜZERİNE-YAZMA UYARISI:** Bu depodaki testler kayıtlı sonuçların üzerine yazar.
> Koşmadan önce klasörün bir kopyasını alın.
> - `validate_testb.py` → `testb_*.csv` dosyalarını ezer (ayrıca `/tmp/testb_diag.csv` yazar).
> - `bench/snapshot.sh` → `bench/build/` ve `bench/baseline_snapshot/` içeriğini
>   ezer (kayıtlı `MANIFEST.sha256` dahil).
> - `plot_*.py` → çalışılan dizindeki `*.png` dosyalarını ezer (CSV'leri okuduğu
>   için `salep_core/` içinde koşulmak zorundadır).
> - C++ programları CSV'leri çalışılan dizine yazar; boş bir dizinde koşun.

## Doğruluk durumu (dürüst özet)

28 Eki 2026 kontrolünde taze derlemeden elde edilenler
(ayrıntı `YENIDEN_URETIM_KONTROLU.md`):

- **Tam üretim:** örüntü lobu `mem.csv`/`log.csv` ve `neuron_trace.csv` kayıtlarla
  bit-bit aynı. Taze derlemeler kendi içinde tam tekrarlanabilir
  (15 Eki anlık görüntüsü ile bit-bit aynı).
- **Kısmi üretim:** bitki NPU özet kapıları taze derlemede de 4/4 OK, ancak CSV
  içerikleri Eylül kayıtlarıyla bit-bit aynı değil (ilk fark 15. satırda).
- **Üretilemeyen iddia:** duyusal lob `A=OK` sonucu taze derlemede **`A=UYARI`**
  çıkıyor; `A=OK` yalnız Eylül'de derlenmiş kayıtlı binary ile alınabiliyor.
- Kayıtlı derlenmiş programlar (`npu_*`) bu paylaşıma alınmadı; yeniden
  derlenebilir. Eylül sayılarının dayandığı binary'ler asıl arşivdedir.

## Dışarıda bırakılanlar

- `bench/real_data/plant_lib.rar` (gerçek bitki verisi arşivi): kaynağı ve
  yeniden-dağıtım izni doğrulanmadığı için paylaşıma alınmadı; yerel arşivde
  tutuluyor. `bench` Aşama 7 bu paketten tekrarlanamaz (`REPORT.md` sonuçlar
  olduğu gibi durur). `bench/REAL_DATA_SEARCH.md` arama kaydı dahildir.
- `bench/real_data/tools/` içindeki üçüncü taraf `unrar-nonfree` programı ve
  Debian belge/kılavuz dosyaları paylaşıma alınmadı (yerel arşivde). Arşiv
  açmak isteyen `unrar` paketini kendi sistemine kurmalıdır.
- `bench/results/` ham verileri (~823 MB): aşama özet dosyaları (83 dosya:
  `auc.csv`, `grid_auc.csv` vb.) dahil, tohum-başına veriler hariç.
- `pattern/p0_out/` iz dosyaları (~111 MB): küçük kanıt dosyaları
  (`frozen_*.txt`) dahil.
- `.venv/`, `__pycache__/`, derlenmiş programlar (`npu_*`, `bench/build/`).
- Gizli bilgi taraması yapıldı: API anahtarı/token bulunamadı.
