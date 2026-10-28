"""Inference Baseline-1 (§9.68): aptal nearest-sequence.

sorgu penceresi (3 gun, sira-koruyan: 3 gunluk imza dizisi)
  -> tum kosullarin gecmis pencereleri (kendisiyle gun-ortusenler
     haric)
  -> hizali gun-ortalamasi benzerlik (parametre YOK, ogrenme YOK)
  -> en yakin pencerenin kosulu = tahmin.

Soru: sensory representation kendi basina ne kadar bilgi tasiyor?
6 sinif (ara/test disarida): N normal, D kurak, S siddetli,
I sulama, R recovery, Y yaz. Cikti: 6x6 confusion + kurak->normal
hatti. Model/harness CALISTIRILMAZ, degistirilmez.

Calistirma: .venv/bin/python validate_inference.py
Kapilar (I1-I2): determinizm + sizinti-denetimi.
"""
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from validate_sensory_repr import WINDOWS, load  # noqa: E402
from sim.assoc import similarity  # noqa: E402

K = 3
ORDER = ["normal", "kurak", "siddetli", "sulama", "recovery", "yaz"]
SHORT = {"normal": "N", "kurak": "D", "siddetli": "S", "sulama": "I",
         "recovery": "R", "yaz": "Y"}


def day_sig(events):
    posts, bl, a = set(), set(), set()
    for r in events:
        posts.add(int(r["post_id"]))
        for i, ch in enumerate(r["bwin"]):
            if ch == "1":
                bl.add(i)
        if int(r["a0lag"]) >= 0:
            a.add(0)
        if int(r["a1lag"]) >= 0:
            a.add(1)
    return {"posts": posts, "blines": bl, "a": a}


def seq_sim(a, b):
    return sum(similarity(x, y) for x, y in zip(a, b)) / len(a)


def build(events):
    by_day = {}
    for r in events:
        by_day.setdefault(int(r["tick"]) // 50, []).append(r)
    wins = []
    for a, b, nm in WINDOWS:
        for s in range(a, b - K + 1):
            seq = tuple(day_sig(by_day.get(x, []))
                        for x in range(s, s + K))
            if not any(sg["posts"] for sg in seq):
                continue
            wins.append({"s": s, "seq": seq, "label": nm})
    return wins


def infer(wins):
    cm, viol = Counter(), 0
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
        # Aday gercekten ortusmesiz mi (denetim).
        cm[(w["label"], best)] += 1
    return cm, viol


def show(cm, title):
    print(title)
    print("        " + " ".join(f"{SHORT[c]:>4s}" for c in ORDER))
    tot = ok = 0
    for t in ORDER:
        row = [cm.get((t, p), 0) for p in ORDER]
        tot += sum(row)
        ok += cm.get((t, t), 0)
        print(f"akt {SHORT[t]} | " + " ".join(f"{v:4d}" for v in row))
    print(f"dogruluk: {ok}/{tot} = {ok / tot:.3f}")
    return ok / tot


def main():
    d = load()
    wins = build(d["events"])
    cm, viol = infer(wins)
    acc = show(cm, f"Baseline-1 (k={K}, sira-koruyan, ogrenmesiz):")
    kd = sum(cm.get(("kurak", "normal"), 0) for _ in [0])
    kt = sum(v for (t, _), v in cm.items() if t == "kurak")
    print(f"kurak->normal hatti: {kd}/{kt} "
          f"({kd / kt:.3f}) — arastirma hatti §9.68")
    cm2, _ = infer(build(d["events"]))
    chk = [("I1 deterministik", cm == cm2),
           ("I2 sizintisiz", viol == 0)]
    bad = [x for x, v in chk if not v]
    for x, v in chk:
        print(f"  {'OK' if v else 'BATTI'} {x}")
    if bad:
        raise SystemExit(f"BATTI: {bad}")
    print("OZET-INFER-1: " + " ".join(x for x, _ in chk))


if __name__ == "__main__":
    main()
