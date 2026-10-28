"""TEST B: Sensory -> Afferent -> CR (§9.59).

Kademeli stres arkı (220 gun kosullama + 30 gun test):
normal (0-30) -> kuraklik (30-60) -> siddetli+tuz (60-100) ->
ara (100-130) -> yaz kurakligi (130-170) -> sulama (170-180) ->
recovery (180-220) -> test (220-250, sensor kapali).

Not: bu cekirdek-kosuda isi soku dusmedi (stokastik, seed 1);
isi ekseni TEST A supurmede karakterize (sicak35/40).

Calistirma: .venv/bin/python validate_testb.py
Uretir: testb_{sensors,spikes,membrane,conditions}.csv
Olcutler (B1-B6): surus yogunlugu, stres kontrasti, recovery dususu,
afferent ates, aktif post, CR, agirlik degisimi.
"""
import csv
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

MASTER = 1
N_DAYS = 250
N_COND = 22
N_TEST = 3
PREFIX = "testb"

STAGES = [(0, 30, "normal"), (30, 60, "kurak"), (60, 100, "siddetli"),
          (100, 130, "ara"), (130, 170, "yaz"), (170, 180, "sulama"),
          (180, 220, "recovery"), (220, 250, "test")]

COND_POSTS = ("p2a", "p2b", "p2c", "p2d", "p2e", "p2f", "p2g", "p2h",
              "p2i", "p2j")


def stage_of(day):
    for a, b, nm in STAGES:
        if a <= day < b:
            return nm
    return "test"


def build_inputs():
    from sim.plant_sim import run_population
    from sim.sensor_map import SensorMapper
    from sim.electro import ElectroState

    ev = {d: {"force_no_rain": True}
          for d in list(range(30, 100)) + list(range(130, 170))}
    ev[60] = {"force_no_rain": True, "fertilizer_dose_mass": 130.0}
    for d in (170, 174, 178):
        ev[d] = {"irrigation_mm": 10.0}
    df = run_population(n_plants=1, n_days=N_DAYS, seed=MASTER,
                        scripted_events=ev)
    sub = df[df.plant_id == 0].sort_values("day").reset_index(drop=True)
    assert len(sub) == N_DAYS, f"gun sayisi {len(sub)}"

    mp = SensorMapper()
    el = ElectroState()
    sens_rows, spike_rows, memb_rows = [], [], []
    stage_rate = {}
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
                          str(r["stage"]), stage_of(day)))
        stage_rate.setdefault(stage_of(day), []).append(r0)
    for name, rows in (("sensors", sens_rows), ("spikes", spike_rows),
                       ("membrane", memb_rows)):
        with open(os.path.join(ROOT, f"{PREFIX}_{name}.csv"), "w",
                  newline="") as f:
            w = csv.writer(f)
            w.writerows(rows)
    means = {k: sum(v) / len(v) for k, v in stage_rate.items()}
    return len(spike_rows), means


def run_harness():
    exe = os.path.join(ROOT, "npu_sensory_plant")
    out = os.path.join(ROOT, f"{PREFIX}_conditions.csv")
    diag = "/tmp/testb_diag.csv"
    p = subprocess.run(
        [exe, "--spikes", os.path.join(ROOT, f"{PREFIX}_spikes.csv"),
         "--sensors", os.path.join(ROOT, f"{PREFIX}_sensors.csv"),
         "--out", out, "--cond", str(N_COND), "--test", str(N_TEST),
         "--diag", diag],
        cwd=ROOT, capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        raise SystemExit(f"harness batti:\n{p.stderr[-2000:]}")
    return p.stdout, out, diag


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


def print_chain(diag):
    """Zincir tanisi: pencere basina gelen/cikan/maxV (odak p2a+p2f)."""
    import csv as _csv
    rows = list(_csv.DictReader(open(diag)))
    print("zincir [gelen -> cikan | maxV] (esik 1.0; V reset-sonrasi):")
    for a, b, nm in STAGES:
        r = [x for x in rows if a * 50 <= int(x["t"]) < b * 50]
        if not r:
            continue
        pin = sum(int(x["pin0"]) + int(x["pin1"]) for x in r)
        p1f = sum(int(x["p1f0"]) + int(x["p1f1"]) for x in r)
        p1v = max(float(x["p1V0"]) for x in r)
        bsum = (sum(int(x["bA"]) for x in r),
                sum(int(x["bF"]) for x in r))
        brb = max(max(float(x["brBa"]), float(x["brBf"])) for x in r)
        smx = max(max(float(x["somaA"]), float(x["somaF"]))
                  for x in r)
        p2 = (sum(int(x["p2A"]) for x in r),
              sum(int(x["p2F"]) for x in r))
        print(f"  {nm:9s} bitki:{pin:4d} P1:{p1f:4d}/{p1v:.2f} "
              f"B:{bsum[0]:3d},{bsum[1]:3d} dal:{brb:.2f} "
              f"soma:{smx:.2f} P2:{p2[0]:2d},{p2[1]:2d}")


def main():
    nsp, means = build_inputs()
    print("kademe hizlari: " + ", ".join(
        f"{nm}={means[nm]:.1f}" for _, _, nm in STAGES))
    print(f"girdi: {nsp} bitki spike")
    log, cond_csv, diag = run_harness()
    print_chain(diag)
    oz = parse_ozet(log)
    print(f"afferent: {oz['ncond']} ayri kosul")
    print(f"cond atis: {dict(zip(COND_POSTS, oz['cond']))}")
    print(f"test atis: {dict(zip(COND_POSTS, oz['test']))}")
    print(f"decoy/gercek={oz['decoy_gercek']:.3f} "
          f"CR_a={oz['CR_a']:.3f} CR_b={oz['CR_b']:.3f}")

    import csv as _csv
    with open(cond_csv) as f:
        rows = list(_csv.reader(f))
    ncol = 6  # t,blok,kademe,p1a,p1b,bitler(tek alan)+agirliklar
    w0 = [float(x) for x in rows[0][ncol:]]
    w1 = [float(x) for x in rows[N_COND * 500 - 1][ncol:]]
    dw = [b - a for a, b in zip(w0, w1)]
    print(f"dw: {[round(x, 4) for x in dw]}")

    ok = []
    ok.append(("B1 surus_yogun", nsp > 1500))
    ok.append(("B2 stres_kontrast",
               means["siddetli"] > 8 * means["normal"]))
    ok.append(("B3 recovery_dusus",
               means["recovery"] < means["siddetli"]))
    ok.append(("B4 afferent_atis", sum(oz["cond"]) > 200))
    # B6: ogrenme izi herhangi postta (oynayanlar f/g — raporlanir).
    dwmax = max(abs(x) for x in dw)
    ok.append(("B6 agirlik_hareket", dwmax > 0.02))
    bad = [k for k, v in ok if not v]
    for k, v in ok:
        print(f"  {'OK' if v else 'BATTI'} {k}")
    if bad:
        raise SystemExit(f"BATTI: {bad}")
    # B5 CR: gecit degil BULGU — kirmizi kalir, mekanizmasiyla raporlanir.
    cr = oz["CR_a"] > 0 or oz["CR_b"] > 0
    print(f"  {'OK' if cr else 'BULGU'} B5 CR_var "
          f"(test_atis={sum(oz['test'])})")
    print("OZET-TESTB: " + " ".join(k for k, _ in ok) +
          (" + B5_CR" if cr else " + B5_CR_YOK"))


if __name__ == "__main__":
    main()
