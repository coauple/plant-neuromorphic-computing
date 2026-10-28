"""IDEN analizi — IDEN_SPEC.md §3/§4. Kosudan ONCE yazildi (kilit).

1. Manifest kilidi (amp seti, INH, tren, tick-sirasi).
2. Kazanan (RAPORLAMA kurali, mekanizma degil): en cok spike;
   esitlikte en erken ilk-spike; onda da dusuk indeks. None acik sonuc.
3. M1..M6 + HUKUM (KORUR/KISMEN/KORUMAZ). stdlib-only.
"""
import ast
import csv
import json
import os

import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)

OUT = os.path.join(ENC, "p0_out")
LOCK = {"amps": [0.5, 1.0, 2.0, 4.0], "inh": 1.0, "feed": 1.0,
        "train": {"n_pulse": 5, "isi": 12, "t0": 50, "horizon": 200},
        "tick_order": "0..11"}


def winner(fire_state):
    # fire_state: 12 readout'un tick listeleri (string ayristirilir).
    cols = [tuple(map(int, p.split(","))) if p != "-" else ()
            for p in fire_state.split(";")]
    scored = [(len(c), -(c[0] if c else 10 ** 9), -i) for i, c in
              enumerate(cols)]
    best = max(range(12), key=lambda i: scored[i])
    if not cols[best]:
        return None
    return best


def main():
    man = json.load(open(os.path.join(OUT, "iden_manifest.json")))["manifest"]
    for k, v in LOCK.items():
        assert man[k] == v, f"KILIT IHLALI {k}: {man[k]}"
    print("manifest kilidi OK")

    with open(os.path.join(OUT, "iden_runs.csv")) as f:
        rows = list(csv.DictReader(f))
    m = {}
    m["M1"] = all(r["repeat_ok"] == "1" for r in rows)

    singles = [r for r in rows if r["mode"] == "single"]
    win = {}
    for r in singles:
        win[(int(r["phi_b"]), float(r["amp"]))] = winner(r["fire_state"])
    m["winners"] = {f"{k[0]}@{k[1]}": v for k, v in sorted(win.items())}

    # M2 koruma: phi basina 4 amp'ta ayni kazanan (None dahil ayni olmali)
    m["M2"] = {}
    for slot in range(12):
        ws = [win[(slot * 30, a)] for a in (0.5, 1.0, 2.0, 4.0)]
        m["M2"][slot * 30] = {"winners": ws, "stable": len(set(ws)) == 1}
    # M3 ayrışma + M4 kapsama (amp=1.0 referans + tum amp'lar)
    m["M3_M4"] = {}
    for a in (0.5, 1.0, 2.0, 4.0):
        ws = [win[(slot * 30, a)] for slot in range(12)]
        live = [w for w in ws if w is not None]
        m["M3_M4"][a] = {"winners": ws,
                         "coverage": f"{len(set(live))}/12",
                         "all_distinct": len(set(live)) == 12}
    duels = {}
    for r in rows:
        if r["mode"] == "duel":
            duels[r["phi_b"]] = winner(r["fire_state"])
    m["duels"] = duels

    stable_all = all(v["stable"] for v in m["M2"].values())
    cover_all = all(m["M3_M4"][a]["all_distinct"]
                    for a in (0.5, 1.0, 2.0, 4.0))
    cover_ref = m["M3_M4"][1.0]["all_distinct"]
    if stable_all and cover_all:
        verdict = "KORUR"
    elif stable_all or cover_ref:
        verdict = "KISMEN"
    else:
        verdict = "KORUMAZ"
    m["HUKUM"] = verdict

    bad = []
    for nm in ("iden.py", "iden_run.py", "iden_analyze.py"):
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

    with open(os.path.join(OUT, "iden_metrics.json"), "w") as f:
        json.dump(m, f, indent=1, sort_keys=True, default=str)
    print(f"M1: {'OK' if m['M1'] else 'BATTI'}")
    print(f"M2 koruma: {json.dumps(m['M2'], sort_keys=True)}")
    print(f"M3/M4: {json.dumps(m['M3_M4'], sort_keys=True)}")
    print(f"duello: {duels}")
    print(f"HUKUM: {verdict}")
    if bad:
        raise SystemExit(f"SIFIR-BAG IHLALI: {bad}")
    print(f"OZET-IDEN-ANALYZE: {verdict}")
    if not m["M1"]:
        raise SystemExit("G1 BATTI")


if __name__ == "__main__":
    main()
