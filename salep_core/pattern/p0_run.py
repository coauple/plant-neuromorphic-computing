"""P0 matrisi E1..E7 — P0_SPEC.md §4. Deterministik, RNG yok.

Cikti: p0_runs.csv (imza/ozet), p0_traces.csv (P3 tick izi),
p0_manifest.json (matris+parametre SHA256). K1-b E2-E7'de tau=4
(sonuclar gorulmeden sabitlendi, SPEC §3); E1 tau izgarasi ayri
sutun (gecici mekanizma taramasi).
"""
import csv
import hashlib
import json
import os

import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)
import pl_core as C

OUT = os.path.join(ENC, "p0_out")
DT_GRID = (1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50, 60)
AMP = 1.0
W_RING = 0.2


def conditions():
    conds = []
    for dt in DT_GRID:  # E1
        conds.append(("E1", {"phi_a": 120, "phi_b": 240, "dt": dt,
                             "order": "AB"}))
    for order in ("AB", "BA"):  # E2
        for dt in (5, 10, 30):
            conds.append(("E2", {"phi_a": 120, "phi_b": 240, "dt": dt,
                                 "order": order}))
    for slot in range(12):  # E3
        conds.append(("E3", {"phi_a": 120, "phi_b": slot * 30, "dt": 5,
                             "order": "AB"}))
    for phi_a in (0, 120, 240):  # E4
        for k in range(12):
            conds.append(("E4", {"phi_a": phi_a,
                                 "phi_b": (phi_a + k * 30) % 360,
                                 "dt": 5, "order": "AB", "dphi": k * 30}))
    for dphi in (30, 90, 180):  # E5
        for wr in (0.0, 0.2, 0.4, 0.6):
            conds.append(("E5", {"phi_a": 120,
                                 "phi_b": (120 + dphi) % 360, "dt": 5,
                                 "order": "AB", "dphi": dphi,
                                 "w_ring": wr}))
    for single in ("A", "B"):  # E6
        for amp in (0.5, 1.0, 2.0):
            conds.append(("E6", {"phi_a": 120, "phi_b": 240, "dt": 5,
                                 "order": "AB", "single": single,
                                 "amp": amp}))
    return conds


def run_once(exp, p, mode, tau):
    kw = dict(mode=mode, tau=tau, phi_a_deg=p["phi_a"],
              phi_b_deg=p["phi_b"], dt=p["dt"], order=p.get("order", "AB"),
              w_ring=p.get("w_ring", W_RING), amp=p.get("amp", AMP),
              single=p.get("single"))
    return C.run_condition(**kw)


def main():
    conds = conditions()
    manifest = {"conds": conds, "tau_grid": list(C.TAU_GRID), "amp": AMP,
                "w_ring": W_RING,
                "params": {"DIFF": C.DIFF, "THR": C.THR,
                           "V_RESET": C.V_RESET, "G_ACT": C.G_ACT,
                           "G_INC": C.G_INC, "WIN": C.WIN,
                           "BONUS": C.BONUS}}
    mh = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    with open(os.path.join(OUT, "p0_manifest.json"), "w") as f:
        json.dump({"sha256": mh, "manifest": manifest}, f, indent=1)
    print(f"p0_manifest: {mh} ({len(conds)} kosul)")

    run_rows, trace_rows = [], []
    rid = 0
    all_ok = True
    for exp, p in conds:
        jobs = [("ring", 0), ("resonant", 4)]
        if exp == "E1":
            jobs += [("resonant", t) for t in C.TAU_GRID if t != 4]
        for (mode, tau) in jobs:
            r1 = run_once(exp, p, mode, tau)
            r2 = run_once(exp, p, mode, tau)  # E7 bit-esit tekrar
            same = (r1["soma_tr"] == r2["soma_tr"]
                    and r1["eff_tr"] == r2["eff_tr"]
                    and r1["fire_ticks"] == r2["fire_ticks"])
            all_ok = all_ok and same
            run_rows.append(
                (rid, exp, mode, tau, p.get("phi_a"), p.get("phi_b"),
                 p.get("dphi", (p.get("phi_b", 0) - p.get("phi_a", 0)) % 360),
                 p.get("dt"), p.get("order", "AB"),
                 p.get("w_ring", W_RING), p.get("amp", AMP),
                 p.get("single", "-"), r1["n_fires"],
                 ";".join(map(str, r1["fire_ticks"])),
                 f"{r1['max_soma']:.9f}", f"{r1['max_eff_g']:.9f}",
                 r1["n_coinc"], r1["k_fires"], int(same)))
            for t in range(len(r1["soma_tr"])):
                trace_rows.append(
                    (rid, t, f"{r1['soma_tr'][t]:.9f}",
                     f"{r1['eff_tr'][t]:.9f}"))
            rid += 1
    with open(os.path.join(OUT, "p0_runs.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(("rid", "exp", "mode", "tau", "phi_a", "phi_b", "dphi",
                    "dt", "order", "w_ring", "amp", "single", "n_fires",
                    "fire_ticks", "max_soma", "max_eff_g", "n_coinc",
                    "k_fires", "repeat_ok"))
        w.writerows(run_rows)
    with open(os.path.join(OUT, "p0_traces.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(("rid", "t", "soma", "eff_g"))
        w.writerows(trace_rows)
    print(f"kosu: {rid} (E7 tekrar dahil), determinizm: "
          f"{'OK' if all_ok else 'BATTI'}")
    if not all_ok:
        raise SystemExit("G1 BATTI")
    print("OZET-P0-RUN: OK")


if __name__ == "__main__":
    main()
