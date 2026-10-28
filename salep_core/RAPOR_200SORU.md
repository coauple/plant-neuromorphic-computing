# 200 SORU — TEK RAPOR (kod kanıtlı, deneyli)

Tarih: 2026-09-22. 7 paralel arastirma grubu; kaynak govde acilip incelendi,
deneyler `npu_pattern_lobe` ile kostu (repo degisikligi yok).
Ham ciktilar /tmp/g1..g7, grup raporlari /tmp/rpt_g1..g7.md.

Kisaltmalar: OZET = OZET-PATTERN-LOB; STATE = wsum/tsum/rsum ham toplamlari
(taze: 34209792/0/0, FIXED_ONE=65536).

## GRUP 1 — Gercekte ne urettik?

**1.1 Girdi bitki sinyali mi sim temsili mi?** Sim temsili: plant_sim fizigi
-> sensor_map (7 sensor: hs/ts/hn/tn/ph/npk/ec) -> duyusal lob (P1/P2) ->
(tick,post,tau) afferent. testb_afferent.csv ham bitki kaydi degil harness uretimidir.

**1.2 Hangi ozellikler korunuyor?** Zaman (tick), faz adresi (post 0..11),
periyot (tau 4..60). Binary ilk uc kolonu okur; label/w/a0lag/bmask okunmaz.

**1.3 Ham mi on-islenmis mi?** On-islenmis: fizik -> sensor -> P1 PLIR -> P2
kosul bankasi -> T telemetrisi -> pencere -> pattern lob.

**1.4 Sensory lob duyu mu donusturucu mu?** Donusturucu: ham sensoru kosul
etiketine (p2a(p2c,p2d)) ve (tick,post,tau) olayina cevirir.

**1.5 Afferent haberlesme katmani mi?** Evet: dar alfabeli olay listesi
(SPEC_v0_1 donuk), pattern lobdan bagimsiz.

**1.6 Pattern lob yeni oruntu cikariyor mu?** Evet: 29 birim + 58 node K4;
cikti ates vektoru (fires_hex) + mem kaydi.

**1.7 Pattern matematiksel tanimi?** (a) ates vektoru (29 birim bitmask);
(b) mem satiri (voltaj+gating+coinc); (c) K4 matrisi (58x58 simetrik r)
+ nicemlenmis dal imzasi q[3] + uyum sim=SUM(6-|dq|)/18, esik 13/18.

**1.8 Ayni girdi ayni pattern mi?** Evet: deterministik, RNG yok; iki kosu
mem/log/OZET bayt-bayt ayni (cmp temiz).

**1.9 Kucuk degisiklik etkisi?** +2 tick kaydirma deseni korur, zamanda oter.
Tum kapilar goreli zamana bakar; mutlak referans yok.

**1.10 Buyuk spike degisiminde neden sabit?** Kosullu sabitlik: zaman-ardisik
x2'de birim siralamasi korunur (nicemlenmis imza + coincidence kapisi + S4
tavani). AMA ayni-tick bindirme bozar (mem 140->1313).

**1.11 Zamanlama degisince neden?** Coincidence (10 tick), ISI kapisi, q
imzasi, K4 coin hep goreli zamana bagli (jitter mem 140->73).

**1.12 Kural mi emergent mi?** Kural: esikler/pencereler/formuller sabit.
K4 r birikir ama guncelleme deterministiktir.

**1.13 Patternler onceden biliniyor mu?** Kablolama bilinir, ates bilinmez.
P3ab/ac (27,28) OPEN/sessiz.

**1.14 Yeni pattern ureyebilir mi?** Evet: r sifirdan yazar, eta>0 iken
agirliklar degisir, yeni kombinasyon yeni vektor uretir.

**1.15 Kapasite siniri?** 29 birim; 12 slot x 57 tau; birim basi 18 sinaps;
58 node/1653 cift; mem tavani 4096.

**1.16 29 birim bagimsiz mi?** Hayir: her olay 29 birime dagilir; K4
birimleri baglar. Dagitik durumdur.

**1.17 K4 temsilin parcasi mi?** Evet, opt-in: +2 kolon, 116->140 ates,
k4_kfires=92; N-kapisi geregi tek basina atesletemez. Kapaliyken F1 saf (J).

**1.18 Tek spike mi dagitik durum mu?** Dagitik: ates vektoru + voltajlar +
gating + coinc + K4 + argmax partner.

## GRUP 2 — Ogrenme gercekten ogrenme mi?

**2.1 Baslangic bilgisi?** Kablolama + sabitler + w=1.0/T=0/r=0. Deneyim yok.

**2.2 Degisenler?** A1 sonrasi wsum +638896, tsum 0->647128, rsum 0->4804688;
wkdev 0->0.9989; unit 9'da 6 ates.

**2.3-2.5 w/T/r nedenselligi?** Potansiyasyonda w += dw*(1+T),
T += 1/8*(1-T) (yalniz artar); dw=0 iken w tabana gevser (T*WMAX, sifira degil).
r: coin+sim>=13 ise +1/8, her tick -1/8 (yari-omur ~5 tick).

**2.6-2.7 Gercek bilgi?** Davranisa yansiyan kalici bilgi w/T'dir. Eta=0
kosusunda (r ogreniyor, w/T donuk) A2=A1, hizlanma YOK; k4=0'da hizlanma
korunur. r tek basina hizlandirmaz; K4 atesi ve w-ogrenmesine geri-besler.

**2.8 Fiziksel konum?** Proses RAM'i: 522 weight + 522 trace + r[58][58].
Ogrenilmis A: yalnizca unit 9'un 10 bagli sinapsi (8x1.9989, 2x1.8788).

**2.9-2.10 Kapanma?** SAVE yoksa her sey gider (taze STATE). SAVE varsa .plst
sag kalir; --load ile birebir geri gelir.

**2.11 .plst rolu?** Depo, mekanizma degil: yalniz w/T/r (17668 B). V/gating
tasinmaz; yuklenen proses tcur=0. Bozuk dosyada kismi yukleme YOK.

**2.12-2.14 Sifirlanirsa?** CLI komutu yok; vekil deney: T=0 -> saf GQS
(hizlanma yok); w dusuk+T>0 -> taban yukari ceker (sessizlikte +15.2);
r=0 -> F1 surer, K4-atesi kaybolur.

**2.15 T-only relearning olculdu mu?** Evet: taze 61-71 tick -> yuklu 1-11
tick (ayni dizi). Olaysiz toparlanma +997448 (T sabit). Hizda gorunur,
buyuklukte degil (tavan).

**2.16-2.17 Capraz etki?** B unit {6,7,11,14,15,23,24,25} atesledi, unit 9
HIC ateslemedi (tam ayrisma). B sonrasi A izleri silinmedi.

**2.18-2.22 Fark zamanlamasi?** A2 farki 2. sunumun 1. tick'inde cikar, surekli
surar (6->7 ates). 20000 tick + restart sonrasi tam korunur.

**2.23 Interference?** Yok (bu cift icin).

**2.24-2.25 Unutma?** Gozlenmedi: doymus izlerde w duz cizgi; kismi izlerde w
tabana YUKSELDI. Klasik agirlik-sonumu unutusu YOK.

**2.26 T-varken-w-dusmesi?** Olculmedi; kodda mumkun (tabana gevreme) ama
gozlemde hep w<=taban tarafindaydik.

**2.27 STM/LTM?** r=STM (~5 tick yari-omur); w/T=LTM (T sonmez, taban).
V/gating/sayaclar episodik. (k4_spikes tum kosularda 0; K4 etkisi S4/kfires.)

**2.28 KRITIK TEST A-sil-B-sil-A vs A-sil-A:** Ikinci A birebir ayni
(ilk ates +1. tick, 7 ates rel 1,60,193,275,1152,1215,1298; birinci A'da rel
61, 6 ates). B ikinci sunumu HIC degistirmedi (rsum A2 sonrasi ikisinde de
4804688). Sessizlikte wsum/tsum bit-bit ayni, rsum->16464.

**Sinirlar:** tek A/B cifti; T/w/r tek-tek sifirlama CLI'da yok; (1+T)
buyuklugu izole olculmedi.

## GRUP 3 — Genelleme

**3.1 Ezber mi genelleme mi?** Kademeli ikisi: jit2/drop1/shift J=1.0;
jit10 J=0.846; drop50 J=0.692. Tam ezber degil, tam degismezlik degil.

**3.2 Kucuk/buyuk varyasyon?** Kucuk (±2 tick, tek spike) gorunmez; buyuk
daraltir/bozar ama cekirdek birimler (6,7,9,23,24,25) ayakta kalir.

**3.3 Ara pattern?** p2a+p2h karisimi coker (J=0.077, tek birimde 2 mem).
Ara oruntu ebeveynlerin birlesimi olarak taninmaz.

**3.4 Ayni sayi farkli zaman?** Grup-ici eszamanlilik korunursa yanit
bit-identical (retime J=1.0). Mutlak zaman temsil edilmez; 10 tick
birliktelik yapisi belirleyicidir.

**3.5 Farkli sayi ayni yapi?** Yapi tekrarlanirsa yanit ust kume olur
(25 birim, J=0.520, mem ~10x). Secicilik duser, guc buyur.

**3.6 Genlik?** AFF formatinda genlik YOKTUR. w kolonu okunmaz. Giristen
genlik verilemez; bu harness ile test edilemez.

**3.7 Sure olcegi?** En kirilgan boyut: x0.5 -> 496 mem/22 birim (tasma);
x2 -> 16 mem/5 birim (unutma).

**3.8 Gurultu?** %10 rastgele: J=0.650, cekirdek korunur ama 7 yeni birim
sahte atesler; secicilik duser.

**3.9 Dusurme/kaydirma?** Tek dusurme etkisiz (J=1.0); %25 kayip sert
(J=0.462). Global kaydirma tamamen etkisiz (J=1.0): goreli-zaman sistemi.

**3.10 Esik?** Kod SIM_MIN_NUM=13/18 (birebir 18; 13-17 gecer; <=12 gecemez).
Deneysel kirilma 2-5 tick arasi (10 tick pencereyle tutarli). Tek tohum.

**3.11 Hic gorulmemis organizasyon?** Periyodik dizi yeni temsil acmaz:
yalniz birim 23 (J=0.077). Yabanci ritim mevcut kabloya indirgenir.

**3.12 Yeni sinaps?** Hayir: sabit 18 slot; kablosuz slot ogrenmez.
Ogrenme yalniz bagli agirliklari degistirir.

**3.13 Alan paylasimi?** Evet: 29 birimlik sabit havuz; dinamik buyume yok,
mevcut birimler yeniden kullanilir.

**3.14 Yeni-ogrenme vs guclendirme?** Kodda ayri kapi yok: tek kural
dw=eta*G*Q*S + iz. Eta 0.30'da 139/522 sinaps degisti, mem 140->562.
Ogrenme = mevcut yollarin guclenmesi.

**3.15 Online yeni-temsil?** Sinaps tarafinda HAYIR. Kismi EVET yalniz K4
r-matrisinde (deneyimle dolar, eta bagimsiz) — ama sabit 58 dugum arasi
agirlik; yeni birim/slot mekanizmasi YOKTUR.

## GRUP 4 — Habituasyon iddiasi

**4.1 Tekrarda ne olur?** Cevap AZALMAZ: eta=0'da duz (200-tick bloklar
~202-231); eta=0.30'da ARTAR-doyar (219->422, fasilitasyon).

**4.2 Neden sonsuz pattern yok?** Ates-reset + leak + 29 sabit birim + mem
4096 tavani + S(w) doyumu (w=2.0 tavan). Yogun uyaran plato (~575/200).

**4.3 K4 neden az atesler?** K4 yalnizca EKLEYEBILIR (yapisal: s123+s4>esik).
Birim-bazi eksiler ogrenme-iz ayrisma. Bu rejimde K4 spike HIC yok
(k4_spikes=0 tum kosularda): yerel surus seyrek + rel partner spike kapili.
Katki yalniz esik-alti S4 (cap 0.25).

**4.4 Adaptasyon mu leak/reset mi?** Leak/reset. Adaptasyon mekanizmasi kodda
YOK (gating birikimi kolaylastirma yonunde). Eta=0 egrisi duz; 1000 tick
sessizlik sonrasi tam toparlanma.

**4.5 Azalma hangi degisken?** Yok. wmax 1.0->2.0 doyar, Tmax->1.0, r ogrenir
ama spike kapisinda etkisiz. Azaltan degisken YOKTUR.

**4.6 Mekanizma kapatinca?** Duzluk eta=0'da K4 bagimsiz (F1 leak/reset);
artis eta=0.30'da K4 bagimsiz (sinaptik ogrenme). K4 etkisi +23/+25 ates.

**4.7 Parametre siddeti?** Uyaran 2.5x: hiz ~230->575 olceklenir, egri yine
duz, k4_spikes yine 0. Siddet seviyeyi belirler, dinamigi degistirmez.

**4.8 Toparlanma + tekrar?** Sessizlikte ates 0 (STATE sabit); donuste eski
seviye (~228). Kalici baskilanma YOK. Farkli pattern (post=7): duz ama dusuk
seviye (secicilik).

**4.9 Terminoloji hukmu?** `habituation` KULLANILAMAZ: tekrarla azalma yok;
koda ozgu plastisite yok. Dogru: en fazla betimleyici
`adaptation-like response suppression` (reset+leak). Raporlara "habituasyon
gozlendi" yazilMAMAli.

## GRUP 5 — Nedensellik

**5.1 Korelasyon mu?** KORELASYON. v4c_net_update a<b ciftlerini gezer;
tek rij iki hucreye de yazilir (r[a][b]==r[b][a]). Once/sonra, yon terimi YOK.

**5.2 AB vs BA?** Neredeyse ayni, bit-identical DEGIL. Ayni cift kumesi
(1332/1332, ortak-disi 0), en guclu ciftler bit-identical (r=0.414322).
Ama zayif ciftler farkli ((48,45): 0.0376 vs 0.3193; matris korelasyonu 0.23),
K4-atesi 43'e 31. Sebep: q imza kalintilari siraya bagli; YON yazilmaz ama
esik-kenari etkilenir.

**5.3 AB/BA ayriliyor mu?** HAYIR. Final matriste yon saklanamaz (simetri
sapmasi 0.000000). Ayiran sinyaller ikincil/zayif (artefakt).

**5.4 Sira etkisi?** Guclu iliski degismez; zayif cift degeri + K4-ates adedi
degisir. Cekirdek iliski bozulmaz.

**5.5 K4 neyi temsil eder?** BILESK E: coin (10 tick birlikte-aktivite) AND
sim>=13/18 (kimlik yakinligi). Benzerlik tek basina yetmez, birlikte-ates
tek basina yetmez. "K1-K3 = ne oldu; K4 = neyle birlikte oldu".

**5.6 r gecmis tasir mi?** EVET, kisa-sureli: +1/8 adimlarla denge ~1'e;
son olaydan ~10 tick sonra bile buyur; sonra leak (1-1/8)/tick: 10 tickte
x0.263 (teoriyle birebir), yari-omur ~5.2 tick, ~80 tickte taban.

**5.7 Tekrar guclendirir mi?** EVET, iki katman: r +0.125/adim; w dw*(1+T)
(Unit6: 12 tekrarda +0.14, T 0->0.9999).

**5.8 Kullanim-disi?** EVET zayiflar, ama UNUTMA YOK: r x0.875/tick; w
T*WMAX tabanina gevser (120 tickte 1.143->1.267 YUKSELDI - klasik decay
degil). Sifira silinme hicbir katmanda yok.

**5.9 Trace kalir mi?** T EVET (120 tickte 0.9999 sabit, ASLA sonmez). r'de
islevsel iz YOK (taban rsum=9324 yalniz kuantalama kalintisi).

**5.10 Geri-donuste hizlanma?** r'de HAYIR (tepe %0.13 fark - bellek yok);
w'de EVET (ilk 12 tekrar +0.14, geri-donus +0.64; (1+T)~2 carpani).

**5.11 KRITIK HUKUM:** "A, B'nin sebebidir" DENEMEZ. Dogru: "A ile B
iliskili". Kanit: kod simetrisi + ampirik sapma 0 + sira-takas ust-yapiyi
degistirmiyor + kuralda oncelik terimi yok. Yon-asimetrisi tanimsal olarak
yoktur.

## GRUP 6 — Hafiza

**6.1 Dagilim?** Olay basi fan-out: slot1->15 birim/38 sinaps, slot5->22/65,
slot8->7/8, slot9/10->0 (kablosuz olu), slot11->1/1. Pattern ~8-65 sinapsa
dagilir; bedel ortak havuzdan.

**6.2 Iz kac parametrede?** 522 w + 522 T (bagli 393). AB oturumu: wsum
ortalama ~1.12, T ortalama ~0.14.

**6.3 Maliyet dagilimi?** Hicbiri pattern-spesifik DEGIL: w/T sinaps-seviyesi
ortak, r global-ortak (100-patternd 1066/1653 cift dolu - tum patternlerin
tortusu). Marjinal maliyet yalniz mem kaydi (4096 cap).

**6.4 Paylasim/interferens?** Yapisa: slot1n5 kesisimi 10 birim (Jaccard
0.40). Ogrenme portu (soma-as-post, G=min kapisi) yalniz bagli sinapslarda;
kesisim birimleri karsi patternde ateslenirse A-kablolu sinapslar da
potansiyasyona ugrar - interferens = potansiyasyon-yayilmasi (depresyon YOK).

**6.5 Cift yonlu bozma?** Evet: B-fazinda A-birimleri 13,18 (2 capraz);
A-fazinda B-birimi 18 (1 capraz). Doygun dozda +44/+57. Bicim AZALMA degil
secicilik kaybidir.

**6.6 Olcek?** P=10: mem294/wkdev0.98; P=30: mem1412/wkdev1.0; P=60: 3148;
P=100: 4096 CAP (1412 ates kayitsiz; ogrenme surer). P=1000: ~0.6 sn ama ilk
~30 pattern zaten tavanda - geri kalan kayitsiz+seciciliksiz. Darbogaz sure
degil kapasitedir.

**6.7 Saturasyon/unutma/REV-LEARN?** Saturasyon erken: tek patternde 12 olayda
wkdev 0.01->0.71; P=10'da ~0.98, P=30'da 1.0. T asimptotik dolar (~17
potansiyasyonda %90); tasma/ezme/silme YOK (kodda depotansiyasyon ve delete
komutu yok). Catastrophic forgetting GOZLENMEDI (A-probu taban alti dusmedi:
13'e 13; 138'e 136). REV-LEARN azaltir: T sonmez + T*WMAX taban + monoton
potansiyasyon + S-tavani. T==0 klasik davranir.

**6.8 1 gun/ay/yil?** Tick=1ms varsayimiyla tum dinamik olcekler (gating
69-347, gevreme ~139, iliski ~5, pencere 30 tick) 86.4M tick yaninda sifirdir:
uc vade AYNI son duruma yakinsar - yalniz (w->taban, T) kalir.

## GRUP 7 — Biz mi yaptik, zaten oyle miydi?

**7.1 K4 iliskisi?** TASARLANDI. B'de 2352 nonzero cift, +26 ates, 91 kfire.

**7.2 Volume invariance?** EMERGENT: nicemleme+bayrak sonucu; ayri normalizasyon
kodu YOK. 3x hacimde cikti bit-ayni (k4_maxact/k4_s4max birebir).

**7.3 Temporal selectivity?** PARAMETRE (10-tick) + tasarlanmis kapi: yayik
girdi iliski kuramaz (top r 0.2888->0.1561, kutle yigilmasi).

**7.4 Habituation-like?** DURUST NEGATIF: ates-hizinda GOZLENMEDI (40 tekrarda
bloklar 2,9,9,8,9,9,9,9 duz); yalniz r-sonumu + S4 tavan doyumu var. K4 act
ARTTI (0.115->2.54, fasilitasyon).

**7.5 Trace->relearning?** TASARLANDI (REV-LEARN): (1+T) + sonmeyen iz + taban.
wkdev~1, mem 139->561. (Iki-faz izole olcumu yapilmadi - kisit.)

**7.6 Ablasyon (ayni girdi, 299 olay):** A K4-OFF: mem=115/ates=138/wkdev=0.
B K4-ON: mem=139/164/kfires=91. C +ogrenme: mem=561/669/wkdev=0.9998.
D +persistence: B ile bit-identical (diff bos). Sonuc: K4 +26 ates/91 kfire
uretir; ogrenme 115->561'i uretir; persistence HICBIR sey uretmez, dondurur.
k4_spikes tum hucrelerde 0 (katki hep subthreshold S4).

## GRUP 8 — Gercekten ne urettik? (hukum)

**8.1 Yeni noromorfik mimari mi?** Kismi EVET: cift-rayli sabit kablolu F1
(K1/K2/K3 ayrisimi) + coincidence-kapili iliskisel K4 + sonmeyen iz + tabanli
gevreme bir arada standart bir kutuphane parcasi degil. Ama "mimari" iddiasi
icin karsilastirma deneyi YOK (asagida).

**8.2 Yeni ogrenme algoritmasi mi?** REV-LEARN uzantisi (iz-hizli
potansiyasyon + tabanli gevreme + sonmeyen iz) GQS cekirdegine ek deger katar
ve olculdu (geri-donus +0.14 -> +0.64). "Yeni algoritma" demek icin STDP
karsilastirmasi gerekir - yapilmadi.

**8.3 Yeni bellek mekanizmasi mi?** En guclu aday: T (sonmeyen iz) + w tabani
+ r (kisa-sureli iliski) uclu ayrisimi ve 17.6 KB'a sigan checkpoint formati.
Catastrophic forgetting gozlenmemesi + 20000 tick sagkalim olculdu.

**8.4 Yeni pattern representation mi?** Nicemlenmis dal imzasi (q) + uyum payi
(sim 13/18) + argmax partner kimligi ozgun bir bileske; tek basina "yeni"
denemez, karsilastirma gerekir.

**8.5 Kombinasyon mu?** EVET - su anki durust konum bu: bilinen fikirlerin
(GQS plastisite, coincidence detection, leak/integrate) ozgun birlesimi +
iki gercek yenilik adayi (sonmeyen iz+taban, iliskisel K4+S4 N-kapisi).

**8.6-8.7 Literaturden ayrilma / bilinen fikirler?** Ayrisma: faz-kilitli
PLIR giris + cift-dal coincidence zorunlulugu + K4'un spike-uretemeyen
ikinci-asama olmasi. Bilinen: LIF-benzeri integrate-leak-reset, Hebbian
GQS, rate penceresi, winner-take-all benzeri max-secimi.

**8.8 Gercekten ozgun olabilir?** Adaylar: (a) T*WMAX tabanli gevreme
(sifira unutma yok), (b) spike-uretemeyen iliskisel ikinci asama (S4 N-kapisi),
(c) 17.6 KB fixed-layout checkpoint. KANIT ICIN: STDP karsilastirmasi +
literatur taramasi + iki-faz relearning olcumu gerekir.

**8.9 Rakip deneyler?** Basit LIF+STDP ayni aff ile kosturulup mem/ates/Jaccard
karsilastirmasi; basit RNN ayni gorevde; K1/K2/K3 ayrisimini kapatan ablasyon
(tek-dal kontrolu). HICBIRI henuz yapilmadi - bu raporun en buyuk eksigi.

**8.10 LIF+STDP / RNN ayni seyi yapar mi?** Bilinmiyor (denenmedi). Tahmin:
saf STDP tabansiz unutur (bizde yok), RNN sira yonunu ogrenir (bizde yok).
Ama bu tahmin, kanit degil.

**8.11 K1/K2/K3 ayrisimi ne kazandiriyor?** Faz (K1) + genislik (K2) +
capa (K3anchor/follow) ayrisimi; q imzasi 3 dalin nicemlenmis oybirligi.
Kazanc olcusu: dal dusurme deneyleri yapilmadi - eksik.

**8.12 REV-LEARN ne kazandiriyor?** Olculdu: geri-donus hizi ~4.6x (+0.14 ->
+0.64), olaysiz tabana yukselme (+15.2), 20000 tick sagkalim. Maliyet: erken
saturasyon (P=30'da wkdev=1.0).

**8.13 Persistent trace ne kazandiriyor?** Yuklenen prob 61->1 tick ilk ates;
restart sonrasi kayipsiz devam. Maliyet: 17668 B dosya + SAVE/LOAD disiplini.

**8.14 Computational/enerji avantaji?** Olculmedi. Tick basina islem sayisi
cikarilabilir (tahmin: ~29x18 MAC + K4 58x58, sabit-nokta) ama enerji iddiasi
icin olcum/sentez YOK.

**8.15 FPGA'da ne kazanilir?** Tasarim elverisli (sabit-nokta, statik diziler,
~300 KB durum, ~18 KB checkpoint) ama sentez/yerlesim/zamanlama kaniti YOK.
Su an yalnizca mimari hedef + tasinabilirlik envanteri var (§onceki rapor).

## COZULMEMISLER (acik kalemler)

- G2: T/w/r tek-tek sifirlama CLI'da yok; sonuclar tek A/B ciftine ait;
  (1+T) buyuklugu izole olculmedi.
- G3: jitter tek tohum; SIM_MIN_NUM derleme-sabiti (runtime tarama yok).
- G7: iki-fazli relearning kosusu yapilmadi; habituasyon ritim taramasi yok.
- G8: LIF+STDP / RNN karsilastirmasi YOK; dal-dusurme ablasyonu YOK; enerji
  olcumu YOK; FPGA sentez kaniti YOK.

## TEK CUMLELIK OZET

Ogreniyor (kanitli), hatirliyor (kanitli), genellemesi kademeli (kanitli),
nedensellik yok (kanitli), habituasyon yok (kanitli), unutma yok (kanitli),
yeni temsil uretmiyor (kanitli), ozgunluk ve rakip karsilastirmasi eksik
(yapilmadi).

— Rapor sonu. Ham veriler /tmp/g1..g7, grup dosyalari /tmp/rpt_g1..g7.md.
