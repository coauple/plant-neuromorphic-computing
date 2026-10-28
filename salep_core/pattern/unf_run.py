"""UNF testi — UNF_SPEC.md §1. Sadakat + 4-kosul.

Sadakat: k=0, ayni agirliklarla yalın-P3 tek-surus (ux, us-modu)
ile bit-esit. Test: k=0.5. un.UnUnit aynen.
"""
import csv
import hashlib
import json
import os

import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)
import un as N
from ux import run_cell

OUT = os.path.join(ENC, "p0_out")
CONDS = (("K1", {"K1"}), ("K2", {"K2"}), ("K3", {"K3"}),
          ("JOINT", {"K1", "K2", "K3"}))


def episodes():
    inst = json.load(open(os.path.join(OUT, "upu_instances.json")))
    wlog = json.load(open(os.path.join(OUT, "unf_weights.json")))
    pair = tuple(inst["pair"])
    eps = [(pair[0], pair[1], e)
           for b in inst["bins"] for e in inst["episodes"][str(b)]]
    if inst["ipair"]:
        eps += [(inst["ipair"][0], inst["ipair"][1], e)
                for e in inst["ipair_episodes"]]
    wkeys = {(5, 6, 0): "5+6@dt0", (5, 6, 17): "5+6@dt17",
             (4, 5, 9): "4+5@dt9"}
    out = []
    for (x, y, e) in eps:
        sc = {}
        for dt_ in e["x"]:
            sc.setdefault(dt_, []).append((0, x, 1.0))
        for dt_ in e["y"]:
            sc.setdefault(dt_, []).append((1, y, 1.0))
        out.append((f"{x}+{y}@dt{e['dt']}", sc,
                    wlog[wkeys[(x, y, e["dt"])]]["w_end"]))
    return out


def main():
    manifest = {"conds": [c[0] for c in CONDS],
                "dal_map": N.UnUnit.PARAMS["dal_map"],
                "k": N.K_RES, "r": N.R_REC, "weights": "unf_weights.json",
                "train_cycles": 60}
    mh = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    with open(os.path.join(OUT, "unf_test_manifest.json"), "w") as f:
        json.dump({"sha256": mh, "manifest": manifest}, f, indent=1)
    print(f"unf_test_manifest: {mh}")

    # Sadakat: k=0 <-> yalın-P3 tek-surus (yeni agirliklarla)
    bad = []
    for (key, sc, w) in episodes():
        for (cn, allow) in CONDS:
            a = N.UnUnit(w, 0.0, N.R_REC)
            fa, _ = a.run(dict(sc), allow)
            fb = run_cell(w, dict(sc), allow, "us", False)
            if fa != fb:
                bad.append((key, cn, fa, fb))
    assert not bad, f"SADAKAT BATTI: {bad}"
    print("sadakat kapisi OK (yalın-P3 ile bit-esit)")

    run_rows = []
    for (key, sc, w) in episodes():
        for (cn, allow) in CONDS:
            u = N.UnUnit(w, N.K_RES, N.R_REC)
            fires, rmin = u.run(dict(sc), allow)
            run_rows.append((key, cn, len(fires),
                            ";".join(map(str, fires)) or "-",
                            f"{rmin[1]:.6f}", f"{rmin[2]:.6f}"))
    with open(os.path.join(OUT, "unf_runs.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(("key", "cond", "n", "fires", "rminA", "rminB"))
        w.writerows(run_rows)
    print(f"test kosusu: {len(run_rows)} hucre")
    print("OZET-UNF-RUN: OK")


if __name__ == "__main__":
    main()
