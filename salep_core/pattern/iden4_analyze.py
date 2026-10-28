"""IDEN4 analizi — IDEN4_SPEC.md §2/§3. Kosudan ONCE yazildi (kilit).

Manifest kilidi + M1/M2'/M3/M4/M5 + HUKUM. stdlib-only.
"""
import ast
import csv
import json
import os

import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)

OUT = os.path.join(ENC, "p0_out")
LOCK = {"slots": 12, "amps": [1.0, 2.0, 4.0], "onsets": [50, 70],
        "inhs": [0.0, 1.0],
        "train": {"n_pulse": 5, "isi": 12, "horizon": 200}}


def winner(fire_state):
    cols = [tuple(map(int, p.split(","))) if p != "-" else ()
            for p in fire_state.split(";")]
    scored = [(len(c), -(c[0] if c else 10 ** 9), -i) for i, c in
              enumerate(cols)]
    best = max(range(12), key=lambda i: scored[i])
    return best if cols[best] else None


def main():
    man = json.load(open(os.path.join(OUT, "iden4_manifest.json")))["manifest"]
    for k, v in LOCK.items():
        assert man[k] == v, f"KILIT IHLALI {k}: {man[k]}"
    print("manifest kilidi OK")

    with open(os.path.join(OUT, "iden4_runs.csv")) as f:
        rows = list(csv.DictReader(f))
    m = {}
    m["M1"] = all(r["repeat_ok"] == "1" for r in rows)

    def get(phi_b, amp, onset, inh):
        out = [r for r in rows if int(r["phi_b"]) == phi_b
               and float(r["amp"]) == amp and int(r["onset"]) == onset
               and float(r["inh"]) == inh]
        assert len(out) == 1
        return winner(out[0]["fire_state"])

    # M2': phi basina 6 hucrede ayni kazanan mi?
    m["M2p"] = {}
    for slot in range(12):
        ws = [get(slot * 30, a, o, i) for a in (1.0, 2.0, 4.0)
              for o in (50, 70) for i in (0.0, 1.0)]
        m["M2p"][slot * 30] = {"winners": ws, "stable": len(set(ws)) == 1,
                               "driven": all(w == slot for w in ws
                                             if w is not None)}
    # M4: hucre bazinda kapsama (amp,onset,inh) = 12 hucre
    m["M4"] = {}
    for a in (1.0, 2.0, 4.0):
        for o in (50, 70):
            for i in (0.0, 1.0):
                ws = [get(slot * 30, a, o, i) for slot in range(12)]
                live = [w for w in ws if w is not None]
                m["M4"][f"{a}@{o}/INH{i}"] = {
                    "coverage": f"{len(set(live))}/12",
                    "full": len(set(live)) == 12 and all(
                        w == s for s, w in enumerate(ws))}
    # M5: WTA etkisi (OFF vs ON, hucre eslesmesi)
    m["M5"] = {}
    for a in (1.0, 2.0, 4.0):
        for o in (50, 70):
            same = all(get(slot * 30, a, o, 0.0) == get(slot * 30, a, o, 1.0)
                       for slot in range(12))
            m["M5"][f"{a}@{o}"] = same

    stable_all = all(v["stable"] and v["driven"]
                     for v in m["M2p"].values())
    cover_all = all(v["full"] for v in m["M4"].values())
    if stable_all and cover_all:
        verdict = "KORUR"
    elif any(v["stable"] for v in m["M2p"].values()):
        verdict = "KISMEN"
    else:
        verdict = "KORUMAZ"
    m["HUKUM"] = verdict

    bad = []
    for nm in ("iden4_run.py", "iden4_analyze.py"):
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

    with open(os.path.join(OUT, "iden4_metrics.json"), "w") as f:
        json.dump(m, f, indent=1, sort_keys=True, default=str)
    print(f"M1: {'OK' if m['M1'] else 'BATTI'}")
    print(f"M2': {json.dumps(m['M2p'], sort_keys=True)}")
    print(f"M4: {json.dumps(m['M4'], sort_keys=True)}")
    print(f"M5 WTA-etkisi: {json.dumps(m['M5'], sort_keys=True)}")
    print(f"HUKUM: {verdict} "
          f"({'IDEN5 kapisi ACILDI' if verdict == 'KORUR' else 'IDEN5 YOK'})")
    if bad:
        raise SystemExit(f"SIFIR-BAG IHLALI: {bad}")
    print(f"OZET-IDEN4-ANALYZE: {verdict}")
    if not m["M1"]:
        raise SystemExit("G1 BATTI")


if __name__ == "__main__":
    main()
