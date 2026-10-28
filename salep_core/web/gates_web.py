"""Web kapıları — headless bekçi (G19–G23 + G26, §9.21; G38 §9.116).

    Çalıştırma:
        cd salep_core
        .venv/bin/python -m web.gates_web

    G19 zero-CDN/offline · G20 LAN (0.0.0.0) · G21 WS sözleşme +
    latest-wins · G22 NPU'suz web tam çalışır · G23 izole koşu
    (G24 geometri paritesi: node web/g24_parity.mjs — ayrı koşar).
    G26 sprint düğmesi (2 sn'de 1 gün) — kablolama + canlı hız.
    G27 canlı veri paneli + gün-ay (NPU paneli yerine).
    G29 bayraklı yayıncıda UV akışı (bayraksızda null — G27b).
    G31 bitki sensörleri paneli (fizik + NPU-kanal değerleri).
    G32 modele değer yalnız simden girer (manuel SET kapalı).
    G33 müdahaleler paneli (su/gübre doz + toprak düğmeleri).
    G34 bayraksız sunucu varsayılan havayı (W-base) yayıncıya verir.
    G35 kopan istemcide no_frame sessiz (taklit soket, sunucusuz).
    G36 cift sunucu ayri yayin portuyla ayni anda kare akitir.
"""

import ast
import json
import os
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(ROOT, "web")
STATIC_DIR = os.path.join(WEB_DIR, "static")

# Sandbox proxy'sini atla: 127.0.0.1'e doğrudan bağlan.
os.environ["no_proxy"] = "127.0.0.1,localhost"
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)

PORT_MAIN = 18080
PORT_NPULESS = 18081
PORT_MANUAL = 18083
PORT_SPRINT = 18084
PORT_WEATHER = 18085
PORT_WX = 18086
PORT_SIMNPU = 18087
PORT_ACTION = 18088
PORT_DEFWX = 18089
PORT_DUAL_A = 18092
PORT_DUAL_B = 18093
PUB_DUAL_A = 41793
PUB_DUAL_B = 41794
PORT_LOBES = 18096
PUB_LOBES = 41796
PORT_P1 = 18097
PUB_P1 = 41797


def _npu_stream_pids():
    """Çalışan `npu_plant_npu --stream` süreçleri (/proc taraması)."""
    pids = set()
    try:
        names = os.listdir("/proc")
    except OSError:
        return pids
    for pid in names:
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                cl = f.read().replace(b"\0", b" ").decode()
        except OSError:
            continue
        if "npu_plant_npu" in cl and "--stream" in cl:
            pids.add(int(pid))
    return pids


def _get(url, timeout=10.0):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, r.read()


def _start_server(port, host="127.0.0.1", env_extra=None,
                  server_args=None, cwd=None):
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    # -m web.server baska dizinden de calisabilmeli: PYTHONPATH'e ROOT eklenir
    # (kullanicinin herhangi bir dizinden kaldirmasi durumu, 2026-09-21).
    env["PYTHONPATH"] = ROOT + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.Popen(
        [sys.executable, "-m", "web.server",
         "--host", host, "--port", str(port)] + list(server_args or []),
        cwd=cwd or ROOT, env=env, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, bufsize=1)
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            out = proc.stdout.read()
            raise RuntimeError(f"server kalkmadı:\n{out[-2000:]}")
        try:
            status, body = _get(f"http://127.0.0.1:{port}/healthz", timeout=2.0)
            d = json.loads(body)
            if status == 200 and d.get("ok"):
                return proc
        except OSError:
            time.sleep(0.3)
    proc.terminate()
    raise RuntimeError("server /healthz vermedi (30 sn)")


def _stop_server(proc):
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def gate_g19():
    """G19: static'te dış referans yok (http/cdn).

    Tek istisna: SVG ad-uzayı URI'si (createElementNS sabiti — ağa
    çıkmaz, getirme yok). Harfi harfine çıkarılıp taranır (§9.115).
    """
    bad = []
    for dirpath, _, files in os.walk(STATIC_DIR):
        if "vendor" in dirpath:
            continue
        for fn in files:
            if not fn.endswith((".html", ".css", ".js")):
                continue
            p = os.path.join(dirpath, fn)
            s = open(p, encoding="utf-8").read().lower()
            s = s.replace("http://www.w3.org/2000/svg", "")
            for pat in ("http://", "https://", "cdn.", "cdn/"):
                if pat in s:
                    bad.append(f"{os.path.relpath(p, STATIC_DIR)}: {pat}")
    assert not bad, "G19 BAŞARISIZ: dış referans:\n" + "\n".join(bad)
    print("✅ G19 GEÇTİ: zero-CDN/offline (dış referans yok)")
    return True


def gate_g20():
    """G20: 0.0.0.0 bind + erişim + TÜM yerel statik varlık 200."""
    import re
    proc = _start_server(PORT_MAIN, host="0.0.0.0")
    try:
        status, body = _get(f"http://127.0.0.1:{PORT_MAIN}/healthz")
        d = json.loads(body)
        assert status == 200 and d.get("ok"), f"G20: /healthz {status}"
        assert d.get("schema") == 2, "G20: schema!=2"
        # Beyaz-ekran bekçisi: index'in refere ettiği her yerel varlık
        # + bilinen modüller 200 dönmeli (boş vendor hariç).
        refs = set()
        status, index = _get(f"http://127.0.0.1:{PORT_MAIN}/")
        assert status == 200 and b"Salep" in index, "G20: index"
        refs.update(re.findall(rb'["\'](/static/[^"\']+)["\']',
                               index))
        for js in ("app.js", "ws.js", "profile.js", "world2d.js",
                   "world3d.js", "brain.js", "charts.js"):
            p = os.path.join(STATIC_DIR, "js", js)
            s = open(p, encoding="utf-8").read()
            refs.update(("/static/js/" + m).encode()
                        for m in re.findall(r'"(\./[\w]+\.js)"', s))
            refs.update(("/static/" + m).encode()
                        for m in re.findall(r'"/static/([\w./]+)"', s))
        refs.add(b"/static/data/npu_sample.json")
        bad = []
        for ref in sorted(refs):
            if b"/vendor/" in ref:
                continue  # erteli vendor (yokluğu 2D'yi bozmaz)
            st, bd = _get(f"http://127.0.0.1:{PORT_MAIN}"
                          f"{ref.decode()}")
            if st != 200 or not bd:
                bad.append(f"{ref.decode()}: {st}")
        assert not bad, "G20 BAŞARISIZ (beyaz ekran):\n" + "\n".join(bad)
        print(f"✅ G20 GEÇTİ: 0.0.0.0:{PORT_MAIN} bind + /healthz OK + "
              f"{len(refs)} statik varlık 200")
        return True
    finally:
        _stop_server(proc)


def _ws_frames(port, path, n, send=None, timeout=30.0):
    import websockets
    import asyncio

    async def _run():
        frames = []
        async with websockets.connect(
                f"ws://127.0.0.1:{port}{path}",
                max_size=4 * 1024 * 1024) as ws:
            if send is not None:
                await ws.send(json.dumps(send))
            deadline = time.monotonic() + timeout
            while len(frames) < n and time.monotonic() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
                except asyncio.TimeoutError:
                    break
                d = json.loads(raw)
                if d.get("v") == 2:  # §9.27 v2 (§9.20 dondurma prosedürü)
                    frames.append(d)
        return frames

    return asyncio.run(_run())


def gate_g21():
    """G21: /ws/world N frame + v2 üst şema + monoton gün + komut yolu.

    Üst şema: donuk v2 anahtarları + İSTEĞE BAĞLI lobes (frame.py'nin
    yayıncıya bıraktığı anahtar, §9.115). lobes varsa sözlük olmalı;
    yokluğu da geçerli (zincir kapalı koşu).
    """
    proc = _start_server(PORT_MAIN)
    try:
        frames = _ws_frames(PORT_MAIN, "/ws/world", 15)
        assert len(frames) == 15, f"G21: {len(frames)} frame (15 değil)"
        for f in frames:
            keys = set(f) - {"lobes"}
            assert keys == {"v", "wall_t", "sim", "world", "plant",
                            "visual", "sensors", "actions", "events"}, \
                "G21: v2 üst şema"
            if "lobes" in f:
                assert isinstance(f["lobes"], dict), \
                    "G21: lobes sözlük değil"
            assert f["v"] == 2, f"G21: şema v!=2 ({f['v']})"
        days = [f["sim"]["day"] + f["sim"]["day_frac"] for f in frames]
        assert all(b >= a for a, b in zip(days, days[1:])), \
            "G21: latest-wins monoton değil"
        # Komut yolu: water → kuyruk/applied/olay (yayıncı 1x hızda
        # gün devri ~120 sn sürer; pending aynı karedde görünür —
        # relay kanıtı kuyruk girişi + G14'teki applied kanıtıyla tamdır).
        frames2 = _ws_frames(PORT_MAIN, "/ws/world", 25,
                             send={"cmd": "water", "mm": 20})

        def _water_seen(f):
            a = f["actions"]
            if a["applied_irrigation_mm"] > 0:
                return True
            if a["pending_irrigation_mm"] > 0:
                return True
            return any(e.get("kind") == "irrigation_applied"
                       for e in f.get("events", []))

        seen = any(_water_seen(f) for f in frames2)
        assert seen, "G21: water komutu relay'den geçmedi"
        # Tohum yolu (§9.54): /seeds canlı listesi (çerçeve dışı kanal;
        # üst şema değişmez, sızıntı yok).
        status, body = _get(f"http://127.0.0.1:{PORT_MAIN}/seeds")
        d = json.loads(body)
        assert status == 200 and isinstance(d.get("plants"), list) \
            and d["plants"], f"G21: /seeds {status}"
        p0 = d["plants"][0]
        assert isinstance(p0.get("seed"), int), \
            "G21: tohum int değil"
        assert isinstance(p0.get("params"), dict) \
            and "field_capacity" in p0["params"], \
            "G21: tohum parametreleri eksik"
        assert b"ground_truth" not in body, "G21: tohumda sızıntı!"
        print(f"✅ G21 GEÇTİ: 15 frame v2 + monoton + komut relay + "
              f"/seeds tohum={p0['seed']} (son gün {frames[-1]['sim']['day']})")
        return True
    finally:
        _stop_server(proc)


def gate_g22():
    """G22: NPU yokken web tam çalışır (SALEP_NPU_BIN=/yok)."""
    proc = _start_server(PORT_NPULESS, env_extra={"SALEP_NPU_BIN": "/yok/npu"})
    try:
        status, body = _get(f"http://127.0.0.1:{PORT_NPULESS}/healthz")
        d = json.loads(body)
        assert d.get("npu_present") is False, "G22: npu_present yalancı"
        frames = _ws_frames(PORT_NPULESS, "/ws/world", 10)
        assert len(frames) == 10, f"G22: {len(frames)} frame (10 değil)"
        import websockets
        import asyncio

        async def _npu():
            async with websockets.connect(
                    f"ws://127.0.0.1:{PORT_NPULESS}/ws/npu") as ws:
                raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
                return json.loads(raw)

        d = asyncio.run(_npu())
        assert d.get("status") == "offline", f"G22: npu {d}"
        print("✅ G22a GEÇTİ: NPU'suz /ws/world akar + /ws/npu offline")
    finally:
        _stop_server(proc)
    # G22b el sıkışması: GERÇEK binary varken bile yalnız /ws/world
    # kullanılınca yeni npu_plant_npu --stream süreci doğmaz.
    proc = _start_server(PORT_MANUAL)
    try:
        before = _npu_stream_pids()
        frames = _ws_frames(PORT_MANUAL, "/ws/world", 10)
        assert len(frames) == 10, f"G22b: {len(frames)} frame"
        after = _npu_stream_pids()
        assert after <= before, \
            f"G22b BAŞARISIZ: world yalnızken NPU doğdu: {after - before}"
        print("✅ G22b GEÇTİ: el sıkışmasız NPU süreci yok")
        return True
    finally:
        _stop_server(proc)


def gate_g23():
    """G23: web sim/npu iç modülü import etmez (AST lint)."""
    import sys as _sys
    stdlib = set(_sys.stdlib_module_names)
    allow = {"server": {"starlette", "uvicorn"},
             # gates_web TEST tarafidir: web.server + starlette'i dogrudan
             # kullanabilir (G35 taklit soket); yasak sim/npu ic modulleridir.
             "gates_web": {"websockets", "web", "starlette"}}
    violations = []
    for fn, third in allow.items():
        path = os.path.join(WEB_DIR, fn + ".py")
        tree = ast.parse(open(path, encoding="utf-8").read(), path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    mods = ["<relative>"]
                else:
                    mods = [node.module or ""]
            else:
                continue
            for mod in mods:
                top = mod.split(".")[0]
                if top in stdlib or top in third or top in ("__future__",):
                    continue
                violations.append(f"{fn}.py: {mod}")
    assert not violations, "G23 BAŞARISIZ:\n" + "\n".join(violations)
    print("✅ G23 GEÇTİ: web izole (sim/npu importu yok)")
    return True


def gate_g26():
    """G26: Sprint düğmesi — 2 gerçek-sn'de 1 sim-günü.

    a) Statik kablolama: index.html'de data-cmd="sprint" düğmesi var,
       app.js CMDS'te speed v=0.5'e (60/120) bağlı.
    b) Canlı hız: /ws/world üzerinden speed komutu → frame'deki hız
       0.5 okunur ve gün ~0.5 gün/sn akar (4 sn pencerede ≥1.0 gün).
    """
    import re
    index = open(os.path.join(STATIC_DIR, "index.html"),
                 encoding="utf-8").read()
    assert 'data-cmd="sprint"' in index, \
        "G26a BAŞARISIZ: index.html'de sprint düğmesi yok"
    app = open(os.path.join(STATIC_DIR, "js", "app.js"),
               encoding="utf-8").read()
    m = re.search(r"sprint:\s*\{\s*cmd:\s*\"speed\",\s*v:\s*([^}]+)\}", app)
    assert m, "G26a BAŞARISIZ: app.js CMDS'te sprint eşlemesi yok"
    v = eval(m.group(1), {"__builtins__": {}}, {})  # yalnız aritmetik
    assert abs(v - 0.5) < 1e-9, \
        f"G26a BAŞARISIZ: sprint hızı {v} (0.5 gün/sn değil)"

    proc = _start_server(PORT_SPRINT)
    try:
        frames = _ws_frames(PORT_SPRINT, "/ws/world", 20,
                            send={"cmd": "speed", "v": 0.5}, timeout=40.0)
        assert len(frames) >= 10, \
            f"G26b BAŞARISIZ: {len(frames)} frame (sprint akmıyor)"
        speeds = [f["sim"]["speed"] for f in frames[-5:]]
        assert any(abs(s - 0.5) < 1e-9 for s in speeds), \
            f"G26b BAŞARISIZ: hız 0.5'e geçmedi {speeds}"
        days = [f["sim"]["day"] + f["sim"]["day_frac"] for f in frames]
        assert days[-1] - days[0] >= 1.0, \
            f"G26b BAŞARISIZ: sprint yavaş ({days[-1] - days[0]:.2f} gün)"
        print(f"✅ G26 GEÇTİ: sprint kablolu, hız 0.5, "
              f"ilerleme {days[-1] - days[0]:.1f} gün (~2 sn/gün)")
        return True
    finally:
        _stop_server(proc)


def gate_g27():
    """G27: Canlı veri paneli + gün-ay (NPU paneli yerine).

    a) NPU paneli kalkık: index.html'de braincv/npu-btn yok; app.js
       brain.js'e dokunmaz, drawBrain çağırmaz.
    b) Statik kablolama: data-date/stage/season/temp/soilt/sky/rain/photo
       id'leri var, app.js hepsine her karede yazar; gün-ay eşlemesi
       (dateOfDoy + TR ay adları) ve dönem TR eşlemesi (stageTr)
       kaynakta; gök derecesiz yazılır (sun_alt_deg panele çıkmaz).
    c) Veri akışı: canlı /ws/world frame'inde panelin okuduğu yollar
       mevcut ve tipli.
    """
    index = open(os.path.join(STATIC_DIR, "index.html"),
                 encoding="utf-8").read()
    for gone in ("braincv", "npu-btn", "npu-state"):
        assert gone not in index, \
            f"G27a BAŞARISIZ: NPU paneli artığı #{gone} duruyor"
    assert "Canlı Veriler" in index, "G27a BAŞARISIZ: veri paneli yok"
    data_ids = ("data-date", "data-stage", "data-season", "data-temp",
                "data-soilt", "data-sky", "data-rain", "data-photo",
                "data-uv", "data-height", "data-applied")
    for el in data_ids:
        assert f'id="{el}"' in index, \
            f"G27a BAŞARISIZ: index.html'de #{el} yok"
    app = open(os.path.join(STATIC_DIR, "js", "app.js"),
               encoding="utf-8").read()
    assert "brain.js" not in app and "drawBrain" not in app, \
        "G27a BAŞARISIZ: app.js hâlâ beyin paneline bağlı"
    for el in data_ids:
        assert f'$("{el}")' in app, \
            f"G27a BAŞARISIZ: app.js #{el}'ye yazmıyor"
    for token in ("dateOfDoy", "MONTHS_TR", "MDAYS", "photoperiod_h",
                  "temp_soil", "stageTr", "w.temp_air"):
        assert token in app, \
            f"G27a BAŞARISIZ: gün-ay/panel eşlemesi eksik ({token})"
    assert "Dormansi" in app and "Vejetatif" in app, \
        "G27a BAŞARISIZ: dönem TR eşlemesi yok"
    # Gök derecesizliği: sun_alt_deg karede durur ama panele çıkmaz.
    assert "sun_alt_deg" not in app, \
        "G27a BAŞARISIZ: gök derecesi panele sızmış"
    # Meteorolojik mevsim sınırları (1 Mar/1 Haz/1 Eyl/1 Ara) kaynakta kilitli.
    assert "doy < 60" in app and "doy < 151" in app \
        and "doy < 243" in app and "doy < 334" in app, \
        "G27a BAŞARISIZ: meteorolojik mevsim sınırları kayık"
    assert "'gece'" in app or '"gece"' in app, \
        "G27a BAŞARISIZ: gök TR eşlemesi yok"

    proc = _start_server(PORT_WEATHER)
    try:
        frames = _ws_frames(PORT_WEATHER, "/ws/world", 3, timeout=30.0)
        assert frames, "G27b BAŞARISIZ: frame akmıyor"
        f = frames[-1]
        assert isinstance(f["sim"].get("doy"), int), "G27b: sim.doy yok"
        assert f["world"].get("sky") in ("day", "dusk", "night"), \
            f"G27b: world.sky {f['world'].get('sky')!r}"
        for k in ("rain_mm", "temp_air_display", "temp_soil",
                  "photoperiod_h", "sun_alt_deg", "temp_air"):
            assert isinstance(f["world"].get(k), (int, float)), \
                f"G27b: world.{k} yok"
        # Dosyasız koşu: UV null gelir (çizgi yolu), boy sayı ve ≥ 0.
        assert "uv_index" in f["world"], "G27b: world.uv_index anahtarı yok"
        assert f["world"]["uv_index"] is None, \
            f"G27b: dosyasız koşuda UV olmamalı ({f['world']['uv_index']})"
        sh = f["plant"].get("stem_height")
        assert isinstance(sh, (int, float)) and sh >= 0, \
            f"G27b: plant.stem_height bozuk ({sh})"
        assert f["plant"].get("stage") in ("DORMANT", "SPROUTING",
            "VEGETATIVE", "FLOWERING", "SENESCENCE", "DEAD"), \
            f"G27b: plant.stage adı bozuk ({f['plant'].get('stage')})"
        print(f"✅ G27 GEÇTİ: veri paneli kablolu, NPU paneli yok, "
              f"canlı veri (doy={f['sim']['doy']}, "
              f"gün-uzunluğu={f['world']['photoperiod_h']}s)")
        return True
    finally:
        _stop_server(proc)


def gate_g29():
    """G29: Web yayıncısına hava dosyası geçişi (§9.28).

    --weather-csv/--weather-uv ile kalkan sunucunun /ws/world
    karelerinde world.uv_index gerçek sayı, plant.stem_height ≥ 0 gelir.
    (Bayraksız sunucuda UV null'dur — G27b kilidi.)
    """
    import glob
    csvs = sorted(glob.glob(os.path.join(ROOT, "open-meteo-37.8*.csv")))
    temp_csv = next((p for p in csvs if "37.86" in p), None)
    uv_csv = next((p for p in csvs if "37.88" in p), None)
    assert temp_csv and uv_csv, "G29 BAŞARISIZ: Aydın dosyaları yok"
    proc = _start_server(PORT_WX, server_args=["--weather-csv", temp_csv,
                                               "--weather-uv", uv_csv])
    try:
        frames = _ws_frames(PORT_WX, "/ws/world", 5, timeout=40.0)
        assert frames, "G29 BAŞARISIZ: frame akmıyor"
        f = frames[-1]
        uv = f["world"].get("uv_index")
        assert isinstance(uv, (int, float)) and uv >= 0, \
            f"G29 BAŞARISIZ: UV yayıncıdan geçmedi ({uv})"
        sh = f["plant"].get("stem_height")
        assert isinstance(sh, (int, float)) and sh >= 0, \
            f"G29 BAŞARISIZ: boy bozuk ({sh})"
        print(f"✅ G29 GEÇTİ: bayraklı yayıncı UV akıtıyor (UV={uv}, "
              f"boy={sh})")
        return True
    finally:
        _stop_server(proc)


def gate_g31():
    """G31: Bitki Sensörleri paneli (§9.32).

    a) Statik kablolama: index.html'de sens-soil/ec/hn/hs/ts/tn/ph/npk/
       leaf/root/water/o2 id'leri var, app.js hepsine her karede yazar.
    b) Veri akışı: canlı /ws/world karesinde panelin okuduğu plant +
       sensors yolları mevcut ve tipli (kanallar 0-100).
    """
    sens_ids = ("sens-soil", "sens-ec", "sens-hn", "sens-hs", "sens-ts",
                "sens-tn", "sens-ph", "sens-npk", "sens-leaf", "sens-root",
                "sens-water", "sens-o2")
    index = open(os.path.join(STATIC_DIR, "index.html"),
                 encoding="utf-8").read()
    assert "Bitki Sensörleri" in index, "G31a BAŞARISIZ: sensör paneli yok"
    for el in sens_ids:
        assert f'id="{el}"' in index, \
            f"G31a BAŞARISIZ: index.html'de #{el} yok"
    app = open(os.path.join(STATIC_DIR, "js", "app.js"),
               encoding="utf-8").read()
    for el in sens_ids:
        assert f'$("{el}")' in app, \
            f"G31a BAŞARISIZ: app.js #{el}'ye yazmıyor"
    proc = _start_server(PORT_WEATHER)
    try:
        frames = _ws_frames(PORT_WEATHER, "/ws/world", 3, timeout=30.0)
        assert frames, "G31b BAŞARISIZ: frame akmıyor"
        f = frames[-1]
        for k in ("soil_moisture", "soil_ec", "leaf_health",
                  "root_health", "water_balance", "o2_deficit"):
            assert isinstance(f["plant"].get(k), (int, float)), \
                f"G31b: plant.{k} yok"
        for k in ("hs", "ts", "hn", "tn", "ph", "npk", "ec"):
            v = f["sensors"].get(k)
            assert isinstance(v, (int, float)) and 0 <= v <= 100, \
                f"G31b: sensors.{k} aralık-dışı ({v})"
        print(f"✅ G31 GEÇTİ: sensör paneli kablolu, canlı değerler tipli "
              f"(EC={f['plant']['soil_ec']}, nem={f['plant']['soil_moisture']})")
        return True
    finally:
        _stop_server(proc)


def gate_g32():
    """G32: Modele değer yalnız simülasyondan girer (§9.33).

    a) Statik kilitler: /ws/npu'da tarayıcı SET rölesi yok; sunucu
       güncel karenin 7 sensörünü SET'ler; lobda uydurma 50 yok.
    b) Saf fonksiyon: tam kare → 7 SET satırı; eksik/boş kare → [].
    c) Canlı: /ws/npu telemetrisi akarken /ws/world karesi sensörlü
       gelir (model sim günüyle birlikte koşar).
    """
    src = open(os.path.join(WEB_DIR, "server.py"), encoding="utf-8").read()
    assert 'msg.get("cmd") == "SET"' not in src, \
        "G32a BAŞARISIZ: tarayıcı SET rölesi duruyor"
    assert "_sim_sensor_sets" in src and "_latest_frame" in src, \
        "G32a BAŞARISIZ: sim-itkili SET yok"
    lobe = open(os.path.join(ROOT, "sim", "lobes", "plant_npu.py"),
                encoding="utf-8").read()
    assert "frame.get(k, 50)" not in lobe, \
        "G32a BAŞARISIZ: lobda uydurma 50 duruyor"
    import importlib  # stdlib: G23 statik-import lintine takılmaz
    _sim_sensor_sets = importlib.import_module("web.server")._sim_sensor_sets
    full = {"sensors": {"hs": 75, "ts": 40, "hn": 60, "tn": 40,
                        "ph": 40, "npk": 40, "ec": 68}}
    assert _sim_sensor_sets(full) == [
        "SET hs 75", "SET ts 40", "SET hn 60", "SET tn 40",
        "SET ph 40", "SET npk 40", "SET ec 68"], \
        "G32b BAŞARISIZ: 7 satır birebir değil"
    assert _sim_sensor_sets({"sensors": {"hs": 75}}) == [], \
        "G32b BAŞARISIZ: eksik karede gönderim olmamalı"
    assert _sim_sensor_sets(None) == [], \
        "G32b BAŞARISIZ: boş karede gönderim olmamalı"
    proc = _start_server(PORT_SIMNPU)
    try:
        import websockets
        import asyncio

        async def _tele():
            out = []
            async with websockets.connect(
                    f"ws://127.0.0.1:{PORT_SIMNPU}/ws/npu",
                    max_size=4 * 1024 * 1024) as ws:
                deadline = time.monotonic() + 30.0
                while len(out) < 2 and time.monotonic() < deadline:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    except asyncio.TimeoutError:
                        break
                    d = json.loads(raw)
                    if isinstance(d.get("t"), int):
                        out.append(d)
            return out

        teles = asyncio.run(_tele())
        assert len(teles) == 2 and teles[1]["t"] > teles[0]["t"], \
            "G32c BAŞARISIZ: NPU telemetrisi akmıyor"
        frames = _ws_frames(PORT_SIMNPU, "/ws/world", 1, timeout=30.0)
        assert frames and "sensors" in frames[-1], \
            "G32c BAŞARISIZ: sim karesi sensörsüz"
        print(f"✅ G32 GEÇTİ: NPU sim-itkili koşuyor "
              f"(tele t={teles[-1]['t']}, sim gün={frames[-1]['sim']['day']})")
        return True
    finally:
        _stop_server(proc)


def gate_g33():
    """G33: Müdahaleler + Toprak paneli (§9.34/§9.35).

    a) Statik: index.html'de Müdahaleler paneli + 4 doz + 3 toprak
       düğmesi, app.js CMDS'te su/gübre/toprak eşlemeleri.
    b) Canlı: water/fert komutu /ws/world kuyruğuna düşer
       (pending_irrigation_mm / pending_fert_mass); soil komutunda
       akış sürer.
    """
    index = open(os.path.join(STATIC_DIR, "index.html"),
                 encoding="utf-8").read()
    assert "Müdahaleler" in index, "G33a BAŞARISIZ: müdahale paneli yok"
    for cmd in ("water10", "water20", "fert15", "fert30"):
        assert f'data-cmd="{cmd}"' in index, \
            f"G33a BAŞARISIZ: #{cmd} düğmesi yok"
    app = open(os.path.join(STATIC_DIR, "js", "app.js"),
               encoding="utf-8").read()
    for token in ('water10: { cmd: "water", mm: 10 }',
                  'water20: { cmd: "water", mm: 20 }',
                  'fert15: { cmd: "fert", mass: 15 }',
                  'fert30: { cmd: "fert", mass: 30 }',
                  ".panel.actions button"):
        assert token in app, \
            f"G33a BAŞARISIZ: CMDS/bağlantı eksik ({token})"
    for cmd in ("soil_kumlu", "soil_tinli", "soil_killi"):
        assert f'data-cmd="{cmd}"' in index, \
            f"G33a BAŞARISIZ: #{cmd} düğmesi yok"
    for token in ('soil_kumlu: { cmd: "soil", preset: "kumlu" }',
                  'soil_tinli: { cmd: "soil", preset: "tınlı" }',
                  'soil_killi: { cmd: "soil", preset: "killi" }'):
        assert token in app, \
            f"G33a BAŞARISIZ: toprak eşlemesi eksik ({token})"
    proc = _start_server(PORT_ACTION)
    try:
        frames = _ws_frames(PORT_ACTION, "/ws/world", 6,
                            send={"cmd": "water", "mm": 10}, timeout=30.0)
        assert frames, "G33b BAŞARISIZ: frame akmıyor"
        assert any(f["actions"].get("pending_irrigation_mm") == 10
                   for f in frames), \
            "G33b BAŞARISIZ: sulama kuyruğa düşmedi"
        frames = _ws_frames(PORT_ACTION, "/ws/world", 6,
                            send={"cmd": "fert", "mass": 15}, timeout=30.0)
        assert any(f["actions"].get("pending_fert_mass") == 15
                   for f in frames), \
            "G33b BAŞARISIZ: gübre kuyruğa düşmedi"
        frames = _ws_frames(PORT_ACTION, "/ws/world", 6,
                            send={"cmd": "soil", "preset": "killi"},
                            timeout=30.0)
        assert frames, "G33b BAŞARISIZ: toprak komutunda akış durdu"
        print("✅ G33 GEÇTİ: müdahale+toprak paneli kablolu, kuyruk canlı")
        return True
    finally:
        _stop_server(proc)


def gate_g34():
    """G34: bayraksız kalkan sunucu varsayılan havayı yayıncıya verir.

    Davranış kanıtı yayıncı sürecinin komut satırıdır (/proc taraması):
    serve.py komutunda W-base.csv (MUTLAK yol) görülmeli; ayrıca /ws/world
    kareleri akmalı. Sunucu /tmp'den kaldırılır: varsayılan hava cwd'ye
    bağlı olmamalı (2026-09-21 regresyonu).
    """
    proc = _start_server(PORT_DEFWX, cwd="/tmp")
    try:
        hit = False
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            try:
                with open(f"/proc/{pid}/cmdline", "rb") as f:
                    cmd = f.read().replace(b"\0", b" ").decode()
            except OSError:
                continue
            if "serve.py" in cmd and "W-base.csv" in cmd:
                hit = True
                break
        assert hit, "G34 BAŞARISIZ: yayıncıda varsayılan hava yok"
        frames = _ws_frames(PORT_DEFWX, "/ws/world", 3, timeout=40.0)
        assert frames, "G34 BAŞARISIZ: frame akmıyor"
        print("✅ G34 GEÇTİ: bayraksız sunucu W-base havasıyla yayın yapıyor")
        return True
    finally:
        _stop_server(proc)


def gate_g35():
    """G35: ws_world no_frame yolunda kopan istemcide sessiz donus.

    Taklit soketin send_json'u WebSocketDisconnect yukseltir (istemci
    ilk kare gelmeden kapandi); ws_world tracebacksiz donmeli.
    Canli sunucu gerekmez (~10 sn no_frame bekleme suresi)."""
    import asyncio
    from starlette.websockets import WebSocketDisconnect
    import web.server as S

    class KopukSoket:
        async def accept(self):
            pass

        async def send_json(self, _):
            raise WebSocketDisconnect(code=1006)

        async def close(self):
            pass

    prev = S._latest_frame
    S._latest_frame = None
    try:
        asyncio.run(S.ws_world(KopukSoket()))
    finally:
        S._latest_frame = prev
    print("✅ G35 GEÇTİ: kopan istemcide no_frame sessiz")
    return True


def gate_g36():
    """G36: iki sunucu aynı anda, ayrı yayın portu (§9.36).

    Aynı PUB_PORT'ta ikinci sunucu no_frame'e düşerdi (boş panel);
    --pub-port ile iki sunucu da v2 kare akıtır. Yayıncı ayrılığı
    /proc komut satırındaki farklı --port ile kanıtlanır.
    """
    a = _start_server(PORT_DUAL_A,
                      server_args=["--pub-port", str(PUB_DUAL_A)])
    try:
        b = _start_server(PORT_DUAL_B,
                          server_args=["--pub-port", str(PUB_DUAL_B)])
        try:
            fa = _ws_frames(PORT_DUAL_A, "/ws/world", 3, timeout=40.0)
            fb = _ws_frames(PORT_DUAL_B, "/ws/world", 3, timeout=40.0)
            assert len(fa) == 3, f"G36 BAŞARISIZ: A {len(fa)} kare"
            assert len(fb) == 3, f"G36 BAŞARISIZ: B {len(fb)} kare"
            seen = set()
            for pid in os.listdir("/proc"):
                if not pid.isdigit():
                    continue
                try:
                    with open(f"/proc/{pid}/cmdline", "rb") as f:
                        cmd = f.read().replace(b"\0", b" ").decode()
                except OSError:
                    continue
                if "serve.py" in cmd:
                    for port in (str(PUB_DUAL_A), str(PUB_DUAL_B)):
                        if f"--port {port}" in cmd or f"--port={port}" in cmd:
                            seen.add(port)
            assert seen == {str(PUB_DUAL_A), str(PUB_DUAL_B)}, \
                f"G36 BAŞARISIZ: yayıncılar ayrık değil ({sorted(seen)})"
            print(f"✅ G36 GEÇTİ: çift sunucu akıyor "
                  f"(A gün={fa[-1]['sim']['day']}, B gün={fb[-1]['sim']['day']})")
            return True
        finally:
            _stop_server(b)
    finally:
        _stop_server(a)


def gate_g37():
    """G37: /ws/world kareleri lob tasiyiciyi icerir (§9.115).

    2026-09-24 regresyonu: eski sunucu (lobes'suz yayin) + yeni panel
    "zincir kapali" gosteriyordu. Bekci: ilk karelerden birinde lobes
    sozlugu + iki lob canli olmali; /healthz has_lobes dogrulamali.
    """
    proc = _start_server(PORT_LOBES,
                         server_args=["--pub-port", str(PUB_LOBES)])
    try:
        frames = _ws_frames(PORT_LOBES, "/ws/world", 4, timeout=40.0)
        assert frames, "G37 BAŞARISIZ: frame akmıyor"
        lob = [f.get("lobes") for f in frames
               if isinstance(f.get("lobes"), dict)]
        assert lob, "G37 BAŞARISIZ: karelerde lobes yok (zincir kapalı?)"
        L = lob[-1]
        for k in ("sensory_alive", "pattern_alive", "fed_tick",
                  "fed_events", "aff", "k4"):
            assert k in L, f"G37 BAŞARISIZ: lobes.{k} yok"
        assert L["sensory_alive"] and L["pattern_alive"], \
            "G37 BAŞARISIZ: lob ölü (sensory/pattern)"
        status, body = _get(f"http://127.0.0.1:{PORT_LOBES}/healthz")
        d = json.loads(body)
        assert d.get("has_lobes") is True, \
            "G37 BAŞARISIZ: /healthz has_lobes!=true"
        print(f"✅ G37 GEÇTİ: lobes yayında (fed_tick={L['fed_tick']}, "
              f"aff={len(L['aff'])}, k4={len(L['k4'])})")
        return True
    finally:
        _stop_server(proc)


def gate_g38():
    """G38: sinyal panelinde bitki P1 atimi gorunur (§9.116).

    2026-09-28 regresyonu: motor T-satirinda p1=01/10/11 atesliyordu
    ama zincir p1 bitlerini dusuruyor (T_RE yakalamiyordu), panelde
    P1/bitki yolu hic yanmiyordu (yalniz sensor teli + P2).
    Bekci:
    a) statik: T_RE p1 yakalama grubu + snapshot "p1" anahtari +
       signal.js L.p1/fireP1 kablolamasi + legend bitki notu.
    b) canli: /ws/world karelerinde lobes.p1 listesi var.
    """
    chain = open(os.path.join(ROOT, "sim", "sensory_chain.py"),
                 encoding="utf-8").read()
    assert "p1=([01]{2})" in chain, \
        "G38a BAŞARISIZ: T_RE p1 yakalamiyor"
    assert '"p1":' in chain, \
        "G38a BAŞARISIZ: snapshot p1 anahtari yok"
    assert "p1_events_from_t" in chain, \
        "G38a BAŞARISIZ: p1 eslemesi yok"
    sig = open(os.path.join(STATIC_DIR, "js", "signal.js"),
               encoding="utf-8").read()
    for token in ("L.p1", "fireP1", "lastP1Tick", "firedP1"):
        assert token in sig, \
            f"G38a BAŞARISIZ: signal.js {token} yok (bitki yolu cizilmiyor)"
    index = open(os.path.join(STATIC_DIR, "index.html"),
                 encoding="utf-8").read()
    assert "p1a/p1b" in index, \
        "G38a BAŞARISIZ: legend bitki atimini belgelemiyor"
    proc = _start_server(PORT_P1,
                         server_args=["--pub-port", str(PUB_P1)])
    try:
        frames = _ws_frames(PORT_P1, "/ws/world", 4, timeout=40.0)
        assert frames, "G38b BAŞARISIZ: frame akmıyor"
        lob = [f.get("lobes") for f in frames
               if isinstance(f.get("lobes"), dict)]
        assert lob, "G38b BAŞARISIZ: karelerde lobes yok"
        L = lob[-1]
        assert isinstance(L.get("p1"), list), \
            "G38b BAŞARISIZ: lobes.p1 liste değil (bitki akışı yok)"
        print(f"✅ G38 GEÇTİ: bitki P1 kablolu (p1={len(L['p1'])} olay)")
        return True
    finally:
        _stop_server(proc)


def main():
    gates = [("G19", gate_g19), ("G20", gate_g20), ("G21", gate_g21),
             ("G22", gate_g22), ("G23", gate_g23), ("G26", gate_g26),
             ("G27", gate_g27), ("G29", gate_g29), ("G31", gate_g31),
             ("G32", gate_g32), ("G33", gate_g33), ("G34", gate_g34),
             ("G35", gate_g35), ("G36", gate_g36), ("G37", gate_g37),
             ("G38", gate_g38)]
    results = {}
    for name, fn in gates:
        print(f"--- {name} ---")
        try:
            results[name] = fn()
        except Exception as e:
            print(f"❌ {name} BAŞARISIZ: {e}")
            results[name] = False
        print()
    print("SONUÇ:")
    for k, v in results.items():
        print(f"  {k}: {'✅ GEÇTİ' if v else '❌ BAŞARISIZ'}")
    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()
