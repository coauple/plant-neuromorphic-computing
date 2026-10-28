## Goal

Hedef mimariye geçiş: 1 Pattern Unit = 29 gerçek Pattern nöronu (P3a–P3ac);
her P3x nöronu 2 dal × 3 paralel kompartman (K1/K2/K3) + soma.
K1/K2/K3 artık ayrı nöron değil, nöron-içi kompartman.
P3x farklılaşması morfolojide değil bağlantı matrisindedir: 29 P3x aynı
morfolojik nörondur, ancak hangi afferent/faz girişinin hangi P3x'in hangi
dalındaki hangi K-kompartmanına bağlandığı P3x'ler arası farklılaşır.
Bağlantı matrisi rastgele/keyfi üretilmez; encoder + V-kanıtlarından türetilene
kadar OPEN kalır. 29 özdeş tam-bağlı kopya yasaktır.
Mevcut çalışan sistem bozulmadan, testler ve frozen baseline korunarak.

## Success Criteria

- Mevcut 29-nöron sisteminin referans çıktıları hash'li baseline olarak kilitli;
  geçiş sonrası legacy yol aynı hash'leri üretiyor.
- Yeni topolojide 29 P3x nöronu kuruluyor; her biri root + 2 dal × 3 K-kompartman
  (7 kompartman) iç yapısına sahip.
- V1–V8 kapılarının yeni topolojiye uyarlanmış karşılıkları geçiyor
  (eski kapılar legacy yolda aynen yeşil kalıyor).
- Kod değişikliği yok hükmü bu plan onaylanana kadar sürüyor.
- Bağlantı topoloji spec'i (aşağıdaki tablo) Faz 0.5 analizinde doldurulup
  ayrıca onaylanmadan Faz 1 koduna geçilmez; doldurulamayan hücre OPEN kalır.

## Context And Current Facts (üç sorunun cevabı — kod değişikliği yapılmadı)

### S1. Mevcut kodda kaç gerçek P3/Pattern nöronu var? — 1 adet.

`src/pattern_lobe.h` `pl_init` (:111–131): 28 ayrı K-nöronu + 1 P3.

- `lobe.k1[dal][s]` — 2 dal × 12 slot = 24 ayrı `DendriticNeuron` (id 1000+).
- `lobe.k2[dal]`, `lobe.k3[dal]` — 2 + 2 = 4 ayrı `DendriticNeuron` (id 2000+/3000+).
- `lobe.p3` — **tek** Pattern soması (id 4000, `wp3[2]` girişi).

Toplam `DendriticNeuron` örneği 29, ama gerçek P3 nöronu **1**. Python ikizi
`pattern/pl_core.py` `PatternUnit` aynı yapıyı kuruyor (`make_neuron` + `p3`).

### S2. İç yapı 2 dal × 3 paralel kompartman mı? — Hayır.

`neuron_init` ve `neuron_init_with_params` (`src/neuron.h` :185, :267) her nörona
(sınıf ayırt etmeden, p3 dahil) tam 3 kompartman veriyor:
`[0]=root, [1]=Dal-A, [2]=Dal-B`. K1/K2/K3'ün nöron içinde **hiçbir karşılığı yok**;
K-farkı yalnızca nöron-seviyesi parametre (`pl_k_params`: K2 `brA_leak 0.10 /
root_gdecay 0.010`, K3 `0.02 / 0.002`). `compartment.h` dalları yaprak düğüm
sayıyor; alt-kompartman kavramı yok. Olumlu taraf: `Compartment` zaten
kompartman-başına `leak_rate`/`gating_state` taşıyor (:28–29) ve
`MAX_COMPARTMENTS=12` slotun yalnızca 3'ü kullanılıyor — 7'li yapı (root+6K) sığar.

### S3. Mevcut 29 nöron nerede/nasıl oluşuyor?

Tek yer: `pl_init` (`src/pattern_lobe.h` :111–131). K1'ler dal×slot döngüsünde
`wk1` sinapslarıyla, K2/K3 dal-başına `wk2`/`wk3` ile, P3 `wp3[2]` ile kuruluyor.
Mevcut topoloji (ASCII):

```text
DUYUSAL LOB (slot s=0..11)
 │  wk1[A][s] / wk1[B][s] (slot-özel ağırlık)   wk2/wk3 (dal-başına paylaşımlı)
 ▼                                               ▼
K1[A][0..11] K1[B][0..11]            K2[A] K3[A]  K2[B] K3[B]
(24 ayrı DendriticNeuron)            (4 ayrı DendriticNeuron)
 │ her biri: root + Dal-A + Dal-B     │ her biri: root + Dal-A + Dal-B
 └──────────────┬────────────────────┘
                ▼
          P3 (TEK soma, id 4000)
```

Hedef topoloji (tek P3x örneği):

```text
P3a SOMA (root)
 ├── Dal-A: K1 │ K2 │ K3 (paralel kompartman)
 └── Dal-B: K1 │ K2 │ K3 (paralel kompartman)
 × 29 (P3a … P3ac)
```

### S4. Mevcut bağlantı kanıtı (P3x tablo zemini — `pl_tick` + main, kod değişikliği yok)

- **Dal-A/B girişi production'da ÖZDEŞ:** her afferent olay (post p) hem
  `(dal=0, slot=p)` hem `(dal=1, slot=p)` darbesi üretir
  (`main_pattern_lobe.cpp` :106–113). Dal ayrışması girdide YOK; yalnızca ayrı
  durum/ağırlık ikizi. "Dal-eşlemesi" doğrulanmamış prototip olarak DAHİL DEĞİL
  (`pattern_lobe.h` başlık notu). Sonuç: P3x'te Dal-A/B farklılaştırmasının
  production kanıtı YOK → tabloda OPEN. Aday hipotez (kanıt değil): UPU
  prototip semantiği X-treni→A-hattı / Y-treni→B-hattı (`UPU_SPEC.md` §1;
  prototip, öğrenme/C++ YOK).
- **K1 rolü = slot-özel merkez + halka:** `pl_tick` her darbeyi merkez slot
  (1.0×) + komşular (s±1 mod 12, 0.2×) olarak enjekte eder (`as={100,20,20}`,
  `PL_W_RING=0.2`, P0 ring). Hangi MERKEZ slotun hangi P3x'e gideceği OPEN
  (farklılaşmanın ta kendisi).
- **K2/K3 rolü = dal-geneli slot-kör iz:** her dal darbesinde `wk2/wk3` akımı
  aynen enjekte edilir (`cur2/cur3`); fark yalnızca dinamik
  (K2 `brA_leak 0.10`, K3 `0.02`). Slot seçiciliği YOK.
- **Başlangıç ağırlığı:** tüm K-ağırlıkları `PL_W0=1.0` (UPL rejimi), `eta=0.30`;
  P3'e her K-ateşi `wp3[dal]` üzerinden girer; P3 coincidence =
  A-ve-B dal girişleri `COINCIDENCE_WINDOW_MS` içinde.
- **Kullanılabilir slot havuzu:** post 0..7 canlı, 8–9 (p2i/p2j) kalıcı karanlık,
  10–11 yedek (`SPEC_v0_1.md` §3 banka + §9.4). `tau_b→phi` kimlikte kullanılmaz
  (çakışma ölçüldü); slot-üstü farklılaşma K2/K3'e değil K1-merkez seçimine ve
  faz-çiftlerine dayanmak zorunda.
- **"29" sayısının kanıtı YOK:** 29, legacy birim sayısının (24+2+2+1) taşınmış
  halidir; veride 29 ayrışabilir pattern olduğu gösterilmedi. Ampirik kontrol
  mevcut: V6 ayrı-imza sayısı + UPU madencilik çift envanteri. Sayı varsayım
  olarak korunur, Faz 0.5'te mining ile sınanır (az pattern → sessiz P3x'ler).

### S5. Bağlantı topoloji tablosu (rol-satırlar DERIVED, P3x-atamaları OPEN)

Aşağıdaki 6 rol-satır tüm P3x'ler için aynen geçerlidir (kanıt S4):

| Dal | Kompartman | Giriş | w0 | Gerekçe |
| --- | ---------- | ----- | -- | ------- |
| A/B | K1 | merkez slot c(P3x) + halka c±1 (0.2×) | 1.0 | `pl_tick` ring, `PL_W_RING`, `PL_W0` |
| A/B | K2 | daldaki TÜM olaylar (slot-kör, tam genlik) | 1.0 | `cur2` enjeksiyonu, `PL_W0` |
| A/B | K3 | daldaki TÜM olaylar (slot-kör, tam genlik) | 1.0 | `cur3` enjeksiyonu, `PL_W0` |

P3x-farklılaşması = `c(P3x)` merkez-slot seçimi (+ Dal-A/B farklılaşırsa dal
eşlemesi). 174 hücrelik tam tablo şeması:

| P3x | Dal | Kompartman | Giriş slotları | Başlangıç ağırlığı | Gerekçe |
| --- | --- | ---------- | -------------- | ------------------ | ------- |
| P3a | A | K1 | OPEN (c(P3a) atanmadı) | 1.0 (rol-default) | merkez-seçim kanıtı yok |
| P3a | A | K2 | dal-A tüm olayları | 1.0 | S4 K2 rolü |
| P3a | A | K3 | dal-A tüm olayları | 1.0 | S4 K3 rolü |
| P3a | B | K1 | OPEN (c(P3a) + dal-eşleme atanmadı) | 1.0 (rol-default) | dal-eşleme kanıtı yok |
| P3a | B | K2 | dal-B tüm olayları | 1.0 | S4 K2 rolü |
| P3a | B | K3 | dal-B tüm olayları | 1.0 | S4 K3 rolü |
| P3b–P3ac | A/B | K1 | OPEN (28 atama) | 1.0 (rol-default) | mining türetmesi Faz 0.5'te |
| P3b–P3ac | A/B | K2/K3 | ilgili dalın tüm olayları | 1.0 | S4 K2/K3 rolü |

Türetme kaynakları (sırayla, Faz 0.5'te koşulur): D1 eş-ateşleyen faz çiftleri
+ D2 faz-sıra dizileri (`SPEC_v0_1.md` §7) → aday merkez-slotlar; UPU çift
envanteri ((4,7), (4,8) öncelikli) → aday A/B eşleşmeleri; V6 ayrı-imza sayısı →
P3x sayısı kontrolü. Koşulmayan analizin hücresi OPEN kalır; varsayım yazılmaz.

### S6. V1–V8'in mimari varsayımları (hangisi korunur, hangisi re-derive)

- **V1 build-parity — RE-DERIVE (koşullu).** Tek binary + tek `pl_init` yolu
  varsayar. Binary/CLI/log şeması değişirse parity hedefi yenilenir; legacy
  binary bit-aynı kaldığı sürece legacy V1 aynen koşar.
- **V2 determinizm — KORUNUR.** Topolojiden bağımsız (bit-eşit iki koşu).
- **V3 encoder eşdeğerliği — KORUNUR.** Encoder frozen; port formülleri değişmez.
- **V4 zincir (`olay==len(aff)`, `k>0`, `p3>0`, `mem==n_p3`) — RE-DERIVE.**
  Tek-P3 + P3-başına-mem varsayar; çok-P3x'te ateşleme P3x-başına sayılır,
  mem kaydına P3x kimliği girer.
- **V5 boff sessizliği — RE-DERIVE (ruh korunur).** 29 P3x'in tamamı sessiz olmalı.
- **V6 mining (`k1a/k1b/k2ab/k3ab/p3` sütunları, ≤100 tick gruplar, ±10 pencere
  imzalar) — RE-DERIVE.** Log şeması P3x-başına kompartmanlara genişler;
  grup/imza mantığı aynen taşınır.
- **V7 evre dağılımı — RE-DERIVE.** Hangi P3x'in hangi evrede ateşlediği eklenir.
- **V8 ağırlık hareketi (`wk1/wp3` 1.0'dan kıpırdadı) — RE-DERIVE.** Ağırlık seti
  değişir (kompartman-girdi ağırlıkları); "öğrenme açık ve hareket var" kapısı
  aynen taşınır.

## Constraints And Non-goals

- `salep_core/CLAUDE.md` anayasa: frozen dosyalara dokunulmaz, encoder v0.1
  frozen, merkezi classifier/label/phase comparison eklenmez, Python reference
  C++ runtime yerine konmaz.
- Non-goal: K2/K3 paylaşım-vs-kopya kararı bu planda verilmez (açık soru olarak
  korunur); inference bağlantısı ayrı onayda.

## Key Decisions

- **D1 — Q1 kararı: 29 aynı-morfolojili P3x; farklılaşma bağlantı matrisinde.**
  "Hepsi tüm slotları görür" ve "legacy 24+2+2+1 mirası" seçenekleri doğrudan
  kullanılmaz. Her P3x tüm giriş uzayından bağlantı ALABİLİR (aynı morfoloji),
  ancak matris P3x'ler arası farklılaşır; matris encoder + V-kanıtlarından
  (D1/D2/D3, UPU çiftleri, V6 imzalar) türetilir. Reddedilen: rastgele/keyfi
  matris, 29 özdeş tam-bağlı kopya (seçicilik kanıtını bozar), varsayımla
  doldurulmuş tablo (doldurulamayan OPEN kalır).
- **D2 — Morfoloji düz (flat) 7 kompartman.** `[root, A-K1..K3, B-K1..K3]`;
  iç içe ağaç yok (`compartment.h` yaprak varsayımı + difüzyon döngüleri düz kalır).
- **D3 — Additive-only geçiş.** Eski `pl_init` legacy olarak korunur
  (`pl_init_legacy`); yeni yol `pl_init_v2` yanına eklenir. V1–V8 eski eşikleri
  eski sayımları kodladığı için yeni topolojiye re-derive edilir; eski kapılar
  legacy yolda koşmaya devam eder.
- **D4 — Önce baseline kilit.** Herhangi bir editleme öncesi referans çıktıların
  hash'leri alınır ve salt-okunur kopyalanır.

## Recommended Approach

Önce Faz 0 ile mevcut çıktıyı dondur; sonra Faz 0.5 ile bağlantı tablosunu
türet (analiz, kod yok) → morfoloji (Faz 1) → lob v2 (Faz 2) → ikiz+kapılar
(Faz 3) → kabul ve eski-yol kararı (Faz 4). Her faz bir öncekinin
yeşil kanıtına dayanır; kabul öncesi hiçbir legacy satır silinmez.

## Work Plan

- **Faz 0 — Baseline kilit (kod değişikliği yok).** `validate_pattern_lobe.py`
  ve `npu_pattern_lobe` yeniden koşulur; `pattern_testb_mem/log.csv` + OZET
  çıktıları hash'lenip salt-okunur kopyalanır (`V1_BASELINE.md` yanına).
- **Faz 0.5 — Bağlantı tablosu türetme (analiz, kod değişikliği yok).**
  Donuk E0 kablosu + mevcut loglar üzerinden: D1 eş-ateşleyen faz çiftleri ve
  D2 faz-sıra dizileri (`encoder/analyze_phase.py`, SPEC §7) → aday K1-merkez
  slotlar; UPU çift envanteri → aday A/B eşleşmeleri; V6 ayrı-imza sayısı →
  "29" sayısı kontrolü. Çıktı: S5 tablosunun doldurulmuş hali (doldurulamayan
  OPEN). Kapı: tablo onayı olmadan Faz 1'e geçilmez.
- **Faz 1 — 7-kompartman morfolojisi.** Yeni `neuron_init_7comp` (eski init'lere
  dokunmadan): kompartman indeks konvansiyonu, kompartman-başına K parametreleri
  (leak + gating-decay; decay alanı yoksa `Compartment`'a eklenir), tick/difüzyon
  döngülerinin 7 kompartmana genellenmesi. Birim test: tek P3x'e Dal-A-K1 darbesi
  yalnızca ilgili kompartmanda voltaj yükseltir.
- **Faz 2 — PatternLobe v2.** `p3x[29]` dizisi; her P3x'in Dal-A/B'sine eski
  `wk1/wk2/wk3` ağırlıklarının taşınma eşlemesi (hangi slot → hangi P3x);
  `pl_tick_v2` yalnızca v2 dizisini sürer.
- **Faz 3 — Python ikizi + kapılar.** `pattern/pl_core.py`'ye `PatternUnitV2`;
  V1–V8'in v2 karşılıkları (`validate_pattern_unit.py`); legacy script aynen yeşil.
- **Faz 4 — Kabul + eski-yol kararı.** v2 kapıları yeşil + legacy hash'ler aynı →
  eski yolun silinip silinmeyeceği ayrı onay.

## Validation Plan

- Faz 0: `g++ -std=c++17 -Isrc src/main_pattern_lobe.cpp` + `validate_pattern_lobe.py`;
  beklenen kanıt: V1–V8 OK ve hash listesi.
- Faz 0.5: D1/D2 çift listesi + UPU envanteri + V6 imza sayısı raporu;
  beklenen kanıt: S5 tablosunun doldurulmuş hali (OPEN'lar işaretli), kod diff YOK.
- Faz 1: kompartman izolasyon birim testi (tek dal darbesi, komşu K-kompartman sessiz).
- Faz 2–3: `validate_pattern_unit.py` V1–V8-v2 OK; legacy `validate_pattern_lobe.py`
  hâlâ OK (değişen hash yok).
- En yüksek riskli adım: V-kapılarının re-derivasyonu (eski eşikler yeni sayımlara
  uymayabilir; kapı başına beklenen/gerçekleşen tablo şart).

## Risks / Rollback

- Kapı semantiği kayması (en büyük risk): eski eşikler yeni topolojide anlamsız
  sayılara bağlanabilir → her kapı re-derive edilir, legacy kapılar referans kalır.
- Ağırlık taşıma hatası: wk eşlemesi tablo olarak dokümante edilir, toplam
  iletkenlik Faz 0 değerleriyle karşılaştırılır.
- Rollback: kabul öncesi her şey additive-only olduğundan rollback = v2
  dosyalarının silinmesi; legacy'ye dokunulmadığı için risksiz.

## Open Questions

- **Q1 — KAPANDI (D1 + Faz 0.5).** İkili seçenekler reddedildi; bağlantı matrisi
  türetme yöntemi kararlaştırıldı. Kalan iş: Faz 0.5 analizini koşup S5
  tablosunu doldurmak; doldurulamayan OPEN kalır.
- **Q2.** K2/K3 dinamiği her P3x'e kopya mı (açık K2/K3 sorusuyla aynı), paylaşımlı
  kompartman-dışı nöron olarak mı kalır? Faz 2'de karar verilir, Faz 0–1'i bloklamaz.
- **Q3.** "29" sayısı varsayım (S4): veride 29 ayrışabilir pattern kanıtı yok.
  Faz 0.5 mining (V6 ayrı-imza sayısı, UPU çift envanteri) sayıyı sınar; düşük
  çıkarsa fazla P3x'ler sessiz kalır (zararsız ama raporda açık yazılır).

## Durum (onaylı faz kayıtları — kod değil, defter)

- **Faz 0 (2026-09-16, ONAYLI-TAMAM).** `validate_pattern_lobe.py` V1–V8 OK
  (`olay=300 k_atis=0+42+136 p3_atis=47 mem=47`); `f0_baseline/` hash + salt-okunur
  kilit (mem `19a4db…`, log `da01ed…`).
- **Faz 0.5 (2026-09-16, ONAYLI-TAMAM).** 6 güçlü aday + 22 tekil bağlam; S5 tablo
  onaylı haliyle donduruldu (P3a–P3e KANITLI, P3f ZAYIF, P3g–P3ac OPEN, B-K1 OPEN,
  29 = kapasite).
- **Faz 1 (2026-09-16, ONAYLI-TAMAM).** `src/pattern_unit_v2.h` (YENİ, additive-only;
  legacy dosyalara dokunulmadı) + `check_pattern_unit_v2.cpp` (T2/T3a/T3b/T3c/T4 OK);
  legacy V1–V8 OK, hash'ler `f0_baseline/HASHES.txt` ile aynı. K1/K2/K3 nöron-içi
  paralel kompartman; B-K1 yapısal olarak kablosuz.
- **Faz 2 (2026-09-16, ONAYLI-TAMAM).** `src/main_pattern_unit_v2.cpp` (YENİ) +
  `npu_pattern_unit_v2` gerçek kabloyu sürdü (öğrenme YOK, w0=1.0 sabit):
  `olay=300 mem=950`, P3a–f ~153–164 ateş, P3g–ac 0. K2/K3 ortak-sürüş baskın
  (coinc 950/950, Jaccard 0.41–0.87); birimler-arası farkın tek kaynağı K1-merkez
  (K2/K3 girdileri özdeş). 37 ayrı popülasyon vektörü, 270 tekrar. v2 deterministik
  (2 koşu bit-eşit). Legacy V1–V8 OK, hash'ler aynı. Ayar/sweep yapılmadı.
- **Faz 3 (2026-09-16, ONAYLI-TAMAM).** `pattern/pl_core.py` sonuna `PatternUnitV2`
  aynası (eklemeli) + `validate_pattern_unit.py` (YENİ): V1–V8-v2 + M1 HEPSİ OK.
  V8-v2 = öğrenme-KAPALI kilidi (`wkdev=0.0`, OZET-V2 satırı eklendi). M1: ayna
  ateş/sessizlik kümeleri C++ ile eşit; sayılar ±2 içinde (fixed-kuantalama farkı:
  örn. P3a 155/153). Legacy V1–V8 OK, hash'ler aynı. Q2 açık.
- **Faz 4 (2026-09-16, KABUL + KARAR).** Silme YOK: legacy KONTROL, v2 DENEYSEL
  olarak yan yana tutulur. Karşılaştırma (aynı kablo): legacy P3 47 ateş vs v2
  birim-başına ~153–164; ateş-tick kesişimi 1/47 (rejimler neredeyse ayrık —
  legacy öğrenilmiş-seçici, v2 öğrenmesiz-yoğun); v2 tick-başına dağılım
  1:117, 6:61 (tekil-birim tickleri baskın = ayrışma kanıtı). Kabul: v2 kapıları
  yeşil + legacy hash'ler aynı → v2 deneysel yol olarak KABUL. Öğrenme portu
  henüz KAPALI (wkdev=0 kilitli); açılma önerisi kararda, onay bekler.
- **Öğrenme portu (2026-09-16, ONAYLI-TAMAM, sweep yok).** soma-as-post, yalnızca
  v2 dosyaları, `--eta 0/0.30` (ontanım 0 = frozen rejim). V8L-learn OK:
  `--eta 0.30` wkdev=0.2607, mem 950→1053, deterministik; K2/K3 dörtlüsü
  +0.24–0.26 (birimler-arası tekdüze), K1c/m/p birim-özgül küçük (+0–0.05),
  P3g–ac ağırlık sapması 0; tekrarlar güçlendi (altılı 61→78x, vektör 37→42);
  frekans-çökmesi yok; eta=0 wkdev=0 + V1–V8 yeşil. Legacy V1–V8 OK, hash'ler aynı.
  Not: ilk `--eta 0.30` koşusu wkdev=0 verdi — neden LUT init eksikliği
  (`synapse_build_luts` sürücüde yoktu); eklendi, sorun çözüldü.
- **Davranış deneyleri (2026-09-16, ONAYLI-TAMAM, kod değişikliği yok).**
  Sentetik kablolar (A=(1,4), B=7-tren, varyantlar, A+B) × frozen/öğrenen ×2:
  determinizm 5/5. Kalıcılık ✓ (A1dom==A2dom iki rejimde de — sürüş-açıklamalı);
  enterferans-direnç ✓ (B, A'yı bozmadı); transfer ✗ (üç varyantın dominantı
  aynı altılı); emergans ✗ (AB-dom==A-dom, yenilik yok). Ortak-sürüş (K2/K3)
  bu patlama şiddetinde K1 farklarını yıkıyor — mekanik bulgu, gizlenmedi.
- **Düşük-şiddet kolları (2026-09-16, ONAYLI-TAMAM, kod değişikliği yok).**
  Tek-slot tren episodları, aynı ölçütler, determinizm 3/3: Q1 ✗ (A1dom altılı,
  A2dom P3a-yalnız — frozen'da da eşitsiz, sürüş-varyansı); Q2 ✓ (B ayrı);
  Q3 ✓-zayıf (çekirdek {P3a} + varyant-dominantlar farklı); Q4 kısmi (AB1==AB2
  stabil + AB-dom A/B'den farklı = rekombinasyon, ama güçlü-yenilik boş-küme).
  Öğrenen-frozen farkları mütevazı (wkdev 0.06–0.08).
- **Inference-tüketim (2026-09-16, ONAYLI-TAMAM, Pattern Lobe'a dokunulmadı).**
  `validate_infer_pattern.py` (YENİ): aynı protokol (TEST B, 175 aday, k=3,
  nearest-sequence, sızıntı-denetimi) Pattern Memory girdisiyle. Sonuç C:
  öğrenen 0.310 (n=174), frozen 0.356 (n=174) vs sensory 0.554 (n=175).
  Deterministik + sızıntısız OK. frozen > öğrenen. Legacy V1–V8 OK, hash'ler aynı.
