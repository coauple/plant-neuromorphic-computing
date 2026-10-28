# bench/REAL_DATA_SEARCH.md — gerçek veri arama günlüğü (AŞAMA 7)

Tarih: 2026-10-15. Yöntem: web araması + API/lisans/indirme doğrulaması.
Hiçbir aday uydurulmadı; reddedilenler gerekçesiyle listeli.

## Kabul edilen

- **A library of electrophysiological responses in plants** (DesRosiers vd.)
  - URL: https://tandf.figshare.com/articles/dataset/25425920
  - DOI: 10.6084/m9.figshare.25425920.v2 (API ile doğrulandı)
  - Lisans: **CC BY 4.0** (API `license.name`, araştırma kullanımına uygun;
    atıf şartı REPORT'ta yerine getirilecek)
  - İçerik: 22 bitki cinsi, Backyard Brains kayıtları (.wav, çoğunluk 10 kHz
    mono 16-bit, 15–80 sn) + `-events.txt` uyaran işaretleri (saniye).
    249 kayıt (10 kHz mono + events) kullanılabilir durumda sayıldı.
  - Dosya: `kpsb_a_2310977_sm0241.rar` (67.581.219 bayt,
    md5 API: 4e720f041014c8db4186b25f0de271dc — indirme sonrası doğrulanacak)
  - Kullanım: Ocimum alt-kümesi (38 kayıt, kayıt-başına 1–2 uyaran).
    Seçim kuralı (kör): "10 kHz mono + events çifti en çok olan cins".
  - Sınır: makaleye göre bitkilerin ~%60'ı yanıtl ı; zemin-gerçeklik zayıf
    (uyaran var ≠ yanıt var). Etki: AUC üst sınırı düşük olabilir; bu,
    çekirdeğin değil etiketlerin sınırı olarak raporlanacak.

## Reddedilen / kullanılmayan

- Zenodo 21810489 ("Plant Electrophysiology..." .docx): veri değil, derleme
  belgesi — RED (sinyal yok).
- Chatterjee vd. 2014 (Royal Society, bitki uyaran-sınıflandırma): makale açık
  ama ham kayıt dosyası/depo bağlantısı bulunamadı — RED (erişilebilir veri yok).
- PlantES platformu (MDPI): analiz platformu tanıtımı; doğrudan indirilebilir
  etiketli kayıt seti sunmuyor — RED (erişilebilir veri yok).
- Kim vd. 2023 (biber PIES, Sci Rep): açık makale; ham kayıt deposu
  makalede belirtilmemiş — RED (erişilebilir veri yok, zaman kısıtı).

## Tekrar-üretim

`bench/stage7.sh fetch`: figshare API'den taze imzalı URL alır, rar'ı
`bench/real_data/` altına indirir, md5'i API kaydıyla karşılaştırır,
Ocimum alt-kümesini `bench/real_data/work/` altına çıkarır (unrar:
apt `unrar` paketi root'suz `apt-get download` + `dpkg-deb -x` ile alınır).
Ağ/paket yoksa aşama, gerekçesiyle "atlandı" raporlanır (uydurma yok).
