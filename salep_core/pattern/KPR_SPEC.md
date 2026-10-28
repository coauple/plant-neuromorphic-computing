# KPR — K1→root Projeksiyon Yeniden Tasarımı (dondurulmuş sözleşme, 2026-09-16)

Teşhis modu: Aşama 2/3/4... bu planın Aşama 1–4'ü KOŞAR (aşağıda); sonrası
(mimari fazı, S6, B-K1, gerçek-kablo doğrulaması, C++ geçişi) AÇILMAZ.
C++ YOK. `neuron.h` (518/524 dahil), `pattern_unit_v2.h`, `pattern_lobe.h`,
`pl_core.py` (import-only), `CMakeLists.txt` dokunulmaz. Deterministik, RNG yok.

## Türetilmiş denklem (kilitli)

C0 (mevcut, `p3x_tick` aynası): yerinde-mutasyon kök döngüsü
`V0 += D·(S_k − V0)` → geometrik projeksiyon ağırlıkları
(A_K1 0.06656 … B_K3 0.15000; A_K1/B_K1 = 0.614; kök tutma 0.347).

F1/F4/F8 (yerel step, twin-düzeyi):

```
kök   : V0 += (G_ROOT/6) · w_k · (S_k − ref_k)     # snapshot S0, sıra-bağımsız
          ref_k = 0.0  (k == A_K1 VE F4 açık)      # F4: K1 bağımsız referans
          ref_k = S0   (diğer tüm durumlar)
çocuk : Vk += D_CHILD · w_k · (S0 − Sk)            # snapshot, sıra-bağımsız
soma  : V0·(1 + g0 + BONUS·coinc) + ALPHA·Σ(V1..V6)   # ALPHA terimi YALNIZ F8 açıkken
```

Kilitli parametreler: G_ROOT=0.30, D_CHILD=0.15, ALPHA=0.3, w_k=1.0 (tümü;
simetri varsayımı, raporda açık). Eşik THR=1.0 (değişmez). Ateş-reset C0 ile aynı.

Konfigürasyonlar: C0 | F1 | F1+sep | F1+sep+F4 | F1+sep+F8 | TAM(F1+sep+F4+F8).
`sep` = sürüş-düzeyi (KBHP ile aynı: Dal-B sessiz; K2/K3 4→2 komp).

## Uyaran (KBHP ile birebir — sadakat için)

Tek-slot: 8 darbe · ISI=10 · t0=5 · H=160 · amp 1.0 (kilitli) · ring 0.2 ·
iki dal · S5 kablolama (6 birim). d ∈ {0,1} (A0: varış t+slot×d).
amp_süpürme (amp_break): {0.25, 0.5, 1.0, 2.0} (d0 birincil; d1 JSON'da).

## Metrikler (kilitli tanımlar)

- `N_sig/12`: KBHP R0 imzası AYNI (birim-başına g0[::10]+ateş-demeti ×6).
  Birincil: N_sig(d0) (d1 tavanlı, regresyon-kontrolü).
- `amp_break`: N_sig < 10 olan en yüksek genlik (birincil d1? HAYIR — d0;
  d1 tavan yaptığı için ayırt etmez. Düzeltme: birincil d0).
- `S_share-merkez`: merkez-eşleşen (birim,slot) çiftlerinde difüzyon-paylaşımı
  (KBHP tanımı AYNI); 12-slot ortalaması DEĞİL.
- `A/B simetrisi`: impuls-probu (tek kompartmana birim darbe → kök ΔV):
  min-maks projeksiyon ağırlık oranı (C0: 0.614 beklenti; F1: 1.000 beklenti).
- `K2/K3 rol koruması`: tek-darbe sonrası ΣV_K3 / ΣV_K2 (kalıcılık oranı);
  kapı: K3>K2 sıralaması korunur VE oran C0'ın [0.5×, 2×] bandında.

## Kapılar

- Faz 0 SADAKAT: C0 konfigürasyonu KBHP sayılarını tái-üretir:
  N_sig(d0)=7, N_sig(d1)=12, S_share(12-slot-ort)=0.027 (±0.005 tolerans?
  HAYIR — bit-eşit dinamik + aynı uyaran = TAM eşitlik beklenir; tolerans YOK).
  + 8-hash bekçisi + determinizm 2×.
- Aşama kapıları (iyileşme-parite, ön-kayıtlı): F1 N_sig(d0) ≥ C0;
  d1 regresyonu YOK (12 kalır). Karar eşiği değil, rapor eşiği.

## Koşu sayısı

6 konfig × 12 slot × 2 d = 144 + amp 6×4×12 (d0) + 6×4×12 (d1) = 288 + 12 impuls
+ K2/K3 paarları (impuls içinde) ≈ **450 sim**.

## Dosyalar

`pattern/KPR_SPEC.md`, `kpr_drive.py`, `kpr_run.py`, `kpr_analyze.py`,
`p0_out/kpr_fidelity.json`, `kpr_axes.csv`, `kpr_runs.json`,
`kpr_manifest.json`, `kpr_budget.json`, `KPR_REPORT.md` (iddia defteriyle).

## İddia defteri (rapor aynen + KBHP notu; etiketleri veri günceller)
