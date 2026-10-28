"""IDEN2 analizi — IDEN2_SPEC.md §2. Kosudan ONCE yazildi (kilit).

Manifest kilidi + R1/R2/R3 atif kurallari. Kazanan kurali IDEN ile
ayni (raporlama). HUKUM: atif tablosu. stdlib-only.
"""
import ast
import csv
import json
import os

import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)

OUT = os.path.join(ENC, "p0_out")
LOCK = {"inhs": [0.0, 1.0], "amodes": ["AB", "Bonly"],
        "phis": [60, 90, 150], "amps": [1.0, 4.0],
        "train": {"n_pulse": 5, "isi": 12, "t0": 50, "horizon": 200}}


def winner(fire_state):
    cols = [tuple(map(int, p.split(","))) if p != "-" else ()
            for p in fire_state.split(";")]
    scored = [(len(c), -(c[0] if c else 10 ** 9), -i) for i, c in
              enumerate(cols)]
    best = max(range(12), key=lambda i: scored[i])
    return best if cols[best] else None


def main():
    man = json.load(open(os.path.join(OUT, "iden2_manifest.json")))["manifest"]
    for k, v in LOCK.items():
        assert man[k] == v, f"KILIT IHLALI {k}: {man[k]}"
    print("manifest kilidi OK")

    with open(os.path.join(OUT, "iden2_runs.csv")) as f:
        rows = list(csv.DictReader(f))
    m = {}
    m["M1"] = all(r["repeat_ok"] == "1" for r in rows)

    def get(inh, am, ph, a):
        out = [r for r in rows if float(r["inh"]) == inh and r["amode"] == am
               and int(r["phi_b"]) == ph and float(r["amp"]) == a]
        assert len(out) == 1
        return winner(out[0]["fire_state"])

    tab = {}
    for inh in (0.0, 1.0):
        for am in ("AB", "Bonly"):
            for ph in (60, 90, 150):
                for a in (1.0, 4.0):
                    tab[(inh, am, ph, a)] = get(inh, am, ph, a)
    m["winners"] = {f"INH{i}-{'AB' if am == 'AB' else 'B'}-{ph}@{a}": v
                    for (i, am, ph, a), v in sorted(tab.items())}

    # R1: WTA rolu (INH0 vs INH1 @1.0 AB)
    r1_same = all(tab[(0.0, "AB", ph, 1.0)] == tab[(1.0, "AB", ph, 1.0)]
                  for ph in (60, 90, 150))
    # R2: A-baskinligi (A-yok @4.0: kayma duzelir mi?)
    r2_fixed = all(tab[(1.0, "Bonly", ph, 4.0)] == ph // 30
                   for ph in (90, 150))
    # R3: B-yeterliligi (A-yok @1.0 eslesir mi?)
    r3_ok = all(tab[(1.0, "Bonly", ph, 1.0)] == ph // 30
                for ph in (60, 90, 150))
    m["R1_WTA_role"] = ("feedforward-secer" if r1_same
                        else "WTA-katilir")
    m["R2_A_dominance"] = ("A-treni+bonus-suclu" if r2_fixed
                           else "B-tarafi-icsel")
    m["R3_B_sufficiency"] = ("B-tek-basina-yeter" if r3_ok
                             else "bonus-gerekli")
    m["HUKUM"] = {"R1": m["R1_WTA_role"], "R2": m["R2_A_dominance"],
                  "R3": m["R3_B_sufficiency"]}

    bad = []
    for nm in ("iden2.py", "iden2_run.py", "iden2_analyze.py"):
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

    with open(os.path.join(OUT, "iden2_metrics.json"), "w") as f:
        json.dump(m, f, indent=1, sort_keys=True, default=str)
    print(f"M1: {'OK' if m['M1'] else 'BATTI'}")
    print(f"kazananlar: {json.dumps(m['winners'], sort_keys=True)}")
    print(f"HUKUM: {json.dumps(m['HUKUM'], sort_keys=True)}")
    if bad:
        raise SystemExit(f"SIFIR-BAG IHLALI: {bad}")
    print("OZET-IDEN2-ANALYZE: OK")
    if not m["M1"]:
        raise SystemExit("G1 BATTI")


if __name__ == "__main__":
    main()
