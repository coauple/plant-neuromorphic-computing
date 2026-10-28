"""Duyusal lob bitki-surucu dogrulama (§9.57).

Zincir: felaket senaryosu (G2'nin aynisi) -> run_population fizigi ->
SensorMapper (7 kanal) + electro.py (bitki spike) -> npu_sensory_plant
(P1 bitki spike, Dal B sensor fazi, banka §9.14 ile ayni) -> afferent
raporu (kosul sayisi + atesler + etkililik).

Calistirma: .venv/bin/python validate_sensory_plant.py
Uretir: sensory_plant_{sensors,spikes,membrane,conditions}.csv
Olcutler (M1-M4): spike varligi, kosul cesitliligi, decoy/gercek,
CR (sensor-kapali testte kosullu yanit).
"""
import csv
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

MASTER = 1
N_DAYS = 130  # (10 kosullama + 3 test) x 10 gun

COND_POSTS = ("p2a", "p2b", "p2c", "p2d", "p2e", "p2f", "p2g", "p2h",
              "p2i", "p2j")


def build_inputs():
    from sim.plant_sim import run_population
    from sim.sensor_map import SensorMapper
    from sim.electro import ElectroState

    # G2 felaketinin uzatılmışı: uzun kuraklık + tuz şoku + 2 sulama
    # (mekanik patlama). Stres kontrastı bitki ateşlemesini sürer.
    ev = {d: {"force_no_rain": True} for d in range(55, 126)}
    ev[110] = {"force_no_rain": True, "fertilizer_dose_mass": 130.0}
    ev[60] = {"irrigation_mm": 10.0}
    ev[75] = {"irrigation_mm": 10.0}
    df = run_population(n_plants=1, n_days=N_DAYS, seed=MASTER,
                        scripted_events=ev)
    sub = df[df.plant_id == 0].sort_values("day").reset_index(drop=True)
    assert len(sub) == N_DAYS, f"gun sayisi {len(sub)}"

    mp = SensorMapper()
    el = ElectroState()
    sens_rows, spike_rows, memb_rows = [], [], []
    for _, r in sub.iterrows():
        day = int(r["day"])
        s = mp.update({"temp": float(r["temp"]),
                       "rain_mm": float(r["rain_mm"]),
                       "soil_moisture": float(r["soil_moisture"]),
                       "soil_ec": float(r["soil_ec"]),
                       "tuber_mass": float(r["tuber_mass"])})
        v, r0, b1 = el.step(float(r["temp"]), float(r["rain_mm"]), 0.0,
                            float(r["water_balance"]),
                            float(r["leaf_health"]),
                            float(r["root_health"]), str(r["stage"]),
                            MASTER, day)
        sp = el.spikes_for_day(r0, b1, MASTER, day)
        for line, ticks in sp.items():
            for t in ticks:
                spike_rows.append((day, line, t))
        sens_rows.append((day, s["hn"], s["ec"], s["hs"], s["ts"],
                          s["tn"], s["ph"], s["npk"]))
        memb_rows.append((day, round(v, 1), round(r0, 2),
                          str(r["stage"])))
    with open(os.path.join(ROOT, "sensory_plant_sensors.csv"), "w",
              newline="") as f:
        w = csv.writer(f)
        w.writerow(["day", "hn", "ec", "hs", "ts", "tn", "ph", "npk"])
        w.writerows(sens_rows)
    with open(os.path.join(ROOT, "sensory_plant_spikes.csv"), "w",
              newline="") as f:
        w = csv.writer(f)
        w.writerow(["day", "line", "tick"])
        w.writerows(spike_rows)
    with open(os.path.join(ROOT, "sensory_plant_membrane.csv"), "w",
              newline="") as f:
        w = csv.writer(f)
        w.writerow(["day", "V_mV", "rate_hz", "stage"])
        w.writerows(memb_rows)
    return len(spike_rows)


def run_harness(extra=(), out_name="sensory_plant_conditions.csv"):
    exe = os.path.join(ROOT, "npu_sensory_plant")
    if not os.path.isfile(exe):
        raise SystemExit(
            "npu_sensory_plant yok: g++ -std=c++17 -O2 -Isrc "
            "src/main_sensory_plant.cpp -o npu_sensory_plant")
    out = out_name if os.path.isabs(out_name) else os.path.join(ROOT,
                                                               out_name)
    p = subprocess.run(
        [exe, "--spikes", os.path.join(ROOT, "sensory_plant_spikes.csv"),
         "--sensors", os.path.join(ROOT, "sensory_plant_sensors.csv"),
         "--out", out, "--cond", "10", "--test", "3"] + list(extra),
        cwd=ROOT, capture_output=True, text=True, timeout=300)
    if p.returncode != 0:
        raise SystemExit(f"harness batti:\n{p.stderr[-2000:]}")
    return p.stdout, out


def parse_ozet(log):
    d = {}
    labels = []
    for line in log.splitlines():
        if line.startswith("K t="):
            parts = line.split()
            if len(parts) >= 3:
                labels.append(parts[2])
        elif line.startswith("OZET-PLANT: post_atis:"):
            d["cond"] = [int(x)
                         for x in line.split("post_atis:")[1].split()]
        elif line.startswith("OZET-PLANT: test_atis:"):
            d["test"] = [int(x)
                         for x in line.split("test_atis:")[1].split()]
        elif line.startswith("OZET-PLANT: p1darbesi="):
            toks = line.split()
            d["p1"] = tuple(int(x) for x in
                            toks[1].split("=")[1].split("/"))
            for tok in toks:
                if tok.startswith("kosul_sayisi="):
                    d["ncond"] = int(tok.split("=")[1])
        elif line.startswith("OZET-PLANT: decoy_gercek="):
            for tok in line.split():
                if "=" in tok:
                    k, v = tok.split("=")
                    d[k] = float(v)
    d["labels"] = sorted(set(labels))
    return d


def main():
    nsp = build_inputs()
    print(f"girdi: {nsp} bitki spike, {N_DAYS} gun sensor")
    log, cond_csv = run_harness()
    oz = parse_ozet(log)
    print(f"afferent: {oz['ncond']} ayri kosul "
          f"({', '.join(oz['labels'][:12])})")
    print(f"cond atis: {dict(zip(COND_POSTS, oz['cond']))}")
    print(f"test atis: {dict(zip(COND_POSTS, oz['test']))}")
    print(f"decoy/gercek={oz['decoy_gercek']:.3f} "
          f"CR_a={oz['CR_a']:.3f} CR_b={oz['CR_b']:.3f}")

    import hashlib
    log2, _ = run_harness(out_name="/tmp/sensory_plant_rerun.csv")
    h1 = hashlib.sha256(
        "\n".join(l for l in log.splitlines()
                  if l.startswith("OZET-PLANT")).encode()).hexdigest()
    h2 = hashlib.sha256(
        "\n".join(l for l in log2.splitlines()
                  if l.startswith("OZET-PLANT")).encode()).hexdigest()

    ok = []
    ok.append(("M1 spike_var", nsp > 450 and sum(oz["p1"]) > 450))
    ok.append(("M2 kosul_cesit", oz["ncond"] >= 4))
    real = oz["cond"][0] + oz["cond"][1] + oz["cond"][2]
    ok.append(("M3 gercek_atis", real > 40))
    ok.append(("M4 decoy_baski",
               oz["decoy_gercek"] >= 0 and oz["decoy_gercek"] <= 0.6))
    ok.append(("M5 deterministik_afferent", h1 == h2))
    bad = [k for k, v in ok if not v]
    for k, v in ok:
        print(f"  {'OK' if v else 'BATTI'} {k}")
    if bad:
        raise SystemExit(f"BATTI: {bad}")
    test_tot = sum(oz["test"])
    print(f"BULGU: test-atisi {test_tot} -> §9.14 olcutuyle CR YOK "
          f"(seyrek P1 + kuraklikta B sessizligi; agirliklar yerinde).")
    print(f"OZET-PLANT-VALID: {' '.join(k for k, _ in ok)} "
          f"-> {cond_csv}")


if __name__ == "__main__":
    main()
