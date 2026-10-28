# KPR1 — AŞAMA 1: K1 Kaynak Ablasyonu (dondurulmuş sözleşme, 2026-09-16)

Tek soru: **`d=1`'deki 12/12 ayrışmanın kaynağı gerçekten K1 mi?**
Teşhis modu: Aşama 2/3/4 AÇILMAZ, mimari kararı VERİLMEZ, C++ YOK,
`pl_core.py` import-only, yeni `frozen` YOK. Deterministik, RNG yok.

## Kollar (arch=v2, okuma=R0, parite=id, topoloji=T0; her kol d=0 VE d=1)

| # | Kol | Sürüş | Amaç |
|---|---|---|---|
| A0 | normal | A_K1 + A_K2 + A_K3 + B_K2 + B_K3 | referans |
| A1 | k1_ablate | K1 hiç sürülmez; K2/K3 tam | ★ K1 gerekli mi |
| A2 | k23_ablate | K2/K3 sürülmez; yalnız K1 | K1 tek başına taşır mı |
| A3 | coinc_lock | normal + bonus sabit-açık | bonus sabitken |
| A4 | coinc_off | normal + bonus kapalı | bonus çıkınca |
| A5 | amp_sweep | normal, amp ∈ {0.05,0.1,0.2,0.3,0.5,1.0} | amp_break |
| A6 | k1_ablate + amp_sweep | aynı süpürme | kırılma kayıyor mu |
| L1,L2 | legacy normal / k1_ablate (twin-yerel) | 3-komp | çapraz kontrol |

Ayırıcı: `Δ_d = N_sig(d=1) − N_sig(d=0)` (KBHP normal: +5).
K1-ablate'te Δ_d +5 kalırsa → zaman K2/K3 üzerinden, K1 taşıyıcı DEĞİL.
Kaybolursa → K1 taşıyıcı.

## Metrikler

- `N_sig/12`: KBHP ile AYNI imza tanımı (R0 full-popülasyon: birim-başına
  g0-izi[::10] + ateş-demeti, 6 birim konkatenasyonu; tam-ayrık kümeleme).
- `amp_break`: N_sig < 10/12 olan en yüksek genlik (birincil: d=1; d=0 JSON'da).
- `S_share(K1)`: KBHP ile AYNI tanım (v2 difüzyon-paylaşımı; legacy enjeksiyon-paylaşımı).
- `Δ_d`: yukarıdaki ayırıcı.

## Ön-kayıtlı 3 yönlü hüküm (B=A1d1, C=A2d1, N=A0d1=12)

- B = 12 → "K1, 12/12 İÇİN GEREKLİ DEĞİL" → Aşama 2 YANLIŞ HEDEF; dur, yeniden düşün.
- B < 12 → "K1 taşıyıcı" → Aşama 2 haklı hedef.
- C = 12 → "K2/K3 gereksiz" (beklenmez; çıkarsa büyük bulgu).
- A4 = 12 → bonus gerekli değil | A4 < 12 → bonus taşıyıcının parçası.

## Faz 0 (kırmızıysa DURUR)

- K1: yerel step === `pl_core.p3x_tick` (bit-eşit, reset dahil).
- K2 REGRESYON: normal·d0 → N_sig = 7 VE normal·d1 → N_sig = 12 (KBHP
  dondurulmuş sayılarının birebir tái-üretimi).
- K3: determinizm 2× bit-eşit (A0 d0+d1 tái-koşusu).
- K4: 8 donuk dosya SHA256 bekçisi (kilit değil).

## Açılmayacaklar

L-a..L-e projeksiyon kaldıraçları, `w_proj`, bağımsız referanslı köprü,
doğrudan enjeksiyon, Aşama 2/3/4, mimari kararı, N_min temiz G-C, C++ değişikliği.

## Dosyalar

`pattern/KPR1_SPEC.md`, `kpr1_drive.py`, `kpr1_run.py`, `kpr1_analyze.py`,
`p0_out/kpr1_fidelity.json`, `kpr1_axes.csv`, `kpr1_runs.json`,
`kpr1_budget.json`, `KPR1_REPORT.md`.
