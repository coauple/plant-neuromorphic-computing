"""UPL analizi — UPL_SPEC.md §3. Kosudan ONCE yazildi (kilit).

Manifest kilidi + UYANIYOR/SESSIZ + kimlik-hukmu + sessizlik-atfi.
Bu dosya ogrenme-davranisinin kalici bekcisidir. stdlib-only.
"""
import ast
import csv
import json
import os

import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)

OUT = os.path.join(ENC, "p0_out")
LOCK_PARAMS = {"eta": 0.3, "w_max": 2.0, "win": 30, "w0": 1.0}
LOCK_CYCLES, LOCK_GAP = 20, 30


def dist(a, b):
    fa = set() if a["post_fires"] == "-" else set(
        map(int, a["post_fires"].split(";")))
    fb = set() if b["post_fires"] == "-" else set(
        map(int, b["post_fires"].split(";")))
    return ((0 if fa == fb else 1) + abs(int(a["post_n"]) - int(b["post_n"]))
            / 10.0 + abs(float(a["post_max_soma"]) - float(b["post_max_soma"]))
            + abs(float(a["post_max_eff"]) - float(b["post_max_eff"])))


def main():
    man = json.load(open(os.path.join(OUT, "upl_manifest.json")))["manifest"]
    assert man["params"] == LOCK_PARAMS, f"KILIT: {man['params']}"
    assert man["cycles"] == LOCK_CYCLES and man["gap"] == LOCK_GAP, "KILIT"
    print("manifest kilidi OK")

    with open(os.path.join(OUT, "upl_runs.csv")) as f:
        rows = list(csv.DictReader(f))
    wlog = json.load(open(os.path.join(OUT, "upl_weights.json")))
    m = {}
    for r in rows:
        key = r["key"]
        cyc = list(map(int, r["cyc_fires"].split(";")))
        m[key] = {"post_n": int(r["post_n"]),
                  "post_fires": r["post_fires"],
                  "max_soma": round(float(r["post_max_soma"]), 6),
                  "cyc_fires": cyc, "woke_in_training": any(c > 0 for c in
                                                            cyc),
                  "wp3_end": wlog[key]["wp3"],
                  "w_min": round(wlog[key]["w_min"], 6),
                  "w_max": round(wlog[key]["w_max"], 6),
                  "k1a": r["k1a_slots"], "k1b": r["k1b_slots"]}
    ep_keys = [r["key"] for r in rows]
    wakes = {k: m[k]["post_n"] > 0 for k in ep_keys}
    m["wake"] = ("UYANIYOR" if any(wakes.values()) else "SESSIZ")
    ids = {}
    keys = ep_keys
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a = next(r for r in rows if r["key"] == keys[i])
            b = next(r for r in rows if r["key"] == keys[j])
            ids[f"{keys[i]}|{keys[j]}"] = round(dist(a, b), 6)
    m["cross_distances"] = ids
    # Sessizlik atfi: girdi agirliklari oynadi mi? P3 agirliklari?
    moved_in, moved_p3 = {}, {}
    for k, v in m.items():
        if k in ("wake", "cross_distances"):
            continue
        w = wlog[k]["w_end"]
        flat_in = ([x for row in w["wk1"] for x in row] + w["wk2"]
                   + w["wk3"])
        moved_in[k] = round(max(abs(x - 1.0) for x in flat_in), 6)
        moved_p3[k] = round(max(abs(x - 1.0) for x in w["wp3"]), 6)
    m["moved_input"] = moved_in
    m["moved_p3"] = moved_p3
    if m["wake"] == "UYANIYOR":
        m["HUKUM"] = ("kimlik-korunuyor" if all(v > 0 for v in ids.values())
                      else "uyanis-var-ayrisma-yok")
    else:
        if all(v == 0 for v in moved_p3.values()):
            m["HUKUM"] = "SESSIZ (G=0 kilidi: P3 ateslemeden P3 agirligi oynamaz)"
        else:
            m["HUKUM"] = "SESSIZ (P3 agirligi oynadi ama esik asilmadi)"

    with open(os.path.join(OUT, "upl_metrics.json"), "w") as f:
        json.dump(m, f, indent=1, sort_keys=True, default=str)
    for k, v in m.items():
        if k in ("wake", "cross_distances", "HUKUM"):
            continue
        if isinstance(v, dict) and "post_n" in v:
            print(f"  {k}: post_n={v['post_n']} maxsoma={v['max_soma']} "
                  f"wp3={v['wp3_end']} k1a=[{v['k1a']}] k1b=[{v['k1b']}]")
    print(f"uyanis: {m['wake']}; capraz: {m['cross_distances']}")
    print(f"girdi-oynama: {m['moved_input']}; p3-oynama: {m['moved_p3']}")
    print(f"HUKUM: {m['HUKUM']}")

    bad = []
    for nm in ("upl.py", "upl_run.py", "upl_analyze.py"):
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
    print("OZET-UPL-ANALYZE: OK")


if __name__ == "__main__":
    main()
