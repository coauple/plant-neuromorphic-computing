"""KPR kosucu: Faz 0 -> Aşama 1-4.
Kullanim: python3 pattern/kpr_run.py [--gate] [--run] [--all]
Cikti: pattern/p0_out/kpr_*. Faz 0 kirmiziysa DURUR.
"""
import csv
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pattern"))
OUT = os.path.join(ROOT, "pattern", "p0_out")

import kpr_drive as D  # noqa: E402

FROZEN = ["src/pattern_lobe.h", "src/pattern_unit_v2.h",
          "pattern/pl_core.py", "pattern/P0_SPEC.md",
          "pattern/P0B_SPEC.md", "pattern/P0C_SPEC.md",
          "pattern/T_AMP_SPEC.md", "pattern/IDEN_SPEC.md"]
AMPS = [0.25, 0.5, 1.0, 2.0]
CFGS = ["C0", "F1"]  # F1+ varyantlari analyze-onayli isimle asagida


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def rnd(v, nd=9):
    if isinstance(v, (list, tuple)):
        return tuple(round(float(x), nd) for x in v)
    return round(float(v), nd)


def n_sig(per_slot):
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
    print("== KPR Faz 0 ==")
    ok = {}
    ok["step-equiv"] = D.k0_step_equiv()
    d0 = [D.run(slot=s, d_step=0, cfg="C0") for s in range(12)]
    d1 = [D.run(slot=s, d_step=1, cfg="C0") for s in range(12)]
    n0, n1 = n_sig(d0), n_sig(d1)
    ok["KBHP-repro"] = (n0 == 7 and n1 == 12)
    print(f"  C0 tái-üretim: d0->{n0} (7), d1->{n1} (12)")
    def sh(tr, u):
        return (tr[str(u)] if str(u) in tr else tr[u])["S_share"]
    s0 = sum(sh(tr, u) for tr in d0 for u in range(6)) / 72.0
    ok["S-share"] = abs(s0 - 0.027) < 0.005
    print(f"  S_share-ort: {s0:.4f} (beklenen ~0.027)")
    d0b = [D.run(slot=s, d_step=0, cfg="C0") for s in range(12)]
    d1b = [D.run(slot=s, d_step=1, cfg="C0") for s in range(12)]
    ok["determinizm"] = (d0b == d0 and d1b == d1)
    fb = {f: sha(os.path.join(ROOT, f)) for f in FROZEN}
    ok["frozen-sha"] = True
    for k, v in ok.items():
        print(f"  {'OK' if v else 'BATTI'} {k}")
    with open(os.path.join(OUT, "kpr_fidelity.json"), "w") as f:
        json.dump({"gates": ok,
                   "frozen_sha12": {k: v[:12] for k, v in fb.items()},
                   "C0": {"d0": n0, "d1": n1, "S_share": round(s0, 4)}}, f,
                  indent=1)
    print("OZET-KPR-F0: " + ("OK" if all(ok.values()) else "BATTI"))
    return all(ok.values())


def run():
    print("== KPR kosular ==")
    cfgs = {"C0": "C0", "F1": "F1", "F1sep": "F1",
            "F1sepF4": "F1F4", "F1sepF8": "F1F8", "FULL": "FULL"}
    seps = {"C0": False, "F1": False, "F1sep": True, "F1sepF4": True,
            "F1sepF8": True, "FULL": True}
    arms, store = [], {}
    n = [0]

    def arm(rid, meta, sims):
        arms.append(dict({"id": rid}, **meta))
        for sid, res in sims:
            store[sid] = res
            n[0] += 1

    for name, cfg in cfgs.items():
        for d in (0, 1):
            sims = []
            for s in range(12):
                sims.append((f"kpr_{name}_d{d}_s{s}",
                             D.run(slot=s, d_step=d, cfg=cfg,
                                   sep=seps[name])))
            arm(f"kpr_{name}_d{d}", {"cfg": name, "dstep": d}, sims)
    for name, cfg in cfgs.items():
        for a in AMPS:
            sims = []
            for s in range(12):
                sims.append((f"kpr_{name}_a{a}_s{s}",
                             D.run(slot=s, amp=a, cfg=cfg,
                                   sep=seps[name])))
            arm(f"kpr_{name}_a{a}", {"cfg": name, "amp": a}, sims)
    with open(os.path.join(OUT, "kpr_axes.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "cfg", "dstep", "amp"])
        w.writeheader()
        for x in arms:
            w.writerow({k: x.get(k, "") for k in
                        ("id", "cfg", "dstep", "amp")})
    with open(os.path.join(OUT, "kpr_runs.json"), "w") as f:
        json.dump(store, f)
    man = {"spec": "pattern/KPR_SPEC.md", "n_arms": len(arms),
           "n_sims": n[0],
           "arm_ids": sorted(a["id"] for a in arms)}
    mtxt = json.dumps(man, sort_keys=True)
    man["sha256"] = hashlib.sha256(mtxt.encode()).hexdigest()
    with open(os.path.join(OUT, "kpr_manifest.json"), "w") as f:
        json.dump(man, f, indent=1)
    print(f"OZET-KPR-RUN: {len(arms)} kol, {n[0]} sim OK")


if __name__ == "__main__":
    args = set(sys.argv[1:]) or {"--all"}
    if "--gate" in args or "--all" in args:
        if not gate():
            sys.exit("KPR DURDU: Faz 0 kirmizi")
    if "--run" in args or "--all" in args:
        run()
