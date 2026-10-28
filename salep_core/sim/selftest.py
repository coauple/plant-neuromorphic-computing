"""Headless doğrulama kapıları — Salep Dijital İkizi.

G1: 365 gün, NPU canlı, frame üretir, ground_truth sızıntısı yok.
G2: disaster_scenario.csv ile satır satır eşleşme (sadakat kanıtı).
G3: Eşlenen sensörler NPU'ya verilince kanal eşiklerini geçiyor mu.
G4: EMEKLİ (Qt render, W0 ile karşılıksız SKIP).
G5: Eylem kuyruğu uçtan uca (sulama/gübre/kuraklık/tek-atımlık).
G6: EMEKLİ (Qt piksel farkı, W0 ile karşılıksız SKIP).
G8: EMEKLİ (QML lint, W0 ile karşılıksız SKIP).
G9: NPU'suz dünya + lob sözleşmesi (binary/display gerekmez).
G11: Alan ayrılığı — sim NPU'yu import edemez (AST lint).
G7: EMEKLİ (QML bağlama, W0 ile karşılıksız SKIP).
G12: Sürekli görsel türevler (sap/çiçek/toprak, sıçramasız).
G13: Prosedürel mesh'ler geçerli + deterministik.
G14: v2 şema + soket + komut yolu.
G15: Mesh kalite tabanı (JSON üçgen sayıları).
G16: Doku haritaları (prosedürel PNG).
G10: Diurnal salınım + doğru faz (tepe 13-17, dip 03-07).
G25: Sonsuz koşu — DEAD yutucu durum değil, ölümden sonra rebirth.
G30: Ölüm disiplini — kuruma DORMANT'a çeker, DEAD yalnız çürüme/açlık.
G34: Toprak presetleri (kumlu/tınlı/killi) + spread=0 determinizmi.
G35: fiziksel-v1 su modeli (defter kapanışı + alım + saat-altı).
G36: Gözlem gürültüsü (tohumlu, gözlem-only) + SNN arayüz hazırlığı.
G37: Pertürbasyon bataryası (8 önden-hipotez, TEST01-10+12).
G38: Çıkarım fazı (D2+D3 tekrarı, D1-null kaydı).
G39: Simulator validation battery (TEST1-13+ADV+REC, §9.51/§9.53).

Çalıştırma:
    cd salep_core
    .venv/bin/python -m sim.selftest

Anayasa referansları:
  §0: ground truth etiketleri modele ASLA girmez
  §9.9: C++ çekirdeğe dokunulmaz
  K6: ground_truth_event frame'e asla girmez
  K7: "stres" etiketi yok
"""
import os
import sys
import time
import traceback

import numpy as np
import pandas as pd


SIM_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(SIM_DIR, "out")


def gate_g1(days=365, verbose=True):
    """G1: Headless — NPU canlı, ground truth sızıntısı yok.

    days sim-günü boyunca:
      1. WorldState fizik ilerletir
      2. SensorMapper 7 sensör üretir
      3. NpuBridge sensörleri NPU'ya SET eder
      4. Frame oluşturulur ve ground_truth sızıntısı ASSERT edilir
    """
    from sim.world_state import WorldState
    from sim.sensor_map import SensorMapper
    from sim.npu_bridge import NpuBridge
    from sim.frame import Frame, FrameBuffer, compute_visuals

    ws = WorldState(seed=42, speed=1.0)
    mapper = SensorMapper()
    bridge = NpuBridge()
    fb = FrameBuffer()

    bridge.start()
    time.sleep(1.0)  # NPU başlangıcı — ilk telemetri için bekleme

    if not bridge.is_alive():
        print("❌ G1 BAŞARISIZ: NPU süreci başlatılamadı")
        return False

    npu_set_count = 0
    for day in range(days):
        # Fizik ilerlet
        ws.clock.sim_day = day
        ws.clock.day_frac = 0.5  # günün ortası
        ws._last_stepped_day = -1  # her gün step at
        ws.step_if_needed()
        snap = ws.get_snapshot()

        # Sensör eşleme
        fert = snap.get("fert_dose", 0.0)
        sensors = mapper.update(snap, fert_dose=fert)

        # NPU'ya gönder (her 10 günde bir — hız için)
        if day % 10 == 0:
            bridge.set_sensors(sensors)
            npu_set_count += 1
            time.sleep(0.1)  # NPU'nun işlemesi için

        # Frame oluştur
        f = Frame()
        f.sim_day = snap["sim_day"]
        f.day_of_year = snap["day_of_year"]
        f.temp = snap["temp"]
        f.photoperiod = snap["photoperiod"]
        f.rain_mm = snap["rain_mm"]
        f.stage = snap["stage"]
        f.leaf_health = snap["leaf_health"]
        f.root_health = snap["root_health"]
        f.tuber_mass = snap["tuber_mass"]
        f.water_balance = snap["water_balance"]
        f.soil_moisture = snap["soil_moisture"]
        f.soil_ec = snap["soil_ec"]
        f.o2_deficit_ticks = snap["o2_deficit_ticks"]
        f.stem_height = snap.get("stem_height", 0.0)
        f.uv_index = snap.get("uv_index")
        for k, v in sensors.items():
            setattr(f, k, v)

        tele = bridge.get_latest_telemetry()
        if tele:
            f.npu_tick = tele["t"]
            f.npu_wire = tele["wire"]
            f.npu_fire = tele["f"]
            f.npu_w = tele["w"]
            f.npu_cc = tele["cc"]

        f = compute_visuals(f)
        fb.write(f)

        # ASSERT: ground_truth frame'de YOK (K6)
        frame_dict = vars(fb.read())
        frame_str = str(frame_dict).lower()
        assert "ground_truth" not in frame_str, \
            f"G1 BAŞARISIZ: ground_truth frame'e sızdı! gün={day}"
        assert "root_rot" not in frame_str, \
            f"G1 BAŞARISIZ: root_rot frame'e sızdı! gün={day}"
        assert "salt_burn" not in frame_str, \
            f"G1 BAŞARISIZ: salt_burn frame'e sızdı! gün={day}"
        assert "plant_death" not in frame_str, \
            f"G1 BAŞARISIZ: plant_death frame'e sızdı! gün={day}"

    bridge.stop()
    final = fb.read()

    # NPU çalıştı mı?
    assert final.npu_tick > 0, \
        f"G1 BAŞARISIZ: NPU hiç tick üretmedi (son tick={final.npu_tick})"

    if verbose:
        print(f"✅ G1 GEÇTİ: {days} gün, NPU tick={final.npu_tick}, "
              f"SET komutları={npu_set_count}, "
              f"son stage={final.stage}, "
              f"ground truth sızıntısı yok")
    return True


def gate_g2(verbose=True):
    """G2: disaster_scenario.csv ile satır satır eşleşme.

    Aynı seed + aynı scripted_events ile koşturulur,
    temp/soil_moisture/soil_ec/leaf_health/root_health/tuber_mass/
    water_balance/stage sütunları atol=1e-6 ile eşleşmelidir.

    Bu, "3D gerçekten fizik motorunu gösteriyor" kanıtıdır.
    """
    from sim.plant_sim import run_population

    # Aynı senaryo (scenario_disaster.py ile birebir)
    scripted_events = {}
    for d in range(55, 115):
        scripted_events[d] = {"force_no_rain": True}
    scripted_events[110] = {"force_no_rain": True, "fertilizer_dose_mass": 130.0}

    df = run_population(n_plants=1, n_days=200, seed=1,
                        scripted_events=scripted_events)

    # Referans CSV
    ref_path = os.path.join(OUT_DIR, "disaster_scenario.csv")

    if os.path.exists(ref_path):
        ref = pd.read_csv(ref_path)
        numeric_cols = ["temp", "soil_moisture", "soil_ec", "leaf_health",
                        "root_health", "tuber_mass", "water_balance"]
        string_cols = ["stage"]

        for col in numeric_cols:
            if col in ref.columns and col in df.columns:
                np.testing.assert_allclose(
                    df[col].values, ref[col].values,
                    atol=1e-6,
                    err_msg=f"G2 BAŞARISIZ: {col} eşleşmiyor"
                )

        for col in string_cols:
            if col in ref.columns and col in df.columns:
                assert (df[col].values == ref[col].values).all(), \
                    f"G2 BAŞARISIZ: {col} eşleşmiyor"

        if verbose:
            print(f"✅ G2 GEÇTİ: {len(numeric_cols)+len(string_cols)} sütun, "
                  f"{len(df)} satır birebir eşleşti")
    else:
        # Referans yoksa oluştur
        os.makedirs(OUT_DIR, exist_ok=True)
        df.to_csv(ref_path, index=False)
        if verbose:
            print(f"⚠️  G2: Referans CSV oluşturuldu → {ref_path}")
            print(f"    {len(df)} satır. İlk çalıştırmada referans seti kuruldu,")
            print(f"    sonraki koşularda eşleşme doğrulanacak.")
    return True


def gate_g3(verbose=True):
    """G3: Eşlenen sensörler kanal eşiklerini geçiyor mu?

    Kuraklık senaryosunda:
      - soil_moisture düşmeli → tn düşmeli
      - EC gübre sonrası 3.4'ü geçmeli → ec > 68
    """
    from sim.plant_sim import run_population
    from sim.sensor_map import SensorMapper

    scripted_events = {}
    for d in range(55, 115):
        scripted_events[d] = {"force_no_rain": True}
    scripted_events[110] = {"force_no_rain": True, "fertilizer_dose_mass": 130.0}

    df = run_population(n_plants=1, n_days=200, seed=1,
                        scripted_events=scripted_events)

    mapper = SensorMapper()
    ec_exceeded = False
    tn_below_threshold = False
    ec_max = 0
    tn_min = 100

    # Eşik notu: plant_sim fiziğinde soil_moisture minimum ~28%
    # (self-limiting ET + floor=1.0). Kuraklıkta ~36-43% aralığında.
    # tn=40 eşiği "belirgin kuraklık" anlamına gelir.
    TN_DROUGHT_THRESHOLD = 40

    for _, row in df.iterrows():
        snap = {
            "temp": row["temp"],
            "rain_mm": row["rain_mm"],
            "soil_moisture": row["soil_moisture"],
            "soil_ec": row["soil_ec"],
            "tuber_mass": row["tuber_mass"],
        }
        fert = 130.0 if row["day"] == 110 else 0.0
        sensors = mapper.update(snap, fert_dose=fert)

        if sensors["ec"] > ec_max:
            ec_max = sensors["ec"]
        if sensors["tn"] < tn_min:
            tn_min = sensors["tn"]
        if sensors["ec"] > 68:  # EC yanık eşiği 3.4 mS/cm = 68
            ec_exceeded = True
        if sensors["tn"] < TN_DROUGHT_THRESHOLD:
            tn_below_threshold = True

    assert ec_exceeded, \
        f"G3 BAŞARISIZ: EC sensörü hiç 68'i geçmedi (max={ec_max})"
    assert tn_below_threshold, \
        f"G3 BAŞARISIZ: tn hiç {TN_DROUGHT_THRESHOLD}'ın altına düşmedi (min={tn_min})"

    if verbose:
        print(f"✅ G3 GEÇTİ: EC max={ec_max} (>68 ✅), "
              f"tn min={tn_min} (<{TN_DROUGHT_THRESHOLD} ✅)")
    return True


def _retired_skip(verbose, gate, note):
    """Emekli kapı: W0 ile görsel katman kaldırıldı, karşılığı yok."""
    if verbose:
        print(f"⏭️  {gate} SKIP: {note} (W0: godot/_legacy/dashboard silindi)")
    return "skip"


def gate_g4(verbose=True):
    """G4 (emekli Qt render kanıtı, W0 ile karşılıksız)."""
    return _retired_skip(verbose, "G4", "Qt render kanıtı emekli")


def gate_g6(verbose=True):
    """G6 (emekli Qt piksel farkı, W0 ile karşılıksız)."""
    return _retired_skip(verbose, "G6", "Qt piksel farkı emekli")


def gate_g8(verbose=True):
    """G8 (emekli QML lint, W0 ile karşılıksız)."""
    return _retired_skip(verbose, "G8", "QML lint emekli")


def gate_g9(verbose=True):
    """G9: NPU'suz dünya + lob sözleşmesi (Adım 2).

    a) ObserverBus + PlantNpuLobe: 25 frame yayınlanır → 10'arlık
       throttle ile 2 SET komutu üretilir, değerler frame'den gelir.
    b) serve.py --ticks (NPU'suz yayıncı): TCP'den v2 frame alınır,
       ground_truth yokluğu ASSERT edilir.
    NPU binary'si gerekmez, display gerekmez.
    """
    from sim.observer import ObserverBus
    from sim.lobes.plant_npu import PlantNpuLobe, SENSORS_7

    bus = ObserverBus()
    lobe = PlantNpuLobe(every_n_frames=10)
    bus.subscribe(lobe)
    assert bus.lobe_names == ["plant_npu"], \
        f"G9a BAŞARISIZ: abonelik yok {bus.lobe_names}"

    sent = []
    for i in range(25):
        frame = {k: 40 + i for k in SENSORS_7}
        out = bus.publish(frame)
        state, cmd = out["plant_npu"]
        if cmd:
            assert set(cmd["set"]) == set(SENSORS_7), \
                f"G9a BAŞARISIZ: eksik kanal {sorted(cmd['set'])}"
            assert all(v == 40 + i for v in cmd["set"].values()), \
                "G9a BAŞARISIZ: SET değeri frame'den gelmiyor"
            sent.append(cmd["set"])
    assert lobe.sent_batches == 2, \
        f"G9a BAŞARISIZ: throttle bozuk (batch={lobe.sent_batches}, beklenen=2)"
    assert len(sent) == 2, f"G9a BAŞARISIZ: komut sayısı {len(sent)}"

    # G9b (A7: Qt smoke yerine sim-yayıncısı smoke): serve.py NPU'suz
    # koşar; TCP'den 1 frame alınır, v1 + ground_truth yokluğu ASSERT edilir.
    import json
    import socket
    import subprocess
    serve_mod = os.path.join(SIM_DIR, "serve.py")
    port = 41791
    proc = subprocess.Popen(
        [sys.executable, serve_mod, "--port", str(port),
         "--speed", "1000", "--ticks", "200"],
        cwd=os.path.dirname(SIM_DIR),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        ready = ""
        assert proc.stdout is not None
        import time as _time
        t0 = _time.monotonic()
        while _time.monotonic() - t0 < 30:
            if proc.poll() is not None:
                break
            import select as _select
            r, _, _ = _select.select([proc.stdout], [], [], 1.0)
            if r:
                ready += proc.stdout.readline()
                if "READY" in ready:
                    break
        assert "READY" in ready, \
            f"G9b BAŞARISIZ: yayıncı hazır olmadı ({ready[-300:]!r})"
        line = ""
        with socket.create_connection(("127.0.0.1", port), timeout=30) as s:
            buf = b""
            while b"\n" not in buf:
                chunk = s.recv(65536)
                if not chunk:
                    break
                buf += chunk
            line = buf.split(b"\n", 1)[0].decode("utf-8", "replace")
    finally:
        proc.terminate()
        proc.wait(timeout=15)
    assert line.startswith("{"), \
        f"G9b BAŞARISIZ: yayıncıdan frame gelmedi ({line[:120]!r})"
    d = json.loads(line)
    assert d.get("v") == 2, f"G9b BAŞARISIZ: şema v!=2 ({d.get('v')})"
    assert "ground_truth" not in line, "G9b BAŞARISIZ: ground_truth sızıntısı"

    if verbose:
        print("✅ G9 GEÇTİ: lob 25 framede 2 SET üretti, "
              "NPU'suz yayıncı frame verdi")
    return True


def gate_g11(verbose=True):
    """G11: Alan ayrılığı — sim NPU'yu import edemez (AST lint).

    Saf sim: world_state, frame, sensor_map, observer → stdlib +
    numpy/pandas/matplotlib + sim.plant_sim dışında import yasak
    (npu_bridge/lobes dahil NPU tarafı importu yok).
    Sınır katmanı: npu_bridge → stdlib-only; lobes/plant_npu →
    stdlib + sim.observer.
    Birleşme noktası selftest.py muaftır.
    """
    import ast
    import sys

    stdlib = set(sys.stdlib_module_names)
    third = {"numpy", "pandas", "matplotlib"}

    SIM_PURE = {
        "world_state.py": {"sim.plant_sim"},
        "frame.py": set(),
        "sensor_map.py": set(),
        "observer.py": set(),
    }
    LOBE_ALLOW = {"sim.observer"}

    def imports_of(path):
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), path)
        mods = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.extend(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level and node.level > 0:
                    base = "sim" + (("." + node.module) if node.module else "")
                    mods.append(base)
                elif node.module:
                    mods.append(node.module)
        return mods

    def top(mod):
        return mod.split(".")[0]

    violations = []
    for fname, sim_allow in SIM_PURE.items():
        path = os.path.join(SIM_DIR, fname)
        for mod in imports_of(path):
            if top(mod) in stdlib or top(mod) in third:
                continue
            if top(mod) == "sim" and mod in sim_allow:
                continue
            violations.append(f"{fname}: {mod}")

    lobe_path = os.path.join(SIM_DIR, "lobes", "plant_npu.py")
    for mod in imports_of(lobe_path):
        if top(mod) in stdlib or top(mod) in third:
            continue
        if mod in LOBE_ALLOW:
            continue
        violations.append(f"lobes/plant_npu.py: {mod}")

    # W2: koşucu yalnız stdlib + third-party + sim.* görebilir (NPU yok)
    run_path = os.path.join(SIM_DIR, "run.py")
    for mod in imports_of(run_path):
        if top(mod) in stdlib or top(mod) in third:
            continue
        if top(mod) == "sim":
            continue
        violations.append(f"run.py: {mod}")

    bridge_path = os.path.join(SIM_DIR, "npu_bridge.py")
    for mod in imports_of(bridge_path):
        if top(mod) in stdlib or top(mod) in third:
            continue
        violations.append(f"npu_bridge.py: {mod}")

    assert not violations, \
        "G11 BAŞARISIZ: sınır ihlali:\n" + "\n".join(violations)

    if verbose:
        print("✅ G11 GEÇTİ: sim saf, sınır katmanı stdlib-only, "
              "lob yalnız observer'a bağlı")
    return True


def gate_g12(verbose=True):
    """G12: Sürekli görsel türevler (Adım 3).

    Sap evre-içi monoton uzar, evre sınırlarında sıçrama yok;
    çiçek 0 → 12 kademeli açılır; soil_wet [0,1]'de, sulama ve
    kuyruk izi taşır. NPU/display gerekmez.
    """
    from sim.frame import Frame, compute_visuals

    def vis(stage, age, **kw):
        f = Frame(stage=stage, stage_age=age, soil_moisture=50.0,
                  tuber_mass=8.0, **kw)
        return compute_visuals(f)

    # Sap: evre içi monoton + sınır sürekliliği
    sprout = [vis("SPROUTING", a).stem_h for a in range(0, 21)]
    assert sprout[0] == 0.0 and abs(sprout[-1] - 0.6) < 1e-9, \
        f"G12 BAŞARISIZ: sürgün rampası {sprout[0]:.2f}→{sprout[-1]:.2f}"
    assert all(b >= a for a, b in zip(sprout, sprout[1:])), \
        "G12 BAŞARISIZ: sürgün monoton değil"
    veg0 = vis("VEGETATIVE", 0).stem_h
    assert abs(veg0 - sprout[-1]) < 1e-9, \
        f"G12 BAŞARISIZ: SPROUTING→VEGETATIVE sıçraması ({veg0:.3f})"
    veg = [vis("VEGETATIVE", a).stem_h for a in range(0, 31)]
    assert all(b >= a for a, b in zip(veg, veg[1:])), \
        "G12 BAŞARISIZ: rozet monoton değil"
    fl0 = vis("FLOWERING", 0).stem_h
    assert abs(fl0 - veg[-1]) < 1e-9, \
        f"G12 BAŞARISIZ: VEGETATIVE→FLOWERING sıçraması ({fl0:.3f})"
    se0 = vis("SENESCENCE", 0).stem_h
    assert abs(se0 - 1.0) < 1e-9, \
        f"G12 BAŞARISIZ: FLOWERING→SENESCENCE sıçraması ({se0:.3f})"

    # Çiçek: 0 → 12 kademeli, başka evrede 0
    flowers = [vis("FLOWERING", a).flower_count for a in range(0, 36)]
    assert flowers[0] == 0 and flowers[-1] == 12, \
        f"G12 BAŞARISIZ: salkım {flowers[0]}→{flowers[-1]} (0→12 değil)"
    assert all(b >= a for a, b in zip(flowers, flowers[1:])), \
        "G12 BAŞARISIZ: çiçek açılımı monoton değil"
    assert vis("VEGETATIVE", 15).flower_count == 0, \
        "G12 BAŞARISIZ: çiçeksiz evrede çiçek var"

    # Toprak ıslaklığı: sınırlar + sulama izi + kuyruk ön-izlemesi
    base = vis("VEGETATIVE", 10).soil_wet
    assert 0.0 <= base <= 1.0, f"G12 BAŞARISIZ: soil_wet aralık dışı {base}"
    wet_app = vis("VEGETATIVE", 10, applied_irrigation_mm=40.0).soil_wet
    assert wet_app > base + 0.1, \
        f"G12 BAŞARISIZ: sulama izi yok ({base:.2f}→{wet_app:.2f})"
    wet_pen = vis("VEGETATIVE", 10, pending_irrigation_mm=20.0).soil_wet
    assert wet_pen > base, \
        f"G12 BAŞARISIZ: kuyruk ön-izlemesi yok ({base:.2f}→{wet_pen:.2f})"

    if verbose:
        print(f"✅ G12 GEÇTİ: sap 0→{se0:.1f} sürekli, "
              f"çiçek 0→12, soil_wet izli ({base:.2f})")
    return True


def gate_g13(verbose=True):
    """G13: Prosedürel mesh'ler geçerli + deterministik (Adım 4).

    sim/models/*.obj: üçgen yüzler, aralık-içi indeksler, sonlu
    normaller, alt sınır üstü sayılar; tempdir'e yeniden üretim
    repodaki dosyalarla bayt-eşit olmalı. NPU/display gerekmez.
    """
    import filecmp
    import math
    import tempfile
    from sim.models import salep_gen as g

    # Alt sınırlar (cömert): çökmüş/boş üretimi yakalar
    MIN_V = {"salep_leaf": 50, "salep_tuber": 50, "salep_root": 100,
             "salep_stem": 20, "salep_flower": 100}
    for name in g.PARTS:
        path = os.path.join(SIM_DIR, "models", name + ".obj")
        assert os.path.isfile(path), f"G13 BAŞARISIZ: {name}.obj yok"
        V, T, N, F = [], [], [], []
        with open(path, encoding="utf-8") as fh:
            for ln in fh:
                s = ln.split()
                if not s:
                    continue
                if s[0] == "v":
                    V.append(s[1:4])
                elif s[0] == "vt":
                    T.append(s[1:3])
                elif s[0] == "vn":
                    N.append(s[1:4])
                elif s[0] == "f":
                    F.append(s[1:])
        assert len(V) >= MIN_V[name] and F, \
            f"G13 BAŞARISIZ: {name} çok küçük ({len(V)}v {len(F)}f)"
        # Qt Quick 3D formatı: tam v/vt/vn (QSSG `f v//vn` reddeder)
        assert len(V) == len(T) == len(N), \
            f"G13 BAŞARISIZ: {name} v/vt/vn uyumsuz"
        for f in F:
            assert len(f) == 3, f"G13 BAŞARISIZ: {name} üçgen değil"
            for v in f:
                parts = v.split("/")
                assert len(parts) == 3 and all(parts), \
                    f"G13 BAŞARISIZ: {name} yüz formatı ({v})"
                vi, ti, ni = map(int, parts)
                assert 1 <= vi <= len(V), \
                    f"G13 BAŞARISIZ: {name} verteks indeksi"
                assert 1 <= ti <= len(T), \
                    f"G13 BAŞARISIZ: {name} uv indeksi"
                assert 1 <= ni <= len(N), \
                    f"G13 BAŞARISIZ: {name} normal indeksi"
        assert all(math.isfinite(float(c)) for n in N for c in n), \
            f"G13 BAŞARISIZ: {name} normal sonlu değil"
        # QSSG dejenere üçgeni toptan reddeder — sıfır alan yasak
        pts = [(float(V[i][0]), float(V[i][1]), float(V[i][2]))
               for i in range(len(V))]
        for f in F:
            (ax, ay, az), (bx, by, bz), (cx, cy, cz) = (
                pts[int(p.split("/")[0]) - 1] for p in f)
            ux, uy, uz = bx - ax, by - ay, bz - az
            vx, vy, vz = cx - ax, cy - ay, cz - az
            area2 = ((uy * vz - uz * vy) ** 2 + (uz * vx - ux * vz) ** 2
                     + (ux * vy - uy * vx) ** 2)
            assert area2 > 1e-24, \
                f"G13 BAŞARISIZ: {name} dejenere üçgen içeriyor"

    with tempfile.TemporaryDirectory() as d:
        g.generate(d)
        for name in g.PARTS:
            assert filecmp.cmp(
                os.path.join(SIM_DIR, "models", name + ".obj"),
                os.path.join(d, name + ".obj"), shallow=False), \
                f"G13 BAŞARISIZ: {name} deterministik değil"

    if verbose:
        print(f"✅ G13 GEÇTİ: {len(g.PARTS)} mesh geçerli + bayt-eşit")
    return True


def gate_g7(verbose=True):
    """G7 (emekli QML bağlama kapısı, W0 ile karşılıksız)."""
    return _retired_skip(verbose, "G7", "QML bağlama kapısı emekli")


# v2 şema anahtar kümeleri (§9.27 dondurma prosedürü: SCHEMA_VERSION +
# bu kümeler + G14 birlikte değişti). v1'den fark: world.uv_index +
# plant.stem_height eklendi, başka anahtar değişmedi.
_V2_TOP = {"v", "wall_t", "sim", "world", "plant", "visual",
           "sensors", "actions", "events"}
_V2_SIM = {"day", "day_frac", "doy", "paused", "speed"}
_V2_WORLD = {"temp_air", "temp_air_display", "temp_soil", "photoperiod_h",
             "sun_alt_deg", "sun_az_deg", "rain_mm", "sky", "uv_index"}
_V2_PLANT = {"stage", "stage_age", "leaf_health", "root_health",
             "tuber_mass", "water_balance", "o2_deficit", "soil_moisture",
             "soil_ec", "stem_height"}
_V2_VISUAL = {"stem_h", "leaf_scale", "leaf_turgor", "wilt", "yellowing",
              "flower_count", "flower_open", "root_tint", "root_necrotic",
              "tuber_scale", "soil_wet", "salt_crust"}
_V2_SENSORS = {"hs", "ts", "hn", "tn", "ph", "npk", "ec"}
_V2_ACTIONS = {"pending_irrigation_mm", "pending_fert_mass",
               "applied_irrigation_mm", "applied_fert_mass"}


def _check_v2_schema(d):
    assert set(d) == _V2_TOP, f"şema üst: {sorted(set(d))}"
    assert d["v"] == 2, f"şema sürümü {d['v']}"
    assert set(d["sim"]) == _V2_SIM, "şema sim"
    assert set(d["world"]) == _V2_WORLD, "şema world"
    assert set(d["plant"]) == _V2_PLANT, "şema plant"
    assert set(d["visual"]) == _V2_VISUAL, "şema visual"
    assert set(d["sensors"]) == _V2_SENSORS, "şema sensors"
    assert set(d["actions"]) == _V2_ACTIONS, "şema actions"
    assert isinstance(d["events"], list), "şema events"


def gate_g14(verbose=True):
    """G14: Şema (v2) + soket + latest-wins + komut (A2/A3).

    serve.py alt-süreci (sınırlı tick) → probe okur: v2 şema birebir,
    ham metinde ground_truth yok, günler monoton. Sonra ham soketten
    water komutu → applied_irrigation_mm > 0 görülür (komut yolu).
    seeds komutu → stdout'a TOHUM listesi (tohum=42, sızıntısız) (§9.54).
    """
    import json
    import socket
    import subprocess
    import time

    port = 41791
    proc = subprocess.Popen(
        [sys.executable, os.path.join(SIM_DIR, "serve.py"),
         "--port", str(port), "--speed", "4", "--ticks", "400"],
        cwd=os.path.dirname(SIM_DIR),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        # READY bekle
        deadline = time.monotonic() + 20.0
        ready = False
        while time.monotonic() < deadline:
            line = proc.stdout.readline()
            if "READY" in line:
                ready = True
                break
            if proc.poll() is not None:
                break
        assert ready, "G14 BAŞARISIZ: serve READY vermedi"

        from sim.probe import read_frames
        frames = read_frames(port, 10, timeout=20.0)
        assert len(frames) == 10, \
            f"G14 BAŞARISIZ: {len(frames)} frame (10 değil)"
        for f in frames:
            _check_v2_schema(f)
        days = [f["sim"]["day"] + f["sim"]["day_frac"] for f in frames]
        assert all(b >= a for a, b in zip(days, days[1:])), \
            "G14 BAŞARISIZ: latest-wins monoton değil"

        # Komut yolu: water → uygulanan sulama görülmeli
        s = socket.create_connection(("127.0.0.1", port), timeout=10.0)
        s.settimeout(10.0)
        s.sendall(b'{"cmd": "water", "mm": 20}\n')
        buf, seen, deadline = "", False, time.monotonic() + 15.0
        while time.monotonic() < deadline and not seen:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk.decode("utf-8", "replace")
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                line = line.strip()
                if not line.startswith("{"):
                    continue
                assert "ground_truth" not in line, \
                    "G14 BAŞARISIZ: ham yayında ground_truth!"
                d = json.loads(line)
                if d["actions"]["applied_irrigation_mm"] > 0:
                    seen = True
                    break
        s.close()
        assert seen, "G14 BAŞARISIZ: water komutu uygulanmadı"

        # Tohum yolu (§9.54): seeds → stdout TOHUM listesi; şema
        # değişmez (çerçeve dışı kanal), ground_truth sızmaz.
        s3 = socket.create_connection(("127.0.0.1", port), timeout=10.0)
        s3.settimeout(10.0)
        s3.sendall(b'{"cmd": "seeds"}\n')
        tohum, deadline = None, time.monotonic() + 10.0
        while time.monotonic() < deadline and tohum is None:
            line = proc.stdout.readline()
            if not line:
                break
            if line.startswith("TOHUM "):
                tohum = json.loads(line[len("TOHUM "):])
        s3.close()
        assert isinstance(tohum, list) and tohum, \
            "G14 BAŞARISIZ: seeds komutu TOHUM düşürmedi"
        assert tohum[0].get("seed") == 42, \
            f"G14 BAŞARISIZ: bitki tohumu 42 değil ({tohum[0].get('seed')})"
        assert "ground_truth" not in json.dumps(tohum), \
            "G14 BAŞARISIZ: tohum günlüğünde sızıntı!"

        # Hız kilidi: pause → speed emri sürdürmeli + saat ilerlemeli
        s2 = socket.create_connection(("127.0.0.1", port), timeout=10.0)
        s2.settimeout(10.0)
        s2.sendall(b'{"cmd": "pause"}\n')
        time.sleep(0.5)
        s2.sendall(b'{"cmd": "speed", "v": 0.5}\n')
        buf2, pa, pb, deadline = "", None, None, time.monotonic() + 15.0
        while time.monotonic() < deadline and (pa is None or pb is None):
            chunk = s2.recv(65536)
            if not chunk:
                break
            buf2 += chunk.decode("utf-8", "replace")
            while "\n" in buf2:
                line, buf2 = buf2.split("\n", 1)
                line = line.strip()
                if not line.startswith("{"):
                    continue
                d = json.loads(line)
                if pa is None and d["sim"]["paused"]:
                    pa = d["sim"]["day"] + d["sim"]["day_frac"]
                elif pa is not None and not d["sim"]["paused"]:
                    pb = d["sim"]["day"] + d["sim"]["day_frac"]
        s2.close()
        assert pa is not None, "G14 BAŞARISIZ: pause tutmadı"
        assert pb is not None and pb > pa, \
            "G14 BAŞARISIZ: speed, duraklatmayı sürdürmedi"
    finally:
        proc.terminate()
        proc.wait(timeout=10)

    if verbose:
        print(f"✅ G14 GEÇTİ: v2 şema birebir, soket + komut yolu canlı "
              f"(son gün {frames[-1]['sim']['day']})")
    return True


_G15_MIN_TRIS = {"salep_leaf": 600, "salep_flower": 3000,
                  "salep_root": 5000, "salep_tuber": 1500,
                  "salep_stem": 400}


def gate_g15(verbose=True):
    """G15 ★: Mesh kalite tabanı (A4).

    salep_meshes.json üçgen sayıları plan eşiklerinde (kör sabitlendi);
    dizi uzunlukları tutarlı (vertex=3n, index=3t, normal/uv eşli).
    """
    import json
    path = os.path.join(SIM_DIR, "models", "salep_meshes.json")
    assert os.path.isfile(path), "G15 BAŞARISIZ: salep_meshes.json yok"
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    assert doc.get("meta", {}).get("format") == "world_arrays.v1", \
        "G15 BAŞARISIZ: format world_arrays.v1 değil"
    for name, minimum in _G15_MIN_TRIS.items():
        assert name in doc["parts"], f"G15 BAŞARISIZ: parça yok {name}"
        p = doc["parts"][name]
        tris = p["tris"]
        assert tris >= minimum, \
            f"G15 BAŞARISIZ: {name} {tris}t < {minimum}t"
        nv = len(p["vertex"]) // 3
        assert len(p["vertex"]) == 3 * nv, f"G15 BAŞARISIZ: {name} vertex"
        assert len(p["normal"]) == 3 * nv, f"G15 BAŞARISIZ: {name} normal"
        assert len(p["uv"]) == 2 * nv, f"G15 BAŞARISIZ: {name} uv"
        assert len(p["index"]) == 3 * tris, f"G15 BAŞARISIZ: {name} index"
        assert max(p["index"]) < nv and min(p["index"]) >= 0, \
            f"G15 BAŞARISIZ: {name} indeks aralığı"
    if verbose:
        counts = {n: doc["parts"][n]["tris"] for n in _G15_MIN_TRIS}
        print(f"✅ G15 GEÇTİ: mesh tabanı tuttu {counts}")
    return True


def gate_g16(verbose=True):
    """G16: Doku haritaları var + okunur (A4).

    tex/*.png: albedo RGB(+A), roughness gri/RGB, kenar ≥64 px.
    DÜRÜST NOT: dokular prosedürel (fotoğraf yok) — stil, ölçü değil.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    tex_dir = os.path.join(SIM_DIR, "models", "tex")
    need = {"leaf_albedo.png": 3, "leaf_roughness.png": 1,
            "tuber_albedo.png": 3, "soil_albedo.png": 3}
    for fname, min_ch in need.items():
        path = os.path.join(tex_dir, fname)
        assert os.path.isfile(path), f"G16 BAŞARISIZ: {fname} yok"
        img = plt.imread(path)
        assert img.shape[0] >= 64 and img.shape[1] >= 64, \
            f"G16 BAŞARISIZ: {fname} çok küçük {img.shape}"
        ch = 1 if img.ndim == 2 else img.shape[2]
        assert ch >= min_ch, \
            f"G16 BAŞARISIZ: {fname} kanal {ch} (<{min_ch})"
    if verbose:
        print("✅ G16 GEÇTİ: 4 doku okunur (prosedürel)")
    return True


def _step_world_to(ws, day):
    """Test yardımcısı: saati güne kurup step attırır."""
    ws.clock.sim_day = day
    ws.clock.day_frac = 0.0
    ws.step_if_needed()
    return ws.get_snapshot()


def gate_g17(verbose=True):
    """G17: Canlı döngü kapanışı (§9.55) — çekirdek DEĞİŞMEZ.

    a) Döngü tohumu deterministik, master'dan farklı, döngüden döngüye
       farklı (SeedSequence kardeş akış).
    b) Erken ölüm (kök): plant_death ilan edilir (cause=root_rot),
       tohum bekleyişte SABİT kalır; 5 gün sonra resow — yeni tohum,
       taze birey (DORMANT), aynı saksı (nem korunur).
    c) Doğal döngü sonu (sararma→uyku, yaprak tazelenmiş): aynı gün
       cycle_complete + yeni tohum (bekleyiş yok).
    d) Çekirdek diriltmesi (rebirth) bekleyişi BÖLEMEZ — bekleyiş
       bitmeden eski tohumla diriliş olmaz.
    e) Yayın 1 Ekim'de (273) uykuda başlar; ilk filizlenme güz
       yolundandır (Ocak kapısı değil).
    """
    from sim.world_state import WorldState, RESOW_DELAY_DAYS
    from sim.plant_sim import Stage

    w = WorldState(seed=7)
    s1 = w._cycle_seed(1)
    assert s1 == w._cycle_seed(1), "G17a BAŞARISIZ: döngü tohumu kararsız"
    assert s1 != 7, "G17a BAŞARISIZ: döngü tohumu master'la aynı"
    assert w._cycle_seed(2) != s1, "G17a BAŞARISIZ: döngüler aynı tohumu veriyor"

    w.plant.root_health = 0.0
    _step_world_to(w, 0)
    assert w.plant.stage == Stage.DEAD, "G17b BAŞARISIZ: ölüm gerçekleşmedi"
    assert w.plant.seed == 7, "G17b BAŞARISIZ: bekleyişte tohum değişti"
    kinds = [e["kind"] for e in w._events]
    assert "plant_death" in kinds, "G17b BAŞARISIZ: ölüm ilan edilmedi"
    death = next(e for e in w._events if e["kind"] == "plant_death")
    assert death["cause"] == "root_rot", \
        f"G17b BAŞARISIZ: ölüm nedeni yanlış ({death.get('cause')})"
    for d in range(1, RESOW_DELAY_DAYS):
        _step_world_to(w, d)
        assert w.plant.stage == Stage.DEAD, \
            f"G17d BAŞARISIZ: {d}. günde çekirdek diriltti (tohum {w.plant.seed})"
        assert w.plant.seed == 7, \
            f"G17d BAŞARISIZ: {d}. günde eski tohumla diriliş"
    _step_world_to(w, RESOW_DELAY_DAYS)
    assert w.plant.seed == s1, \
        f"G17b BAŞARISIZ: yeniden ekim tohumu yanlış ({w.plant.seed})"
    assert w.plant.stage == Stage.SPROUTING, \
        f"G17b BAŞARISIZ: fide filizlenerek başlamadı ({w.plant.stage})"
    assert w.plant.leaf_health == 100.0 and w.plant.root_health == 100.0, \
        "G17b BAŞARISIZ: taze birey değerleri kanonik değil"
    assert w.describe_plants()[0]["seed"] == s1, \
        "G17b BAŞARISIZ: /seeds kanalı yeni tohumu vermiyor"
    assert any(e["kind"] == "resow" and e.get("reason") == "plant_death"
               for e in w._events), "G17b BAŞARISIZ: resow olayı yok"

    w2 = WorldState(seed=7)
    _step_world_to(w2, 170)
    w2.plant.stage = Stage.SENESCENCE
    w2.plant.leaf_health = 100.0
    w2.plant.root_health = 100.0
    w2.plant.tuber_mass = 1.0
    done = False
    for d in range(171, 201):
        _step_world_to(w2, d)
        if any(e["kind"] == "resow" and e.get("reason") == "cycle_complete"
               for e in w2._events):
            done = True
            break
    assert done, "G17c BAŞARISIZ: sararma tamamlanınca ekim olmadı"
    assert w2.plant.seed == w2._cycle_seed(1), \
        "G17c BAŞARISIZ: doğal döngüde tohum yenilenmedi"

    from sim.world_state import START_DAY as _SD
    assert _SD == 273
    w3 = WorldState(seed=7)
    assert w3.clock.sim_day == _SD == 273, \
        f"G17e BAŞARISIZ: yayın Ekim'de başlamıyor ({w3.clock.sim_day})"
    s0 = _step_world_to(w3, _SD)
    assert s0["day_of_year"] == 273, "G17e BAŞARISIZ: açılış 1 Eki değil"
    assert s0["stage"] == "DORMANT", \
        f"G17e BAŞARISIZ: açılışta filizlenme ({s0['stage']})"
    sprout = None
    for d in range(_SD + 1, _SD + 60):
        s = _step_world_to(w3, d)
        if s["stage"] == "SPROUTING":
            sprout = (d, s["day_of_year"])
            break
    assert sprout is not None, "G17e BAŞARISIZ: 60 günde filizlenme yok"
    assert sprout[1] > 240, \
        f"G17e BAŞARISIZ: Ocak kapısından filizlenme ({sprout})"
    if verbose:
        print(f"✅ G17 GEÇTİ: ölüm ilanı+{RESOW_DELAY_DAYS}g bekleyiş+ekim "
              f"(tohum {s1}), doğal döngüde anında ekim")
    return True


def gate_g18(verbose=True):
    """G18: Bitki elektrofizyolojisi (sim/electro.py, §9.57) — türetme.

    a) Determinizm: aynı girdiler → aynı (V, hız, patlama, spike).
    b) Monotonluk: stresli bitki sağlıklıdan hızlı ateşler.
    c) Kapılama: DEAD sessiz, DORMANT ~1/4 hız.
    d) Fizik dokunulmazlığı: electro bitki nesnesini değiştirmez.
    """
    from sim.electro import ElectroState, DAY_TICKS

    a, b = ElectroState(), ElectroState()
    kw = dict(temp=20.0, rain_mm=0.0, irrig_mm=0.0, water_balance=-1.5,
              leaf_health=40.0, root_health=50.0, stage_name="VEGETATIVE",
              master_seed=7, day=100)
    r1, r2 = a.step(**kw), b.step(**kw)
    assert r1 == r2, "G18a BAŞARISIZ: elektrofizyoloji kararsız"
    assert a.spikes_for_day(*r1[1:], 7, 100) == \
        b.spikes_for_day(*r2[1:], 7, 100), "G18a BAŞARISIZ: spike kararsız"

    c = ElectroState()
    rh = c.step(temp=20.0, rain_mm=0.0, irrig_mm=0.0, water_balance=0.0,
                leaf_health=100.0, root_health=100.0,
                stage_name="VEGETATIVE", master_seed=7, day=100)
    assert 0 < rh[1] < r1[1], \
        f"G18b BAŞARISIZ: hız monoton değil ({rh[1]} vs {r1[1]})"

    d = ElectroState()
    rd = d.step(temp=20.0, rain_mm=0.0, irrig_mm=0.0, water_balance=-1.5,
                leaf_health=40.0, root_health=50.0, stage_name="DEAD",
                master_seed=7, day=100)
    assert rd[1] == 0.0 and rd[2] == 0.0, "G18c BAŞARISIZ: ölü ateşliyor"
    assert d.spikes_for_day(0.0, 0.0, 7, 100) == {0: [], 1: []}, \
        "G18c BAŞARISIZ: ölü spike üretiyor"
    e = ElectroState()
    re_ = e.step(temp=20.0, rain_mm=0.0, irrig_mm=0.0, water_balance=-1.5,
                 leaf_health=40.0, root_health=50.0, stage_name="DORMANT",
                 master_seed=7, day=100)
    assert abs(re_[1] / r1[1] - 0.25) < 1e-9, "G18c BAŞARISIZ: uyku oranı bozuk"
    sp = e.spikes_for_day(*re_[1:], 7, 100)
    assert all(0 <= t < DAY_TICKS for line in sp.values() for t in line), \
        "G18c BAŞARISIZ: tick aralığı taştı"

    from sim.plant_sim import Plant, PlantParams
    p = Plant(PlantParams(), 0)
    before = (p.leaf_health, p.root_health, p.soil_moisture, p.stage.name)
    f = ElectroState()
    f.step(35.0, 0.0, 0.0, -2.0, 10.0, 5.0, "FLOWERING", 7, 200)
    f.spikes_for_day(40.0, 5.0, 7, 200)
    after = (p.leaf_health, p.root_health, p.soil_moisture, p.stage.name)
    assert before == after, "G18d BAŞARISIZ: electro bitkiyi değiştirdi"
    if verbose:
        print("✅ G18 GEÇTİ: deterministik spike, stres-monoton, "
              "ölü sessiz, fizik el değmemiş")
    return True


def gate_g5(verbose=True):
    """G5: Eylem kuyruğu uçtan uca (5 alt-test, A7).

    a) Sulama yön+büyüklük: sulanan dünya ≥ +8 nem farkı açar
       (sihirli +18.0 yok — parametre değişimine dayanıklı).
    b) Kuyruk tek-atımlık: ikinci step'te applied=0, kuyruk boş.
    c) Gübre → EC yükselir (kontrol dünyasına göre).
    d) Kuraklıkta nem monoton azalır (5 step, yaz günü).
    e) Latest-wins: aynı gün 5× basış birikmez, son değer uygulanır.
    Eski kusur: sulama bugünün anahtarına yazılır, step çoktan
    çalışmış olurdu → kaybolurdu (delta = 0).
    """
    from sim.world_state import WorldState

    # --- a) sulama yön + asgari büyüklük ---
    watered = WorldState(seed=7)
    control = WorldState(seed=7)
    _step_world_to(watered, 5)
    _step_world_to(control, 5)
    watered.inject_irrigation(20.0)
    snap_w = _step_world_to(watered, 6)
    snap_c = _step_world_to(control, 6)
    assert snap_w["applied_irrigation_mm"] == 20.0, \
        f"G5a BAŞARISIZ: kuyruk tüketilmedi ({snap_w['applied_irrigation_mm']})"
    delta = snap_w["soil_moisture"] - snap_c["soil_moisture"]
    assert delta >= 8.0, \
        f"G5a BAŞARISIZ: sulama izi zayıf (delta={delta:+.2f}, eşik=+8)"

    # --- b) tek-atımlık: sonraki step'te kuyruk boş ---
    snap_w2 = _step_world_to(watered, 7)
    assert snap_w2["applied_irrigation_mm"] == 0.0, \
        f"G5b BAŞARISIZ: kuyruk iki kez uygulandı " \
        f"({snap_w2['applied_irrigation_mm']})"
    assert snap_w2["pending_irrigation_mm"] == 0.0, \
        "G5b BAŞARISIZ: kuyruk temizlenmedi"

    # --- c) gübre → EC artışı ---
    fed = WorldState(seed=7)
    plain = WorldState(seed=7)
    _step_world_to(fed, 5)
    _step_world_to(plain, 5)
    fed.inject_fertilizer(130.0)
    snap_f = _step_world_to(fed, 6)
    snap_p = _step_world_to(plain, 6)
    assert snap_f["applied_fert_mass"] == 130.0, \
        "G5c BAŞARISIZ: gübre kuyruğu tüketilmedi"
    assert snap_f["soil_ec"] > snap_p["soil_ec"] + 0.5, \
        f"G5c BAŞARISIZ: EC yükselmedi " \
        f"(gübreli={snap_f['soil_ec']:.2f}, sade={snap_p['soil_ec']:.2f})"

    # --- d) kuraklıkta monoton azalış (yaz, 10 gün) ---
    dry = WorldState(seed=7)
    _step_world_to(dry, 195)
    dry.inject_scenario(
        {d: {"force_no_rain": True} for d in range(195, 208)})
    moistures = []
    for d in range(196, 207):
        moistures.append(_step_world_to(dry, d)["soil_moisture"])
    assert all(b <= a for a, b in zip(moistures, moistures[1:])), \
        f"G5d BAŞARISIZ: monoton azalmıyor {moistures}"
    assert moistures[0] - moistures[-1] >= 3.0, \
        f"G5d BAŞARISIZ: 10 günde düşüş yetersiz " \
        f"({moistures[0]:.1f} → {moistures[-1]:.1f})"

    # --- e) latest-wins: aynı gün 5×10mm basış 50mm biriktirmez ---
    multi = WorldState(seed=7)
    _step_world_to(multi, 5)
    for _ in range(5):
        multi.inject_irrigation(10.0)
    snap_m = _step_world_to(multi, 6)
    assert snap_m["applied_irrigation_mm"] == 10.0, \
        f"G5e BAŞARISIZ: kuyruk gizlice birikti " \
        f"(applied={snap_m['applied_irrigation_mm']})"
    multi_f = WorldState(seed=7)
    _step_world_to(multi_f, 5)
    for _ in range(3):
        multi_f.inject_fertilizer(15.0)
    snap_mf = _step_world_to(multi_f, 6)
    assert snap_mf["applied_fert_mass"] == 15.0, \
        f"G5e BAŞARISIZ: gübre kuyruğu gizlice birikti " \
        f"(applied={snap_mf['applied_fert_mass']})"

    if verbose:
        print(f"✅ G5 GEÇTİ: sulama delta={delta:+.1f} (≥+8), "
              f"tek-atımlık OK, gübre EC "
              f"{snap_p['soil_ec']:.2f}→{snap_f['soil_ec']:.2f}, "
              f"kuraklık {moistures[0]:.1f}→{moistures[-1]:.1f} monoton ↓")
    return True


def gate_g10(verbose=True):
    """G10: Diurnal salınım + DOĞRU FAZ (güçlendirilmiş).

    Tepe saati ∈ [13:00, 17:00], dip saati ∈ [03:00, 07:00] olmalı.
    Eski kusurlar: (a) tam-sayı gün → fark sıfırdı; (b) faz tersti
    (tepe 06:00, dip 18:00) ve eski G10 bunu onaylıyordu (A2).
    """
    from sim.world_state import WorldState

    ws = WorldState(seed=11)
    day = 100
    # 24 saat tara (günlük baz önbellekli → tarama pürüzsüz/deterministik)
    hours = list(range(24))
    temps = [ws.sample_display_temp(day + h / 24.0) for h in hours]
    peak_h = hours[max(range(24), key=lambda h: temps[h])]
    dip_h = hours[min(range(24), key=lambda h: temps[h])]
    swing = max(temps) - min(temps)

    assert swing > 3.0, \
        f"G10 BAŞARISIZ: gün-içi salınım yok (salınım={swing:.2f}°C)"
    assert 13 <= peak_h <= 17, \
        f"G10 BAŞARISIZ: tepe saati {peak_h:02d}:00, [13-17] dışında (A2)"
    assert 3 <= dip_h <= 7, \
        f"G10 BAŞARISIZ: dip saati {dip_h:02d}:00, [03-07] dışında (A2)"

    if verbose:
        print(f"✅ G10 GEÇTİ: tepe {peak_h:02d}:00 "
              f"({max(temps):.1f}°C), dip {dip_h:02d}:00 "
              f"({min(temps):.1f}°C), salınım {swing:.1f}°C")
    return True


def gate_g25(verbose=True):
    """G25: Sonsuz koşu — DEAD yutucu durum değildir (§9.22).

    a) 1600 günlük popülasyonda her günün satırı vardır (ölümde gün
       ızgarası delinmez — eski `continue` kusuru ızgarayı delerdi).
    b) En az bir DEAD→SPROUTING rebirth geçişi görülür (seed 42 ~gün 1049).
    c) En uzun kesintisiz DEAD serisi 365 günden kısadır (takılma yok).
    d) WorldState yolu (web/serve hattı, §9.55 politikası): 0'dan 1500
       güne sıralı yürüyüşte en az bir döngü kapanır (resow + tohum
       yenilenir), DEAD serisi 365 günü bulmaz (takılma yok), yayın
       master tohumla (42) başlar.
    NPU/display gerekmez.
    """
    from sim.plant_sim import run_population
    from sim.world_state import WorldState

    df = run_population(n_plants=1, n_days=1600, seed=42)
    assert len(df) == 1600, \
        f"G25a BAŞARISIZ: {len(df)} satır (1600 değil — gün ızgarası delik)"
    assert df["day"].tolist() == list(range(1600)), \
        "G25a BAŞARISIZ: gün ızgarasında boşluk var"
    stages = df["stage"].tolist()
    assert "DEAD" in stages, \
        "G25b BAŞARISIZ: beklenen ölüm görülmedi (seed 42 ~gün 1049)"
    pairs = list(zip(stages, stages[1:]))
    assert any(a == "DEAD" and b == "SPROUTING" for a, b in pairs), \
        "G25b BAŞARISIZ: DEAD→SPROUTING rebirth geçişi yok"
    longest = cur = 0
    for s in stages:
        cur = cur + 1 if s == "DEAD" else 0
        longest = max(longest, cur)
    assert longest < 365, \
        f"G25c BAŞARISIZ: DEAD'de takılma ({longest} gün kesintisiz)"

    # Sıralı yürüyüş (0'dan itibaren — RNG kanonik akışta kalır; G1 disiplini).
    # Gelişigüzel güne zıplamak hava senaryosunu değiştirirdi.
    # §9.55: canlı katman döngüyü kapatır (resow) — çekirdek rebirth
    # yalnız run_population yolunda (a-c) sınanır.
    ws = WorldState(seed=42)
    assert ws.plant.seed == 42, \
        "G25d BAŞARISIZ: canlı yayın master tohumla başlamıyor"
    crossed = []
    seeds = set()
    for d in range(1500):
        ws.clock.sim_day = d
        ws.clock.day_frac = 0.0
        ws._last_stepped_day = d - 1
        ws.step_if_needed()
        crossed.append(ws.get_snapshot()["stage"])
        seeds.add(ws.plant.seed)
    assert ws.cycle_idx >= 1, \
        "G25d BAŞARISIZ: 1500 günde hiç döngü kapanmadı"
    assert len(seeds) > 1 and 42 in seeds, \
        f"G25d BAŞARISIZ: tohum yenilenmedi ({sorted(seeds)})"
    assert any(e["kind"] == "resow" for e in ws._events), \
        "G25d BAŞARISIZ: resow olayı yok"
    longest_ws = cur_ws = 0
    for s in crossed:
        cur_ws = cur_ws + 1 if s == "DEAD" else 0
        longest_ws = max(longest_ws, cur_ws)
    assert longest_ws < 365, \
        f"G25d BAŞARISIZ: WorldState DEAD'de takıldı ({longest_ws} gün)"

    if verbose:
        print(f"✅ G25 GEÇTİ: 1600 gün ızgara tam, rebirth var, "
              f"en uzun DEAD {longest} gün (<365), WorldState çıkar")
    return True


def gate_g30(verbose=True):
    """G30: Ölüm yalnız gerçek ölümdür (§9.31).

    a) Kuruyan-rezervli bitki DORMANT'a çekilir: kuraklık rejiminde
       `drought_dormancy` olayı görülür, aktif evreden direkt DEAD'e
       (yaprak bitmesiyle) düşüş olmaz.
    b) Her DEAD satırında root_health==0 veya tuber_mass<0.3 (kök
       çürüklüğü/tuz yanığı ya da rezervsiz açlık) — üç rejimde de.
    c) Su basma rejiminde ölüm kökten gelir: ilk DEAD girişinde yaprak
       yüksek (>50), kök sıfır.
    NPU/display gerekmez.
    """
    from sim.plant_sim import run_population

    ND = 400
    drought = {d: {"force_no_rain": True} for d in range(ND)}
    waterlog = {d: {"irrigation_mm": 30.0} for d in range(ND)}
    salt = {d: {"fertilizer_dose_mass": 20.0} for d in range(ND)}
    runs = {
        "drought": run_population(n_plants=1, n_days=ND, seed=7,
                                  scripted_events=drought),
        "waterlog": run_population(n_plants=1, n_days=ND, seed=7,
                                   scripted_events=waterlog),
        "salt": run_population(n_plants=1, n_days=ND, seed=7,
                               scripted_events=salt),
    }
    ACTIVE = ("SPROUTING", "VEGETATIVE", "FLOWERING", "SENESCENCE")
    for name, df in runs.items():
        p0 = df[df["plant_id"] == 0].reset_index(drop=True)
        # --- b) her DEAD satırı patoloji/açlık imzası taşır ---
        dead = p0[p0["stage"] == "DEAD"]
        bad = dead[(dead["root_health"] > 0) & (dead["tuber_mass"] >= 0.3)]
        assert len(bad) == 0, \
            f"G30b BAŞARISIZ ({name}): {len(bad)} DEAD satırı kök sağlam " \
            f"+ rezerv dolu (kuruma ölümü sızdı)"
        # --- a) aktif evreden direkt DEAD yalnız kök bitince olur ---
        stages = p0["stage"].tolist()
        roots = p0["root_health"].tolist()
        for (a, b), r in zip(zip(stages, stages[1:]), roots[1:]):
            assert not (a in ACTIVE and b == "DEAD" and r > 0), \
                f"G30a BAŞARISIZ ({name}): {a}→DEAD kök sağlamken " \
                f"(kuruma öldürdü)"

    # --- a) kuraklıkta uyku olayı var ---
    p0 = runs["drought"][runs["drought"]["plant_id"] == 0]
    assert "drought_dormancy" in p0["ground_truth_event"].tolist(), \
        "G30a BAŞARISIZ (drought): drought_dormancy olayı yok"
    # uyku rezervliyken gelir (yumru >= 0.3)
    first = p0[p0["ground_truth_event"] == "drought_dormancy"].iloc[0]
    assert first["tuber_mass"] >= 0.3, \
        "G30a BAŞARISIZ (drought): uyku rezervsiz geldi"

    # --- c) su basmada ölüm kökten, yaprak sapasağlam ---
    p0 = runs["waterlog"][runs["waterlog"]["plant_id"] == 0].reset_index(
        drop=True)
    idx = p0[p0["stage"] == "DEAD"].index.min()
    assert idx is not None and idx > 0, \
        "G30c BAŞARISIZ (waterlog): beklenen çürüme ölümü yok"
    row = p0.loc[idx]
    assert row["root_health"] == 0 and row["leaf_health"] > 50, \
        f"G30c BAŞARISIZ (waterlog): ölüm kökten değil " \
        f"(root={row['root_health']}, leaf={row['leaf_health']})"

    if verbose:
        print("✅ G30 GEÇTİ: kuruma→uyku, ölüm yalnız çürüme/açlık, "
              "su basma kökten öldürür")
    return True


def gate_g34(verbose=True):
    """G34: Toprak presetleri + deterministik sürüm (§9.35).

    a) Aynı sulamada tutma sıralaması: kumlu < tınlı < killi.
    b) spread=0 iki koşuda birebir aynı (eğitim determinizmi).
    c) soil="tınlı" == soil=None (varsayılan fizik kilitli).
    d) Bilinmeyen preset adı ValueError verir (sessiz düşüş yok).
    e) fiziksel-v1 thetaları tanımlı+tutarlı; bozuk tanım batar,
       thetasız dict'e dokunulmaz (§9.37).
    f) mini-F: v1'de 3×60mm θs'yi aşmaz, legacy'den düşük kalır (§9.39).
    NPU/display gerekmez.
    """
    from sim.plant_sim import run_population, soil_overrides

    irr = {d: {"irrigation_mm": 6.0} for d in range(5)}
    fin = {}
    for preset in ("kumlu", "tınlı", "killi"):
        df = run_population(n_plants=1, n_days=5, seed=5,
                            scripted_events=irr, soil=preset,
                            param_spread=0)
        fin[preset] = df[df.plant_id == 0].soil_moisture.iloc[-1]
    assert fin["kumlu"] < fin["tınlı"] < fin["killi"], \
        f"G34a BAŞARISIZ: tutma sırası bozuk {fin}"

    a = run_population(n_plants=3, n_days=60, seed=11, param_spread=0)
    b = run_population(n_plants=3, n_days=60, seed=11, param_spread=0)
    assert a.equals(b), "G34b BAŞARISIZ: spread=0 deterministik değil"

    dflt = run_population(n_plants=2, n_days=60, seed=11)
    tinli = run_population(n_plants=2, n_days=60, seed=11, soil="tınlı")
    assert dflt.equals(tinli), "G34c BAŞARISIZ: tınlı varsayılandan saptı"

    try:
        soil_overrides("çakıl")
        raise SystemExit("G34d BAŞARISIZ bayrağı")
    except ValueError:
        pass
    except SystemExit:
        raise AssertionError("G34d BAŞARISIZ: bilinmeyen preset sustu")

    # --- e) fiziksel-v1 kapasitesi tanımlı + tutarlı; bozuk tanım batar ---
    v1 = soil_overrides("fiziksel-v1")
    assert (v1["theta_wp"], v1["theta_fc"], v1["theta_s"]) == (18.0, 34.0, 48.0), \
        f"G34e BAŞARISIZ: fiziksel-v1 thetaları saptı {v1}"
    assert v1["theta_wp"] < v1["theta_fc"] < v1["theta_s"], \
        "G34e BAŞARISIZ: kapasite sıralaması bozuk"
    for bad in ({"theta_fc": 34.0},  # eksik tanım
                {"theta_s": 48.0, "theta_fc": 34.0, "theta_wp": 40.0},  # wp>fc
                {"theta_s": 30.0, "theta_fc": 34.0, "theta_wp": 18.0},  # fc>s
                {"theta_s": 48.0, "theta_fc": 0.0, "theta_wp": 18.0}):  # sıfır
        try:
            soil_overrides(bad)
            raise SystemExit(f"G34e BAŞARISIZ bayrağı ({bad})")
        except ValueError:
            pass
        except SystemExit:
            raise AssertionError(
                f"G34e BAŞARISIZ: tutarsız kapasite sustu ({bad})")
    assert soil_overrides({"field_capacity": 60.0}) == {"field_capacity": 60.0}, \
        "G34e BAŞARISIZ: thetasız dict'e dokunuldu"

    # --- f) v1 drenajı fazlayı çıkarır: mini-F (3×60mm) θs'yi aşmaz ---
    f_events = {d: {"irrigation_mm": 60.0} for d in range(3)}
    df_v1 = run_population(n_plants=1, n_days=3, seed=5,
                           scripted_events=f_events, soil="fiziksel-v1",
                           param_spread=0)
    df_leg = run_population(n_plants=1, n_days=3, seed=5,
                            scripted_events=f_events, soil="tınlı",
                            param_spread=0)
    m_v1 = df_v1.soil_moisture.iloc[-1]
    m_leg = df_leg.soil_moisture.iloc[-1]
    assert m_v1 <= 48.0, \
        f"G34f BAŞARISIZ: v1 mini-F θs'yi aştı ({m_v1:.1f})"
    assert m_v1 < m_leg, \
        f"G34f BAŞARISIZ: v1 drenajı legacy'den iyi değil " \
        f"(v1={m_v1:.1f}, legacy={m_leg:.1f})"

    if verbose:
        print(f"✅ G34 GEÇTİ: tutma {fin['kumlu']:.1f}<{fin['tınlı']:.1f}"
              f"<{fin['killi']:.1f}, spread=0 birebir, tınlı=varsayılan, "
              f"fiziksel-v1 18/34/48 + bekçi, mini-F v1={m_v1:.1f} "
              f"legacy={m_leg:.1f}")
    return True


def gate_g35(verbose=True):
    """G35: fiziksel-v1 su modeli (§9.40).

    a) Su defteri kapanır: clip'e takılmayan her günde
       infil−et−drain−uptake−Δdepo = 0 (±1e-9).
    b) Bitki alımı toprağı tüketir (v1'de uptake>0, legacy'de 0).
    c) Saat-altı bütünleme: deterministik, kuru-sıcak günde azalış,
       alımlı günde defter kapalı.
    NPU/display gerekmez.
    """
    from sim.plant_sim import Plant, PlantParams, Stage, soil_overrides

    # --- a) defter kapanışı (ıslak+kuru karışık 6 gün, tabana değmez) ---
    p = PlantParams()
    for k, v in soil_overrides("fiziksel-v1").items():
        setattr(p, k, v)
    pl = Plant(p, 0)
    pl.soil_moisture = 28.0
    pl.ec_mass = p.ec_baseline * 28.0
    sched = {0: 20.0, 3: 10.0}
    worst = 0.0
    for d in range(6):
        pl.step(345 + d, 8.0, 8.04, 0.0,
                irrigation_mm=sched.get(d, 0.0))
        b = pl.wb_last
        assert set(b) == {"infil", "et", "drain", "uptake",
                          "d_storage", "residual", "vpd_kpa",
                          "rh_frac"}, \
            f"G35a BAŞARISIZ: defter anahtarları eksik {sorted(b)}"
        worst = max(worst, abs(b["residual"]))
    assert worst < 1e-9, \
        f"G35a BAŞARISIZ: defter kapanmadı (en kötü residual={worst:.2e})"

    # --- b) alım toprağı tüketir (ıslak v1 toprağı, vejetatif, sıcak gün) ---
    def _scene(soil):
        pp = PlantParams()
        for k, v in soil_overrides(soil).items():
            setattr(pp, k, v)
        q = Plant(pp, 0)
        q.soil_moisture = 45.0
        q.ec_mass = pp.ec_baseline * 45.0
        q.stage = Stage.VEGETATIVE
        q.step(200, 25.0, 14.0, 0.0)
        return q
    v1q, legq = _scene("fiziksel-v1"), _scene("tınlı")
    assert v1q.wb_last["uptake"] > 0, \
        f"G35b BAŞARISIZ: v1 alımı sıfır ({v1q.wb_last['uptake']})"
    assert v1q.wb_last["uptake"] <= 45.0 - 18.0, \
        f"G35b BAŞARISIZ: alım solma-noktası altına indi " \
        f"({v1q.wb_last['uptake']:.3f})"
    assert legq.wb_last["uptake"] == 0.0, \
        "G35b BAŞARISIZ: legacy alımı toprağa dokundu"
    assert abs(v1q.wb_last["residual"]) < 1e-9, \
        f"G35b BAŞARISIZ: alımlı günde defter kapanmadı " \
        f"({v1q.wb_last['residual']:.2e})"

    # --- c) saat-altı bütünleme kararı ve defter uyumu ---
    def _v1plant(moist):
        pp = PlantParams()
        for k, v in soil_overrides("fiziksel-v1").items():
            setattr(pp, k, v)
        q = Plant(pp, 0)
        q.soil_moisture = moist
        q.ec_mass = pp.ec_baseline * moist
        q.stage = Stage.VEGETATIVE
        return q
    qa, qb = _v1plant(36.0), _v1plant(36.0)
    for d in range(3):
        qa.step(200 + d, 30.0, 14.0, 0.0)
        qb.step(200 + d, 30.0, 14.0, 0.0)
    assert qa.soil_moisture == qb.soil_moisture, \
        "G35c BAŞARISIZ: saat-altı bütünleme deterministik değil"
    assert qb.soil_moisture < 36.0, \
        f"G35c BAŞARISIZ: kuru-sıcak günde nem azalmadı ({qb.soil_moisture:.2f})"
    assert abs(qb.wb_last["residual"]) < 1e-9, \
        f"G35c BAŞARISIZ: bütünlemeli günde defter kapanmadı " \
        f"({qb.wb_last['residual']:.2e})"

    if verbose:
        print(f"✅ G35 GEÇTİ: su defteri 6 günde kapandı "
              f"(en kötü residual={worst:.1e}), alım v1={v1q.wb_last['uptake']:.3f} "
              f"legacy=0.0, bütünleme deterministik "
              f"(kuru-sıcak 36→{qb.soil_moisture:.2f})")
    return True


def main():
    print("=" * 60)
    print("Salep Dijital İkizi — Doğrulama Kapıları")
    print("=" * 60)
    print()

    results = {}

    # G5 (eylem kuyruğu) + G10 (diurnal) + G8 (lint) — hızlı kapılar önce
    print("--- G5: Eylem Kuyruğu ---")
    try:
        results["G5"] = gate_g5()
    except Exception as e:
        print(f"❌ G5 BAŞARISIZ: {e}")
        traceback.print_exc()
        results["G5"] = False

    print()

    print("--- G8: Placeholder Lint ---")
    try:
        results["G8"] = gate_g8()
    except Exception as e:
        print(f"❌ G8 BAŞARISIZ: {e}")
        traceback.print_exc()
        results["G8"] = False

    print()

    # G9 (NPU'suz dünya + lob sözleşmesi) — display ve NPU binary'siz
    print("--- G9: NPU'suz Dünya + Lob ---")
    try:
        results["G9"] = gate_g9()
    except Exception as e:
        print(f"❌ G9 BAŞARISIZ: {e}")
        traceback.print_exc()
        results["G9"] = False

    print()

    # G7 (kamera presetleri) — hızlı, display/NPU'suz
    print("--- G7: Kamera Presetleri ---")
    try:
        results["G7"] = gate_g7()
    except Exception as e:
        print(f"❌ G7 BAŞARISIZ: {e}")
        traceback.print_exc()
        results["G7"] = False

    print()

    # G14 (şema+soket+komut) — alt-süreçli, ~15 sn
    print("--- G14: Şema + Soket ---")
    try:
        results["G14"] = gate_g14()
    except Exception as e:
        print(f"❌ G14 BAŞARISIZ: {e}")
        traceback.print_exc()
        results["G14"] = False

    print()

    # G15+G16 (mesh tabanı + doku) — hızlı
    print("--- G15: Mesh Tabanı ---")
    try:
        results["G15"] = gate_g15()
    except Exception as e:
        print(f"❌ G15 BAŞARISIZ: {e}")
        traceback.print_exc()
        results["G15"] = False

    print()

    print("--- G16: Dokular ---")
    try:
        results["G16"] = gate_g16()
    except Exception as e:
        print(f"❌ G16 BAŞARISIZ: {e}")
        traceback.print_exc()
        results["G16"] = False

    print()

    print("--- G17: Canlı Döngü Kapanışı ---")
    try:
        results["G17"] = gate_g17()
    except Exception as e:
        print(f"❌ G17 BAŞARISIZ: {e}")
        traceback.print_exc()
        results["G17"] = False

    print()

    print("--- G18: Bitki Elektrofizyolojisi ---")
    try:
        results["G18"] = gate_g18()
    except Exception as e:
        print(f"❌ G18 BAŞARISIZ: {e}")
        traceback.print_exc()
        results["G18"] = False

    print()

    # G13 (prosedürel mesh) — hızlı
    print("--- G13: Prosedürel Mesh ---")
    try:
        results["G13"] = gate_g13()
    except Exception as e:
        print(f"❌ G13 BAŞARISIZ: {e}")
        traceback.print_exc()
        results["G13"] = False

    print()

    # G12 (sürekli görsel türevler) — hızlı
    print("--- G12: Sürekli Görseller ---")
    try:
        results["G12"] = gate_g12()
    except Exception as e:
        print(f"❌ G12 BAŞARISIZ: {e}")
        traceback.print_exc()
        results["G12"] = False

    print()

    # G11 (alan ayrılığı AST lint) — hızlı, her şeyden önce koşabilirdi
    print("--- G11: Alan Ayrılığı ---")
    try:
        results["G11"] = gate_g11()
    except Exception as e:
        print(f"❌ G11 BAŞARISIZ: {e}")
        traceback.print_exc()
        results["G11"] = False

    print()

    print("--- G10: Gün-İçi Sıcaklık (diurnal) ---")
    try:
        results["G10"] = gate_g10()
    except Exception as e:
        print(f"❌ G10 BAŞARISIZ: {e}")
        traceback.print_exc()
        results["G10"] = False

    print()

    # G2 (referans CSV oluşturma/eşleşme) — NPU gerektirmez
    print("--- G2: Sadakat Testi (CSV eşleşme) ---")
    try:
        results["G2"] = gate_g2()
    except Exception as e:
        print(f"❌ G2 BAŞARISIZ: {e}")
        traceback.print_exc()
        results["G2"] = False

    print()

    # G3 (sensör eşik testi) — NPU gerektirmez
    print("--- G3: Kanal Eşik Geçişleri ---")
    try:
        results["G3"] = gate_g3()
    except Exception as e:
        print(f"❌ G3 BAŞARISIZ: {e}")
        traceback.print_exc()
        results["G3"] = False

    print()

    # G25 (sonsuz koşu) — NPU gerektirmez
    print("--- G25: Sonsuz Koşu (rebirth) ---")
    try:
        results["G25"] = gate_g25()
    except Exception as e:
        print(f"❌ G25 BAŞARISIZ: {e}")
        traceback.print_exc()
        results["G25"] = False

    print()

    # G30 (ölüm disiplini) — NPU gerektirmez
    print("--- G30: Ölüm Yalnız Gerçek Ölümdür ---")
    try:
        results["G30"] = gate_g30()
    except Exception as e:
        print(f"❌ G30 BAŞARISIZ: {e}")
        traceback.print_exc()
        results["G30"] = False

    print()

    # G34 (toprak presetleri) — NPU gerektirmez
    print("--- G34: Toprak Presetleri ---")
    try:
        results["G34"] = gate_g34()
    except Exception as e:
        print(f"❌ G34 BAŞARISIZ: {e}")
        traceback.print_exc()
        results["G34"] = False

    print()

    # G35 (fiziksel-v1 su modeli) — NPU gerektirmez
    print("--- G35: Fiziksel-v1 Su Modeli ---")
    try:
        results["G35"] = gate_g35()
    except Exception as e:
        print(f"❌ G35 BAŞARISIZ: {e}")
        traceback.print_exc()
        results["G35"] = False

    print()

    # G36 (gözlem gürültüsü + SNN hazırlığı) — NPU gerektirmez
    print("--- G36: Gözlem Gürültüsü + SNN Hazırlığı ---")
    try:
        results["G36"] = gate_g36()
    except Exception as e:
        print(f"❌ G36 BAŞARISIZ: {e}")
        traceback.print_exc()
        results["G36"] = False

    print()

    # G37 (pertürbasyon bataryası) — NPU gerektirmez
    print("--- G37: Pertürbasyon Bataryası ---")
    try:
        results["G37"] = gate_g37()
    except Exception as e:
        print(f"❌ G37 BAŞARISIZ: {e}")
        traceback.print_exc()
        results["G37"] = False

    print()

    # G38 (çıkarım fazı) — NPU gerektirmez
    print("--- G38: Çıkarım Fazı 1. Tur ---")
    try:
        results["G38"] = gate_g38()
    except Exception as e:
        print(f"❌ G38 BAŞARISIZ: {e}")
        traceback.print_exc()
        results["G38"] = False

    print()

    # G39 (validation battery) — NPU gerektirmez (~40sn, 10k dahil)
    print("--- G39: Simulator Validation ---")
    try:
        results["G39"] = gate_g39()
    except Exception as e:
        print(f"❌ G39 BAŞARISIZ: {e}")
        traceback.print_exc()
        results["G39"] = False

    print()


def gate_g39(verbose=True):
    """G39: simulator validation battery (§9.51).

    sim/validate.py'deki 13 kapıyı koşar (TEST1-10 + TEST9b + ADV +
    REC). Eşikler validate.py'de ÖNDEN kayıtlıdır; bu kapı yalnız
    çalıştırır. NPU/binary gerekmez.
    """
    from sim.validate import run_all

    out = run_all(verbose=False)
    bad = sorted(k for k, v in out.items() if not v["pass"])
    assert not bad, f"G39 BAŞARISIZ: {bad}"

    if verbose:
        print(f"✅ G39 GEÇTİ: {len(out)}/{len(out)} validation "
              f"({', '.join(sorted(out))})")
    return True


def gate_g36(verbose=True):
    """G36: gözlem gürültüsü + SNN arayüz hazırlığı (§9.40).

    a) noise_std=0 birebir eski eşleme (iki örnek aynı çıktı);
       noise_std>0 tohumlu-tekrarlanabilir, aralıkta (0-100) ve
       iç hallere (ts EMA, hn/ph/npk) işlemez — yalnız gözlem.
    b) v1 karesi → mapper → lob zinciri çalışır: tn nemi izler,
       lob 10 karede 1 SET üretir. KAPALI DÖNGÜ YOK (§9.21 —
       otomatik bağlanma yasak, bu kapı yalnız arayüz uyumudur).
    NPU/binary gerekmez.
    """
    from sim.sensor_map import SensorMapper
    from sim.world_state import WorldState
    from sim.lobes.plant_npu import PlantNpuLobe, SENSORS_7

    snap = {"temp": 20.0, "rain_mm": 0.0, "soil_moisture": 40.0,
            "soil_ec": 1.0, "tuber_mass": 2.0}

    # --- a) gürültü disiplini ---
    c1, c2 = SensorMapper(), SensorMapper()
    r1 = [c1.update(dict(snap)) for _ in range(5)]
    r2 = [c2.update(dict(snap)) for _ in range(5)]
    assert r1 == r2, "G36a BAŞARISIZ: temiz eşleme deterministik değil"
    n1, n2 = SensorMapper(noise_std=8.0, noise_seed=11), \
        SensorMapper(noise_std=8.0, noise_seed=11)
    nr1 = [n1.update(dict(snap)) for _ in range(5)]
    nr2 = [n2.update(dict(snap)) for _ in range(5)]
    assert nr1 == nr2, "G36a BAŞARISIZ: tohumlu gürültü tekrarlanmıyor"
    assert any(a != b for a, b in zip(r1[0].values(), nr1[0].values())), \
        "G36a BAŞARISIZ: gürültü çıkışa yansımadı"
    for row in nr1:
        assert set(row) == set(SENSORS_7) and all(
            isinstance(v, int) and 0 <= v <= 100 for v in row.values()), \
            f"G36a BAŞARISIZ: aralık/şema saptı {row}"
    # Gözlem-only kanıtı: 20 kare sonra iç haller temiz örnekle aynı.
    c3, n3 = SensorMapper(), SensorMapper(noise_std=8.0, noise_seed=11)
    for _ in range(20):
        c3.update(dict(snap))
        n3.update(dict(snap))
    for attr in ("ts_ema", "hn_state", "ph_state", "npk_state"):
        assert getattr(n3, attr) == getattr(c3, attr), \
            f"G36a BAŞARISIZ: gürültü {attr} haline sızdı"

    # --- b) v1 → mapper → lob zinciri (açık döngü, bağlama yok) ---
    ws = WorldState(seed=7, soil="fiziksel-v1")
    mp, lobe = SensorMapper(), PlantNpuLobe(every_n_frames=10)
    tn_track = True
    for day in range(10):
        ws.clock.sim_day = day
        ws.clock.day_frac = 0.0
        ws.step_if_needed()
        s = ws.get_snapshot()
        out = mp.update(s, fert_dose=s.get("fert_dose", 0.0))
        tn_track &= (out["tn"] == int(max(0.0, min(100.0,
                                                  s["soil_moisture"]))))
        lobe.on_frame(out)
    assert tn_track, "G36b BAŞARISIZ: tn v1 nemini izlemiyor"
    assert lobe.sent_batches == 1, \
        f"G36b BAŞARISIZ: lob 10 karede 1 SET üretmedi " \
        f"({lobe.sent_batches})"
    cmd = lobe.commands()
    assert set(cmd.get("set", {})) == set(SENSORS_7), \
        "G36b BAŞARISIZ: SET 7 kanalı taşımıyor"

    if verbose:
        print("✅ G36 GEÇTİ: gürültü tohumlu+aralıkta+gözlem-only, "
              "v1→mapper→lob zinciri OK (kapalı döngü yok)")
    return True


def gate_g37(verbose=True):
    """G37: pertürbasyon bataryası — 11 hipotez (§9.45/§9.46).

    Hipotezler sim/perturb.py'de ÖNDEN kayıtlıdır (H1..H8); bu kapı
    bataryayı koşup hepsinin geçtiğini doğrular. Düşen hipotez =
    model sorgulanır (post-hoc eşik oynama yok).
    NPU/binary gerekmez.
    """
    from sim.perturb import run_battery, check_battery

    verdicts = check_battery(run_battery())
    bad = sorted(h for h, ok in verdicts.items() if not ok)
    assert not bad, f"G37 BAŞARISIZ: hipotezler düştü {bad}"

    if verbose:
        print(f"✅ G37 GEÇTİ: {len(verdicts)}/{len(verdicts)} hipotez "
              f"({', '.join(sorted(verdicts))})")
    return True


def gate_g38(verbose=True):
    """G38: çıkarım fazı 1. tur (§9.50) — N=150 sabit toplulukta
    D2+D3 keşfi tekrarlanır. 10k koşu kapıda koşmaz (hız); aynı kod
    yoludur (discover). D1 kapıda YOKTUR: küçük-N'de tuzlu alt-küme
    tanımsız kalır; D1 keşfi 10k kaydındadır.
    """
    from sim.events import run_ensemble
    from sim.infer import summarize, discover

    df, _ = run_ensemble(150, days=12, rh_mode="mixed")
    v = discover(summarize(df))
    assert v["D2"][3], f"G38 BAŞARISIZ: D2 tekrarlanmadı {v['D2']}"
    assert v["D3"][3], f"G38 BAŞARISIZ: D3 tekrarlanmadı {v['D3']}"

    if verbose:
        print(f"✅ G38 GEÇTİ: D2={v['D2'][0]:+.3f} D3={v['D3'][0]:+.3f} "
              f"(D1-KEŞİF 10k kaydında)")
    return True


def gate_g28(verbose=True):
    """G28: Gözlenen hava — gerçek istasyon dosyası (§9.26).

    a) Aydın dosyası yapısal olarak yüklenir (366 satır, year0=2026,
       1 Oca 2026 tam-tarih isabeti).
    b) Mini dosyayla koşu: dosyadaki günler birebir (sıcaklık/yağış),
       dosya-dışı gün sentetik yedek; aynı dosya → aynı sonuç.
    c) Öncelik: tam-tarih > gün-ay havuzu (iki yıllık dosyada dosya-dışı
       yıl aynı gün-ayın ortalamasını verir).
    d) Bozuk dosya (sütun eksik) yüksek sesle ValueError verir.
    e) UV dosyası: 366 satır yüklenir, açık-gün açığı 0, aralık 0..1.
    f) Uzama yönü (§9.27): kapalı UV koşusu açık koşudan uzun; oran
       formülü tutar; boy yumru seyrini değiştirmez.
    g) Gün-içi eğri (§9.30): 15:00 maks, 03:00 min çapası; dosyası
       WorldState display'i 15:00'te maksı verir; min/maks'sız dosya
       eğriyi kapatır (None).
    NPU/display gerekmez.
    """
    import tempfile
    from sim.plant_sim import load_observed_weather, run_population

    # --- a) gerçek Aydın dosyası ---
    real = os.path.join(os.path.dirname(SIM_DIR),
                        "open-meteo-37.86N27.87E108m.csv")
    if os.path.isfile(real):
        obs = load_observed_weather(real)
        assert obs.n_rows == 366, \
            f"G28a BAŞARISIZ: {obs.n_rows} satır (366 değil)"
        assert obs.year0 == 2026, \
            f"G28a BAŞARISIZ: year0={obs.year0} (2026 değil)"
        hit = obs.get(0, 0)  # 1 Oca 2026 tam-tarih
        assert hit is not None and isinstance(hit[0], float), \
            "G28a BAŞARISIZ: 1 Oca 2026 isabeti yok"
        if verbose:
            print(f"✅ G28a: Aydın dosyası OK "
                  f"({obs.n_rows} satır, year0={obs.year0})")
    elif verbose:
        print("⚠️  G28a: Aydın dosyası yok, atlandı (b/c/d koşuyor)")

    # --- b) mini dosya: birebir günler + sentetik yedek + determinizm ---
    with tempfile.TemporaryDirectory() as d:
        mini = os.path.join(d, "mini.csv")
        with open(mini, "w", encoding="utf-8") as fh:
            fh.write("time,temperature_2m_mean (°C),rain_sum (mm)\n"
                     "2026-01-01,15.0,2.0\n"
                     "2026-01-02,16.0,0.0\n"
                     "2026-01-03,14.0,5.0\n")
        df = run_population(n_plants=1, n_days=10, seed=1,
                            weather_csv=mini, weather_year=2026)
        assert len(df) == 10, f"G28b BAŞARISIZ: {len(df)} satır"
        r0 = df.iloc[0]
        assert r0["temp"] == 15.0 and r0["rain_mm"] == 2.0, \
            f"G28b BAŞARISIZ: gözlenen gün birebir değil " \
            f"({r0['temp']}, {r0['rain_mm']})"
        r9 = df.iloc[9]  # dosya-dışı gün: sentetik yedek, satır var
        assert abs(r9["temp"]) < 60.0, "G28b BAŞARISIZ: yedek sıcaklık"
        df2 = run_population(n_plants=1, n_days=10, seed=1,
                             weather_csv=mini, weather_year=2026)
        assert (df["temp"] == df2["temp"]).all() \
            and (df["rain_mm"] == df2["rain_mm"]).all(), \
            "G28b BAŞARISIZ: aynı dosya farklı sonuç verdi"

        # --- c) tam-tarih > gün-ay havuzu ---
        two = os.path.join(d, "two.csv")
        with open(two, "w", encoding="utf-8") as fh:
            fh.write("time,temperature_2m_mean (°C),rain_sum (mm)\n"
                     "2025-06-15,20.0,1.0\n"
                     "2026-06-15,30.0,3.0\n")
        obs2 = load_observed_weather(two, year0=2026)
        assert obs2.get(165, 165) == (30.0, 3.0), \
            "G28c BAŞARISIZ: tam-tarih önceliği yok"
        assert obs2.get(165 + 365, 165) == (25.0, 2.0), \
            "G28c BAŞARISIZ: gün-ay havuz ortalaması yok"

        # --- d) bozuk dosya yüksek sesle hatalı ---
        bad = os.path.join(d, "bad.csv")
        with open(bad, "w", encoding="utf-8") as fh:
            fh.write("time,temperature_2m_mean (°C)\n2026-01-01,15.0\n")
        try:
            load_observed_weather(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("G28d BAŞARISIZ: eksik sütuna ses yok")

    # --- e) UV dosyası: yükleme + açık-gün isabeti + açık aralığı ---
    from sim.plant_sim import attach_observed_uv, WorldDriver
    real_uv = os.path.join(os.path.dirname(SIM_DIR),
                           "open-meteo-37.88N27.88E108m.csv")
    if os.path.isfile(real_uv):
        obs_uv = attach_observed_uv(None, real_uv)
        assert obs_uv.n_uv == 366, \
            f"G28e BAŞARISIZ: {obs_uv.n_uv} UV satırı (366 değil)"
        hit = obs_uv.get_uv(14, 14)  # 15 Oca 2026 tam-tarih
        assert hit is not None and abs(hit[0] - 3.20) < 1e-9, \
            f"G28e BAŞARISIZ: UV isabeti {hit}"
        wd = WorldDriver(seed=1, observed=obs_uv)
        assert wd.uv_deficit(14, 14) == 0.0, \
            "G28e BAŞARISIZ: açık günde açık > 0"
        for t in range(0, 366, 7):
            dv = wd.uv_deficit(t, t % 365)
            assert 0.0 <= dv <= 1.0, \
                f"G28e BAŞARISIZ: açık aralık-dışı ({dv})"
        if verbose:
            print("✅ G28e: Aydın UV dosyası OK (366 satır, açık 0..1)")
    elif verbose:
        print("⚠️  G28e: Aydın UV dosyası yok, atlandı")

    # --- f) uzama yönü: kapalı UV > açık UV (§9.27) ---
    with tempfile.TemporaryDirectory() as d:
        wx = os.path.join(d, "w.csv")
        with open(wx, "w", encoding="utf-8") as fh:
            fh.write("time,temperature_2m_mean (°C),rain_sum (mm)\n")
            import datetime as _dt
            day = _dt.date(2026, 1, 1)
            for _ in range(90):
                fh.write(f"{day.isoformat()},18.0,5.0\n")
                day += _dt.timedelta(days=1)
        uva = os.path.join(d, "uva.csv")  # açık: uv == clear
        uvb = os.path.join(d, "uvb.csv")  # kapalı: uv == 0
        for p, u in ((uva, 5.0), (uvb, 0.0)):
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("time,uv_index_max,uv_index_clear_sky_max\n")
                day = _dt.date(2026, 1, 1)
                for _ in range(90):
                    fh.write(f"{day.isoformat()},{u},5.0\n")
                    day += _dt.timedelta(days=1)
        dfa = run_population(n_plants=1, n_days=60, seed=3,
                             weather_csv=wx, weather_year=2026,
                             weather_uv=uva)
        dfb = run_population(n_plants=1, n_days=60, seed=3,
                             weather_csv=wx, weather_year=2026,
                             weather_uv=uvb)
        ha, hb = dfa.iloc[-1]["stem_height"], dfb.iloc[-1]["stem_height"]
        assert ha > 0, "G28f BAŞARISIZ: açık koşuda boy artmadı"
        assert hb > ha, \
            f"G28f BAŞARISIZ: kapalı UV daha çok uzatmadı ({hb} <= {ha})"
        ratio = (hb - ha) / ha  # == jitter'lı gain (~1.0 ± %13)
        assert 0.8 < ratio < 1.2, \
            f"G28f BAŞARISIZ: uzama oranı formülden saptı ({ratio:.2f})"
        # Boy verimi etkilemez: yumru seyri iki koşuda birebir aynı.
        assert (dfa["tuber_mass"] == dfb["tuber_mass"]).all(), \
            "G28f BAŞARISIZ: boy yumruya sızdı"

    # --- g) gün-içi eğri (§9.30) ---
    from sim.plant_sim import reconstruct_hour_temp
    from sim.world_state import WorldState
    with tempfile.TemporaryDirectory() as d:
        mm = os.path.join(d, "mm.csv")
        with open(mm, "w", encoding="utf-8") as fh:
            fh.write("time,temperature_2m_mean (°C),rain_sum (mm),"
                     "temperature_2m_min (°C),temperature_2m_max (°C)\n"
                     "2026-01-01,15.0,0.0,10.0,20.0\n"
                     "2026-01-02,16.0,1.0,11.0,21.0\n")
        obs_mm = load_observed_weather(mm, year0=2026)
        assert obs_mm.get_day_curve(0, 0) == (10.0, 20.0), \
            "G28g BAŞARISIZ: gün çapası yok"
        assert reconstruct_hour_temp(10.0, 20.0, 15.0) == 20.0, \
            "G28g BAŞARISIZ: 15:00 maks değil"
        assert reconstruct_hour_temp(10.0, 20.0, 3.0) == 10.0, \
            "G28g BAŞARISIZ: 03:00 min değil"
        assert reconstruct_hour_temp(10.0, 20.0, 9.0) == 15.0, \
            "G28g BAŞARISIZ: 09:00 orta değil"
        ws_mm = WorldState(seed=1, weather_csv=mm, weather_year=2026)
        assert ws_mm.sample_display_temp(15 / 24) == 20.0, \
            "G28g BAŞARISIZ: display 15:00'te maksı vermedi"
        assert ws_mm.sample_display_temp(3 / 24) == 10.0, \
            "G28g BAŞARISIZ: display 03:00'te mini vermedi"
        # Min/maks'sız dosya: eğri kapalı, fizik yedeği çalışır.
        with open(os.path.join(d, "plain.csv"), "w",
                  encoding="utf-8") as fh:
            fh.write("time,temperature_2m_mean (°C),rain_sum (mm)\n"
                     "2026-01-01,15.0,0.0\n")
        obs_plain = load_observed_weather(os.path.join(d, "plain.csv"),
                                          year0=2026)
        assert obs_plain.get_day_curve(0, 0) is None, \
            "G28g BAŞARISIZ: sütunsuz dosyada eğri açılmamalı"

    if verbose:
        print("✅ G28 GEÇTİ: birebir gün + yedek + öncelik + hata sesi + "
              "UV/boy + gün-içi eğri")
    return True


    # G28 (gözlenen hava) — NPU gerektirmez
    print("--- G28: Gözlenen Hava (Aydın) ---")
    try:
        results["G28"] = gate_g28()
    except Exception as e:
        print(f"❌ G28 BAŞARISIZ: {e}")
        traceback.print_exc()
        results["G28"] = False

    print()

    # G1 (headless köprü) — NPU gerektirir
    print("--- G1: Headless Köprü (365 gün) ---")
    try:
        results["G1"] = gate_g1(days=365)
    except Exception as e:
        print(f"❌ G1 BAŞARISIZ: {e}")
        traceback.print_exc()
        results["G1"] = False

    print()

    # G4 emekli (Qt, W0 ile karşılıksız)
    print("--- G4: Emekli Qt render (karşılıksız) ---")
    try:
        results["G4"] = gate_g4()
    except Exception as e:
        print(f"❌ G4 BAŞARISIZ: {e}")
        traceback.print_exc()
        results["G4"] = False

    print()

    # G6 emekli (Qt, W0 ile karşılıksız)
    print("--- G6: Emekli Qt piksel farkı (karşılıksız) ---")
    try:
        results["G6"] = gate_g6()
    except Exception as e:
        print(f"❌ G6 BAŞARISIZ: {e}")
        traceback.print_exc()
        results["G6"] = False

    print()
    print("=" * 60)
    print("SONUÇ:")
    for gate, passed in results.items():
        if passed == "skip":
            status = "⏭️  SKIP"
        else:
            status = "✅ GEÇTİ" if passed else "❌ BAŞARISIZ"
        print(f"  {gate}: {status}")
    print("=" * 60)

    all_passed = all(v is True or v == "skip" for v in results.values())
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
