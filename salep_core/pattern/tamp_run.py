"""T-AMP matrisi — T_AMP_SPEC.md §4. Tek kosu (kilit).

Prototip basina 26 kosul x2 tekrar. Manifest prototip parametrelerini
kaydeder; analizor esitligi assert'ler.
"""
import csv
import hashlib
import json
import os

import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)
from tamp_common import k_schedule
import tamp_a as A
import tamp_b as B

OUT = os.path.join(ENC, "p0_out")


def conditions():
    conds = []
    for dt in (5, 10, 30):
        for phi_b in (60, 240):
            conds.append(("CORE", {"phi_a": 120, "phi_b": phi_b, "dt": dt,
                                   "order": "AB", "amp": 1.0}))
    for dt in (5, 10, 30):
        for phi_b in (60, 240):
            conds.append(("ORD", {"phi_a": 120, "phi_b": phi_b, "dt": dt,
                                  "order": "BA", "amp": 1.0}))
    for slot in range(12):
        conds.append(("SCALE", {"phi_a": 120, "phi_b": slot * 30, "dt": 10,
                                "order": "AB", "amp": 1.0}))
    for amp in (1.0, 1.25):
        conds.append(("AMPCTL", {"phi_a": 120, "phi_b": 60, "dt": 10,
                                 "order": "AB", "amp": amp}))
    return conds


def run_proto(proto, sched):
    if proto == "A":
        return A.PrototypeA().run(sched)
    return B.PrototypeB().run(sched)


def main():
    L = B.relay_check()
    print(f"role onkosulu OK, L={L} (kilitli ongorü: varis farki 42)")
    conds = conditions()
    manifest = {"conds": conds, "relay_L": L,
                "A_PARAMS": A.PrototypeA.PARAMS,
                "B_PARAMS": B.PrototypeB.PARAMS,
                "train": {"n_pulse": 5, "isi": 12, "t0": 50,
                          "horizon": 200}}
    mh = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    with open(os.path.join(OUT, "tamp_manifest.json"), "w") as f:
        json.dump({"sha256": mh, "manifest": manifest}, f, indent=1)
    print(f"tamp_manifest: {mh}")

    run_rows, rid, all_ok = [], 0, True
    for proto in ("A", "B"):
        for exp, p in conds:
            sched = k_schedule(p["phi_a"], p["phi_b"], p["dt"],
                               p["order"], p["amp"])
            r1 = run_proto(proto, sched)
            r2 = run_proto(proto, dict(sched))
            same = (json.dumps(r1, sort_keys=True, default=str)
                    == json.dumps(r2, sort_keys=True, default=str))
            all_ok = all_ok and same
            if proto == "A":
                state = (";".join(
                    ",".join(map(str, v)) if v else "-" for v in r1["fire"]))
                mx = max(max(v) for v in r1["soma_tr"])
                arr = "-;-"
            else:
                state = ",".join(map(str, r1["fire"])) or "-"
                mx = r1["max_soma"]
                arr = ";".join(
                    str(min(r1["chain_out"][d]) if r1["chain_out"][d]
                        else -1) for d in (0, 1))
            run_rows.append(
                (rid, proto, exp, p["phi_a"], p["phi_b"], p["dt"],
                 p["order"], p["amp"], r1["n_in"], r1["n_fires"], state,
                 f"{mx:.9f}", f"{r1.get('max_eff', -9.0):.9f}" if proto == "B"
                 else "-", arr, int(same)))
            rid += 1
    with open(os.path.join(OUT, "tamp_runs.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(("rid", "proto", "exp", "phi_a", "phi_b", "dt", "order",
                    "amp", "n_in", "n_fires", "fire_state", "max_soma",
                    "max_eff", "arrAB", "repeat_ok"))
        w.writerows(run_rows)
    # Tam izler: A 12 readout, B P3 (ayri dosyalar, %.9f)
    with open(os.path.join(OUT, "tamp_traces_a.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(("rid", "t") + tuple(f"ro{i}" for i in range(12)))
        rid = 0
        for exp, p in conds:
            sched = k_schedule(p["phi_a"], p["phi_b"], p["dt"],
                               p["order"], p["amp"])
            r = A.PrototypeA().run(sched)
            for t in range(len(r["soma_tr"][0])):
                w.writerow((rid, t) + tuple(f"{r['soma_tr'][i][t]:.9f}"
                                            for i in range(12)))
            rid += 1
    with open(os.path.join(OUT, "tamp_traces_b.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(("rid", "t", "soma", "eff_g"))
        rid = len(conds)
        for exp, p in conds:
            sched = k_schedule(p["phi_a"], p["phi_b"], p["dt"],
                               p["order"], p["amp"])
            r = B.PrototypeB().run(sched)
            for t in range(len(r["soma_tr"])):
                w.writerow((rid, t, f"{r['soma_tr'][t]:.9f}",
                            f"{r['eff_tr'][t]:.9f}"))
            rid += 1
    print(f"kosu: {rid}, determinizm: {'OK' if all_ok else 'BATTI'}")
    if not all_ok:
        raise SystemExit("G1 BATTI")
    print("OZET-TAMP-RUN: OK")


if __name__ == "__main__":
    main()
