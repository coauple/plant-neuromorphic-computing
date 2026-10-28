## 5. Güvenli koşma (kayıtların üzerine yazmadan)

Testler varsayılan çıktıyı kaynak dizine yazar. İki güvenli yoldan biri:

```bash
# Yöntem 1 (önerilir): paketin kopyasında çalış
cp -a . /tmp/inceleme && cd /tmp/inceleme/salep_core
# ... derle, koş, boz; asıl paket temiz kalır

# Yöntem 2: C++ deneyleri için boş dizin + mutlak girdi yolu (Deney A–C yukarıda)
```

Üzerine yazanlar [KODDAN doğrulandı, koşulmadı]: `validate_testb.py` →
`testb_*.csv` dosyalarını ezer; `bench/snapshot.sh` → `bench/build/` ve
`bench/baseline_snapshot/` içeriğini ezer; `plot_*.py` → dizindeki `*.png`
dosyalarını ezer. `sim/selftest.py`, `web/gates_web.py`, `bench/run_all.sh`
komutları belgede yazdığı gibidir ancak bu denetimde **koşulmadı**.
