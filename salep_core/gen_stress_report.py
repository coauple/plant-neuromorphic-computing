"""Stres rapor uretici: results.json + run.log -> CSV + PNG.

Girdi: PSTRESS_BASE (/tmp/pstress_d) altinda results.json + run.log.
Cikti: salep_core/stress_out/ (cases.csv, groups.csv, fig1/2/3.png).
ADDITIVE-ONLY yeni dosya; analiz-only, mimari degisikligi yok.
"""
import csv
import json
import os
import re
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BASE = os.environ.get("PSTRESS_BASE", "/tmp/pstress_d")
ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "stress_out")

CASE_RE = re.compile(
    r"^  (\w+): rows=(\d+) Nsig=(\d+) Npv=(\d+) rep=([\d.\-]+)"
    r"(?: stab=([\d.\-]+))?")
ACC_RE = re.compile(r"retrieval-acc=([\d.\-]+)\(n=(\d+)\)")
WITHIN_RE = re.compile(
    r"within\(45,45r\)=([\d.\-]+) betw\(40,45\)=([\d.\-]+) "
    r"betw\(45,50\)=([\d.\-]+) betw\(40,50\)=([\d.\-]+)")
ROB_RE = re.compile(r"seed-robustness=([\d.\-]+)")
JAC_RE = re.compile(r"jacc\(b,h\)=([\d.\-]+) jacc\(b,c\)=([\d.\-]+) "
                    r"jacc\(h,c\)=([\d.\-]+)")
SETJ_RE = re.compile(r"setJ\((?:ABC,CBA|n,d)\)=([\d.\-]+)")
SETJ2_RE = re.compile(r"setJ\(ABC,ROT\)=([\d.\-]+)")
SETJ_NI = re.compile(r"setJ\(n,i\)=([\d.\-]+)")
FAM_RE = re.compile(r"aile-uyumu=([\d.\-]+)\(n=(\d+)\)")
Q_RE = re.compile(r"  (q\w+)->uyum=([\d.\-]+)\(n=(\d+)\)")
FIN_RE = re.compile(r"final-setJ=([\d.\-]+) sensDIST=([\d.\-]+)")
ETA_RE = re.compile(
    r"  eta=([\d.]+): Nsig=(\d+) Npv=(\d+) rep=([\d.\-]+) stab=([\d.\-]+)")
ETAJ_RE = re.compile(r"jacc\(0,0\.30\)=([\d.\-]+) "
                     r"jacc\(0\.15,0\.30\)=([\d.\-]+)")
TILE_RE = re.compile(r"  karo-x6: Nsig=(\d+) Npv=(\d+) rep=([\d.\-]+)")
LONG_RE = re.compile(r"  260gun: rows=(\d+) Nsig=(\d+) Npv=(\d+) "
                     r"rep=([\d.\-]+)")
CHANCE = {"G1": 1 / 7, "G2": 0.25, "G5": 0.25, "G9": 1 / 3, "G12": 0.5}


def m_of(mem):
    import sys as _s
    _s.path.insert(0, ROOT)
    import pattern_stress_v3 as P
    tv = P.tickvec(mem)
    vecs = list(tv.values())
    n_pv = len(set(vecs))
    rep = round(1 - n_pv / len(vecs), 4) if vecs else -1.0
    by = P.daysig(mem)
    sigs = [s for s in by.values() if s]
    import statistics as _st
    per = {}
    for u in range(29):
        per[u] = sorted(t for t, s in tv.items() if u in s)
    diffs = []
    for ts in per.values():
        diffs += [b - a for a, b in zip(ts, ts[1:])]
    isi = (round(_st.mean(diffs), 2), round(_st.pstdev(diffs), 2),
           len(diffs)) if diffs else (-1, -1, 0)
    days = sorted(by)
    h = len(days) // 2
    s1 = {frozenset(by[d]) for d in days[:h] if by[d]}
    s2 = {frozenset(by[d]) for d in days[h:] if by[d]}
    stab = round(len(s1 & s2) / len(s1 | s2), 4) if (s1 | s2) else -1.0
    import csv as _c
    rows = sum(1 for _ in open(mem)) - 1
    return {"rows": rows, "N_sig": len({frozenset(s) for s in sigs}),
            "N_pv": n_pv, "repetition": rep, "ISI_mean": isi[0],
            "ISI_std": isi[1], "ISI_n": isi[2], "stabilite": stab,
            "days": len(by),
            "units": "+".join(map(str, sorted(
                {u for s in by.values() for u in s})))}


def main():
    os.makedirs(OUT, exist_ok=True)
    log = open(os.path.join(BASE, "run.log")).read().splitlines()

    cases = []
    mems = []
    for root, _, files in os.walk(BASE):
        if "mem.csv" in files and not root.endswith(".chk"):
            mems.append(os.path.join(root, "mem.csv"))
    for mp in sorted(mems):
        tag = os.path.basename(os.path.dirname(mp))
        if tag.endswith("_c"):
            tag = tag[:-2]
        try:
            m = m_of(mp)
        except Exception as e:
            print(f"  ATLAMA {tag}: {e}")
            continue
        cases.append({"case": tag, **m})
    extra = []  # mem-taramasi tum caseleri kapsar; log-ayristirma
    # yalniz grup-metrikleri (groups.csv) icin kullanilir, case satiri uretmez.
    with open(os.path.join(OUT, "cases.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(cases[0].keys()))
        w.writeheader()
        w.writerows(cases + extra)

    groups, cur, gd = [], None, {}
    GH_RE = re.compile(r"^(G\d+)\s")
    for ln in log:
        mtg = GH_RE.match(ln)
        if mtg:
            if cur:
                groups.append((cur, gd))
            cur, gd = mtg.group(1), {}
            continue
        for rx, ks in ((ACC_RE, ("ret_acc", "ret_n")),
                       (ROB_RE, ("robust",)),
                       (FAM_RE, ("family", "family_n")),
                       (FIN_RE, ("final_setJ", "sensDIST")),
                       (ETAJ_RE, ("eta_j01", "eta_j02")),
                       (WITHIN_RE, ("w_in", "b4045", "b4550", "b4050"))):
            mt = rx.search(ln)
            if mt:
                gd.update(dict(zip(ks, mt.groups())))
        mt = JAC_RE.search(ln)
        if mt:
            gd.update({"j_bh": mt.group(1), "j_bc": mt.group(2),
                       "j_hc": mt.group(3)})
        mt = SETJ_RE.search(ln)
        if mt:
            gd["setJ1"] = mt.group(1)
        mt = SETJ2_RE.search(ln)
        if mt:
            gd["setJ_ROT"] = mt.group(1)
        mt = SETJ_NI.search(ln)
        if mt:
            gd["setJ_ni"] = mt.group(1)
        mt = Q_RE.search(ln)
        if mt:
            gd[f"fam_{mt.group(1)}"] = f"{mt.group(2)}(n={mt.group(3)})"
        mt = TILE_RE.search(ln)
        if mt:
            gd.update({"tile_Nsig": mt.group(1), "tile_Npv": mt.group(2),
                       "tile_rep": mt.group(3)})
        mt = LONG_RE.search(ln)
        if mt:
            gd.update({"long_rows": mt.group(1), "long_Nsig": mt.group(2),
                       "long_Npv": mt.group(3), "long_rep": mt.group(4)})
        if "OK " in ln or "BATTI" in ln:
            gd[ln.split()[1]] = "OK" if "OK " in ln else "BATTI"
    if cur:
        groups.append((cur, gd))
    groups.sort(key=lambda gd: int(gd[0][1:]))
    gkeys = sorted({k for _, d in groups for k in d})
    with open(os.path.join(OUT, "groups.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["group"] + gkeys)
        w.writeheader()
        for g, d in groups:
            w.writerow({"group": g, **d})

    names = [c["case"] for c in cases]
    nsig = [c["N_sig"] for c in cases]
    nppv = [c["N_pv"] for c in cases]
    fig, ax = plt.subplots(figsize=(14, 5))
    x = range(len(names))
    ax.bar([i - 0.2 for i in x], nsig, 0.4, label="N_sig")
    ax.bar([i + 0.2 for i in x], nppv, 0.4, label="N_pv")
    ax.set_xticks(list(x))
    ax.set_xticklabels(names, rotation=90, fontsize=7)
    ax.legend(fontsize=8)
    ax.set_title("v3d pattern cesitliligi (N_sig / N_pv)")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig1_diversity.png"), dpi=100)

    accs = [(g, float(d["ret_acc"]), int(d["ret_n"]))
            for g, d in groups if "ret_acc" in d]
    fig, ax = plt.subplots(figsize=(7, 4))
    labs = [g for g, _, _ in accs]
    ax.bar(labs, [a for _, a, _ in accs], label="retrieval-acc")
    ax.bar(labs, [CHANCE.get(g, 0) for g, _, _ in accs], alpha=0.4,
           label="sans")
    for i, (_, a, n) in enumerate(accs):
        ax.text(i, a + 0.01, f"{a:.3f}(n={n})", ha="center", fontsize=8)
    ax.legend(fontsize=8)
    ax.set_title("retrieval-acc vs sans")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig2_retrieval.png"), dpi=100)

    reps = [(c["case"], c["repetition"]) for c in cases
            if c["repetition"] >= 0]
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.bar([r[0] for r in reps], [r[1] for r in reps])
    ax.set_xticks(range(len(reps)))
    ax.set_xticklabels([r[0] for r in reps], rotation=90, fontsize=7)
    ax.set_title("tekrar orani (repetition)")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig3_repetition.png"), dpi=100)
    print(f"OZET-REPORT: {len(cases)} case +{len(extra)} log, "
          f"{len(groups)} grup -> {OUT}")


if __name__ == "__main__":
    sys.exit(main())
