"""UNF egitimi — UNF_SPEC.md §1. UPL rejimi aynen, 60 tur.

Cikti: unf_weights.json (+ tur-basi P3 atesleri). ABORT: P3 h event.
upl.py degismez (import).
"""
import csv
import hashlib
import json
import os

import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)
import upl as U
from upl_run import sched_of, run_fresh

OUT = os.path.join(ENC, "p0_out")
CYCLES, GAP = 60, 30


def main():
    inst = json.load(open(os.path.join(OUT, "upu_instances.json")))
    pair = tuple(inst["pair"])
    eps = [(pair[0], pair[1], e)
           for b in inst["bins"] for e in inst["episodes"][str(b)]]
    if inst["ipair"]:
        eps += [(inst["ipair"][0], inst["ipair"][1], e)
                for e in inst["ipair_episodes"]]
    manifest = {"params": U.UplUnit.PARAMS, "cycles": CYCLES, "gap": GAP,
                "episodes": [(x, y, e["dt"], e["t0"]) for (x, y, e) in eps]}
    mh = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    with open(os.path.join(OUT, "unf_manifest.json"), "w") as f:
        json.dump({"sha256": mh, "manifest": manifest}, f, indent=1)
    print(f"unf_manifest: {mh}")

    wlog, trainlog, abort = {}, {}, []
    for (x, y, e) in eps:
        key = f"{x}+{y}@dt{e['dt']}"
        span = max(e["x"] + e["y"]) + GAP
        u = U.UplUnit()
        cyc, t = [], 0
        for _ in range(CYCLES):
            r = run_fresh(u, x, y, e["x"], e["y"], True, t0=t, span=span)
            cyc.append(r["n"])
            t += span
        w1 = u.weights()
        flat = [w for row in w1["wk1"] for w in row] + w1["wk2"] + w1[
            "wk3"] + w1["wp3"]
        wlog[key] = {"w_end": w1, "w_max": max(flat)}
        trainlog[key] = cyc
        if not any(c > 0 for c in cyc):
            abort.append(key)
    with open(os.path.join(OUT, "unf_weights.json"), "w") as f:
        json.dump(wlog, f, indent=1)
    print(f"egitim atesleri: {json.dumps(trainlog, sort_keys=True)}")
    print(f"w_max: {json.dumps({k: round(v['w_max'], 4) for k, v in wlog.items()}, sort_keys=True)}")
    assert not abort, f"ABORT (P3 egitimde ateslemedi): {abort}"
    print("ABORT kontrolu OK (P3 atesledi)")
    print("OZET-UNF-TRAIN: OK")


if __name__ == "__main__":
    main()
