"""Simülasyon yayıncısı — ayrı süreç, ayrı çekirdek (W0 sonrası tek yayıncı).

Tasarım (kullanıcı kararı): simülasyon kendi başına koşar (istemci
yokken bile ilerler); görselleştirme ayrı süreçte TCP'den okur.
NPU bu döngüde YOK — sonradan lob olarak entegre edilecek.

Protokol: TCP 127.0.0.1:PORT, NDJSON satırları (world_state.v2).
latest-wins: sunucu 5 Hz'de EN YENİ frame'i yazar; istemci okurken
aradakileri atar → saat senkronu gerekmez.
Komutlar (istemci→sunucu, satır JSON): pause/resume/speed/water/
fert/drought — sula/gübre pending kuyruğuna (G5 disiplini).

Kullanım:
    .venv/bin/python -m sim.serve [--port 41790] [--speed 4]
                                   [--ticks 0] [--record out/live.jsonl]
                                   [--scenario drought]
Anayasa: §0 (ground_truth yok — frame_to_dict garantisi), §9.9
(çekirdeğe dokunulmaz), K5/K6/K7 host tarafı.
"""
import argparse
import json
import os
import socket
import sys
import threading
import time

SIM_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.dirname(SIM_DIR)
if CORE_DIR not in sys.path:
    sys.path.insert(0, CORE_DIR)

from sim.world_state import WorldState
from sim.sensor_map import SensorMapper
from sim.frame import Frame, compute_visuals, frame_to_dict
from sim.sensory_chain import SensoryChain

DEFAULT_PORT = 41790
SEND_HZ = 5.0


class WorldServer:
    """Fizik döngüsü + TCP yayın + komut uygulama."""

    def __init__(self, seed=42, speed=4.0, scenario=None,
                 weather_csv=None, weather_year=None, weather_uv=None,
                 chain=True, chain_events=300, chain_dir=None):
        self.world = WorldState(seed=seed, speed=speed,
                                weather_csv=weather_csv,
                                weather_year=weather_year,
                                weather_uv=weather_uv)
        self.mapper = SensorMapper()
        # Canli zincir (duyusal->kosul->oruntu, §9.96): kareye
        # dokunmaz, yalniz okur; binary yoksa kendiliginden kapanir.
        self.chain = None
        self._chain_day = None
        if chain:
            self.chain = SensoryChain(events_per_window=chain_events,
                                      outdir=chain_dir)
            self.chain.start()
        if scenario == "drought":
            self.world.inject_scenario(
                {d: {"force_no_rain": True} for d in range(0, 220)})
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._latest = ""
        self._tick_count = 0

    def stop(self):
        self._stop.set()

    def apply_command(self, cmd: dict):
        """İstemci komutu → dünya (kilitli). Bilinmeyen komut yok sayılır."""
        name = cmd.get("cmd")
        try:
            if name == "pause":
                self.world.clock.pause()
            elif name == "resume":
                self.world.clock.resume()
            elif name == "speed":
                # Hız emri çalıştırma niyetidir: kilitliyse önce sürdür.
                self.world.clock.resume()
                self.world.clock.set_speed(float(cmd.get("v", 1.0)))
            elif name == "water":
                self.world.inject_irrigation(float(cmd.get("mm", 20.0)))
            elif name == "fert":
                self.world.inject_fertilizer(float(cmd.get("mass", 30.0)))
            elif name == "drought":
                day = self.world.clock.sim_day
                self.world.inject_scenario(
                    {d: {"force_no_rain": True} for d in range(day, day + 60)})
            elif name == "soil":
                self.world.set_soil(cmd.get("preset", "tınlı"))
            elif name == "seeds":
                print(f"TOHUM {json.dumps(self.world.describe_plants())}",
                      flush=True)
        except (TypeError, ValueError):
            pass

    def _build_frame(self) -> Frame:
        snap = self.world.get_snapshot()
        fert = snap.get("fert_dose", 0.0)
        sensors = self.mapper.update(snap, fert_dose=fert)
        f = Frame()
        f.sim_day = snap["sim_day"]
        f.day_frac = self.world.clock.day_frac
        f.day_of_year = snap["day_of_year"]
        f.temp = snap["temp"]
        f.display_temp = snap.get("display_temp", snap["temp"])
        f.temp_soil = snap.get("temp_soil", snap["temp"])
        f.photoperiod = snap["photoperiod"]
        # Gökyüzü CANLI saatten: snapshot güneş/gök değeri günlük adımda
        # donar (step_if_needed), oysa day_frac kareler arası akar.
        # Fizik değişmez — yalnız yayınlanan display alanı tazelenir.
        _live_frac = self.world.clock.day_frac
        _sun_alt, _sun_az, _sky = WorldState.sun_position(
            _live_frac, snap["photoperiod"])
        f.sun_alt_deg = _sun_alt
        f.sun_az_deg = _sun_az
        f.sky = _sky  # snapshot satırı kaldırıldı (yukarıda canlı hesap)
        f.rain_mm = snap["rain_mm"]
        f.stage = snap["stage"]
        f.stage_age = snap.get("stage_age", 0)
        f.leaf_health = snap["leaf_health"]
        f.root_health = snap["root_health"]
        f.tuber_mass = snap["tuber_mass"]
        f.water_balance = snap["water_balance"]
        f.soil_moisture = snap["soil_moisture"]
        f.soil_ec = snap["soil_ec"]
        f.o2_deficit_ticks = snap["o2_deficit_ticks"]
        f.stem_height = snap.get("stem_height", 0.0)
        f.uv_index = snap.get("uv_index")
        f.applied_irrigation_mm = snap.get("applied_irrigation_mm", 0.0)
        f.applied_fert_mass = snap.get("applied_fert_mass", 0.0)
        f.pending_irrigation_mm = snap.get("pending_irrigation_mm", 0.0)
        f.pending_fert_mass = snap.get("pending_fert_mass", 0.0)
        f.paused = snap.get("paused", self.world.clock.paused)
        f.speed = self.world.clock.speed
        f.events = snap.get("events", [])
        for k, v in sensors.items():
            setattr(f, k, v)
        return compute_visuals(f)

    def physics_loop(self, max_ticks=0):
        """20 Hz fizik; snapshot tazelenir (istemci olmasa da koşar)."""
        dt = 0.05
        n = 0
        while not self._stop.is_set():
            t0 = time.monotonic()
            self.world.clock.tick(dt)
            self.world.step_if_needed()
            self.world.refresh_display()
            snap = self.world.get_snapshot()
            if snap:
                f = self._build_frame()
                d = frame_to_dict(f, wall_t=time.time())
                # Lob canlisi (frame.py'de yayinciya birakilan lobes):
                # zincir varsa hafif snapshot, yoksa/kapalisa anahtar yok
                # (panel "zincir kapali" gosterir, uydurma yok).
                if self.chain is not None and not self.chain.disabled:
                    try:
                        d["lobes"] = self.chain.lobes_snapshot()
                    except (OSError, ValueError, AttributeError):
                        pass
                with self._lock:
                    self._latest = json.dumps(d, separators=(",", ":"))
                # Zincir besleme: gun degisince 7 sensoru SET'le (salt-okuma).
                if self.chain is not None and not self.chain.disabled:
                    day = self.world.clock.sim_day
                    if day != self._chain_day:
                        self._chain_day = day
                        self.chain.feed({
                            k: getattr(f, k, None)
                            for k in ("hs", "ts", "hn", "tn",
                                      "ph", "npk", "ec")})
            n += 1
            if max_ticks and n >= max_ticks:
                break
            time.sleep(max(0.0, dt - (time.monotonic() - t0)))
        self._stop.set()

    def serve_loop(self, port, record_path=None):
        """TCP yayın (5 Hz latest-wins) + komut okuma."""
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", port))
        srv.listen(1)
        srv.settimeout(0.2)
        rec = open(record_path, "a", encoding="utf-8") if record_path else None
        conn = None
        last_send = 0.0
        try:
            while not self._stop.is_set():
                if conn is None:
                    try:
                        conn, _ = srv.accept()
                        conn.setblocking(False)
                    except socket.timeout:
                        pass
                if conn is not None:
                    # Komutlar (non-blocking, satır bazlı)
                    try:
                        data = conn.recv(4096)
                        if not data:
                            conn.close()
                            conn = None
                        else:
                            for line in data.decode("utf-8",
                                                    "replace").splitlines():
                                line = line.strip()
                                if line.startswith("{"):
                                    try:
                                        self.apply_command(json.loads(line))
                                    except json.JSONDecodeError:
                                        pass
                    except BlockingIOError:
                        pass
                    except (ConnectionResetError, BrokenPipeError):
                        conn.close()
                        conn = None
                    # Yayın (5 Hz latest-wins)
                    now = time.monotonic()
                    if now - last_send >= 1.0 / SEND_HZ:
                        last_send = now
                        with self._lock:
                            line = self._latest
                        if line and conn is not None:
                            try:
                                conn.sendall((line + "\n").encode("utf-8"))
                                if rec:
                                    rec.write(line + "\n")
                            except (ConnectionResetError, BrokenPipeError):
                                conn.close()
                                conn = None
                else:
                    time.sleep(0.05)
        finally:
            if conn is not None:
                conn.close()
            srv.close()
            if rec:
                rec.close()
            self._stop.set()


def main():
    ap = argparse.ArgumentParser(description="Salep simülasyon yayıncısı")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--speed", type=float, default=4.0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--ticks", type=int, default=0,
                    help="fizik tick sayısı (0=sonsuz; kapılar için sınırlı)")
    ap.add_argument("--record", default=None)
    ap.add_argument("--scenario", default=None, choices=[None, "drought"])
    ap.add_argument("--weather-csv", default=None,
                    help="gerçek gözlem dosyası (Open-Meteo günlük, §9.26)")
    ap.add_argument("--weather-year", type=int, default=None,
                    help="sim günü 0 = 1 Oca bu yıl (varsayılan: dosyanın son yılı)")
    ap.add_argument("--weather-uv", default=None,
                    help="UV gözlem dosyası (Open-Meteo günlük, §9.27)")
    ap.add_argument("--chain", dest="chain", action="store_true",
                    default=True,
                    help="canlı duyusal->koşul->örüntü zinciri (§9.96)")
    ap.add_argument("--no-chain", dest="chain", action="store_false",
                    help="zinciri kapat (yalnız fizik + yayın)")
    ap.add_argument("--chain-events", type=int, default=300,
                    help="örüntü penceresi başına afferent olay eşiği")
    ap.add_argument("--chain-dir", default=None,
                    help="zincir çıktı dizini (varsayılan: geçici dizin)")
    args = ap.parse_args()

    server = WorldServer(seed=args.seed, speed=args.speed,
                         scenario=args.scenario,
                         weather_csv=args.weather_csv,
                         weather_year=args.weather_year,
                         weather_uv=args.weather_uv,
                         chain=args.chain,
                         chain_events=args.chain_events,
                         chain_dir=args.chain_dir)
    phys = threading.Thread(target=server.physics_loop,
                            kwargs={"max_ticks": args.ticks or 0},
                            daemon=True)
    phys.start()
    chain_state = "kapali"
    if server.chain is not None:
        chain_state = "acik" if not server.chain.disabled else "binary-yok"
    print(f"READY port={args.port} speed={args.speed} chain={chain_state}",
          flush=True)
    print(f"TOHUM {json.dumps(server.world.describe_plants())}",
          flush=True)
    server.serve_loop(args.port, record_path=args.record)
    phys.join(timeout=5)
    if server.chain is not None:
        server.chain.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
