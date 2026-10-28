"""P0b matrisi — P0B_SPEC.md §3. Tren surusu (5 darbe, ISI=12, amp=1.0).

pl_core.py ikizini kullanir (degistirmez); tren zamanlamasi burada.
Tek kosu kuralı (SPEC §4): parametreler P0B_SPEC'ten alinir, analizor
manifest-esitligini assert'ler. RNG yok.
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

# Pre-registered tren (P0B_SPEC.md §1) — burasi SPEC ile ayni olmali.
N_PULSE = 5
ISI = 12
AMP = 1.0
W_RING = 0.2
T0 = 50
HORIZON = 200
DT_GRID = (1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50, 60)


def run_train(mode, tau, phi_a, phi_b, dt, order="AB", w_ring=W_RING,
              single=None):
    assert phi_a % 30 == 0 and phi_b % 30 == 0
    u = C.PatternUnit(mode, tau)
    sa, sb = (phi_a // 30) % 12, (phi_b // 30) % 12
    ta = T0 if order == "AB" else T0 + dt
    tb = T0 + dt if order == "AB" else T0
    sched = {}
    if single in (None, "B"):
        for k in range(N_PULSE):
            sched.setdefault(ta + k * ISI, []).append((0, sa))
    if single in (None, "A"):
        for k in range(N_PULSE):
            sched.setdefault(tb + k * ISI, []).append((1, sb))
    soma_tr, eff_tr, fire_ticks, n_coinc, k_n = [], [], [], 0, 0
    max_eff = 0.0
    for t in range(HORIZON):
        for (dal, slot) in sched.get(t, ()):
            C.inject_phase(u, dal, slot, AMP, w_ring, t)
        k_fires, fired, coinc, eff_g, soma = C.step(u, t)
        k_n += len(k_fires)
        soma_tr.append(soma)
        eff_tr.append(eff_g)
        max_eff = max(max_eff, eff_g)
        n_coinc += 1 if coinc else 0
        if fired:
            fire_ticks.append(t)
    return {"fire_ticks": fire_ticks, "n_fires": len(fire_ticks),
            "max_soma": max(soma_tr), "max_eff_g": max_eff,
            "n_coinc": n_coinc, "k_fires": k_n, "soma_tr": soma_tr,
            "eff_tr": eff_tr}


def conditions():
    conds = []
    for dt in DT_GRID:
        conds.append(("E1p", {"phi_a": 120, "phi_b": 240, "dt": dt,
                              "order": "AB"}))
    for order in ("AB", "BA"):
        for dt in (5, 10, 30):
            conds.append(("E2p", {"phi_a": 120, "phi_b": 240, "dt": dt,
                                  "order": order}))
    for slot in range(12):
        conds.append(("E3p", {"phi_a": 120, "phi_b": slot * 30, "dt": 5,
                              "order": "AB"}))
    for phi_a in (0, 120, 240):
        for k in range(12):
            conds.append(("E4p", {"phi_a": phi_a,
                                  "phi_b": (phi_a + k * 30) % 360,
                                  "dt": 5, "order": "AB", "dphi": k * 30}))
    for dphi in (30, 90, 180):
        for wr in (0.0, 0.2, 0.4, 0.6):
            conds.append(("E5p", {"phi_a": 120,
                                  "phi_b": (120 + dphi) % 360, "dt": 5,
                                  "order": "AB", "dphi": dphi,
                                  "w_ring": wr}))
    for single in ("A", "B"):
        conds.append(("E6p", {"phi_a": 120, "phi_b": 240, "dt": 5,
                              "order": "AB", "single": single}))
    return conds


def main():
    conds = conditions()
    manifest = {"conds": conds, "train": {"n_pulse": N_PULSE, "isi": ISI,
                                          "amp": AMP, "t0": T0,
                                          "horizon": HORIZON},
                "w_ring": W_RING, "tau_grid": list(C.TAU_GRID)}
    mh = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    with open(os.path.join(OUT, "p0b_manifest.json"), "w") as f:
        json.dump({"sha256": mh, "manifest": manifest}, f, indent=1)
    print(f"p0b_manifest: {mh} ({len(conds)} kosul)")

    run_rows, trace_rows, rid, all_ok = [], [], 0, True
    for exp, p in conds:
        jobs = [("ring", 0), ("resonant", 4)]
        if exp == "E1p":
            jobs += [("resonant", t) for t in C.TAU_GRID if t != 4]
        for (mode, tau) in jobs:
            kw = dict(mode=mode, tau=tau, phi_a=p["phi_a"],
                      phi_b=p["phi_b"], dt=p["dt"],
                      order=p.get("order", "AB"),
                      w_ring=p.get("w_ring", W_RING),
                      single=p.get("single"))
            r1 = run_train(**kw)
            r2 = run_train(**kw)
            same = (r1["soma_tr"] == r2["soma_tr"]
                    and r1["fire_ticks"] == r2["fire_ticks"])
            all_ok = all_ok and same
            run_rows.append(
                (rid, exp, mode, tau, p.get("phi_a"), p.get("phi_b"),
                 p.get("dphi", (p.get("phi_b", 0) - p.get("phi_a", 0)) % 360),
                 p.get("dt"), p.get("order", "AB"),
                 p.get("w_ring", W_RING), p.get("single", "-"),
                 r1["n_fires"], ";".join(map(str, r1["fire_ticks"])),
                 f"{r1['max_soma']:.9f}", f"{r1['max_eff_g']:.9f}",
                 r1["n_coinc"], r1["k_fires"], int(same)))
            for t in range(len(r1["soma_tr"])):
                trace_rows.append(
                    (rid, t, f"{r1['soma_tr'][t]:.9f}",
                     f"{r1['eff_tr'][t]:.9f}"))
            rid += 1
    with open(os.path.join(OUT, "p0b_runs.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(("rid", "exp", "mode", "tau", "phi_a", "phi_b", "dphi",
                    "dt", "order", "w_ring", "single", "n_fires",
                    "fire_ticks", "max_soma", "max_eff_g", "n_coinc",
                    "k_fires", "repeat_ok"))
        w.writerows(run_rows)
    with open(os.path.join(OUT, "p0b_traces.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(("rid", "t", "soma", "eff_g"))
        w.writerows(trace_rows)
    print(f"kosu: {rid}, determinizm: {'OK' if all_ok else 'BATTI'}")
    if not all_ok:
        raise SystemExit("G1 BATTI")
    print("OZET-P0B-RUN: OK")


if __name__ == "__main__":
    main()
