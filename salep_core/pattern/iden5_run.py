"""IDEN5 matrisi — IDEN5_SPEC.md §1. Tek kosu (kilit). 24 x2."""
import csv
import hashlib
import json
import os

import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)
import iden5 as D

OUT = os.path.join(ENC, "p0_out")
PHIS = (60, 150, 240)
AMPS = (1.0, 4.0)
ONSETS = (50, 70)
CONFS = (False, True)


def sched(phi_b, amp, onset):
    sb = (phi_b // 30) % 12
    return {onset + k * D.ISI: [(1, sb, amp)] for k in range(D.N_PULSE)}


def main():
    conds = [(p, a, o, c) for p in PHIS for a in AMPS for o in ONSETS
             for c in CONFS]
    manifest = {"phis": list(PHIS), "amps": list(AMPS),
                "onsets": list(ONSETS), "confs": ["K1", "K1+K2"],
                "train": {"n_pulse": D.N_PULSE, "isi": D.ISI,
                          "horizon": D.HORIZON}}
    mh = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    with open(os.path.join(OUT, "iden5_manifest.json"), "w") as f:
        json.dump({"sha256": mh, "manifest": manifest}, f, indent=1)
    print(f"iden5_manifest: {mh} ({len(conds)} kosul)")

    run_rows, rid, all_ok = [], 0, True
    for (p, a, o, c) in conds:
        sc = sched(p, a, o)
        r1 = D.Iden5Unit(c).run(sc)
        r2 = D.Iden5Unit(c).run(dict(sc))
        same = r1 == r2
        all_ok = all_ok and same
        state = ";".join(",".join(map(str, v)) if v else "-" for v in r1)
        run_rows.append((rid, p, a, o, "K1+K2" if c else "K1",
                        sum(len(v) for v in r1), state, int(same)))
        rid += 1
    with open(os.path.join(OUT, "iden5_runs.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(("rid", "phi_b", "amp", "onset", "conf", "n_fires",
                    "fire_state", "repeat_ok"))
        w.writerows(run_rows)
    print(f"kosu: {rid}, determinizm: {'OK' if all_ok else 'BATTI'}")
    if not all_ok:
        raise SystemExit("G1 BATTI")
    print("OZET-IDEN5-RUN: OK")


if __name__ == "__main__":
    main()
