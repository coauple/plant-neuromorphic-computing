"""npu_plant_npu --stream alt-süreç köprüsü.

SINIR KATMANI: NPU tarafına import YOK (live_term dahil). TELE_RE deseni
live_term.py L78-86'dan birebir alıntıdır (provenance notu); bu dosya
stdlib-only'dir — sim tarafı NPU modüllerini görmez, NPU tarafı sim'i
görmez. Tek buluşma: alt-süreç sınırı (stdin komut / stdout telemetri).

Anayasa kuralları:
  K5: Çekirdeğe dokunulmaz, köprü tamamen host tarafında.
  K1: Tek süreç, sıfır soket — NPU alt-süreç, GUI aynı süreçte.
"""
import os
import re
import subprocess
import threading
import queue
import time

# Kanıtlanmış desen (live_term.py L78-86'dan alıntı, import yerine kopya —
# alan ayrılığı: sim NPU modüllerine bağımlı olamaz, bkz. G11).
TELE_RE = re.compile(
    r"^T\s+(\d+)\s+wire=([0-9.]+)\s+f=([01]{9})\s+w=([0-9.,]+)\s+cc=([0-9,]+)"
)


def parse_telemetry(line: str) -> dict | None:
    m = TELE_RE.match(line)
    if not m:
        return None
    return {
        "t": int(m.group(1)),
        "wire": float(m.group(2)),
        "f": m.group(3),
        "w": [float(x) for x in m.group(4).split(",")],
        "cc": [int(x) for x in m.group(5).split(",")],
    }


# Binary yolu: bu dosyanın üst dizini (salep_core). sys.path'e eklenmez —
# sınır katmanı NPU modüllerini import etmez, yalnız binary'yi çalıştırır.
NPU_BIN = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "npu_plant_npu")


class NpuBridge:
    """NPU --stream alt-sürecini yönetir.

    Thread modeli:
      - _reader_loop: stdout'u dinler, TELE_RE ile parse eder
      - Ana thread (veya fizik thread'i): send() ile komut gönderir
      - GUI thread: get_latest_telemetry() ile son snapshot'ı okur
    """

    def __init__(self, bin_path: str | None = None):
        self.bin_path = bin_path or NPU_BIN
        self.proc: subprocess.Popen | None = None
        self._reader_thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._tele_queue: queue.Queue = queue.Queue(maxsize=64)
        self._latest_tele: dict | None = None
        self._tele_lock = threading.Lock()
        self._event_log: list = []  # OK/ERR mesajları

    def start(self):
        """NPU sürecini başlat."""
        if not os.path.isfile(self.bin_path):
            raise FileNotFoundError(f"NPU binary bulunamadı: {self.bin_path}")

        env = os.environ.copy()
        env["ASAN_OPTIONS"] = "detect_leaks=0"  # §9.9 kısıtı

        self.proc = subprocess.Popen(
            [self.bin_path, "--stream"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # satır tamponlu
            env=env,
        )
        self._stop.clear()
        self._reader_thread = threading.Thread(
            target=self._reader_loop, daemon=True, name="npu-reader"
        )
        self._reader_thread.start()

    def _reader_loop(self):
        """Stdout okuyucu thread — live_term.py'nin kanıtlanmış deseni."""
        try:
            for line in self.proc.stdout:
                if self._stop.is_set():
                    break
                line = line.rstrip("\n")
                if not line:
                    continue

                # Telemetri satırı mı?
                tele = parse_telemetry(line)
                if tele:
                    with self._tele_lock:
                        self._latest_tele = tele
                    try:
                        self._tele_queue.put_nowait(tele)
                    except queue.Full:
                        try:
                            self._tele_queue.get_nowait()  # eski at
                        except queue.Empty:
                            pass
                        self._tele_queue.put_nowait(tele)
                else:
                    # OK/ERR/OZET satırları
                    self._event_log.append(line)
                    if len(self._event_log) > 200:
                        self._event_log = self._event_log[-100:]
        except (OSError, ValueError):
            pass  # süreç kapandı

    def send(self, cmd: str):
        """Motor komutları gönder (SET/RESET/QUIT/SENSOR_OFF|ON)."""
        if self.proc and self.proc.stdin and self.proc.poll() is None:
            try:
                self.proc.stdin.write(cmd + "\n")
                self.proc.stdin.flush()
            except (OSError, BrokenPipeError):
                pass

    def set_sensors(self, values: dict[str, int]):
        """7 sensör değerini toplu SET et."""
        for sensor, val in values.items():
            self.send(f"SET {sensor} {val}")

    def get_latest_telemetry(self) -> dict | None:
        """Son telemetri snapshot'ı (thread-safe)."""
        with self._tele_lock:
            return dict(self._latest_tele) if self._latest_tele else None

    def drain_events(self) -> list[str]:
        """Birikmiş OK/ERR/OZET mesajlarını al ve temizle."""
        events = list(self._event_log)
        self._event_log.clear()
        return events

    def is_alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def stop(self):
        """Temiz kapanış protokolü (live_term.py'den miras)."""
        self._stop.set()
        if self.proc and self.proc.poll() is None:
            try:
                self.send("QUIT")
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
