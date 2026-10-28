"""UN kosusu — UN_SPEC.md §2/§3. Sadakat kapisi + tek test kosusu.

Once k=0 sadakat (US tablosuyla bit-esitlik assert'i), sonra k=0.5.
"""
import csv
import hashlib
import json
import os

import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)
import un as N

OUT = os.path.join(ENC, "p0_out")
CONDS = (("K1", {"K1"}), ("K2", {"K2"}), ("K3", {"K3"}),
          ("JOINT", {"K1", "K2", "K3"}))


def episodes():
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


def run_all(k, r):
    rows = []
    for (key, sc, w) in episodes():
        for (cn, allow) in CONDS:
            u = N.UnUnit(w, k, r)
            fires, rmin = u.run(dict(sc), allow)
            rows.append((key, cn, len(fires),
                         ";".join(map(str, fires)) or "-",
                         f"{rmin[1]:.6f}", f"{rmin[2]:.6f}"))
    return rows


def main():
    manifest = {"conds": [c[0] for c in CONDS],
                "dal_map": N.UnUnit.PARAMS["dal_map"],
                "k": N.K_RES, "r": N.R_REC, "weights": "upl_weights.json",
                "episodes": [[5, 6, 0], [5, 6, 17], [4, 5, 9]]}
    mh = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    with open(os.path.join(OUT, "un_manifest.json"), "w") as f:
        json.dump({"sha256": mh, "manifest": manifest}, f, indent=1)
    print(f"un_manifest: {mh}")

    # Sadakat kapisi: k=0, us2 (tek-surus) tablosuyla bit-esit olmali
    with open(os.path.join(OUT, "us2_runs.csv")) as f:
        us = {(r["key"], r["cond"]): r["n"]
              for r in csv.DictReader(f)}
    fid = run_all(0.0, N.R_REC)
    bad = [(k, c, n) for (k, c, n, _, _, _) in fid
           if us[(k, c)] != str(n)]
    assert not bad, f"SADAKAT BATTI: {bad}"
    print(f"sadakat kapisi OK ({len(fid)} hucre bit-esit)")

    test = run_all(N.K_RES, N.R_REC)
    with open(os.path.join(OUT, "un_runs.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(("key", "cond", "n", "fires", "rminA", "rminB"))
        w.writerows(test)
    print(f"test kosusu: {len(test)} hucre")
    print("OZET-UN-RUN: OK")


if __name__ == "__main__":
    main()
