# UNF — Ateşleyen Rejimde Doyum Testi (PRE-REGISTERED)

Tarih: 2026-09-16. Soru: ateşleyen rejimde doyum K3-alone'u
bastırıp joint'i koruyor mu? Rejim, el-ayarıyla DEĞİL doğal
öğrenmeyle üretilir: aynı kural, 20→60 tur (3× maruziyet;
gerekçe: 20 turda w≈1.3 asimptota yürüyordu, 60 tur plato-yakını;
sonuçtan bağımsız tek seçim). Başka hiçbir sayı değişmez.

## 1. Prosedür (kilitli)

unf_train.py: episode başına sıfır UplUnit → 60 tur sürekli +
öğrenme (UPL rejimi aynen) → unf_weights.json. ABORT: eğitimde
P3 hiç ateşlemezse test YOK (rapor).
unf_run.py: sadakat (k=0 vs tek-sürüş yalın-P3, bit-eşit assert)
+ test (k=0.5, dal-eşlemesi, 4 koşul). un.UnUnit aynen.
unf_analyze.py (önce): kilit + hüküm.

## 2. Hüküm (kilitli)

K1/K2/K3-only → 0 · JOINT → >0 ise SELECTIVE-JOINT (doyum
mekanizması ateşleyen rejimde seçicilik üretiyor). Aksi →
NON-SELECTIVE + R-min profili. Aşırı-sürüş (hepsi ateşler) de
geçerli FAIL'dir.
