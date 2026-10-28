"""US2 analizi — US ile ayni hukum (SELECTIVE-JOINT iff 0,0,0,>0).

Kosudan ONCE yazildi. Bu dosya dal-eslemeli entegrasyonun
duzeltilmis bekcisidir. Manifest kilidi + HUKUM. stdlib-only.
"""
import ast
import csv
import json
import os

import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)

OUT = os.path.join(ENC, "p0_out")
LOCK = {"rerun_of": "US", "mode": "us",
        "dal_map": {"A": "K3", "B": ["K1", "K2"]},
        "conds": ["K1", "K2", "K3", "JOINT"],
        "episodes": [[5, 6, 0], [5, 6, 17], [4, 5, 9]],
        "weights": "upl_weights.json"}


def main():
    man = json.load(open(os.path.join(OUT, "us2_manifest.json")))["manifest"]
    for k, v in LOCK.items():
        assert man[k] == v, f"KILIT IHLALI {k}: {man[k]}"
    print("manifest kilidi OK")

    with open(os.path.join(OUT, "us2_runs.csv")) as f:
        rows = list(csv.DictReader(f))
    tab = {}
    for r in rows:
        tab[(r["key"], r["cond"])] = int(r["n"])
    keys = sorted(set(k for (k, _) in tab))
    ok = True
    for k in keys:
        solo = all(tab[(k, c)] == 0 for c in ("K1", "K2", "K3"))
        joint = tab[(k, "JOINT")] > 0
        print(f"  {k}: K1={tab[(k, 'K1')]} K2={tab[(k, 'K2')]} "
              f"K3={tab[(k, 'K3')]} JOINT={tab[(k, 'JOINT')]} "
              f"-> {'OK' if solo and joint else 'FAIL'}")
        ok = ok and solo and joint
    verdict = ("SELECTIVE-JOINT" if ok else "NON-SELECTIVE")
    with open(os.path.join(OUT, "us2_metrics.json"), "w") as f:
        json.dump({"table": {f"{k}/{c}": tab[(k, c)] for (k, c) in
                             sorted(tab)},
                   "HUKUM": verdict}, f, indent=1, sort_keys=True)
    print(f"HUKUM: {verdict}")

    bad = []
    for nm in ("ux.py", "us2_run.py", "us2_analyze.py"):
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
    print("OZET-US2-ANALYZE: OK")


if __name__ == "__main__":
    main()
