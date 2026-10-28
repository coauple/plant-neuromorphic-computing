"""KBHP analiz: N_sig / N_pair / N_pv / L4 / S_share + eksen tablosu.
Kullanim: python3 pattern/kbp_analyze.py
Cikti: pattern/p0_out/kbp_budget.json (+ stdout).
"""
import csv
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "pattern", "p0_out")


def rnd(v, nd=9):
    if isinstance(v, (list, tuple)):
        return tuple(round(float(x), nd) for x in v)
    return round(float(v), nd)


def load():
    with open(os.path.join(OUT, "kbp_runs.json")) as f:
        store = json.load(f)
    arms = {}
    with open(os.path.join(OUT, "kbp_axes.csv")) as f:
        for r in csv.DictReader(f):
            arms[r["id"]] = r
    pairs = json.load(open(os.path.join(OUT, "kbp_pairs.json")))["ciftler"]
    return store, arms, pairs


def sims_of(store, arms, **flt):
    out = []
    for aid, a in arms.items():
        skip = any(a.get(k, "") != str(v) for k, v in flt.items())
        if skip:
            continue
        out.append(aid)
    return out


def sig_v2(tr, u, okuma):
    u = tr[str(u)]
    base = (rnd(u["g0"]), tuple(u["fire_ticks"]))
    if okuma in ("R1", "R2"):
        base = base + (rnd([u["r1"][t] for t in range(0, 160, 10)]),)
    if okuma == "R2":
        base = base + (rnd([u["r2"][t] for t in range(0, 160, 10)]),)
    return base


def sig_leg(tr, okuma):
    base = (rnd(tr["g0"]), tuple(tr["fire_ticks"]))
    if okuma in ("R1", "R2"):
        base = base + (rnd(tr["r1"][::10]),)
    if okuma == "R2":
        base = base + (rnd(tr["r2"][::10]),)
    return base


def pair_sig_v2(store, arms, topo, okuma, coinc, pairs):
    # cift imzasi: 6 birim atis-sayilari + dominant vektor; sahipler = merkezi
    # X/Y olan kablolu birimler (S5: {1:P3a,4:P3b,7:P3c,5:P3d,6:P3e,0:P3f}).
    centers = {0: 1, 1: 4, 2: 7, 3: 5, 4: 6, 5: 0}
    out = {}
    for pi, pr in enumerate(pairs):
        aid = f"v2p_{topo}_{okuma}_{coinc}_p{pi}"
        tr = store[aid]
        counts = tuple(sum(tr[str(u)]["fire"]) for u in range(6))
        dom = tuple(sorted(u for u in range(6)
                           if sum(tr[str(u)]["fire"]) == max(counts) and
                           max(counts) > 0))
        owners = tuple(sorted(u for u, c in centers.items()
                              if c in (pr["X"], pr["Y"])))
        out[pi] = {"counts": counts, "dom": dom, "owners": owners,
                   "X": pr["X"], "Y": pr["Y"], "destek": pr["destek"]}
    return out


def N_pair(store, arms, topo, okuma, coinc, pairs):
    ps = pair_sig_v2(store, arms, topo, okuma, coinc, pairs)
    sigs = [(v["counts"], v["dom"]) for v in ps.values()]
    n_distinct = len(set(sigs))
    sel = 0
    for pi, v in ps.items():
        others = [s for pj, s in enumerate(
            [(w["counts"], w["dom"]) for w in ps.values()]) if pj != pi]
        own_fire = sum(v["counts"][u] for u in v["owners"])
        tot_fire = sum(v["counts"])
        if (v["counts"], v["dom"]) not in others and v["owners"] and \
                own_fire >= 0.5 * tot_fire and tot_fire > 0:
            sel += 1
    return n_distinct, sel, ps


def N_pv(store, arms, arch, **flt):
    vecs = set()
    for a in arms.values():
        if a["arch"] != arch:
            continue
        if any(a.get(k, "") != str(v) for k, v in flt.items()):
            continue
        tr = store[a["id"]]
        if arch == "v2":
            T = max(len(tr[str(u)]["fire"]) for u in range(6))
            for t in range(T):
                v = tuple(tr[str(u)]["fire"][t] for u in range(6))
                if any(v):
                    vecs.add(v)
        else:
            for kb in tr["kbits"]:
                if any(kb):
                    vecs.add(tuple(kb) + (0,))
    return len(vecs)


def _sim_match(sid, arch, flt):
    # kol-ici sim esleme: v2_{okuma}_{parite}_d{d}_s{N}[_CL], leg_*.
    if arch == "v2":
        if not sid.startswith("v2_"):
            return False
        p = sid.split("_")
        got = {"okuma": p[1], "parite": p[2], "dstep": p[3][1:],
               "coinc": "lock" if sid.endswith("_CL") else "nat",
               "topoloji": "T0"}
    else:
        if not sid.startswith("leg_"):
            return False
        got = {"okuma": "R0", "parite": "id", "dstep": "0",
               "coinc": "nat", "topoloji": "T0"}
    return all(got.get(k, "") == str(v) for k, v in flt.items())


def L4(store, arms, arch, **flt):
    tot = c = 0
    for sid, tr in store.items():
        if not _sim_match(sid, arch, flt):
            continue
        if arch == "v2":
            for u in range(6):
                tot += len(tr[str(u)]["coinc"])
                c += sum(tr[str(u)]["coinc"])
        else:
            tot += len(tr["coinc"])
            c += sum(tr["coinc"])
    if tot == 0:
        return None
    return 1.0 - c / tot


def S_share(store, arms, arch, **flt):
    vals = []
    for sid, tr in store.items():
        if not _sim_match(sid, arch, flt):
            continue
        if arch == "v2":
            for u in range(6):
                vals.append(tr[str(u)]["S_share"])
        else:
            vals.append(tr["S_share"])
    if not vals:
        return None, 0
    return sum(vals) / len(vals), len(vals)


def main():
    store, arms, pairs = load()
    rep = {"arms": {}, "selectivity": {}, "L4": {}, "S_share": {}}
    for arch in ("v2", "legacy"):
        for okuma in ("R0", "R1", "R2"):
            for parite in ("id", "sep"):
                for d in ("0", "1", "2", "4", "6"):
                    for co in (["nat"] if parite == "id" else ["nat", "lock"]):
                        flt = {"okuma": okuma, "parite": parite, "dstep": d,
                               "topoloji": "T0", "coinc": co}
                        ids = [a["id"] for a in arms.values()
                               if a["arch"] == arch and all(
                                   a.get(k, "") == str(v)
                                   for k, v in flt.items())
                               and a["id"].split("_")[0] in
                               ("v2", "leg")]
                        if not ids:
                            continue
                    # N_sig: 12 slot-sim uzerinden (kol-ici)
                    if arch == "v2":
                        suf = "_CL" if co == "lock" else ""
                        subs = [f"v2_{okuma}_{parite}_d{d}_s{s}{suf}"
                                for s in range(12)]
                    else:
                        if not (okuma == "R0" and parite == "id" and
                                d == "0"):
                            continue
                        subs = [f"leg_R0_id_d0_s{s}" for s in range(12)]
                    sigs = []
                    for sid in subs:
                        tr = store[sid]
                        if arch == "v2":
                            parts = []
                            for u in range(6):
                                cu = tr[str(u)]
                                p = [rnd(cu["g0"][::10]),
                                     tuple(cu["fire_ticks"])]
                                if okuma in ("R1", "R2"):
                                    p.append(rnd(cu["r1"][::10]))
                                if okuma == "R2":
                                    p.append(rnd(cu["r2"][::10]))
                                parts.append(tuple(p))
                            sigs.append(tuple(parts))
                        else:
                            p = [rnd(tr["g0"][::10]), tuple(tr["fire_ticks"])]
                            if okuma in ("R1", "R2"):
                                p.append(rnd(tr["r1"][::10]))
                            if okuma == "R2":
                                p.append(rnd(tr["r2"][::10]))
                            sigs.append(tuple(p))
                    rep["arms"][f"{arch}_{okuma}_{parite}_d{d}_{co}"] = {
                        "N_sig": len(set(sigs)), "n": len(sigs)}
    for topo in ("T0", "T1"):
        for okuma in ("R0", "R1", "R2"):
            for cl in ("nat", "CL"):
                nd, sel, ps = N_pair(store, arms, topo, okuma, cl, pairs)
                rep["selectivity"][f"{topo}_{okuma}_{cl}"] = {
                    "N_distinct": nd, "selective": sel, "pairs": ps}
    for arch in ("v2", "legacy"):
        rep["L4"][arch] = {"d0": L4(store, arms, arch, topoloji="T0",
                                    coinc="nat", dstep="0", parite="id",
                                    okuma="R0"),
                           "dall": {d: L4(store, arms, arch, topoloji="T0",
                                          coinc="nat", dstep=d, parite="id",
                                          okuma="R0") for d in
                                    ("0", "1", "2", "4", "6")}}
        rep["S_share"][arch] = {
            d: S_share(store, arms, arch, topoloji="T0", coinc="nat",
                       dstep=d, parite="id", okuma="R0") for d in
            ("0", "1", "2", "4", "6")}
    with open(os.path.join(OUT, "kbp_budget.json"), "w") as f:
        json.dump(rep, f, indent=1, default=str)
    print("OZET-KBHP-ANALIZ: budget yazildi")
    for k, v in rep["arms"].items():
        print(f"  {k}: N_sig={v['N_sig']}/{v['n']}")
    for k, v in rep["selectivity"].items():
        print(f"  {k}: distinct={v['N_distinct']}/6 selective={v['selective']}/6")


if __name__ == "__main__":
    main()
