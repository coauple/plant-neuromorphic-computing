"""KBH analiz: N kanallari, L0-L4 butcesi, tavan, greedy-secimi.
Kullanim: python3 pattern/kbh_analyze.py [--greedy-pick]
Cikti: pattern/p0_out/kbh_budget.json (+ stdout tablolari).
"""
import csv
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "pattern", "p0_out")
TAVAN = {"legacy": 1, "v2": 6}


def load():
    with open(os.path.join(OUT, "kbh_traces.json")) as f:
        traces = json.load(f)
    runs = {}
    for fn in ("kbh_taps.csv", "kbh_runs.csv"):
        p = os.path.join(OUT, fn)
        if os.path.exists(p):
            with open(p) as f:
                for r in csv.DictReader(f):
                    runs[r["id"]] = r
    return traces, runs


def rnd(v, nd=9):
    if isinstance(v, (list, tuple)):
        return tuple(round(float(x), nd) for x in v)
    return round(float(v), nd)


def N_distinct(sigs):
    return len(set(sigs))


def isi(ticks):
    t = list(ticks)
    return tuple(b - a for a, b in zip(t, t[1:]))


def leg(tr):
    return tr


def units(tr):
    return sorted(int(k) for k in tr.keys() if str(k).isdigit())


def N_T5(runs_traces, arch, analog=True):
    # spike sayi-imzasi: ates tick demetleri
    per = {}
    if arch == "legacy":
        sigs = [tuple(r[1]["fire_ticks"]) for r in runs_traces]
        return N_distinct(sigs), {}
    for r in runs_traces:
        rid, tr = r
        uu = units(tr)
        per[rid] = {u: tuple(tr[str(u)]["fire_ticks"]) for u in uu}
    pool = [s for d in per.values() for s in d.values()]
    # birim-basi N + max (tavan baglamiyla raporlanir)
    by_unit = {}
    for u in range(6):
        by_unit[u] = N_distinct([d[u] for d in per.values()])
    return max(by_unit.values()), by_unit


def N_T5_time(runs_traces, arch):
    if arch == "legacy":
        return N_distinct([isi(r[1]["fire_ticks"]) for r in runs_traces]), {}
    by_unit = {}
    per = [(rid, tr) for rid, tr in runs_traces]
    for u in range(6):
        by_unit[u] = N_distinct([isi(tr[str(u)]["fire_ticks"]) for _, tr in per])
    return max(by_unit.values()), by_unit


def N_T4(runs_traces, arch):
    if arch == "legacy":
        sigs = [(rnd(r[1]["soma"]), rnd(r[1]["eff"])) for r in runs_traces]
        return N_distinct(sigs), {}
    by_unit = {}
    per = [(rid, tr) for rid, tr in runs_traces]
    for u in range(6):
        by_unit[u] = N_distinct([(rnd(tr[str(u)]["soma"]),
                                  rnd(tr[str(u)]["eff"])) for _, tr in per])
    return max(by_unit.values()), by_unit


def N_T1(runs_traces, arch):
    if arch == "legacy":
        sigs = [(rnd(r[1]["k1V"]), rnd(r[1]["k1g"])) for r in runs_traces]
        return N_distinct(sigs), {}
    by_unit = {}
    per = [(rid, tr) for rid, tr in runs_traces]
    for u in range(6):
        by_unit[u] = N_distinct([(rnd(tr[str(u)]["k1V"]),
                                  rnd(tr[str(u)]["k1g"])) for _, tr in per])
    return max(by_unit.values()), by_unit


def N_T3_count(runs_traces, arch):
    # projeksiyon yuku imzasi: (darbe sayisi, varis tick demeti)
    # Faz 1 tek-uyaranda tum slotlar ayni -> N=1 (A0 gecikmede ayrisir).
    sigs = []
    for rid, tr in runs_traces:
        if arch == "legacy":
            ft = tr["fire_ticks"]
            sigs.append((len(ft),))
        else:
            uu = units(tr)
            sigs.append(tuple(sorted(
                (u, len(tr[str(u)]["fire_ticks"])) for u in uu)))
    return N_distinct(sigs), {}


def L4_coinc(runs_traces, arch):
    if arch == "legacy":
        tot = sum(len(r[1]["coinc"]) for r in runs_traces)
        c = sum(sum(r[1]["coinc"]) for r in runs_traces)
        return 1.0 - c / max(1, tot)
    tot = c = 0
    for _, tr in runs_traces:
        for u in units(tr):
            tot += len(tr[str(u)]["coinc"])
            c += sum(tr[str(u)]["coinc"])
    return 1.0 - c / max(1, tot)


def M_amp(traces, runs, arch):
    # ayni slot: amp 1.0 vs 4.0 K1-V L2 mesafesi (Faz 1 ciftleri)
    ds = []
    by_slot = {}
    for r in runs.values():
        if r.get("axis") == "F1" and r["arch"] == arch:
            by_slot.setdefault(int(r["slot"]), {})[float(r["amp"])] = r["id"]
    for s, d in by_slot.items():
        if 1.0 in d and 4.0 in d:
            a = traces[d[1.0]]
            b = traces[d[4.0]]
            if arch == "legacy":
                va, vb = a["k1V"], b["k1V"]
            else:
                va = [x for u in range(6) for x in a[str(u)]["k1V"]]
                vb = [x for u in range(6) for x in b[str(u)]["k1V"]]
            ds.append(math.sqrt(sum((x - y) ** 2 for x, y in zip(va, vb))))
    return sum(ds) / max(1, len(ds)), len(ds)


def subset(traces, runs, arch, axis=None, amp=None, **flt):
    out = []
    for rid, r in runs.items():
        if r["arch"] != arch:
            continue
        if axis is not None and r.get("axis") != axis:
            continue
        if amp is not None and float(r.get("amp") or 0) != amp:
            continue
        skip = False
        for k, v in flt.items():
            if r.get(k) != str(v):
                skip = True
                break
        if skip:
            continue
        out.append((rid, traces[rid]))
    return out


def budget_for(runs_traces, arch):
    n1, d1 = N_T1(runs_traces, arch)
    n3, _ = N_T3_count(runs_traces, arch)
    n4, d4 = N_T4(runs_traces, arch)
    n5, d5 = N_T5(runs_traces, arch)
    nt, dt = N_T5_time(runs_traces, arch)
    l4 = L4_coinc(runs_traces, arch)
    tot = 12 - n5
    return {"N_T1": n1, "N_T3": n3, "N_T4": n4, "N_T5": n5,
            "N_zaman": nt, "L_total": tot, "L0": 12 - n1,
            "L1": n1 - n3, "L2": n3 - n4, "L3": n4 - n5, "L4": round(l4, 4),
            "tavan": TAVAN[arch], "by_unit_T5": d5, "by_unit_T1": d1,
            "by_unit_T4": d4}


def main():
    traces, runs = load()
    rep = {"tavan": TAVAN, "faz1": {}, "eksenler": {}, "M_amp": {}}
    for arch in ("legacy", "v2"):
        f1 = subset(traces, runs, arch, axis="F1", amp=1.0)
        rep["faz1"][arch] = budget_for(f1, arch)
        rep["M_amp"][arch] = M_amp(traces, runs, arch)
    # OFAT eksen taramalari: N(T5) kontrol-degisimi
    for axis in ("A0", "A1a", "A1b", "A2"):
        rep["eksenler"][axis] = {}
        key = {"A0": "dstep", "A1a": "wring", "A1b": "ratio",
               "A2": "mode"}[axis]
        for arch in ("legacy", "v2"):
            vals = sorted(set(r.get(key, "") for r in runs.values()
                              if r.get("axis") == axis and r["arch"] == arch))
            rep["eksenler"][axis][arch] = {}
            for v in vals:
                sub = subset(traces, runs, arch, axis=axis, amp=1.0,
                             **{key: v})
                n5, _ = N_T5(sub, arch)
                rep["eksenler"][axis][arch][v] = n5
    # A1c readout + A3 analog: analiz-boyutu degerlendirme
    rep["A1c"] = {}
    for arch in ("legacy", "v2"):
        f1 = subset(traces, runs, arch, axis="F1", amp=1.0)
        if arch == "legacy":
            full = []
            for rid, tr in f1:
                full.append((rnd(tr["k1V"]), rnd(tr["k1g"]), rnd(tr["soma"]),
                             rnd(tr["eff"]), tuple(tr["fire_ticks"])))
            rep["A1c"][arch] = {"readout1_N": N_T5(f1, arch)[0],
                                "readout12_N": N_distinct(full)}
        else:
            full = []
            for rid, tr in f1:
                full.append(tuple(
                    (rnd(tr[str(u)]["k1V"]), rnd(tr[str(u)]["soma"]),
                     tuple(tr[str(u)]["fire_ticks"])) for u in range(6)))
            rep["A1c"][arch] = {"readout1_N": N_T5(f1, arch)[0],
                                "readout12_N": N_distinct(full)}
    rep["A3"] = {}
    for arch in ("legacy", "v2"):
        rep["A3"][arch] = {}
        for lk in ("0.02", "0.06", "0.10"):
            sub = subset(traces, runs, arch, axis="A3", amp=1.0, leak=lk)
            n_spike, _ = N_T5(sub, arch)
            if arch == "legacy":
                n_full = N_distinct([(rnd(tr["k1V"]), rnd(tr["soma"]),
                                      tuple(tr["fire_ticks"]))
                                     for _, tr in sub])
            else:
                n_full = N_distinct([tuple(
                    (rnd(tr[str(u)]["k1V"]), rnd(tr[str(u)]["soma"]),
                     tuple(tr[str(u)]["fire_ticks"])) for u in range(6))
                    for _, tr in sub])
            rep["A3"][arch][lk] = {"analog0_N": n_spike, "analog1_N": n_full}
    with open(os.path.join(OUT, "kbh_budget.json"), "w") as f:
        json.dump(rep, f, indent=1)
    print(json.dumps({"faz1": rep["faz1"], "M_amp": rep["M_amp"]}, indent=1))
    print("OZET-KBH-ANALIZ: budget yazildi")


if __name__ == "__main__":
    main()
