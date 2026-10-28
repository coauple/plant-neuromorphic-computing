"""KPR analiz: N_sig / amp_break / S_share-merkez / simetri / K2K3-rol.
Kullanim: python3 pattern/kpr_analyze.py
Cikti: pattern/p0_out/kpr_budget.json (+ stdout).
"""
import csv
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "pattern", "p0_out")

import sys
sys.path.insert(0, os.path.join(ROOT, "pattern"))
import kpr_drive as D  # noqa: E402


def rnd(v, nd=9):
    if isinstance(v, (list, tuple)):
        return tuple(round(float(x), nd) for x in v)
    return round(float(v), nd)


def load():
    with open(os.path.join(OUT, "kpr_runs.json")) as f:
        store = json.load(f)
    arms = {}
    with open(os.path.join(OUT, "kpr_axes.csv")) as f:
        for r in csv.DictReader(f):
            arms[r["id"]] = r
    return store, arms


def n_sig(sims):
    sigs = []
    for tr in sims:
        sigs.append(tuple((rnd(tr[str(u)]["g0"][::10]),
                           tuple(tr[str(u)]["fire_ticks"]))
                          for u in range(6)))
    return len(set(sigs))


def s_center(sims, slots):
    # merkez-eslesen (birim,slot) S_share ortalamasi (S5 merkezleri).
    centers = {0: 1, 1: 4, 2: 7, 3: 5, 4: 6, 5: 0}
    vals = []
    for tr, s in zip(sims, slots):
        for u, c in centers.items():
            if c == s:
                vals.append(tr[str(u)]["S_share"])
    return sum(vals) / max(1, len(vals)), len(vals)


def main():
    store, arms = load()
    cfgs = ["C0", "F1", "F1sep", "F1sepF4", "F1sepF8", "FULL"]
    rep = {"N_sig": {}, "amp_break": {}, "S_center": {}, "simetri": {},
           "K2K3": {}}
    for cfg in cfgs:
        for d in ("0", "1"):
            ids = [f"kpr_{cfg}_d{d}_s{s}" for s in range(12)]
            sims = [store[i] for i in ids]
            rep["N_sig"].setdefault(cfg, {})[d] = n_sig(sims)
            if d == "0":
                v, n = s_center(sims, list(range(12)))
                rep["S_center"][cfg] = {"ort": round(v, 4), "n": n}
    for cfg in cfgs:
        curve = []
        for a in ("0.25", "0.5", "1.0", "2.0"):
            ids = [f"kpr_{cfg}_a{a}_s{s}" for s in range(12)]
            curve.append((float(a), n_sig([store[i] for i in ids])))
        below = [a for a, v in curve if v < 10]
        rep["amp_break"][cfg] = {"amp_break": max(below) if below else None,
                                 "egri": curve}
    for cfg in ["C0", "F1", "FULL"]:
        w = D.impulse_weights(cfg)
        rep["simetri"][cfg] = {"agirliklar": [round(x, 5) for x in w],
                               "minmaks": round(min(w) / max(w), 4)}
        r, raw = D.persistence(cfg)
        rep["K2K3"][cfg] = {"oran": round(r, 3),
                            "k2": round(raw["k2"], 2),
                            "k3": round(raw["k3"], 2)}
    with open(os.path.join(OUT, "kpr_budget.json"), "w") as f:
        json.dump(rep, f, indent=1)
    print("konfig: N_sig d0/d1 | amp_break | S_merkez | simetri | K3/K2")
    for cfg in cfgs:
        print(f"  {cfg}: {rep['N_sig'][cfg]['0']}/{rep['N_sig'][cfg]['1']} | "
              f"{rep['amp_break'][cfg]['amp_break']} | "
              f"{rep['S_center'][cfg]['ort']} | "
              f"{rep['simetri'].get(cfg, {}).get('minmaks', '-')} | "
              f"{rep['K2K3'].get(cfg, {}).get('oran', '-')}")
    print("OZET-KPR-ANALIZ: budget yazildi")


if __name__ == "__main__":
    main()
