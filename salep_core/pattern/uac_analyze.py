"""UAC analizi — UAC_SPEC.md §2. Kosudan ONCE yazildi (kilit).

Manifest kilidi + SELECTIVE/NON-SELECTIVE + profil. stdlib-only.
"""
import ast
import csv
import json
import os
from collections import Counter

import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)

OUT = os.path.join(ENC, "p0_out")
LOCK = {"cycles": 20, "gap": 30, "win": 30,
        "params": {"eta": 0.3, "w_max": 2.0, "win": 30, "w0": 1.0}}


def main():
    man = json.load(open(os.path.join(OUT, "uac_manifest.json")))["manifest"]
    assert man["cycles"] == LOCK["cycles"] and man["gap"] == LOCK["gap"] \
        and man["win"] == LOCK["win"], "KILIT"
    assert man["params"] == LOCK["params"], f"KILIT: {man['params']}"
    print("manifest kilidi OK")

    with open(os.path.join(OUT, "uac_runs.csv")) as f:
        rows = list(csv.DictReader(f))
    prof = Counter()
    detail = {}
    for r in rows:
        cell = []
        if r["spikes"] != "-":
            for tok in r["spikes"].split(";"):
                _, cls = tok.split(":")
                s = frozenset(cls.split("/") if cls else ())
                prof[s] += 1
                cell.append(s)
        detail[r["key"]] = ["+".join(sorted(s)) if s else "bos"
                            for s in cell]
    joint = sum(n for s, n in prof.items()
                if {"K1", "K2", "K3"} <= set(s))
    solo_k3 = sum(n for s, n in prof.items() if set(s) == {"K3"})
    total = sum(prof.values())
    m = {"profile": {"+".join(sorted(s)) if s else "bos": n for s, n in
                      sorted(prof.items())},
         "n_total": total, "n_joint": joint, "n_solo_k3": solo_k3,
         "HUKUM": ("SELECTIVE" if joint > 0 and solo_k3 == 0
                   else "NON-SELECTIVE")}
    with open(os.path.join(OUT, "uac_metrics.json"), "w") as f:
        json.dump(m, f, indent=1, sort_keys=True, default=str)
    print(f"toplam P3 spike: {total}; JOINT: {joint}; solo-K3: {solo_k3}")
    print(f"profil: {m['profile']}")
    print(f"HUKUM: {m['HUKUM']}")

    bad = []
    for nm in ("uac_run.py", "uac_analyze.py"):
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
    print("OZET-UAC-ANALYZE: OK")


if __name__ == "__main__":
    main()
