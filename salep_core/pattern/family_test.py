"""Kanonik aile testi (STIMULUS_SNR_SPEC.md G-FAM/G-DOSE/G-BIN).

LOO aile-kimligi: kablo (gun post-kumeleri) / S0 / eff_g x 3 kova
(B1 sabit [1.5,2.5,3.5]; B2 havuz-ceyrekler; B3 esit-genislik 4).
Doz: hava-yagmuru + sulama (mm); <=%2 eslesen ciftlerde uyum.
Cikti: stress_out_snr/family_test.csv.
"""
import argparse
import csv
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "pattern"))
import readout_v3d as R  # noqa: E402

BASE = "/tmp/snr"
OUTD = os.path.join(ROOT, "stress_out_snr")
B1 = [0, 1.5, 2.5, 3.5, float("inf")]


def bin_of(v, edges):
    for i in range(len(edges) - 1):
        if edges[i] <= v < edges[i + 1]:
            return i
    return len(edges) - 2


def day_posts(aff):
    by = {}
    with open(aff, newline="") as f:
        for r in csv.DictReader(f):
            by.setdefault(int(r["tick"]) // 50, set()).add(
                int(r["post_id"]))
    return {d: frozenset(s) for d, s in by.items()}


def day_eff(mem, edges):
    rec = {}
    with open(mem) as f:
        for r in csv.DictReader(f):
            rec.setdefault((int(r["tick"]) // 50, int(r["unit"])),
                           []).append(float(r["eff_g"]))
    byu = {}
    for (d, u), vs in rec.items():
        byu.setdefault(d, {})[u] = sum(vs) / len(vs)
    return {d: frozenset((u, bin_of(v, edges)) for u, v in m.items())
            for d, m in byu.items()}


def loo(pools):
    wins = []
    for i, (sig, lab) in enumerate(pools):
        wins += R.wins_from_sig(sig, lab, i * 100000)
    cm, viol = R.infer_cm(wins)
    tot = sum(cm.values())
    ok = sum(v for (t, p), v in cm.items() if t == p)
    conf = {}
    for (t, p), v in cm.items():
        conf[f"{t}->{p}"] = v
    return (round(ok / tot, 4), tot, viol, conf) if tot else (-1.0, 0, 0,
                                                             {})


def main():
    ap = argparse.ArgumentParser(description="Aile testi")
    ap.add_argument("--scens", default="base,drynew,irrig,hot,fert")
    ap.add_argument("--seeds", default="42,43,44,101,102")
    ap.add_argument("--tag", default="main")
    a = ap.parse_args()
    scens = [s.strip() for s in a.scens.split(",")]
    seeds = [int(s) for s in a.seeds.split(",")]
    os.makedirs(OUTD, exist_ok=True)
    mems = {s: [f"{BASE}/{s}_s{sd}/c/mem.csv" for sd in seeds]
            for s in scens}
    affs = {s: [f"{BASE}/{s}_s{sd}/afferent.csv" for sd in seeds]
            for s in scens}
    for s in scens:
        for p in mems[s] + affs[s]:
            assert os.path.exists(p), f"eksik: {p} (once snr_audit)"
    out = {}
    confs = {}
    # Kablo duzeyi.
    pools = []
    for i, s in enumerate(scens):
        for p in affs[s]:
            pools.append((day_posts(p), f"{s}"))
    acc, n, viol, conf = loo(pools)
    out["cable"] = {"acc": acc, "n": n, "viol": viol}
    confs["cable"] = conf
    print(f"  cable: acc={acc}(n={n}) viol={viol}", flush=True)
    # S0.
    pools = []
    for s in scens:
        for p in mems[s]:
            tv, by = R.load_mem(p)
            pools.append((R.READOUTS["S0"](tv, by), s))
    acc, n, viol, conf = loo(pools)
    out["S0"] = {"acc": acc, "n": n, "viol": viol}
    confs["S0"] = conf
    print(f"  S0: acc={acc}(n={n}) viol={viol}", flush=True)
    # eff_g kovalari.
    pool_eff = []
    for s in scens:
        for p in mems[s]:
            pool_eff.append(p)
    flat = []
    for p in pool_eff:
        with open(p) as f:
            flat += [float(r["eff_g"]) for r in csv.DictReader(f)]
    flat.sort()
    q = [flat[int(len(flat) * t)] for t in (0.25, 0.5, 0.75)]
    B2 = [0] + q + [float("inf")]
    mn, mx = flat[0], flat[-1]
    st = (mx - mn) / 4
    B3 = [mn + st * i for i in range(4)] + [float("inf")]
    for tag, edges in (("B1", B1), ("B2", B2), ("B3", B3)):
        pools = []
        for s in scens:
            for p in mems[s]:
                pools.append((day_eff(p, edges), s))
        acc, n, viol, conf = loo(pools)
        out[f"eff_{tag}"] = {"acc": acc, "n": n, "viol": viol,
                             "edges": [round(e, 3) for e in edges]}
        confs[f"eff_{tag}"] = conf
        print(f"  eff_{tag}: acc={acc}(n={n}) viol={viol}", flush=True)
    # W-dry -> base karisma (eff_B1 kanalindan).
    cb1 = confs["eff_B1"]
    out["confuse"] = cb1.get("drynew->base", 0)
    tot_dry = sum(v for k, v in cb1.items()
                  if k.startswith("drynew->"))
    out["confuse_frac"] = round(out["confuse"] / tot_dry, 4) \
        if tot_dry else -1.0
    print(f"  drynew->base: {out['confuse']}/{tot_dry} "
          f"= {out['confuse_frac']}", flush=True)
    # Doz eslesmesi.
    import snr_audit as S
    doses = {s: S.dose_of(s) for s in scens}
    pairs = []
    for i in range(len(scens)):
        for j in range(i + 1, len(scens)):
            da, db = doses[scens[i]], doses[scens[j]]
            if da and db and abs(da - db) / max(da, db) <= 0.02:
                pairs.append((scens[i], scens[j], da, db))
    out["dose_pairs"] = pairs
    print(f"  doz-ciftleri(<=%2): {pairs}", flush=True)
    dagree = []
    for aa, bb, _, _ in pairs:
        pp = []
        for s in (aa, bb):
            for p in mems[s]:
                pp.append((day_eff(p, B1), s))
        acc, n, viol, _ = loo(pp)
        dagree.append(acc)
        print(f"  doz {aa}-{bb}: acc={acc}(n={n})", flush=True)
    out["dose_agree"] = round(sum(dagree) / len(dagree), 4) if dagree \
        else -1.0
    if pairs:
        ok = out["dose_agree"] >= 0.90
        print(f"  {'OK' if ok else 'BATTI'} G-DOSE(>={out['dose_agree']})",
              flush=True)
    with open(os.path.join(OUTD, f"family_test_{a.tag}.csv"), "w",
              newline="") as f:
        w = csv.DictWriter(f, fieldnames=["kanal", "acc", "n", "viol",
                                          "not"])
        w.writeheader()
        for k, d in out.items():
            if not isinstance(d, dict):
                continue
            w.writerow({"kanal": k, "acc": d["acc"], "n": d["n"],
                        "viol": d["viol"],
                        "not": str(d.get("edges", ""))})
    import json as _j
    with open(os.path.join(OUTD, f"family_test_{a.tag}.json"), "w") as f:
        _j.dump(out, f, default=str)
    # G-FAM kapisi (5 sinif, sans 0.20).
    fam = out["eff_B1"]["acc"]
    ok = fam >= 0.90 and out["confuse_frac"] <= 0.05
    print(f"  {'OK' if ok else 'BATTI'} G-FAM(eff_B1>={fam} "
          f"karisma<={out['confuse_frac']})", flush=True)
    print("OZET-FAM: biten")


if __name__ == "__main__":
    main()
