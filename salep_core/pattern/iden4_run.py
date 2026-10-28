"""IDEN4 matrisi — IDEN4_SPEC.md §1. Tek kosu (kilit).

Mekanizma iden2.Iden2Unit (B-only sched; degisiklik yok).
144 kosul x2 tekrar.
"""
import csv
import hashlib
import json
import os

import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)
from iden2 import Iden2Unit, N_PULSE, ISI, HORIZON

OUT = os.path.join(ENC, "p0_out")
AMPS = (1.0, 2.0, 4.0)
ONSETS = (50, 70)
INHS = (0.0, 1.0)


def sched(phi_b, amp, onset):
    sb = (phi_b // 30) % 12
    return {onset + k * ISI: [(1, sb, amp)] for k in range(N_PULSE)}


def main():
    conds = [(s, a, o, i) for s in range(12) for a in AMPS
             for o in ONSETS for i in INHS]
    manifest = {"slots": 12, "amps": list(AMPS), "onsets": list(ONSETS),
                "inhs": list(INHS),
                "train": {"n_pulse": N_PULSE, "isi": ISI,
                          "horizon": HORIZON}}
    mh = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    with open(os.path.join(OUT, "iden4_manifest.json"), "w") as f:
        json.dump({"sha256": mh, "manifest": manifest}, f, indent=1)
    print(f"iden4_manifest: {mh} ({len(conds)} kosul)")

    run_rows, rid, all_ok = [], 0, True
    for (s, a, o, i) in conds:
        sc = sched(s * 30, a, o)
        r1 = Iden2Unit(i).run(sc)
        r2 = Iden2Unit(i).run(dict(sc))
        same = r1 == r2
        all_ok = all_ok and same
        state = ";".join(",".join(map(str, v)) if v else "-" for v in r1)
        run_rows.append((rid, s * 30, a, o, i, sum(len(v) for v in r1),
                        state, int(same)))
        rid += 1
    with open(os.path.join(OUT, "iden4_runs.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(("rid", "phi_b", "amp", "onset", "inh", "n_fires",
                    "fire_state", "repeat_ok"))
        w.writerows(run_rows)
    print(f"kosu: {rid}, determinizm: {'OK' if all_ok else 'BATTI'}")
    if not all_ok:
        raise SystemExit("G1 BATTI")
    print("OZET-IDEN4-RUN: OK")


if __name__ == "__main__":
    main()
