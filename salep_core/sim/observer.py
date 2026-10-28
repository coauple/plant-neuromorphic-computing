"""Observer Bus + Lobe arayüzü — NPU entegrasyon yuvası.

Sözleşme (HİBRİT Adım 2):
- Dünya `ObserverBus`'ı tanımaz; fizik kendi işini yapar.
- Loblar `on_frame(frame) → durum` ile frame'i okur, `commands()` ile
  komut kuyruğu döner. SET üretimi lobun işidir, dünyanın değil.
- NPU entegrasyonu sonraya bırakıldı: `lobes/plant_npu.py` hazır arayüz,
  runtime bağlantısı entegrasyon adımında yapılacak. Mevcut doğrudan
  köprü (NpuBridge) NPU'lu koşularda aynen çalışır (§9.9, K5).

Anayasa: loblar frame'i OKUR, çekirdeğe dokunmaz; ground truth
frame'e girmez (§0, K6); "stres" etiketi yok (K7).
"""


class Lobe:
    """Tüm lobların uyguladığı arayüz."""

    name = "lobe"

    def on_frame(self, frame: dict) -> dict:
        """Frame'i işle, kendi durum sözlüğünü dön."""
        raise NotImplementedError

    def commands(self) -> dict:
        """Bekleyen komutları dön (örn. {"set": {...}}); yoksa {}."""
        return {}


class ObserverBus:
    """Frame yayıncısı — dünyayı kimse bloke etmez.

    publish(frame) → {lob_adı: (durum, komut)} döner. Lob içi hata
    bus'ı devirmez (hata durum sözlüğüne işlenir).
    """

    def __init__(self):
        self._lobes: list = []

    def subscribe(self, lobe: Lobe):
        self._lobes.append(lobe)
        return lobe

    def unsubscribe(self, name: str) -> bool:
        before = len(self._lobes)
        self._lobes = [l for l in self._lobes if l.name != name]
        return len(self._lobes) < before

    @property
    def lobe_names(self) -> list:
        return [l.name for l in self._lobes]

    def publish(self, frame: dict) -> dict:
        out = {}
        for lobe in self._lobes:
            try:
                state = lobe.on_frame(frame)
                cmd = lobe.commands()
            except Exception as e:  # lob hatası bus'ı devirmez
                state = {"error": f"{type(e).__name__}: {e}"}
                cmd = {}
            out[lobe.name] = (state, cmd)
        return out
