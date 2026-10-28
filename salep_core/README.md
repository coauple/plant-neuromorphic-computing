# salep_core — kaynak kod, deneyler ve kayıtlı çıktılar

Projenin anlatısı ve bulguları için kökteki [README.md](../README.md) dosyasına bakın. Bu dizin, anlatının dayandığı kodu ve ham kayıtları içerir.

| Yol | İçerik |
|---|---|
| `src/` | C++17 sabit-noktalı sinir çekirdeği (`*.h`) ve her biri ayrı deney olan `main_*.cpp` programları |
| `encoder/` | Afferent (duyusal → olay) kodlama |
| `sim/` | Python bitki simülatörü, sentetik elektrofizyoloji katmanı, canlı zincir |
| `web/` | Web sunucusu ve sinyal paneli |
| `pattern/` | Örüntü lobu analiz ve okuma betikleri |
| `bench/` | Bağımsız değerlendirme: `TEST_PLAN.md` (önceden dondurulmuş), `REPORT.md` (sonuçlar) |
| `weather_v3/` | Aydın hava verisi (Open-Meteo) |
| `stress_out*/`, `f0_baseline/` | Stres bataryası ve regresyon çıktıları |
| `validate_*.py` | Doğrulama betikleri (determinizm, sızıntı, doğruluk kapıları) |
| `CLAUDE.md` | Geliştirme günlüğü: her deney `§9.xx` numarasıyla kayıtlıdır |
| `ARCHITECTURE.md` | Mimari belge |
| `DENETIM_RAPORU_2026-10-14.md` | İç denetim raporu |
| `*.csv`, `*.png` | Deney çıktıları ve şekiller |

Hızlı doğrulama için kökte `bash run_review.sh`; ayrıntılı adımlar için [QUICKSTART](../QUICKSTART.md).
Deneyler çıktıları çalışılan dizine yazar; kayıtlı dosyaları bozmamak için kopyada çalışın.
