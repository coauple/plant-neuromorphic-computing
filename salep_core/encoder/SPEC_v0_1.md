# AfferentSpikeEncoder v0.1 — Sözleşme (DONDURULDU)

Tarih: 2026-09-15. Durum: donduruldu — sayı değişikliği bu dosyaya yeni
fıkra ister. Pattern Lobe'a dokunulmaz; encoder ondan bağımsız
karakterize edilir.

## 1. Kapsam

NPU tarafı `salep_core/encoder/` — `sim/` ve `web/` ile kod bağı YOK
(import yok, stdlib-only). Girdi: afferent kablo (`tick,post_id,tau_b`
sütunları; `label/a0lag/a1lag/bmask/bwin/w` okunmaz, karara girmez).
Çıktı: spike listesi + `out/enc_*.csv` karakterizasyonu.

## 2. Kilitli sabitler (tamsayı)

| Ad | Değer | Gerekçe |
|---|---|---|
| `PHASE_SLOTS` | 12 | faz adres alanı |
| `PHI_FULL_X100` | 36000 | 360.00 derece, yüzde-derece |
| `PHI_ID_STEP_X100` | 3000 | `36000 // 12`, 30.00 derece |
| `TAU_LO` | 4 | tanı aralığı alt sınırı (dahil) |
| `TAU_HI_EXCL` | 61 | ayrık üst sınır; `tau=60` dahilken `phi<36000` korunur |
| `TAU_SPAN` | 57 | `61 - 4` |
| `P2_MAX` | 64 | `AfferentEvent.post_id` ham aralığı 0..63 |

`TAU_HI_EXCL=61` seçimi: `tau=60` kapsayıcı olsaydı pay `(60-4)*36000`
ve payda 56 olurdu → tam 36000 = 360.00 derece → `phi<36000`
değişmezi bozulurdu. Ayrık üst sınır invariantı koruyan tek seçimdir.

## 3. Formüller (tamsayı aritmetiği, float yolu YOK)

```python
phi_id_x100 = post_id * 3000
phi_tau_x100 = ((tau_b - 4) * 36000) // 57
```

Derece = `x100 / 100`. `phi_id` posta sabit adrestir (30 derece adım,
0 çakışma). `phi_tau` tanı kanalıdır; çakışması aranan bulgudur
(2 grup, 6/10 post) — saklanmaz, raporlanır.

Banka tablosu (`post_id, tau_b, rol, phi_id`):

| post | tau_b | rol | phi_id |
|---|---|---|---|
| 0 p2a | 35 | HN | 0.00 |
| 1 p2b | 45 | HS | 30.00 |
| 2 p2c | 35 | replika | 60.00 |
| 3 p2d | 36 | decoy | 90.00 |
| 4 p2e | 46 | decoy | 120.00 |
| 5 p2f | 26 | EC(-) | 150.00 |
| 6 p2g | 37 | TS | 180.00 |
| 7 p2h | 37 | TN | 210.00 |
| 8 p2i | 37 | PH | 240.00 |
| 9 p2j | 37 | NPK | 270.00 |
| 10, 11 | — | yedek | 300.00, 330.00 |

## 4. Veri yapıları

`AfferentEvent{tick:int>=0, post_id:int, tau_b:int}`.
`AfferentSpike{tick, phi_id_x100:int, phi_tau_x100:int}`.
1 olay → 1 spike (genişletme YOK — bilgi kaybedemez; patlama ayrı aşama).

Aralık sözleşmesi (v0.1): `post_id` 0..11 dışında → `ValueError`;
`tau_b` 4..60 dışında → `ValueError`. Sessiz `% 12` sarması YASAK
(kimlikleri karıştırır). Banka 12'ye ulaşırsa bu spesifikasyon v0.2'ye
yükseltilmek ZORUNDADIR (`sl_add_post` büyümesi kapılı olaydır).

## 5. Değişmezler

I1 zaman korunumu (`spike.tick == event.tick`). I2 tersinirlik
(`post_id == phi_id_x100 // 3000`). I3 sıra korunumu. I4 determinizm
(bit-eşit). I5 etiket körlüğü (etiket sütunu okunmaz, karara girmez).
I6 sessiz varsayılan yok (aralık dışı yüksek sesle batar).

## 6. Kapılar (T1..T12)

T1 determinizm (bit-eşit) · T2 zaman korunumu · T3 etiket körlüğü
(yapısal: kaynakta `label` geçmez, AST ile) · T4 etiket körlüğü
(temiz null: label-dışı birebir aynı kabloda bit-eşit) · T5
`0 <= phi < 36000` · T6 `phi_id` çakışma == 0 (assert) /
`phi_tau` çakışma raporlanır · T7 sıra korunumu · T8 tersinirlik ·
T9 aralık dayanıklılığı (`ValueError`) · T10 `boff` ablasyonu →
0 spike · T11 seyreklik raporu · T12 tamsayı-aritmetik eşdeğerliği
(AST: `Div` yok, float sabit yok — float yolu YOK).

## 7. Δφ disiplini (Düzeltme 5)

`phi_id` sabit adres olduğundan aynı postun ardışık olaylarında
`Δphi_id ≡ 0` → sıfır bilgi. Doğru metrikler: D1 aynı tick'te
eşleşen postların `|Δphi_id|` çiftleri (hangi fazlar birlikte
ateşliyor); D2 ardışık olaylarda işaretli `phi_id(n+1)-phi_id(n)`
(kimlik fazı zaman sırası); D3 `|Δphi_id| mod 30°` histogramı
(bantlı mı, faz-başına-bir mi).

## 8. E0 provenansı (gerçek koşu, 2026-09-15)

TEST B düzeninin 300 günlük uzantısı: `--cond 27 --test 3` →
15000 tick, 300 gün (recovery 180-270'e uzatıldı, diğer evreler/
olaylar/tohum aynen). `encoder/out/aff300_*`:
girdi 2275 bitki spike; P1 darbesi 2192/56; 9 ayrı koşul etiketi;
cond ateş `7 76 7 7 74 88 94 53 0 0`; test ateş `0 0 0 0 0 0 1 0 0 0`;
boff P2 kaydı 0 (407 olaylı ana kablo, 407 satırlı temiz null).

## 9. Dürüst sınırlar

1. `tau_b → phi` kimlik için kullanılmaz (çakışma ölçüldü).
2. `bwin` varsayılan KAPALI (vekil sızıntı).
3. T4 temiz null ister (`shuf_afferent.csv` temiz null değildir).
4. p2i/p2j ölü → 240°/270° kalıcı karanlık (gerçek kusur, açık kalem).
5. `PHASE_SLOTS=12` donmuş → 12. postta v0.2 zorunlu.
6. Δφ tek başına anlamsız → D1/D2/D3.
7. `sim/assoc.py` NPU tarafı ama `sim/` içinde — dokunulmuyor,
   bildiriliyor.

## 10. Düzeltme notu (2026-09-15, E2 koşusu)

Plan mesajındaki `phi_tau` derece tablosu span-56 ile hesaplanmıştı
(36→205.71°, 37→212.14°); kilitli formül span-57 kullanır, doğru
değerler: 26→138.94° · 35→195.78° · 36→202.10° · 37→208.42° ·
45→258.94° · 46→265.26° · 60→353.68°. Formül değişmedi, tablo
düzeltildi (T12 el-hesabı kilidi).
