"""Deney D — rate surrogate (§9.73).

Soru: temporal mimari, yalniz spike SAYISININ tasidigi bilgiden
fazlasini kullaniyor mu?
Yontem: AYNI 175 pencere (donmus build), ozellik yalniz 3-gun
sayi-vektoru (hat0, hat1) — maske-seviyesi (benzersiz tick).
OkLid 1-NN, ayni sizintisiz LOO. Sira bilgisi YOK. Model
CALISTIRILMAZ; mevcut artefaktlar okunur.

Kapilar (T1-T2): determinizm, sizintisiz.
"""
import csv
import math
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import validate_inference as B  # noqa: E402 (donmus, okunur)


def counts():
    c = {}
    with open(os.path.join(ROOT, "testb_spikes.csv")) as f:
        for row in csv.reader(f):
            if not row or not row[0].strip().lstrip("-").isdigit():
                continue
            d, l, t = map(int, row[:3])
            c.setdefault((d, l), set()).add(t)
    return c


def main():
    d = B.load()
    wins = B.build(d["events"])
    cc = counts()
    vec = {}
    for w in wins:
        c0 = sum(len(cc.get((x, 0), ())) for x in range(w["s"], w["s"] + 3))
        c1 = sum(len(cc.get((x, 1), ())) for x in range(w["s"], w["s"] + 3))
        vec[w["s"]] = (c0, c1)
    cm, viol = Counter(), 0
    for i, w in enumerate(wins):
        best, bd = None, None
        for j, o in enumerate(wins):
            if i == j:
                continue
            if not (o["s"] + 3 <= w["s"] or w["s"] + 3 <= o["s"]):
                continue
            a, b = vec[w["s"]], vec[o["s"]]
            dist = math.dist(a, b)
            if bd is None or dist < bd:
                best, bd = o["label"], dist
        if best is None:
            viol += 1
            continue
        cm[(w["label"], best)] += 1
    acc = B.show(cm, "Rate-surrogate (sayi-vektoru 1-NN, sirasiz):")
    kd = cm.get(("kurak", "normal"), 0)
    kt = sum(v for (t, _), v in cm.items() if t == "kurak")
    print(f"kurak->normal (rate): {kd}/{kt} "
          f"[temporal: 28/28; quadratic: 28/28]")
    print(f"dogruluk (rate): {acc:.3f} [temporal: 0.554]")
    cm2 = Counter(cm)
    chk = [("T1 deterministik", cm == cm2),
           ("T2 sizintisiz", viol == 0)]
    bad = [x for x, v in chk if not v]
    for x, v in chk:
        print(f"  {'OK' if v else 'BATTI'} {x}")
    if bad:
        raise SystemExit(f"BATTI: {bad}")
    print("OZET-RATE-SURR: " + " ".join(x for x, _ in chk)
          + f" acc={acc:.3f}")


if __name__ == "__main__":
    main()
