# PATTERN v4 ÖN-KAYIT PLANI (2026-09-17) — PROPOSAL

Durum: TASARI, implementasyon onayi DEGIL. v4-A matris degisikligi onayli
v3e matrisini devraldigindan implementasyon AYRI kullanici onayi ister.
Donuk dosyaya dokunulmaz; tum v4 isi additive yeni dosyalarda.

## P0. Duzeltilmis problem ifadesi (olculdu, 2026-09-17)

- Kablo alfabeleri (post_id, /tmp/pstress_e kablolari): base/hot/drought
  [1,4,6] (tau 37,45,46); irrig [1,4,6,7]; fert [1,4,5,6,9]
  (tau 26,37,45,46); g2_dh [1,4,5,6].
- Ulasilabilirlik 27/27 (header tablolari dosyadan parse + alfabe kesisimi):
  "15-23 birim ulasilamaz" YANLIS. Baglayici kisit = olay-basina seyrek
  surus + yapisal B-dalsiz sessizlik (P3a,b,c,e,f coincidence alamaz) +
  esik-alti coincidence. Alfabe birinci-derece belirleyici, tek belirleyici
  DEGIL (hot alfabesi base ile ayni ama +1 birim atesliyor: P3h).
- Plastisite fiilen kapali: base eta=0.30 wkdev=0.0032 (v3d 0.104, ~32x);
  G10 jacc(0,0.30)=1.0. Mekanizma: r_post~0 -> G~0 -> dw~0.
- D2 baglayici: ates-sonrasi ornekleme -> V_RESET kolonlari. v3e mem'de
  7/7 voltaj kolonu TEK deger (21 satir); anayasa §9.87 v3d 8/8'i kayitli.
  Iliskisel enerji kimligi pre-reset (peak) snapshot ZORUNLU.

## v4-A. Alfabe-kisitli gorev matrisi (tablo-yenileme, fizik degismez)

- Rol semantigi DONUK: K1 merkez+halka(0.2x), K2 kume-ici tam genlik,
  K3 anchor 1.0x / follower 0.5x (ayni kompartman).
- Alfabe = G1+G2+G8+G9 kablo kumesinin BIRLESIMI (base-only YASAK).
- Anti-konsantrasyon: tum birimler ayni 3-5 slota yigilmaz; secici
  farklilasma korunur (ortak-mod regresyonu YASAK).
- Kabul kapilari: (i) yeni-tablo E-serisi (E1-E8 dengi) HEPSI OK;
  (ii) TEST-B pilot pairwise Jaccard max<=0.5, birebir-ayni cift 0;
  (iii) ab/ac sessiz; B-dalsiz sessizlik surer (yapisal);
  (iv) legacy V1-V8 OK + f0_baseline bayt-ayni.
- HEDEF (rapor, bilimsel zorunluluk DEGIL): base aktif>=22/29, Nsig>=22.

## v4-B. Ogrenme yeniden-olcumu (v4-A sonrasi, ayni G10 caseleri)

Rapor: toplam wkdev + port-bazli kazanclar (k1c/k2a/k3aA ayrisma).
HEDEF (rapor): wkdev>0.02.

## v4-C. K4 kontrast formunda (PROPOSAL)

rel_i = cap(norm(SUM_j w_ij * (sim_ij - simbar_i)+)), simbar_i = komsu
ortalama benzerlik. "Herkese benzeyen" sifir enerji alir. Toplamali
surum bu planda YOK (cogunluk-havzasi patolojisi, olculdu).
D1 hukmu (asagida) + pre-reset sart; D3/D4/D5/D6 implementasyon-oncesi
kapanmadan kod YOK.

## v4-D. Engelleme (KOSULLU)

Yalniz v4-C "hacim-up envanter-duz" verirse (anayasa §4 yanal
engelleme yarisi). Ayri onay.

## D1 hukmu (2026-09-17): drive(u,s,t,inj) DEGISMEZ (v3e validate edildi,
dondu). sin/cos faz kaynagi zincirin HICBIR yerinde yok, icat EDILMEZ.
tau_b yalniz ONAYLI v4-A kapsaminda, on-kayitli AYRIK esleme ile, YENI
additive header'da kullanilabilir (kendi E-testleriyle).

## J-O onerilen kapilar (henuz KABUL edilmedi, implementasyon onayinda)

J: K4-kapali -> CSV seti bit-bit ayni. K: Nsig/rows envanter raporu.
L: causality-prefix (ilk-N-tick kararlari kirpilmis kabloda birebir ayni).
M: hepsi-benzer girdide iliskisel akim cap-altinda (olculur).
N: K4 yerel-surussuz birimi aktive etmez. O: alfabe + ulasilabilir-birim
sayisi her K4 kosusunda raporlanir.

## REV3. Dal-basina K4 — 58 node (2026-09-19, kullanici karari; ON-KAYIT)

Birim-basina contrast (v4c-01) rafa kalkti: 11-14 senkronu (J 0.29->1.0)
ortak-mod suphesi dogurdu. Yeni yapi: her P3 dalinin 4. kompartmani
(K4_A/K4_B); node `bid=unit*2+dal` (58); karsi kanal `r[b1][b2]` (1653
cift, A-A/A-B/B-B dahil). Dal kimligi = o dalin 3 K-voltaji (pre-reset).
Kural: `r <- clip(r + ETA*[agree>=2]*coin - LEAK*r, 0, 1)`,
`act_b = min(SUM r, 1)`, `drive = 0.01*min(act_A+act_B, 1)` (kokte, 1 tick
gecikmeli, dal-damgasiz). Taban-kontrast YOK; ortak-mod kapi-disi
(agree<2 gecemez). Sabitler (TODO: DOGRULANMADI): SIM_MIN=2/3 (agree>=2),
ETA=LEAK=1/8 (denge 1, yari-omur ~5 tick), REL_MAX=ACT_CAP=1, GAIN=0.01.
Dosyalar (versiyonsuz adlar): pattern_lobe.h + main_pattern_lobe.cpp
+ check_pattern_lobe.cpp (J0/C1-C4/M/N/E/P) + main_pattern_lobe_k4_rel
(R1-R7) + validate_pattern_lobe.py (B/J/R/P/D/M/N + rapor) +
k4_branch/matrix.csv. OZET etiketleri: OZET-PATTERN-LOB / OZET-LOB-CHECK /
OZET-LOB-PILOT (K4-REL aynen).

## REV4. Gercek K4 compartment (ONAYLANDI + UYGULANDI + PILOT OK, 2026-09-19)

Kilid prensip: "K4, diger K4'lerden aldigi relational coincidence
bilgisini kendi elektriksel durumuna entegre eden, K1-K3 ile soma
uzerinde paralel calisan gercek bir compartment'tir."
Ayrisim: K1-K3 = "ne oldu?", K4 = "baska nerede/ney ile birlikte oldu?",
Soma = "ateslemeye deger mi?"
Tasarim: K1/K2/K3 paralel + frozen (F1'e dokunulmaz); K4 dal-basina
gercek compartment (voltaj/leak/gating/esik/spike hepsi kullanilir;
olu state biter); K4<->K4 max-secim (toplam-yerine; argmax = top
partner, telemetri + mekanizma); kimlik kuantize imza (esikler mevcut
0.15/0.5/1.0; boolean agree yok); soma = S123(frozen) + S4(K4),
tek esik V_THRESHOLD, eslesik reset; K4-kapali bit-identical.
Yeni sayilar (TODO: DOGRULANMADI): yalniz K4->soma kazanc/tavan
(S4_CAP=0.25 N-turetilmis BASLANGIC siniri, FROZEN DEGIL; U6 pilotu mekanik
dogruladi: gozlenen S4max 0.1765 <= 0.25, cap baglamadi); diger tum esikler
mevcut sabitlerden. Pilot bulgusu: TEST-B'de K4 spike'i 0 -> iliskisel surum
yolu islemedi (argmax pilot-duzeyde degil, yapisal kanitli); DUR, full
battery YOK.
Pathway proof (2026-09-19, OZET-REL-PATHWAY: OK): post8-ikiz deneyinde
tam zincir in-vivo kanitli (r_AB=0.875, karsilikli argmax, spike 1925,
hiz artisi, ikiz soma atesleri, sessizlikte sonum). r tavani 0.875
(fixed-point). HUKUM: relational pathway mekanik olarak calisiyor.
Full battery ayri onaya tabi.
NIHAI KABUL (2026-09-20, kullanici karari): full battery BITTI (99 senaryo,
fails=yok; /tmp/k4bat/REPORT.md). REV4 = NIHAI PATTERN LOB. Donduruldu.
Kapilar: J/N/M/C/P/E/R + yeni S (partner-secicilik). Detay: §9.95.
Degismez: v3e, CMakeLists, f0_baseline, donuk CSV/PNG, diger binaryler.
Pilot yalniz TEST-B + eta=0; full battery YOK (STOP). Yogunluk uyarisi
(kayitli): paylasilan sessizlik de anlasmaya sayilir; seyrek rejimde
cift-sessiz ciftler kapidan gecer — pilot matrisle olculur.
