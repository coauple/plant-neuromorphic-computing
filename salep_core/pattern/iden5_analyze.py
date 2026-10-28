"""IDEN5 analizi — IDEN5_SPEC.md §2. Kosudan ONCE yazildi (kilit).

Manifest kilidi + determinizm + HUKUM (BOZMUYOR/BOZUYOR).
stdlib-only.
"""
import ast
import csv
import json
import os

import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)

OUT = os.path.join(ENC, "p0_out")
LOCK = {"phis": [60, 150, 240], "amps": [1.0, 4.0], "onsets": [50, 70],
        "confs": ["K1", "K1+K2"],
        "train": {"n_pulse": 5, "isi": 12, "horizon": 200}}


def winner(fire_state):
    cols = [tuple(map(int, p.split(","))) if p != "-" else ()
            for p in fire_state.split(";")]
    scored = [(len(c), -(c[0] if c else 10 ** 9), -i) for i, c in
              enumerate(cols)]
    best = max(range(12), key=lambda i: scored[i])
    return best if cols[best] else None


def main():
    man = json.load(open(os.path.join(OUT, "iden5_manifest.json")))["manifest"]
    for k, v in LOCK.items():
        assert man[k] == v, f"KILIT IHLALI {k}: {man[k]}"
    print("manifest kilidi OK")

    with open(os.path.join(OUT, "iden5_runs.csv")) as f:
        rows = list(csv.DictReader(f))
    m1 = all(r["repeat_ok"] == "1" for r in rows)

    def get(phi_b, amp, onset, conf):
        out = [r for r in rows if int(r["phi_b"]) == phi_b
               and float(r["amp"]) == amp and int(r["onset"]) == onset
               and r["conf"] == conf]
        assert len(out) == 1
        return winner(out[0]["fire_state"])

    tab = {}
    for p in (60, 150, 240):
        for a in (1.0, 4.0):
            for o in (50, 70):
                w1 = get(p, a, o, "K1")
                w2 = get(p, a, o, "K1+K2")
                tab[(p, a, o)] = {"K1": w1, "K1+K2": w2,
                                  "driven": p // 30,
                                  "ok": w1 == p // 30 and w2 == p // 30
                                  and w1 == w2}
    m = {"cells": {f"{k[0]}@{k[1]}/{k[2]}": v for k, v in
                   sorted(tab.items())},
         "HUKUM": ("BOZMUYOR" if all(v["ok"] for v in tab.values())
                   else "BOZUYOR")}

    bad = []
    for nm in ("iden5.py", "iden5_run.py", "iden5_analyze.py"):
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
    m["zero_link"] = bad

    with open(os.path.join(OUT, "iden5_metrics.json"), "w") as f:
        json.dump(m, f, indent=1, sort_keys=True, default=str)
    print(f"M1: {'OK' if m1 else 'BATTI'}")
    print(f"hucreler: {json.dumps(m['cells'], sort_keys=True)}")
    print(f"HUKUM: {m['HUKUM']}")
    if bad:
        raise SystemExit(f"SIFIR-BAG IHLALI: {bad}")
    print(f"OZET-IDEN5-ANALYZE: {m['HUKUM']}")
    if not m1:
        raise SystemExit("G1 BATTI")


if __name__ == "__main__":
    main()
