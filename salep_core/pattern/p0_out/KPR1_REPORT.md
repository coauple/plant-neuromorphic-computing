# KPR1_REPORT — AŞAMA 1 Hükmü (2026-09-16)

Soru: d=1'deki 12/12'nin kaynağı K1 mi? Cevap: HAYIR (aşağıda).
Teşhis modu: Aşama 2 açılmadı, mimari kararı verilmedi, C++ yok.
Faz 0: K1 bit-eşit OK · K2 regresyon d0→7/d1→12 OK · K3 determinizm OK ·
K4 8-hash bekçisi OK. 38 kol, 456 sim.

## Kol tablosu (N_sig/12 · Δ_d · amp_break · S_share)

```
kol          d0   d1   Δ_d   amp_break(d1)   S_share(d1, kol-ort)
A0 normal     7   12    +5       —              0.027
A1 k1_ablate  1   12   +11       —              0.005 (pasif kalıntı)
A2 k23_ablate 7    7     0       —              0.245 (sürülen-birim 0.98; sessiz 0)
A3 coinc-lock 7   12    +5       —              0.027
A4 coinc-off 11   12    +1       —              0.027
A5 amp        —    —     —       0.1            —
A6 amp+k1abl  —    —     —       0.1            —
L1 legacy     1   12   +11       —              0.348*
L2 leg-k1abl  1   12   +11       —              0.000
```

A5 d0 eğrisi: 0.05→1, 0.1→1, 0.2→11, 0.3→11, 0.5→7, 1.0→7 (monotonik DEĞİL;
tatlı-nokta 0.2–0.3, doygunluk üstte öldürür).
A5 d1: 0.05→3, 0.1→3, 0.2+→12. A6 d1 ≡ A5 d1 bit-bit aynı (K1 katkısı SIFIR).
\* legacy farklı işlemsel tanım (enjeksiyon-paylaşımı).

## 3 yönlü hüküm (ön-kayıtlı kural)

B = N(A1,d1) = 12, C = N(A2,d1) = 7, N = 12.

**HAYIR: K1, 12/12 İÇİN GEREKLİ DEĞİL → Aşama 2 YANLIŞ HEDEF. Dur, yeniden düşün.**

- Δ_d K1'siz de +11 (A1): zaman etkisi K2/K3 (+coincidence altyapısı) üzerinden.
- K1'siz d0 çöküyor (7→1): K1 eşzamanlı-rejimde 6 kanal taşıyor (7 vs 1).
- A2 (yalnız K1): d0=d1=7 — gecikme K1-yoluyla İŞLEMİYOR (Δ_d=0).
- A4: bonus KAPALIYKEN d0 7→11 — bonus eşzamanlı-rejimde ayrıştırmayı BASTIRIYOR;
  d1'de 12 (gerekli değil). Bonus taşıyıcının parçası değil, düzenleyicisi.
- C=12 çıkmadı (K2/K3'süz 12 yok) — sürpriz "K2/K3 gereksiz" bulgusu YOK.

## Nüans (hükmü değiştirmeyen gerçek sinyal)

Merkez-eşleşen birimde S_share 0.20, diğerlerinde 0.005 (A0 d1 s4: P3b 0.197).
K1 payı slot-seçici ve 40× farklı — ama N_sig düzeyinde d1 rejimini K2/K3 belirliyor.

## Sonrası (kapalı)

Aşama 2 (projeksiyon) bu hükümle HEDEFSİZ kaldı — açılmadı. S_share kol-ortalaması
sürülen+sessiz birimleri karıştırır (A2: sürülen 0.98, sessiz tanımsız→0);
birim-düzeyi tablo `kpr1_budget.json` + üstte. DURULDU.
