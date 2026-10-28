"""§9.83 — Metric limitation diagnostic.

Soru: exact-match tavaninin altinda kalan orneklerde bilgi mevcut
ama mevcut metrik tarafindan kullanilamiyor mu? Temsil DONMUS
(degisiklik YOK); yalniz okuma geometrisi degisir. Ogrenme YOK,
SECIM YOK (6 kol onceden kayitli, max-secimi yapilmaz).

Kollar (hepsi ayni 175 pencere, ayni LOO, ilk-bulunan esitlik):
- exact: tam-eslesme (abstain; referans).
- hamming: 66-bit duz vektor uzakligi.
- jaccard-uniform: gun-ortalamali es-agirlikli Jaccard.
- jaccard-frozen: 0.5/0.3/0.2 (referans, §9.68).
- rotation-max: 3 devirli-hizalama uzerinden max (faz-duyarsiz
  sira geometrisi; parametresiz).
- count-cosine: 22-boyutlu sayim vektorunde kosinus (post
  olay-sayisi + B-hatti aktif-gun + A aktif-gun; buyukluk
  bilgisini kumeler disinda okur, temsili degistirmez).

Olcu (kol-basina): accuracy, confusion, esitlik, kurak<->normal.
Eger hepsi ~0.50-0.58 bandinda takilirsa: temsil %92 saf ama
geometri global duzen uretmiyor → sorun organizasyonda.

Kapilar (E1-E3): determinizm, donmus-sadakat (frozen 0.554 +
exact 64/0.578), sizintisiz.
"""
import math
import sys
from collections import Counter

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import validate_inference as B  # noqa: E402 (donmus)
from sim.assoc import _jaccard, similarity  # noqa: E402


def flatbits(seq):
    b = []
    for sg in seq:
        b += [1 if k in sg["posts"] else 0 for k in range(10)]
        b += [1 if k in sg["blines"] else 0 for k in range(10)]
        b += [1 if k in sg["a"] else 0 for k in (0, 1)]
    return b


def seqkey(seq):
    return tuple((frozenset(s["posts"]), frozenset(s["blines"]),
                  frozenset(s["a"])) for s in seq)


def wsim(wp, wb, wa):
    def f(a, b):
        return (wp * _jaccard(a["posts"], b["posts"])
                + wb * _jaccard(a["blines"], b["blines"])
                + wa * _jaccard(a["a"], b["a"]))
    return f


def countvec(seq, events_by_day, s):
    pc = Counter()
    bc = Counter()
    ac = Counter()
    for x in range(s, s + 3):
        for r in events_by_day.get(x, []):
            pc[int(r["post_id"])] += 1
            for i, ch in enumerate(r["bwin"]):
                if ch == "1":
                    bc[i] += 1
            if int(r["a0lag"]) >= 0:
                ac[0] += 1
            if int(r["a1lag"]) >= 0:
                ac[1] += 1
    return ([pc[k] for k in range(10)] + [bc[k] for k in range(10)]
            + [ac[0], ac[1]])


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 1.0 if na == nb else 0.0
    return dot / (na * nb)


def loo(wins, sim):
    cm, ties = Counter(), 0
    for i, w in enumerate(wins):
        best, cands = -1.0, []
        for j, o in enumerate(wins):
            if i == j:
                continue
            if not (o["s"] + 3 <= w["s"] or w["s"] + 3 <= o["s"]):
                continue
            v = sim(w, o)
            if v > best:
                best, cands = v, [o["label"]]
            elif v == best and o["label"] not in cands:
                cands.append(o["label"])
        if len(cands) > 1:
            ties += 1
        cm[(w["label"], cands[0])] += 1
    return cm, ties


def main():
    d = B.load()
    wins = B.build(d["events"])
    by_day = {}
    for r in d["events"]:
        by_day.setdefault(int(r["tick"]) // 50, []).append(r)
    for w in wins:
        w["flat"] = flatbits(w["seq"])
        w["cnt"] = countvec(w["seq"], by_day, w["s"])
    uni = wsim(1 / 3, 1 / 3, 1 / 3)

    def rotmax(sa, sb):
        best = -1.0
        for k in range(3):
            rot = sb[k:] + sb[:k]
            v = sum(similarity(x, y) for x, y in zip(sa, rot)) / 3
            best = max(best, v)
        return best

    sims = {
        "hamming": lambda w, o: 1.0 - sum(
            1 for x, y in zip(w["flat"], o["flat"])
            if x != y) / len(w["flat"]),
        "jaccard-uniform": lambda w, o: sum(
            uni(x, y) for x, y in zip(w["seq"], o["seq"])) / 3,
        "jaccard-frozen": lambda w, o: B.seq_sim(w["seq"], o["seq"]),
        "rotation-max": lambda w, o: rotmax(w["seq"], o["seq"]),
        "count-cosine": lambda w, o: cosine(w["cnt"], o["cnt"]),
    }
    accs = {}
    for nm, sim in sims.items():
        cm, ties = loo(wins, sim)
        tot = sum(cm.values())
        ok = sum(v for (t, p), v in cm.items() if t == p)
        accs[nm] = (cm, ties, ok / tot)
        B.show(cm, f"{nm}:")
        print(f"  acc={ok}/{tot}={ok / tot:.3f} esitlik={ties} "
              f"D->N={cm.get(('kurak', 'normal'), 0)}/28 "
              f"N->D={cm.get(('normal', 'kurak'), 0)}/25")
    lo = min(a for _, _, a in accs.values())
    hi = max(a for _, _, a in accs.values())
    print(f"BANT: [{lo:.3f},{hi:.3f}] (5 geometri, exact-haric)")
    cm0, _ = B.infer(wins)
    chk = [("E1 deterministik",
            loo(wins, sims["hamming"])[0] == accs["hamming"][0]),
           ("E2 donmus-sadakat", accs["jaccard-frozen"][0] == cm0),
           ("E3 sizintisiz",
            all(sum(c.values()) == 175 for c, _, _ in
                accs.values()))]
    bad = [x for x, v in chk if not v]
    for x, v in chk:
        print(f"  {'OK' if v else 'BATTI'} {x}")
    if bad:
        raise SystemExit(f"BATTI: {bad}")
    print("OZET-METRIC-LIMIT: " + " ".join(x for x, _ in chk))


if __name__ == "__main__":
    main()
