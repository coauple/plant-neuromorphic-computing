"""UPL kosusu — UPL_SPEC.md §2. Tek kosu (kilit).

Episode basina: sifir birim -> 20 tur surekli maruziyet -> dondur ->
sifir-durum olcum. Cikti: upl_runs.csv + upl_weights.json.
"""
import csv
import hashlib
import json
import os

import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)
import upl as U

OUT = os.path.join(ENC, "p0_out")
CYCLES, GAP = 20, 30


def sched_of(x_slot, y_slot, x_tr, y_tr, base):
    s = {}
    for dt_ in x_tr:
        s.setdefault(base + dt_, []).append((0, x_slot, 1.0))
    for dt_ in y_tr:
        s.setdefault(base + dt_, []).append((1, y_slot, 1.0))
    return s


def run_fresh(unit, x_slot, y_slot, x_tr, y_tr, learn, t0=0, span=300,
              rec_k1=False):
    sc = sched_of(x_slot, y_slot, x_tr, y_tr, t0)
    fires, mx_soma, mx_eff, n_co = [], 0.0, 0.0, 0
    k1a, k1b = set(), set()
    for t in range(t0, t0 + span):
        kf, f3, coinc, eff_g, soma = unit.tick(t, sc.get(t, ()))
        mx_soma = max(mx_soma, soma)
        mx_eff = max(mx_eff, eff_g)
        n_co += 1 if coinc else 0
        if f3:
            fires.append(t - t0)
        if rec_k1:
            for u in kf:
                d = unit._dal_of(u)
                for dal in (0, 1):
                    for s in range(12):
                        if u is unit.k1[dal][s]:
                            (k1a if dal == 0 else k1b).add(s)
    return {"fires": fires, "n": len(fires), "max_soma": mx_soma,
            "max_eff": mx_eff, "n_co": n_co, "k1a": sorted(k1a),
            "k1b": sorted(k1b)}


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
    with open(os.path.join(OUT, "upl_manifest.json"), "w") as f:
        json.dump({"sha256": mh, "manifest": manifest}, f, indent=1)
    print(f"upl_manifest: {mh} ({len(eps)} episode)")

    run_rows, wlog = [], {}
    for (x, y, e) in eps:
        key = f"{x}+{y}@dt{e['dt']}"
        u = U.UplUnit()
        span = max(e["x"] + e["y"]) + GAP
        cyc_fires = []
        t = 0
        for _ in range(CYCLES):
            r = run_fresh(u, x, y, e["x"], e["y"], True, t0=t, span=span)
            cyc_fires.append(r["n"])
            t += span
        w1 = u.weights()
        m = U.UplUnit()
        m.set_weights(w1)
        post = run_fresh(m, x, y, e["x"], e["y"], False, span=span,
                         rec_k1=True)
        flat = [w for row in w1["wk1"] for w in row] + w1["wk2"] + w1[
            "wk3"] + w1["wp3"]
        wlog[key] = {"w_end": w1, "w_min": min(flat), "w_max": max(flat),
                     "wp3": w1["wp3"], "cyc_fires": cyc_fires}
        run_rows.append(
            (key, x, y, e["dt"], ";".join(map(str, cyc_fires)),
             post["n"], ";".join(map(str, post["fires"])) or "-",
             f"{post['max_soma']:.9f}", f"{post['max_eff']:.9f}",
             post["n_co"], "+".join(map(str, post["k1a"])),
             "+".join(map(str, post["k1b"]))))
    with open(os.path.join(OUT, "upl_runs.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(("key", "X", "Y", "dt", "cyc_fires", "post_n",
                    "post_fires", "post_max_soma", "post_max_eff",
                    "post_nco", "k1a_slots", "k1b_slots"))
        w.writerows(run_rows)
    with open(os.path.join(OUT, "upl_weights.json"), "w") as f:
        json.dump(wlog, f, indent=1)
    print(f"kosu: {len(run_rows)} episode")
    print("OZET-UPL-RUN: OK")


if __name__ == "__main__":
    main()
