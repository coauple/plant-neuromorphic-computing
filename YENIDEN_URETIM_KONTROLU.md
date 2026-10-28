# YENIDEN_URETIM_KONTROLU

Tarih: 2026-10-28. Yöntem: asıllara dokunmadan denetleme.

- Çalışma kopyası: `/tmp/yeniden_uretim/salep_core` (11.381 dosya, asılla birebir
  doğrulandı; 1,2 GB `.venv` kopyalanmadı, onun yerine asıl `.venv`'in Python'u
  salt-okunur çalıştırıcı olarak kullanıldı).
- Tüm derleme ve koşular kopyada yapıldı. Asıl `salep_core` içinde hiçbir dosya
  değiştirilmedi, hiçbir CSV/JSON/PNG üzerine yazılmadı, Git işlemi yapılmadı.
- Yeni algoritma/özellik/mimari değişikliği yok.

Terimler: derleme = C++ kodunu çalışır programa çevirme. Bayrak = derleyiciye
verilen ayar. Hash (SHA256) = dosyanın dijital parmak izi; tek bit değişse bile
değişir. OZET = programın sonunda bastığı geçme/kalma satırı. Telemetri = NPU'nun
düzenli durum satırları.

## 1. C++ derleme sonucu: 15/15 + 3/3 BAŞARILI, 0 uyarı

Derleyici: `g++ 11.4.0` (Ubuntu 22.04). `cmake` kurulu değil, bu yüzden doğrudan
`g++` kullanıldı (projenin `bench/snapshot.sh` deseninin aynısı):

```
cd /tmp/yeniden_uretim/salep_core
g++ -std=c++17 -O2 -Isrc src/main_*.cpp -o rebuild/<ad>   # 15 program
g++ -std=c++17 -O2 -Isrc check_*.cpp -o rebuild/<ad>      # 3 kapı testi
```

Derlenenler: `main` (nöron izi), `main_branch`, `main_event`, `main_multi`,
`main_synapse`, `main_network`, `main_phase_group`, `main_causality`, `main_fdm`,
`main_plant_npu` (bitki NPU), `main_sensory_lobe` (duyusal lob),
`main_sensory_plant`, `main_causal_afferent`, `main_pattern_lobe` (örüntü lobu),
`main_pattern_lobe_k4_rel` + `check_pattern_lobe`, `check_learning`,
`check_learn_baseline`. Derleme günlüğü: kopyada `rebuild/build.log` (0 uyarı).

Kapı testleri koştu, üçü de OK:
`OZET-LOB-CHECK: OK`, `OZET-LEARN-CHECK: OK`, `OZET-LEARN-BASE: OK`.

Düzeltme notu: ilk sayımda `src/main.cpp` gözden kaçtı (adında alt-çizgi yok,
`main_*` kalıbına uymuyor); sonradan derlenip koşturuldu, sonuç aşağıda.

## 2. Duman koşuları ve kayıtlı sonuçlarla karşılaştırma

Her program kopya içinde kendi boş klasöründe koşturuldu (çıktılar asıllara
karışmadı). Odak: bitki NPU, duyusal lob, örüntü lobu.

| Program | Komut (kopyada) | Çıkış | Kayıtlı sonuçla karşılaştırma |
|---|---|---|---|
| Bitki NPU | `rebuild/main_plant_npu` | exit 0, `OZET: KILIT=OK KAZANIM=OK NEGATIF=OK CR=OK` | 3 CSV, 9 Eyl kayıtlı CSV'lerden **farklı** (ilk fark 15. satır, ağırlığın 5. ondalığında); ama 15 Eki `bench/baseline_snapshot` ile **bit-bit aynı** |
| Duyusal lob | `rebuild/main_sensory_lobe` | exit 0, `OZET: A=UYARI B=OK C=OK D=OK` | 9 Eyl kaydından **farklı**; 15 Eki snapshot ile **bit-bit aynı** |
| Örüntü lobu | `rebuild/main_pattern_lobe --aff .../testb_afferent.csv --mem mem.csv --log log.csv --eta 0 --k4 0` | exit 0, `OZET-PATTERN-LOB: k4=0 olay=300 mem=116` | `mem.csv`/`log.csv` snapshot ile **bit-bit aynı** (tam üretim) |
| Nöron izi | `rebuild/main` | exit 0 | `neuron_trace.csv` hem kök kaydı hem snapshot ile **bit-bit aynı** (tam üretim) |

Ek bulgular (neden-sonuç araştırması, hepsi kopyada):

- Kayıtlı 9 Eyl binary'leri (`npu_plant_npu`, `npu_sensory_lobe`) bugün koşturuldu:
  kayıtlı CSV'leri **bit-bit aynen** üretiyor, duyusal lob `A=OK` veriyor. Yani
  ortam sağlam; sapma ortamdan değil.
- Taze derlemede 6 bayrak denendi: `-O0`, `-O2`, `-O3`, sanitizer, sanitizer+`-O1`,
  sanitizer+`-O2`, `-march=native`. Tümü birbirinin aynısını üretti, hiçbiri 9 Eyl
  CSV'sini vermedi. Kayıtlı binary sanitizer'lı (`strings` ile doğrulandı) ama aynı
  derleyici sürümü (GCC 11.4.0). Sonuç: 9 Eyl binary'si, diskteki kaynaktan küçük
  bir farkla (kaynağın derlemeden sonraki hali ya da bilinmeyen bayrak) üretilmiş;
  Git olmadığı için kesin neden bulunamıyor.
- Önemli: **taze derlemeler kendi içinde tam tekrarlanabilir** — 15 Eki snapshot
  ile 28 Eki taze derleme bit-bit aynı. Akademik sunumda "9 Eyl sayıları" yerine
  "taze derlemeden üretilen sayılar" kullanılmalı (bkz. §5).

Hash kanıtları (taze `-O2` derleme):
`plant_learning.csv=664ba523…`, `plant_conditions.csv=023ff77a…`,
`plant_dualrail.csv=bd3d7c9d…`, `sensory_lobe_learning.csv=832dc61c…`,
`pattern mem.csv=2f3811e3…`, `log.csv=0942be1f…`, `neuron_trace.csv=8e91337c…`.

## 3. Python bağımlılıkları: requirements.txt oluşturuldu (kopyada)

Dosya: kopyada `/tmp/yeniden_uretim/salep_core/requirements.txt` (asılda YOK,
istenirse kopyalanabilir). İçerik — kodda gerçekten import edilen 7 paket,
çalışan `.venv` sürümlerine sabitlendi:

```
numpy==2.2.6  pandas==2.3.3  matplotlib==3.10.9  starlette==1.6.0
uvicorn==0.52.4  websockets==16.1.1  rich==15.0.0
```

Denetimler (hepsi geçti):

- 7 paketin importu + sürümleri asıl `.venv` ile doğrulandı.
- Proje modülleri (`sim.*`, `web.*`, `live_term` vb.) kopyadan hatasız import
  edildi. `matplotlib` ilk importta ev-dizini önbelleğine yazamadığını bildirip
  `/tmp`'ye düştü — zararsız uyarı.
- Tüm proje `.py` dosyaları sözdizimi denetiminden geçti (`compileall`, hata 0).
- `.venv`'deki `streamlit/requests/Pillow/PySide6` hiçbir dosyada import edilmiyor
  (artık); listeye alınmadı. `node` (G24 testi için) sistem gereksinimi olarak
  not edildi.

Taze kurulum denenemedi, iki engel (ikisi de bu makinenin durumu, proje hatası
değil): (1) `python3 -m venv` çalışmıyor (`ensurepip` yok; `apt install
python3.10-venv` ve sudo gerekir — yapılmadı); (2) PyPI ağına erişim yok
(`pip download` zaman aşımı). Yani `requirements.txt` içeriği doğru paketleri
kapsıyor ama sıfırdan `pip install` bu makinede kanıtlanamadı.

## 4. Uçtan uca test: web → simülasyon → C++ NPU veri akışı KANITLANDI

Test betiği: `/tmp/e2e_test.py` (kopyadaki sunucuyu başlatır, `/healthz` +
`/ws/world` + `/ws/npu` okur, sunucuyu kapatır). Sunucu komutu:

```
cd /tmp/yeniden_uretim/salep_core
SALEP_NPU_BIN=<taze main_plant_npu> <.venv>/bin/python -m web.server
  --port 18081 --pub-port 41881
```

Yayıncı açılış satırı: `READY port=41881 ... chain=acik` (canlı zincir devrede).

NPU AÇIK (taze derlenmiş binary):

- `/healthz`: `publisher_alive=true, has_frame=true, has_lobes=true,
  npu_present=true`
- `/ws/world`: `gun=273`, 7 sensör (`ec hn hs npk ph tn ts`), `lobes=True`
- `/ws/npu`: canlı akış — `t=0 → 25 → 50`, ağırlıklar öğrenmeyle değişiyor
  (`0.2 → 0.206 → 0.259`), taşıyıcı sayaçlar artıyor. Simülasyon NPU'yu besliyor,
  NPU öğreniyor, sonuç tarayıcıya akıyor.

NPU KAPALI (`SALEP_NPU_BIN` olmayan yola verildi):

- `/healthz`: aynı ama `npu_present=false`; site ve kare akışı çalışmaya devam
  ediyor (beklenen G22 davranışı).
- `/ws/npu`: `{"status": "offline"}`.

Doğrudan köprü kanıtı (`sim/npu_bridge.py` + taze binary): 7 `SET` komutuna NPU
`OK SET hs=85` gibi yanıtlar döndü, telemetri `t=125 → 175` ilerledi. Yani veri
gerçekten Python'dan C++'a gidip geri dönüyor; placebo değil.

## 5. Yeniden üretilemeyen / sapan noktalar (gizlenmedi)

1. **Duyusal lob `A=OK` iddiası (§9.14) taze derlemeden üretilemiyor.**
   Taze derleme `A=UYARI` veriyor (p2a dw +1.7991/CR 75; kayıtlı iddia +0.65/CR 35).
   `A=OK` yalnız kayıtlı 9 Eyl binary'siyle alınabiliyor. Sunumda bu sayı
   "kayıtlı binary ile" notuyla verilmeli ya da taze değere güncellenmeli.
2. **9 Eyl bitki/duyusal CSV'leri taze derlemeden bit-bit üretilemiyor.**
   OZET düzeyi aynı (bitki 4/4 OK), ama CSV bit-farkı 15. satırda başlıyor.
   15 Eki snapshot'ı taze derlemeyle birebir tuttuğu için projenin kendi
   regresyonu bunu yakalayamamış (snapshot-snapshot karşılaştırması yapıyor,
   kök CSV ile değil).
3. **`src/main.cpp` ilk envanterde eksik sayıldı** (bu kontrolde düzeltildi;
   derleme+koşu OK, CSV bit-bit aynı).
4. Geçmiş "test başarılı" kayıtlarından bu kontrolde koşulmayanlar hakkında
   hüküm verilemedi (aşağıda).

## 6. Güvenli biçimde çalıştırılamayan / koşulmayan işler

- Taze `.venv` kurulumu (§3'teki iki engel yüzünden). Zorlanmadı.
- `validate_*.py` tam seti, `sim/selftest.py`, `web/gates_web.py`, `bench/run_all.sh`
  koşulmadı: görev kapsamı derleme + bağımlılık + uçtan uca kanıttı; ayrıca
  `run_all.sh` ~2 saat sürer. Kopyada koşulmaları güvenli olurdu ama denenmedi —
  sonuçsuz bırakıldı, "geçti" sayılmadı.
- `cmake` ile derleme denenmedi (`cmake` kurulu değil).

## 7. Akademisyen sunumu için öneri

- "Taze derleme bit-bit tekrarlanabilir" denebilir (15 Eki = 28 Eki kanıtıyla),
  ama "9 Eyl CSV'leriyle bit-bit aynı" DENEMEZ.
- Duyusal lob A kapısı sunumda `A=UYARI (taze derleme)` olarak verilmeli;
  `A=OK` yalnız kayıtlı binary'ye ait.
- Örüntü lobu (`mem/log`) ve nöron izi tam üretim — en güçlü kalemler bunlar.
- `requirements.txt` hazır ama taze `pip install` kanıtı yok; "bağımlılık listesi
  çıkarıldı, temiz kurulum internetli makinede doğrulanacak" denmeli.

## Ek: kullanılan dosyalar ve komut özeti

- Kopya: `tar --exclude=.venv --exclude=__pycache__` ile `/tmp/yeniden_uretim/`.
- Derleme: `g++ -std=c++17 -O2 -Isrc ...` (15+3 hedef) + bayrak varyantları
  (`-O0/-O3/-march=native/-fsanitize=address,undefined`).
- Koşular: kopyada `rebuild/runs/<ad>/` altında; kayıtlı binary'ler
  `ASAN_OPTIONS=detect_leaks=0` ile.
- Karşılaştırma: `sha256sum`, `cmp`, `bench/baseline_snapshot/*/SHA256SUMS`.
- Web testi: `/tmp/e2e_test.py` (port 18081/41881 açık, 18082/41882 kapalı) +
  `sim/npu_bridge.py` doğrudan köprü betiği.
- Python: asıl `.venv` yorumlayıcısıyla import + `compileall`; taze venv
  girişimi başarısız (ensurepip/PyPI).
- Rapor + `requirements.txt`: rapor asıl dizinde bu dosya; `requirements.txt`
  yalnız kopyada (`/tmp/yeniden_uretim/salep_core/requirements.txt`).
