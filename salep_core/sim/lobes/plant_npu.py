"""Bitki NPU lobu — entegrasyon yuvası (şu an UYUYOR).

Durum: simülasyon NPU'dan ayrı kurgulanıyor; NPU sisteme sonradan
entegre edilecek. Bu lob, o günkü bağlantı noktasıdır: frame'deki
7 sensörü throttled SET komutlarına çevirir, gönderimi kendisi yapmaz
(app komut kuyruğunu tüketir).

Anayasa: lob yalnız frame OKUR (§0/K6); çekirdek değişmez (§9.9/K5);
"stres" etiketi yok (K7). ph/npk DOĞRULANMADI işaretleri sensor_map'te.
"""
from sim.observer import Lobe

SENSORS_7 = ("hs", "ts", "hn", "tn", "ph", "npk", "ec")


class PlantNpuLobe(Lobe):
    """Frame sensörleri → throttled SET komutları."""

    name = "plant_npu"

    def __init__(self, every_n_frames: int = 10):
        self.every = max(1, int(every_n_frames))
        self._count = 0
        self._pending: dict = {}
        self.sent_batches = 0  # G9 sayacı

    def on_frame(self, frame: dict) -> dict:
        """Her frame'de çağrılır; kuyruk dolunca komut üretir.

        7 kanalın 7'si de frame'den gelir (§9.33) — eksik kanal
        KeyError ile yüksek sesle batar, 50 gibi uydurma değer YOK.
        """
        self._count += 1
        sensors = {k: int(frame[k]) for k in SENSORS_7}
        if self._count % self.every == 0:
            self._pending = dict(sensors)
            self.sent_batches += 1
            return {"sent": True, "tick": self._count}
        return {"sent": False, "tick": self._count}

    def commands(self) -> dict:
        """Bekleyen SET varsa {"set": {...}} döner ve kuyruğu boşaltır."""
        if self._pending:
            cmd = {"set": self._pending}
            self._pending = {}
            return cmd
        return {}
