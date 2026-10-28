"""UPU analizi — UPU_SPEC.md §3. Kosudan ONCE yazildi (kilit).

Manifest-hash kilidi + kilitli mesafe + hukum. n=1/bin ise yayilim
tabani YOKTUR: hukum "INCE (mesafe olculdu, taban-yok)" olur, PASS
verilmez. stdlib-only.
"""
import ast
import csv
import hashlib
import json
import os

import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)

OUT = os.path.join(ENC, "p0_out")


def sig(r):
    fs = set() if r["fire_ticks"] == "-" else set(
        map(int, r["fire_ticks"].split(";")))
    return (fs, int(r["n_fires"]), round(float(r["max_soma"]), 6),
            round(float(r["max_eff"]), 6))


def dist(a, b):
    sa, sb = sig(a), sig(b)
    return ((0 if sa[0] == sb[0] else 1) + abs(sa[1] - sb[1]) / 10.0
            + abs(sa[2] - sb[2]) + abs(sa[3] - sb[3]))


def main():
    man = json.load(open(os.path.join(OUT, "upu_manifest.json")))
    inst = json.load(open(os.path.join(OUT, "upu_instances.json")))
    assert man["instances"] == inst, "KILIT: instances degismis"
    assert (hashlib.sha256(
        json.dumps(inst, sort_keys=True).encode()).hexdigest()
            == man["sha256"]), "KILIT: hash tutmadi"
    print("manifest kilidi OK")

    with open(os.path.join(OUT, "upu_runs.csv")) as f:
        rows = list(csv.DictReader(f))
    main_rows = [r for r in rows if r["tag"] == "main"]
    ident_rows = [r for r in rows if r["tag"] == "ident"]
    bins = inst["bins"]
    bybin = {b: [r for r in main_rows if int(r["dt"]) == b] for b in bins}
    m = {"bins": bins, "n_per_bin": {str(b): len(bybin[b]) for b in bins},
         "sigs": {}}
    for r in rows:
        m["sigs"][r["rid"]] = {
            "tag": r["tag"], "X": r["X"], "Y": r["Y"], "dt": r["dt"],
            "n_fires": r["n_fires"], "fire_ticks": r["fire_ticks"],
            "max_soma": round(float(r["max_soma"]), 6)}

    thin = any(len(bybin[b]) < 2 for b in bins)
    cross = None
    if len(bins) == 2 and all(len(bybin[b]) >= 1 for b in bins):
        cross = dist(bybin[bins[0]][0], bybin[bins[1]][0])
    m["cross_dt_distance"] = round(cross, 6) if cross is not None else None
    icross = None
    if ident_rows and main_rows:
        icross = min(dist(a, b) for a in main_rows for b in ident_rows)
    m["cross_pair_distance"] = (round(icross, 6)
                                if icross is not None else None)
    if thin:
        verdict = ("INCE (n=1/bin: mesafe olculdu, yayilim-tabani yok; "
                   "PASS verilmez)")
    else:
        verdict = "KRITER-DISI (beklenmeyen orneklem)"
    m["HUKUM"] = verdict

    with open(os.path.join(OUT, "upu_metrics.json"), "w") as f:
        json.dump(m, f, indent=1, sort_keys=True, default=str)
    print(f"binler: {bins}, orneklem: {m['n_per_bin']}")
    print(f"imzalar: {json.dumps(m['sigs'], sort_keys=True)}")
    print(f"capraz-Dt mesafe: {m['cross_dt_distance']}, "
          f"capraz-cift: {m['cross_pair_distance']}")
    print(f"HUKUM: {verdict}")

    bad = []
    for nm in ("upu_mine.py", "upu_run.py", "upu_analyze.py"):
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
    print("OZET-UPU-ANALYZE: OK")


if __name__ == "__main__":
    main()
