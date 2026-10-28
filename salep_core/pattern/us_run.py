"""US matrisi — US_SPEC.md §2. Tek kosu (kilit). 3 episode x 4 kosul."""
import csv
import hashlib
import json
import os

import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)
import us as S

OUT = os.path.join(ENC, "p0_out")
CONDS = (("K1", {"K1"}), ("K2", {"K2"}), ("K3", {"K3"}),
          ("JOINT", {"K1", "K2", "K3"}))


def main():
    inst = json.load(open(os.path.join(OUT, "upu_instances.json")))
    wlog = json.load(open(os.path.join(OUT, "upl_weights.json")))
    pair = tuple(inst["pair"])
    eps = [(pair[0], pair[1], e)
           for b in inst["bins"] for e in inst["episodes"][str(b)]]
    if inst["ipair"]:
        eps += [(inst["ipair"][0], inst["ipair"][1], e)
                for e in inst["ipair_episodes"]]
    wkeys = {(5, 6, 0): "5+6@dt0", (5, 6, 17): "5+6@dt17",
             (4, 5, 9): "4+5@dt9"}
    manifest = {"conds": [c[0] for c in CONDS],
                "dal_map": S.UsUnit.PARAMS["dal_map"],
                "episodes": [(x, y, e["dt"]) for (x, y, e) in eps],
                "weights": "upl_weights.json"}
    mh = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    with open(os.path.join(OUT, "us_manifest.json"), "w") as f:
        json.dump({"sha256": mh, "manifest": manifest}, f, indent=1)
    print(f"us_manifest: {mh}")

    run_rows = []
    for (x, y, e) in eps:
        sc = {}
        for dt_ in e["x"]:
            sc.setdefault(dt_, []).append((0, x, 1.0))
        for dt_ in e["y"]:
            sc.setdefault(dt_, []).append((1, y, 1.0))
        w = wlog[wkeys[(x, y, e["dt"])]]["w_end"]
        for (cn, allow) in CONDS:
            u = S.UsUnit(w)
            fires = u.run(dict(sc), allow)
            run_rows.append((f"{x}+{y}@dt{e['dt']}", cn, len(fires),
                            ";".join(map(str, fires)) or "-"))
    with open(os.path.join(OUT, "us_runs.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(("key", "cond", "n", "fires"))
        w.writerows(run_rows)
    print(f"kosu: {len(run_rows)}")
    print("OZET-US-RUN: OK")


if __name__ == "__main__":
    main()
