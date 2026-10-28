"""Salep web yayın katmanı — Starlette (W3, §9.21).

    SINIR: stdlib + starlette + uvicorn dışında import YOK. sim/npu
    iç modülleri import edilmez; tek bağ veridir:
      - sim  → sim/serve.py alt-süreci + TCP NDJSON (world_state.v2)
      - npu  → npu_plant_npu --stream alt-süreci (TELE satırları)
      - mesh → sim/models/salep_meshes.json dosyasından birebir

    Rotalar: /healthz, /ws/world, /ws/npu, / (statik).

    Çalıştırma:
        cd salep_core
        .venv/bin/python -m web.server [--host 127.0.0.1] [--port 8000]
                                                 [--pub-port 41792]
    (hava otomatik: varsayılan weather_v3/W-base.csv yayıncıya verilir;
    --weather-csv ile ezilebilir).
"""

import argparse
import asyncio
import json
import os
import queue
import socket
import subprocess
import sys
import threading
import time
from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket, WebSocketDisconnect

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(ROOT, "web")
STATIC_DIR = os.path.join(WEB_DIR, "static")
SIM_SERVE = os.path.join(ROOT, "sim", "serve.py")
MESH_JSON = os.path.join(ROOT, "sim", "models", "salep_meshes.json")
NPU_BIN = os.environ.get(
    "SALEP_NPU_BIN", os.path.join(ROOT, "npu_plant_npu"))
# Varsayılan hava: tek komutla kalkan sunucu yayıncıya bunu verir (§9.28).
# Bayrakla ezilebilir (--weather-csv). UV varsayılanı YOK (kayıtlı standart
# yok; bayraksızda UV null — G27b kilidi korunur).
# MUTLAK yol zorunlu: sunucu baska dizinden de kalkabilir; goreli yol
# yayinciya ulasamaz, yayinci coker, panel bos kalir (2026-09-21).
DEFAULT_WEATHER_CSV = os.path.join(ROOT, "weather_v3", "W-base.csv")
DEFAULT_PUB_PORT = 41792  # iç yayın (serve.py TCP); çakışırsa --pub-port ile ezilir (§9.36)
_pub_port = DEFAULT_PUB_PORT

_state_lock = threading.Lock()
_latest_frame = None          # son v2 frame (dict)
_pub_alive = False
_pub_extra_args: list = []    # main() doldurur: yayıncıya hava dosyaları
_pub_proc = None
_pub_sock = None              # TEK yayın soketi (oku + komut; serve.py tek istemcili)
_pub_send_lock = threading.Lock()
_seed_read_lock = threading.Lock()  # /seeds komut→satır eşleşmesi (§9.54)


def _pump_publisher():
    """TCP NDJSON → latest-wins yuvası (arka plan thread'i).

    Soket yayın + komut için paylaşılır: serve_loop tek bağlantı
    kabul eder; ikinci soket asla accept'lenmez (ölçüldü).
    """
    global _latest_frame, _pub_alive, _pub_sock
    backoff = 1.0
    while True:
        try:
            s = socket.create_connection(("127.0.0.1", _pub_port), timeout=10)
            f = s.makefile("r", encoding="utf-8", errors="replace")
            with _state_lock:
                _pub_sock = s
                _pub_alive = True
            backoff = 1.0
            for line in f:
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                with _state_lock:
                    _latest_frame = d
        except OSError:
            pass
        finally:
            with _state_lock:
                _pub_alive = False
                _pub_sock = None
        time.sleep(backoff)
        backoff = min(backoff * 2.0, 10.0)


def pub_command(msg: dict) -> bool:
    """Paylaşılan yayın soketinden komut gönder (thread-güvenli)."""
    with _state_lock:
        s = _pub_sock
    if s is None:
        return False
    with _pub_send_lock:
        try:
            s.sendall((json.dumps(msg) + "\n").encode())
            return True
        except OSError:
            return False


def _wait_ready(proc, timeout=25.0):
    """serve.py READY satırını bekler; satırı döndürür (yoksa None).

    Satırda `chain=acik|kapali|binary-yok` yazar — terminale geçirilir,
    panel "zincir kapalı" derse bakılacak ilk yer burasıdır.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return None
        line = proc.stdout.readline()
        if "READY" in line:
            return line.strip()
    return None


def _read_publisher_line(timeout=5.0):
    """Yayıncı stdout'undan tek satır (engelleyici; thread'de çağır).

    Zaman aşımında None döner; takılı okuma thread'i daemon kalır
    (yayıncı komut başına en fazla 1 satır basar, boru şişmez).
    """
    proc = _pub_proc
    if proc is None or proc.poll() is not None or proc.stdout is None:
        return None
    holder = []

    def _rd():
        try:
            holder.append(proc.stdout.readline())
        except Exception:
            pass

    t = threading.Thread(target=_rd, daemon=True)
    t.start()
    t.join(timeout)
    if not holder or not holder[0]:
        return None
    return holder[0].strip()


@asynccontextmanager
async def lifespan(app):
    global _pub_proc
    # Açılış hızı 1x: 5 gerçek-sn'de 1 sim-saati (sakin, akıcı döngü).
    # Hava dosyaları main() --weather-* bayraklarından gelir (§9.28).
    _pub_proc = subprocess.Popen(
        [sys.executable, SIM_SERVE, "--port", str(_pub_port),
         "--speed", str(1 / 120)] + list(_pub_extra_args),
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1)
    _ready_line = await asyncio.to_thread(_wait_ready, _pub_proc)
    if not _ready_line:
        _pub_proc.terminate()
        raise RuntimeError("yayıncı alt-süreç READY vermedi")
    print(f"[web] yayıncı: {_ready_line}", flush=True)
    # Açılış TOHUM satırını tüket (taze /seeds okumaları bayat satır
    # almasın; gelmezse sorun değil — istekler kendi satırını tetikler).
    await asyncio.to_thread(_read_publisher_line, 5.0)
    pump = threading.Thread(target=_pump_publisher, daemon=True)
    pump.start()
    yield
    _pub_proc.terminate()


async def healthz(request):
    with _state_lock:
        alive = _pub_alive
        has_frame = _latest_frame is not None
        has_lobes = isinstance((_latest_frame or {}).get("lobes"), dict)
    return JSONResponse({
        "ok": True,
        "schema": 2,  # world_state frame sözleşmesi (§9.27 v2)
        "publisher_alive": alive,
        "has_frame": has_frame,
        "has_lobes": has_lobes,  # zincir tasiyici ayakta mi (tani destegi)
        "npu_present": os.path.isfile(NPU_BIN) and os.access(NPU_BIN, os.X_OK),
    })


async def mesh_json(request):
    return FileResponse(MESH_JSON, media_type="application/json")


async def seeds(request):
    """GET /seeds: canlı birey listesi (tohum + toprak + parametreler).

    Çerçeve (v2) DIŞI kanal (§9.54): yayıncıya `seeds` komutu gider,
    stdout'taki TOHUM satırı okunup aynen döndürülür. Yayıncı ölü ya
    da satır gelmezse 503.
    """
    def _query():
        with _seed_read_lock:
            if not pub_command({"cmd": "seeds"}):
                return None
            line = _read_publisher_line(timeout=5.0)
            if not line or not line.startswith("TOHUM "):
                return None
            try:
                return json.loads(line[len("TOHUM "):])
            except json.JSONDecodeError:
                return None

    plants = await asyncio.to_thread(_query)
    if plants is None:
        return JSONResponse({"status": "unavailable"}, status_code=503)
    return JSONResponse({"plants": plants})


async def index(request):
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


async def ws_world(ws: WebSocket):
    """/ws/world: v2 frame (5 Hz latest-wins) + istemci komut iletimi."""
    await ws.accept()
    # İlk kareyi bekle (en fazla 10 sn)
    deadline = time.monotonic() + 10.0
    snap = None
    while time.monotonic() < deadline:
        with _state_lock:
            snap = _latest_frame
        if snap is not None:
            break
        await asyncio.sleep(0.1)
    if snap is None:
        try:
            await ws.send_json({"status": "no_frame"})
            await ws.close()
        except WebSocketDisconnect:
            pass
        return
    while True:
        try:
            msg = await asyncio.wait_for(ws.receive_json(), timeout=0.2)
        except asyncio.TimeoutError:
            msg = None
        except WebSocketDisconnect:
            break
        if isinstance(msg, dict) and "cmd" in msg:
            await asyncio.to_thread(pub_command, msg)
        with _state_lock:
            snap = _latest_frame
        if snap is not None:
            try:
                await ws.send_json(snap)
            except WebSocketDisconnect:
                break


def _parse_tele(line):
    """TELE satırı → dict (sınır kopyası, import yok)."""
    parts = line.split()
    if len(parts) < 6 or parts[0] != "T":
        return None
    try:
        kv = {}
        for p in parts[2:]:
            k, v = p.split("=", 1)
            kv[k] = v
        return {
            "t": int(parts[1]),
            "wire": float(kv["wire"]),
            "f": kv["f"],
            "w": [float(x) for x in kv["w"].split(",")],
            "cc": [int(x) for x in kv["cc"].split(",")],
        }
    except (ValueError, KeyError, IndexError):
        return None


SENSORS_7 = ("hs", "ts", "hn", "tn", "ph", "npk", "ec")


def _sim_sensor_sets(frame):
    """v2 frame → 7 SET satırı (NPU yalnız sim değeri yer — §9.33).

    7 kanal tamamsa hepsi gönderilir; biri bile eksikse HİÇBİRİ
    gönderilmez (eksik kanal uydurulmaz, model kendi değerine dönemez).
    """
    s = (frame or {}).get("sensors") or {}
    lines = []
    for k in SENSORS_7:
        try:
            v = int(round(float(s[k])))
        except (KeyError, TypeError, ValueError):
            return []
        lines.append(f"SET {k} {max(0, min(100, v))}")
    return lines


async def ws_npu(ws: WebSocket):
    """/ws/npu: TELE→JSON (latest-wins); binary yoksa offline durumu.

    Model girdisi YALNIZ simülasyondur (§9.33): bağlanınca güncel karenin
    7 sensörü SET'lenir, sim günü ilerledikçe tazelenir.
    İstemciden SET rölesi YOK (manuel enjeksiyon kapalı).
    """
    await ws.accept()
    try:
        proc = subprocess.Popen(
            [NPU_BIN, "--stream"], cwd=ROOT,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1)
    except OSError:
        proc = None
    if proc is None or proc.poll() is not None:
        try:
            await ws.send_json({"status": "offline"})
            await ws.close()
        except WebSocketDisconnect:
            pass
        return

    def _push(frame):
        for line in _sim_sensor_sets(frame):
            try:
                proc.stdin.write(line + "\n")
            except OSError:
                return
        try:
            proc.stdin.flush()
        except OSError:
            pass

    # İlk kareyi bekle (en fazla 10 sn), NPU sim değeriyle başlasın —
    # gömülü g_* öntanımlılarıyla serbest koşu yok.
    deadline = time.monotonic() + 10.0
    first = None
    while time.monotonic() < deadline:
        with _state_lock:
            first = _latest_frame
        if first is not None:
            break
        await asyncio.sleep(0.1)
    pushed_day = None
    if first is not None:
        _push(first)
        try:
            pushed_day = first["sim"]["day"]
        except (KeyError, TypeError):
            pushed_day = None
    q: queue.Queue = queue.Queue(maxsize=4)

    def _reader():
        try:
            for line in proc.stdout:
                d = _parse_tele(line.strip())
                if d is None:
                    continue
                try:
                    q.put_nowait(d)
                except queue.Full:
                    try:
                        q.get_nowait()
                    except queue.Empty:
                        pass
                    q.put_nowait(d)
        except Exception:
            pass

    threading.Thread(target=_reader, daemon=True).start()
    try:
        while True:
            try:
                await asyncio.wait_for(ws.receive_json(), timeout=0.5)
            except asyncio.TimeoutError:
                pass
            except WebSocketDisconnect:
                break
            # İstemci mesajları yalnız bağlantı denetimidir; SET rölesi
            # YOK (§9.33 — modele değer yalnız simülasyondan girer).
            # Sim günü ilerledikçe 7 sensörü tazele.
            with _state_lock:
                cur = _latest_frame
            try:
                cur_day = cur["sim"]["day"]
            except (KeyError, TypeError):
                cur_day = None
            if cur is not None and cur_day != pushed_day:
                _push(cur)
                pushed_day = cur_day
            latest = None
            while True:
                try:
                    latest = q.get_nowait()
                except queue.Empty:
                    break
            if latest is not None:
                try:
                    await ws.send_json(latest)
                except WebSocketDisconnect:
                    break
            if proc.poll() is not None:
                try:
                    await ws.send_json({"status": "offline"})
                except WebSocketDisconnect:
                    pass
                break
    finally:
        try:
            proc.stdin.write("QUIT\n")
            proc.stdin.flush()
        except OSError:
            pass
        proc.terminate()


app = Starlette(
    lifespan=lifespan,
    routes=[
        Route("/healthz", healthz),
        Route("/", index),
        Route("/seeds", seeds),
        Route("/static/data/salep_meshes.json", mesh_json),
        WebSocketRoute("/ws/world", ws_world),
        WebSocketRoute("/ws/npu", ws_npu),
    ])
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Salep web sunucusu (W3)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--pub-port", type=int, default=DEFAULT_PUB_PORT,
                    help="iç yayın portu (serve.py TCP); ikinci sunucu "
                         "farklı portla kalkar (§9.36)")
    ap.add_argument("--weather-csv", default=DEFAULT_WEATHER_CSV,
                    help="gerçek gözlem dosyası, yayıncıya iletilir (§9.28); "
                         "varsayılan weather_v3/W-base.csv")
    ap.add_argument("--weather-year", type=int, default=None)
    ap.add_argument("--weather-uv", default=None,
                    help="UV gözlem dosyası, yayıncıya iletilir (§9.28)")
    args = ap.parse_args(argv)
    global _pub_extra_args, _pub_port
    _pub_port = args.pub_port
    _pub_extra_args = []
    if args.weather_csv:
        _pub_extra_args += ["--weather-csv", args.weather_csv]
    if args.weather_year is not None:
        _pub_extra_args += ["--weather-year", str(args.weather_year)]
    if args.weather_uv:
        _pub_extra_args += ["--weather-uv", args.weather_uv]
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
