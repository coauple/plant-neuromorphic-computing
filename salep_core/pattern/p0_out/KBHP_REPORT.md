# KBHP_REPORT — Kilitli Hüküm + Kapanış Belgesi (2026-09-16)

Teşhis modu: çözüm seçilmedi, implemente edilmedi, kazanan ilan edilmedi.
C++ değişikliği yok. G-A yeşil (`p0_out/kbp_fidelity.json`).
59 kol (57 v2 + 2 legacy), ~630 sim. Deterministik, RNG yok.

## Eksen tablosu (N_sig/12 · N_pair/6 · N_pv · L4 · S_share)

Tek-slot N_sig (R0/R1/R2 × id/sep × d):

```
v2  R0·id : d0=7  d1=12 d2=12 d4=12 d6=12
v2  R1·id : d0=11 d1=12 d2=12 d4=12 d6=12
v2  R2·id : d0=11 d1=12 d2=12 d4=12 d6=12
v2  sep   : R0/R1/R2 d0=11, d≥1=12 (nat ve CL AYNI — bonus-zorlama etkisiz)
legacy    : 1/12 (R0·id·d0)
```

Çift N_pair (12 kolun TAMAMI): distinct=1/6, selective=0/6.
T1 çift-kablolama etkisi YOK (T0 ile özdeş).

L4: v2 d0=0.494 (tüm d'de aynı — nabız sayısı sabit, kayma etkisiz);
legacy d0=0.725 (d1+ legacy kolu YOK → null, ölçülmedi).
S_share: v2 = 0.027 (tüm d; ön-değer %30 ÇÜRÜTÜLDÜ);
legacy = 0.348 (enjeksiyon-paylaşımı; farklı işlemsel tanım, yan yana).

## G kapıları

- G-A SADAKAT: OK (step-equiv + cable-repro + binary-sets + frozen-sha).
- G-B TAŞINMA: GEÇTİ — R0·id·d1 = 12/12 (≥10/12). "K1 soma'ya taşınıyor."
- G-C SEÇİCİLİK: KALDI — en iyi kol 1/6 distinct, 0/6 selective (≥5/6 yok).
  "Çift seçiciliği var" DENEMEDİ → GÖZLENMEDİ.
- G-D NEGATİF: tüm kollar amp=1.0 kilitli → genlik-konfounder yapısal dışlanır.
  16× önermesi plan-aslîdir; KBHP matrisinde genlik ekseni YOKTUR (aşağıda).

## Hüküm

- GEREKLİ+YETERLİ eksen: `zaman` (d≥1 tek başına 12/12 kapatır).
- `okuma` ① EK katkı VERİR (zaman kapalıyken R0=7 → R1/R2=11, +4 kanal).
- `parite` ②: sep≈id (Dal-B sürüşü N_sig'e katkı ~0 — dal-parite null bulgusu).
- `topoloji` ③: T1=T0 (çift-kablolama seçicilik üretmedi).
- `coinc`-kilit: nat ile özdeş (bonus-zorlama etkisiz bu rejimde).
- Tavanla: v2 N_seq=12 (R1+ ile), paralel tavan 6; legacy N_seq=1, tavan 1.
- ①'in yanıtı sayıyla: K1 kök-sürüş payı %2.7 (yelpaze-seyreltmesi);
  legacy enjeksiyon-paylaşımı %34.8 (farklı tanım).

## İddia Defteri (plan-aslî 9 cümle aynen + KBHP notu)

| İddia (aynen) | Etiket (aynen) | KBHP notu |
|---|---|---|
| `g[A_K1]` üretiliyor, `eff_g=g[0]` onu okumuyor (7 komp'un 6'sı atılıyor) | KANITLANDI | R1/R2 okuma +4 kanal ekledi (7→11) — okunmayan kısımda bilgi VARMIŞ |
| K1'in üretim genliği, kök gating'ini tek başına açamıyor (`g[0]=0`, 0 ateş) | KANITLANDI | Forensik A-koşulu ile tutarlı (K1-tek başına ateşletemez) |
| Genlik 16× artışı ayrıştırmayı değiştirmiyor (`N_sig 1/12` sabit) | KANITLANDI | Plan-aslî; KBHP'de genlik ekseni yok — KBHP'nin kendi kontrolü amp-kilididir (tüm kollar 1.0). 16× bağımsız tái-üretilmedi |
| `TOPLA-g` okuma, A/B özdeşken katkısız (`N_sig 1/12`) | KANITLANDI | Plan-aslî; KBHP'de parite=sep (B-sessiz) kolu id ile özdeş N verdi (11/12) — yakınsayan bağımsız kanıt |
| Çift-kablolama / eşzamanlılık seçiciliği | TEST EDİLMEDİ ← v2.1'in asıl işi | TEST EDİLDİ → GÖZLENMEDİ: 12 kolun tamamı 0-1/6. Etiket GÜNCELLENDİ (veri) |
| "K1'i güçlendirmek örüntüyü ayırt eder" | GÖZLENMEDİ | KBHP ekliyor: A1b-KBH'de oran 4× bile v2 N=3'te kaldı (spike-düzeyi) |
| "Δslot=3 → periyod-3 faz yapısı" | GÖZLENMEDİ | Değişmedi |
| "Madencilik ↔ geometri çapraz doğrulama" | GÖZLENMEDİ | Değişmedi |
| `(1,4)×37 …` tablo | TEST EDİLMEDİ — SPEC-uyumlu kaynaktan yeniden üretilemedi | ÜRETİLDİ: E0 kablosundan (1,4)×58 + 5 çift daha (`kbp_pairs.json`); D-A ataması kuralı kilitli. Etiket GÜNCELLENDİ (kısmi: TEST-B-tablosu değil, E0-tablosu) |

## Sonrası (kapalı)

Mimari fazı, S6 tablosu, B-K1 alan kararı AÇILMADI. Rapor yazıldı, tablo basıldı,
DURULDU.
