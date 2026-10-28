"""Kosul supurme deneyi (§9.65): ayni PLIR-A'dan kosul imzalari.

Pencereler (TEST B artefaktlari, kod degisikligi YOK): normal, kurak,
siddetli, sulama, recovery, yaz-kurakligi (cekirdekte isi soku
dusmedi; isi ekseni TEST A'da). Her kosulda: bitki spike, PLIR
kabul/red, P1, P2 ates, ayri etiket.

Soru: farkli fizyolojik durumlar farkli aktivite imzalarina
donusuyor mu?
Olcutler (D1-D5): red-sebebi + soma-destegi sutunlari dahil.
"""
import csv
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

WINDOWS = [(0, 30, "normal"), (30, 60, "kurak"), (60, 100, "siddetli"),
           (170, 180, "sulama"), (180, 220, "recovery"),
           (130, 170, "yaz")]
TAU = {0: 4, 1: 12}
BW = 1


def verdicts(ticks, tau):
    lock = 2 * tau + BW
    last = None
    out = []
    for t in sorted(ticks):
        if last is None or (t - last) > lock:
            out.append((t, "A"))
            last = t
        elif abs((t - last) - tau) < BW:
            out.append((t, "A"))
            last = t
        else:
            out.append((t, "R"))
    return out


def main():
    sp = {}
    with open(os.path.join(ROOT, "testb_spikes.csv")) as f:
        for row in csv.reader(f):
            if not row[0].isdigit():
                continue
            d, l, t = map(int, row)
            sp.setdefault(l, set()).add(d * 50 + t)
    acc = {l: verdicts(sorted(v), TAU[l]) for l, v in sp.items()}

    # Red-sebebi: plir karar gunlugunden ISI/TAU (kisa/uzun).
    red_why = {}
    with open(os.path.join(ROOT, "plir_decisions.csv")) as f:
        for row in csv.DictReader(f):
            if row["verdict"] != "RES-REJECT":
                continue
            d = int(row["tick"]) // 50
            w = red_why.setdefault(d, Counter())
            w["short" if int(row["isi"]) < TAU[int(row["line"])]
              else "long"] += 1

    p1, p2, lab = {}, {}, {}
    p1_ticks = []
    with open(os.path.join(ROOT, "testb_conditions.csv")) as f:
        for row in csv.reader(f):
            t = int(row[0])
            d = t // 50
            if row[3] == "1":
                p1[d] = p1.get(d, 0) + 1
                p1_ticks.append(t)
            if row[4] == "1":
                p1[d] = p1.get(d, 0) + 1
                p1_ticks.append(t)
            for k, ch in enumerate(row[5][:10]):
                if ch == "1":
                    c = p2.setdefault(d, Counter())
                    c[k] += 1
    with open(os.path.join(ROOT, "testb_afferent.csv")) as f:
        for row in csv.DictReader(f):
            lab.setdefault(int(row["tick"]) // 50, set()).add(
                row["label"])

    # Soma-destegi: P2 atesinin +-10 tick yakininda P1 var mi?
    # Var: A-destekli; yok: saf B-surus (soma desteksiz).
    import bisect as _bis
    p1_ticks.sort()
    p2_ticks = []
    with open(os.path.join(ROOT, "testb_afferent.csv")) as f:
        for row in csv.DictReader(f):
            p2_ticks.append(int(row["tick"]))
    p2_ticks.sort()

    def n_supported(a, b):
        n_sup = 0
        for ft in p2_ticks:
            if not (a * 50 <= ft < b * 50):
                continue
            i = _bis.bisect_left(p1_ticks, ft - 10)
            if i < len(p1_ticks) and p1_ticks[i] <= ft + 10:
                n_sup += 1
        return n_sup

    sig = {}
    print("kosul | bitki | kabul | red(k/u) | P1 | destek/safB | P2 | etiket")
    for a, b, nm in WINDOWS:
        ticks = [(l, t, v) for l in acc for t, v in acc[l]
                 if a * 50 <= t < b * 50]
        nsp, na = len(ticks), sum(1 for _, _, v in ticks if v == "A")
        rw = red_why.get(a, Counter())
        for d in range(a + 1, b):
            rw.update(red_why.get(d, Counter()))
        n1 = sum(p1.get(d, 0) for d in range(a, b))
        c = Counter()
        for d in range(a, b):
            c.update(p2.get(d, Counter()))
        labels = set()
        for d in range(a, b):
            labels.update(lab.get(d, set()))
        n2 = sum(c.values())
        nsup = n_supported(a, b)
        sig[nm] = {"nsp": nsp, "na": na, "p1": n1, "p2": n2,
                   "labels": labels, "sup": nsup,
                   "short": rw.get("short", 0),
                   "long": rw.get("long", 0)}
        print(f"{nm:9s} | {nsp:5d} | {na:4d} | "
              f"{rw.get('short', 0)}/{rw.get('long', 0)} | {n1:3d} | "
              f"{nsup}/{n2 - nsup} | {n2:4d} | {len(labels)}")

    ok = []
    ok.append(("D1 siddet_kontrast",
               sig["siddetli"]["p1"] > 5 * sig["normal"]["p1"]))
    ok.append(("D2 temsil_sessiz_degil",
               all(sig[nm]["p2"] > 0 for _, _, nm in WINDOWS)))
    ok.append(("D3 B-surus_kanit",
               sig["kurak"]["p1"] == 0 and sig["kurak"]["p2"] > 0))
    sets = [frozenset(sig[nm]["labels"]) for _, _, nm in WINDOWS]
    ok.append(("D4 imza_cesitliligi",
               len(set(sets)) > 1
               and sum(len(s) for s in sets) >= 12))
    tot_sup = sum(sig[nm]["sup"] for _, _, nm in WINDOWS)
    tot_p2 = sum(sig[nm]["p2"] for _, _, nm in WINDOWS)
    ok.append(("D5 cift-surus",
               tot_sup > 0 and tot_p2 - tot_sup > 0))
    bad = [k for k, v in ok if not v]
    for k, v in ok:
        print(f"  {'OK' if v else 'BATTI'} {k}")
    if bad:
        raise SystemExit(f"BATTI: {bad}")
    print(f"soma-destegi toplami: {tot_sup}/{tot_p2} "
          f"(A-destekli/saf-B)")
    print("HUKUM: her kosul ayri imza (P1 orani, P2 dagilimi, etiket "
          "kumesi farkli); kuraklik P1'siz temsil (B-surus).")
    print("OZET-COND-SWEEP: " + " ".join(k for k, _ in ok))


if __name__ == "__main__":
    main()
