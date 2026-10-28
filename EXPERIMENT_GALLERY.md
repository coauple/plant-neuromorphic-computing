# Deney Galerisi (Experiment Gallery)

Kayıtlı grafiklerin ne olduğu, hangi deneyden çıktığı ve neyi kanıtlamadığı.
Görsellerin pikselleri tek tek incelenmedi; eşleşmeler üretici betik + girdi
CSV üzerinden doğrulandı. "Belirsiz" işaretlilerde tahmin yürütülmedi.

## Tam eşleşme tablosu

| Grafik | Deney | Üreten / girdi | Ölçtüğü | Durum / sınır |
|---|---|---|---|---|
| `salep_core/neuron_trace.png` | Tek nöron izi | `plot_trace.py` ← `neuron_trace.csv` (`main.cpp`) | Membran voltajı, spike zamanları | Tam üretim (bit-bit) |
| `salep_core/neuron_trace_event.png` | Olay nöronu | `plot_trace.py` ← `neuron_trace_event.csv` | Aynı, olay varyantı | Erken karakterizasyon |
| `salep_core/branch_s1/2/3.png` | Dal S1–S3 | `plot_branch.py` ← `branch_s*.csv` (`main_branch`) | Dal voltajları | Erken karakterizasyon |
| `salep_core/branch_comparison.png` | Dal karşılaştırma | `plot_branch.py` | 3 senaryo yan yana | Aynı |
| `salep_core/synapse_learning.png` | L0 öğrenme | `plot_synapse.py` ← `synapse_learning.csv` | Ağırlık büyüme + doygunluk | Taze derlemede doygunluk sınırda (UYARI) |
| `salep_core/phase_group_learning.png` | TDM demux | `plot_phase_group.py` ← `phase_group_learning.csv` | Bant seçiciliği ≥%98,8 | Simultane değil (TDM) |
| `salep_core/causality_learning.png` | Nedensellik köprüsü | `plot_causality.py` ← `causality_learning.csv` | F3 bonusu 2.11× | Faz-3 pre-bazlı taşıma |
| `salep_core/fdm_simultaneous.png` | Simultane FDM | `plot_fdm.py` ← `fdm_*.csv` | Kilit + faz doğruluğu | Harmonik/tohum sınırları |
| `salep_core/q_dt_curve.png` | Q(Δt) taraması | `plot_q_dt_curve.py` (9× `npu_causality`) | Faz kaymasına ~düz yanıt | Hız-eşzamanlılığı devresi |
| `salep_core/plant_npu.png` | Koşullanma (dual-rail) | `plot_plant_npu.py` ← `plant_*.csv` | Kilit/kazanç/CR | 2 bant; Eylül bit-farkı |
| `salep_core/sensory_lobe.png` | Duyusal lob (4 panel) | `plot_sensory_lobe.py` ← `sensory_*.csv` | w/CR/işe-alım/kararlılık | Taze derlemede A=UYARI |
| `salep_core/causal_afferent.png` | Afferent + öngörü | `plot_causal_afferent.py` ← `causal_afferent_learning.csv` | A–F/P kapıları | Precision ölçülemedi |
| `salep_core/perturb_battery.png` | Pertürbasyon bataryası | `plot_perturb.py` ← `sim/out/perturb_battery.csv` | 8 fizik hipotezi | Simülatör karakterizasyonu |
| `salep_core/infer_interaction.png` | Çıkarım etkileşimi | `plot_infer.py` ← `sim/out/infer_summary.csv` | D2/D3 tekrarı | Faz-1, 10.000 yörünge |
| `salep_core/pattern/p0_out/p0_dt_curve.png` | p0 karakterizasyonu | `pattern/p0_analyze.py` ← `p0_runs.csv` | Δt eğrisi | Karakterizasyon |
| `salep_core/pattern/p0_out/p0b_dt_curve.png` | p0b karakterizasyonu | `pattern/p0b_analyze.py` ← `p0b_runs.csv` | Δt eğrisi | Karakterizasyon |
| `salep_core/stress_out_snr/snr_ladder.png` | Uyaran merdiveni | `plot_snr.py` ← `snr_ensemble.csv` | SNR basamakları | Kanonik aile |
| `salep_core/stress_out/fig1_diversity.png` | Stres çeşitliliği | `gen_stress_report.py` ← `cases.csv` | Görev çeşitliliği | v3d stres |
| `salep_core/stress_out/fig2_retrieval.png` | Geri çağırma | `gen_stress_report.py` | Geri-çağırma | Aynı |
| `salep_core/stress_out/fig3_repetition.png` | Tekrar | `gen_stress_report.py` | Tekrar güçlenmesi | Aynı |
| `salep_core/bench/figures/fig1_demux_ornek.png` | Demux örneği | `bench/stage9_figs.py` ← `results/` (**paylaşımda yok**) | Tel + bant ateşi örneği | Girdi hariç, betik dahil |
| `salep_core/bench/figures/fig2_agirlik.png` | Ağırlık | `stage9_figs.py` ← `results/` (yok) | Ağırlık dağılımı | Aynı |
| `salep_core/bench/figures/fig3_gurultu.png` | Gürültü | `stage9_figs.py` ← `results/stage3/grid_auc.csv` | S + baseline eğrileri | Özet CSV dahil |
| `salep_core/bench/figures/fig4_ablasyon.png` | Ablasyon | `stage9_figs.py` ← `results/` (yok) | Mekanizma kapatma etkisi | Girdi hariç |
| `salep_core/bench/figures/fig5_genelleme.png` | Genelleme | `stage9_figs.py` ← `results/` (yok) | Kalibre-dışı tau | Girdi hariç |
| `salep_core/bench/figures/fig6_seyrek_pr.png` | Seyrek nedensellik | `stage9_figs.py` ← `results/` (yok) | 12/12 sessizlik | Olumsuz sonuç |
| `salep_core/bench/figures/fig7_gercek.png` | Gerçek veri | `stage9_figs.py` ← `results/` (yok) | S 0.493, ayrım yok | Olumsuz sonuç |
| `salep_core/sim/out/g4_shot.png` | **Belirsiz (miras)** | Üretici kodda yok (G4 emekli Qt) | Bilinmiyor | Yorumlanmadı |
| `salep_core/sim/out/g6_drought.png` | **Belirsiz (miras)** | Üretici kodda yok (G6 emekli Qt) | Bilinmiyor | Yorumlanmadı |
| `salep_core/sim/models/tex/*.png` (4) | Deney grafiği değil | 3B doku haritaları | — | — |

Not: `network_learning.csv` ve örüntü lobu `mem/log` için kayıtlı PNG yoktur.

## Seçilmiş deneyler

### 1. Sinaps öğrenmesi — birlikte ateşle, güçlen, tavanda dur

- **Soru:** Sık birlikte ateşleyen iki nöron arası sinaps büyür ve doygunluğa ulaşır mı?
- **Program:** `salep_core/src/main_synapse.cpp` → `./npu_synapse` (boş dizinde)
- ![sinaps](salep_core/synapse_learning.png)
- **CSV:** `synapse_learning.csv` (+ closedloop/transfer_low/high)
- **Sonuç:** Büyüme OK (0.05→1.76); aktarım OK (düşükte N1=0, yüksekte 79).
- **Kanıtlamadığı:** Doygunluk taze derlemede sınırda (UYARI); `S` teriminde
  zaman/eskime yok; Eylül sayılarıyla bit-bit aynı değil.
- **Bağlantı:** [CLAUDE.md §9–9.4](salep_core/CLAUDE.md), [INCELEME_REHBERI §4B](INCELEME_REHBERI.md)

### 2. Simultane FDM — iki ritim, tek tel

- **Soru:** Aynı tele binen iki ritim birbirinden ayrılıp faz-kilitlenebilir mi?
- **Program:** `salep_core/src/main_fdm.cpp` → `./npu_fdm`
- ![fdm](salep_core/fdm_simultaneous.png)
- **CSV:** `fdm_simultaneous.csv`, `fdm_events.csv`, `fdm_dshift.csv`
- **Sonuç:** `OZET: A=OK A2=OK C=OK D=OK`; faz kayması ≤0.03 tick.
- **Kanıtlamadığı:** Harmonik çiftte yavaş-bant faz takibi yok; 3. bant yok;
  yavaş kilit tohum-duyarlı; deterministik ızgara koşulu.
- **Bağlantı:** [CLAUDE.md §9.8](salep_core/CLAUDE.md)

### 3. Koşullanma — bant + sensör eşleşmesi

- **Soru:** Frekans bandı sensörle eşleşince sensörsüz yanıt (CR) oluşur mu?
- **Program:** `salep_core/src/main_plant_npu.cpp` → `./npu_plant_npu`
- ![plant](salep_core/plant_npu.png)
- **CSV:** `plant_learning.csv`, `plant_conditions.csv`, `plant_dualrail.csv`
- **Sonuç:** `KILIT/ KAZANIM/NEGATIF/CR = OK`; NEM CR=62, SIC CR=117, EC=0.
- **Kanıtlamadığı:** 2 bant sınırı; uzun oturumda tavan karşılaştırması;
  Eylül CSV bit-farkı.
- **Bağlantı:** [CLAUDE.md §9.11–9.12](salep_core/CLAUDE.md)

### 4. Duyusal lob — banka + öz-örgütlenme + stres

- **Soru:** 10 üyeli koşul bankası öğrenir, yeniliği işe alır, strese dayanır mı?
- **Program:** `salep_core/src/main_sensory_lobe.cpp` (varsayılan / `--selforg` / `--stress`)
- ![sensory](salep_core/sensory_lobe.png)
- **CSV:** `sensory_lobe_learning.csv`, `sensory_selforg.csv`, `sensory_stress*.csv`
- **Sonuç:** Taze derlemede `A=UYARI B=C=D=OK`; işe-alım sıralı yenilikte OK.
- **Kanıtlamadığı:** `A=OK` yalnız kayıtlı binary ile; WTA rekabeti yok;
  eşzamanlı çift yenilik denenmedi; yoğun-faz kilit kusursuz değil.
- **Bağlantı:** [CLAUDE.md §9.14–9.16](salep_core/CLAUDE.md)

### 5. Q(Δt) — faz kaymasına duyarsızlık bulgusu

- **Soru:** Öğrenme kazancı faz kaymasına nasıl bağlı?
- **Program:** `salep_core/plot_q_dt_curve.py` (9× `npu_causality` koşar)
- ![qdt](salep_core/q_dt_curve.png)
- **CSV:** `q_dt_curve.csv`
- **Sonuç:** Eğri ~düz (yayılım <%6); devre hız-eşzamanlılığı yapıyor.
- **Kanıtlamadığı:** Alt-10-tick spike-zaman hassasiyeti bu devrede yok.
- **Bağlantı:** [CLAUDE.md §9.10](salep_core/CLAUDE.md)

### 6. Nedensellik köprüsü — birlikte-oluş bonusu

- **Soru:** A+B birlikte olunca öğrenme ve ateş tekillere göre artar mı?
- **Program:** `salep_core/src/main_causality.cpp` → `./npu_causality`
- ![caus](salep_core/causality_learning.png)
- **CSV:** `causality_learning.csv`
- **Sonuç:** Amplifikasyon 2.11×; negatif kontrol temiz (w1/w3 sabit).
- **Kanıtlamadığı:** Faz-3 pre-bazlı taşıma (tek-tel değil); öğrenme oran-tabanlı.
- **Bağlantı:** [CLAUDE.md §9.7](salep_core/CLAUDE.md)

### 7. Bağımsız değerlendirme — olumsuz sonuçlar dahil

- **Soru:** Çekirdek kör kriterlerde ne yapıyor?
- **Program:** `salep_core/bench/stage*.sh` (bu paketten tam koşulmadı)
- ![ablasyon](salep_core/bench/figures/fig4_ablasyon.png)
- ![seyrek](salep_core/bench/figures/fig6_seyrek_pr.png)
- **CSV:** `bench/results/` özetleri (83 dosya; ham veriler hariç)
- **Sonuç:** Demux D1/D2 KALDI; seyrek nedensellikte 12/12 sessizlik; gerçek
  veride ayrım yok (S 0.493); PLIR kapalıyken tau4 yükseldi (sürpriz).
- **Kanıtlamadığı:** Bu bir çekirdek-hükmü değil, ölçüm-sınırı kaydıdır.
- **Bağlantı:** [bench/REPORT.md](salep_core/bench/REPORT.md),
  [bench/TEST_PLAN.md](salep_core/bench/TEST_PLAN.md)

### 8. Simülatör fiziği — pertürbasyon ve çıkarım

- **Soru:** Bitki fiziği kırma testlerine ve 10.000 yörüngelik çıkarıma dayanır mı?
- **Program:** `salep_core/sim/perturb.py`, `salep_core/sim/infer.py`
- ![perturb](salep_core/perturb_battery.png)
- **CSV:** `salep_core/sim/out/perturb_battery.csv`, `infer_summary.csv`
- **Sonuç:** 8 önden-hipotez bataryası + Faz-1 çıkarım kayıtları.
- **Kanıtlamadığı:** Simülasyon sonucu; tarla değil.
- **Bağlantı:** [CLAUDE.md §9.45, §9.50](salep_core/CLAUDE.md)
