# V3D READOUT SPEC — olcum dogrulamasi + pattern-okuma testi (ON-KAYIT)

Soru: problem TEMSIL-OKUMA katmaninda mi, CEKIRDEKTE mi?
Cekirdek (v3d C++/frozen/encoder/sensory) DEGISTIRILMEZ. Okuma katmani
AYRI dosya: pattern/readout_v3d.py (salt-okunur mem okur). Ciktilar
stress_out_v2/ (stress_out/ DOKUNULMAZ).

## T/N/B/R kollari (day_jacc: gun-hizali Jaccard, bos-bos=1, bos-dolu=0)
- T tekrar-tavani: ayni senaryo + ayni tohum TEKRAR kosu (beklenti 1.0;
  determinizm kanitiyla ayni olcum). Olculemezse V0 BATTI.
- N gurultu-tabani: ayni senaryo + farkli tohum (G8 uclusu; olculdu 0.82).
- B ayrim: FARKLI senaryo ciftleri; ON-KOSUL: ciftin iki kablosu da md5
  FARKLI (dogru girdi garantisi). B kumesini V0 belirler: adaylar
  {base,irrig,fert,soil,hot,drought} arasindan md5-farkli altkume;
  NPU kosulmadan once assert.
- R fayda: ret_acc (G1 havuzu) + fam_qd (G11 drought sorgusu).

## V0 kapisi (Faz 1 ACILMAZ eger)
margin = T - B > 0 ; B < N ; ret_acc(S0) >= 0.2301 ; fam_qd(S0) >= 0.0
(rapor; kapi 0.40 Faz-1 hedefi) ; T,N,B tanimli ve B != N.
N_sig YALNIZ RAPOR (tavan-etkili, kapi DEGIL).

## V1 G3-rotasyon duzeltmesi
Eski ROT gun-kati (4x500 tick = 40 gun) oldugundan imza-kumesi aynen
korunuyordu (yapi-artefakti). Yeni ROT: ofset 750 tick (gun-kati DEGIL),
yalniz TAM 500-tick bloklar (kismi blok duser). Kapi: setJ(ABC,ROT) < 0.9.

## V2 G5-drought% duzeltmesi
Pencere aktif doneme [47,99] alinir; NPU kosulmadan once
md5(d40)!=md5(d45)!=md5(d50) assert. Assert BASARISIZSA: doygunluk
fizigi (on-kayitli yedek): B kumesine drought% ALINMAZ, raporlanir.

## V3 soguk karari
cold rows==0 ise (beklenti): kapsam-disi; G9 j_bc/j_hc RAPOR EDILMEZ
(crash kapisi aynen). rows>0 ise normal kol.

## V4 yeni stabilite (eski yan yana)
stab_new = 0.5*(|I|/|S1| + |I|/|S2|); S1/S2 = gun sirasiyla ilk/son yari
imza kumeleri, I = kesisim. Bos kume => -1 (rapor).

## V5 G6 uzunluk kontrolu
Tile 3000 tick; long mem tick<=3000'e kirpilarak ayni uzunlukta
Nsig/Npv/rep karsilastirilir (rapor).

## Faz 1 readoutlar (gun -> frozenset(token); Jaccard-uyumlu)
- S0 mevcut: atesleyen birimler kumesi (referans, ZORUNLU).
- S1 top-k: gun-ici en cok atesleyen k=3 birim; esitlikte kucuk id once.
- S2a rank: (sira, birim) ciftleri kumesi; sira = ates-sayisi azalan,
  esitlikte kucuk id once. PARAMETRESIZ.
- S2b oranli: (birim, bin) ciftleri; r = sayi/gun-maksi; bin = -1 (r==0)
  else 1+min(3,int(r*4)).
- S3 ISI: (birim, isibin) ciftleri; birim-global ortalama ISI, kenarlar
  [0,25,50,100,200,inf) -> 0..5; yalniz o gun atesleyen birimler.
- S0-gurultu: S0 + sentetik gurultu (her birim-uyelik p=0.05 flip,
  seed=7). SAHTELEME KONTROLU: kapiyi GECMEMELI (gecerse kapi gecersiz).

Tum readoutlar ayni alt-makineyle: gun-hizali Jaccard (T/N/B),
k=3 LOO nearest-sequence (ret_acc/fam), N_sig solveden.

## Faz 1 hedefi
fam_qd >= 0.40, margin > 0, B < N, benign T korunur (~1.0).

## Faz 2 (KOSULLU — bu turda ACILMAZ)
Faz 1 GECERSE: problem temsil-okuma; CEKIRDEK DOKUNULMAZ (kanit).
Faz 1 GECMEZSE: cekirdek implicate; BONUS/coinc ekseni YALNIZ
kullanici onayiyla ayri turda acilir.

## Iddia defteri (V3'e ait degil, bu spec'e ait)
- G5 within/robust ayni olcummus (farkli tohum); gercek tekrar T ile olculur.
- between=1.0 dejenere (kablo-ayni); B md5-sartli.
- ret_acc(G5)=0.0763 ayni artefakt.
- setJ(ABC,ROT)=1.0 gun-kati artefakti suphesi (V1 test eder).
- N_sig tavan-etkili; kapi degil.
