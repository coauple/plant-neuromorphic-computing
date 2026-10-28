# P0b — Tren-Sürüş Hipotezi (PRE-REGISTERED, 2026-09-16)

Statü: P0'ı kurtarma DEĞİL, yeni hipotez. P0 (tek-darbe rejimi)
başarısız rejim olarak donuk kalır; bu dosya ayrı rejimi test eder.
"Sonuç çıkana kadar sürüşü ayarla" yasaktır (aşağıdaki Kilit 4).

## 1. Rejim farkı (açık beyan)

P0: dal başına TEK darbe, amp=1.0 → E1–E5 sessiz (G3/G4/G5 FAIL).
P0b: dal başına 5-darbeli tren, ISI=12, amp=1.0 (genlik AYNI —
ayarlanan tek şey darbe sayısı/zamanlaması).

Parametre gerekçesi (sonuçtan bağımsız, yapısal): ISI=12 yavaş
bandın tau'sudur (§9.8 iki-bant sınırı {4,12}); 5×12=48 tick tren
Δt≤60 ile 200-tick ufka sığar (50+60+48=158<200); amp=1.0 P0 ile
aynı tutulur. DÜRÜST NOT: /tmp probu bu noktanın ateşlediğini
önceden gördü (keşif) — P0b onun doğrulayıcı tekrarıdır; keşif
gizlenmiyor, veri olarak kullanılmıyor.

## 2. Hipotez H-P0b

Tren rejiminde P3 `max soma_V`, Δt∈{5,10,30}'u ≥3 seviyeye ayırır
(G3'); sıra asimetrisi >0'dır (G4'); tepki `f(Δφ)`'dir (G5').

## 3. Matris (P0 ile aynı iskelet, tren sürüşü)

E1' Δt 16 değer · E2' sıra×{5,10,30} · E3' φ_B 12 slot · E4'
φ_A∈{0,120,240}×Δφ 12 değer · E5' Δφ∈{30,90,180}×w_ring 4 değer ·
E6' tek-TREN (yalnız A / yalnız B, amp=1.0 sabit — amp sorusu
P0'da cevaplandı) · E7' 2× tekrar. K1-b E2'–E7'de tau=4 (P0 ile
aynı kural), E1' tau ızgarası geçici tarama etiketli.

## 4. KİLİT — anti-tuning kuralı (bu deneyin omurgası)

1. P0b BİR kez koşar; n/ISI/amp/w_ring P0b içinde ASLA değiştirilmez.
2. `p0b_analyze.py` koşudan önce kilitli K1 kuralını uygular ve
   manifestteki tren parametrelerinin buradaki değerlere eşitliğini
   assert'ler (uyumsuzluk = sert hata, analiz yok).
3. Her sonuç (tam FAIL dahil) aynen raporlanır; devamı yeni
   hipotezdir (P0c…), sessiz yeniden-ayar YOK.

## 5. Kapılar

G1 determinizm (sert). G2' tek-tren dalları — ÖLÇÜM: PASS/FAIL ne
çıkarsa yorumu önceden kilitli (tek-tren ateşlerse tren rejimi
coincidence-gating'i yapısal değil sürüş-bağımlı kılar). G3' ≥3
soma seviyesi · G4' sıra>0 · G5' `f(Δφ)` · G6' M3>1 (E6'-dışı
varyasyon şartıyla — yalnız-amp varyasyonu G6-PASS sayılmaz).

## 6. K1 karar kuralı (koşudan önce kilitli, üç çıkışlı)

- K1-b kazanır ⟺ M8_res4 kapasitesi > M8_ring VE G5' resonant'ta PASS.
- RING kazanır ⟺ simetrik tersi.
- Aksi halde KARARSIZ (zorunlu seçim YOK — bu da bulgudur).
Kapasite = M3 (E6'-dışı) + M4 seviyeleri + M5/M7 mesafeleri toplamı;
analizörde tek skor formülüyle hesaplanır.
