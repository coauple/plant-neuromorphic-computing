"""IDEN3 matrisi — IDEN3_SPEC.md §1. Tek kosu (kilit). 8 dt x2."""
import csv
import hashlib
import json
import os

import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)
import iden3 as D

OUT = os.path.join(ENC, "p0_out")
DTS = (0, 2, 5, 8, 10, 15, 20, 30)


def sched(dt):
    s = {}
    for k in range(D.N_PULSE):
        s.setdefault(D.T0 + k * D.ISI, []).append((0, 4, 4.0))
        s.setdefault(D.T0 + dt + k * D.ISI, []).append((1, 3, 4.0))
    return s


def energy(sc):
    return (sum(1 for v in sc.values() for _ in v),
            round(sum(a for v in sc.values() for (_, _, a) in v), 6))


def main():
    manifest = {"dts": list(DTS), "phi_a": 120, "phi_b": 90, "amp": 4.0,
                "inh": D.INH,
                "train": {"n_pulse": D.N_PULSE, "isi": D.ISI,
                          "t0": D.T0, "horizon": D.HORIZON}}
    mh = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    with open(os.path.join(OUT, "iden3_manifest.json"), "w") as f:
        json.dump({"sha256": mh, "manifest": manifest}, f, indent=1)
    print(f"iden3_manifest: {mh}")

    run_rows, all_ok = [], True
    for dt in DTS:
        sc = sched(dt)
        e1 = energy(sc)
        f1, c1, i1 = D.run_sched(sc)
        f2, c2, i2 = D.run_sched(dict(sc))
        same = f1 == f2 and c1 == c2 and i1 == i2
        all_ok = all_ok and same
        run_rows.append(
            (dt, e1[0], e1[1],
             ";".join(",".join(map(str, v)) if v else "-" for v in f1),
             ";".join(map(str, c1)),
             ";".join(f"{a}/{b}" for (a, b) in i1), int(same)))
    with open(os.path.join(OUT, "iden3_runs.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(("dt", "n_pulses", "energy", "fire_state", "coinc",
                    "ro_in", "repeat_ok"))
        w.writerows(run_rows)
    print(f"kosu: {len(run_rows)}, determinizm: {'OK' if all_ok else 'BATTI'}")
    if not all_ok:
        raise SystemExit("G1 BATTI")
    print("OZET-IDEN3-RUN: OK")


if __name__ == "__main__":
    main()
