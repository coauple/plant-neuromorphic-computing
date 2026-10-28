"""SNR topluluk orkestrasyonu (STIMULUS_SNR_SPEC.md A0/A1/A2).

Senaryo x tohum -> front->plant->v3d -> 7 ozellik. Cikti:
stress_out_snr/snr_ensemble.csv (+ snr_gates.json).
DEGISTIRILMEZ: src/, sim/, kanonik CSV/PNG, encoder, sensory, v3d C++.
Ayni (senaryo,tohum) varsa kosulmaz (determinizm bit-esit kanitli).
"""
import argparse
import csv
import hashlib
import json
import math
import os
import statistics as st
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "encoder"))
import run_chain_v3 as C  # noqa: E402

WV = os.path.join(ROOT, "weather_v3")
PLANT = os.path.join(ROOT, "npu_sensory_plant")
OUT = "/tmp/snr"
REP = os.path.join(ROOT, "stress_out_snr")
SEEDS = [42, 43, 44, 101, 102]

SCEN = {
    "base": {"weather": f"{WV}/W-base.csv"},
    "dryold": {"weather": f"{WV}/W-base.csv", "drought": True,
               "drought_from": 60, "drought_len": 60},
    "drynew": {"weather": f"{WV}/W-dry.csv"},
    "irrig": {"weather": f"{WV}/W-base.csv", "irrig": 20.0},
    "hot": {"weather": f"{WV}/W-hot.csv"},
    "fert": {"weather": f"{WV}/W-base.csv", "fert": 30.0},
    "s1": {"weather": f"{WV}/W-s1.csv"},
    "s2": {"weather": f"{WV}/W-s2.csv"},
}
FEATS = ["ec_mean", "tn_mean", "ch0_n", "ch1_bdays", "cable_n", "lob_n",
         "effD"]


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def run_case(sc, seed):
    d = f"{OUT}/{sc}_s{seed}"
    mem = f"{d}/c/mem.csv"
    if os.path.exists(mem):
        print(f"  reuse {sc} s{seed}", flush=True)
        return d
    os.makedirs(d, exist_ok=True)
    kw = dict(SCEN[sc])
    cmd = [sys.executable, os.path.join(ROOT, "drive_line_front.py"),
           "--seed", str(seed), "--days", "130", "--outdir", d]
    for k, v in kw.items():
        fl = f"--{k}".replace("_", "-")
        cmd += [fl, str(v)] if v is not True else [fl]
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       timeout=900)
    assert p.returncode == 0, p.stderr[-500:]
    p = C.run([PLANT, "--spikes", f"{d}/pspikes.csv", "--sensors",
               f"{d}/sensors.csv", "--out", f"{d}/plant_out.csv",
               "--aff", f"{d}/afferent.csv", "--cond", "10", "--test",
               "3"])
    assert p.returncode == 0, p.stderr[-500:]
    os.makedirs(f"{d}/c", exist_ok=True)
    _, evs, full, _ = C.stage_intake(f"{d}/afferent.csv", f"{d}/c")
    _, spk = C.stage_encoder(evs, f"{d}/c")
    aff2 = C.stage_adapter(spk, evs, full, f"{d}/c")
    C.stage_v3(aff2, f"{d}/c", "0.30")
    return d


def features(d):
    sens = list(csv.reader(open(f"{d}/sensors.csv")))
    ec = [float(r[2]) for r in sens]
    tn = [float(r[5]) for r in sens]
    spk = list(csv.reader(open(f"{d}/pspikes.csv")))
    ch0 = sum(1 for r in spk if r[1] == "0")
    ch1d = len({r[0] for r in spk if r[1] == "1"})
    aff = list(csv.DictReader(open(f"{d}/afferent.csv")))
    mem = list(csv.DictReader(open(f"{d}/c/mem.csv")))
    return {"ec_mean": round(st.mean(ec), 2),
            "tn_mean": round(st.mean(tn), 2), "ch0_n": ch0,
            "ch1_bdays": ch1d, "cable_n": len(aff),
            "lob_n": len(mem),
            "effD": len({r["eff_g"] for r in mem})}


def dose_of(sc):
    rain = 0.0
    w = SCEN[sc].get("weather")
    if w:
        with open(w, newline="") as f:
            for r in csv.DictReader(f):
                rain += float(r.get("rain_sum (mm)", 0.0))
    irr = SCEN[sc].get("irrig", 0.0)
    ilen = SCEN[sc].get("irrig_len", 130)
    ifrom = SCEN[sc].get("irrig_from", 0)
    if irr:
        rain += irr * max(0, min(130, ifrom + ilen) - ifrom)
    return round(rain, 1)


def snr(vals, base):
    m = st.mean(vals)
    s = st.pstdev(vals) if len(vals) > 1 else 0.0
    if s == 0:
        return (float("inf"), m) if m != base else (0.0, m)
    return (round(abs(m - base) / s, 2), round(m, 2))


def main():
    ap = argparse.ArgumentParser(description="SNR toplulugu")
    ap.add_argument("--scens", default="",
                    help="ornek: base,dryold,drynew (bos=hepsi)")
    ap.add_argument("--seeds", default="",
                    help="ornek: 42,43 (bos=SPEC beslisi)")
    a = ap.parse_args()
    scens = [s.strip() for s in a.scens.split(",") if s.strip()] or \
        sorted(SCEN)
    seeds = [int(s) for s in a.seeds.split(",") if s.strip()] or SEEDS
    os.makedirs(REP, exist_ok=True)
    rows = []
    for sc in scens:
        assert sc in SCEN, sc
        for sd in seeds:
            d = run_case(sc, sd)
            f = features(d)
            f.update({"scen": sc, "seed": sd, "dose": dose_of(sc),
                      "md5": sha(f"{d}/afferent.csv")[:12]})
            rows.append(f)
            print(f"  {sc} s{sd}: " +
                  " ".join(f"{k}={f[k]}" for k in FEATS), flush=True)
    keep = {}
    ep = os.path.join(REP, "snr_ensemble.csv")
    if os.path.exists(ep):
        with open(ep, newline="") as fh:
            for r in csv.DictReader(fh):
                for k in FEATS + ["dose"]:
                    try:
                        r[k] = float(r[k])
                    except (ValueError, TypeError):
                        pass
                keep[(r["scen"], r["seed"])] = r
    for r in rows:
        keep[(r["scen"], str(r["seed"]))] = r
    rows = [keep[k] for k in sorted(keep)]
    with open(ep, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["scen", "seed", "dose",
                                           "md5"] + FEATS)
        w.writeheader()
        w.writerows(rows)
    # SNR tablosu (base referansli).
    base = {k: st.mean([r[k] for r in rows if r["scen"] == "base"])
            for k in FEATS}
    gates = {}
    for sc in scens:
        if sc == "base":
            continue
        line = {}
        for k in FEATS:
            v, m = snr([r[k] for r in rows if r["scen"] == sc], base[k])
            line[k] = v
        gates[sc] = line
        print(f"  SNR({sc}): " +
              " ".join(f"{k}={v}" for k, v in line.items()), flush=True)
    with open(os.path.join(REP, "snr_gates.json"), "w") as fh:
        json.dump({"snr": gates, "base_mean": base}, fh, default=str)
    for sc in gates:
        for g, k, th in (("G-SNR0", "cable_n", 10),
                         ("G-SNR1", "lob_n", 10)):
            v = gates[sc][k]
            ok = (v == float("inf")) or (isinstance(v, (int, float))
                                         and v >= th)
            print(f"  {'OK' if ok else '--'} {g}[{sc}]({k}={v})",
                  flush=True)
    if "drynew" in gates:
        ok = all((gates["drynew"][k] == float("inf")) or
                 gates["drynew"][k] >= th
                 for k, th in (("cable_n", 10), ("lob_n", 10)))
        print(f"  {'OK' if ok else 'BATTI'} A0-KAPI(drynew)", flush=True)
    if "dryold" in gates:
        empty = all(gates["dryold"][k] < 10 for k in
                    ("cable_n", "lob_n"))
        print(f"  {'OK' if empty else '??'} A0-KONTROL(dryold-bos)",
              flush=True)
    print("OZET-SNR: ensemble bitten")


if __name__ == "__main__":
    main()
