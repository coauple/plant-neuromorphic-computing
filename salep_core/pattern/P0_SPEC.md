# P0 — PatternUnit Float İkiz Deney Sözleşmesi (DONDURULDU)

Tarih: 2026-09-16. Durum: donduruldu — parametre/matris değişikliği
yeni fıkra ister. Karar kilidi: **P0 önce, K1 seçimi ölçümden sonra.**

## 1. Sözleşme

| P0 YAPAR | P0 YAPMAZ |
|---|---|
| `neuron.h` dinamiğinin float ikizi | C++ yazmaz (o P2) |
| §14'ün 4 dizisini + geniş Δt süpürgesi koşar | `encoder/`'ı import etmez |
| faz kimliği ayrıştırıcı bilgi taşıyor mu ölçer | `sim/`'e dokunmaz |
| K1-a ve K1-b'yi yan yana koşturur | semantik `label` kullanmaz |
| deterministik, tekrar üretilebilir | classifier kurmaz |
| `f(Δφ)` mi `f(φ_B)` mi — döngüsellik testi | öğrenme çağırmaz (`eta=0`) |

Tek doğruluk kaynağı: `pl_core.py` (C++'a taşınacak ikiz budur).

## 2. İkiz denklem eşlemesi (`neuron.h` satır karşılıkları)

- Difüzyon: snapshot-then-apply, `V += 0.15·(V_komşu − V)` (ebeveyn +
  çocuklar; `compartment_apply_diffusion`).
- Sızıntı: `V -= leak·(V − V_REST)`, `V_REST=0.0`
  (`compartment_apply_leak`; V_REST=0 olduğundan kısa formla denk).
- Gating: `V>0.15` ise `g+=0.2`; `g-=gdecay·g`; `g<0→0`
  (`compartment_update_gating`).
- Eşzamanlılık (TAM C++ formu): `dal_last>=0 ve (t−last)<=10`, iki dal
  birden → `eff_g = g_root + 0.8`, yoksa `eff_g = g_root`.
- Soma: `soma = V_root·(1+eff_g)`; `soma>1.0` ise ateşle → tüm
  `V=-0.2` (gating SIFIRLANMAZ, aktivite tick'leri silinmez).
- Sıra: enjekte ÖNCE (`neuron_inject_current`), sonra `neuron_tick`.
- PLIR (K1-b): `neuron_inject_current` bloğunun aynısı —
  kabulde `mu=(bw−|ISI−tau|)/bw` ölçekler, redde ref korunur voltaj
  yok; taze kabul ilk darbe veya `ISI>2·tau+bw`; geçersiz kapı
  (tau/bw≤0) kapısız kabul. `bw=1` sabit.

## 3. PatternUnit kablolaması (somut basamak tanımı)

`k1[dal][12 slot] + k2[2] + k3[2] + p3` (29 nöron). A-darbesi (φ,t):
`k1[0][slot]` Dal-A + `±1` halka komşusu (`amp·w_ring`) + `k2[0]`/`k3[0]`
Dal-A. B-darbesi simetrik: `k1[1]` Dal-B + `k2[1]`/`k3[1]` Dal-B.
Aynı tick'te ateşleyen K nöronları P3'e basamak besler (A-tarafı→Dal-A,
B-tarafı→Dal-B, `amp_k=1.0`). Seri değil, üçüne birden paralel.

K tablosu (farklılığın tamamı; yazmayan alanlar `neuron_init`
öntanımı: root `0.08/0.005`, brA `0.06/0.004`, brB `0.04/0.003`):

| | K1 | K2 | K3 |
|---|---|---|---|
| brA leak | 0.06 | 0.10 | 0.02 |
| root gdecay | 0.005 | 0.010 | 0.002 |
| tau_isi / plir | RING: 0/0 · RESONANT: ızgara/1 | 0/0 | 0/0 |

Adil karşılaştırma kilidi: K1-a ve K1-b **aynı giriş koşullarında**,
aynı `amp=1.0`, aynı `w_ring=0.2`, aynı P3 ile koşar; K1-b E2–E7'de
`tau_isi=4` (sonuç görülmeden sabitlendi — en hızlı bandın tau'su,
§9.8 gerekçesi) kullanır. E1'deki tau ızgarası **geçici mekanizma
taraması** olarak raporlanır, encoder kalibrasyonu yerine geçmez.

## 4. Deney matrisi (t∈[0,200), RNG yok, `amp=1.0`, `w_ring=0.2`)

Temel: A(120°)=slot4 · B(240°)=slot8 · B(60°)=slot2.

| # | Deney | Koşu sayısı |
|---|---|---|
| E1 | Δt ∈ {1,2,3,4,5,6,8,10,12,15,20,25,30,40,50,60}, A→B | 16 (+K1-b ×12 tau=192) |
| E2 | sıra A→B/B→A × Δt∈{5,10,30} | 6 |
| E3 | φ_B 12 slot, Δt=5 | 12 |
| E4 | φ_A∈{0°,120°,240°} × Δφ 12 değer, Δt=5 | 36 |
| E5 | Δφ∈{30°,90°,180°} × w_ring∈{0,0.2,0.4,0.6} | 12 |
| E6 | tek-dal (yalnız A / yalnız B) × amp∈{0.5,1.0,2.0} | 6 |
| E7 | tüm matris 2× (bit-eşit determinizm) | ×2 |

## 5. Metrikler (classifier YOK, `label` YOK; diag büyüklükleri
`min(A_V,B_V)` vb. yalnız raporlamadır, dinamiği sürmez)

M1 tekrar bit-eşitliği · M2 durum imzası (P3 ateş tick'leri, max
soma_V, eff_g tepe, coinc tick sayısı + K ateş sayıları) · M3 ayrı
kuantalanmış imza sayısı (tam matris + deney-bazlı duyarlılık
kırılımı — elektriksel ayrışma ölçüsüdür, bilgi-kapasite kanıtı
DEĞİL) · M4 max soma_V vs Δt · M5 sıra asimetrisi · M6 döngüsellik
(Δφ-grubu içi varyans ≈0 ise `f(Δφ)`) · M7 Δφ=30° vs 180° farkı ·
M8 M3–M7 iki K1 modunda yan yana.

## 6. Kapılar

G1 M1=0 (determinizm) — **başarısızsa sert hata (exit 1), düzelt.**
G2 tek-dal ateşlememeli — **yalnız P0'ın A-B ilişki mekanizması**
kapsamında; genel mimari kuralı DEĞİL. G3 Δt eğrisi ≥3 seviye —
**hipotezdir, varsayım değil**; düşerse Boşluk 1 raporlanır,
sessizce yeniden kalibre EDİLMEZ. G4 sıra ayrımı>0 · G5 tepki
`f(Δφ)` · G6 M3>1. G2–G6 ölçüm sonucudur (exit 0); FAIL veridir.

## 7. Determinizm + frozen koruma

RNG yok (LCG kullanılmıyor). Tüm değerler `%.9f`. `p0_manifest.json`
(matris+parametre SHA256). Frozen 7 dosya (önce/sonra SHA256 aynı):
`src/{neuron,compartment,synapse,fdm,sensory_lobe}.h`,
`src/main_sensory_plant.cpp`, `scenario_engine.py`. P0 `sim/`,
`encoder/`, `web/` import etmez (AST kapısı).

## 8. Fıkra — P0b (2026-09-16, yeni hipotez; P0 rejimi donuk)

P0 tek-darbe rejimi başarısız rejim olarak aynen durur. Tren rejimi
(5 darbe, ISI=12, amp=1.0) ayrı hipotez olarak `P0B_SPEC.md` +
`p0b_run.py` + `p0b_analyze.py` ile test edildi; P0 dosya ve
verisine dokunulmadı. Anti-tuning kilidi (tek koşu + manifest
assert'i) P0B_SPEC §4'tedir.
