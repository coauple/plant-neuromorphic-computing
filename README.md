# Salep Sibernetiği — Zamansal Nöromorfik Hesaplama Araştırması

*Salep Cybernetics — temporal neuromorphic computing: from plant
electrophysiology to learned representations. An experimental prototype and
its documented development history (not a finished diagnostic system).*

**Özet:** Bitki elektriksel olaylarındaki zamansal örüntülerden koşul temsili
öğrenilebilir mi? Bu depo, soruyu çok bölmeli dendritik nöronlar, faz seçici
rezonans (TDM → PLIR/FDM), kuadratik sinapslar, duyusal lob, bitki simülatörü
ve örüntü lobuyla araştıran prototipin Eylül–Ekim 2026 geliştirme kayıtlarını,
deneylerini ve dürüst sınırlarını sunar. Olumsuz sonuçlar gizlenmemiştir.

**İçindekiler**

1. [Araştırmanın doğuşu](#1-araştırmanın-doğuşu)
2. [Temel araştırma sorusu](#2-temel-araştırma-sorusu)
3. [İlk hesaplama düşüncesi](#3-ilk-hesaplama-düşüncesi)
4. [İlk nöron ve sinaps deneyleri](#4-ilk-nöron-ve-sinaps-deneyleri)
5. [TDM'den PLIR/FDM'ye](#5-tdmden-plirfdmye)
6. [Duyusal lobun gelişmesi](#6-duyusal-lobun-gelişmesi)
7. [Bitki simülatörü](#7-bitki-simülatörü)
8. [Sistem bütünleşmesi ve TEST B](#8-sistem-bütünleşmesi-ve-test-b)
9. [Örüntü lobu](#9-örüntü-lobu)
10. [Başarısız deneyler ve tasarım kararları](#10-başarısız-deneyler-ve-tasarım-kararları)
11. [Bugünkü mimari](#11-bugünkü-mimari)
12. [Sınırlar ve doğrulanmamış iddialar](#12-sınırlar-ve-doğrulanmamış-iddialar)
13. [Gelecek araştırmalar](#13-gelecek-araştırmalar)
14. [Deneyleri çalıştırma ve belgeler](#14-deneyleri-çalıştırma-ve-belgeler)

> Not: Kodlar yapay zekâ araçlarıyla yoğun destekle yazıldı; sorular, deneyler
> ve kararlar kullanıcı tarafından yönlendirildi. `[KOŞULDU]` = 28 Eki 2026'da
> taze derlemeden doğrulandı; `[BELGE]` = kayıtlı belge + kod okumasına dayanır.

## 1. Araştırmanın doğuşu

> ✍️ **[KULLANICI TAMAMLAYACAK — belgede yok, uydurulmadı]:** Salep
> yetiştiriciliğinden bitki elektrofizyolojisine, oradan nöromorfik hesaplamaya
> nasıl yöneldiniz? Başlangıçta hangi sorulara cevap arıyordunuz? 2–3 paragraf
> kişisel motivasyon buraya.

Belgelenmiş kapsam: teknik günlükler Eylül 2026 geliştirme sürecini kapsar;
daha eski fikirlerin bu hedefleri paylaşıp paylaşmadığı kayıtlardan
doğrulanamaz. Eylül kayıtlarının başlangıcında tanımlı hedef: bitki
biyoelektrik olaylarını işleyen, çok kompartımanlı, ileride FPGA'ya
taşınması hedeflenen bir nöromorfik çekirdek (`salep_core/CLAUDE.md` §1–2).

## 2. Temel araştırma sorusu

Zamansal örüntülerden koşul temsili öğrenmek mümkün mü — yavaş, gürültülü,
seyrek bitki sinyallerinde, etiketsiz, zamanın kendisi bilgi taşıyıcıyken?
Klasik zorunlu-etiketli sınıflandırma yerine araştırılan: faz seçici rezonansla
ritim ayıklama, spike zamanlamasıyla ayrıştırma, birlikte-ateşlemeyle koşul
öğrenme. Model "bu kuraklık" diye etiketlenmez; temsil dinamiğin ürünü olur
(ya da olmaz — §10).

## 3. İlk hesaplama düşüncesi

Üç erken karar mimariyi kilitled (`ARCHITECTURE.md`, `CLAUDE.md` §0–2):
(1) nokta-nöron değil **çok bölmeli dendritik nöron** (iki dal + soma;
çift-dal çakışmasıyla ateş); (2) **üç katman** (faz çözümleme → rekabetçi
kümeleme → çapraz-bant nedensellik; CPU yalnız özet okur); (3) **donanım
kısıtları** (Q16.16 sabit nokta, dinamik bellek yok, LUT, deterministik tick).
Yöntem kuralı: sayısal iddia önce Monte Carlo ile doğrulanır (§0) — geçmişte
testsiz sabitlenen iddiaların dersi.

## 4. İlk nöron ve sinaps deneyleri

**Soru:** İki dallı nöron + kuadratik sinaps birlikte-ateşlemede büyür ve
tavanda durur mu? **Kurulum:** tek nöron + `dw = eta·G·Q·S` (`src/main.cpp`,
`src/synapse.h`, `src/main_synapse.cpp`); N0–N1 20×500 tick birlikte
ateşlendirildi; ağırlık her tick CSV'ye yazıldı. **Sonuç:** büyüme OK
(0.05→1.76); aktarım OK (düşük ağırlıkta N1=0, yüksekte 79 ateş) [KOŞULDU].
**Sınır:** doygunluk taze derlemede sınırda (UYARI); `S` teriminde zaman yok.
**Karar:** kural çekirdeğe girdi; Katman-1 ağına geçildi (3 sinaps monoton,
N3 1.71×, multiplex 2.26× — §9.5, [BELGE]).

![nöron izi](salep_core/neuron_trace.png)
![sinaps](salep_core/synapse_learning.png)

*Tek nöron membran izi ve sinaps ağırlık eğrisi (`neuron_trace.csv`,
`synapse_learning.csv`).*

## 5. TDM'den PLIR/FDM'ye

**Soru:** Aynı hattaki farklı ritimler birbirini bozmadan ayrı popülasyonlarca
işlenebilir mi? **İlk yaklaşım:** tau-ayarlı nöronlarla ardışık-pencere
seçiciliği (TDM, `main_phase_group.cpp`): bant-içi ≥%98,8 [BELGE].
**Problem:** sonuç simultane karışımı kanıtlamıyordu; eski ISI kapısı yabancı
darbeyle tazelenip yavaş bandı boğuyordu (kök neden analizi, §9.8).
**Değişiklik:** PLIR (yalnız kabul gören darbede güncellenen rezonans
hafızası) + bant başına 8 üyeli popülasyon; iki ritim tek tele süperpoze
(`main_fdm.cpp`). **Sonuç:** kilit + faz kayması ≤0.03 tick [KOŞULDU,
`A=A2=C=D=OK`]. **Sınır:** harmonik-faz takibi yok, 3. bant yok,
tohum-duyarlılık, deterministik ızgara. **Karar:** FDM çekirdek mekanizma oldu.
[§9.6–9.8]

![tdm](salep_core/phase_group_learning.png)
![fdm](salep_core/fdm_simultaneous.png)

*TDM seçiciliği ve simultane FDM kilit/faz haritası. Bu deney herhangi sayıda
sinyalin ayrılabileceğini veya tarlada tanı konabileceğini kanıtlamaz.*

## 6. Duyusal lobun gelişmesi

**Soru:** Frekans bandı sensörle eşleşince sensörsüz yanıt (CR) oluşur mu?
**Kurulum:** P1 faz hatları + 10 üyeli P2 koşul bankası, negatif kontrollü
(`main_plant_npu.cpp`, `main_sensory_lobe.cpp`). **Kırılma:** 7 kanalın tek
tele zorlanması §9.8 sınırlarına takıldı → **dual-rail** kararı: frekans
Rail-F'de, kanal kimliği Rail-C sayaçlarında (§9.12). **Sonuç:** bitki NPU
4/4 OK (CR 62/117/0) [KOŞULDU]; duyusal lob taze derlemede `A=UYARI`
(`A=OK` yalnız Eylül binary'siyle — dürüst kayıt). **Sınır:** 2 bant; WTA
rekabeti yok; eşzamanlı çift yenilik denenmedi. [§9.11–9.16]

![bitki](salep_core/plant_npu.png)
![duyusal](salep_core/sensory_lobe.png)

*Koşullanma (kilit/kazanç/CR) ve duyusal lob panelleri.*

## 7. Bitki simülatörü

**Soru:** Deneyleri besleyecek fiziksel çevre + sentetik elektro olaylar
üretilebilir mi? **Gelişim:** `sim/` paketi (11 Eyl), web katmanı, gerçek Aydın
havası, UV/şema-v2, 9 adımlı fiziksel su modeli, pertürbasyon bataryası
(8 hipotez), 10.000 yörüngelik çıkarım Faz-1 (§9.19–9.51). **Sonuç:**
simülatör kapıları + K6/K7 sızıntı yasakları; fizyoloji parametreleri model
seçimidir, tarla değil. **Karar:** TEST B bu zemin üzerinde kuruldu.

![perturbasyon](salep_core/perturb_battery.png)

## 8. Sistem bütünleşmesi ve TEST B

**Soru:** Fizik→elektro→duyusal→afferent zinciri 250 günlük stres arkını temsil
edebilir mi? **Kurulum:** `validate_testb.py` → `npu_sensory_plant`
(tek yörünge, seed 1). **Sonuç:** B1–B4+B6 geçti; **B5 CR üretilemedi
(CR_YOK)** [BELGE]. **Karar:** kapalı çevrime geçilmedi; temsil
karakterizasyona (süpürmeler, imzalar, A-only) dönüldü. Etiketler temsilden
türetildiği için assoc skoru (163/165) dünya-sınıflaması değildir. [§9.57–9.66]

## 9. Örüntü lobu

**Soru:** Afferent akış tekrar-kullanılabilir zamansal/uzaysal temsile dönüşür
ve korunur mu? **Kurulum:** K1 (what) / K2 (when) / K3 (history) + K4
ilişkisel yol, 29 birim (`src/pattern_lobe.h`, `main_pattern_lobe.cpp`);
REV3 bataryalar → REV4 → dondurma (§9.90–9.114). **Sonuç:** `olay=300
mem=116`, snapshot ile bit-bit aynı [KOŞULDU]; determinizm/sınırlar OK.
**Gerçekleşmeyen:** bellekten çıkarım duyusal tabanı geçemedi (0.310/0.356'ya
karşı 0.554); yeni kavram ve nedensel öğrenme gösterilemedi (B7/B9/B10).
**Karar:** lob donduruldu; canlı zincire bağlandı (§9.110–9.113). (Örüntü
çıktılarının kayıtlı PNG'si yoktur.)

## 10. Başarısız deneyler ve tasarım kararları

| Hipotez | Sonuç | Karar |
|---|---|---|
| Ardışık ayrım simultane genellenir | TDM sınırı belgelendi | PLIR/FDM (§9.8) |
| 7 bant tek tele sığar | İmkânsızlık | Dual-rail (§9.12) |
| Kuadratik çıkarımı iyileştirir | 0.400 < 0.554, varyantlar da altında | Kural donduruldu (§9.71–72) |
| TEST B'de CR üretilir | CR_YOK | Kapalı çevrim yok (§9.59) |
| Bellekten çıkarım tabanı geçer | 0.310/0.356 < 0.554 | B10 açık borç |
| Çekirdek kör barları geçer | Demux D1/D2 KALDI; seyrekte sessizlik | Raporlandı, yumuşatılmadı |
| Eylül CSV'leri taze derlenir | Bit-farkı; sensory `A=UYARI` | Kayıtlı-binary koşulu |

## 11. Bugünkü mimari

```
[Bitki simülatörü] ── 7 sensör ──> [P1 faz hatları] ──> [P2 koşul bankası]
      (Python)                        (PLIR)              (10 üye, dual-rail)
                                                              │ afferent
[Web izleme] <── pencere özetleri <── [Örüntü lobu] <─────────┘
                                        (29 birim, donuk)
```

**Çalışan:** yukarıdaki zincir (açık döngü), web + canlı zincir, deterministik
tekrar. **Eksik:** kapalı çevrim, WTA rekabeti, kavram/çıkarım/nedensellik/
öngörü katmanları, tarla doğrulaması.

## 12. Sınırlar ve doğrulanmamış iddialar

- Faz-seçiciliği skorları sınıflandırma skorlarından ayrı okunmalı; AUC tek
  başına seçicilik/ret/sessizlik/kapsama ölçmez.
- Tek yörünge (seed 1); tohum-duyarlılık ana skorlarda yok; 85 sessiz gün
  skor dışı; hn/ph/npk türetmeleri `TODO: DOĞRULANMADI`.
- Gerçek bitki kaydıyla temas yok (Aşama 7 ölçüm-sınırı kaydıdır).
- Web NPU görselleştirmesi eksik/güvenilmez; esas: kod + telemetri + CSV/OZET.

## 13. Gelecek araştırmalar

Koşul temsillerinden **kavram oluşturma ve türetme**, **kavramsal çıkarım**,
**nedensel modelleme** ve **öngörü** — bütünleşik ve doğrulanmış biçimde
geliştirilmedi. Önkoşul borçları: bağımsız yörüngeler, sessizliğin karar
olması, belleğin çıkarıma katkısı, gerçek kayıt.

## 14. Deneyleri çalıştırma ve belgeler

```bash
cd salep_core
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt  # ağ gerekir
g++ -std=c++17 -O2 -Isrc src/main.cpp -o npu_sim && ./npu_sim       # ilk deney
.venv/bin/python -m web.server --port 8001 --pub-port 41793         # canlı site
```

Ayrıntı: [QUICKSTART.md](QUICKSTART.md) (doğrulanmış ilk deney),
[INCELEME_REHBERI.md](INCELEME_REHBERI.md) (10–15 dk tur),
[DENEYLER_VE_ANALIZLER.md](DENEYLER_VE_ANALIZLER.md) (bütün deneyler),
[RESEARCH_HISTORY.md](RESEARCH_HISTORY.md) (tarihçe),
[salep_core/CLAUDE.md](salep_core/CLAUDE.md) (günlük),
[salep_core/bench/REPORT.md](salep_core/bench/REPORT.md) (bağımsız değerlendirme).

> Testler kayıtlı sonuçların üzerine yazar — paketin kopyasında çalışın.
> Bu paket GitHub'da yayınlanmıştır:
> [coauple/plant-neuromorphic-computing](https://github.com/coauple/plant-neuromorphic-computing).
> Kaynak: [DOSYA_LISTESI.txt](DOSYA_LISTESI.txt).
