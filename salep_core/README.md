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
| `CLAUDE.md` | **Asıl araştırma günlüğü:** kurallar (§0), mimari (§1…), her deney `§9.xx` numarasıyla kayıtlıdır |
| `DENETIM_RAPORU_2026-10-14.md` | İç denetim raporu |
| `*.csv`, `*.png` | Deney çıktıları ve şekiller |

Hızlı doğrulama için kökte `bash run_review.sh`; ayrıntılı adımlar için [QUICKSTART](../QUICKSTART.md).
Deneyler çıktıları çalışılan dizine yazar; kayıtlı dosyaları bozmamak için kopyada çalışın.

## Kod okuma rehberi

Kodu incelemek isteyen biri için önerilen sıra (satır sayıları yaklaşıktır). Mimarinin bütünü için kökteki README §6.

### 1) C++ çekirdek (`src/`) — alttan üste

| Sıra | Dosya | Ne var? |
|---|---|---|
| 1 | `fixed_point.h` (85 satır) | Q16.16 sabit nokta aritmetiği; bütün çekirdek bunun üzerine kurulu, kayan nokta yok |
| 2 | `compartment.h`, `neuron.h` | Dendritik bölmeler ve çok bölmeli nöron (Dal A / Dal B / soma) |
| 3 | `synapse.h` | Sinaps ve kuadratik öğrenme kuralı (`dw = η·G·Q·S`), kalıcı iz (`T`) |
| 4 | `phase_group.h`, `fdm.h` | Faz seçici gruplar; aynı telde iki ritmi ayıran PLIR / FDM mekanizması |
| 5 | `causality.h`, `causal_afferent.h` | Nedensellik öğrenmesi ve afferent kablo (zaman damgalı olay arayüzü) |
| 6 | `sensory_lobe.h` | Duyusal lob: bitki darbeleri ve sensörlerin koşullu öğrenmesi |
| 7 | `pattern_lobe.h` (~690 satır), `pattern_state.h` | Örüntü lobu (K1–K4, iki aşamalı soma) ve w/T/r kontrol noktası |
| 8 | `plant_npu.h`, `network.h` | Bütünleşik bitki NPU'su ve küçük ağ |

Her `main_*.cpp`, bu başlıkları kullanan bağımsız bir deney programıdır (ör. `main.cpp` tek nöron, `main_fdm.cpp` FDM, `main_pattern_lobe.cpp` örüntü lobu).

### 2) Python tarafı

| Dosya | Ne var? |
|---|---|
| `sim/plant_sim.py` | Toprak–bitki–atmosfer fiziği (su, EC, buharlaşma, VPD) |
| `sim/electro.py` | Sentetik elektrofizyoloji (stres → elektriksel darbe) |
| `sim/events.py` | Stokastik olay motoru (yağmur, sıcak dalgası, hastalık vb.) |
| `sim/assoc.py`, `sim/infer.py` | Association ve çıkarım analizleri |
| `sim/sensory_chain.py` | Canlı zincir: simülatör → duyusal lob → örüntü lobu |
| `encoder/afferent_encoder.py` + `encoder/SPEC_v0_1.md` | Afferent kodlayıcı ve sözleşmesi |
| `web/` | Web sunucusu ve panel |

### 3) Neyi, nasıl doğrulayabilirsiniz?

- **Determinizm:** aynı girdi, bit-eşit çıktı. Kök dizinde `bash run_review.sh` bunun bir kısmını tek komutla gösterir.
- **Donanım kısıtları:** çekirdek hesabı sabit noktadır; `float`/`double` yalnızca CSV/hata ayıklama dönüşümlerinde ve ilklendirmede geçer (ör. `fixed_point.h` içindeki dönüştürücüler). Bunu `src/*.h` içinde `new`, `malloc`, `float`, `double` arayarak kendiniz kontrol edebilirsiniz; bilinen istisnalar (ör. `fdm_init` içinde `double`) README §9 ve bench raporunda belirtilmiştir.
- **Testler:** `validate_*.py` dosyaları (40 adet) her deneyin kapılarını ve sonuçlarını kontrol eder; hangi deneyin hangi dosyaya karşılık geldiği `DENEYLER_VE_ANALIZLER.md` içindedir.
- **Her sayının izi:** README'deki her sonucun yanındaki `§9.xx` numarası, `CLAUDE.md` içindeki ilgili günlük kaydına gider.
- **Bağımsız değerlendirme:** `bench/TEST_PLAN.md` (önceden dondurulmuş kriterler) ile `bench/REPORT.md` (sonuçlar; başarısızlıklar dahil) karşılaştırılabilir.
