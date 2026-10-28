# Hızlı Başlangıç (Quickstart) — Ubuntu 22.04 / C++17 / Python 3.10

`[DOGRULANDI]` = 28 Eki 2026'da bu paketin kaynaklarından gerçekten koşuldu;
`[DOGRULANMADI]` = bu makinede denenemedi. Paket kökü: klonlanan dizin.

## Hızlı yol

Köke gidip `bash run_review.sh` çalıştırın (~2 sn; geçici kopyada çalışır, depoyu bozmaz). Aşağıdaki adımlar aynı işin elle, ayrıntılı halidir.

## 0. Güvenli çalışma (önce bunu yapın)

Deneyler çıktıları çalışılan dizine yazar; kayıtlı sonuçların üzerine yazmamak
için paketin kopyasında çalışın [DOGRULANDI — bu yöntemle test edildi]:

```bash
cp -a plant-neuromorphic-computing /tmp/incele && cd /tmp/incele/salep_core
```

## 1. Gereksinimler

- `g++` (C++17; denenen: Ubuntu 11.4.0) [DOGRULANDI]
- Python 3.10 + `python3.10-venv` (bu makinede yoktu; `apt install` gerekir)
- `requirements.txt` paketleri (numpy, pandas, matplotlib, starlette, uvicorn,
  websockets, rich) — `pip install` bu makinede ağ yokluğundan [DOGRULANMADI]
- `node` (yalnız `web/g24_parity.mjs` için) [DOGRULANMADI]
- `cmake` [DOGRULANMADI — bu makinede kurulu değil; aşağıda doğrudan `g++` var]

## 2. İlk C++ deneyi: tek nöron izi [DOGRULANDI]

```bash
mkdir -p /tmp/ilksurus && cd /tmp/ilksurus
g++ -std=c++17 -O2 -I<PAKET>/salep_core/src <PAKET>/salep_core/src/main.cpp -o npu_sim
./npu_sim
```

`<PAKET>` = paketin bulunduğu dizin. Beklenen çıktı (birebir):

```
Simülasyon tamamlandı: 500 tick, 6 ateşleme
Çıktı: neuron_trace.csv
```

Çıktı dosyası çalışılan dizine yazılır (`/tmp/ilksurus/neuron_trace.csv`,
26.979 bayt). Doğrulama: `sha256sum` değeri kayıtlı kanonik değerle aynı olmalı:

```
8e91337c32f7a60e848651fe9def6b35ee86db137ceb1f61fe56da3256ba62d5
```

Diğer deneyler aynı kalıpla (`main_synapse`, `main_fdm`, `main_pattern_lobe`
...); tam komutlar [INCELEME_REHBERI.md](INCELEME_REHBERI.md) §4'tedir.
Örüntü lobu ayrıca `--aff <PAKET>/salep_core/testb_afferent.csv` ister.

## 3. Python simülatörü ve web sunucusuna geçiş

```bash
cd <PAKET>/salep_core
python3 -m venv .venv                              # [DOGRULANMADI: ensurepip engeli]
.venv/bin/pip install -r requirements.txt          # [DOGRULANMADI: ağ engeli]
.venv/bin/python -m web.server --port 8001 --pub-port 41793   # [DOGRULANDI desen]
```

Sunucu açılınca (ayrı uçbirim):

```bash
curl -s http://127.0.0.1:8001/healthz   # [DOGRULANDI]
# beklenen: {"ok":true,...,"has_lobes":true,"npu_present":true}
```

Tarayıcı: `http://127.0.0.1:8001`. `npu_present:false` ise site yine çalışır,
NPU hattı `{"status":"offline"}` döner. C++ programları `salep_core/` köküne
`npu_*` adlarıyla derlenmeden NPU bağlı olmaz (2. adımdaki komutlar).

## 4. Bilinen kurulum ve yeniden-üretim sorunları

- `python3 -m venv` → `ensurepip` yoksa `apt install python3.10-venv` gerekir.
- Sanitizer'lı derlemeler bazı ortamlarda `ASAN_OPTIONS=detect_leaks=0` ister.
- `matplotlib` ilk importta ev-dizini önbelleğine yazamazsa `/tmp`'ye düşer (zararsız).
- `validate_testb.py` → `testb_*.csv` dosyalarını ezer; `bench/snapshot.sh` →
  `bench/build/` + `bench/baseline_snapshot/` içeriğini ezer; `plot_*.py` →
  `*.png` dosyalarını ezer. Kopyada çalışın.
- Taze derleme Eylül CSV'leriyle bit-bit aynı değildir; duyusal lob taze
  derlemede `A=UYARI` verir (bkz. README'deki doğruluk durumu).
