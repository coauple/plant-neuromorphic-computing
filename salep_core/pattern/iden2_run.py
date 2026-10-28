"""IDEN2 matrisi — IDEN2_SPEC.md §1. Tek kosu (kilit). 24 kosul x2."""
import csv
import hashlib
import json
import os

import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)
import iden2 as D

OUT = os.path.join(ENC, "p0_out")
INHS = (0.0, 1.0)
AMODES = ("AB", "Bonly")
PHIS = (60, 90, 150)
AMPS = (1.0, 4.0)


def sched(phi_b, amp, amode):
    sa = 4
    sb = (phi_b // 30) % 12
    s = {}
    for k in range(D.N_PULSE):
        if amode == "AB":
            s.setdefault(D.T0 + k * D.ISI, []).append((0, sa, amp))
        s.setdefault(D.T0 + 5 + k * D.ISI, []).append((1, sb, amp))
    return s


def main():
    conds = [(inh, am, ph, a) for inh in INHS for am in AMODES
             for ph in PHIS for a in AMPS]
    manifest = {"inhs": list(INHS), "amodes": list(AMODES),
                "phis": list(PHIS), "amps": list(AMPS),
                "train": {"n_pulse": D.N_PULSE, "isi": D.ISI,
                          "t0": D.T0, "horizon": D.HORIZON}}
    mh = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    with open(os.path.join(OUT, "iden2_manifest.json"), "w") as f:
        json.dump({"sha256": mh, "manifest": manifest}, f, indent=1)
    print(f"iden2_manifest: {mh} ({len(conds)} kosul)")

    run_rows, rid, all_ok = [], 0, True
    for (inh, am, ph, a) in conds:
        sc = sched(ph, a, am)
        r1 = D.Iden2Unit(inh).run(sc)
        r2 = D.Iden2Unit(inh).run(dict(sc))
        same = r1 == r2
        all_ok = all_ok and same
        state = ";".join(",".join(map(str, v)) if v else "-" for v in r1)
        run_rows.append((rid, inh, am, ph, a, sum(len(v) for v in r1),
                        state, int(same)))
        rid += 1
    with open(os.path.join(OUT, "iden2_runs.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(("rid", "inh", "amode", "phi_b", "amp", "n_fires",
                    "fire_state", "repeat_ok"))
        w.writerows(run_rows)
    print(f"kosu: {rid}, determinizm: {'OK' if all_ok else 'BATTI'}")
    if not all_ok:
        raise SystemExit("G1 BATTI")
    print("OZET-IDEN2-RUN: OK")


if __name__ == "__main__":
    main()
