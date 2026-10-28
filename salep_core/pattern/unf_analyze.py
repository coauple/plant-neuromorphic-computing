"""UNF analizi — UNF_SPEC.md §2. Kosudan ONCE yazildi (kilit).

Manifest kilidi + HUKUM (SELECTIVE-JOINT / NON-SELECTIVE) + R-min.
Bu dosya atesleyen-rejim doyum-testinin bekcisidir. stdlib-only.
"""
import ast
import csv
import json
import os

import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)

OUT = os.path.join(ENC, "p0_out")
LOCK = {"conds": ["K1", "K2", "K3", "JOINT"],
        "dal_map": {"A": "K3", "B": ["K1", "K2"]},
        "k": 0.5, "r": 0.05, "weights": "unf_weights.json",
        "train_cycles": 60}


def main():
    man = json.load(open(os.path.join(OUT, "unf_test_manifest.json")))["manifest"]
    for k, v in LOCK.items():
        assert man[k] == v, f"KILIT IHLALI {k}: {man[k]}"
    print("manifest kilidi OK")

    with open(os.path.join(OUT, "unf_runs.csv")) as f:
        rows = list(csv.DictReader(f))
    tab = {}
    for r in rows:
        tab[(r["key"], r["cond"])] = (int(r["n"]),
                                      round(float(r["rminA"]), 3),
                                      round(float(r["rminB"]), 3))
    keys = sorted(set(k for (k, _) in tab))
    ok = True
    for k in keys:
        solo = all(tab[(k, c)][0] == 0 for c in ("K1", "K2", "K3"))
        joint = tab[(k, "JOINT")][0] > 0
        print(f"  {k}: K1={tab[(k, 'K1')][0]} K2={tab[(k, 'K2')][0]} "
              f"K3={tab[(k, 'K3')][0]} JOINT={tab[(k, 'JOINT')][0]} "
              f"rmin={tab[(k, 'JOINT')][1:]} "
              f"-> {'OK' if solo and joint else 'FAIL'}")
        ok = ok and solo and joint
    verdict = ("SELECTIVE-JOINT" if ok else "NON-SELECTIVE")
    with open(os.path.join(OUT, "unf_metrics.json"), "w") as f:
        json.dump({"table": {f"{k}/{c}": tab[(k, c)][0] for (k, c) in
                             sorted(tab)},
                   "rmin_joint": {k: tab[(k, "JOINT")][1:] for k in keys},
                   "HUKUM": verdict}, f, indent=1, sort_keys=True)
    print(f"HUKUM: {verdict}")

    bad = []
    for nm in ("unf_train.py", "unf_run.py", "unf_analyze.py"):
        tree = ast.parse(open(os.path.join(ENC, nm)).read())
        for n in ast.walk(tree):
            mods = []
            if isinstance(n, ast.Import):
                mods = [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom) and n.module:
                mods = [n.module]
            for mod in mods:
                if mod.split(".")[0] in ("sim", "encoder", "web"):
                    bad.append((nm, mod))
    if bad:
        raise SystemExit(f"SIFIR-BAG IHLALI: {bad}")
    print("OZET-UNF-ANALYZE: OK")


if __name__ == "__main__":
    main()
