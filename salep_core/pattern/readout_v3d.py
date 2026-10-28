"""v3d pattern-okuma katmani (V3D_READOUT_SPEC.md Faz 1).

Salt-okunur mem.csv okur; C++ YOK, mimari degisikligi YOK.
Tum readoutlar gun -> frozenset(token) uretir (Jaccard-uyumlu):
  S0: atesleyen birimler (referans).
  S1: top-k (k=3; esitlikte kucuk id).
  S2a: (sira, birim) ciftleri; sira = sayi-azalan, esitlik id-artan.
  S2b: (birim, bin); r=sayi/gun-maks; bin=-1 (r==0) else 1+min(3,int(r*4)).
  S3: (birim, isibin); global ortalama ISI, kenar [0,25,50,100,200,inf).
  S0-gurultu: S0 + flip (p=0.05, seed=7, evren 0..28).
Alt-makine: day_jacc, wins_from_sig, ret_acc, fam_agreement.
"""
import csv
import random
from collections import Counter

ISI_EDGES = [0, 25, 50, 100, 200, float("inf")]
K = 3


def load_mem(path):
    tv, by = {}, {}
    with open(path) as f:
        for r in csv.DictReader(f):
            t, u = int(r["tick"]), int(r["unit"])
            tv.setdefault(t, set()).add(u)
            by.setdefault(t // 50, set()).add(u)
    return tv, by


def day_counts(tv, by):
    dc = {}
    for d in by:
        c = Counter()
        for t, s in tv.items():
            if t // 50 == d:
                c.update(s)
        dc[d] = c
    return dc


def sig_S0(tv, by):
    return {d: frozenset(s) for d, s in by.items()}


def sig_S1(tv, by, k=3):
    dc = day_counts(tv, by)
    return {d: frozenset(u for u, _ in
                         sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[:k])
            for d, c in dc.items()}


def sig_S2a(tv, by):
    dc = day_counts(tv, by)
    out = {}
    for d, c in dc.items():
        ordered = sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))
        out[d] = frozenset((r, u) for r, (u, _) in enumerate(ordered))
    return out


def sig_S2b(tv, by):
    dc = day_counts(tv, by)
    out = {}
    for d, c in dc.items():
        mx = max(c.values()) if c else 0
        s = set()
        for u in range(29):
            n = c.get(u, 0)
            if n == 0 or mx == 0:
                s.add((u, -1))
            else:
                s.add((u, 1 + min(3, int(n / mx * 4))))
        out[d] = frozenset(s)
    return out


def unit_isi(tv):
    per = {}
    for u in range(29):
        per[u] = sorted(t for t, s in tv.items() if u in s)
    mean = {}
    for u, ts in per.items():
        dd = [b - a for a, b in zip(ts, ts[1:])]
        mean[u] = sum(dd) / len(dd) if dd else float("inf")
    return mean


def isi_bin(v):
    for i in range(len(ISI_EDGES) - 1):
        if ISI_EDGES[i] <= v < ISI_EDGES[i + 1]:
            return i
    return len(ISI_EDGES) - 2


def sig_S3(tv, by):
    mean = unit_isi(tv)
    return {d: frozenset((u, isi_bin(mean[u])) for u in s)
            for d, s in by.items()}


def sig_noise(tv, by, p=0.05, seed=7):
    rng = random.Random(seed)
    out = {}
    for d, s in by.items():
        t = set(s)
        for u in range(29):
            if rng.random() < p:
                if u in t:
                    t.discard(u)
                else:
                    t.add(u)
        out[d] = frozenset(t)
    return out


READOUTS = {"S0": lambda tv, by: sig_S0(tv, by),
            "S1": lambda tv, by: sig_S1(tv, by),
            "S2a": lambda tv, by: sig_S2a(tv, by),
            "S2b": lambda tv, by: sig_S2b(tv, by),
            "S3": lambda tv, by: sig_S3(tv, by),
            "S0n": lambda tv, by: sig_noise(tv, by)}


def day_jacc(a, b):
    ds = [d for d in set(a) | set(b) if a.get(d) or b.get(d)]
    if not ds:
        return -1.0
    tot = 0.0
    for d in ds:
        x, y = set(a.get(d, ())), set(b.get(d, ()))
        if not x and not y:
            tot += 1.0
        elif not x or not y:
            tot += 0.0
        else:
            tot += len(x & y) / len(x | y)
    return tot / len(ds)


def wins_from_sig(sig, label, off):
    wins = []
    days = sorted(sig)
    for i in range(len(days) - K + 1):
        ds = days[i:i + K]
        if ds != list(range(ds[0], ds[0] + K)):
            continue
        seq = tuple({"posts": set(sig.get(x, ())), "blines": set(),
                     "a": set()} for x in ds)
        if not any(sg["posts"] for sg in seq):
            continue
        wins.append({"s": ds[0] + off, "seq": seq, "label": label})
    return wins


def seq_sim(a, b):
    from validate_infer_pattern import similarity
    return sum(similarity(x, y) for x, y in zip(a, b)) / len(a)


def infer_cm(wins):
    from collections import Counter as _C
    cm, viol = _C(), 0
    for i, w in enumerate(wins):
        best, bs = None, -1.0
        for j, o in enumerate(wins):
            if i == j:
                continue
            if not (o["s"] + K <= w["s"] or w["s"] + K <= o["s"]):
                continue
            v = seq_sim(w["seq"], o["seq"])
            if v > bs:
                best, bs = o["label"], v
        if best is None:
            viol += 1
            continue
        cm[(w["label"], best)] += 1
    return cm, viol


def ret_acc(pools):
    wins = []
    for i, (sig, lab) in enumerate(pools):
        wins += wins_from_sig(sig, lab, i * 100000)
    if len(wins) < 4:
        return -1.0, len(wins)
    cm, _ = infer_cm(wins)
    tot = sum(cm.values())
    ok = sum(v for (t, p), v in cm.items() if t == p)
    return round(ok / tot, 4) if tot else -1.0, tot


def fam_agree(refs, queries):
    rw = []
    for i, (sig, lab) in enumerate(refs):
        rw += wins_from_sig(sig, lab, i * 100000)
    out = {}
    for sig, fam, tag in queries:
        qw = wins_from_sig(sig, fam, 900000)
        hit = 0
        for q in qw:
            best, bs = None, -1.0
            for r in rw:
                v = seq_sim(q["seq"], r["seq"])
                if v > bs:
                    best, bs = r["label"], v
            if best == fam:
                hit += 1
        out[tag] = round(hit / len(qw), 4) if qw else -1.0
    return out
