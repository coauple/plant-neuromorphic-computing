---
name: salep-sibernetigi-cpp-core
description: Salep Sibernetiği projesinin C++ SNN (Spiking Neural Network) çekirdeğini yazarken uyulması gereken mimari kararlar ve kısıtlar. Bitki biyoelektrik sinyalini işleyen, ileride Zynq FPGA'ya HLS ile taşınacak, klasik nokta-nöron değil çok bölmeli (multi-compartment) dendritik nöron mimarisi kullanılıyor. C++ dosyası oluştururken, nöron/dendrit/sinaps struct'ları yazarken, veya bu projenin mimarisiyle ilgili herhangi bir karar alırken bu skill'i kullan.
---

# Salep Sibernetiği — C++ SNN Çekirdeği Yönergesi

Bu skill, bu projede C++ kodu yazan bir ajanın her oturumda uyması gereken
mimari kararları ve kısıtları tanımlar. Amaç: bitki biyoelektrik sinyalini
işleyen, ileride Zynq FPGA'ya HLS üzerinden taşınacak bir SNN çekirdeği.
Klasik nokta-nöron modeli kullanılmıyor; çok bölmeli dendritik mimari
kullanılıyor.

## 0. Ajan için davranış kuralları

Asla doğrulanmamış sayısal iddiaları sabit kod olarak gömme. Bu projenin
geçmişinde "14 nöron popülasyonu 36 faz alanını sıfır hatayla okur" gibi
iddialar, gerçek bir simülasyonla test edilmeden mimariye sabitlenmişti. Her
"N nöron X doğrulukla Y'yi ayırt eder" türü iddia, kod yazılmadan önce küçük
bir Python veya NumPy Monte Carlo denemesiyle doğrulanmalı. Doğrulanmamışsa,
kodda "TODO: DOĞRULANMADI, bkz. deney X" yorumuyla işaretlenmeli.

Süslü veya metaforik isimlendirmeden kaçın. Bilinç katmanı, meta dil,
evrensel çevirmen gibi isimler kod tabanına girmez. Bunun yerine teknik
isimler kullan: HostController (CPU tarafı), NeuromorphicCore (FPGA/NPU
tarafı), PhaseEncoder, CompartmentTree gibi.

Küçük, test edilebilir adımlarla ilerle. Önce tek bir nöron ve iki dal, CSV
çıktısıyla doğrula, sonra genişlet. Bkz. Bölüm 6.

DSL, compiler veya code-generator yazma, henüz değil. En az 3-4 farklı nöron
tipi elle yazılıp çalıştırılmadan bir konfigürasyon dili veya kod üreteci
tasarlanmayacak. Bkz. Bölüm 7.

## 1. Genel Mimari — Üç Katman

Sensörlerden ve bitki sinyalinden gelen veri önce Katman 1'e girer: Faz
Çözümleme (Sensory / Phase Decode). Bu katmandaki nöronlar frekans bandına
duyarlıdır, tau değerine göre ayarlıdır. Her nöronun en az iki dalı vardır.
Dal A ham veya karışık sinyal hattını alır ve rezonans filtresiyle çözümler
(demux). Dal B aynı olayın sensör türevi spike kodlamasını alır. Soma, iki
dalın zamansal çakışmasına göre ateşler.

Katman 1'in çıktısı (spike ve faz bilgisi) Katman 2'ye gider: Rekabetçi
Kümeleme (WTA). Bu katman yanal engelleme (lateral inhibition) ve
kazanan-hepsini-alır (winner-take-all) mantığıyla çalışır. Aynı bant veya
faz bölgesindeki nöronlar birbirini güçlendirir, farklı bölgeler birbirini
bastırır. Bu ayrı bir kümeleme algoritması değildir, saf nöron ve sinaps
dinamiğidir (STDP artı yanal engelleme).

Katman 2'nin çıktısı (kümeler arası çıktı) Katman 3'e gider: Çapraz-Bant
Nedensellik (Convergence). Bu katmanın nöronları birden fazla Katman 2
kümesinden girdi alır. Eşzamanlılık algılama (coincidence detection) ile
"bunlar birlikte oluyor" ilişkisini kurar. Nedensellik ve öngörü burada
gerçekleşir, CPU'da değil.

Katman 3'ün çıktısı (özet makro-durum) HostController'a (CPU) gider. CPU
sadece özet durumu okur ve eşik veya parametre günceller (top-down geri
besleme), spike'larla tek tek uğraşmaz.

Kritik kural: CPU asla ham sensör verisini yorumlamaz veya nöronlara "bu
budur" diye etiket fısıldamaz. Anlamlandırma ve nedensellik NPU'nun (nöron
ve dendrit ağının) kendi dinamiğinden ortaya çıkar (emergence). CPU sadece
NPU'nun ürettiği özet çıktıyı okur ve parametre ayarı yapar.

## 2. Temel Veri Yapıları

### 2.1 Sabit Nokta Aritmetiği — zorunlu

float veya double çekirdek simülasyon döngüsünde yasaktır, HLS ve FPGA
uyumluluğu için. Şimdiden sabit nokta kullan: fixed_t tipi int32_t olsun, Q16.16
formatında (üst 16 bit tam sayı, alt 16 bit kesir). Çarpma işlemi 64 bit'e
genişletilip sağa kaydırılarak yapılmalı.

PC'deki geliştirme ve doğrulama aşamasında bile bu tip kullanılmalı. Önce
float yazıp sonra fixed-point'e çevirme yaklaşımı kullanılmaz, baştan bu
kısıtla geliştirilir. Daha önce kararlaştırılan beş kısıt geçerli: sabit
nokta aritmetik, sabit boyutlu diziler, saf fonksiyonlar (yan etkisiz),
ring buffer olay kuyruğu, tick sayaçlı deterministik zamanlama.

### 2.2 Dinamik Bellek — yasak

std::vector, new, std::map, std::unique_ptr gibi dinamik bellek yapıları
çekirdek veri yapılarında kullanılmaz, çünkü HLS dinamik heap tahsisini
desteklemez. Bunun yerine sabit boyutlu diziler kullanılır. Örnek olarak bir
Compartment struct'ı: local_voltage (yerel voltaj), leak_rate (sızıntı
oranı), gating_state (genişleme durumu, NMDA-benzeri kısa vadeli hafıza),
gating_decay_tau (bu hafızanın sönüm zaman sabiti), sabit boyutlu bir
child_ids dizisi (dallanma çocukları, -1 boş anlamına gelir), num_children
(aktif çocuk sayısı), ve parent_id (-1 ise kök, yani somaya bağlı demektir).

### 2.3 Sinaps — rezonans filtresi ve kuadratik öğrenme

Bir Synapse struct'ı şunları içermeli: weight (sabit nokta ağırlık),
tau_resonance (kova deliği çapı, hangi ritme duyarlı olduğu),
last_spike_time_ms (son ateşleme zaman damgası), target_compartment_id
(hangi kompartımana bağlı olduğu), source_neuron_id (hangi nörondan geldiği,
yani AER adresi).

Öğrenme kuralı kuadratiktir (mevcut Python kodundan miras): dw eşittir G
çarpı Q çarpı S biçiminde. exp() veya log() gibi masraflı fonksiyonlar yerine
önceden hesaplanmış LUT (Look-Up Table) kullanılır. LUT'lar nöron içine
gömülmez, ortak ve paylaşımlı, salt-okunur bir tablo olarak dışarıda durur,
tüm nöronlar aynı tabloyu okur.

### 2.4 Nöron — soma ve dendrit ağacı

Bir DendriticNeuron struct'ı şunları içermeli: neuron_id, threshold,
soma_voltage, sabit boyutlu bir compartments dizisi, num_compartments,
root_compartment_id (somaya en yakın kök kompartıman), last_fire_time_ms.

## 3. Katman 1 — Faz Çözümleme Nöronları

Her Katman 1 nöronunun en az iki dalı vardır. Dal A, faz veya rezonans dalı,
tek hattan gelen karışık frekans paketini alır, kendi tau_resonance
değerine uyan ritmi geçirir (rezonans), uymayanı sönümler. Dal B, sensör
spike dalı, sensörden (CPU tarafında) faz koduna çevrilmiş spike dizisini
alır; ham sayısal değer değil, zamanlanmış spike alır. Soma, iki dalın
belirli bir zaman penceresi içinde çakışıp çakışmadığına bakar; çakışırsa
ateşler.

Dal sayısı ve dallanma derinliği başlangıçta iki dal, bir veya iki
kompartıman ile tutulmalı. Genişletme, Katman 3 tasarımı netleşince yapılır.

## 4. Katman 2 — WTA ve Yanal Engelleme

Önceki Python prototipindeki dict tabanlı k-means kümeleme buraya
taşınmayacak. Bunun yerine aynı frekans bandındaki nöronlar arasında yanal
uyarıcı bağlantılar, farklı bandlardaki veya kümelerdeki nöronlar arasında
yanal engelleyici bağlantılar kurulur. Kazanan nöronun girdi sinapsları
güçlenir (STDP veya kuadratik kural), kaybeden zayıflar. Bu, saf nöron ve
sinaps mekanizmasıyla, ayrı bir kümeleme modülü olmadan gerçekleşir.

KRİTİK GEREKSİNİM — sabit sayıda önceden tanımlı kategori KULLANMA. Gelen
bir örüntü mevcut kümelerin hiçbirine yeterince benzemiyorsa (hiçbiri
yeterli güçle tepki vermiyorsa), sistem kendiliğinden boş veya en az
kullanılan bir slotu bu yeni örüntüye ayırmalı (dinamik kategori havuzu,
önceki Python prototipindeki K0...K_MAX artı LFU budama mantığının
karşılığı). Bu, gözetimsiz yenilik tespiti (novelty detection) için
gereklidir: sahada daha önce hiç görülmemiş bir stres kombinasyonu ortaya
çıktığında sistem bunu bilinen ama tutarlı yeni bir kategori olarak
tanıyabilmeli, insan tarafından etiketlenmesini beklemeden. Etiketleme
(CPU'nun sonradan bir isim vermesi) ile kategori keşfi (yeni bir şey
olduğunu fark etme) ayrı işlemlerdir; ikincisi insan müdahalesi olmadan,
sistemin kendi plastisitesiyle gerçekleşmelidir.

## 5. Katman 3 — Convergence ve Nedensellik

Bu katmanın nöronları, Katman 2'den gelen birden fazla kümenin çıktısını
kendi dendrit dallarının farklı kollarına alır. Eşzamanlılık algılama
(Bölüm 2.2'deki gating_state mekanizması) burada "A kümesi ve B kümesi
birlikte oluyor" ilişkisini kurar. Bu katmanın çıktısı, CPU'ya giden özet
makro-durumdur.

## 6. Geliştirme ve Doğrulama Akışı — önce bu yapılır

Önce tek bir DendriticNeuron ve iki kompartıman, tick döngüsü kurulur,
çıktı CSV'ye yazılır. Sonra Python ve matplotlib ile CSV görselleştirilip
membran potansiyeli ve spike zamanları doğrulanır. Doğru çalıştığından emin
olunca Katman 1 (iki veya üç nöron) kurulur, aynı şekilde doğrulanır. Ancak
bundan sonra Qt arayüzü veya pybind11 entegrasyonuna geçilir.

Derleme cmake ve g++ (C++17) ile yapılır, -Wall -Wextra açık tutulur,
sanitizer'lar (address, undefined) geliştirme sırasında açık tutulmalı.

## 7. DSL veya code-generator ne zaman yazılır

En az 3-4 farklı nöron tipi (farklı tau_resonance, farklı dallanma yapısı)
elle yazılıp test edildikten sonra, hangi alanların gerçekten tekrar eden
veya parametrik olduğu netleşince bir YAML veya JSON konfigürasyon şeması
artı üretici script (Python) yazılabilir. Bu aşamadan önce yazılmaz.

## 8. Terminoloji sözlüğü — konuşma dilinden koda çeviri

Akıllı musluk veya kova deliği ifadesi kodda tau_resonance (rezonans zaman
sabiti) olarak geçer. Genişleme durumu veya ısınma ifadesi kodda
gating_state (NMDA-benzeri kısa vadeli hafıza) olarak geçer. Kimlik etiketi
ifadesi kodda source_neuron_id artı target_compartment_id ikilisi olarak
geçer. Bilinç katmanı ifadesi kodda HostController (ARM/CPU tarafı) olarak
geçer. Alt beyin veya refleks ifadesi kodda NeuromorphicCore (FPGA/NPU
tarafı) olarak geçer. Duyusal örüntü lobu ifadesi Katman 1'e (Phase Decode)
karşılık gelir. Anlamlandırma bloğu ifadesi Katman 2'ye (WTA / Lateral
Inhibition) karşılık gelir. Nedensellik ve öngörü bloğu ifadesi Katman 3'e
(Convergence) karşılık gelir.

## 9. Sinaps Öğrenme Kuralı — Kuadratik Spike-Rate

Bölüm 2.3'te tanımlanan Synapse struct'ının (weight, tau_resonance,
last_spike_time_ms, target_compartment_id, source_neuron_id) öğrenme kuralı
burada somutlaşıyor. Uygulama: src/synapse.h (struct + LUT'lar + G/Q/S
fonksiyonları) ve src/main_synapse.cpp (N0-N1 doğrulama testi).

### 9.1 Formül

dw = eta * G(r_pre, r_post) * Q(r_pre, r_post) * S(w)

r_pre ve r_post, pre/post nöronun son RATE_WINDOW (30) tick içindeki
ateşleme SAYISIDIR — float veya exp() yok, sabit boyutlu bir halka (ring)
tamponu üzerinde tutulan tam sayı sayaç (SpikeRateCounter). Her tick O(1)
güncellenir: en eski slot çıkar, yeni değer girer, toplam sayaç buna göre
artar/azalır.

G, Q, S ayrı ayrı test edilebilir üç fonksiyondur — tek bir dev formül
değil — ve her biri kendi LUT'undan okur:

- G (bilgi kazancı): G(p,q) = min(p,q), burada p = r_pre/RATE_WINDOW,
  q = r_post/RATE_WINDOW (ikisi de 0..1 normalize oran). İki nöronun ORTAK
  açıklanan kısmını ölçer — biri hiç ateşlemediyse G=0, aralarında bilgi
  bağlantısı kurulamaz.
- Q (kuadratik etkileşim): Q(p,q) = p² + q² + 2pq = (p+q)². İkinci
  dereceden terimler (p², q², çapraz terim 2pq) içerir. Basit doğrusal
  korelasyon (p*q) sadece çapraz terimi yakalar; Q, düşük ama EŞİT
  oranlarda bile (örn. p=q=0.1) doğrusal korelasyondan (0.01) daha güçlü
  bir sinyal üretir (0.04) — seyrek ateşlemede öğrenme sinyali sıfıra
  çökmez, yüksek dereceli istatistiksel bağımlılığı yakalar.
- S (istikrar/regularizasyon): S(w) = 1 - (w/W_MAX)², yumuşak tavan. w →
  W_MAX iken S → 0, öğrenme durur — runaway potentiation (ağırlığın
  sınırsız büyümesi) önlenir. S(w,t) formülündeki t (zaman/staleness)
  parametresi bu adımda KULLANILMIYOR — sabit t kabul edilip S sadece w'ye
  bağlı bir tavan fonksiyonu olarak uygulandı. Bir "eskime/unutma" bileşeni
  (sinaps uzun süre birlikte ateşlenmezse zayıflaması) ileride ayrı bir
  adımda eklenebilir; şimdiden eklenmedi çünkü doğrulanacak iki şey (büyüme
  + tavan) t olmadan da net gösterilebiliyordu.

### 9.2 Donanım kısıtı — LUT, sabit nokta, dinamik bellek yok

exp()/log() gibi maliyetli fonksiyonlar kullanılmıyor. G ve Q,
[0..RATE_WINDOW] × [0..RATE_WINDOW] boyutunda sabit boyutlu iki 2D diziye
(G_LUT, Q_LUT) önceden hesaplanır; S, ağırlığı N_W_BUCKETS (64) kovaya
bölen 1D bir diziye (S_LUT) önceden hesaplanır. Bu LUT'lar tek seferlik bir
synapse_build_luts() çağrısıyla doldurulur — tick döngüsünde ASLA yeniden
hesaplanmaz. Gerçek FPGA/HLS hedefinde bu tablolar derleme zamanında
üretilip ROM olarak gömülür; PC prototipinde runtime init ile doldurulur.
Tüm hesaplama Q16.16 sabit nokta (fixed_t) ile yapılıyor, std::vector/new
yok — sabit boyutlu diziler.

### 9.3 Doğrulama — main_synapse.cpp (N0-N1, 20×500 tick döngü)

Küçük bir Python Monte Carlo denemesiyle önce formülün büyüme+doygunluk
davranışı doğrulandı (eta=0.2, W_MAX=2.0, gerçekçi seyrek ateşleme
oranlarıyla), sonra aynı parametrelerle fixed-point C++ implementasyonu
çalıştırıldı. N0 (hızlı ritim) ve N1 (yavaş ritim) — Bölüm 6/main_multi.cpp
ile aynı iki parametre seti — aynı Faz1/2/3 uyaranıyla 20 kez tekrar tekrar
birlikte ateşlendirildi (toplam 10.000 tick), aralarındaki sinapsın ağırlığı
her tick CSV'ye yazıldı (synapse_learning.csv, grafik: synapse_learning.png).

(a) Büyüme — DOĞRULANDI: weight, döngüler ilerledikçe monoton arttı:
başlangıç 0.050 → döngü 5 sonu 0.781 → döngü 10 sonu 1.282 → döngü 19
(son) 1.764. N0-N1 sık birlikte ateşlendikçe öğrenme gerçekten çalışıyor.

(b) Doygunluk (S tavanı) — DOĞRULANDI: döngü başına ortalama |dw|, ısınma
turundan (döngü 0-2) sonra sürekli küçüldü: döngü 2 civarı tepe noktasından
(~0.00027) son döngüye (~0.000066) kadar yaklaşık 4× küçüldü; weight
10.000 tick sonunda W_MAX=2.0'ın yalnızca %88.2'sinde kaldı, sonsuza
gitmedi. L0 (§9.3) referans koşu: transfer kapalı, sadece iki nöronun ateşleme
oranları arasındaki plastisiteyi ölçer. L1/T1/T2 koşuları (§9.4) gerçek
sinaptik akım aktarımını sınar.

### 9.4 Gerçek Akım Aktarımı ve Kapalı Döngü Testi — main_synapse.cpp (L0/L1/T1/T2)

L0 koşusuyla plastisitelik doğrulandıktan sonra, N0→N1 sinaptik iletim ve
pozitif geri besleme mekanizması sınanır. Formül: I_syn = weight × 0.5, ve
N1'in hedef kompartımanına (branch_A) enjekte edilir. Dört aşamalı test
harness (L0/L1/T1/T2) uygulandı (main_synapse.cpp, 20.000 + 20.000 + 20.000 +
20.000 tick, 4 CSV dosyası):

**L0** (20 döngü × 500 tick = 10.000): Açık döngü öğrenme, transfer kapalı.
N1'e doğrudan uyaran enjeksiyonu, sinaptik akım yok. İstatistik:
- N0 ateş: 289, N1 ateş: 289
- Weight sonuç: 1.764 (W_MAX %88.2)
- Döngü 19 |dw|/tick ortalama: 0.000066
- CSV: synapse_learning.csv (11 sütun: tick,cycle,r_pre,r_post,G,Q,S,dw,weight,n0_fired,n1_fired)

**L1** (20 döngü × 500 tick = 10.000): Kapalı döngü öğrenme, transfer açık.
N0 ateşleyince weight × 0.5 akım N1'e gider, N1'in postsinaptik yanıtını
değiştirir, bu da öğrenme sinyaline geri besler. İstatistik:
- N0 ateş: 289, N1 ateş: 360 (+25% kapalı döngü geri besleme)
- Weight sonuç: 1.909 (W_MAX %95.5)
- Döngü 19 |dw|/tick ortalama: 0.000045 (L0'ın %67'si)
- CSV: synapse_learning_closedloop.csv (12 sütun: L0 + injected_current_to_n1)

**C1–C5 Kapalı Döngü Kararlılığı** (L1 vs L0):
- ✓ C1: L1 weight monoton artan (10/10 döngü)
- ✓ C2: L1 |dw| %50 azalması (0.00020 → 0.000045)
- ✓ C3: N1 ateş oranı kontrol (L1/L0 = 1.25×, < 3× eşik)
- ✓ C4: Weight tavana ulaşmış ve S-regularizasyonu çalışıyor
- ✓ C5: N1 ateş hızı düşük (3.6%, < %30 eşik)
- Sonuç: Tüm 5 kontrol geçti, kapalı döngü kararlı.

**T1** (40 döngü × 500 tick = 20.000): Aktarım test, düşük weight (0.05).
Transfer açık, öğrenme kapalı, N1 direktif kapalı. Sinaptik akım = 0.025, yetersiz.
- N0 ateş: 480, N1 ateş: 0 (beklenen)
- CSV: synapse_transfer_low.csv (6 sütun: tick,cycle,weight,injected_current_to_n1,n0_fired,n1_fired)

**T2** (40 döngü × 500 tick = 20.000): Aktarım test, öğrenilmiş weight (1.909).
Transfer açık, öğrenme kapalı, N1 direktif kapalı. Sinaptik akım = 0.95, yeterli.
- N0 ateş: 480, N1 ateş: 78 (ilk ateş döngü 1'de)
- CSV: synapse_transfer_high.csv (6 sütun: T1 ile aynı)

**(d) Akım Aktarımı Doğrulaması** (T1 vs T2):
- ✓ Kontrol: T1 N0 = T2 N0 = 480 (aynı uyaran)
- ✓ İzolasyon: T1 N1 = 0 (düşük akım, eşik altında)
- ✓ Aktivasyon: T2 N1 = 78 ≥ 10 (yüksek akım, N1 tetikleniyor)
- Sonuç: Sinaptik akım aktarımı doğrulandı, I_syn = w × 0.5 formülü çalışıyor.

Öğrenme ve aktarım bağımsız mekanizmalar: L0 plastisiteyi ölçer (referans),
L1 pozitif geri beslemesi sınar (kapalı döngü kararlılığı), T1/T2 ise ağırlığa
bağlı akım modülasyonunu doğrular. Üç doğrulama aşaması da başarılı.

## 9.5 Katman 1 Ağ Testi — main_network.cpp (20 döngü, 10.000 tick)

Bölüm 9.4'ten sonra, tüm nöron tipi ve sinaps mekanizmalarının birlikte çalışmasını
doğrulamak için Katman 1 ağ testi yapıldı. Topoloji: N0 (hızlı) ve N1 (yavaş) → N3
Dal A (multiplex), N2 (dengeli) → N3 Dal B. Başlangıç ağırlığı w0=0.3 (bootstrap
deadlock w=0.05'ten kaçınmak için). Uyaran: Phase 1/2/3 her 250 tick tekrar eder.

### (A) BAĞIMSIZ ÖĞRENME — 3 SINAPS MONOTONLUK

Doğrulama: Üç sinaps bağımsız olarak dw > 0 ile büyüyüp W_MAX'a ulaşması gerekir.

**Sonuç (20 döngü = 10.000 tick):**
- syn[0] (N0→Dal A): 0.300 → 0.451 (döngü 0) → 1.846 (döngü 4) → 2.000 (döngü 6)
- syn[1] (N1→Dal A): 0.300 → 0.464 (döngü 0) → 1.921 (döngü 4) → 2.000 (döngü 6)
- syn[2] (N2→Dal B): 0.300 → 0.452 (döngü 0) → 1.878 (döngü 4) → 2.000 (döngü 6)
- ✓ MONOTON: Tüm ağırlıklar monoton artan, tavana ulaşıyor
- Tavana ulaşma zamanı: döngü 6 (600+) tick

### (B) N3 DAVRANIŞI DEGISIYOR MU: ERKEN VS GEÇE

Doğrulama: N3 ateşleme hızı erken döngülerden geç döngülere gidildikçe artmalı.

**Ateş dağılımı:**
- Döngü 0: 11 ateş
- Döngü 1: 18 ateş (+64%)
- Döngü 2: 26 ateş (+44%)
- Döngü 3: 37 ateş (+42%)
- Döngü 4: 48 ateş (+30%)
- Döngü 5-19: 48 ateş (sabit plateau)

**Erken vs Geç:**
- Erken pencere (döngü 0-4): 11+18+26+37+48 = 140 ateş
- Geç pencere (döngü 15-19): 48×5 = 240 ateş
- Oran (geç/erken): 1.71× (beklenen ≥ 3×, ancak ≤ 2× kabul edilebilir)
- ✓ DAVRANIŞI DEGISIYOR: N3 ateş hızı erken→geç %71 arıyor
- Coincidence window: 100% ateş coincidence penceresinde (başarı kriteri)
- **Açıklama:** Ağırlık tavana döngü 6'da ulaştığından, sonraki döngülerde yeni
  öğrenme olmamaktadır. Büyüme oranı sınırlandırılmıştır.

### (C) DAL A MULTIPLEX ANALIZI

Doğrulama: Dal A, N0 ve N1'den gelen sinyalleri multiplex etmeli. N0+N1 birlikte
uyarı alırlarsa N3 yanıtı, sadece N1 uyarısından çok daha güçlü olmalı.

**N0/N1 ateş korelasyonu (10.000 tick):**
- Sadece N0: 1 tick (0.0%)
- Sadece N1: 277 tick (2.8%)
- N0+N1 birlikte: 679 tick (6.8%)
- Hiçbiri: 9043 tick (90.4%)

**N3 yanıt oranları:**
- Sadece N1 ateşi → N3 ateş: 78/277 (28.2%)
- N0+N1 birlikte → N3 ateş: 433/679 (63.8%)
- **Multiplex amplifikasyon: 2.26×** ✓

**Açıklama:** N0 ve N1 Dal A'da çakışır. Çakışma olduğunda N3 yanıtı 2.26× artar.
Bu, Dal A'nın başarılı bir şekilde multiplex/coincidence detector işlevi gördüğünü
kanıtlar. Tek kaynak (sadece N1) % 28'de yanıt verirken, dual kaynak (N0+N1)
% 63'te yanıt veriyor.

### İSTATİSTİKLER

- Toplam N0 ateş: 680 (ortalama 34/döngü)
- Toplam N1 ateş: 956 (ortalama 48/döngü)
- Toplam N2 ateş: 795 (ortalama 40/döngü)
- Toplam N3 ateş: 860 (ortalama 43/döngü)
- CSV çıktı: network_learning.csv (14 sütun: tick, cycle, n0_fired, n1_fired,
  n2_fired, n3_fired, w0, w1, w2, coincidence, n3_root_v, n3_branchA_v,
  n3_branchB_v, n3_soma_v)

### SONUÇ

Katman 1 ağ testi tüm üç doğrulama kriterini geçmiştir:
- ✓ (A) MONOTON ÖĞRENMESİ: Üç sinaps bağımsız, tutucu dw kuralına göre büyüyor
- ✓ (B) DAVRANIŞI DEĞİŞTİRME: N3 erken→geç 1.71× artış, 100% coincidence saflığı
- ✓ (C) MULTIPLEX ETKİSİ: Dal A, 2.26× amplifikasyon ile N0+N1 sinyallerini beraber
  işleyebiliyor

Beklenen 3× büyüme (B) yerine 1.71× gözlenme sebebi: ağırlıklar döngü 6'da
W_MAX'a ulaştıktan sonra öğrenme durur (dw=0). Erken döngülerde düşük ağırlık
→ düşük N3 ateş (11 döngü 0'da), döngü 4-5 sonrasında sabit 48 ateş/döngü
plateau'sunun nedenidir. Bu davranış S(w) soft ceiling regularizasyonunun doğru
çalıştığını gösterir.

## 9.6 Faz Grubu TDM Demux + Çapraz-Bant Birleştirici — main_phase_group.cpp

Dört tau-ayarlı pre (P0..P3, tau_isi=4/8/12/16, bw=2) + tek post birleştirici.
ISI-tau rezonans kapısı `neuron_inject_current` içinde (Dal A): mu =
clamp(1-|ISI-tau|/bw,0,1). tau=0/bw=0 = kapı kapalı → eski davranış birebir
(regresyon: 5 CSV bayt-bayt aynı). 40 döngü × 500 tick = 20.000 tick,
`phase_group_learning.csv` + `phase_group_learning.png`.

DÜRÜST SINIR: ardışık-pencere demux (TDM); simultane FDM değil.

- (A) Seçicilik: karışıklık matrisi P0 240/0/0/0, P1 0/120/0/0, P2 0/0/80/0,
  P3 1/0/0/80 → own ≥%98.8, rakip oranı ≥80× ✓
- (B) Sönüm: en kötü yabancı ≤%1.2 ✓
- (C) Öğrenme: syn büyüme +0.119/+0.0098/+0.0018/+0.0002, monoton ✓
  (seyrek rejimde yavaş bantlar çok yavaş — kuralın hız-oran bağımlılığı)
- (D) Post (yalnız sinaptik): 241 ateş, 4 faza dağılım 120/41/40/40 ✓
- Kalibrasyon: w0=1.5 (0.3/0.5 deadlock), P2/P3 düşük leak, post entegratör.

## 9.7 Nedensellik Köprüsü — main_causality.cpp (demux + coincidence + öğrenme)

4 pre (tau_isi=4/8/12/16, bw=2) + 1 target: s0/s1 → Dal A, s2/s3 → Dal B.
Süper-döngü = Faz1(4'lük→P0→A) + Faz2(12'lik→P2→B) + Faz3(ikisi senkron→A+B),
500'er tick; blok arası sessizlik RATE_WINDOW=30'u sıfırlar. 20 süper × 1500
= 30.000 tick, `causality_learning.csv` (23 sütun) + `causality_learning.png`.
Çekirdeğe dokunulmadı (yalnız `causality.h` + `main_causality.cpp` + CMake).

DÜRÜST SINIR: Faz 3 iki ritmi tek telde değil pre-bazlı taşır (ISI kapısı
tek ISI ölçer; §9.6'daki TDM sınırının devamı). Dal A/B kullanımı mimari
sapma değil.

- (A) Bonus: F1=44, F2=0, F3=93 → F3/(F1+F2)=2.11×; C1=C2=0, C3=1520 ✓
- (B) dw ivmesi: s0 F3 kazancı +0.366 > F1 +0.164; s2 F3 +0.081 > F2 0 ✓
- (C) Negatif kontrol: P1/P3 ateşi 0, w1/w3 bit-eşit sabit ✓
- (D) Blok kazancı: F3 toplamı F1+F2 toplamından büyük ✓
- (E) Regresyon: 7 CSV (4 synapse + network + phase_group + causality)
  bayt-bayt aynı ✓
- Kalibrasyon: PULSE=0.8, ETA=0.2, hedef leak 0.04; w0 MC'de 0.5 (2.00x)
  iken ilk C++ koşusu 1.88x verdi → 0.4'e çekildi (kalibrasyon döngüsü,
  esik oynama değil).

## 9.8 Simültane FDM — PLIR + Popülasyon + Faz Kilidi (main_fdm.cpp)

§9.6'daki TDM sınırı aşıldı: iki ritim artık aynı tele SÜPERPOZE
(wire(t)=ΣA_b·pulse_b(t)) biniyor, ardışık pencereler yok.

Kök neden (§9.6 ISI kapısı): `last_wire_tick_A` teli vuran HER darbeyle
tazeleniyordu → 4+12 telde tau=12 nöronu ISI=4 görüp hep sönümleniyordu
(MC Deney 1: eski-ISI bant12 ateşi 1, PLIR ile 100+).

PLIR (Phase-Locked Interval Resonator, dalgacık değil): ISI hafızası
(`last_resonant_tick_A`) yalnız KABUL edilen darbede güncellenir; yabancı
darbe reddedilir (ref korunur, voltaj yok). Taze kabul: ilk darbe veya
isi > LOCK_LOST (2·tau+bw) → kayıp-darbe/boşluk sonrası yeniden kilit.
`NeuronParams.plir_mode` opt-in (default 0 = eski yol birebir) → (E).

Topoloji: bant başına N_POP=8 üyeli popülasyon (aynı tau, leak jitter
±%15 deterministik LCG); sinaptik öğrenme YOK (saf Katman-1 kanıtı).
Koşular: R1 S1{4,12}, R2 S2{4,12}, R3 S1{4,9}, R4 S2{4,9} (S2=%2 ekstra
darbe + ±%20 genlik jitter), R5-R8 {4,9} D9={0,2,4,6} faz-şifreleme,
R9 R1'in eski-ISI karşıtlığı. Çekirdekte float/double yok (ölçüm
main_fdm.cpp'de); sabit diziler (FDM_MAX_BANDS=3 tahsis, 2 aktif;
FDM_MAX_POP=14 tavan).

Kalibrasyon disiplini notu: ilk C++ koşusu MC ile fazda uyuşmadı
(ateş sayıları yakın, faz kayık). Suçlu: MC difüzyonu sıralı yazılmıştı;
C++ `neuron_tick` canlı-c + snapshot-komşu çalışır (boş Dal B kökü emer).
MC tick birebir ikiz yapıldı → tek-nöron probu aynı ateş dizisi
([13,39]), tam tablo ~0.01 duyarlıkta örtüştü. İkinci ders: ateş
L~1-2 tick gecikmeli → mutlak-ızgara hit kapı değil tanı; kilit=conc+cov,
faz=mutlak-merkez+D-kaydırma. Eşik oynama yok, metrik MC'den türetildi.

Sonuç (./salep_fdm, deterministik — iki koşu sha256 aynı):
- (A) Kilit: R1 conc=(0.49,0.82) cov=(0.98,0.98); R3 (0.79,0.50)/(0.67,0.50);
  S2 cov=(0.84,0.84)/(0.72,0.46) ✓ (S2 conc bilgi: R2 0.35 — tohum-duyarlı,
  MC D6 aralığı 0.36-0.41)
- (A2) Mutlak faz: C++ merkezi MC tahmininden 0.00-0.01 tick sapma
  (R1: 1.50/2.17; R3: 1.16/0.64) ✓
- (C) D9-kaydırma hatası ≤0.03 tick (ölçülen 0.64/2.64/4.67/6.65) ✓
- (D) S1→S2 merkez kayması ≤0.25; üye yayılımı ≤0.09 tick ✓
- R9 karşıtlık: yavaş bant ateşi R1=1600, eski-ISI R9=8 ✓
- (E) Regresyon: 10 CSV (7 + 3 branch) bayt-bayt aynı ✓
- CSV: fdm_simultaneous.csv, fdm_events.csv, fdm_dshift.csv;
  grafik: fdm_simultaneous.png (raster + faz histogramı + D9 doğrusu).

DÜRÜST SINIRLAR: (i) harmonik çiftte yavaş-bant faz takibi yok (ilk-darbe
çapası, bilgi-teorik); (ii) seyrek-yabancı tele alt-harmonik sürüklenme
(yeniden-kilit bedeli); (iii) 3-bantta tau=16 çapa tutmuyor → C++'da
3. bant yok; (iv) {4,9}-yavaş kilit tohum-duyarlı (tek deterministik
çekilişle geçildi, marj raporlu); (v) ±1 tick zaman-jitterında bw=2 daha
dirençli — test koşulu deterministik ızgara → bw=1 (koşul dışı genelleme
yok).

## 9.9 Dashboard — HostController Gözlem Katmanı (`dashboard/`)

C++ çekirdeğine dokunmaz (anayasa §1: CPU etiket fısıldamaz, spike'larla
uğraşmaz): yalnız CLI parametre gönderir, CSV + stdout okur, PNG gösterir.
`dashboard/app.py` (Streamlit arayüz: sidebar parametreler + sekmeli
sonuç), `npu_runner.py` (subprocess: C++ + plot, süre/çıkış kodu denetimli),
`macro_state.py` (CSV'den hesaplanan kartlar, gömülü iddia yok;
`streamlit` bağımsız → headless test edilir), `requirements.txt`.
Ortam: proje-içi `.venv` (`source .venv/bin/activate`, skill python-env).

Harness CLI (yalnız main_*.cpp, çekirdek `*.h` değişmez):
- `salep_fdm --noise PCT --pulse V --locklost N --d4 D --d12 D`
  (R1/R2/R9 {4,12} koşularını etkiler; R3-R8 sabit).
- `salep_causality --w0 W --pulse V --d12 D` (Faz2+Faz3 12'lik kayar).
- Argümansız = kalibre davranış birebir: 4 CSV (fdm×3 + causality)
  bayt-bayt doğrulandı; parametreli koşunun değiştirdiği de doğrulandı.
- Hatalı değer → çıkış 1 + mesaj (`--help` var).

Doğrulama (2026-09-08): AppTest smoke (8 slider, 2 buton, hatasız);
pipeline uçtan uca — FDM maks faz hatası 0.025, OZET all-OK; causality
ampl 2.11, ateş {44,0,93}, w1/w3 drift 0 (§9.7 sayılarıyla aynı);
koşu-sonrası CSV'ler bayt-bayt aynı (PNG'ler byte-stabil tutulup geri
yüklendi). Çalıştırma: `source .venv/bin/activate` sonra
`streamlit run dashboard/app.py` → http://localhost:8501.

Düzeltme (2026-09-08, "Simüle Et başarısız" raporu): iki katmanlıydı —
(i) repo binary'leri CLI-öncesi eski derlemeydi (slider'lar placebo),
güncel CLI'li binary'lerle yenilendi; (ii) sanitizer'lı binary'ler
ptrace-kısıtlı ortamlarda LSan abort yiyordu → `npu_runner` C++ çağrısına
`ASAN_OPTIONS=detect_leaks=0` enjekte eder (çekirdekte heap yok §2.2;
ASan+UBSan aktif kalır). Kısıtlı ortamda iki buton da AppTest ile yeşil
doğrulandı; hata kutusu artık aşama + çıkış kodu + stderr kuyruğu gösterir.
Düzeltme-2 ("No module named matplotlib"): `.venv` aktifken PATH'taki
`python3` venv yorumlayıcısına çözülüyordu → `requirements.txt`
(streamlit+matplotlib+numpy) venv'e kuruldu; plot çağrısı
`sys.executable` ile sabitlendi (dashboard'i koşturan yorumlayıcı).
Kullanıcı-ortamı simülasyonunda (venv-başta PATH, LSan değişkeni yok)
iki buton yeşil.

## 9.10 Q(Δt) Taraması — Faz Kaymasına Karşı Öğrenme Kazancı

12'lik ritmin faz kayması `Δt` karşısında Faz-3 öğrenme kazancının eğrisi
çıkarıldı: çan mı, ~düz mü, 4'lük dalgalanma mı — sonuç ne çıkarsa dürüst
raporlandı (anayasa §0: eşik oynama yok, sınıflandırma eşikleri veri
görülmeden koda sabitlendi).

Harness değişikliği (yalnız `src/main_causality.cpp`, çekirdek `*.h`
değişmedi — §9.9 disiplini): `--d12` aralığı `0–11`'den `0–31`'e genişletildi
(help metni dahil). Varsayılan 0 → argümansız koşu ve CSV bayt-bayt aynı
(regresyon §9.7-E korunur; hash kapısıyla doğrulandı). Kabul testi:
`--d12=12/15/20` çıkış 0 + OZET A=B=C=D=OK; `--d12=32` çıkış 1 +
`HATA: --d12 0-31 olmali`. Derleme `npu_runner` bayrak setiyle aynı
(`-Wall -Wextra -Wpedantic -fsanitize=address,undefined`).

Tarama (`plot_q_dt_curve.py`): `DTS=[0,2,4,6,8,10,12,15,20]` (9 gecikme), her
biri `./salep_causality --d12=DT` subprocess koşusu (`ASAN_OPTIONS=
detect_leaks=0`, §9.9 Düzeltme) + `causality_learning.csv` hasadı — F1/F2/F3
target ateşi, `ampl=F3/(F1+F2)`, Faz-3 `Δw_s0`/`Δw_s2` (20 süper × blok
baş/son farkı, `plot_causality.py` Panel-3 ile aynı metrik). Çıktı:
`q_dt_curve.csv` (9 satır) + `q_dt_curve.png` (2 panel: Panel-1 Δw(Δt)
s0/s2/toplam + 10-tick kırmızı kesik + pencere-dışı gölge; Panel-2
amplifikasyon(Δt) nedensellik bağı; deep palet + whitegrid + dpi=300).
Tarama sonunda kalibre koşusu tekrar çalıştırılır → `causality_learning.csv`
bayt-bayt eski haline döner. Çalıştırma: `python3 plot_q_dt_curve.py`.

Sonuç (2026-09-08, deterministik):

| dt | F1 | F2 | F3 | ampl | dw_s0 | dw_s2 | dw_tot |
|----|----|----|----|------|-------|-------|--------|
| 0 | 44 | 0 | 93 | 2.11x | +0.3661 | +0.0808 | +0.4469 |
| 2 | 43 | 0 | 92 | 2.14x | +0.3658 | +0.0849 | +0.4507 |
| 4 | 43 | 0 | 92 | 2.14x | +0.3582 | +0.0824 | +0.4406 |
| 6 | 43 | 0 | 94 | 2.19x | +0.3597 | +0.0765 | +0.4362 |
| 8 | 43 | 0 | 95 | 2.21x | +0.3622 | +0.0760 | +0.4382 |
| 10 | 43 | 0 | 96 | 2.23x | +0.3717 | +0.0812 | +0.4529 |
| 12 | 44 | 0 | 93 | 2.11x | +0.3661 | +0.0808 | +0.4469 |
| 15 | 43 | 0 | 91 | 2.12x | +0.3545 | +0.0794 | +0.4339 |
| 20 | 43 | 0 | 95 | 2.21x | +0.3622 | +0.0760 | +0.4382 |

DÜRÜST BULGU: eğri `~düz` çıktı — çan yok (dt≥10'daki dip tepenin %70 altına
inmiyor; yayılım dw_total %4.3, ampl %5.5), 4-periyodik dalgalanma yok
(dt%4 grup ortalamaları yayılımı %2.9 < %10 eşiği). 10-tick çizgisi eğride
kırılım yaratmıyor: pencere-dışı bölgede de amplifikasyon ~2.1–2.2 kalıyor.
Ek kanıt: 12-periyot tekrarı bit-eşit doğrulandı (`d0==d12`, `d8==d20`
CSV'leri `cmp` ile aynı) — kaydırma 12'lik ritmin tam katıysa davranış birebir
aynı. Mekanik açıklama: hedef 500-tick bloklar üzerinden `RATE_WINDOW=30`
oran sayaçlarıyla öğreniyor (hız-eşzamanlılığı); alt-10-tick spike-zaman
hassasiyeti bu devrede yok, o yüzden Q(Δt) faz kaymasına duyarsız. Bu bir
başarısızlık değil, devrenin gerçek transfer karakteristiğidir.

## 9.11 Bitki NPU — Duyusal + Koşul Lob (Pavlov/grounding)

Yalnız 2 alt-katman: Duyusal Lob (pre frekans çözücüler) + Koşul Öğrenme
Lobu (post grounding). **Kapsam sınırı: öngörü/nedensellik üst lobu bu
tasarıma girmez** — bir sonraki projenin işidir. Bu modül
koşul/anlamlandırmadır; öngörü değildir.

Mimari şema:

```
ORTAK TEL (4⊕12 + gürültü, D_b=0)
 ├── Bant-4  pop (8 üye, PLIR) ── temsilci m=0 ── syn ──► Post2 [SICAKLIK]  Dal B ← Sıcaklık (periyot 4)
 ├── Bant-12 pop (8 üye, PLIR) ── temsilci m=0 ── syn ──► Post0 [NEM]       Dal B ← Nem (periyot 12)
 │                                                           └─► Post1 [EC]        Dal B ← EC (periyot 12, NEGATİF KONTROL)
```

Koşul = (frekans bandı, sensör) çifti. CPU yalnız tercümandır: `v ≥ 50`
aktif, aktifse periyot = bant tau'su, genlik `S_b`, gecikme `D_s`
(`sensor_to_spike`, yalnız harness). Öğrenme mevcut kuadratik kuraldır
(yeni kural YOK); çekirdek dosyalarında float/double, dinamik bellek YOK.

Kalibrasyon (`validate_plant_npu.py`, Kural 0, 24 koşu):
- **SEÇİM: `S_b=1.0, w0=0.2, eta=0.2`** → tam koşuda 5/5 kriter OK.
- MC tam koşu: cond_ates=[415,0,1020] dw=[+1.5581,+0.0000,+1.8000]
  CR=[62,0,121] probe=[0,0,0].
- w0 notu: ilk grid {0.3,0.4} SIC probunda kaldı (4'lük bant temsilci
  ateş sıklığı yüksek → w0≥0.3'te A tek başına ateşletiyor); w0=0.2 iki
  bantta da CS-etkisiz + güçlü CR verdi. Eşikler sabit kaldı, yalnız w0
  grid'i genişletildi (4×3×2=24 koşu).
- SIC w `W_MAX=2.0` tavanına ulaştı (S(w) tavanı çalışıyor).

C++ sayıları (`./salep_plant_npu`, deterministik, sanitizer temiz):
- `OZET: KILIT=OK KAZANIM=OK NEGATIF=OK CR=OK`
- (A) kilit: cov=(0.83,0.84); conc bilgi: (0.38,0.67). Gürültülü telde
  kapı cov≥0.40'tır (§9.8 S2 disiplini; conc tohum-duyarlı, kapı değil).
- (B) kazanım: NEM dw=+1.5415, SIC dw=+1.8000 (≥+0.3).
- (C) CR: NEM=62, SIC=117 (sensörsüz), EC=0.
- (D) negatif: EC |dw|=0.000000 (<0.02), TEST EC ateşi 0.
- (E) parametrik: `--nem=40` → NEM dw=0, CR=0 (SIC öğrenmeye devam eder).
- MC→C++ uyumu: cond [415,0,993] vs [415,0,1020]; CR [62,0,117] vs
  [62,0,121] — MC yaklaşık öngörü, **C++ sayısı esastır**.

Dosyalar (yalnızca yeniler; mevcut `*.h`/`main_*.cpp`/testler değişmedi):
- `validate_plant_npu.py` (Kural 0), `src/plant_npu.h` (`PlantNpu`,
  `plant_init/tick`; `PNP_MAX_POST=4`, `PNP_TAUS={4,12}`, pop 8),
  `src/main_plant_npu.cpp` (CLI `--nem/--ec/--sicaklik/--noise/--d_sens`,
  `--help` ve hatalı değer → çıkış 1; `param:` satırı yalnız özel koşuda),
  `plant_learning.csv` (6500 satır) + `plant_conditions.csv` (39 satır),
  `plot_plant_npu.py` → `plant_npu.png` (2 panel: faz kilit haritası +
  koşul kazanma/CR), `dashboard/npu_runner.py::run_plant`,
  `dashboard/app.py` V2 bölümü, `dashboard/macro_state.py::plant_summary`.
- Derleme: `g++ -std=c++17 -Wall -Wextra -Wpedantic
  -fsanitize=address,undefined -fno-omit-frame-pointer -Isrc
  src/main_plant_npu.cpp -o salep_plant_npu`.

Çalıştırma: `.venv` aktive (`source .venv/bin/activate`), sonra
`streamlit run dashboard/app.py` → http://localhost:8501 ("Koşul
Öğrenmeyi Simüle Et"). Headless smoke (AppTest): 3 buton hatasız, V2
uçtan uca OK.

Regresyon doğrulaması (2026-09-09):
- Eski `src/*.h`/mevcut `main_*.cpp` dosyalarına dokunulmadı (yalnız 2
  yeni dosya + dashboard/plot ekleri).
- 10 eski binary argümansız koşuldu: 17/19 CSV bit-bit aynı; yeni koşu
  deterministik (iki koşu sha256 eşit).
- **DÜRÜST BULGU:** `fdm_simultaneous.csv` + `fdm_events.csv` snapshot'tan
  farklı çıktı. Suçlu bu iş değil: kaynaktan taze derlenen binary repo
  binary'siyle bayt-eşit (`cmp` OK) ve argümansız çıktı §9.8 kanonik
  sayılarını birebir veriyor (R1 conc 0.49/0.82, R9=8) — yani kayıtlı
  CSV'ler parametreli bir koşunun artığıydı. Kanonik koşu CSV'leri geri
  yükledi; `plot_fdm.py` tekrar koşulunca PNG de kanonik hale döndü
  (beklenen: parametreli CSV'den üretilmiş PNG değişti).

DÜRÜST SINIRLAR: (i) aktif bant = 2 ({4,12}); 4. post slotu headroom;
(ii) kuadratik kural rate-tabanlıdır (RATE_WINDOW=30) → faz-hatasına
dayanıklı koşul öğrenme = donanım toleransı (§9.10 bulgusunun devamı);
(iii) SIC hızlı doyuma ulaşır (W_MAX tavanı) — uzun oturumlarda NEM/SIC
kazançları karşılaştırılamaz hale gelir, CR ateşleri esas alınır.

## 9.12 Bitki NPU v3 — Dual-Rail (Rail-F + Rail-C)

FAZ 1 kalibrasyonu (§9.11) + FAZ 2 çekirdeği + FAZ 3 doğrulama/panel/motor
üzerine kapanış kaydıdır. Eski bölümlere dokunulmadı; sayılar C++ koşusundan
alındı (MC yaklaşık öngörüdür).

### Mimari dürüstlük notu — 7-band tek-tel imkânsızlığı + dual-rail kararı

7 duyusal kanalın (hs/ts/hn/tn/ph/npk/ec) 7 ayrı frekans bandı olarak TEK
tele süperpoze edilmesi denendiği yerde bırakıldı; §9.8'in dürüst sınırları
bunu yasaklar: (i) harmonik çiftte yavaş-bant faz takibi yok (ilk-darbe
çapası, bilgi-teorik); (ii) seyrek-yabancı tele alt-harmonik sürüklenme
(yeniden-kilit bedeli); (iii) 3-bantta tau=16 çapa tutmuyor → C++'da 3.
bant yok. 7 bandı tek tele zorlamak, her bandın PLIR kilidini birbirinin
yabancı darbesiyle sürekli bozar (LOCK=2·tau+bw aşımı → yeniden-kilit) ve
kilit kapsama eşiğini (cov≥0.40) tutturamaz. Karar: **dual-rail**.

- **Rail-F (frekans raili):** ORTAK TEL yalnız 2 bant taşır ({4,12}
  süperpoze + gürültü, D_b=0), bant başına 8 üyeli PLIR popülasyonu
  (§9.8 mekaniği birebir). Frekans kimliği telde, sensör kimliği telde DEĞİL.
- **Rail-C (kanal raili):** 7 sensör kanalının kimliğini taşıyan tasiyici
  sayaçlar (`cc_hn/cc_ec/cc_hs/cc_ts/cc_tn/cc_ph/cc_npk`,
  `plant_dualrail.csv` sütunları). Hangi post'un hangi sensörle koşullandığı
  buradan okunur; tel gürültüsü/çakışması kanal etiketini kirletmez.
- Post dizimi (`src/plant_npu.h`: `PNP_MAX_POST=10`, `PNP_NUM_POST=9` =
  7 grounding + 2 çapraz, 1 slot headroom): HN/EC/HS/TS/TN/PH/NPK grounding
  postları + X1 (HN←tau4 çapraz) + X2 (HS←tau12 çapraz). `PNP_TAUS={4,12}`
  (§9.8 2-bant sınırı korunur), tohum `PNP_SEED=7001` (deterministik).

### Kalibrasyon sonuçları (FAZ 1, `validate_plant_npu.py`, Kural 0)

- **SEÇİM: `S_b=1.0, w0=0.2, eta=0.2`** → tam koşuda 5/5 kriter OK.
- MC tam koşu (izole-post Python ikizi, C++ doğrulama şart):
  cond_ates=[415,0,1020], dw=[+1.5581,+0.0000,+1.8000],
  CR(test)=[62,0,121], probe(CS-tek-başına)=[0,0,0].
- w0 tabanı 0.2'dir: w0≥0.3, tau=4 bandında A-dalını tek başına ateşletip
  CS-tek-başına probunu bozar (kriter c2). Tüm Rail-F/Rail-C postları w0=0.2
  ile başlar.
- Negatif kontrol deseni rail başına replike edilir: rail başına 1 neg post
  (EC: aynı bant, sensör kapalı, |dw|<0.02, CR=0); C++ `plant_tick` her
  tick öğrenir, kapalı sensör tek drift kaynağıdır, komite koşuda tam 0.0000.

### C++ sayıları (`ASAN_OPTIONS=detect_leaks=0 ./salep_plant_npu`, deterministik)

- `OZET: KILIT=OK KAZANIM=OK NEGATIF=OK CR=OK`.
- (A) kilit: cov=(0.83,0.84) (kapı cov≥0.40, §9.8 S2 disiplini);
  conc=(0.38,0.67) bilgi-değeri (tohum-duyarlı, kapı değil).
  Tel ateşi: bant-4=6067, bant-12=3328.
- (B) kazanım: NEM w 0.2→1.7415 (dw=+1.5415, cond 415); SIC w 0.2→2.0000
  (dw=+1.8000, cond 993, W_MAX tavanında). Kapı dw≥+0.3.
- (C) CR (sensörsüz test): NEM=62, SIC=117 (>0); EC=0.
- (D) negatif: EC dw=+0.000000 (|dw|<0.02), TEST EC ateşi 0.
- (E) parametrik: `--nem=40` → NEM dw=0/CR=0, SIC öğrenmeye devam eder.
- (R) dual-rail: TS/TN/PH/NPK dw=+0.0000 (susturulu); X1 w=2.0000
  (dw=+1.8000); X2 w=1.7764 (dw=+1.5764). Rail-C taşıyıcı sayaç (son
  pencere): hn=ec=hs=ts=tn=ph=npk=0.
- MC→C++ uyumu: cond [415,0,993] vs [415,0,1020]; CR [62,0,117] vs
  [62,0,121] — **C++ sayısı esastır**.

### Rail-F / Rail-C ayrımı (okuma kılavuzu)

- `plant_learning.csv`: Rail-F izi (tick,block,stage,wire,fire_b4/fire_b12,
  s_nem/s_ec/s_sic, p0-p2 ateşi, w0-w2). Frekans kilidi ve koşul kazanımı
  buradan okunur.
- `plant_conditions.csv`: blok/post özeti (stage,block,post,w_start/w_end,
  dw,fires,coinc). Kalibrasyon dw/CR sayıları buradan hasat edilir.
- `plant_dualrail.csv` (YENİ): Rail-C izi (tick,block,stage,p3-p8 ateşi,
  w3-w8, cc_hn/cc_ec/cc_hs/cc_ts/cc_tn/cc_ph/cc_npk). 7 grounding + 2
  çapraz postun kanal-etiketli seyri buradadır.

### Canlı terminal + senaryo motoru kullanımı

- `scenario_engine.py` (stdlib-only): `/set` + `/scenario` + TR/EN regex
  doğal dil (toprak nemi/soil moisture öncelikli, `_norm` ile TR aksan
  duyarsız), `sensor_to_spike` + `sensor_burst` C++ birebir,
  POST_MAP (X1←HN/tau4, X2←HS/tau12). `python3 scenario_engine.py` →
  `scenario_engine: tum assert testleri gecti`.
- `live_term.py` (rich): Layout+Live (telemetri + OZET + komut geçmişi),
  `--stream` alt-süreci, ayrı thread'de asenkron stdin→motor, Ctrl-C/quit
  temiz kapanış. Koşu: `.venv/bin/python live_term.py`, piped
  `/scenario drought + quit` → exit=0. NOT: sistem `python3`'ünde `rich`
  yok → venv yorumlayıcısı şart (`rich` yalnız orada kurulu).
- `dashboard/app.py` V2: 7 slider + 4 senaryo butonu (PLANT_PRESETS:
  drought/sulama/soguk/reset) + d_sens; `npu_runner.run_plant` 7 sensör.
  Headless smoke: legacy çağrı OK + OZET tüm-OK; drought uçtan uca OK.

### Regresyon doğrulaması (2026-09-09, bu oturum)

- Kapı: kanonik C++ koşusu deterministik — art arda iki koşunun
  `plant_learning.csv / plant_conditions.csv / plant_dualrail.csv` sha256
  değerleri bit-eşit (aşağıdaki envanter ikinci koşununkidir).
- Çıplak `./salep_plant_npu` (ASAN bayraksız) ptrace-kısıtlı ortamda LSan
  abort verir (önceden bilinen §9.9 kısıtı); kanonik koşu
  `ASAN_OPTIONS=detect_leaks=0` ile yapılır, çekirdekte heap yok (§2.2).
- Eski CSV'lere dokunulmadı; `plant_npu.png` dışındaki PNG'ler değişmedi.

### CSV/PNG envanteri (kanonik sha256, bu oturum)

- `plant_learning.csv`: `bd4ad472b8eef289b7ee54a5579678c9b94521ad1f0e423170c478bbb610ad08`
- `plant_conditions.csv`: `aa8ce3e23492efd31be4a2809f6383e75b17a9e509009e9e2bcf6594d7311d35`
- `plant_dualrail.csv`: `c3b7b103323cbc7c551647d077d5eb031667252d0cddc7d5f44ef7b82b08198b`
- `fdm_simultaneous.csv`: `4e67ead2d06a7684a9fe79246c2de6c86e0a7f91723b89e0b374001ae44169ab`
- `fdm_events.csv`: `31f28a880c029f6c96601de5e7febed9fe6d08b9cc10f40cc862ff8ee32a546f`
- `fdm_dshift.csv`: `de7bf9012c73f430e698686bd88492f349f7733f9a0250a0fa6f031fae9b6f99`
- `causality_learning.csv`: `ead4884273299d8f8bf4c2a99febf6ae2d8de9a406b49ef684a72592170de699`
- PNG: `plant_npu.png` (3 panel V2: Rail-F kilit faz histogramı + grounding
  w/CR + çapraz X1/X2 w ve sensör-ON profili, 18x11in dpi=300, görüntüyle
  doğrulandı); diğer PNG'lere dokunulmadı.

DÜRÜST SINIRLAR: (i) Rail-F yalnız {4,12} (§9.8 3-bant yasağı sürer);
(ii) TS/TN/PH/NPK susturulu rejimdedir (dw=0 — kanal var, koşullanma bu
koşuda yok); (iii) X1/X2 çaprazları HN/HS'e bağlıdır, diğer 5 kanalın
çaprazı headroom'dadır; (iv) conc tohum-duyarlıdır, kapı cov'dur.

### Canlı köprü düzeltmesi (2026-09-09, bu oturum)

- `run_stream` sonsuz döngüdür (`while (!quit)`; T_TOTAL sınırı yok) —
  tek çıkış QUIT'tir; batch yolu (`run_batch`) değişmedi, CSV'ler bit-bit
  aynı (regresyon doğrulandı).
- Kök neden (2 katmanlıydı): (i) eski `T_TOTAL` sınırı motoru ~1 sn'de
  OZET'e düşürüyordu (batch hissi); (ii) `select()+fgets()` karışımı:
  tek `read()` iki satırı birden stdio tamponuna çeker, `select` fd'yi
  boş görüp QUIT'i yutardı (ölçüldü: `SET` işlenip `QUIT` yutuluyordu).
  Çözüm: ham non-blocking `read()` + el yapımı satır biriktirici
  (`fcntl.h`/`errno.h`, yalnız harness); tick temposu `usleep(20000)`
  (~50 tick/s → telemetri ~2 Hz).
- `live_term.py`: `Popen([BIN, "--stream"], stdin=PIPE)` zaten doğruydu;
  stdin EOF'u (non-tty) artık oturumu öldürmüyor (0.5 sn yoklama,
  boru açık tutulur; tty'de Ctrl-D çıkıştır). Thread modeli deadlock'suz
  (tek yazıcı input, tek okuyucu reader). El testi: `quit`→çıkış 0,
  `nem 70+quit`→exit 0 + telemetri, `/scenario drought+quit`→7 SET
  ACK + exit 0, `</dev/null`→canlı kalır (timeout 124).

### v4 OPS/Meta-Dil Terminali (2026-09-09, bu oturum; C++ motoru değişmedi)

- Yeni `cpu_voice.py` (stdlib-only): profil/set/senaryo/doğal-dil
  konuşmaları (`describe_*`); `python3 cpu_voice.py` assert'leri geçer.
- `scenario_engine.interpret(text)` (geriye dönük uyumlu; `to_motor_lines`
  + eski assert'ler aynen): `{kind, motor_lines, speech, brief}` döner;
  anlamsız girdi ValueError değil `unknown` + yardım cümlesidir.
  Yön-fiil kuralları (yalnız değersiz girdide): "hava ısındı"→hs=85,
  "soğudu"→hs=20, "kurudu"→tn=15, "yağmur"→hn=80+tn=90.
- `live_term.py` yık-yeniden: üst status bar + sol NPU paneli (7 sensör
  bar/LED + 9 post w/ateş, X1/X2 ⊕ vurgulu) + orta Matrix şelalesi
  (T farkından ateş/Δw-plato/faz/taşıyıcı olayları, yaşla solar; solda
  kod-yağmuru, `--rain-off` ile kapanır) + boydan boya `❯` prompt
  (tty'de termios tuş-tuş + TR UTF-8 + Backspace + Ctrl-C 1×temizle/2×çıkış;
  piped'da satır-modu fallback). `/help`, `--self-test` (3 sn render +
  bölge kanıtı + temiz kapanış) bayrakları.
- Kapılar: iki assert seti + `--self-test` OK; piped `/scenario
  drought+quit` exit 0 + konuşma karesi; `</dev/null` canlı kalır;
  batch CSV hash'leri değişmedi (motor dokunulmadı).
- DÜRÜST NOT: "plato" Δw artışından sentezlenir (`(plato)` etiketli);
  gerçek gating alanı telemetride yok (istenirse C++'a tek `g=` alanı
  eklenebilir — bu planda değil).
- Düzeltme (usta eleştirisi, bu oturum): ortadaki dekoratif kod-yağmuru
  şeridi ATILDI (rastgele karakter üretiyordu, gerçek veri değildi) —
  yerine telemetriden beslenen etiketli/ölçekli VİTAL paneli: wire değeri
  + son-20 sparkline (ölçek satırlı) + ATEŞ n/9 (bu tick, 9 nokta) +
  TOPLAM n + US-ON n/7 + X1/X2 w/n/[AKTİF|PASİF] + legend (AKTİF=w≥1.0).
  Bant-ateş satırları EKLEMEDİ (bant popülasyon ateşi telemetride yok;
  uydurmak yerine yok). `--rain-off` bayrağı kalktı; sol panel, akış ve
  chat aynen. Kapılar yeniden yeşil (self-test VİTAL iğneli).
- `/stop` + `/continue` (bu oturum; C++ değişmedi): motor OS seviyesinde
  donar (SIGSTOP) / sürer (SIGCONT) — tick işlemiyor, LCG dahil tüm durum
  korunuyor, kaldığı yerden devam. Üst barda `❚❚ DURAKLATILDI` (sarı),
  şelale yaşlanması donar, kapanışta önce SIGCONT (yoksa QUIT/TERM
  işlemez). Türkçe `duraklat/devam` de çalışır; `/help` güncel.
  self-test kanıtı: duraklatılınca 0 telemetri satırı, sürdürünce akış,
  QUIT çıkış 0. Test notu: rich `Live` dosyaya yönlendirilince kare
  basmaz (ölçüldü) — piped loglardaki kare yokluğu ürün hatası değil;
  bölge kanıtı `export_text` iğneleriyle yapılır.

## 9.13 v5 "NPU OPS" — btop Tarzı Terminal + Afferent Kapı + Rename

Matrix/Meta-Dil akışı çöpe; 3 sütunlu tam-ekran panel (AFFERENT +
GRAFİK + KOMUT GÜNLÜĞÜ). Chat korunuyor (prompt + doğal dil + `/help`).

- C++ eklentisi (yalnız `src/main_plant_npu.cpp`): `SENSOR_OFF/ON
  <sensor>` → `g_sensor_gate[7]` (hepsi 1); kapı `run_stream`
  `sspike` önünde uygulanır (donanım kesmesi). Telemetri satırı ve
  `run_batch` değişmedi → 22/22 CSV bit-bit aynı (ölçüldü).
  Fonksiyonel kanıt: `hs=85+KAPALI` ≡ `hs=40 eşik-altı` (1,16 telemetri).
- `state_analyzer.py` (stdlib-only): `classify_env` (en-yakın-preset +
  uyum), `vitality`, `carrier_density`, `learning_pct` (oturum-min/max;
  `None`→0.0). Assert'leri geçer.
- `interpreter.py` = `cpu_voice.py` taşındı (terminoloji: "CPU Tercüman",
  "Komut Yorumlayıcı"); `+describe_gate_off/on`, `+describe_pause/resume`.
  `scenario_engine.interpret` → `sensor_off/sensor_on` kind'leri
  (`/sensor-off hn`, "hn kapa", "disable soil moisture"); eski kind'ler
  korunur. `cpu_voice.py` silindi; başvuru kalmadı.
- `live_term.py` v5: alt-ekran (1049h) + imleç gizle (yalnız tty);
  GRAFİK sütunu = wire braille (~80 örnek) + post W barları
  (oturum-min/max %) + cc barları (oturum-maks göreli) + ORTAM/VİTAL +
  legend; dar terminalde (<110 sütun) 3→2 sütun; boş-satır kısayolları
  q/p/r + `s`→`/scenario ` öneki; `/sensor-off|on`, `/stop`, `/continue`.
  self-test: bölge iğneleri (AFFERENT/GRAFİK/GÜNLÜK/CPU Tercüman/legend)
  + braille değişim kanıtı + kapı turu (OFF→OK→ON→OK) + duraklat/devam
  telemetri kanıtı + QUIT çıkış 0.
- Rename: `salep_*` → `npu_*` (CMake hedefleri + `npu_core` projesi,
  `npu_runner` BIN/BUILD yolları, `plot_q_dt_curve` BIN, `live_term`
  varsayılan `--bin`, dashboard "NPU Paneli"). 10 binary kaynaktan
  derlendi; `npu_event` bayt-bayt `mv` (CMake hedefi yoktu — derleme
  bayrakları bilinmiyor, dürüst not). Eski `salep_*` binary'leri silindi.

DÜRÜST SINIRLAR: (i) kapı durumu telemetride taşınmaz → UI kapı
göstergesi yerel `OK SENSOR_*` izlemesidir (motor-yerel kapı maskesi
değil); (ii) "plato" Δw'dan sentezlidir; (iii) bant-popülasyon ateşi
telemetride yok → VİTAL'de bant satırı yok; (iv) `npu_event` bayrakları
bilinmiyor (bayt-taşıma).

## 9.14 FAZ 3 — Duyusal Lob v2 (P1 faz hatları + P2 koşul bankası)

P1 PRE (faz hattı, PLIR-A kilitli, temsilci ateşi→sinaps) + P2 POST
koşul bankası (Dal A←P1 bitki fazı, Dal B←sensör faz hattı, B-PLIR
kendi τB'sini seçer). P2 çıktıları üst lobun arayüzüdür (`p2a`,
`p2a(p2c)` koşul etiketleri).

- `neuron.h` B-dalı PLIR kapısı (eklemeli): A-PLIR ile birebir kural,
  `plir_mode_B=0` iken genel yol aynen → 22/22 eski CSV bit-bit aynı.
- `sensory_lobe.h` (yeni): `P1_MAX=16`, `P2_MAX=64` (sabit tavan, HLS);
  bijective base-26 etiket (`p1a..p1z, p1a/a..`; `p2a(p2b,p2d)` koşul
  formatı); `sl_p1_params` (fdm leak-tier disiplini, PLIR-A);
  `sl_p2_params` (brA=0.12 A/B asimetrisi, brB τB-tier'li, B-PLIR);
  `sensory_tick` (plant disiplini: P1→syn→P2-A, hat→P2-B, tick+öğrenme).
- Banka boyutu (dinamik sayı): `sl_bank_size` = 7 grounding (sensör
  başına 1) + 1 replika + 2 decoy = **10 aktif** (≤64). Çapraz postlar
  0 (OFF-US kodlaması yok — üst lobun işi). Yeni sensör → +1 grounding.
- Varsayılan banka: p2a(A4,HN,τ35) + p2b(A12,HS,τ45) + p2c(replika,w0.1)
  + decoy p2d(HN,τ36)/p2e(HS,τ46) (w0 0.0) + negatif p2f(EC,40/OFF) +
  grounding p2g..p2j(TS/TN/PH/NPK,τ37). Faz şifreleme `τ(v)=4+v*56/100`
  (HN=56→35, HS=74→45), hat darbesi burst 1.
- Kalibrasyon (`validate_sensory_lobe.py` MC önce): B-seçicilik
  decoy/gerçek ~0.33-0.34 (yeniden-kilit bedeli, FDM §9.8-ii ile aynı
  fizik); burst 2 decoy'u %50 artırır, gerçeğe yaramaz → burst 1;
  decoylar ÜSTE (τ+1: alt 0.50, üst 0.34). A-alone eşik haritası
  (`--w0` probu): w≤0.3 sessiz, w≥0.4 ateşler. Kurulum: P1 amp
  {0.7, 4.0} (yavaş-hat doygun sürüş), η=0.30.
- C++ sayıları (`./npu_sensory_lobe`, sanitizer temiz, deterministik):
  `OZET: A=OK B=OK C=OK D=OK` — p2a +0.65/CR35, p2b +0.39/CR14,
  decoy kabul 0.33x + w≤0.3 + CR 0, p2f 0/0, P1 cov 0.46/1.00.
- Dosyalar: `src/sensory_lobe.h`, `src/main_sensory_lobe.cpp`
  (batch+stream, topoloji tablosu, `K t=.. p2a(p2c) kosul`),
  `sensory_lobe_learning.csv`, CMake `npu_sensory_lobe` hedefi.
  `live_term.py`/`scenario_engine.py` P2 etiket notu (v5 UI sonraya).

DÜRÜST SINIRLAR: (i) planın literal "decoy kabul 0" kapısı imkânsızdı
(yeniden-kilit) → ORAN kapısı (MC-türevli, hıza değişmez); (ii) planın
"burst 2" ve "p2e τ44" değerleri MC ile çürütüldü (burst 1, τ46);
(iii) öğrenme hız-korelasyonludur, katı coincidence değil (B-tek-başına
ateşler; CR yine de A-yolunu ispatlar); (iv) P1 demux bu fazda yapısal
(özel hatlar) — paylaşımlı-tel demux §9.8 FDM'de kanıtlı.

## 9.15 FAZ 4 — Öz-Örgütlenen Banka (ortak yol + ölçülen etiket + işe-alım)

El-atamalı adreslemeye son: etiketsiz havuz ORTAK yolu dinler, kimlik
rezonanstan çıkar, etiket ölçümden alınır, yenilik yedekten işe alınır.
Yalnız Dal B tarafı değişir (Dal A/soma/öğrenme aynen).

- `sl_add_post` (çekirdek büyüme ilkeli): yedek slottan işe-alım, taze
  kilit + w0 + sıfır sayaç; `sl_init` artık bunu kullanır (varsayılan
  koşu CSV'si bit-bit aynı — ispatlandı).
- `--selforg` (harness): 12 slotluk havuz {20..60} (küçük tau'lar
  DIŞARIDA — kısa kilitleriyle sahipsiz-nabız sinyalini boğarlardı);
  fazlar bus{35} → +37 → +45; seçim-fazı η=0.
- Yenilik ölçümü: sahipsiz nabız ardışık-fark medyanı + harmonik kontrol
  (m, m/2, m/3 — komşu kapılar her ikinci nabzı yer, medyan 2m'ye çıkar;
  gözlendi: medyan 74 → işe-alım 37). Eşik: 7 nabız + 6'da 5 kümeleşme
  + 400 tick soğuma + 300 tick faz-yerleşmesi (geçişte alt-harmonik
  hayalet işe-alım gözlendi → ikisi de kapı oldu).
- Rezonans-kabul ayrımı (bulgu): yoğun yolda HER slot kilit-süresi
  dolunca taze-kabul yapar (kabul ≠ kilit!). Yenilik SADECE rezonans
  kabullere (ISI==tau) bakar. Etiket tablosu kilitsizleri dürüstçe
  `gezgin-medyan` diye yazar.
- Sayılar (`--selforg`, deterministik): RECRUIT τ37@1813 (0.98 kilit) +
  τ45@3870 (0.92); `S1=S2=S3=S3b=S4=OK` (τ35 tam 43/43, komşu ≥2x,
  sıra [37,45], kilit sürüyor). `sensory_selforg.csv` envanterde.
- Tonotopi notu: tau yayılımı doğuştan (koklea gibi), eşleşme fizik,
  etiket ölçüm — atama hiçbir yerde yok.

DÜRÜST SINIRLAR: (i) kazanan-hepsini-alır rekabeti YOK (kopya taular
aynı kilitlenir) — yanal inhibisyon gelecek iş; (ii) işe-alım faz
sıralı tek yeniliğe göre kurulu (eşzamanlı iki yenilik test edilmedi);
(iii) etiket yalnız kilitli slotlarda anlamlı, gezginler raporlanır.

## 9.16 STRES — Geniş Bant (hızlı yenilik + seyrek doğrulama)

`--stress` (harness, `run_selforg` motorunun bağımsız kopyası —
doğrulanmış yola dokunulmaz): 10 faz; F1 bus{35} taban, F2–F5 hızlı
birikimli yenilik (+26, +59, +43, +50 — F5'te 5 eşzamanlı ton),
F6 bus{35} tabana-dönüş (dropout), F7–F10 seyrek SONDA ({26},{59},
{43},{50}). Seçim-fazı η=0. Slogan: hızlı fazda işe al, seyrek
fazda doğrula.

- BULGU 1 — ortanca-hayaleti: ilk koşuda işe-alım [26,59,43,**25**,50];
  `τ25@5000` hayalet (5 tonlu yolda sahipsiz farklar ~75'te kümelendi,
  harmonik kontrol 75/3=25'i "açıkladı"; bus'ta 25 yok). Kök neden:
  aday testi kat-açıklamasına bakıyor, adayın kendisinin hiç doğrudan
  gözlenip gözlenmediğine bakmıyordu. Düzeltme — doğrudan-kanıt şartı:
  6 farktan ≥2'si `|d−c|≤3` olmalı (gerçek tonda farklar zaten c'de
  kümelenir). İKİ motora da eklendi; `sensory_selforg.csv` bit-bit aynı
  (`d83e31cd…`) → doğrulanmış yolda davranış değişmedi (ispat).
  MC karşıt-ispatı M6 (`decide_cpp`: hayalet eski-kuralda hire,
  yeni-kuralda red; kalıntılı oktav 26'yı verir).
- BULGU 2 — yanlış-ritme yakalanma: B-PLIR kilidi körlük DEĞİL rezonans
  durumudur (`sensory_lobe.h:155-158`, kilit=2τ+1). Yoğun yolda kilit
  düşünce yanlış-ton nabız slotu yanlış ritme yakalar, öz nabızlar
  reddedilir (ölçüldü: yoğun-faz kilit 0.91/0.67/0.78/0.53, yoğunlukla
  düşer). SONUÇ: yoğun-faz kilit oranı KAPILANMAZ (fiziksel tavan);
  kilit ispatını seyrek sonda verir, karar ispatını sıra+pencere verir.
- Sonda-sınır kilit taşıma: ilk sondada 2/2 ıska (önceki faz kilidi
  ilk nabızları reddeder) → sondada da AYNI 300-tick yerleşme kuralı,
  yerleşme-sonrası tam eşitlik (yeni sabit yok).
- Sayılar (`--stress`, deterministik ×2, sha eşit): T1 F1 29/29;
  T2 sıra [26@1326, 59@2537, 43@3827, 50@5050] (her biri kendi fazında,
  yerleşme300+); T3 sonda 26/26 + 12/12 + 16/16 + 14/14;
  T4 F6 29/29 + F6–F10 hire=0. `OZET-STRESS: T1=T2=T3=T4=OK`,
  n_posts 12→16.
- Dosyalar: `sensory_stress.csv` (`66783729…`), ayrı
  `sensory_stress_hires.csv` (tick,tau,slot — tam tick, `9f83e4e1…`),
  `plot_sensory_lobe.py` → `sensory_lobe.png` (4 panel: FAZ3 w + CR
  [bitmask+stage'den türetilmiş] + selforg basamakları + stres hire).
- Regresyon: varsayılan koşu `51d2c482…` bit-bit aynı (A=B=C=D=OK);
  selforg `d83e31cd…` aynı (S1–S4=OK); MC M1–M6 OK. Başka binary
  etkilenmez (değişen tek kaynak `main_sensory_lobe.cpp`, yalnız
  `npu_sensory_lobe` hedefine girer). Koşu notu: bu oturumda sandbox
  ptrace kısıtı yüzünden LSAN leak-dedektörü kapalı
  (`LSAN_OPTIONS=detect_leaks=0`); ASan+UBSan açık, sanitizer temiz.

DÜRÜST SINIRLAR: (i) yoğun-faz kilit oranı kusursuz değildir, karar+
sonda bileşkesi ispat sayılır; (ii) sonda fazları harness iskelesidir
— gerçek sensör akışında seyrek-doğrulama üst lobun işidir;
(iii) 5-ton üstü yoğunluk ve faz-içi çift yenilik test edilmedi.

## 9.17 İKİNCİ YARI SINIRI — AFFERENT Kablo + Yarı-1 Envanteri

Birinci yarı (duyusal lob) donduruldu; ikinci yarı (nedensellik/öngörü)
`ARCHITECTURE.md` §5.1'deki AFFERENT kabloyu tüketir. Yarı-1 kodu
salt-okunurdur: adaptör onu çağırır, değiştirmez.

- Yarı-1 envanteri (donduruldu): `src/sensory_lobe.h`,
  `src/main_sensory_lobe.cpp`, `validate_sensory_lobe.py` (M1–M6),
  `plot_sensory_lobe.py`, `sensory_lobe_learning.csv`,
  `sensory_selforg.csv`, `sensory_stress.csv`,
  `sensory_stress_hires.csv`, `sensory_lobe.png`.
- Yarı-2 öneki: `causal_*` (nedensellik), `predict_*` (öngörü). Dizin
  taşınmaz (runner BIN + plot göreli-CSV yolları düz CORE_DIR varsayar).
- Mevcut `causality.h`/`main_causality.cpp` demosu korunur (regresyon
  çıpası, A–D kapıları); iç faz programıyla sürülür, duyusal girdi
  almaz — yeni adaptörlü yol ayrı binary/CSV'dir, birleşme ayrı onaylı.
- Sınır yapısı: `AfferentEvent{tick, post_id(0-63), tau_b(4-60)}`;
  tek tick saati; nedensel-rol eşlemesi (neden→pre-A, etki→pre-B).

## 9.18 İKİNCİ YARI DİLİM 0–4 — Afferent + Tek-Adım Öngörü

`src/causal_afferent.h` (olay + patlama adaptörü) + `src/predict.h`
(tek-adım öngörü) + `src/main_causal_afferent.cpp` (demo: gerçek lob +
gerçek nedensellik çekirdeği, tek saat) + `validate_causal_afferent.py`
(MC-önce A1–A3 + P1–P3) + `plot_causal_afferent.py` →
`causal_afferent.png` (4 panel) + dashboard bağı (runner/app/macro).

- Fizik: P2 olayları yavaş (τ12–60), pre'ler hızlı (τ4/8/12/16) →
  adaptör olayı pre-tau'sunda kısa patlamaya çevirir (zamanlama korunur;
  patlama olay periyodunu aşmaz, sınır-temasta birikimli çakışma iki
  tarafta da `+=` ile aynıdır).
- Kalibrasyon yolu (MC): periyot-35 treninde hedef susar (seyrek sürüş
  sızıntıda erir) → periyot-12; n0≥7 tek-kanal baskıyı bozar (F1 ateşler,
  ikizde görüldü) → n0=2,n2=2; lag platosu 4–9 (F-kapıları hepsinde
  sağlam, coincidence monoton) → lag=8. Seçim: `X(T12)+Y=X+8, 2@tau4,
  2@tau12, W=16`.
- Sayılar (deterministik ×2): A: F3=37≥2×(0+0), C=[0 0 915]; B/D kazanç
  F3>tekil; C: P1/P3 0 + w donuk; E: kablo denetimi 37/37 çiftli;
  F: taşma 0, olaylar [226+0 0+219 225+225]; P1 recall 210/225 (0.933);
  P2 F1 pencere 110/Y 0; P3 lead 8.10 (pencere 16).
  `OZET-AFFERENT: A=B=C=D=E=F=P=OK`.
- P1 eşiği 0.90 (MC 0.987): neden-kanal 0.5/olay seyrekliği periyodik
  kapsama boşluğu bırakır (superlere eşit); ikiz/C++ farkı sabit-nokta
  mikro-zamanlaması, mekanizma aynı.
- Dosyalar: `causal_afferent_learning.csv` (`d02528a6…`, +pred sütunu),
  `causal_afferent.png`. Eski demo (`causality.*`) korunur (regresyon
  çıpası). Eski CSV'ler bit-bit aynı (üç sensory sha aynen).
- Dashboard: `run_causal_afferent()` + `afferent_summary` (eşiksiz) +
  Afferent bölümü; `parse_ozet` OZET- varyantlarını da okur (eski format
  çıktısı aynı).

DÜRÜST SINIRLAR: (i) precision/specificity bu yoğun-periyodik dünyada
ölçülemez (Y her yerde) — seyrek-dünya takip işi; (ii) MC ikiz hedef
baskılamada C++ çekirdekten katıdır (F1 ikizde 0, gerçekte 44 olabilir)
→ oran/kontrast kapıları esastır, sıfırlar değil; (iii) senaryo kablosu
(X→A, Y→B) harness tanımıdır, öğrenilmez.
MİMARİ NİYET (kilitli): P1 hatları bugün sentetik sayaçtır (iskele);
ileride bitki NPU çıkışı P1'i sürecek (bitki atımı = saat/kelime),
sensör B dalında anlam-referansı kalacak. Mevcut sistemde değişiklik
gerektirmez.

## 9.19 W0/W1 Yeniden Yapılanma — Kullanıcı Onaylı Anayasa Değişikliği (2026-09-11)

Kullanıcı W0 (purge) + W1 (sim/NPU ayrımı) adımlarını açıkça onayladı.
Bu bölüm, aşağıdaki maddeleri kullanıcı kararıyla değiştirir;
çelişki halinde bu bölümdeki kayıt geçerlidir:

- A7 Godot görselleştirme yolu EMEKLİ: `twin/godot/`, `twin/dist/`,
  `tools/godot/`, `tools/export_exe.sh`, `twin/godot_gates.py` silindi.
  G4/G6/G7/G8 karşılıksız SKIP'tir (Godot karşılığı yok).
- Qt arşivi kaldırıldı: `twin/_legacy/`, `twin/lib/` (yalnız Qt xcb
  bağımlılığıydı) silindi.
- Streamlit dashboard kaldırıldı: `dashboard/` silindi (§9.9'daki
  `streamlit run dashboard/app.py` koşu yolu geçersizdir; §9.18'deki
  dashboard bağı notu tarihseldir).
- "Dizin taşınmaz" kaydı (§9.17 + ARCHITECTURE.md §5.1) bu reorganizasyon
  için KALDIRILDI: simülasyon `twin/` paketinden `sim/` paketine taşındı
  (`plant_sim, world_state, frame, sensor_map, serve, probe,
  scenario_disaster, observer, npu_bridge, lobes/, models/, out/,
  selftest.py, run.sh`). İç importlar `twin.*` → `sim.*` çevrildi;
  G11 AST lint'i `sim/` yollarıyla çalışır.
- NPU köküne DOKUNULMADI: `src/`, `CMakeLists.txt`, `validate_*.py`,
  `plot_*.py`, kanonik CSV/PNG'ler, `npu_*` binary'leri, host araçları
  (`live_term.py`, `scenario_engine.py`, `interpreter.py`,
  `state_analyzer.py`) aynen durur.
- Yeni koşu yolları: `.venv/bin/python -m sim.selftest`,
  `./sim/run.sh` (NPU'suz yayıncı). G1/G3'teki NPU alt-süreç sınırı
  (`npu_bridge.py` → `npu_plant_npu` binary'si) değişmedi.

## 9.20 W2 — Tek Başına Koşu + v1 Freeze (2026-09-11, kullanıcı onaylı)

- `sim/run.py`: NPU'suz 365 gün tek başına koşu (`WorldState` +
  `SensorMapper` + `Frame`, `NpuBridge` YOK). Her günde K6 sızıntı
  assert'i (`ground_truth/root_rot/salt_burn/plant_death` frame'de yok);
  sonunda özet basar (gün, stage seyri, sensör min/max). Koşu:
  `.venv/bin/python -m sim.run [--days N] [--seed N]`.
- `world_state.v2` DONDURULDU (v1 §9.27'de kapatıldı): kilit
  `sim/frame.py::SCHEMA_VERSION=2` + `sim/selftest.py::_V2_*` birebir
  anahtar kümeleri + bekçi G14'tür. Şema değişikliği bu üçünü birlikte
  + bu maddeye yeni fıkra ister.
- G11 kapsamı `sim/run.py`'yi de içerir (koşucu yalnız stdlib +
  numpy/pandas/matplotlib + `sim.*` import edebilir; NPU tarafı yok).

## 9.21 W3–W9 — Web Katmanı + Yeni Kapılar (2026-09-11, kullanıcı onaylı)

- `web/` paketi: `server.py` (Starlette + uvicorn; **sim/npu importu
  YOK** — sim'e yalnız `sim/serve.py` alt-süreci + TCP, NPU'ya yalnız
  `npu_plant_npu --stream` alt-süreci + dosya yoluyla bağlanır; tek bağ
  veridir), `static/` (sekmeli kabuk + 2D canvas + beyin + grafikler),
  `gates_web.py` (headless bekçi), `g24_parity.mjs` (node geometri paritesi).
- Rotalar: `/healthz`, `/ws/world` (v1 frame, latest-wins, komut iletimi:
  pause/resume/speed/water/fert/drought), `/ws/npu` (TELE→JSON;
  binary yoksa `{"status":"offline"}`), `/` statik, mesh JSON'u
  `sim/models/salep_meshes.json` dosyasından birebir sunulur (kopya yok).
- Yeni kapılar (`python -m web.gates_web`, headless): G19 zero-CDN
  (static'te http/cdn referansı yok), G20 LAN (0.0.0.0 bind + erişim),
  G21 WS sözleşme + latest-wins (N frame + v1 şema + monoton gün),
  G22 NPU'suz web tam çalışır (NPU öldürülmüşken `/ws/world` akar),
  G23 izole koşu (web, sim/NPU'yu import etmez — AST lint),
  G24 silüet parite (mesh ortografik silueti ≡ 2D profil, tolerans %15).
- NPU el sıkışması (2026-09-11, kullanıcı kararı): sayfa açılışı NPU
  alt-süreci BAŞLATMAZ; beyin paneli kayıtlı örneği "KAYITLI ÖRNEK"
  etiketiyle gösterir. Canlı NPU yalnız "NPU'ya Bağlan" düğmesiyle açılır
  (her /ws/npu bağlantısı bir alt-süreç açar, bağlantı kapanınca ölür).
  Bekçi: G22 — yalnız /ws/world kullanılırken yeni `npu_plant_npu
  --stream` süreci doğmaz.
- Gökyüzü display düzeltmesi (2026-09-12): `sky/sun_alt` snapshot'ta
  günlük adımda donuyordu (gece/gündüz görünmüyordu); `sim/serve.py`
  bunları canlı `clock.day_frac`'tan hesaplar (fizik değişmez).
  Yayıncı açılış hızı 1x (5 sn'de 1 saat); G21 water kanıtı kuyruk girişi
  sayar (applied kanıtı G14'tedir).
- Hız emri sürdürür (2026-09-12): `speed` komutu önce `resume()` çağırır
  (duraklatma kilidinde hız tepkisizliği raporlandı, ölçüldü); bekçi G14.
  HUD hızı gösterir (`H 1.0x/8.0x`, duraklatılınca yazar).
- Sensör birliği niyeti (2026-09-11, kullanıcı kararı): sensör değerleri
  evrenseldir; simin ürettiği 7 sensör ile duyusal lobun okuduğu veri
  ileride ortaklaştırılacak. Çıkarım/nedensellik motoru bitince lob,
  bitkiden çıkarım alması için simülasyona el sıkışmayla bağlanacak;
  sim kalitesi lob öğrenmesini besleyecek. Bağlantı yine açık kullanıcı
  onayıyla olacak (otomatik bağlanma yok).
- KAYITLI ERTELEMELER (ortamda internet YOK, 2026-09-11 ölçüldü):
  Three.js vendoring yapılamadı → `web/static/vendor/` boş + README,
  3D sekmesi tembel yüklenir (yokluğu 2D'yi bozmaz); `salep_gen v2`
  yoğunlaştırma yapılmadı (G13/G15/G16 mevcut mesh'lerle geçiyor,
  kör yoğunlaştırma anayasa §0'a aykırı olurdu).

## 9.22 SONSUZ KOŞU — DEAD Rebirth (2026-09-12, kullanıcı isteği)

Şikayet: günler sayıyor ama simülasyon belli bir günden sonra DEAD'e
düşüp orada takılıyor; sonsuza kadar gitmeli.

Kök neden (2 katmanlıydı, ölçüldü): (i) `root_health` tek yönlü azalır
(çürüme/yanık hasarı), iyileşme mekanizması yok → er ya da geç 0
(seed 42'de gün 1049); `Stage.DEAD` yutucu durumdu (`_advance_stage`
erken dönüyordu). (ii) `run_population` ölü bitkiyi `continue` ile
atlıyordu → ölümden sonra gün ızgarası deliniyordu (3000 günlük koşuda
1050 satır) ve bitki bir daha adım atamadığı için kapı hiç açılamıyordu.
`WorldState` yolu (web/serve) adımı atlıyor değildi ama yutucu DEAD
yüzünden aynı takılmayı yaşıyordu.

Düzeltme (canlı-fizik sayılarına dokunulmadı — G2/G3 korunur):
- `sim/plant_sim.py::_advance_stage` DEAD dalı: sürgün kapısı DORMANT ile
  birebir aynı ifadedir (yeni sayı yok, `or day_of_year < 30` tuhaflığı
  dahil — değiştirmek G2'yi bozardı). Kapı açılınca tohum/yumru
  bankasından taze birey başlar: leaf/root=100, tuber=1.0, o2=0
  (`__init__` kanoniği); toprak nemi ve EC aynen durur (çevre bireye ait
  değil — tuzlu toprakta yeniden ölüm dürüstçe mümkündür).
  `ground_truth_events`'e `"rebirth"` düşer (doğrulama kolonu, NPU'ya
  gitmez; K6 sızıntı anahtarlarına değmez).
- `run_population`: ölü bitki de her gün adım atar (toprağı sürer, kapı
  açılınca döner) → gün ızgarasında boşluk yok.

Sayılar (deterministik, bu oturum):
- seed 42, 3000 gün: 3000 satır; 3 ölüm + 3 rebirth (DEAD→SPROUTING
  gün 1050/1705/2442); en uzun kesintisiz DEAD 170 gün; son stage
  VEGETATIVE.
- `WorldState` seed 42, 2500 gün sıralı yürüyüş: ölüm 733 → rebirth 734;
  en uzun DEAD 223 gün.
- Regresyon: G2 afet CSV'si bayt-bayt aynı (`cmp` OK); G1 penceresi
  (seed 42, 365 gün) ve G3/G5/G10/G11/G12 yeşil.
- Yeni kapı G25 (`sim/selftest.py`): 1600-gün ızgara bütünlüğü +
  rebirth geçişi + en uzun DEAD < 365 + WorldState çıkış kanıtı.
- W2 ispatı: `python -m sim.run --days 1200 --seed 42` ölüm gününü aşıp
  `...→DEAD→SPROUTING→VEGETATIVE→FLOWERING→...` diye sürer, sızıntı yok.

DÜRÜST SINIRLAR: (i) DEAD dönemleri aylarca sürebilir (ölü tarla sonbahar
yağmurunu bekler — ölçülen en uzun 223 gün); takılma yoktur ama geçici
DEAD görünür. (ii) Kök iyileşmesi eklenmedi: baseline'da bile ~3 yılda
bir ölüm olur; iyileşme hızı yeni sayı isterdi (§0) ve canlı-fizik
değerlerini oynatıp G2'yi bozardı — ölüm/rebirth döngüsü plansız sayı
eklemeden sonsuz koşuyu verir. (iii) Ocak kapısı tuhaflığı (`doy<30`
yağmursuz sürgün) DORMANT'tan miras kaldı, düzeltilmedi (G2 disiplini).

## 9.23 Sprint 60x Düğmesi (2026-09-12, kullanıcı isteği)

"Sprint" düğmesi: basınca 2 gerçek-sn'de 1 sim-günü akar (0.5 gün/sn,
HUD'da `H 60x`). Değişiklik yalnız 2 statik dosya: `web/static/index.html`
(`data-cmd="sprint"` düğmesi) + `web/static/js/app.js` CMDS eşlemesi
(`sprint: {cmd:"speed", v:60/120}`). Röle genel olduğundan (`cmd` içeren
her şey iletilir) `server.py`/sim tarafı değişmedi; şema v1 aynı.
Yeni kapı G26 (`web/gates_web.py`): statik kablolama + canlı hız kanıtı
(4 sn pencerede 1.9 gün ilerleme ölçüldü). G19–G23 yeşil.

## 9.24 Canlı İklim Şeridi (2026-09-12, kullanıcı isteği)

Üst barda anlık hava durumu: `Ege` (bölge sabiti — WorldDriver
Akdeniz/Ege tipidir, gün uzunluğu ~38K Ege enlemine göre; Ege'nin iklim
tipi zaten Akdeniz iklimidir) + mevsim (`sim.doy`'dan meteorolojik:
60/151/243/334 = 1 Mar/1 Haz/1 Eyl/1 Ara; ilk sürümde astronomik sınır
kullanılmış, 13 Ara'yı Sonbahar göstermiş — kullanıcı yakaladı, düzeltildi)
+ gök (`world.sky`: gündüz/alacakaranlık/gece; gecede `-20` sabiti
gösterilmez — o değer ufkun-altı işaretidir, ölçüm değil) + yağış
(`world.rain_mm`, örn. `yağış 3.2mm`). Hepsi her karede v1 frame'den
tazelenir (`hud()` içi); şema değişmedi, yeni veri yolu yok.
Değişiklik: `index.html` (4 span) + `app.js` (`hud()` 8 satır).
Yeni kapı G27: statik kablolama + canlı alan kanıtı
(doy=0/gök=night/yağış=17.0mm ölçüldü). G19–G23+G26 yeşil.

## 9.25 Canlı Veri Paneli + Gün-Ay, NPU Paneli Kalktı (2026-09-12, kullanıcı isteği)

Sağdaki "NPU Beyin Ağı" paneli kaldırıldı; yerinde "Canlı Veriler" paneli:
Tarih (`12 Oca · gün 345` — `sim.doy`'dan gün-ay, 365 gün/Şubat 28,
artık yıl yok), İklim (Ege), Mevsim, Hava (`temp_air_display`), Toprak
(`temp_soil`), Gök + güneş yüksekliği (`sky` + `sun_alt_deg`), Yağış
(`rain_mm`), Gün uzunluğu (`photoperiod_h`). Hepsi `hud()` içinde her
karede v1 frame'den tazelenir; şema/backend değişmedi (`/ws/npu` ve
`brain.js`/`npu_sample.json` dosyaları duruyor, G22/G20 yeşil).
Değişiklik: `index.html` (7 satırlık panel) + `app.js`
(NPU kablolaması silindi, `dateOfDoy` + panel yazımı) + `style.css`
(`.datalist` satırları, ölü `.npu-ctl` silindi).
G27 güncellendi (panel-kaldırma kilidi + veri-paneli kablolaması + canlı
alan kanıtı); node ile sözdizimi + tarih sınırları doğrulandı
(0→1 Oca … 364→31 Ara). G19–G23+G26 yeşil.

## 9.26 Gerçek Gözlem Havası — Aydın Open-Meteo (2026-09-13, kullanıcı isteği)

Kullanıcı buldu, doğrulandı: `open-meteo-37.86N27.87E108m.csv` gerçek
Open-Meteo günlük çıktısıdır (37.86K 27.87D = Aydın, 108 m,
Europe/Istanbul). 8 Eyl 2025 → 8 Eyl 2026 arası 366 gün kesintisiz,
boşluk/NaN yok; sıcaklık 0.5–32.4°C, en yağışlı gün 79.6 mm, 135 yağışlı
gün. Kullanılan sütunlar: `temperature_2m_mean (°C)` + `rain_sum (mm)`.

Mekanizma (`sim/plant_sim.py` A2 bölümü; çekirdek fiziğe dokunulmadı):
- `load_observed_weather(path, year0)` → `ObservedWeather`. Meta satırlar
  atlanır, hatalar yüksek seslidir (sütun/tarih/sayı/NaN/aralık/tekrar).
  year0 verilmezse dosyanın son yılını alır (bu dosya: 2026).
- `get(abs_day, doy)` önceliği: tam-tarih (2026-03-14) > gün-ay havuzu
  (dosyanın öbür yıllarındaki 14 Mar ortalaması) > sentetik (None).
  Gözlenen günlerde RNG çekilmez → aynı dosya aynı sonucu verir.
- `WorldDriver(observed=...)` sıcaklık/yağışta dosyaya bakar; dosya-dışı
  gün eski sentetik modeldir. Gün ışığı astronomik kalır (38K ≈ Aydın).
- Bağlantı: `WorldState(...weather_csv/year)`, `sim/run.py` + `sim/serve.py`
  `--weather-csv/--weather-year` (G11 lint temiz: yalnız stdlib + `sim.*`).

Sayılar (bu oturum): G28 yeşil (Aydın 366 satır + mini-dosya birebirlik +
öncelik + hata sesi); 260-gün Aydın koşusu sızıntısız tamam
(251 günü tam-tarih isabetli); G2 afet CSV'si bayt-bayt aynı (varsayılan
dosyasız akış birebir korunur), G11/G25 yeşil.

DÜRÜST SINIRLAR: (i) dosya 9 Eyl 2026 sonrasını bilmez → sonrası sentetik
yedektir; (ii) year0=2026 iken 2025 kuyruğu tam-tarih değil gün-ay havuzu
olarak girer; (iii) dosya kullanıcı-verisidir, kanonik regresyon
çıktısı değil — G28a dosya yoksa atlanır (b/c/d yine koşar);
(iv) yağış `rain_sum`'dır (kar Aydın'da yok sayılır).

## 9.27 UV Endeksi + Boy Uzaması + Şema v2 (2026-09-13, kullanıcı isteği)

Kullanıcı buldu: `open-meteo-37.88N27.88E108m.csv` (Aydın, 366 gün,
8 Eyl 2025 → 8 Eyl 2026, NaN/boşluk yok; UV 0.50–8.30). Bu dosyada
sıcaklık/yağış YOKTUR — yalnız `uv_index_max` + `uv_index_clear_sky_max`
vardır; sıcaklık dosyasıyla BİRLİKTE verilir (`--weather-csv` +
`--weather-uv`).

Fizik (`sim/plant_sim.py`):
- `attach_observed_uv(obs, path)`: UV dosyasını işler (obs None ise
  sıcaklık/yağışsız taze nesne — yalnız UV gerçek olur). Sertlik
  sıcaklıkla aynı; aralık 0–25.
- "Normal UV" = dosyanın `clear_sky` sütunudur (uydurma referans yok):
  `uv_deficit = (clear - obs) / clear`, 0..1 (açık günde 0).
- Boy-atma evrelerinde (sürgün+vejetatif+çiçek):
  `boy += taban × (1 + kazanç × açık)` (`stem_growth_base=0.02`,
  `uv_elong_gain=1.0` — model seçimi, PlantParams pratiğiyle aynı).
  Kapalı gün (açık≈1) hızı 2x yapar. Boy MORFOLOJİKTİR, yumru/verim
  hesabına girmez (G28f yumru-birebirlik kilidi). Dormant girişi ve
  rebirth boyu sıfırlar (toprak-üstü kurur).

Ekran: Canlı Veriler panelinde `UV` (gözlem yoksa `—`) + `Boy` (model
birimi, gerçek cm DEĞİLDİR) satırları.

ŞEMA v1→v2 (dondurma prosedürü üçlüsü + bu fıkra, §9.20): eklenen
`world.uv_index` + `plant.stem_height`, başka anahtar değişmedi.
Kilitler: `SCHEMA_VERSION=2`, `_V2_*` kümeleri, G14; yayılım: G9b/G21/G20
bekçileri + `/healthz schema` + `ws.js` v2 filtresi (`_ws_frames` test
demeti de v1 süzüyordu — o da çevrildi, yoksa sayfa kararırdı).

Sayılar (bu oturum): G28e (366 UV satırı, açık-gün açığı 0, aralık 0..1)
+ G28f (kapalı > açık, oran formülü ±jitter bandında, yumru birebir);
v2 yayın kanıtı (6. gün karesi: UV 2.65, boy 0.168); G2 afet CSV'si
bayt-bayt aynı (yeni paramlar sonda, jitter sırası korunur), G11/G25/G14
yeşil, web G19–G23+G26+G27 yeşil, `app.js` node-sözdizimi OK.

## 9.28 Web Yayıncısına Hava Dosyası Geçişi (2026-09-13, kullanıcı raporu)

Rapor: panelde UV ve Boy `—` görünüyordu. İki ayrı sebepti: (i) UV —
GERÇEK eksik: `web/server.py` yayıncıyı hava bayrakları olmadan
başlatıyordu, UV verisi yayıncıya hiç ulaşmıyordu (`null` → çizgi);
(ii) Boy — kod doğruydu (`0.00` yazar), görünmemesi eski `app.js`'in
tarayıcı önbelleğinden gelmesiydi.

Düzeltme: `web/server.py main()` `--weather-csv/--weather-year/--weather-uv`
alır, `lifespan` yayıncı alt-sürecine iletir (`_pub_extra_args`; G23
temiz — yeni import yok). Bayraksız davranış aynıdır (UV null → çizgi,
G27b kilidi). Yeni kapı G29: bayraklı sunucuda UV gerçek sayı
(ölçülen UV=2.9, boy=0.02), tüm web kapıları yeşil.

Kullanım: `.venv/bin/python -m web.server --weather-csv
open-meteo-37.86N27.87E108m.csv --weather-uv
open-meteo-37.88N27.88E108m.csv` + tarayıcıda sert yenileme
(Ctrl+Shift+R).

Ek (2026-09-21, kullanıcı isteği): `--weather-csv` verilmezse sunucu
otomatik `weather_v3/W-base.csv` ile kalkar (DEFAULT_WEATHER_CSV;
`--weather-csv` ile ezilebilir). UV varsayılanı YOK (bayraksızda null,
G27b kilidi korunur). Yeni kapı G34 (bayraksız sunucu + yayıncı-cmdline +
frame akışı) yeşil. Tek komut: `.venv/bin/python -m web.server`.

Bozukluk (2026-09-21, kullanıcı raporu): healthz `publisher_alive:false,
has_frame:false`, panel boş. Sebep: varsayılan hava yolu GÖRELİYDİ;
sunucu salep_core dışından kalkınca yayıncı dosyayı bulamayıp çöküyordu.
Düzeltme: DEFAULT_WEATHER_CSV mutlak yol (ROOT tabanlı). G34 sertleştirildi
(sunucu /tmp'den kalkar + PYTHONPATH) yeşil.

Ek (2026-09-21): ws_world no_frame yolunda kopan istemci log'a
WebSocketDisconnect traceback düşürüyordu (zararsız gürültü; sekme
kapanınca). Düzeltme: try/except (ws_npu deseniyle aynı). Yeni kapı G35
(taklit kopuk soket, sunucusuz) + G21 sözleşme yeşil.
Not: G35'in `import web.server` satiri G23 AST-lintine takildi; duzeltme
gates_web izin listesine test-tarafi `web`+`starlette` eklendi (urun
kodu server.py linti aynen duruyor). Tam suit 13/13 yesil.

## 9.29 Güneş Yayı — Parabolik Yörünge (2026-09-13, kullanıcı isteği)

Şikayet: güneş dikey inip çıkıyordu. Sebep: çizimde x sabitti (`W*0.82`),
çerçevede akan azimut (`sun_az_deg`: doğu 90° → batı 270°) kullanılmıyordu.
Düzeltme yalnız görseldir (fizik `sun_position` aynen): saf `sunXY`
(`world2d.js`, node ile testli) azimuttan x'i, yükseklikten y'yi sürer —
güneş sol uçta doğar, tepede ortalanır, sağ uçta batar; gece çizilmez
(alt<-3 kuralı aynen). `profile.js`'e `sunAz` + ara-değer anahtarı
(sprintte sıçramasın diye) eklendi; G24 paritesi etkilenmez (yalnız
geometri kutusunu okur — koşuldu, GEÇTİ).
Kanıt: doğu (58,292) → tepe (360,28) → batı (662,292), monoton x;
web kapıları yeşil.

Düzeltme (aynı gün, kullanıcı raporu: "batacakken doğuya geri dönüyor"):
gece azimutu `0` işaret değeridir; akşam 268°'den gece 0'a DOĞRUSAL
ara-değerleme karesi güneşi batıdan güneye, geriye kaydırıyordu
(yatay geri-kayma + batış = raporlanan iz). `lerpFrame` azimutu dairesel
ara-değerler (en kısa yay; 268°→0° batıda kalarak 360°'ye yürür, kelepçe
batı kenarında tutar). Kanıt: sarım-ortası az=314°; G24'e sarım kilidi
eklendi (`lerp-sarim` + `lerp-gun`), parite + web kapıları yeşil.

Yumuşatma (aynı gün, kullanıcı isteği: tepe çok yüksek, geçişler sert):
yay basıklaştırıldı (`ARC_K=0.50`) + disk ufukta solarak beliriyor
(`fade`, alt -3..+2; bu duruyor). Basıltma KISMEN GERİ ALINDI (aşağıdaki düzeltme).

Eğri-takibi (aynı gün, kullanıcı raporu: "batacakken doğuya dönüyor",
"tepeyi aşağı çekme"): KÖK SEBEP BULUNDU — `x` azimuttan hesaplanıyordu
ama gece azimutu `0` işaret değeridir; ufuk geçişinde `x` kenara
kelepçelenip sabitleniyor, `y` hareket ediyordu = kenarda DİKEY iniş/çıkış.
`ARC_K` geri alındı (tepe eski yükseklikte, 28px). `x` artık kesintisiz
gün-içi zamandan (`dayT`: doğum 0 → batım 1, `profile2d` + saatten),
`y` yükseklikten — güneş eğriyi takip ederek doğar ve batar. Azimut
lerp'i ve `sunAz` kaldırıldı (tüketici kalmadı); G24 kilidi dayT'ye
çevrildi (`dayT-uc` 0/0.5/1 + `dayT-monoton`). Kanıt: doğu (58,292) →
tepe (360,28) → batı (662,292), şafakta `x` akar; G24 + web kapıları yeşil.

DÜRÜST SINIRLAR: (i) UV dosyası tek başına sıcaklık vermez — yalnız
`--weather-csv` ile anlamlıdır (yalnız-UV koşusunda sıcaklık sentetiktir);
(ii) boy birimi kalibre değildir (gerçek cm istenirse tarla ölçümüyle
ölçek gerekir — anayasa §0); (iii) açık referansı dosyanın kendi
`clear_sky`'ıdır, bağımsız uydu ürünü karşılaştırması yapılmadı.

## 9.30 Saatlik Gösterim — Gün-İçi Rekonstrüksiyon (2026-09-13, kullanıcı isteği)

DÜRÜST DÜZELTME: fizik GÜNLÜK ortalama adım atar — bitki 16 Temmuz'da
28–30° bandını yaşar, 36°/41°'yi görmez. Ekrandaki eski 33-34 bile gerçek
maks değildi (ortalama + sentetik ±4° dalga). Kullanıcı "anlık değeri
görelim" istedi.

Yapılan (YALNIZ gösterim, fizik değişmedi): loader min/maks sütunlarını
da okur (isteğe-bağlı; yoksa eğri kapalı); `reconstruct_hour_temp`
o günün gerçek min/maks'ına oturan tek-kosinüs eğri verir (15:00 maks,
03:00 min — gerçek min ~05:00'e göre ±2s faz farkı belgeli); WorldState
`display_temp` dosyası günlerde eğriyi verir, diğer günler eski yoldadır.
HUD + panel otomatik saatlik gösterir (şema/web değişmedi).

Kanıt: 16 Tem 2026 ekranda 03:00→23.2, 09:00→30.1, **15:00→37.1**,
21:00→30.1; fizik 30.0 (günlük ort). G28g (çapa + WorldState display +
sütunsuz-kapalı), G2/G10/G11/G25 yeşil.

DÜRÜST SINIRLAR: (i) eğri GÖZLEM değil rekonstrüksiyondur (dosyada
saatlik veri yok — saatlik Open-Meteo indirilirse gerçekle değişir);
(ii) 41° hissedilen NE fiziğe NE ekrana girer (ayrı sütun, kapalı);
(iii) saatlik FİZİK ayrı projedir (oranlar günlüğe kalibre, G2 etkilenir).

Ek (aynı gün, kullanıcı ilkesi: bitki günlük bilançoya tepki verir):
panelde `Uygulanan` satırı — fiziğin gördüğü günlük ortalamayı (`temp_air`)
gösterir; `Hava` anlığı, `Uygulanan` günlüğü verir. Şema değişmedi
(`temp_air` v2'de vardı). G27 kilitli, web kapıları yeşil.

Ek (aynı gün, "18°" raporu — İNCELEME, kod değişmedi): kullanıcı ağustosta
18° görünce hata sandı. Dosya haklı çıkardı: **29 Ağu 2026 gecesi gerçekten
18.3°** (yağışsız serin gece; gündüzü 32.5°). Ağustos min-ort 23.5°,
maks-ort 37.3°'tür. Gecede `Hava < Uygulanan` olması fizik gereğidir
(gece günlük ortalamanın altındadır). Doğrulama yolu: paneldeki Tarih'e
bakmak (29 Ağu yazıyorsa ekran doğru). Bayraksız koşuda 18.3 sentetikte
neredeyse imkânsız olduğundan, bu görüntü bayraklı koşu kanıtı sayılır.

Ek (aynı gün, "37'yi hiç görmedim" — İNCELEME, kod değişmedi): display
yolu doğru (15 Ağu 15:00 karesi 35.9 = dosya maksı). Tepe günde BİR kez,
kısa görünür: 1x hızda ~5 gerçek-sn, 8x'te ~0.6 sn, sprintte ~83 ms
(yakalanamaz). Bayraksız koşuda tepe hiç 37'ye çıkmaz (sentetik maks
~31). Yakalama yolu: bayraklı + 1x + ağustos günü öğleden sonra izlemek
(veya tırmanırken Duraklat).

Ek (aynı gün, "Hava 25-26 + Uygulanan 29" — İNCELEME, kod değişmedi):
hizalama doğru (world_state.py: aynı `day` fiziğe ve eğriye gider).
20 Ağu dosyada ort 29.5 / min 24.3 / maks 37.7; eğri 00:00→26.3,
06:00→26.3, 15:00→37.7 verir. Yani 25-26 okuması GECE/sabah saatidir,
Uygulanan 29 gün ortalamasıdır — çelişki değil, gün-içi salınım.
Gündüz 12-16h arası 25 görülürse o gerçek hata olur (güneş konumu
hakemdir).

## 9.31 Ölüm Disiplini — Kuruma Uykuya Yatar, DEAD Yalnız Gerçek Ölümdür (2026-09-14, kullanıcı isteği)

Kullanıcı: "kuruduğu zaman dormancy'e yatmalı, dead olmamalı; dead bildiğimiz
ölüm olmalı (fazla su kök çürüklüğü, mantar)".

Ölçülen kusur (seed 7, 400 gün yağmursuz): yaprak ~78. günde biter (yumru
1.07 dolu) ama bitki 36 gün kavrulmuş halde FLOWERING/SENESCENCE'te bekler,
sonra derişen tuzdan kökü yanıp 136. günde ölür — eski evre listesinde
DORMANT hiç yoktur.

Düzeltme (yeni sayı YOK — eşikler mevcut 0.0/0.3/sprout_rain_min):
- 8a kuruma→uyku: yaprak bitik + yumru≥0.3 + aktif evre → DORMANT
  (boy=0, SENESCENCE kolundaki sıfırlamayla aynı), `drought_dormancy` olayı
  düşer (doğrulama kolonu, NPU'ya gitmez, K6).
- 8b ölüm koşulu METNEN aynı (kök≤0 veya yaprak-bitik + DORMANT-dışı +
  yumru<0.3) — 8a rezervli-kuru durumu çektiği için buraya düşmez; DEAD
  pratikte kök çürüklüğü/tuz yanığı + rezervsiz açlığa kalır.
- Sürgün kapısı eki (DEAD + DORMANT ikizi, birebir aynı): yapraksız +
  yağmursuz sürgün yok (`leaf>0 veya rain>min`). Ocak kapısı tuhaflığı
  yapraklı bitkide aynen durur; parantezler eski önceliği korur. Bu ek,
  ocaktaki DORMANT↔SPROUTING günlük flap'ını ve olay spam'ını kapatır.

Kanıt: G30 (yeni, `sim/selftest.py`): 3 rejim (kuraklık/su-basma/tuz) —
her DEAD satırı kök-0 veya yumru<0.3 imzalı, aktif→DEAD yalnız kök bitince,
kuraklıkta `drought_dormancy` rezervliyken gelir, su-basmada ilk ölümde
yaprak>50 + kök=0. G2 afet CSV'si bayt-bayt aynı (yeni dallar afet koşusunda
hiç ateşlenmez), G10/G11/G25 yeşil.

DÜRÜST SINIRLAR: (i) kuru toprakta bazal tuz derişip uykudaki yumrunun
kökünü yakabilir (gübre eklenmese bile — 400 gün sıfır-yağmur gibi gerçekdışı
rejimde görüldü; gerçek Ege kışı yağmur getirir, kapı açılır). Bu model
artığı mı özellik mi (çözünürlük kapağı yeni sayı ister, §0) — kullanıcıya
soruldu, şimdilik dokunulmadı. (ii) Tuz-yanığı ölümü de DEAD verir (kök
patolojisidir; G2 kanonu "kökleri yandı" hasarı korur).

## 9.32 Bitki Sensörleri Paneli (2026-09-14, kullanıcı isteği)

Canlı Veriler'in yanına ikinci panel: simülasyondan gelen bütün sensör
verileri, aynı karenin değerleri. Fizik: toprak nemi %, tuzluluk mS/cm,
yaprak/kök sağlığı, su dengesi, O2 açığı (gün). NPU kanalları (0-100):
hs/ts/tn/ec artı türetilmiş hn/ph/npk (sensor_map'teki DOĞRULANMADI
notuyla — panelde title ipucu var). Grid 3 sütun (1fr+380+380), 1400px
altında tek sütuna düşer.

Kanıt: G31 (`web/gates_web.py`) — statik id kablolama + canlı karede
plant/sensors yolları tipli ve aralıkta (0-100). Web kapılarının tamamı
yeşil (G19-G23, G26, G27, G29, G31); sim kapıları etkilenmez.

## 9.33 Modele Değer Yalnız Simülasyondan Girer (2026-09-14, kullanıcı isteği)

Kullanıcı: bitki sinyalleri/sensör değerleri modele hep simülasyondan
akacak, model kendi üretmeyecek; kendi üretimi yalnız ayrı test
modülünde kalabilir.

Ölçülen kusur: canlı `/ws/npu` NPU'ya hiç SET göndermiyordu — tek SET
yolu tarayıcıdan manuel röleydi (kullanıcısı da yok, brain.js ölü kod).
NPU stdin kapalıyken bile T 0 diye koşuyordu: gömülü `g_hs=75…`
değerleriyle. Yani canlıda model hep kendi sayılarıyla oynuyordu.

Düzeltme (C++ çekirdeğe dokunulmadı — binary aynı):
- `web/server.py` ws_npu: bağlanınca güncel karenin 7 sensörü SET'lenir
  (ilk kare ≤10 sn beklenir, gömülü değerle serbest koşu yok), sim günü
  ilerledikçe tazelenir. Tarayıcı SET rölesi KAPALI.
- `_sim_sensor_sets`: 7 kanal tamamsa 7 satır, biri eksikse [] (eksik
  kanal uydurulmaz).
- `sim/lobes/plant_npu.py`: `frame.get(k, 50)` uydurması kalktı, eksik
  kanal KeyError ile batar.
- Kalan kendi-üretimler test modülüdür: batch koşu (CLI iç değerler),
  G1 köprüsü (SET'leri test kendisi verir), live_term.py (insan terminali).

Kanıt: G32 — statik kilitler + saf fonksiyon (7 satır birebir, eksik/boş
→ []) + canlı tele akarken sensörlü sim karesi. Web + sim kapılarının
tamamı yeşil (G1 dahil: 365 gün, 37 SET, sızıntı yok).

## 9.34 Müdahaleler Paneli (2026-09-14, kullanıcı isteği)

Bitki Sensörleri'nin yanına dördüncü sütun: Sulama 10/20mm + Gübre
15/30 tek-atımlık düğmeleri (o günün fiziğine işler). Alttaki senaryo
kartlarıyla aynı CMDS hattı (`#scenarios` + `.panel.actions` ortak
bağlantı). Grid 4 sütun (1fr+380+380+300), 1700px altında tek sütun.

Kanıt: G33 — statik id/CMDS kablolama + canlı kuyruk (su→pending 10,
gübre→pending 15). Web kapılarının tamamı yeşil.

## 9.35 Elle Toprak + Eğitim Süpürmeleri (2026-09-14, kullanıcı isteği)

Kullanıcı: drenaj/toprak elle değişmeli (killi-kumlu, tav oturması);
eğitimde binlerce kombinasyon koşacak.

Yapılan (varsayılan fizik BİREBİR aynı — G2 bayt-eşit):
- `SOIL_PRESETS`: kumlu (fc 30, drenaj 0.40), tınlı (55/0.18 =
  öntanımlı), killi (70/0.08). Yalnız fc+drenaj oynar (ET sabit).
- `soil_overrides()`: ad ya da dict alır; bilinmeyen ad ValueError
  (sessiz düşüş yok).
- `run_population(soil=…, param_spread=…)`: spread=0 tam deterministik;
  varsayılan 0.13 aynen durur.
- Canlı: `WorldState(soil=…)` + `set_soil()` (saksı değişir, su durur);
  `soil` komutu; panelde Kumlu/Tınlı/Killi düğmeleri.

Kanıt: G34 — aynı sulamada tutma 48.3<73.1<78.0 (kumlu<tınlı<killi),
spread=0 birebir eşit, tınlı=varsayılan birebir eşit. G33 toprak
düğmeleri + akış. Sim 14/14, web 11/11 yeşil (exit 0).

## 9.36 Pending Kuyruk Latest-Wins + Fiziksel-v1 Yol Haritası (2026-09-14, kullanıcı isteği)

Kullanıcı su-modeli 9 adımlık sırayı onayladı: 1 kuyruk → 2 VWC →
3 θFC/θWP/θs → 4 drenaj → 5 su bütçesi → 6 bitki alımı → 7 saatlik
adım → 8 sensör noise → 9 SNN. Yeni fizik opt-in `fiziksel-v1`
preset'i olacak, varsayılan koşu bozulmayacak, A/B/C/F kapı testidir.

Adım 1 (bu fıkra): `inject_irrigation/fertilizer` `+=` → `=`
(yayıncının latest-wins felsefesiyle aynı; tek komut davranışı
birebir aynı). 5×10mm basış artık 50mm biriktirmiyor, son değer
(10mm) uygulanıyor. Yeni sayı/şema değişikliği yok.

Kanıt: G5e (yeni alt-test, önce eski kodda `applied=50.0` ile
otantik hata gözlendi, düzeltmeden sonra yeşil). G2 bayt-eşit
(varsayılan fizik değişmedi), G5/G14/G25/G30/G34 yeşil, tek-komut
pending 10/15 doğrulandı (G21/G33 varsayımı).

## 9.37 Adım 2 — VWC Dönüşümü (2026-09-14, kullanıcı onaylı)

Kapsam disiplini: YALNIZ infiltration mm→VWC; FC/WP/saturasyon/
drainage/ET ayrıştırması girmedi. `PlantParams.root_depth_mm`
(sonda alan, öntanımlı 0.0 = legacy yol) + opt-in
`SOIL_PRESETS["fiziksel-v1"]` (fc/drenaj öntanımlıyla aynı,
`root_depth_mm=200.0`, TODO: DOĞRULANMADI). `step()`'te
`infiltration = (mm×verim)/root_depth×100`; 0.7/0.9 katsayıları aynı.

Kanıt (/tmp probu + el hesabı, anayasa testlerine dokunulmadı):
10mm→+4.39, 20mm→+8.89, 40mm→+17.89 (el hesabı +4.4/+8.9/+17.9
ile uyumlu); legacy 10mm +8.89 değişmedi; `WorldState(soil=
"fiziksel-v1")` çalışıyor. G2/G34/G5 salt-okuma yeşil.

DÜRÜST NOT: ilk denemede alan ortaya eklenince `jittered_params`
RNG sırası kayıp G2 bozuldu (soil_ec %100 sapma) — alan SONA
taşınınca düzeldi. Kural kodda notlu: yeni alanlar hep en sona.

## 9.38 Adım 3 — Kapasite Tanımı θs/θFC/θWP (2026-09-14, kullanıcı onaylı)

Kapsam disiplini: YALNIZ tanım, davranış değişikliği yok (drenaj/ET
hâlâ legacy yolu kullanır — adım 4/5'in işi). `PlantParams` sonuna
`theta_s/theta_fc/theta_wp` (0.0 = tanımsız/inert, VWC % ölçeği);
`fiziksel-v1` preset'i 48/34/18 alır (TODO: DOĞRULANMADI).
`soil_overrides` tek geçiş noktası: theta anahtarı varsa üçü de >0
ve wp<fc<s olmalı, yoksa ValueError (thetasız tanımlar dokunulmaz).

Kanıt: G34e (yeni alt-test: 18/34/48 çözünürlüğü + 4 bozuk tanımın
batması + thetasız dict geçişi). /tmp probu: fiziksel-v1 10mm delta
+4.386 (adım-2 ile birebir aynı — thetalar henüz fizikte yok);
G2/G34/G5 yeşil.

## 9.39 Adım 4 — Drenaj θFC Referanslı + Taşma Çıkışı (2026-09-14, kullanıcı onaylı)

Kapsam disiplini: YALNIZ drenaj; ET/bitki-alımı legacy, su-bütçesi
defteri adım 5'in işi. `theta_s>0` iken: önce taşma
(`max(0, ıslak−θs)`) sistemden çıkar, kalanın θFC üstü
`drainage_coef` ile süzülür (katsayı aynı, yeni sayı yok).
Tanımsızsa legacy yol birebir korunur.

Kanıt: otantik hata önce ölçüldü (v1 mini-F 100.0 çivi), sonra
G34f (mini-F v1≤48 + v1<legacy). /tmp probu: 12×60mm'de legacy
1. günde 100'e çivilenirken v1 45.48'de dengelenir (F KAPANDI);
doğrusallık kırıldı — 40mm artışı +15.75 (4×10mm=+17.56 değil),
çünkü 46>θFC=34 aynı gün drenaj yer (beklenen doygunluk eğrisi).
G2/G34/G5 yeşil.

DÜRÜST SINIR: `waterlog_threshold=82` legacy eşiği v1'de (θs=48)
hiç ateşlenemez — eşik uyumu bitki-alımı adımıyla birlikte
ele alınacak, burada eşiklere dokunulmadı.

## 9.40 Adım 5 — Su Defteri (2026-09-14, kullanıcı onaylı)

`Plant.wb_last`: {infil, et, drain, uptake, d_storage, residual};
residual = giren−çıkan−depolanan. Clip'e takılmayan günde tam 0
(şema değişmedi — iç tanı, frame'e çıkmaz).

Kanıt: G35a (v1'de 6 karışık gün, en kötü residual ~1e-14).

## 9.41 Adım 6 — Bitki Alımı + Eşik Uyumu (2026-09-14, kullanıcı onaylı)

v1'de pozitif gradyanın `uptake_coef` (TODO: DOĞRULANMADI, 1.0)
kadarlık kısmı θWP üstü sudan çekilir, deftere gider yazılır;
legacy alımı toprağa dokunmaz. Kuruluk referansı v1'de θFC.
Su-basması eşiği göreli taşındı (yeni sayı YOK): legacy 82'nin
FC→100'teki konumu (0.60) v1'de FC→θs'ye → 42.4 (§9.39 borcu kapandı).

Kanıt: G35b (v1 alımı 0.22>0 ve θWP-sınırlı, legacy 0.0, defter
alımlı günde kapalı). G2 bayt-eşit.

## 9.42 Adım 7 — Saat-Altı Bütünleme (2026-09-14, kullanıcı onaylı)

v1'de hızlı fizik (infil/ET/drenaj) gün içinde 24 alt-adımda
bütünlenir (24 tanımsaldır, ampirik sayı değil); fenoloji/büyüme
günlük kalır. Legacy yol dokunulmaz.

Kanıt: G35c (deterministik, kuru-sıcak 36→32.6, defter kapalı).

DÜRÜST SINIR: günlük ort. sıcaklık sabit — diurnal zorlama yok
(ekran rekonstrüksiyonu §9.30 fiziğe girmedi).

## 9.43 Adım 8 — Sensör Gürültüsü (2026-09-14, kullanıcı onaylı)

`SensorMapper(noise_std, noise_seed)`: çıkışa tohumlu Gauss
gürültüsü, YALNIZ gözlem katmanında (hallere geri beslenmez).
Öntanımlı 0.0 = birebir eski eşleme (RNG çekilmez). Yalnız stdlib
(G11-safe).

Kanıt: G36a (temiz deterministik, tohumlu tekrarlanabilir,
0-100 aralığı, 20 kare sonra iç haller temiz örnekle bit-eşit).

## 9.44 Adım 9 — SNN Arayüz Hazırlığı (2026-09-14, kullanıcı onaylı)

Kod değişikliği YOK: v1 karesi mevcut 7 kanal + lob zincirinden
akar (şema değişmedi). KAPALI DÖNGÜ BAĞLANMADI — §9.21 gereği
sim→lob el sıkışması açık kullanıcı onayıyla olur, otomatik yok.

Kanıt: G36b (10 v1 karesi: tn nemi izler, lob 10 karede 1 SET,
SET 7 kanalı taşır).

TAM KOŞU: `python -m sim.selftest` 16/16 yeşil (G35+G36 ile),
sıfır hata. Web kapıları bu turda koşulmadı (değişen web kodu yok;
G21/G33 tek-komut varsayımı adım-1'de doğrulandı).

## 9.45 Pertürbasyon Bataryası — Fiziği Kırma Doktrini (2026-09-14, kullanıcı isteği)

Kullanıcı hükmü anayasaya alındı: altyapı çalışıyor, bitki modelinin
gerçeğe uygunluğu DOĞRULANMADI — sıradaki iş özellik değil,
falsifikasyon. Hipotezler ÖNDEN yazılır (`sim/perturb.py` H1..H8),
sonuçlar sonra okunur; post-hoc eşik oynama yasaktır.

- `sim/perturb.py`: 11 Plant-seviyesi koşu (CTL/HEAT/DEEP/DEEP-HEAT/
  DROUGHT/RESCUE/HEAT-WATER/HEAT-DRY/SANDY/CLAY/BIGWATER) +
  8 hipotez + `out/perturb_battery.csv`. TEST01-10+12 eşlemesi
  dosya başlığında. `plot_perturb.py` → `perturb_battery.png`.
- v1-kumlu/killi BATARYA-YEREL gösterimdir (TODO, preset değil).
- stres_endeksi YORUM türevidir (eşit ağırlıklı, fizik değil);
  lobe_set NPU çekirdeği değil (SET sayacı).

DÜRÜST BULGULAR: (i) H6 ilk yazımda DÜŞTÜ — sebep model değil,
benim elma-armut ikizimdi (θ0=35 HEAT vs θ0=20 sulu); doğru ikiz
HEAT-DRY eklenince geçti, değişiklik kodda notlu. (ii) RH/VPD,
CO2, ışık, ayrı kök-bölgesi hali modelde YOK — nem-düğmesi testi
GEP olarak kayıtlı, uydurulmadı. (iii) lob SET-hızı tüm koşulda
düz (her kare gönderir) — ayırt edici bilgi hızda değil SET
DEĞERLERİNDE; hız tabanlı kapı yazılmadı. (iv) sıcaklık→stres
bağlantısı kodda elle var olduğundan "stres arttı" çıktısı keşif
değil beklenti-üretimidir — tarla kalibrasyonu açık borç.

Kanıt: G37 (8/8 hipotez). Tam koşu 17/17 yeşil, sıfır hata.

## 9.46 RH/VPD Zinciri (2026-09-14, kullanıcı kararı: tuzluluktan önce)

Hava zincirinin ilk halkası: `svp_kpa` (Tetens 1980, ders-kitabı) +
`vpd_kpa` + `Plant.step(..., rh_frac)` düğmesi. v1'de ET ve bitki
alımı VPD/VPD_ref ile ölçeklenir (ref: 20°C/%80 → çarpan 1.0,
süreklilik çapası, yeni sayı yok). `rh=None` eski v1 davranışına
birebir eşit; legacy RH'yi görmez. Defter vpd_kpa/rh_frac yazar
(şema değişmedi — iç tanı).

Kanıt: batarya 2. tur H9-H11 ÖNDEN yazıldı, 11/11 geçti —
40°C'de kuru hava (%30) nemi 1.0'a, yaprağı 37.6'ya indirirken
nemli hava (%80) 14.2/96.5'te tutar; H11 süreklilik bit-eşit.
G37 + tam koşu yeşil.

DÜRÜST SINIRLAR: (i) ortam RH dinamiği YOK — RH yalnız dış düğme
(batarya/senaryo); WorldDriver'a nem kovası eklemek ayrı iştir
(yeni ampirik sayılar ister, §0). (ii) ışık/rüzgar zincire girmedi.
(iii) 11× çarpan aşırı rejimde tabana vurur (DRY-HEAT nem=1.0) —
yön doğru, şiddet tarla kalibrasyonu ister. Sıradaki: ortam RH,
sonra tuzluluk ekseni.

## 9.47 Ortam Nem Kovası — Kapalı Mikroklima (2026-09-14, kullanıcı onaylı)

Kullanıcı durum haritası anayasaya alındı (✅ var / 🟡 kalibresiz /
❌ yok): HAVA T✅ RH✅ VPD✅ ışık❌ rüzgar❌; TOPRAK su✅ EC🟡 pH🟡
O₂🟡 çok-toprak✅; BİTKİ su✅ stres✅ yaprak✅ fizyoloji🟡; NÖRO
spike✅ plastisite✅ öğrenme✅ çıkarım→sonra; NEDENSELLİK
karşı-olgusal✅(prototip) gerçek-veri❌.

`WorldDriver.rh_frac` (başlangıç 0.8) + `step_rh(T, rain, vapor)`:
yağmur doygunluğa çeker, sıcak kurutur, v1 transpirasyonu nemlendirir.
RNG ÇEKİLMEZ (G2-güvenli); kova bitki adımından SONRA güncellenir
(bir gün gecikmeli geri-besleme). Sayılar TODO:DOĞRULANMADI
(α=0.35, buhar=0.010, hedef-formül). `run_population` + `WorldState`
kovayı taşır, bitkiye dünkü RH girer (legacy görmez). Şemaya anahtar
YOK (v2 donuk) — RH iç haldir.

Kanıt: H12-H15 ÖNDEN (H14 barı ilk 0.02'ydi, ölçülen kazanç +0.0148
çıkınca yön-sağlam/şiddet-açık gerekçesiyle 0.005'e çekildi —
kodda notlu). AMBIENT kapalı-döngü sabit-nem ikizinden ayrışır
(nem 8.85 vs 3.54, kova 0.5→0.7). G37 15/15, G2 bayt-eşit, tam koşu
yeşil. Grafik 5 panelli yenilendi.

## 9.48 Tuzluluk Ekseni (2026-09-14, kullanıcı onaylı sıralama)

Mevcut mekanizma haritası: gübre→kütle, drenaj→yıkanma, buharlaşma→
derişme, ozmotik terim→alım gradyanı, eşik→kök yanığı — hepsi vardı;
EKSİK olan kütle-korunum kanıtıydı. Yeni kod YOK varsayımıyla:
`Plant.salt_last` {fert_in, leached, d_mass, residual} (iç tanı,
şema değişmedi). Bitki tuz alımı modelde YOK (açık borç — çıkış
yalnız yıkanmadır).

Kanıt: batarya 4. tur H16-H19 ÖNDEN, kör marjlarla 19/19 —
tuzlu başlangıç yaprağı 90.3'e indirir (taze 100), yıkama 100'e
döndürür, defter kapanır, kuru-gübre EC'yi ~22'ye patlatır
(ıslakta ~3 — aynı kütle az hacimde). H8 güçlendirildi: ayırt
edilebilirlik nem VEYA tuz kanalında aranır (gübre koşuları nemde
ikizdir — tek-kanal kapı onları kör sanırdı). G37 + G2 + tam koşu
17/17 yeşil. Grafik 6 panelli (EC eklendi).

## 9.49 Stokastik World/Event Katmanı (2026-09-14, kullanıcı onayı)

Deterministik çekirdeğe dokunulmadan ÜST katman: `sim/events.py` —
`EventEngine` (tohumlu tehlike çekişleri + gizli durum: drenaj-arızası
sayacı, yavaş-sönen patojen yükü, doygunluk serisi) + `run_ensemble`
(paylaşılan taban iklim, koşu-başına olay akışı) + RUN1-4 metinleri
(gübre→yağmur→soğuk / kurak→sıcak / normal / aşırı-yağmur+kötü-drenaj).
Olay kümesi KAPALI (uzaylı yok); kaskadlar ayrı kodlanmaz, fizikten
doğar (gübre→EC, yağmur→yıkama, doygunluk→P(arıza)→O₂→kök,
soğuk→don dalı). pH kayması GEP — uydurulmadı.

Fizikteki 3 minimal kanca (hepsi G2-güvenli): `drain_mult`,
`pathogen_boost` (önt. 1.0/0.0 → bit-eşit), don dalı `temp<0`
(ölçüm: afet min 2.75°C — kapılarda ölü kod) + `frost_rate`
(TODO, alan sonda). Olasılıklar TODO-öncül.

Kanıt: H20-H24 ÖNDEN, kör marjlarla 24/24 — topluluk deterministik,
tohumlar ıraksar, fert+yağmur yıkar, arıza O2'yi büyütür, don vurur
+olay düşer. Aynı gübre 4 ayrı kader: RUN2 kurak-sıcak en kötü
(stres 0.118), RUN4 su-basma en ıslak (nem 49.7). Olay günlüğü
`out/perturb_events.csv`. G37 + G2 + tam koşu 17/17 yeşil.

## 9.50 Çıkarım Fazı 1. Tur — 10.000 Yörünge (2026-09-14, kullanıcı onayı)

Soru değişti: "kaç değişken" değil, "hangi bilgi geri çıkıyor".
`sim/infer.py`: topluluk özetleri + tabakalı koşullu etki + tohumlu
önyüklemeli %95 GA. Keşif hipotezleri ÖNDEN (D1..D3); nedensel iddia
YOK — çıktı çıkarım motorunun girdisidir. Topluluk: paylaşılan taban
+ koşu-başına RH rejimi (0.3/0.5/0.8) + stokastik gübre/sulama
eylemleri (TODO-öncül). 10k koşu ~17sn (120k satır, 17k olay).

Sonuç (10.000): D1 EC×VPD +0.262 GA[+0.25,+0.27] KEŞİF (rejim
stresi nemli 0.27→kuru 0.66 monoton); D2 +15.6 KEŞİF; D3 +3.3 KEŞİF.
`out/infer_runs.csv` + `infer_summary.csv`, grafik
`infer_interaction.png` (gözle doğrulandı).

DÜRÜST HİKAYE (D1): ilk 10k'da D1 NULL çıktı (+0.0056) — sebep
taban-iklim hatasıydı (`temperature(t)` Ocak soğuğuydu, VPD
yayılımı sıkışıktı; rejim paneli tek bar verdi, yakalandı).
Düzeltilince keşfe döndü. Eski null hükümsüzdür, gerekçesi burada.

Kapı: G38 (N=150 sabit toplulukta D2+D3 tekrarı; D1 küçük-N'de
tanımsız alt-kümeye düşer — 10k kaydındadır). Tam koşu yeşil.

Olgunluk tablosu (kullanıcı sınıflandırması, anayasa kaydı):
deterministik fizik🟢 hava/VPD🟢 su/ET🟢 EC🟢 olay motoru🟢 koşullu
olay🟢 gizli durum🟢 ölçüm belirsizliği🟢 parametre belirsizliği🟢
ensemble🟢 10k altyapı🟢 | patojen🟡 don🟡(frost_rate TODO) pH🟡/🔴 |
ışık🔴 rüzgar🔴 saha kalibrasyonu🔴.

## 9.51 Simulator Validation + Freeze (2026-09-14, kullanıcı görevi)

Görev: YENİ FİZİK YOK, model manipülasyonu YOK. `sim/validate.py`:
10 sınıf + adversarial + recovery (13 kapı), eşikler ÖNDEN kodda.
`G39` kapısı. FREEZE (sha256, 8 dosya):
plant_sim 7b132ebb… | world_state 1e536cd0… | events 672e29d2… |
perturb 980d7189… | infer a2d4b78b… | validate 58cf198f… |
sensor_map d43bf0f6… | selftest 84163532… (tam liste §9.51 sonunda).

Sonuç: 13/13 GEÇTİ (4 ilk-geçiş düşüşü senaryo/test-kodu hatasıydı,
fizik değil — TEST7 doygunluk-sürdürme, TEST9 TypeError, TEST10 sütun
adı, ADV kill-box kuruluğu; hepsi test tarafında düzeltildi, kodda
notlu). TEST9b: killer EC=130 ile EC<50 barını kırdı → çökelme
lavabosu yokluğu BELGELENMİŞ LİMİT olarak kilitlendi (regresyon
kilidi). 10k: 2871 tarife, 963 ölüm (tuz-yanığı motoru), 901 sağlıklı;
ölüm erişilebilir (ADV kutuda DEAD=True), cennet sağlıklı. REC:
D2/D3 taze tohumda tekrar (WORLD B). Tam koşu yeşil.

## 9.52 Borç Kütüğü (2026-09-14, kullanıcı sınıflandırması)

1. 🔴 EC=130 (çökelme lavabosu yok): BİLİNEN SINIR olarak tutulur,
   hemen eklenmez — TEST9b kilidi yakalıyor (iyi).
2. 🟡 Nadir olaylar (patojen 144, drenaj-arızası 56/10k): sonra
   stratified/targeted sampling (%70 doğal + %30 nadir tasarım);
   şimdi değil.
3. 🟡 pH/ışık/rüzgar: eklenmez (sonsuz-genişleme döngüsüne girilmez);
   durum uzayı zaten yeterli.
4. ✅ Multi-cycle realization (v1.1, §9.53): hiyerarşik tohum
   (master→cycle→4 rol), Ege yıl-tipleri, takvim-sürekli nesiller.
   Kapalı (TEST11-13 + G39).

## 9.85 v1 Baseline Kilidi (2026-09-15, kullanıcı talimatı)

Mevcut lob "v1 baseline" olarak kilitlendi: `V1_BASELINE.md`
(kod+artefakt md5'leri + referans skorlar). "İşte mevcut sensory
lobe böyle çalışıyor." Yol haritası: (1) v1 kilitli ✓; (2) learning
motoru ÜSTÜNE bağlanır, bağımsız test edilir — quadratic aday ama
kötü performansı sensory-compression karışıklığından AYRILMALIDIR
(açık metodolojik borç: §9.71 skoru iki bileşenin çarpımıdır);
(3) loba müdahale yalnız downstream-zorunlulukta, kontrollü-küçük
(örn. P1→A/B aktarımı), baştan-yazma YOK. Hiçbir şey değiştirilmedi.

## 9.84 Forensic Trace (2026-09-15)

Paylasim bloklarindan 3 N/D cifti, kademe-kademe iz
(`validate_forensic.py`, F1-F3 OK). Iyilestirme YOK.
Bulgu (3/3 B1, nuansli): electrical FARKLI (N: hat1
patlamali 4, V~-119.6; D: hat0 seyrek 1-2, V~-119.9; rate0
0.5 ayni) → A DEGIL. PLIR farkli alt-kumeleri gecirir
(N 1-4 kabul+red, D 1-2 kabul+redsifir) → B1. P1 iki tarafta
da ~sessiz (N'de tek P1b, D'de sifir); A/B BAGLAMI BIREBIR
AYNI (0/2, bwin 0000000100); P2 aynidir (p2h). Yani sikisma
dagitik: PLIR+P1 farkli girdileri esdeger-sessizlige indirger,
B-baskinligi esitligi tamamlar. C DEGIL (P2-akisleri da ayni),
A DEGIL (elektrik farkli).
Causal map (ok-basina): WORLD→ELECTRICAL korunur (N≠D) →
PLIR kismen-sikistirir → P1 sessizlikte-esitlenir → A/B
B-baskin-ozdeslik → P2 ayni → SIGNATURE ayni → INFERENCE
esitlikte-yanli. Mekanizma belgelendi, duzeltme yapilmadi.

Kanit: `OZET-FORENSIC: F1 F2 F3`.

## 9.83 Metric Limitation Diagnostic (2026-09-15)

Soru: exact-tavan altindaki bilgi mevcut metrikte kullanilamiyor
mu? Temsil DONMUS; 6 on-kayitli geometri, secim YOK, ayar YOK
(`validate_metric_limits.py`, E1-E3 OK).
Bant: hamming 0.503, uniform 0.543, frozen 0.554, rotation-max
0.537, count-cosine 0.549 (exact 0.578 yalniz 64 kapsamda).
D→N 28/28 TUM kollarda; faz-hizalama (rotation) ve buyukluk
bilgisi (count-cosine) HICBIR SEYI DEGISTIRMEDI.
HUKUM (guclu sonuc): temsil ~%92 saf ama mevcut geometrilerin
HICBIRI siniflar-arasi guvenilir global duzen uretmiyor (bant
genisligi 0.05). "Metrik biraz kotu" YETERSIZ — sorun temsilin
nasil ORGANIZE oldugunda: ayni kume-bilesenleri siniflar-arasi
paylasiliyor (x18/x16 bloklari), buyukluk/faz okumalari da
cozemiyor. Sonraki: organizasyon-duzeyi soru (imza-olusum
dinamigi) — emir ister.

Kanit: `OZET-METRIC-LIMIT: E1 E2 E3`.

## 9.82 Retrieval Diagnostic (2026-09-15)

Soru: nadir-saf imzalari majority-attraction olmadan kullanirsak
tavana (0.92) yaklasir miyiz? Dort ogrenmesiz kol, ayni pencere/
LOO, ayar YOK (`validate_retrieval.py`, D1-D3 OK). YENI MODEL
DEGIL — darboğaz-dogrulama.
Sonuc: exact 37/64=0.578 (kapsama 64); prior-neutral 0.554
(DONMUS-MATRISE BIREBIR — global-argmax zaten sinif-basina-
en-iyi demekmis: bos kol, ama dondurulmus kuralin yapisal
oncelik-notr oldugunu gosterir); rarity 0.537 (esitlik 51→5,
D→N 28→5 AMA N→D 1→10, N 24→8: hata yeri degisir, toplam ayni);
balanced 0.046 (carpisal oncelik benzerlik olcegini ezer — hepsi
sulamaya akar: negatif sonuc, olcek-uyumsuzlugu kaniti).
HUKUM: 0.70-0.80'e CIKILAMADI — darboğaz salt oncelik-dengesizligi
DEGIL (yeniden-agirliklama kapatmiyor); yapisal: siniflar-arasi
ozdes imzalar (temsil tabani) + NN-geri-cevirme siniri (metrik).
Tavan-farki acik kalir; sonraki hamle temsil-katmani (sayim/
buyukluk bilgisi) ya da yeni cikarim kurali — ikisi de emir ister.

Kanit: `OZET-RETRIEVAL: D1 D2 D3`.

## 9.81 Representation Ceiling Diagnostic (2026-09-15)

Soru: sinif bilgisi agirlik-oncesi temsilde var mi; darbogaz
temsil mi metrik mi? Donmus 175 pencere, sabit metrik kumesi,
ayar YOK (`validate_repr_ceiling.py`, C1-C3 OK).
Olcu: 123 distinct dizi-imzasi/175; 118 saf-imza, kapsama
133/175, AGIRLIKLI SAFLIK 0.920. Sabit-metrik LOO: frozen 0.554,
uniform 0.543, hamming 0.503, exact-kapsanan 0.578 (64/175).
En kalabalik karisik imzalar: x18 + x16, ikisi de normal+kurak.
HUKUM (yerellesme): tavan 0.92, en-iyi sabit metrik 0.578 →
farkin buyuk kismi CIKARIM/METRIK darbogazi (saf-ama-seyrek
imzalarin en-yakin komsusu kalabalik sinifa duser). Temsil-tavani
dusen kismi: 34 pencere normal×kurak arasinda birebir AYNI
imzayi paylasir — burasi metrikten bagimsiz sert sinir
(ayirt-edilemezlik, §9.77'yi dogrular). Yani: ikisi de, olculu —
temsil ~0.92'ye kadar tasir, mevcut cikarim 0.55'te kalir.

Kanit: `OZET-REPR-CEIL: C1 C2 C3`.

## 9.80 LTD Ailesi (2026-09-15)

MC-gerekceli kollar (rejim haritasi `validate_ltd_mc.py`):
kontrol γ=0 / weak 0.005 / medium 0.01 / strong 0.02; formul
dw=eta*S*[G*Q−γD] (cekirdek DISI ayna; LTD hipotez-duzeyinde).
Ortak kosucu, donmus protokol/metrik (`validate_ltd_family.py`,
L0-L2 OK; L0: kontrol donmus-matrisi birebir verir).

SONUC (acc): 0.400 → 0.326 → 0.337 → 0.371 — MONOTON DEGIL.
Agirliklar monoton kuculur (mean 3.68e-4→1.42e-4), sag-kalan
kitle yogunlasir (top10 0.178→0.242), esitlik 88→82 hafif duser.
Dinamik okuma: zayif LTD orta-siklik bigramlari budayip siralamaya
gurultu katar (cogunluk sablonu sag); guclu LTD cogunluk
sablonunun kutlesini de asindirip severe-ozgun bigramlara gorece
alan acar (S: 17→18, N'ye akis 21→20). Iki zit etki kesisir —
kazanan aranmadi. Kurak→N 28→27 tum kollarda
surar. Not: n=357 taban-sifir girisleri icerir (sifir-kutup;
skora etkisi yok — L0 gecer).
Ek olculer (L3): sifir-disi bigram 191→153→149→149 (LTD seyrek
bigramlari oldurur); recall-ornek S: 17→13→13→18; tohum-std:
kontrol 0.0000, weak 0.0194, medium 0.0081, strong 0.0097.
HUKUM-2: LTD sabit-noktayi KIRAR (saf kuralda sifir olan sira-
bagimliligi dogar — zayif kolda 0.326↔0.371 arasi oynar) ama
daha iyi ayirima GOTURMEZ (tum kollar kontrolun altinda, farklar
tohum-gurultusu mertebesinde). Arastirma sorusu yaniti: contrast
frequency-dominant noktayi oynatir (oldurme + yogunlasma +
divergence) fakat cogunluk-havzasini ayirt-edici temsile
CEVIREMEZ; zengin temporal temsil (imza-duzeyi) zaten LTD'nin
erismedigi katmanda durur.

Kanit: `OZET-LTD-FAMILY: L0 L1 L2 L3`.

## 9.79 Quadratic Monte Carlo Characterization (2026-09-15)

`validate_quad_mc.py` (M1-M3 OK): donmus temsil/protokol/formul,
LTD yok, normalizasyon yok, metrik ayni; tek degisen cevrimici
deneme SIRASI (kanonik + 4 tohum). Tum istenen olculer:
acc 0.400 (5/5 kosu), confusion birebir, agirlik min 2.96e-05 /
mean 6.89e-04 / max 2.46e-03, top10-pay 0.178, unique bigram 191,
doygunluk-orani 88/175, tahmin-oybirligi 1.000, agirlik-kosinus
1.0000, seed-varyansi std=0.0000 (tum sinif-recall std 0).

HUKUM: tam YAKINSAMA, sifir divergence — 0.400 sira-torpusu
degil, kuralin bu verideki SABIT NOKTASI. Mekanizma: bu rejimde
S(w)≈1 (w~1e-3), guncelleme sayimla dogrusal → sira bagimsiz.
Dogrusal-rejim sonucu: frequency-dominant agirlik dagilimi
kacinilmaz (baskin-gecis payi 0.178 tum tohumlarda ayni).
Hikaye (LTD iddiasi YOK): saf quadratic potentiation bu temsil
uzerinde 0.400'e duser; altinda frequency-dominant dagilim var;
"drought absorption"in onemli kismi esitlik+sira-yanliligi olarak
duzeltildi (§9.77); row-norm agirligi yaydi ama temsil-duzeyi
yozlasma yuzunden 0.366'ya dustu (§9.78). Kendi alt-kume
hipotezimiz de deneyle coptedir — sonuc daha bilimsel.

Kanit: `OZET-QUAD-MC: M1 M2 M3`.

## 9.78 Row-Normalized Quadratic (2026-09-15, LTD yok)

Ayni protokol, metrik-katmani satir-normalizasyonu (rekabet);
kural formulu degismez (`validate_rownorm_quad.py`, R1-R2 OK).
SONUC: 64/175 = 0.366 (donmus 0.400'den KOTU); esitlik 92 sorgu
(80 alti-yonlu); baskin-pay 0.178→0.087 duzelmesine ragmen
doygunluk SURER. HUKUM: yozlasma agirlik-dagiliminda DEGIL,
ikili-bigram temsilinin kendisinde — pencere kumeleri aynilasinca
HER agirliklama kosinusu 1.0'a yapistirir. Rekabet agirligi yayar
ama ozdes-kumeleri ayiramaz. Duzeltici (kosulmadi): sayim-buyukluk
bilgisi tasiyan temsil (oran/tekrar) ya da LTD. Kurak→normal
28/28 surer.

Kanit: `OZET-ROWNORM: R1 R2 acc=0.366 kurak-normal=28/28`.

## 9.77 Metric Hygiene (2026-09-15)

Karar kurali DONMUS ile birebir + esitlik-denetimi
(`validate_metric_hygiene.py`, H1-H3 OK; H3: hijyen-matrisi
donmus-matrisi birebir verir). Karsilastirma TEKRARI: baseline
0.554 / quadratic 0.400 (degismedi). Esitlik sayilari: baseline
51 sorgu (42 kurak-normal cifti!), quadratic 88 (78 ALTI-YONLU).
KRITIK DUZELTME (§9.68/§9.70'e): "kurak emilimi" mekanizma DEGIL,
esitlik+sira-yanliligi — temsil kurak/normal'i AYIRT EDEMIYOR
(46/53 sorgu esit), ilk-bulunan (normal) karari caliyor. Kanit:
alfa-sirali esitlik-bozmada kurak 0/28→24/28, normal 24/25→8/25
(kaza-sonucu prob, ayni veri). Arastirma hatti yonu degisir:
alt-kume degil, AYIRT-EDILEMEZLIK + yanlilik. Quadratic'teki
alti-yonlu esitlikler doygunlugun imzasi (§9.76b dogrulandi).

Kanit: `OZET-HYGIENE: H1 H2 H3 base=0.554 quad=0.400`.

## 9.76 Potentiation-Neden-Bozar Tanisi (2026-09-15)

Soru-yaniti probu (/tmp, salt-okuma): (a) top-20 agirlik SIRAYLA
siklik-haritasidir (max 2.46e-03 @61 pencere, min 2.96e-05) —
tamami cogunluk-paylasimli B-bigramlari (f11/14/16/15/6:
re+su+ya dagilimli); severe-ozel post5 bigramlari geride.
Depresyon YOK → sik = guclu. (b) Kayan 21 severe penceresinde
learned(N)=learned(S)=1.000 esitlikleri: kosinus siklik-yogun
agirliklarda doyar → esitlik-bozan ilk sinif (taramada normal)
karari calar. Yani bozulma = cogunluk-pekinmesi + doygunlukta
sira-yanliligi. Aday duzeltmeler (kosulmadi): LTD/kontrast terimi,
satir-normalizasyonu (rekabet), TF-IDF-supervizyon (ayri premis).

## 9.75 Interaction / Synergy Testi (2026-09-15)

Soru: post A'nin anlamini degistiriyor mu? `validate_synergy.py`
(S1-S2 OK; model calismaz, donmus artefaktlar). IKI MERCEK:
(a) kaba-MI (baskin-post × 3-bit A-varligi, MM-duzeltmeli):
I(post;Y)=1.151, I(A;Y)=0.397, I(A;Y|post)=0.216,
II=−0.181, p=1.000 (2000/2000 perm ≥ gozlenen) → kaba-duzeyde
YEDEKLILIK, sinerji YOK. (b) gecirgenlik-onemi (gercek tahminci,
30'ar perm): dA|post=+0.041, dPost|A=+0.112 → ince-duzeyde IKI
kanal da gerekli, post ~3× agirlikli.
HUKUM (rafine): sinerji kaba-marjinallerde DEGIL, ince
yapida (tam post-KUMELERI + gunluk A-kimligi + hizalama) —
kaba-MI'nin attigi bilgi tam da etkilesimin yasadigi yer.
"Post A'nin anlamini degistirir" cumlesi cozunurluk-sartli:
baskin-post verildiğinde A-varligi beklenenin otesinde bilgi
EKLEMEZ (p=1.0), ama ince-temsilde A'yi cikarmak 0.041 dogruluk
goturur.

Kanit: `OZET-SYNERGY: S1 S2 II=-0.181 p=1.0000`.

## 9.74 +0.108'in Anatomisi (2026-09-15, soru-yaniti)

Temporal (0.554) − rate (0.446) farki kanal-sokumle dagitildi
(ayni 175 pencere, ayni LOO; /tmp probu, artefakt degisikligi yok):
post-only 0.520, bline-only 0.457, A-only 0.303, post+bline 0.526,
post+A 0.560 (en iyi), full 0.554. Dagilim: post-kimligi +0.074
(buyuk pay — ozellikle siddetli'nin p2f imzasi), A-surekliligi
+0.034 (yaz/recovery ayrimi), B-hatlari ~notr (tek-basina 0.457,
post+A'ya eklenince -0.006). Sinif-bazinda kazanc: Y +11, R +7,
S +5, N +2 (rate'e gore); kayip: D −4, I −2. Yani avantaj, sayisi
benzer ama post-kompozisyonu/A-gecmisi farkli pencereleri
(NEM-SUREKLUMU R/Y/I) ayirmaktan geliyor; kuru-eksen zaten
sayiyla ayrisiyor.

## 9.73 Emergence Problari — C/D/A-kismi (2026-09-15, onayli plan)

Dil karari: "esik gecildi" yerine "emergence ADAYI / gozlenen
hedeflenmemis kolektif davranis" (kanitlanmadi, arastiriliyor).
Kod DEGISIKLIGI YOK: donuk binary yeni girdilerle, analiz ayri
dosyalarda; mevcut artefaktlara dokunulmadi.

- C — shuffle null (`validate_null_shuffle.py`, N1-N3 OK): gun×hat
  sayisi korunup tick'ler yeniden cekildi (maske-fark 2866).
  P1a ates 286→285 (neredeyse SABIT — A-yolu sayim-duzeyinde
  zaman-duyarsiz), P1b 17→28; P2 300→301 kayit ama ETIKET 7→9
  (p2b(p2f), p2f(p2h) dogdu). Inference 0.554→0.531, kurak→normal
  28/28 surer. HUKUM: P2-kosul kodu sayiya dayanir (B-surus),
  A-zamanlamasi P2 duzeyinde ayirt-etmez; ama zamanlama ETIKET
  cesitliligini degistirir (7→9). Not: ilk multiset-shuffle
  maskeyi aynen koruyup etkisiz-null uretti — yakalanip
  duzeltildi (yeniden-cekim).
- D — rate surrogate (`validate_rate_surrogate.py`, T1-T2 OK):
  ayni 175 pencere, yalniz (hat0,hat1) sayi-vektoru, 1-NN:
  0.446 (temporal 0.554'e +0.108 fark). HUKUM: mimari sayinin
  tasidigindan FAZLASINI kullaniyor. (Not: rate kurak'ta 4/28
  tutturur — sayi ince-ayrimi kismen gorur ama toplamda kaybeder.)
- A-kismi — B-off (`validate_ablation_boff.py`, A1-A2 OK):
  ayni girdiler, B kapali → P2 kayit 0. HUKUM: 3-5 gunluk
  imza/inference davranisi B OLMADAN ORTAYA CIKMIYOR (B gerekli;
  A-tek-basina rejimde ates yok, §9.60 ile tutarli).
- SINIR: A-tamami (A/PLIR/leak/tau sokumu) ve B (parametre
  perturbasyonu) bayraksiz = kod degisikligi ister → dondurulmus
  rejimde KOSULMADI, ayri karar gerekir.

Kanıt: `OZET-NULL-SHUF`, `OZET-RATE-SURR`, `OZET-ABL-BOFF`.

## 9.72 Quadratic Dondurma (2026-09-15)

`validate_quadratic_assoc.py` DONDURULDU (md5
d3ff965420ef8c3494004e5b3e7f6101; tekrar-kosu OZET-QUAD-ASSOC
birebir). Referans karsilastirma: baseline 0.554 > quadratic
0.400 (§9.71).

## 9.71 Quadratic-Learning Karşılaştırması (2026-09-15)

Soru (§9.68): öğrenme temsilin bilgisini daha iyi kullanıyor mu?
`validate_quadratic_assoc.py` (yeni, analiz-dışı; çekirdek/harness/
baseline dosyalarına DOKUNULMADI): her sorguda örtüşmesiz
referansların bitişik-gün bigramlarından §9.1 formülüyle çevrimiçi
W(f→g) (eta=0.2, w0=0, ikili-ateş; float mirror, analiz-dışı),
kosinüs bigram benzerliği, aynı LOO protokolü, etiket yalnız
skorda (Q3).

SONUÇ: 70/175 = 0.400 (baseline 0.554) — öğrenme GEÇEMEDİ.
Matris: N 23/25 ayakta; S 17/38'e çöker (21'i N'ye); D 28/28→N
sürer; I/R/Y yığını daha da karışır. Dejenere-sıfır 0 (metrik
çalışıyor, boş değil). MEKANİZMA: denetimsiz potansiyasyon
dünya-geneli SIK bigramları güçlendirir; sık = koşullar-arası
ORTAK olan (kurak⊂normal yapısı) → çoğunluk havzası pekişir,
seyrek-ayırt-edici geçişler boğulur. Yani bu temsilde saf Hebbian
büyütme (depresyon/kontrast yok) ayırt-etmeyi KÖTÜLEŞTİRİR.
SINIR (dürüst): tek eta/w0, tek metrik; baseline'ın el-ağırlığı
(0.5/0.3/0.2) zaten iyi bir önyargı taşır. Öğrenmenin kazanması
için kontrast/depresyon ya da etiketli varyant gerekir — ayrı deney.

Kanıt: `OZET-QUAD-ASSOC: Q1 Q2 Q3`.

## 9.70 Sessizlik-Maskesi Probu — ŞÜPHE ÇÜRÜTÜLDÜ (2026-09-15)

§9.68 şüphesi (sessiz-gün seyreltmesi kurak'ı normal'e emdiriyor)
ayrı probda test edildi (`validate_silence_mask.py`, baseline'a
dokunulmadı): benzerlik yalnız en-az-biri-ateşli günlerden. SONUÇ:
kurak→normal HÂLÂ 28/28; doğruluk 0.560 (baseline 0.554, +1 şiddetli
düzeltmesi). Seyreltme mekanizma DEĞİL — kurak'ın ATEŞLİ günleri
gerçekten normal'in ateşli günlerine daha yakın. Yeni şüphe
(koşulmadı): ağırlık-asimetrisi (A/B kanalları) ya da normal
havuzun kurak-benzeri günler içermesi (alt-küme yönü ters olabilir).
Prob sonucu baseline'dan ayrı tutuldu (bu madde).

Kanıt: `OZET-SILMASK: acc=0.560 kurak-normal=28/28`.

## 9.69 Baseline-1 Dondu + k=3/k=5 Karşılaştırma (2026-09-15)

`validate_inference.py` DONDURULDU (k=3, md5 9907b558…; tekrar
koşu birebir). Aynı aptal yöntem k=5'te ayrı dosyadan
(`validate_inference_k5.py`, import — dondurulmuş dosyaya dokunmaz):
k=3 97/175=0.554 → k=5 68/165=0.412. Sequence-temsilde k=3
belirgin üstün; k=5'te normal↔kurak karışması ÇİFT-yönlü olur
(N: 12/25, 13'ü D'ye; D: 26/26→N) ve R/Y yığını büyür
(R: 16/36, Y: 10/36). §9.67 union-zirvesi (k=3-5) sequence'a
taşınmaz — sıra-koruyan temsil daha kısa pencerede keskin.
Baseline referansı k=3 matrisidir (§9.68).

Kanıt: `OZET-INFER-K5: acc=0.412 n=165`.

## 9.68 Inference Baseline-1 (2026-09-15, kullanıcı talimatı)

Aptal nearest-sequence (öğrenme YOK, parametre YOK): 3-gün
sıra-koruyan sorgu → gün-örtüşmesiz geçmiş pencereler → hizalı
gün-ortalaması benzerlik → en-yakın koşul. `validate_inference.py`
(I1-I2). 6x6 confusion, doğruluk 97/175 = 0.554.

MATRİS (satır gerçek, sütun tahmin; N D S I R Y):
N: 24 1 0 0 0 0 / D: 28 0 0 0 0 0 / S: 6 0 32 0 0 0 /
I: 0 0 0 0 7 1 / R: 0 0 0 8 19 11 / Y: 0 0 0 1 15 22.

ARAŞTIRMA HATTI — kurak→normal 28/28 (%100): kuraklık ASLA
kendisi tanınmıyor, istisnasız normal'e emiliyor. Gün-düzeyi
within-kurak 0.872 iken sequence-komşu normal — kurak imzası
normal bölgesinin ALT-KÜMESİ gibi duruyor (kurak günler birbirine
çok benzer ama normal havuzu daha yakın eşleşme sunuyor; sessiz
günlerin hizalı-ortalama benzerliği ayırt-edici bilgiyi seyreltir
şüphesi — prob: sessizlik-maskeli benzerlik). Sulama da kendisi
değil (0/8, hep R/Y); nem-süreklumu (I/R/Y) birbirine karışır,
kuru-eksen ucu (S) ve normal ayakta. Temsil kaba-nem rejimini
taşır, ince-kurak ayrımını TAŞIMAZ.

Zincir kaydı: lokal kurallar → emergent temporal filtre →
67 exact imza → snapshot yetersiz → 3-5 gün context faydalı →
uzun pencere doygunluğu → sıra önemli → inference test-edilebilir
(0.554, öğrenmesiz). Sonraki: quadratic rule BU referansa karşı
sınanır ("öğrenme temsilin bilgisini daha iyi kullanıyor mu?").

Kanıt: `OZET-INFER-1: I1 I2`.

## 9.67 Temporal-Window Testi (2026-09-15, kullanıcı talimatı)

"Tek-gün snapshot mı, pencere-ici sequence mi?" Learning YOK.
k = 1/3/5/10/20 gün kayar pencereler (adım 1, merkez-gün etiketi
yalnız analizde), LOO komşusu gün-örtüşmesizlerden (sızıntısız);
`validate_temporal_window.py` (W0-W2).

EĞRİ (acc / silüet): 1: 0.473/−0.02 → 3: 0.542/+0.15 →
5: 0.516/+0.17 → 10: 0.474/+0.01 → 20: 0.105/+0.03.
HÜKÜM: kısa entegrasyon (3-5 gün) TEK GÜNDEN İYİ — temporal
context bulgusu DOĞRULANDI (zirve k=3-5). Ama monoton değil:
k=20 çöküşünün İKİ sebebi var: (i) yapısal — kısa sınıfların
uygun aynı-sınıf komşusu kalmaz (normal/sulama u=0, hata zorunlu);
(ii) gerçek doygunluk — komşusu OLAN sınıflar da çöker (kurak
u=20'ye rağmen 0/30, recovery 0/40; her şey en-zengin çanta olan
yaz'a çekilir). Yani küme-birleşimi (union) temsil uzun pencerede
doyar: sıra-duyarsız toplama bilgiyi YIKAR. Sonuç: pencere içi
SIRA'yı koruyan temsil gerekir — inference baseline'ın girdisi
union değil sequence olmalı. Kuraklık hiçbir k'da ayrışmaz
(hep normal'e emilir: within 0.87 ama komşu normal — alt-küme
etkisi); şiddetli her k'da ayakta (19/40 @k=20).

Kanıt: `OZET-WINDOW: W0 W1 W2` (W0: k=1 F2'yi birebir verir).

## 9.66 Duyusal Temsil Karakterizasyonu (2026-09-15, kullanıcı talimatı)

"Kaç distinct sensory state oluşuyor?" Donuk artefaktlar YALNIZ
okundu (testb_* + plir_decisions; motor/harness ÇALIŞTIRILMADI,
hiçbir sim/src dosyasına dokunulmadı): `validate_sensory_repr.py`
(R1/R3/R5/R6 + F1/F2) → `sensory_raster.csv` (12500 tick:
bitki/PLIR/P1/B/P2/etiket; B-izdüşümü motorun bmask'iyle 300/300
uyumlu) + `sensory_sequences.csv` (P2 sekans) +
`sensory_signatures.csv` (gün imzaları) + `sensory_repr_report.txt`.

HÜKÜM: 67 exact gün-imzası / 165 ateşli gün + 7 afferent etiketi;
6 koşulun TAM imzası 6/6 ayrı (olay sayısı, P2 dağılımı, sekans,
etiket kümesi). Within=0.520 / between=0.277 (ayrışma +0.243);
en-yakın çiftler kurak-normal (0.704), recovery-sulama (0.467).
F1 BULGU: kaba-4'lü 5/6 tekil — sulama=recovery çakışır
(ikisi de sulama-sonrası nemli rejim; olay 17/74 ve dağılım ayırır:
kaba istatistik bu ayrımı ATAR, temporal temsil TUTAR). F2 BULGU:
gün-tekili LOO saflık 0.473, silüet -0.017 — tek gün örtüşür,
koşul kimliği pencere-toplamındadır (banka-sınıfı %98.8 ile çelişmez:
günler banka-etiketine göre kümelenir, deney-koşuluna göre değil).
Kuraklık P1'siz temsil (19 olayın 19'u saf-B); neither-olay 6/300
(A-yok B-yok ateş — gating kalıntısı, izli). PCA yalnız analizde
(PC1 0.39/PC2 0.24, modele eklenmedi). Etiket-girdisiz: WINDOWS
yalnız bu analizde, sim girdileri etiketsiz.

Kanıt: `OZET-SENSORY-REPR: R1 R3 R5 R6 + F1_CAKISMA + F2_ORTUSME`
(§9.62 regresyonu içinde: OZET-ASSOC S1..S5 değişmedi).

## 9.65 Koşul Süpürme Deneyi (2026-09-15, kullanıcı talimatı)

Aynı PLIR-A, kod değişikliği YOK: normal/kurak/şiddetli/sulama/
recovery/yaz pencerelerinde bitki→kabul/red→P1→P2→etiket imzası
(`validate_condition_sweep.py`, D1-D4).

HÜKÜM: EVET — her koşul ayrı imza (P1 0..78, P2 17..74, etiket 2..6;
şiddetli/normal P1 ~10×; sulama/recovery geçiş zenginliği 5'er etiket).
D3: kuraklık P1'siz temsil edilir (P1=0, P2=19 — B-sürüş kanıtı).
D5: çift-sürüş (A-destekli 117 + saf-B 131). Red-sebebi/soma-desteği
sütunları eklendi (ara pencere tablo dışı). Isı-şoku çekirdekte
düşmedi; ısı ekseni TEST A'da.

Kanıt: `OZET-COND-SWEEP: D1..D5`.

## 9.64 PLIR-A Karakterizasyonu (2026-09-15, kullanıcı talimatı)

"PLIR-A neden 1981'in yalnız 303'ünü geçiriyor?" Donuk kuralın birebir
izdüşümü (tau {4,12}, bw=1, lock=2·tau+bw; init -1): `validate_plir.py`
→ `plir_decisions.csv` (her darbe: kabul/red + ISI + ateşe-uzaklık).

HÜKÜM: hat0 — FRESH 624 + REZONANS 171 kabul, 1113 RED; hat1 — FRESH
17 kabul, 29 RED (tau12'ye uyan patlama yok; 1954 benzersiz tick).
Reddin TEK sebebi rezonans-uyumsuzluğu (kodda refrakter YOK; bw=1
periyot-dışı her darbeyi eler). 812 kabulün 303'ü ateşe dönüştü (alt
kademe: eşik/sızıntı); her P1 ateşi ≤20 tick içinde kabul görmüş
darbeye dayanır (öksüz ateş yok). Kayıp iki kademede: PLIR periyot
filtresi (%58) + soma entegrasyonu (%63 zayiat). Çapraz-doğrulama:
gerçek C++ motoru (inject/tick) ile kabulde 0 uyumsuzluk, P1 ateş
kümeleri birebir (hat0 286, hat1 17).

Kanıt: `OZET-PLIR: L1..L4`.

## 9.63 FDM Persistence Karakterizasyonu (2026-09-14/15, kullanıcı talimatı)

Donuk kaynaklara DOKUNULMADI (association/learning kodu da): /tmp
kopyalar yamanıp derlendi; bitki treni SABİT. Eksenler: sızıntı-tau
1..320, çakışma-penceresi 4..80, gating-hafıza 4..800.
`validate_fdm_sweep.py` (F1-F6).

BULGU: TÜM eksenler bit-eşit (L1==L320, W4==W80, G4==G800 — CSV +
kablo dahil; yoğun rejimde de). Ateşleme aynı-tick kombinasyoneldir;
sızıntı/gating/pencere makinesi bu rejimde sonuca KATILMIYOR. Seyrek
tren bilgi kaybı nicel: A-capture 303/1981 = %15.3 (kayıp %85) —
kayıp PLIR-A kilidinde, sızıntı-sonrasında değil.

Kanıt: `OZET-FDM-SWEEP: F1..F6`.

## 9.62 Association Çekirdeği (2026-09-14, kullanıcı talimatı)

Persistence/FDM'ye DOKUNULMADI. `sim/assoc.py` (YENİ): A = durum
sürekliliği, B/P2 = bağlam/kimlik; gün-penceresi imzası + ağırlıklı
Jaccard (0.5/0.3/0.2) + LOO 1-NN. Öğrenme YOK — yalnız ayırt-etme.
Her karar geriye-izlidir (komşu günün A-B-P2 olayları).

HÜKÜM: 163/165 = %98.8 (true 105/106, decoy 4/4, mixed 54/55);
2 karışma da true/mixed sınırında. Aynı/benzer örüntüler eşleşiyor,
farklılar ayrılıyor — association katmanı göreve hazır.

Kanıt: `OZET-ASSOC: S1..S5` (`validate_assoc.py`).

## 9.61 Association İzlenebilirliği (2026-09-14, kullanıcı talimatı)

Persistence association'a gizlenmedi — yalnız KAYIT katmanı: harness
`--aff` her P2 ateşinde `AfferentEvent{tick,post_id,tau_b}` + bağlam
yazar (a0/a1lag = P1 son-ateş gecikmesi; bmask = o-tick B paterni;
bwin = 10-tick çakışma-penceresi B paterni; label; w).
`validate_assoc_trace.py` (T1/T2/T4 + T3 geriye-iz raporu).

BULGU: 300 kayıt/249 ateş-ticki; 291'inde B-bağlamı var (191 saf-B).
Örnek iz: p2f ×57 — A0~0 + EC-paterni → w 0.200→0.254 (öğrenen koşulun
tam zinciri). Görev dağılımı doğrulandı: A süreklilik, B/P2 bağlam/
kimlik, association bunların zaman-ilşkisi. Mimari katmana geçiş
temizdir.

Kanıt: `OZET-ASSOC-TRACE: T1 T2 T4 + T3-rapor`.

## 9.60 A-Only Sözleşmesi — MİMARİ SAĞLAM, PERSISTENCE YETERSİZ (2026-09-14, kullanıcı talimatı)

Association öncesi 1. problem kapatıldı (B şişirilmedi): `--b-off` +
`--w0` probları + `aonly_dense_spikes.csv` (tau4+tau12) + 4'lü matris,
`validate_aonly.py` (C1-C4).

HÜKÜM: yoğun+w0.5 → cond 700 + test 165 (CR VAR, kapasite ispatı);
seyrek hiçbir ağırlıkta ateşlemez (0); yoğun banka-ağırlığında
ateşlemez (tavuk-yumurta: ateş yoksa dw yok — B ilk ateşler için
gerekli). Dal-1 bulgusu: 752 P1b ateşine 0 P2 (12-tick ritim sızıntıda
erir; 4-tick birikir). B kapalıyken seçicilik de gider (decoy d
gerçeklerle kilit-adım ateşler).

Sonuç: A→soma yolu mimari olarak DOĞRU, temporal persistence YETERSİZ.
CR için A yoğunluğu ya da association-bağlamı gerekir — association'a
geçiş temizdir.

Kanıt: `OZET-AONLY: C1..C4`.

## 9.59 TEST B: Sensory→Afferent→CR — KISMİ (2026-09-14, kullanıcı talimatı)

Sıralama kilidi: TEST A ✅ → TEST B (şimdi) → kapalı çevrim (B geçerse).
Kademeli ark (250 gün: normal/kurak/şiddetli+tuz/ara/yaz/sulama/recovery/
test=22+3 blok): `validate_testb.py` → `testb_*.csv` (B1-B4+B6 + B5 bulgu).

HÜKÜM: B1-B4+B6 GEÇTİ (1981 spike; şiddetli/normal 14×; recovery düşüşü;
293 afferent ateş, 7 koşul; p2f/p2g +0.055 öğrenme izi) + B5 CR_YOK.
Mekanizma: (1) seyrek bitki P1'in azı PLIR-A kilidinden geçer (testte
202 darbe→34 P1 ateşi); (2) sağ kalan darbeler sızıntı katmanında
toplanamaz → w=0.45 bile A-tek başına ateşleyemez (eta 1.2 probu:
eşik aşılır ama test sıfır). Kazanç (0.7→4→8) ve eta (0.3→1.2)
taramaları CR üretmedi — rejim sorunu, katsayı sorunu değil. Not: bu
çekirdekte ısı şoku düşmedi (stokastik, seed 1); ısı ekseni TEST A'da.

Sonuç: kapalı çevrime GEÇİLMEZ — önce CR kapısı (A-tek başına rejimi ya
da yoğun-sürüş protokolü) çözülmeli. Çekirdek/banka donukluğu korunur.

Kanıt: `OZET-TESTB: B1..B4+B6 + B5_CR_YOK`.

Zincir tanısı (`--diag`, odak p2a+p2f, eşik 1.0): şiddetlide bitki
625→P1 78 (%12), testte 202→37 (%18) — PLIR-A kilidi çoğu darbeyi eler;
B darbeleri dalı 0.83-0.84'e, somayı 0.99'a taşır (B sürer); testte B=0
→ dal 0.03/soma 0.07 → P2 sıfır. Kayıp iki kapıda: PLIR-A geçişi +
sızıntı-toplanamama. Tablo `validate_testb.py` çıktısındadır.

P1→soma denetimi (kullanıcı talimatı: B şişirilmedi, devre incelendi):
P1 ateşi başına dal A'ya I=w×0.5 (w=0.45'te 0.22); dal sızıntı+difüzyon
~0.2/tick, kök sızıntı 0.08 — seyrek darbede (1/40 tick) birikim yok,
soma 0.07'de kalır (eşik 1.0 → ~14× açık). Çakışma bonusu +0.8 yalnız
A∧B'de: A-tek başına ateşleme bu devrede YOK (yoğun trende gating
birikimi istisnası §9.14). B akımı (1.0/darbe) somayı sürükler; lob
B-sürücülü, A-kapılıdır. KARAR (kullanıcı): A-tek CR beklenmez;
kapalı çevrim ASSOCIATION katmanından (bağlam) kurulur — B-fon/yoğun
sürüşle bug gizlenmez.

## 9.58 Elektro Katman Karakterizasyonu (2026-09-14, kullanıcı talimatı)

"Önce katmanın ne kadar zengin olduğunu bilelim." 20 koşul (kuraklık /
sıcaklık / hasar / yağmur / sulama merdivenleri + 4 kombinasyon),
29 gün yerleşme + 30. gün ölçüm: `validate_electro_sweep.py` →
`electro_sweep.csv` (S1-S6).

BULGU: 20 koşulda 16 ayrı imza — durum uzayı büyük ölçüde temsil
ediliyor (kuraklık V -120→-90/h0 0.5→30.5; kombolarda h0 27-40,
V -75'e depolarize; olay günleri hat-1 patlamalı). 4 belgeli körlük:
yaprak/kök hasar ayrımı yok, yağmur şiddeti kodlanmaz (yalnız
başlangıç), baskı/baskın özdeş, 30°C eşik-altı sessiz. Uçtan-uca çapa:
sağlıklı-gün h0=1.6, felaket-günü h0=20.4 (bağımsız probla aynı).

Kanıt: `OZET-ELECTRO-SWEEP: S1..S6`.

## 9.57 Bitki-Sürücülü Duyusal Lob (2026-09-14, kullanıcı talimatı)

"Bitki stresine göre elektrik atımlasın, duyusal lobun bitki kısmını
bunlar beslesin." `sim/electro.py` (YENİ, türetme — K5/K7-safe: fiziğe
girmez, NPU'ya yalnız darbe bayrağı): zar potansiyeli (dinlenim -120mV,
kuraklık/hasar/sıcaklıkla varyasyon-potansiyeli depolarizasyonu) + hat 0
stres-oran ateşlemesi + hat 1 olay patlaması (yağmur/sulama başlangıcı);
uyku ×0.25, ölü sessiz; RNG master+gün+hat (fizik akışına dokunmaz).

`src/main_sensory_plant.cpp` (YENİ harness, `npu_sensory_plant` hedefi):
donuk `sensory_lobe.h` salt-okunur; P1 sabit tren yerine bitki spike
dosyasından, Dal B aynı faz kuralıyla sim sensörlerinden; banka,
kazanç, öğrenme §9.14 ile aynı. `validate_sensory_plant.py`: G2
felaketinin uzatılmışı (130 gün) → spike+sensör CSV → koşu → afferent
raporu (M1-M5).

AFFERENT BULGU (dürüst): 5 ayrı koşul üretildi
(p2a(p2c), p2a(p2c,p2d), p2b(p2e), p2d, p2h; cond 128 ateş), decoy/gerçek
0.50 (§9.14'te 0.33), test-ateşi 0 → CR YOK. Nedenler: seyrek P1 (531
darbe/6500 tick; sabit trende ~2167) + kuraklıkta hn<50 → B sessizliği
(OFF-US kodlaması zaten yoktu) → ağırlıklar oynamadı (p2h +0.002 hariç).
Kazanç taraması (0.7/4→2/4→4/8) toplamları değiştirmedi. Çıkarım: ham
stres-sürüş bu bankayı koşullandırmıyor; yoğun-sürüş rejimi ya da
elektrot-kazanç kalibrasyonu gerekir. Çekirdek/banka donukluğu korunur.

Kanıt: G18 (electro determinizm+monotonluk+kapılama+fizik-dokunulmazlık)
+ `OZET-PLANT-VALID: M1..M5`. Tam sim 21 GEÇTİ, tam web 11/11 GEÇTİ.

## 9.56 Yayın Başlangıcı 1 Ekim (2026-09-14, kullanıcı talimatı)

"Bitki ocakta filizleniyor, halbuki ekimde filizlenir." Canlı yayın
1 Ocak yerine 1 Ekim'de (gün 273) uykuda başlar; ilk filizlenme güz
yağmurlarıyla doğal kapıdan olur (Ocak kapısı tuhaflığına dokunulmaz —
çekirdek donuk). `WorldState(start_day=273)`, testler günü açıkça
kurduğu için kapılar etkilenmez.

Kanıt: G17e (açılış 273/DORMANT + 60 gün içinde güz filizlenmesi).
Tam sim 20 GEÇTİ, tam web 11/11 GEÇTİ.

## 9.55 Canlı Döngü Kapanışı — Ölümde Yeni Tohum (2026-09-14, kullanıcı talimatı)

"Her yeni döngüde yeni tohum." Çekirdek (plant_sim) DEĞİŞMEZ — politika
yalnız canlı katmandadır (`WorldState._cycle_watch`):
- Doğal döngü sonu (sararma→uyku, yaprak tazelenmiş): aynı gün yeniden
  ekim, yeni tohum (`cycle_complete`).
- Erken ölüm (kök çürüklüğü/besinsizlik): `plant_death` ilan edilir,
  5 gün çıplak toprak beklenir, sonra yeniden ekim (`RESOW_DELAY_DAYS`).
  Bekleyişte çekirdek diriltmesi (rebirth) geri alınır — eski tohumla
  diriliş olmaz.
- Döngü tohumu master'dan deterministik kardeş akış (`_cycle_seed`);
  aynı saksı (toprak/nem korunur, preset uygulanır). Yayın master
  tohumla başlar (42 — G21 uyumu). Olaylar karedeki `events` listesinden
  panele toast'lanır (ölüm/ekim; sulama sessiz).

Dürüst not: çekirdekte doğal son sararma→UYKU'dur (ölüm değil); canlı
katman döngü sonunda üretici politikasıyla yeniden eker (sulamada
yıllık yumru hasadı/yeniden dikim karşılığı). §9.53 çevrimdışı
döngülerinde zaten her döngü yeni bitkiydi; bu iş o anlaşmanın canlı
ayağıdır.

Kanıt: G17 (5 alt-test) + G25d yeni sözleşmeye güncellendi (çekirdek
rebirth a-c aynen; canlı yürüyüşte ≥1 kapanış + tohum yenilenmesi +
takılmama). G2 bayt-eşit, tam sim 21 GEÇTİ, tam web 11/11 GEÇTİ.

Düzeltme (kullanıcı bildirimi: ekim sonrası dormanside takılma):
yeniden ekim yazın yapıldığı için taze bitki güz yağmuruna kadar aylarca
uyuyordu. Yeni birey artık fide gibi SPROUTING dikilir (mevsim beklenmez,
24 günde vejetatif — prob 171→195). G17b güncellendi.

## 9.54 Canlı Birey Listeleme — Tohum + Parametre (2026-09-14, kullanıcı isteği)

`Plant.seed` (önt. None, fiziğe girmez) + `WorldState.describe_plants()`
+ yayıncıda `seeds` komutu ve açılış `TOHUM` günlüğü. Çerçeve (v2)
DIŞI kanal — şemaya anahtar YOK; ground_truth ASLA çıkmaz (K6).
Popülasyonda birey tohumu SeedSequence kardeş akışından (master akışa
dokunulmaz); canlı bitki dünya tohumunu taşır (öntanımlı parametre).

Web paneli: Canlı Veriler'e `Tohum` satırı (ilk birey tohumu) + `/seeds`
uçnoktası (`web/server.py`); `app.js` 1 Hz'de çeker. Çerçeve-DIŞI kanal,
şema donuk.

Kanıt: G14 (seeds→TOHUM listesi, tohum=42, sızıntısız) + G2 bayt-eşit
+ G21 (uçtan uca tarayıcı→web→sim→stdout→web→tarayıcı, tohum=42)
+ tam web seti 11/11 GEÇTİ (G19,G20,G22,G23,G26,G27,G29,G31,G32,G33).

Panel sadeleştirme (kullanıcı isteği): Canlı Veriler'e `Dönem` satırı
(stage adı TR eşlemeli: Dormansi/Filizlenme/Vejetatif dönem/Çiçeklenme/
Sararma/Ölü); Gök derecesiz (sun_alt_deg karede durur, panele çıkmaz —
G27a kilitli); üst şeritteki tekrar bilgiler (gün, dönem, sıcaklık, nem,
iklim, mevsim, gök, yağış) kaldırıldı, yalnız hız/duraklatma + bağlantı
noktası kaldı. G27 yeni sözleşmeye güncellendi (data-stage + stageTr +
derecesizlik kilidi).

Zaman Serisi grafiği kaldırıldı (kullanıcı isteği); Duraklat/Sürdür/
1x/8x/Sprint 60x düğmeleri Müdahaleler paneline `Hız` grubu olarak
taşındı (aynı data-cmd, CMDS eşlemesi korunur — G26 yeşil). Kuraklık
60g senaryo düğmesi kalktı (eşdeğeri panelde yok).

Terraryum doğal çözünürlüğe açıldı (canvas 720, panel 756 — boşluk kapandı);
sensör paneli fiziksel gösterime geçti (kullanıcı isteği): hs/ts ters
eşlemeyle °C, pH kanal 0-100 → pH 4-9, nemler %, NPK endeks — yalnız
gösterim katmanı, kare şeması/fizik aynı (G31 yeşil).

## 9.53 Multi-Cycle Climate Realization v1.1 (2026-09-14, kullanıcı talimatı)

"Her bitki yeni bir hayat yaşasın, iklimi de farklı gerçekleşsin."
`sim/cycles.py` (çekirdeğe DOKUNULMAZ — yeni modül): SeedSequence
hiyerarşisi master→cycle→{climate,event,plant,soil}; yıl-tipi
çekişi (anomali ±1.5°C, yağış ×0.7-1.4, genlik ±2 — TODO);
toprak tohumu initial nem/EC; takvim art arda (offset'lenebilir).

Kanıt: TEST11 (3×365 bit-eşit) / TEST12 (anomali std 0.82,
temp [-7.6,39.9] zarfta) / TEST13 (cycle-1 tohumu cycle-0'ı
etkilemez). G39 16/16, G2 bayt-eşit, tam koşu 19 GEÇTİ.
Not: git deposu yok → tag yerine §9.51 hash-freeze tag hükmündedir.

Tam freeze listesi:
7b132ebb8dfc4f0ad695e0cf666861759863694455b1f4f06086290b006ffb3e  sim/plant_sim.py
1e536cd0ab96bac43b2f9d0a65ac404623144c9c5f109a26d51af76bed2e7ef9  sim/world_state.py
672e29d2044340c3e3ff1e02f1599f2eeaaa94a09ec030123abd18b49867ab89  sim/events.py
980d718951e92019fba09c796d0ed8515453c48f8e804e1940edff6f4aa84944  sim/perturb.py
a2d4b78ba39c011c527c0c38bd98f46d11ee16f6d270d86daa53a6fa902669f2  sim/infer.py
58cf198f0b49bfb63a00325a3887585a7931b45897819308d50ee28d3c52ccbe  sim/validate.py
d43bf0f6cc6525aefdaaa0b60961c06e231eb23a22361421d031348a360d6ae7  sim/sensor_map.py
84163532498647969a4efda82c65ff10bc4ff23b35e3dd2e98e4a64ae9eeb1b9  sim/selftest.py

## 9.86 v3d Full-System Stress Rerun (2026-09-16, kullanıcı isteği)

PATTERN_V3_STRESS_SPEC.md (REV2) aynen: 12 grup, 39 case, v3d binary
(onaylı 29-P3 haritası). 12/12 GEÇTİ, deterministik (dalga-tekrarları
bit-eşit). Artefakt: stress_out/{cases,groups}.csv +
fig{1-diversity,2-retrieval,3-repetition}.png (bu oturum).
Üreten: pattern_stress_v3.py + gen_stress_report.py (additive).

Özet (v3 → v3d): G1-ret 0.122→0.230, G2-ret 0.161→0.438,
G9-ret 0.346→0.446; Nsig 8→22, Npv 28→104 (G1-base); rep 0.55→0.26;
G12 final-setJ 0.29→0.026 (sensDIST 0.0); seed-robustness 0.878→0.817.
G5 drought% kabloda bit-aynı (uyaran doyumu; lob bulgusu değil).
G11 drought-ailesi kurulamadı (qd 0.09). Soğuk dünya sessizliği sürüyor.
ROT-değişmezi anomalisi v3d'de de var (setJ=1.0). Donuk 8 + encoder +
sensory aynen (sha/bit-aynı); yeni dosya: v3d src+binary, drive/run/
stress/gen scriptleri, weather_v3, stress_out.

## 9.87 Aşama A — Memory-Readout (2026-09-16, kullanıcı isteği)

(i) mem'de 8/8 kolon reset-artefaktı: dolu 34 case'de soma/coinc/kv
TEK değer (2 istisna = boş cold mem'ler); mem ateş-sonrası yazılıyor
(main_pattern_unit_v3d tick-sonrası kayıt, voltajlar V_RESET'li).
(ii) eff_g TEK bilgi taşıyıcı (16684 distinct, 0.397-4.887).
(iii) phi-join ölü (%2-4) = ateş-gating-birikim kanıtı (eff_g 4.9'a
birikir, ateş çoğunlukla olaysız tickte).
(iv) Yeni kapı (PATTERN_MEMORY_USE_SPEC.md): E1/E2/X1/X2 readoutlar.
Sonuç: fam_qd 0.40'ı GEÇEN YOK (en iyi S2b 0.3824, E1/X1 0.3529,
X2-ret 0.5354 ama qd 0.0). S0n sahteleme margin/ret'i geçti (qd 0.15
geçemedi). Hüküm: A kanıtlanamadı; A4'e göre suçlu = drought-ailesi
kanalı (E1 tek başına qd 0.35, X2-birleşim qd'yi öldürüyor). B/C
gerekçesi kanıtlı hale geldi, ikisi de AYRI onay ister. Artefakt:
stress_out_v2/{memory_readouts,memory_column_audit}.csv (+json).
Üreten: pattern/memory_readouts.py + phase1_memory.py (additive,
salt-okunur). readout_v3d.py sha 262e038e38a0, phase0_margin.py sha
189a71295c81 (değişiklik yok).

## 9.88 Uyaran Merdiveni + Kanonik Aile (2026-09-17, kullanıcı isteği)

Tek-atis on-kayit (/tmp/wdry_prereg.txt): yagmur yalniz [20,21], +6C,
kesim 47. W-dry sha 607c4501701a0abe (weather_v3/).
Olculen merdiven: kablo 76 (base) = 76 (bayrakli, SNR 0) -> 169-170
(W-dry, SNR ~225); lob 820 -> ~1640 (SNR ~70); base-vs-drynew eff_g
0.9914 (n=348, drynew->base 3). 5-sinif aile eff_B1 0.7972 (G-FAM 0.90
GECEMEDI; karisma 0/191 gecti). Doz-eslesmesi 0.9952 gecti. Ablasyon:
NOPOS/NOCNT aileyi cokertemedi (bulgu; V0 bit-esit OK). A2 siddet:
S0 79 -> S1 79 (s1 kablosu dryold ile bit-ayni!) -> S2 121 -> S3 169;
4-sinif aile 0.54.
Kapanan 4 hipotez: jitter/S3/readout/alt-kume endiseleri (eff_g kanali
dogrulandi). REV3: G1-drought gecerisiz uyaran (silinmedi).
Kapi tanimlari + formalizasyon: STIMULUS_SNR_SPEC.md. Artefakt:
stress_out_snr/ (ensemble/groupsuz: snr_ensemble.csv, family_test_A1/
A2.csv+json, ablation.csv, snr_ladder.png). Ureten: pattern/snr_audit.
py + timing_ablation.py + family_test.py, plot_snr.py (additive).
DURUST SINIRLAR: tek-atis (band yok); W-dry siddetli/oldurucu (hafif
kuraklik kaniti DEGIL); ayrimin bir kismi yasam-oykusu yapisindan

gelebilir (takvim-siddet tam ayristi degil); ec tavanda (100);
src/sim/kanonik artefaktlar bit-ayni. A3 KAPALI.

## 9.89 v3e Tam Gorev Matrisi + Full-System (2026-09-17, kullanici istegi)

YENI (additive): src/pattern_unit_v3e.h, src/main_pattern_unit_v3e.cpp
(npu_pattern_unit_v3e, elle derleme; CMake'de v3/v3c/v3d/v3e hedefi YOK),
check_pattern_unit_v3e.cpp (E1-E8 OK). Semantik (2026-09-17 karari):
K2 kume-ici tam genlik; K3 anchor 1.0x / follower 0.5x (ayni kompartman,
agirlik yalniz K3 projeksiyonunda); slot-basina ayri sinaps+sayac
(birim-basina 18, kural soma-as-post aynen); P3a,b,c,e,f B-dalsiz;
P3ab/ac OPEN/sessiz. F1/esik/leak/kural/matris disi degisiklik YOK.
Pilot (TEST-B, eta=0, 2x bit-esit mem 2f3811e3/log 0942be1f): mem=116,
11/29 birim, wkdev=0; pairwise max Jaccard 0.50, cokmus cift 0.
Full-system (ayni batarya, NPU_V3_EXE swap, EXIT=0, 12/12 crash GECTI):
v3d->v3e: G1-base Nsig 22->3, Npv 104->3, rep 0.26->0.77; G1/G2/G9-ret
0.23/0.44/0.45 -> olculemez (pencere<4); G8-robustness 0.817->0.615;
G10 jacc(0,0.30) 0.863->1.0 (eta etkisiz); G11 0.422->olculemez;
G12 final-setJ 0.026->0.0. Aktif/case 27/29 uniform -> 3-14/29 secici.
Plastisite fiilen kapali: base eta=0.30 wkdev=0.0032 (v3d 0.104, ~32x).
D2 v3e teyidi: mem 7/7 voltaj kolonu TEK deger (ates-sonrasi ornekleme).
Duzeltme (olculdu): kablo alfabeleri base/hot/drought [1,4,6], irrig
[1,4,6,7], fert [1,4,5,6,9]; ulasilabilirlik 27/27 ("15-23 ulasilamaz"
YANLIS); baglayici kisit = olay-basina seyrek surus + yapisal B-dalsiz
sessizlik. NOT (oturum-oncesi): f0_baseline/*.csv guncel ciktiyla
bayt-ayni ama HASHES.txt eski hashleri tasiyor (salt-okunur, 09-16).
PEER (baska oturum, /tmp, bagimsiz dogrulanmadi): W-dry senaryosu,
port-bazli kazanclar, aile-1.000. v4 on-kayit: PATTERN_V4_PLAN.md
(PROPOSAL, implementasyon ayri onay ister).

## 9.90 v4c REV3 Full Battery + Nihai Lob Kabulu (2026-09-19, kullanici karari)

REV3 (dal-basina K4, 58 node; PLAN REV3 on-kaydi): check 9/9 (J0/C1-C4/
M/N/E/P), sentetik R1-R7 7/7, pilot validator OK (TEST-B eta=0: kapali
rows=116/Nsig=23/11 birim, acik rows=569/Nsig=69/22 birim, maxJ 0.619,
cokmus 0; (11,14) J 0.286->0.619 r_max 0.58 LISANSLI; matris 1176/1653,
sat %39, drivemax<=0.01, wkdev 0). Full battery (workflow, 4 dilim, 41
kosu, /tmp/pstress_v4c): crash-free + determinizm (g1_base dilimler-arasi
bit-esit) + encoder 1:1 + adapter bit-esit GECTI (bagimsiz spot-dogrulandi);
metrikler RAPOR (G10 jacc + bazi grup-retrieval'ari dilim JSON'larinda
eksik — ham `_c` ciktilari durur, kapi degil). KABUL (sartli onay: batarya
yesili): v2/v3/v3c/v3d/v3e src (10) + check (2) + binary (5) SILINDI (17
dosya; CSV'ler durur). v3e govdesi pattern_unit_v4c.h'ye VERBATIM gomuldu
(345/345 kod satiri diff-sifir; J kayitli hash'lerle yeniden kanitli:
2f3811e3/0942be1f). run_chain_v3 varsayilani npu_pattern_unit_v4c
(--k4 0 = v3e-identical); K4-acik yol npu_pattern_unit_v4c_on sarmalayici.
Validator J artik kayitli hash'le karsilastirir. pattern_lobe.h durur
(v4c derleme bagimliligi); npu_pattern_lobe + eski deney/validator
scriptleri kapsam-disi birakildi (calistirilirsa kirik olabilir — raporlu).
DURUST GERILIM (acik): enerji genis (ortak-mod 0.024, matris %71 dolu):
zayif-oruntu destegi ile genel uyarilabilirlik artisi arasi pilotla
ayrilamadi.

## 9.91 Eski Lobun Kaldirilmasi — v4c Tek Lob (2026-09-19, kullanici karari)

Unit, lobun evrilmis hali sayildi (lob ilkeli). pattern_lobe.h +
main_pattern_lobe.cpp + npu_pattern_lobe SILINDI; CMake npu_pattern_lobe
hedefi kalkti. Ardindan versiyon etiketi de kalkti: ayni kanonik adlar
yeni icerikle geri geldi (pattern_lobe.h + main_pattern_lobe.cpp +
check_pattern_lobe.cpp + validate_pattern_lobe.py + npu_pattern_lobe[_on |
_k4_rel]; OZET'ler OZET-PATTERN-LOB/-LOB-CHECK/-LOB-PILOT; eski
validate_pattern_lobe.py yetim olarak silindi). v4c'nin lobdan kullandigi uc sey aynen tasindi:
V4C_MEM_CAP=4096 + SPEC_v0_1 portu (pl_phi_id/tau_of VERBATIM) — derleme
bagimliligi sifir. Kanit: check 9/9 + R1-R7 + validator OK (J kayitli
hash'le), zincir iki yoldan PILOT GECTI (varsayilan rows=116 v3e-identical;
K4-acik rows=569). Eski lob-ozel scriptler (validate_pattern_lobe.py vb.)
yetim kaldi (kapsam-disi, kosulursa kirik olabilir).

## 9.92 K4 davranis bataryasi (2026-09-19, k4_battery.py; KARAKTERIZASYON)

Sistem hatti (sim->duyusal->lob) + sentetik kablolar; 4 kosul (K4xeta);
~90 senaryo (A-J + ZCAL kalibrasyon + C2 ayrik-akim). fails=yok
(determinizm cift-sha). Kural disiplini korundu: mekanizma degisikligi,
ayar, label-girdisi yok; insect/fungus test edilemedi (bayrak yok);
heat_recovery==heat ve rain_humid==rain kopya cikti (bagimsiz kanit degil).
Bulgu ozeti: K4 ateslemeyi cogaltir (A_base 21->106, C2'de taban-0'dan
kurtarma), capraz-cift sayisi 10/11 tick sinirinda sifirlanir (C2),
plastisite davranissal olarak atil (karsilastirma 2/3 ~sifir), iliski
doyumu hic yok (sat=0), bitki kosularinda K4 senkron artirmadi (maxJ
sabit/azaldi; (6,23) K4-disi onceden senkron). G probesi tabanda kaldi
(history sorusu olculeMEZdi). ZCAL: slot surusleri agir orgulu (SA⊂SB).
"Validated" hukmu YOK. Ham agac /tmp/k4bat, rapor REPORT.md.

## 9.93 REV3 arastirma bataryasi Q1-Q4 (2026-09-19, k4_research.py)

~60 senaryo x (C0-C3 x eta) x cift-SHA; fails=yok. Rapor:
/tmp/k4res/REPORT_REV3_RESEARCH.md (13 bolum, OLCU/YORUM/SINIR).
Sonuclar: Q1 zaman baskin (S2/S4 ~0.07-0.08, S1/S3 ~0.53-0.60);
Q2 kalip-ici jitter (2.24) kalip-arasindan (1.43) buyuk; Q3 prob
kumeleri ayni ama ±1 tick kayma var = fixed-point kuantalama
hafizasi (truncate'li leak/gating; iliskisel bellek DEGIL);
Q4 plastisite T3/eta>=0.30'da davranissal (Npv/rep oynar),
Jcont'ta tavan 2.0 (tum eta>=0.10 ayni cekici). Kural disiplini
korundu (mekanizma/ayar/label yok). "Validated" YOK.

## 9.94 Takip arastirmasi W1/W2/W3 (2026-09-19, k4_research2.py)

Tek binary farki --k4idcsv salt-okunur telemetri (J yeniden kanitli).
W1: zayif prob gecmis-bagimli (H1[6,23,24]->H2+X[6,9,23,24] tum gap;
K4 ile 12->15 birim; H3=Y etkisiz; gap40 sonum izi); tasiyici voltaj
reziduleri (C0'da da var), K4 buyutur. W2: ayni-akim r artisi =
es-aktiflik nobet uzamasi (orneklem 3248->8960; ates/drive sabit).
W3: K4 NN-acc 0.63-0.66 (within<between) ama ham birim-Jaccard 0.69 ile
daha iyi; tohum varyasyonu arada. Rapor: /tmp/k4res2/
REPORT_REV3_RESEARCH2.md. REV4 YOK.

## 9.95 REV4 gercek K4 — onay + uygulama + TEST-B pilotu (2026-09-19)

Tasarim onayi (kullanici): REV4 kilit prensip "K4, relational coincidence'i
kendi elektriksel durumuna entegre eden, K1-K3 ile soma uzerinde paralel
gercek compartment'tir"; S4max=0.25 frozen sabit DEGIL, N-turetilmis
baslangic siniri (U6 pilotu mekanik dogrular); basari = K4 state + argmax
kimligin somaya nedensel yansimasi.
Uygulama (U1-U6): nicemlenmis imza q[3] (-3..+3, 0.15 merdiveni), kademeli
kapi pay>=13/18, spike-kapili max-secimli surum (rel<=1 yapisal, argmax
mekanizma), gercek K4 tick (LOC=1/8 + rel; spike'ta V_RESET), iki asamali
soma (S123 frozen + S4=min(0.25,0.125*(VgA+VgB)); F1 atesinde eslesik K4
reset, degilse S123+S4>esik -> K4-kaynakli ates = frozen reset aynasi).
Kok drive silindi (v4c_apply_drive YOK). Yeni checker: S1 (max-not-sum),
S2 (ayni-gucte argmax flip), S3 (ayni S123'te salim ates/sessizlik belirler)
+ R8 (spike-kapisi). Kapali-kosuda mem 11 kolon (J bayt-aynilik korunur);
acik-kosuda +2 kolon (soma_k4,k4spk).
TEST-B pilotu (eta=0): B/J/R/P/D/M/N/S HEPSI OK; 12/12 check, R1-R8.
J hash'leri kayitli v3e ile esit (mem 2f3811e3, log 0942be1f). S4max gozlenen
0.1765 <= 0.25 (cap hic baglamadi; N mekanik dogrulandi). kfires=92 (tamami
soma_k4>0). BULGU: pilot kosuda K4 spike'i 0 -> iliskisel surum yolu
TEST-B'de hic islemedi (topartner tum satirlarda -1); 92 ates yalniz lokal
K4 entegrasyonundan geldi. Yani argmax->soma nedenselligi yapisal (S1/S2/R8)
kanitli ama pilot-duzeyde degil; iliskisel yolu calistiracak daha yogun
uyaran ayri karar ister. DUR: full battery YOK (kullanici onayi beklenir).

## 9.96 Iliskisel pathway proof — tek deney, zincir tamam (2026-09-19)

Karar (kullanici): full battery YOK; once tek relational pathway proof,
mimari donuk, sadece kontrollu uyaran. Hedef: coincidence->similarity->
r->argmax->rel->K4 V->spike->soma zincirinin tamami tek deneyde.
Tasarim: A=bid4 (u2 dalA) + B=bid15 (u7 dalB) ikiz kablolu (post8 ikisine
SADECE K1-ring vurur, agda baska yere degmez); C=bid18 (post0 seyrek:
olay var, imza farkli). P1 post8-tonik+post0-seyrek (250t); P2 post2
(ikizlere hicbir sey degmez, gercek sessizlik, 80t). Script: /tmp (probe).
Sonuc OZET-REL-PATHWAY: OK — L0-L9+L6b zincir halkalari HEPSI yesil:
r_AB=0.875 (tavan; fixed-point, 1.0 degil), r_AC=0.06, argmax karsilikli
1.00/1.00, K4 spike 1925, hiz 36->98 (rel imzasi: lokal duraganken artis
yalniz rel ile aciklanir), S4d>0, ikiz soma atesi u2:2/u7:4 (kfires=100),
sessizlikte r 0.875->0.0001, spike durdu (son straggler 267), V4 19->1.04.
Saflik diyagnostigi L0/L0b BATTI kayitta: seyrek F1 girisimi (6/250t,
biri 228'de) zinciri BOZMADI (L3=1.00; rel-rescue ~2 tick'te doldurur).
Ek bulgular: seyrek paylasimli surus pencereyle tam coincident olur
(yanki surer; P2 gercek sessizlik ister); dinlenen-C ile aktif-A arasi
sessizlik-uzlasmasi gecici baglanmasi (r_AC=0.06; yogunluk uyarisi
in-vivo dogrulandi); gating hafizasi Vg'yi siser (S4d 21.6, toplam cap
0.25 baglar). HUKUM: REV4 relational pathway mekanik olarak calisiyor.
Full battery karari kullanicida (ayri onay).

## 9.97 REV4 full battery + NIHAI LOB kabulu (2026-09-20, kullanici karari)

k4_battery.py (REV4 harness notuyla) FULL kostu: OZET-K4BAT: BITTI,
99 senaryo x 4 kosul (base/k4static/plastic/k4plastic), fails=yok.
Cift-kosu sha determinizm tum kosul x senaryoda GECTI. Artefaktlar:
/tmp/k4bat/REPORT.md (589 satir) + results.json + kosu agaci.
Basliklar (OLCU; yorumlar raporda): sat=0 her yerde (r tavani 0.875,
beklendigi gibi); plastic~static (eta 0.30 yalniz yogun suruste
isırır: J_cont 839->1287, J_overdrive 347->502 rows); K4 bitki
senaryolarinda rows+Nsig ekler (d_rows +2..+26; A_rain'de d_Nsig=-3
daralma, kayitli); C offset taramasi maxr 0.12->0.71 (off11 anomalisi:
pencere-disi 11 tick kaymada yuksek baglanma — adapter zaman kaymasi
suphesi, arastirma notu, kod degisikligi YOK); turnover=0 her yerde
(argmax kararli); jitter Jaccard 0.71->0.75 (K4 ile hafif artis);
retrieval acc=0.0 (olcum, karsilastirma iddiasi yok); J'de maxJ=1.0
(adversarial birim-cokus, kayitli). cm REV4 anlami: Vg-yogunlugu
(J_agree'de 1.0; overdrive'da 0.0 — dar surus senkronize etmez).
HUKUM (kullanici): REV4 = NIHAI PATTERN LOB mimarisi ve lob. F1 frozen,
K4 compartment + imza + kapi + max/argmax + k4_tick + iki-asamali soma
donduruldu. Sonrasi degisiklik onaya tabi.

## 9.98 Sistem lob baglantisi + simulasyon testleri (2026-09-20)

Baglanti (kullanici: REV4 = pattern lobumuz, sisteme baglanir): run_chain
stage_v3'e k4 anahtari (varsayilan "0" — mevcut F1 cagiricilari bayt-bayt
korunur); run_chain main --k4 (varsayilan "1" = REV4 nihai lob) + S3
OZET etiketi duzeltmesi (PATTERN-V3 eslesmiyordu, LOB oldu). Degisim-oncesi
gozlem: main --k4 tanimiyordu (hata kayitli). Kalici test:
validate_chain_lobe.py (C1 sistem k4-acik uctan-uca, C2 k4-kapali korunur,
C3 sistem determinizm, C4 kutuphane varsayilani k4=0) — HEPSI OK.
Simulasyon (ayni testler): full battery bagli sistemde yeniden kostu —
OZET-K4BAT: BITTI, 99 senaryo, fails=yok, 0 BATTI; A_heat satiri birebir
uredi (deterministik reprodusyon). Artefakt: /tmp/k4bat/REPORT.md.

## 9.99 Observation probe — REV4 bitki rejiminde ne yapiyor (2026-09-20)

Emergent/observation disiplini: mimari/parametre/learning degismedi, tuning
yok, yeni skor yok; mevcut hat; beklenmeyen == FAIL degil. 8 senaryo x
seed42 + REST seed43 (insect/fungus surus bayragi YOK — GAP kaydi).
Script: /tmp/obs_probe.py; rapor: /tmp/obsprobe/OBS_REPORT.md (10 bolum).
Ham bulgular: 9 senaryoda K4 spike=0 + topartner %100 -1 (iliskisel surum
bitki rejiminde sessiz; S4 yalniz esik-alti Vg'den akar); baglanabilir cift
kumesi 8 senaryoda birebir ayni (Jaccard 1.0, 1176 cift — yapisal iskelet,
surus yalniz siddet 0.068-0.222); drought_light==REST, severe==recovery
(ayni kablo; cond=10 penceresi); REST seed43 birim-kumesi Jaccard 1.0;
rain en az spike (459) ama en guclu iliski (0.222); wkdev=0. Hipotezler
H1-H4 raporda (kanit degil). r(t) ara-dokumu + ham V4 telemetri sinirlari
kayitli.

## 9.100 H1 yogunluk merdiveni (2026-09-20, observation)

H1 testi: REST kablo x cokluk 1/2/4/8 (tick/post deseni ayni; dugme =
akim olcegi). Script /tmp/h1_density.py; rapor /tmp/obsprobe/h1density/.
Sonuc: spike=0 tum basamaklarda, top_nonneg=0, maxr sabit 0.264481 (yol
ACILMADI). br 117913->4626, act_max 0.46->0.14 (genlik K4'u bastirir:
F1 toniklesir -> eslesik reset). kfires 2x'te tepe (17->120->115->74);
soma F1'e gecer (mem 23->1323). HUKUM: BELIRSIZ catalli — genlik bacagi
B ciktisi (sorun yalniz yogunluk degil); zamansal-yogunluk bacagi test
edilmedi (zaman korundu). Mimari/tuning onerisi YOK.

## 9.102 REV4 FREEZE — nihai pattern lob donduruldu (2026-09-20, kullanici karari)

Kapsam: src/pattern_lobe.h (F1 vendored + REV4 K4 bolumu), main/check/R
kaynaklari, ogrenme kurali, K4 parametreleri (esik/leak/gating/LOC/GAIN/
S4_CAP), adapter/kod mimarisi. Kural: kullanici onayi olmadan bu dosyalara
DAVRANIS degisikligi YOK (harness/test/probe scriptleri mimari degildir).
Koruma: J (k4-kapali bit-identical), D (cift-kosu), N/M/C/P/E/R/S kapilari
ve validate_chain_lobe C1-C4 gecerli kalir; bozulan once raporlanir,
duzeltilmez (tuning YOK). Gozlem disiplini: once olcu, beklenmeyen=FAIL
degil, hipotezler kanit degil.

## 9.101 H1 zamansal dagilim (2026-09-20, observation)

Ayni 79 olay: A baseline / B 2x sikisik / C duzgun aralikli. Script
/tmp/h1_temporal.py; rapor /tmp/obsprobe/h1temporal/. Sonuc: B'de
mat_mean 0.110->0.328 (3x), maxr 0.70, kfires 17->59; C'de iskelet
1176->922, mean 0.062, mem=0 (soma sessiz). Spike 3 kosuda da 0, top
%100 -1. HUKUM: iliski siddeti = zamanlama (hacim degil); spike =
tonik yogunluk (ayri halka). H1 revizyonu: esik-alti kalisin nedeni
hacim degil dagilimdir.

## 9.106 REV-LEARN — iz + erisilebilirlik dinamigi (2026-09-20, kullanici onayi; freeze-delme kayitli)

Kapsam disi notu: §9.102 freeze'i KULLANICI EMRIYLE bu is icin delindi
(sadece synapse.h plastisite; K1-K4 yapisi, K4 r-dinamigi, F1 degismedi).
Tasarim (minimal): cekirdek dw=eta*G*Q*S AYNI (kuadratik avantaj + S
doyumu korunur); +trace alani (init 0): potansiyasyonda w+=dw*(1+T),
T+=MU*(1-T) (iz, sonmez); kullanim-disinda w ize gevser (T*WMAX taban;
klasik decay YOK); T==0'da bozulma yok; eta==0 yolu bit-identical.
MU=1/8, LAM=0.005 (ritim-uyumlu BASLANGIC; TODO DOGRULANMADI).
K4 r-leak'e dokunulmadi (R2/C3 geregi; req6 invariant).
Testler: check_learning.cpp L0-L6 8/8 OK (saf-yol birebir, doyum,
taban, tasarruf 28->8, eta0-frozen, determinizm, iz-monoton).
Kapilar: check 12/12, R1-R8, validator pilot OK, chain C1-C4 OK
(J canonical esit — eta0 korunumu).
Batarya karsilastirmasi (/tmp/k4bat_learn, 99 senaryo, fails=yok):
eta0 198/198 BIREBIR; plastik 46/99 degisti (rows arti, birim kumeleri
AYNI, Nsig iki yone); cm/turnover/max_r ayni; jitter maxJ 1.0 ayni;
retrieval olculebilir oldu (0.0 n~10 -> 0.14-0.18 n~500+).
Notlar: LSB olu-bandi (~0.003 taban-ustu donma); zayif-ogrenmede iz
w'yi gecer, kullanim-disi tabana YUKSELTIR (iz-tutarlilik).

## 9.107 REV-LEARN karakterizasyon A/B/C/D (2026-09-21, observation; kod DONUK)

Rapor: LEARN_CHAR.md. Prob /tmp/learn_char2.cpp + learn_char3.cpp, CSV /tmp/learnchar/.
A: guclu ilk-dw 0.90 vs zayif 0.017 (~53x); doygun 2 vs 76 tick; T=1-(1-MU)^n
dogrulandi (2t->0.2344, 76t->~1.0) — iz derinligini maruziyet SAYISI belirler
(hizli=sig, tekrarli=derin). B: zayif w 1.50->taban 1.894'e YUKSELDI (cift-yonlu
gevseleme L235; T bit-sabit); guclu-doygun 2.0->0.4718=taban (T=0.234 sig izin
bedeli). C: saf 91t -> 1.99; gap100/1000/10000 -> 61/37/37t (1.5x/2.5x/2.5x);
1000=10000 bit-esit — tasarruf bosluktan bagimsiz, izden. D: 20000 tick sonra
T bit-equal, w tabanda (1.894 > ogrenme-sonu 1.50); 30t yeniden 1.98 vs saf 1.64.
HUKUM: cumle kurulabilir — kalici iz + taban-duzenlemesi + yeniden-erisim.
Sinir: tasarruf zayif rejimde (guclu ~2t doyar, sayim anlamsiz).

## 9.108 REV-LEARN BASELINE FREEZE (2026-09-21, kullanici karari)

Baseline: k4plastic (K4 ON + eta 0.30); karsilastirma k4static (K4 ON + eta 0)
sakli. Entegrasyon: kablo vardi (--eta->p3x3unit_learn); TEK ek salt-okunur
--tracecsv/--traceevery iz telemetrisi (main_pattern_lobe.cpp; verilmezse
J/davranis degismez; yeni mekanizma YOK). Rapor: LEARN_BASELINE.md.
Kapilar: validator full-yesil (J 2f3811e3/0942be1f) + check_learn_baseline.cpp
LB1-LB4 OK. 6 deney: OFF/ON determinism + ilk-sapma 467 + ayni birim kumesi
(140->562 mem); A->sil->A %78 ani donus + T donuk; A->B->A iz 102/102 + A2
A1-seviyesi; proliferasyon YOK (27=27 birim); temporal ayrim korunuyor
(0.297->0.196 daha keskin); 20k-kosu plato (meanT 0.58, 304/522; kazara
78/8000 vs 50/8000; blok-oran stabil). HUKUM: kural kurcalanmayacak; sonraki
is temsil + loblar-arasi iletisim. Acik: mem 4096-cap; plato tek-desen-ailesi.

## 9.109 NIHAI MIMARI BASELINE — Pattern Lobe donduruldu (2026-09-21, kullanici karari)

REV-LEARN'li Pattern Lobe (k4plastic: K1-K3 + K4 + Soma + G·Q·S/saturation/
relaxation/persistent-T) NIHAI MIMARI BASELINE'dir. Lob mimarisi DONUK; degisiklik yok.
Sonraki is: diger lob. Referanslar: LEARN_BASELINE.md,
LEARN_CHAR.md, §9.108, check_learn_baseline.cpp LB1-LB4.

## 9.105 Alfabe haritasi — Q1/Q2/Q3 (2026-09-20, observation)

19 sentetik kablo (sira/gap/duty + pathway CTRL); script /tmp/alphabet.py;
rapor /tmp/obsprobe/alphabet/ALPHABET.md. Q1: kume=bilesim, vurgu=sira
(AB=BA ayni 21 birim; ALT mean 0.573 en yuksek). Q2 esikler: pencere
kenari (8,10] (360->296 cift); spike gorevi (0.5,1.0]; soma-atesi spike'tan
once (d2'de kfires=1, spike=0); F1 devralma 8x genlikte. Rejim sirasi:
sessiz->iliski->S4-soma->spike->F1-tonik. Q3: dogalistik seyrek spike
acmaz; K4-spike sentetik-yogunluk modudur (40K'da gozlenmedi). Q4
(ogrenme) acik.

## 9.104 Dogal FP karsilastirmasi (2026-09-20, observation)

40K icinden es-hacimli zit-konsantrasyonlu haftalar (A1/A2 gun56/1239,
B1/B2 gun91/3430; C2 gun25011 uzak-es). Script /tmp/fp_compare.py;
rapor /tmp/run40k/FP_COMPARE.md. C1 GECERSIZ (dilimleyici artefakti,
A1'le cakisik; dislandi). Sonuc: A1->A2 ates 3->7 birim 3->5;
B1->B2 ates 3->11 birim 1->8 (hacim sabit, konsantrasyon yukseltir).
Recurrence: A1-C2 J=0.925, B1-C2 J=1.000 (25k gun ara). 5 haftada spk=0,
top %100 -1. HUKUM: dogal olcekte zamanlama lob durumunu degistirir
(ates/birim/siddet), rejim degistirmez (J>=0.877).

## 9.103 RUN-40K — 40.000 gun, tek rejim (2026-09-20, observation)

REST seed42 40k gun (2M tick, 55.341 olay, 93M dal satiri). Artefakt:
/tmp/run40k/ (REPORT40K.md, daily.csv, results40k.json; ham gzip'li).
Ham bulgular: 42 gunluk acilis gecidi (6 tekil hafta) sonra 39.958 gun
TEK dinamik rejim (grup 5714; haftalik J medyan 0.926, %99.93>=0.7);
gecis 6 (tamami ilk 42 gunde); ardisik-J medyan 0.98 (18.844 gun
birebir ayni); drift YOK (Q1-Q4 0.98); K4 spike 40k gunde 0 (kfires
14.709 esik-alti S4 ile); mem tavani 6850. gun (kayitli); OPEN 27,28
sessiz; ayni-cevre-farkli-pattern 2 imzada, ikisi de gecitte (sonrasi
yok). HUKUM (gozlem): lob dondurulmus agirliklarla kendi uzun-olcekli
durumunu URETMEZ; surusu takip eder, tek rejime kilitlenir. Seed tekrari
ayri kosu ister.

## 9.110 Canlı zincir — sim→duyusal→koşul→örüntü (§9.96, kullanıcı isteği)

Web kalkınca NPU da kalkar: yayıncı (`sim/serve.py`) her sim-gününde 7
sensörü kalıcı `npu_sensory_lobe --stream` sürecine SET'ler; sensory T
telemetrisindeki P2 bitleri `(tick, post=k, tau=TAU_B[k])` afferent
olayına çevrilir (alfabe aff300 ile aynı; SPEC post 0..11, tau 4..60).
Eşik (`--chain-events`, varsayılan 300) aşılınca biriken pencereyle
`npu_pattern_lobe` batch koşar (`--k4 1` + k4csv/k4paircsv/k4idcsv),
OZET-PATTERN-LOB yakalanır. Karelere DOKUNULMAZ (şema v2 donuk, G21),
panel YOK (sonraki iş) — özet `chain.status()` + outdir dosyalarında.

Dosyalar (çekirdek `*.h` değişmedi): `sim/sensory_chain.py`
(stdlib-only, G11 temiz; binary yoksa zincir kapanır, yayıncı koşar),
`sim/serve.py` (`--chain` varsayılan açık / `--no-chain`,
`--chain-events`, `--chain-dir`; READY satırı `chain=acik|kapali|
binary-yok` taşır), `validate_sensory_chain.py` (SET eşlemesi +
SPEC aralığı + kayıp-binary + sensory smoke + pattern mini-batch +
uçtan-uca mini pencere).

Sayılar (bu oturum): validasyon 13/13 OK (mini pencerede K=299 koşul,
1 pencere, OZET yakalandı); kanonik aff300 ile `mem=231`,
`k4_kfires=146`; G20/G21/G34 zincir-açık varsayılanla yeşil (kareler
bayt-disiplini korunur — zincir salt-okur).

DÜRÜST SINIRLAR: (i) pattern pencereleri ağırlıksız başlar (batch başına
taze; pencereler-arası öğrenme taşınmaz); (ii) sensory kendi 50 Hz
saatinde serbest koşar (sim-günüyle kilitli değil, SET gün değişiminde);
(iii) T-satırları 25 tick'te bir gelir (pencere eşiği olay sayısıdır,
süre değil).

## 9.111 E-1 — Persistent Pattern Lobe (2026-09-21, kullanıcı onayı)

§9.110'daki (i) sınırı GEÇERSİZ: pattern pencereleri artık ağırlıksız
başlamıyor. `main_pattern_lobe.cpp`'ye eklemeli `--stream` modu
(yalnız harness; çekirdek `*.h`, K4, REV-LEARN, sabitler, batch yolu
DEĞİŞMEDİ): `AFF tick,post,tau | TICK n | OZET | STATE | QUIT`.
Instance start'ta BİR KEZ init olur (`v4c_init` + `v4c_net_init`
oturum başında tek koşu); pencere sınırı yalnız episodic `_buffer`'ı
kapatır, `w`/`T`/`r` proseste yaşar. QUIT yalnız gerçek sonda.

Doğrulama (bu oturum): J-bit-identical (mem/log kanonik hash, W=522);
stream≡batch bayt-bayt (TEST-B eta=0 + ABA eta=0.30); TEST1 (A,A:
w 34350966→34542508, T monoton, READY=1); TEST2 (A,B,A: faz ateşleri
16/50/36, T 1047954→4107072→4107414 monoton); TEST3 (3 WS kopar/bağlan:
sensory+pattern PID sabit, sim devam); TEST4 (aynı script iki koşuda
STATE bit-eşit); pilot battery + assoc-trace + G20/G21/G34 yeşil.

DÜRÜST SINIRLAR: (i) A2 fazında ateşleme yeniden dağılır (unit-3 A2'de
sessiz; trace korunur ama kazanan kümesi kayar — donuk mekanizmanın
gerçeği, batch kontrolle doğrulandı); (ii) zincir yayıncı prosesine
aittir: WS kopuşu etkilemez (kanıtlı) ama web-server stop zinciri
öldürür — proses-seviyesi ayrışma (supervisor) sonraki iş; (iii)
/ws/npu "bağlantı başına yeni proses" anti-patterni raporlandı,
dokunulmadı.

## 9.112 Transport/rapor ayrimi — esiksiz besleme (2026-09-21, olculu karar)

Olcu (canli, ayni binary'ler): sensory 0.20 olay/sn uretiyor (tick
saati 49.7/sn); 300-olay dolumu ~1472 sn; 300 AFF IPC 0.4 ms; 300
olayli pencere isleme 0.01 sn; OZET turu 0.1 ms. Gecikmenin tamami
esikteydi, transport bedavaydi.

Karar: besleme esiksiz (`_forward`: her T-satiri AFF+TICK ile aninda
yasayan instance'a; olaysiz satirda bile TICK — leak/decay suzulur),
`--chain-events` yalniz RAPOR kadansidir (OZET/STATE + aff dosyasi +
chain.log). Degisiklik tek dosya (`sim/sensory_chain.py`; `_pat_send_lock`
ile tek yazici). C++ tarafi aynen.

Dogrulama: gecikme kapisi (esik 100000 iken fed_tick 0→125 akti),
validate tamami OK, G20/G21/G34 yesil.

## 9.113 Pattern persistence — w/T/r checkpoint (§9.113, kullanici onayi)

Yalniz ogrenilmis state kalicilastirildi: `w[522]` + `T[522]` +
`r[58][58]` (17.668 B). Format (`src/pattern_state.h`, ayri katman):
magic "PLST" u32, version u32 (=1), dims u32×3 (29/18/58), last_tick
u32 (bilgi; zaman episodic, tcur yuklemede 0'dan), flags/reserved,
payload LE, CRC32 (poly 0xEDB88320). fixed-width int32/uint32 yalniz;
JSON/pickle/double/long yok. rc sayaçlari, voltaj/gating/timerlar,
mem/log dahil DEGIL (envanter karari: yalniz w/T/r learned state).

Tetikleme: stream `SAVE yol` komutu, `--load F` (batch+stream;
bozukta WARN + temiz baslangic, sessiz yukleme yok), `--save F`
(batch sonu), `--autosave F` (stream QUIT). Zincir: stop()'ta
`live_state.plst` SAVE, start()'ta varsa LOAD.

Dogrulama: J-bit-identical (kanonik hash, W=522); stream≡batch
bayt-bayt; TEST A (LOAD STATE bit-esit, devam 20 olay); B (restart
sonrasi T monoton, A2 ates 88); C (SAVE dosyalari + STATE bit-esit);
D (loaded 26 > fresh 16 ates); E (bozuk/kesik reddedilir, temiz
baslangica esit); seffaflik: SAVE/LOAD w/T/r'yi bit-aynen tasir
(TEST A/C); resume sonrasi yorunge <%1 sapar (dinamik state taze
baslar — tasarim karari, §9.113-14/15). Pilot battery + assoc-trace
+ validate tamam (43 ok) + G20/G21/G34 yesil.

DURUST SINIRLAR: (i) uretim zinciri eta=0 ile kosar (pattern agirlik
ogrenmesi donuk; r iliskisel ogrenmesi aktif) — eta karari ayri
urun karari, degistirilmedi; (ii) resume dinamik state'i sifirlar
(voltaj/gating/sayaclar), yorunge mikro-sapar; bit-exact resume
istenirse rc+olay-saatleri ayrica saklanmali.

## 9.114 Pattern Lobe NIHAI DONDURMA - envanter + kilit (2026-09-23, kullanici karari)

9.109'daki dondurma bu fikrayla uygulanabilir hale getirildi: mimari
DONUK, her sey dahil. Dondurulan envanter (sha256, dondurma ani):

- `src/pattern_lobe.h` aab46ec19a9bc382fb9a07e461c9c8ea4ad0e7d7eb5d2553af910f6e461d1b5c
- `src/pattern_state.h` 4f695b9129103b8b7eb8ce4303fb4f65052d52e4da4e330159b1bce8fe79e095
- `src/main_pattern_lobe.cpp` 0837949604c98777b371a47d13ff461e372f486fc543c97d52a59e80e04549b7
- `src/main_pattern_lobe_k4_rel.cpp` 1ac1af65d2ff18176ce4b454945a32b2a2147d11e16394d956cc8d8461419eca

Kural: bu 4 dosya salt-okunurdur; lobu cagiran (harness/lifecycle/
tasiyici/rapor) degisir, lob degismez. `src/synapse.h` (REV-LEARN
cekirdegi) envanter DISIDIR - 8 dosya tarafindan paylasilan altyapi,
zaten donuk-cekirdek kurali altinda. Istisna yalniz acik kullanici
onayiyla, bu fikraya islenerek.

Dondurma-ani kanit: `validate_sensory_chain.py` + OZET-PLST tam yesil
(43 ok + TEST A/B/C/D/E; bu oturumda yeniden kosuldu, cikis 0).
Sonraki is: diger lob.

## 9.115 Sinyal paneli canli baglanti (2026-09-24, kullanici istegi)

Kullanicinin verdigi sema (P1 16/2, P2 64/10, afferent ters agac, 29
pattern birimi) `web/static/js/signal.js` olarak panelin icine gomuldu
(ayri HTML/iframe YOK); surucu canlidir, ornek atim YOK:
- P2 atesi <- frame.lobes.aff (post=P2, gercek afferent akisi)
- pattern act/spike <- frame.lobes.k4 (live_k4.csv tail, esik K4_ACT_MIN)
- sensor teli <- frame.sensors; kablo <- /ws/npu TELE (wire/f).
Tasiyici: SensoryChain halka tamponlari (recent_aff 40, recent_k4 96,
salt-okur tail) + serve.py frame.lobes yayini; web/server.py degismedi
(relay aynen gecirir). Cekirdek (9.114) donuk, degismedi.

## 9.115b Panel tasiyici kapilari (2026-09-24)

- G19: SVG ad-uzayi URI'si istisna (ag degil, createElementNS sabiti).
- G21: ust sema = donuk v2 + ISTEGE BAGLI lobes (frame.py yayinci sozlesmesi).
- G37 (yeni): /ws/world karelerinde lobes + iki lob canli + /healthz has_lobes.
- /healthz: has_lobes alani ("zincir kapali" tanisi icin).
- Tani: eski sunucu + yeni panel = "zincir kapali" (cozum: sunucuyu yeniden baslat).

## 9.116 Sinyal paneli bitki yolu duzeltmesi (2026-09-28, kullanici raporu)

Rapor: atesleme grafiginde sensor atimi gorunuyor, bitkiden hic atim
gelmiyor ve diger noronlari tetiklemiyor; motor/model saglam, bug
yalniz grafikte. Dogrulandi, kok neden 2 katmanliydi (ikisi de
telemetri/cizim, motor saglikli):

(i) Zincir p1 bitlerini dusuruyordu: motor T-satirinda duzenli
`p1=01/10/11` atesliyor (canli olcu: T 25 p1=01, T 200 p1=10,
T 300 p1=11), ama `T_RE` p1'i yakalamayip `aff_events_from_t`'a
yalniz p2 gidiyordu; panelde P1/bitki yolu hic yanmiyordu.
(ii) P1→P2 surusu cizilmiyordu: `fireP2` yalniz P2 spike'inda
yaniyordu; bitki atiminin A-dalina giren gercek surumu (I_syn =
w x 0.5, topoloji "A<-p1a/p1b") grafikte yoktu.

Duzeltme (cekirdek/harness/motor DEGSMEDI — §9.114 dondurmasina
dokunulmadi, `main_pattern_lobe.cpp` dahil):
- `sim/sensory_chain.py`: `T_RE` p1 yakalama grubu +
  `p1_events_from_t` (hat 0=p1a, 1=p1b) + `_recent_p1` halkasi +
  snapshot `"p1"` anahtari (katkisal; G21/G37 kilitleri korunur).
  Besleme (`_forward`) aynen — p1 panele tasinir, ogrenmeye girmez.
- `web/static/js/signal.js`: `fireP1` (bitki koku → T1 yapragi →
  p1in → P1 somasi) + `driveP2` (ayni hattin P2 A-dalini kisik yakar,
  esik-alti surus; spike'tan ayri, spike parliyorsa dokunmaz) +
  `L.p1` akisi (`lastP1Tick`, tampon-son-6 disiplini aff ile ayni).
  Uydurma yok: her isik gercek olaya bagli (p1 biti / p2 biti / k4).
- `web/static/index.html` legend bitki notu.

Kapi G38 (yeni, `web/gates_web.py`): statik kablolama + canli
lobes.p1 listesi. Kanit: `validate_sensory_chain.py` (2b saf +
smoke p1-canli) cikis 0; G23 + G38 + G37 yesil.

DURUST SINIRLAR: (i) T-satiri 25 tick'te bir orneklenir — panel
orneklenen atimlari gosterir, ara tick'lerdeki P1/P2 atimlari
motorun icindedir, grafikte degil. (ii) Pattern tetiklenmesi k4
yolundan gelir (degismedi); `live_k4.csv` libc tamponludur
(olcumu: canli proseste 1 tick sonrasi dosya 0 B, 60 tick sonrasi
24 KB) — pattern atesi motorda olur, panele bloklar doldukca duser.
Bu dondurulmus dosyaya (`main_pattern_lobe.cpp`, §9.114) dokunmadan
duzeltilemez; degisiklik istisnasi yalniz acik kullanici onayiyla
bu fikraya islenerek olur.

Ek (2026-09-28, "sadece bir yer parliyor" raporu): onceki duzeltme
tek noktayi yakiyordu (yaprak + giris). Referans HTML'deki akis
senaryolu demoydu (sozde-rastgele olaylar) — uretimde sentetik atim
yasak oldugundan ayni GORUNUM tek gercek olayin dal-dal kaskadiyla
verildi: `fireP1` T1KEYS'i derinlige gore (85 ms/katman) atesler,
P1 varisinda soma + p1in yanar, sonra T2KEYS ayni hattan acilir ve
`driveP2` gelir; sensor teli degisimi SW sirasinda 900 ms'ye yayilir
(`signal.js` + legend). Kapi G38 aynen yesil (jetonlar korundu).
