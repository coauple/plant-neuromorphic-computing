"""UAC kosusu — UAC_SPEC.md §1. Tek kosu (kilit).

Episode basina sifir UplUnit, 20 tur surekli + ogrenme; her P3
spike'i 30-tick K-konfigurasyonuyla kaydedilir.
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
CYCLES, GAP, WIN = 20, 30, 30


def main():
    inst = json.load(open(os.path.join(OUT, "upu_instances.json")))
    pair = tuple(inst["pair"])
    eps = [(pair[0], pair[1], e)
           for b in inst["bins"] for e in inst["episodes"][str(b)]]
    if inst["ipair"]:
        eps += [(inst["ipair"][0], inst["ipair"][1], e)
                for e in inst["ipair_episodes"]]
    manifest = {"params": U.UplUnit.PARAMS, "cycles": CYCLES,
                "gap": GAP, "win": WIN,
                "episodes": [(x, y, e["dt"], e["t0"]) for (x, y, e) in eps]}
    mh = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    with open(os.path.join(OUT, "uac_manifest.json"), "w") as f:
        json.dump({"sha256": mh, "manifest": manifest}, f, indent=1)
    print(f"uac_manifest: {mh} ({len(eps)} episode)")

    run_rows = []
    for (x, y, e) in eps:
        key = f"{x}+{y}@dt{e['dt']}"
        span = max(e["x"] + e["y"]) + GAP
        u = U.UplUnit()
        spikes = []  # (tick, frozenset(siniflar))
        hist = []
        t = 0
        for _ in range(CYCLES):
            sc = {}
            for dt_ in e["x"]:
                sc.setdefault(t + dt_, []).append((0, x, 1.0))
            for dt_ in e["y"]:
                sc.setdefault(t + dt_, []).append((1, y, 1.0))
            for dt_ in range(span):
                kf, f3, _, _, _ = u.tick(t + dt_, sc.get(t + dt_, ()))
                cls = set()
                for unit in kf:
                    d = u._dal_of(unit)
                    if unit in [u.k1[d][s] for s in range(12)]:
                        cls.add("K1")
                    elif unit is u.k2[d]:
                        cls.add("K2")
                    elif unit is u.k3[d]:
                        cls.add("K3")
                hist.append((t + dt_, cls))
                if f3:
                    win_cls = set()
                    for (ht, hc) in hist:
                        if t + dt_ - WIN <= ht <= t + dt_:
                            win_cls |= hc
                    spikes.append((t + dt_, sorted(win_cls)))
            t += span
        run_rows.append((key, len(spikes),
                         ";".join(f"{tt}:{'/'.join(c)}" for (tt, c) in
                                  spikes) or "-"))
    with open(os.path.join(OUT, "uac_runs.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(("key", "n_spikes", "spikes"))
        w.writerows(run_rows)
    print(f"kosu: {len(run_rows)} episode")
    print("OZET-UAC-RUN: OK")


if __name__ == "__main__":
    main()
