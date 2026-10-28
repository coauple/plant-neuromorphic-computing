"""UPU kosusu — UPU_SPEC.md §1. Tek kosu (kilit).

Episode trenleri (gercek goreki tick) A/B hatlarina; birim
episode-basi sifir. K1/K2/K3+P3 P0b ring aynisi (pl_core degismez).
"""
import csv
import hashlib
import json
import os

import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)
import pl_core as C

OUT = os.path.join(ENC, "p0_out")
HORIZON = 300


def run_episode(x_slot, y_slot, x_tr, y_tr):
    u = C.PatternUnit("ring", 0)
    sched = {}
    for dt_ in x_tr:
        sched.setdefault(dt_, []).append((0, x_slot))
    for dt_ in y_tr:
        sched.setdefault(dt_, []).append((1, y_slot))
    soma_tr, eff_tr, fires, n_co = [], [], [], 0
    for t in range(HORIZON):
        for (dal, slot) in sched.get(t, ()):
            C.inject_phase(u, dal, slot, 1.0, 0.2, t)
        _, fired, coinc, eff_g, soma = C.step(u, t)
        soma_tr.append(soma)
        eff_tr.append(eff_g)
        n_co += 1 if coinc else 0
        if fired:
            fires.append(t)
    return {"fires": fires, "n": len(fires), "max_soma": max(soma_tr),
            "max_eff": max(eff_tr), "n_co": n_co}


def main():
    inst = json.load(open(os.path.join(OUT, "upu_instances.json")))
    pair = tuple(inst["pair"])
    bins = inst["bins"]
    mh = hashlib.sha256(json.dumps(inst, sort_keys=True).encode()).hexdigest()
    with open(os.path.join(OUT, "upu_manifest.json"), "w") as f:
        json.dump({"sha256": mh, "instances": inst,
                   "horizon": HORIZON}, f, indent=1)
    print(f"upu_manifest: {mh}")

    run_rows = []
    rid = 0
    groups = [("main", pair[0], pair[1],
               [e for b in bins for e in inst["episodes"][str(b)]])]
    if inst["ipair"]:
        groups.append(("ident", inst["ipair"][0], inst["ipair"][1],
                       inst["ipair_episodes"]))
    for (tag, x, y, eps) in groups:
        for e in eps:
            r = run_episode(x, y, e["x"], e["y"])
            run_rows.append(
                (rid, tag, x, y, e["dt"], e["t0"], len(e["x"]), len(e["y"]),
                 r["n"], ";".join(map(str, r["fires"])) or "-",
                 f"{r['max_soma']:.9f}", f"{r['max_eff']:.9f}", r["n_co"]))
            rid += 1
    with open(os.path.join(OUT, "upu_runs.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(("rid", "tag", "X", "Y", "dt", "t0", "nx", "ny",
                    "n_fires", "fire_ticks", "max_soma", "max_eff",
                    "n_coinc"))
        w.writerows(run_rows)
    print(f"kosu: {rid}")
    print("OZET-UPU-RUN: OK")


if __name__ == "__main__":
    main()
