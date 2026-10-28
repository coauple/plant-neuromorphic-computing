"""§9.79 — Quadratic Monte Carlo characterization.

Sabitler: donmus temsil, donmus protokol (175 sorgu, sizintisiz
LOO), quadratic formulu DEGISMEZ (sabitler donmus modulden),
LTD YOK, normalizasyon YOK, metrik ayni (learned_sim import).

Degisen TEK sey: cevrimici deneme SIRASI. Kanonik sira (pencere
duzeni) + 4 karisik sira (tohum 11/22/33/44) = 5 MC kosusu.
Soru: kural ayni cekiciye mi yakinsiyor (convergence), siraya gore
dagiliyor mu (divergence)? Tohum-varyansi ne?

Olcu (kosu-basina): accuracy, confusion, agirlik max/mean/min,
top10-pay, unique bigram, doygunluk-orani (esitlik-kararli sorgu
payi); kosular-arasi: tahmin-oybirligi, agirlik-kosinus, seed
varyansi (acc std + sinif-recall std).

Kapilar (M1-M3): determinizm, kanonik-sadakat (0.400 birebir),
sizintisiz.
"""
import math
import random
import sys
from collections import Counter

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import validate_inference as B  # noqa: E402 (donmus)
import validate_quadratic_assoc as Q  # noqa: E402 (donmus)

SEEDS = (11, 22, 33, 44)


def trials(ref_seqs, rng=None):
    out = []
    for sq in ref_seqs:
        days = [Q.feat_list(sg) for sg in sq]
        for t in range(len(days) - 1):
            pre, post = days[t], days[t + 1]
            if not pre or not post:
                continue
            out.append((pre, post))
    if rng is not None:
        rng.shuffle(out)
    return out


def learn_ordered(ref_seqs, rng=None):
    w = {}
    for pre, post in trials(ref_seqs, rng):
        for f in pre:
            for g in post:
                wf = w.get((f, g), 0.0)
                s = 1.0 - (wf / Q.W_MAX) ** 2
                w[(f, g)] = wf + Q.ETA * (1.0 / Q.RATE) * \
                    (4.0 / Q.RATE ** 2) * s
    return w


def run(wins, rng=None):
    cm, preds, ties = Counter(), [], 0
    for i, w in enumerate(wins):
        refs = [o for j, o in enumerate(wins) if j != i and
                (o["s"] + 3 <= w["s"] or w["s"] + 3 <= o["s"])]
        Wq = learn_ordered([o["seq"] for o in refs], rng)
        best, cands = -1.0, []
        for o in refs:
            v = Q.learned_sim(w["seq"], o["seq"], Wq)
            if v > best:
                best, cands = v, [o["label"]]
            elif v == best and o["label"] not in cands:
                cands.append(o["label"])
        if len(cands) > 1:
            ties += 1
        cm[(w["label"], cands[0])] += 1
        preds.append(cands[0])
    return cm, preds, ties


def wstats(W):
    vals = sorted(W.values())
    tot = sum(vals)
    return {"n": len(vals), "min": vals[0], "mean": tot / len(vals),
            "max": vals[-1],
            "top10": sum(vals[-10:]) / tot if tot else 0.0}


def main():
    d = B.load()
    wins = B.build(d["events"])
    # Kanonik: karismamis sira (donmus-formul sadakati).
    cm0, pr0, ties0 = run(wins, None)
    acc0 = B.show(cm0, "MC kanonik-sira (formul-sadakat):")
    print(f"  esitlik-orani={ties0}/175 "
          f"kurak->N={cm0.get(('kurak', 'normal'), 0)}/28")
    W0 = learn_ordered([w["seq"] for w in wins], None)
    s0 = wstats(W0)
    print(f"  agirlik: n={s0['n']} min={s0['min']:.2e} "
          f"mean={s0['mean']:.2e} max={s0['max']:.2e} "
          f"top10={s0['top10']:.3f}")

    accs, cms, predlists, tieNs, wcos = [], [], [], [], []
    allseq = [w["seq"] for w in wins]
    for sd in SEEDS:
        cm, pr, ties = run(wins, random.Random(sd))
        tot = sum(cm.values())
        ok = sum(v for (t, p), v in cm.items() if t == p)
        accs.append(ok / tot)
        cms.append(cm)
        predlists.append(pr)
        tieNs.append(ties)
        Ws = learn_ordered(allseq, random.Random(sd + 1000))
        dot = sum(W0.get(k, 0.0) * v for k, v in Ws.items())
        n0 = math.sqrt(sum(v * v for v in W0.values()))
        ns = math.sqrt(sum(v * v for v in Ws.values()))
        wcos.append(dot / (n0 * ns))
        print(f"  tohum {sd}: acc={ok}/{tot}={ok / tot:.3f} "
              f"esitlik={ties} kurak->N="
              f"{cm.get(('kurak', 'normal'), 0)}/28")
    for k, cm in zip(SEEDS, cms):
        B.show(cm, f"MC tohum {k} confusion:")
    agree = sum(all(p == pr0[i] for p in
                    [pl[i] for pl in predlists])
                for i in range(175)) / 175
    import statistics as st
    print(f"tahmin-oybirligi(5/5): {agree:.3f}; "
          f"agirlik-kosinus: min={min(wcos):.4f}")
    print(f"seed-varyansi: acc mean={st.mean(accs):.3f} "
          f"std={st.pstdev(accs):.4f} aralik="
          f"[{min(accs):.3f},{max(accs):.3f}]")
    for t in B.ORDER:
        rs = []
        for cm in cms:
            tot = sum(v for (tt, _), v in cm.items() if tt == t)
            rs.append(cm.get((t, t), 0) / tot)
        print(f"  recall-std {t:9s} {st.pstdev(rs):.4f}")
    chk = [("M1 deterministik",
            run(wins, random.Random(11))[0] == cms[0]),
           ("M2 kanonik-sadakat", abs(acc0 - 0.400) < 1e-9),
           ("M3 sizintisiz",
            all(sum(c.values()) == 175 for c in [cm0] + cms))]
    bad = [x for x, v in chk if not v]
    for x, v in chk:
        print(f"  {'OK' if v else 'BATTI'} {x}")
    if bad:
        raise SystemExit(f"BATTI: {bad}")
    print("OZET-QUAD-MC: " + " ".join(x for x, _ in chk))


if __name__ == "__main__":
    main()
