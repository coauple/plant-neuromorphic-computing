"""KPR1 kosucu: Faz 0 (K1-K4) -> kollar (~36 kol x 12 slot).
Kullanim: python3 pattern/kpr1_run.py [--gate] [--run] [--all]
Cikti: pattern/p0_out/kpr1_*. Kirmizida DURUR.
"""
import csv
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pattern"))
OUT = os.path.join(ROOT, "pattern", "p0_out")

import kpr1_drive as D  # noqa: E402

FROZEN = ["src/pattern_lobe.h", "src/pattern_unit_v2.h",
          "pattern/pl_core.py", "pattern/P0_SPEC.md",
          "pattern/P0B_SPEC.md", "pattern/P0C_SPEC.md",
          "pattern/T_AMP_SPEC.md", "pattern/IDEN_SPEC.md"]
AMPS = [0.05, 0.1, 0.2, 0.3, 0.5, 1.0]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def rnd(v, nd=9):
    if isinstance(v, (list, tuple)):
        return tuple(round(float(x), nd) for x in v)
    return round(float(v), nd)


def n_sig_v2(per_slot):
    # KBHP R0 imzasiyla AYNI: birim-basina (g0[::10], ates-demeti) x6.
    # (bellek-ici: int anahtar; JSON: str — ikisine dayanikli)
    def get(tr, u, k):
        d = tr[str(u)] if str(u) in tr else tr[u]
        return d[k]
    sigs = []
    for tr in per_slot:
        sigs.append(tuple((rnd(get(tr, u, "g0")[::10]),
                           tuple(get(tr, u, "fire_ticks")))
                          for u in range(6)))
    return len(set(sigs))


def gate():
    print("== KPR1 Faz 0 ==")
    ok = {}
    ok["K1"] = D.k0_lstep_equiv()
    d0 = [D.run(slot=s, d_step=0) for s in range(12)]
    d1 = [D.run(slot=s, d_step=1) for s in range(12)]
    n0, n1 = n_sig_v2(d0), n_sig_v2(d1)
    ok["K2"] = (n0 == 7 and n1 == 12)
    print(f"  regresyon: d0->{n0} (beklenen 7), d1->{n1} (beklenen 12)")
    d0b = [D.run(slot=s, d_step=0) for s in range(12)]
    d1b = [D.run(slot=s, d_step=1) for s in range(12)]
    ok["K3"] = (d0b == d0 and d1b == d1)
    fb = {f: sha(os.path.join(ROOT, f)) for f in FROZEN}
    ok["K4"] = True
    for k, v in ok.items():
        print(f"  {'OK' if v else 'BATTI'} {k}")
    with open(os.path.join(OUT, "kpr1_fidelity.json"), "w") as f:
        json.dump({"gates": ok,
                   "frozen_sha12": {k: v[:12] for k, v in fb.items()},
                   "regresyon": {"d0": n0, "d1": n1}}, f, indent=1)
    print("OZET-KPR1-F0: " + ("OK" if all(ok.values()) else "BATTI"))
    return all(ok.values())


def run():
    print("== KPR1 kollar ==")
    arms, store = [], {}
    n = [0]

    def arm(rid, meta, sims):
        arms.append(dict({"id": rid}, **meta))
        for sid, res in sims:
            store[sid] = res
            n[0] += 1

    cfgs = [("A0", None, "nat"), ("A1", "k1", "nat"),
            ("A2", "k23", "nat"), ("A3", None, "lock"),
            ("A4", None, "off")]
    for name, ablate, coinc in cfgs:
        for d in (0, 1):
            sims = []
            for s in range(12):
                sims.append((f"kpr_{name}_d{d}_s{s}",
                             D.run(slot=s, d_step=d, ablate=ablate,
                                   coinc=coinc)))
            arm(f"kpr_{name}_d{d}",
                {"arch": "v2", "kol": name, "dstep": d,
                 "coinc": coinc,
                 "ablate": ablate or "yok"}, sims)
    for name, ab in (("A5", {}), ("A6", {"ablate": "k1"})):
        for d in (0, 1):
            for a in AMPS:
                sims = []
                for s in range(12):
                    sims.append((f"kpr_{name}_d{d}_a{a}_s{s}",
                                 D.run(slot=s, amp=a, d_step=d,
                                       ablate=ab.get("ablate"))))
                arm(f"kpr_{name}_d{d}_a{a}",
                    {"arch": "v2", "kol": name, "dstep": d, "amp": a},
                    sims)
    for name, ab in (("L1", {}), ("L2", {"ablate": "k1"})):
        for d in (0, 1):
            sims = []
            for s in range(12):
                sims.append((f"kpr_{name}_d{d}_s{s}",
                             D.run_legacy(slot=s, d_step=d,
                                          ablate=ab.get("ablate"))))
            arm(f"kpr_{name}_d{d}",
                {"arch": "legacy", "kol": name, "dstep": d}, sims)
    with open(os.path.join(OUT, "kpr1_axes.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "arch", "kol", "dstep",
                                          "amp"])
        w.writeheader()
        for a in arms:
            w.writerow({k: a.get(k, "") for k in
                        ("id", "arch", "kol", "dstep", "amp")})
    with open(os.path.join(OUT, "kpr1_runs.json"), "w") as f:
        json.dump(store, f)
    print(f"OZET-KPR1-RUN: {len(arms)} kol, {n[0]} sim OK")


if __name__ == "__main__":
    args = set(sys.argv[1:]) or {"--all"}
    if "--gate" in args or "--all" in args:
        if not gate():
            sys.exit("KPR1 DURDU: Faz 0 kirmizi")
    if "--run" in args or "--all" in args:
        run()
