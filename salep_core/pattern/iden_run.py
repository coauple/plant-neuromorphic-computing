"""IDEN matrisi — IDEN_SPEC.md §2. Tek kosu (kilit).

12 slot x amp{0.5,1,2,4} + 2 rekabet. Kazanan analzörde (raporlama).
Manifest kilidi analizorde assert'lenir. RNG yok.
"""
import csv
import hashlib
import json
import os

import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)
import iden as I

OUT = os.path.join(ENC, "p0_out")
AMPS = (0.5, 1.0, 2.0, 4.0)


def train_sched(phi_a, phi_b_list, amp):
    sa = (phi_a // 30) % 12
    sched = {}
    for k in range(I.N_PULSE):
        sched.setdefault(I.T0 + k * I.ISI, []).append((0, sa, amp))
        for phi_b in phi_b_list:
            sb = (phi_b // 30) % 12
            sched.setdefault(I.T0 + 5 + k * I.ISI, []).append((1, sb, amp))
    return sched


def main():
    conds = []
    for slot in range(12):
        for amp in AMPS:
            conds.append({"phi_b": slot * 30, "amp": amp, "mode": "single"})
    for pair in ((60, 240), (60, 90)):
        conds.append({"phi_b": pair, "amp": 1.0, "mode": "duel"})
    manifest = {"amps": list(AMPS), "inh": I.INH, "feed": I.FEED,
                "train": {"n_pulse": I.N_PULSE, "isi": I.ISI,
                          "t0": I.T0, "horizon": I.HORIZON},
                "tick_order": I.IdenUnit.PARAMS["tick_order"],
                "conds": [(c["phi_b"], c["amp"], c["mode"]) for c in conds]}
    mh = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    with open(os.path.join(OUT, "iden_manifest.json"), "w") as f:
        json.dump({"sha256": mh, "manifest": manifest}, f, indent=1)
    print(f"iden_manifest: {mh} ({len(conds)} kosul)")

    run_rows, rid, all_ok = [], 0, True
    for c in conds:
        phis = [c["phi_b"]] if c["mode"] == "single" else list(c["phi_b"])
        sched = train_sched(120, phis, c["amp"])
        r1 = I.IdenUnit().run(sched)
        r2 = I.IdenUnit().run(dict(sched))
        same = r1 == r2
        all_ok = all_ok and same
        state = ";".join(",".join(map(str, v)) if v else "-" for v in r1)
        run_rows.append(
            (rid, c["mode"], c["phi_b"] if isinstance(c["phi_b"], int)
             else "+".join(map(str, c["phi_b"])), c["amp"],
             sum(len(v) for v in r1), state, int(same)))
        rid += 1
    with open(os.path.join(OUT, "iden_runs.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(("rid", "mode", "phi_b", "amp", "n_fires", "fire_state",
                    "repeat_ok"))
        w.writerows(run_rows)
    print(f"kosu: {rid}, determinizm: {'OK' if all_ok else 'BATTI'}")
    if not all_ok:
        raise SystemExit("G1 BATTI")
    print("OZET-IDEN-RUN: OK")


if __name__ == "__main__":
    main()
