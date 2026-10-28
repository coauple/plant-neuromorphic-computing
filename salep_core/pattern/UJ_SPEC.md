# UJ — P3 Feedforward-İnhibisyon Motifi (PRE-REGISTERED)

Tarih: 2026-09-16. Karar: K1/K2/K3 DONUK; P3 entegrasyonu düzeltilir.
Motif (kortikal emsal): K3, P3'e uyarım + INH ara-nöronu üzerinden
eş-miktar inhibisyon çağırır (simetri gerekçesi, sonuçtan bağımsız);
K1/K2 yalnız uyarım verir. Eşik oynaması YOK, if-and YOK, dinamik
değişikliği YOK (negatif akım IDEN'de kurulu mekanizma).

## 1. Kablolama (kilitli)

INH: standart morfoloji (P0b P3 parametreleri); Dal-A ← K3[0],
Dal-B ← K3[1] (besleme 1.0, P3 ile aynı). INH ateşleyince P3
köküne −1.0 (INH_AMP, simetri). Sıra: K-tick → INH-enjekte →
INH-tick → P3-enjekte (K + INH) → P3-tick (aynı tick basamak).
Ağırlıklar: episode-özgü UPL-son-durum (donuk, salt-okunur);
öğrenme KAPALI (frozen). Ablasyon izdüşümde: susturulan sınıfın
spike'ları P3'e de INH'a da gitmez (birimler tick'ler).

## 2. Dört koşul (episode başına; UPU 3 episode'u)

K1-only → 0 · K2-only → 0 · K3-only → 0 · JOINT → >0 (P3 spike
sayısı). Hepsi buysa SELECTIVE-JOINT (ilk gerçek kabul).
Aksi → NON-SELECTIVE + tablo (hangi koşul ne).

## 3. Kilitler

Tek koşu; INH_AMP=1.0 sabit (süpürme YOK); analizör manifest
(INH_AMP, ağırlık-kaynak-hash, episode'lar, koşullar) eşitliğini
assert'ler. upl.py/UPU değişmez. Aşırı-inhibisyon (JOINT de 0)
geçerli FAIL'dir (sessiz INH-zayıflatma YOK).

## 4. Fıkra — çift-sürüş kusuru (UN sadakat kapısı yakaladı, 2026-09-16)

uj.py, `UplUnit.tick` içindeki P3-sürüşüne EK olarak kendi
yönlendirmesini uygulayıp P3'ü tick başına 2× enjekte + 2× tick
eder. Hüküm (NON-SELECTIVE) çift-sürüş rejimindedir → COMPROMISED
(silinmedi, yorumlanmaz). Düzeltilmiş rerun: uj2.py (tek-sürüş).
IDEN/IDEN2/T-AMP/UPL/UPU/UAC etkilenmez (tek-sürüş kullanırlar).
