"""Memory readout ailesi E1/E2/X1/X2 + column_audit (Asama A).

PATTERN_MEMORY_USE_SPEC.md on-kaydi. Salt-okunur mem.csv okur; C++ YOK.
S0..S3 readout_v3d.py'den sarmalanir (O DOSYA DEGISTIRILMEZ).
E1: (birim, effbin); birim-gun ortalama eff_g, kenar [0,1.5,2.5,3.5,inf).
E2: {("MEAN", bin)}; tum-gun ortalama eff_g ayni kenarla (tek ozet).
X1: S3 birlesim E1. X2: iki-asamali (S3 top-3 -> E1 secim, k=3).
"""
import csv
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "pattern"))
import readout_v3d as R  # noqa: E402

EFF_EDGES = [0, 1.5, 2.5, 3.5, float("inf")]
AUDIT_COLS = ["soma", "eff_g", "coinc", "aK1", "aK2", "aK3", "bK1", "bK2",
              "bK3"]


def column_audit(path):
    rows = list(csv.DictReader(open(path)))
    out = {"rows": len(rows)}
    for c in AUDIT_COLS:
        out[c] = len(set(r[c] for r in rows)) if rows else 0
    if rows:
        e = sorted(float(r["eff_g"]) for r in rows)
        out["eff_min"], out["eff_max"] = round(e[0], 4), round(e[-1], 4)
    return out


def load_eff(path):
    rec = defaultdict(list)
    with open(path) as f:
        for r in csv.DictReader(f):
            rec[(int(r["tick"]) // 50, int(r["unit"]))].append(
                float(r["eff_g"]))
    return rec


def eff_bin(v):
    for i in range(len(EFF_EDGES) - 1):
        if EFF_EDGES[i] <= v < EFF_EDGES[i + 1]:
            return i
    return len(EFF_EDGES) - 2


def sig_E1(tv, by, path):
    rec = load_eff(path)
    out = {}
    for d, s in by.items():
        t = set()
        for u in s:
            vs = rec.get((d, u), [])
            if vs:
                t.add((u, eff_bin(sum(vs) / len(vs))))
        out[d] = frozenset(t)
    return out


def sig_E2(tv, by, path):
    rec = load_eff(path)
    allv = []
    for (d, _), vs in rec.items():
        allv += vs
    out = {}
    for d in by:
        vs = []
        for (dd, _), v in rec.items():
            if dd == d:
                vs += v
        if vs:
            out[d] = frozenset({("MEAN", eff_bin(sum(vs) / len(vs)))})
        else:
            out[d] = frozenset()
    return out


def sig_X1(tv, by, path):
    s3 = R.READOUTS["S3"](tv, by)
    e1 = sig_E1(tv, by, path)
    return {d: s3.get(d, frozenset()) | e1.get(d, frozenset())
            for d in set(s3) | set(e1)}


def x2_query(qsig_s3, qsig_e1, refs_s3, refs_e1, k=3):
    """refs_*: [(sig, label)]. Donus: cogunluk labeli (yoksa None)."""
    qw = R.wins_from_sig(qsig_s3, "q", 900000)
    ew = R.wins_from_sig(qsig_e1, "q", 900000)
    rw = []
    for i, (sig, lab) in enumerate(refs_s3):
        rw += R.wins_from_sig(sig, lab, i * 100000)
    er = []
    for i, (sig, lab) in enumerate(refs_e1):
        er += R.wins_from_sig(sig, lab, i * 100000)
    votes = []
    for q, qe in zip(qw, ew):
        scored = sorted(((R.seq_sim(q["seq"], r["seq"]), r) for r in rw),
                        key=lambda t: -t[0])
        top_labels = {r["label"] for _, r in scored[:k]}
        best, bs = None, -1.0
        for e in er:
            if e["label"] not in top_labels:
                continue
            v = R.seq_sim(qe["seq"], e["seq"])
            if v > bs:
                best, bs = e["label"], v
        if best is not None:
            votes.append(best)
    if not votes:
        return None
    return max(set(votes), key=votes.count)


MEMREADOUTS = {"E1": sig_E1, "E2": sig_E2, "X1": sig_X1}
