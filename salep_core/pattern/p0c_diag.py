"""P0c tanisi — P0C_SPEC.md §1/§2. Kilitli karar kurallari.

pl_core.py'yi import eder, degistirmez. Cikti: p0c_traces.csv,
p0c_diag.json + hukum. RNG yok. sim/encoder/web bagi YOK.
"""
import csv
import json
import os

import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)
import pl_core as C

OUT = os.path.join(ENC, "p0_out")
N_PULSE, ISI, AMP, W_RING, T0, HORIZON = 5, 12, 1.0, 0.2, 50, 200


def instrumented_run(phi_b):
    u = C.PatternUnit("ring", 0)
    sa, sb = 4, (phi_b // 30) % 12
    sched = {}
    for k in range(N_PULSE):
        sched.setdefault(T0 + k * ISI, []).append((0, sa))
        sched.setdefault(T0 + 5 + k * ISI, []).append((1, sb))
    ticks = []
    for t in range(HORIZON):
        for (dal, slot) in sched.get(t, ()):
            C.inject_phase(u, dal, slot, AMP, W_RING, t)
        kf, fired, coinc, eff_g, soma = C.step(u, t)
        k1a = "".join("1" if any(d == 0 and n == "k1" and s == i
                                 for (d, n, s) in kf) else "0"
                      for i in range(12))
        k1b = "".join("1" if any(d == 1 and n == "k1" and s == i
                                 for (d, n, s) in kf) else "0"
                      for i in range(12))
        ticks.append({
            "t": t, "k1a": k1a, "k1b": k1b,
            "k2": "".join("1" if any(d == dd and n == "k2"
                                     for (d, n, _) in kf) else "0"
                          for dd in (0, 1)),
            "k3": "".join("1" if any(d == dd and n == "k3"
                                     for (d, n, _) in kf) else "0"
                          for dd in (0, 1)),
            "inA": tuple(sorted(s for (d, n, s) in kf if d == 0)),
            "inB": tuple(sorted(s for (d, n, s) in kf if d == 1)),
            "V": tuple(u.p3.V), "g0": u.p3.g[0], "soma": soma,
            "coinc": coinc, "fired": fired,
            "slotV": tuple(u.k1[1][sb].V), "slotg": u.k1[1][sb].g[1],
            "refV": tuple(u.k1[1][0].V)})
    return ticks


def first_diff(a, b, key):
    for ra, rb in zip(a, b):
        va, vb = ra[key], rb[key]
        if isinstance(va, float):
            if abs(va - vb) > 1e-9:
                return ra["t"]
        elif va != vb:
            return ra["t"]
    return None


def main():
    r60 = instrumented_run(60)
    r240 = instrumented_run(240)
    det = (instrumented_run(60)[50]["soma"]
           == r60[50]["soma"])
    stages = {}
    stages["R1_k1b_pattern"] = first_diff(r60, r240, "k1b")
    stages["R1_k1a_pattern"] = first_diff(r60, r240, "k1a")
    stages["R1_slotV_subthr"] = first_diff(r60, r240, "slotV")
    stages["R2_k2k3"] = (first_diff(r60, r240, "k2"),
                         first_diff(r60, r240, "k3"))
    # R3-ETIKET: kaynak slotu (raporluk; kanal icerigi DEGIL).
    # R3-ELEKTRIK: kanalın tasidigi (dal basina darbe sayisi) — hukum girdisi.
    stages["R3_label_inA"] = first_diff(r60, r240, "inA")
    stages["R3_label_inB"] = first_diff(r60, r240, "inB")
    elec = lambda r: (len(r["inA"]), len(r["inB"]))
    stages["R3_elec"] = next(
        (ra["t"] for ra, rb in zip(r60, r240) if elec(ra) != elec(rb)), None)
    stages["R4_soma"] = first_diff(r60, r240, "soma")
    stages["R4_V"] = first_diff(r60, r240, "V")
    stages["R1_refV"] = first_diff(r60, r240, "refV")

    k1_diff = stages["R1_k1b_pattern"] is not None
    r3_diff = stages["R3_elec"] is not None
    r4_diff = stages["R4_soma"] is not None
    sub_diff = stages["R1_slotV_subthr"] is not None
    ref_same = stages["R1_refV"] is None
    if k1_diff and not r3_diff and not sub_diff and ref_same:
        verdict = ("KAYIP-PROJEKSIYONDA (alt-tip: index-only identity — "
                   "kimlik yalniz HANGI noronda, elektriksel buyuklukte degil)")
    elif k1_diff and not r3_diff:
        verdict = "KAYIP-PROJEKSIYONDA"
    elif r3_diff and not r4_diff:
        verdict = "KAYIP-P3-ENTEGRASYONUNDA"
    elif not k1_diff and not sub_diff:
        verdict = "HIC-ISLENMEDI"
    elif not k1_diff and sub_diff:
        verdict = "ESIKALTI-VAR-SPIKE-YOK (spike-projeksiyon kaybi alt-tipi)"
    else:
        verdict = "KISMİ (R3 farkli, R4 kismen — iz incelenir)"

    with open(os.path.join(OUT, "p0c_traces.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(("phi", "t", "k1a", "k1b", "k2", "k3", "inA", "inB",
                    "V0", "V1", "V2", "g0", "soma", "coinc", "fired"))
        for phi, runs in ((60, r60), (240, r240)):
            for r in runs:
                w.writerow((phi, r["t"], r["k1a"], r["k1b"], r["k2"],
                            r["k3"], "+".join(map(str, r["inA"])) or "-",
                            "+".join(map(str, r["inB"])) or "-",
                            f"{r['V'][0]:.9f}", f"{r['V'][1]:.9f}",
                            f"{r['V'][2]:.9f}", f"{r['g0']:.9f}",
                            f"{r['soma']:.9f}", int(r["coinc"]),
                            int(r["fired"])))
    with open(os.path.join(OUT, "p0c_diag.json"), "w") as f:
        json.dump({"determinism_ok": bool(det), "stages": stages,
                   "verdict": verdict}, f, indent=1, sort_keys=True,
                  default=str)
    print(f"determinizm: {'OK' if det else 'BATTI'}")
    for k, v in stages.items():
        print(f"  ilk-fark {k}: {v}")
    print(f"HUKUM: {verdict}")
    if not det:
        raise SystemExit("determinizm BATTI")
    print("OZET-P0C-DIAG: OK")


if __name__ == "__main__":
    main()
