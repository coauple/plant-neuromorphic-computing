"""Deney H — metric hygiene (§9.77).

Donmus baseline + donmus quadratic AYNI skorla tekrar, ek:
esitlik-denetimi (her sorguda max-skoru paylasan farkli-etiketli
aday sayisi raporlanir; karar kurali sabit: ilk-bulunan).
Ayrica agirlik dagilimi + baskin-gecis payi (top-10 kutle/toplam).
Model/kural/baseline dosyalari DEGISMEZ (import + yerel LOO).
"""
import sys
from collections import Counter

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import validate_inference as B  # noqa: E402 (donmus)
import validate_quadratic_assoc as Q  # noqa: E402 (donmus)


def loo_audit(wins, sim_fn):
    # Karar kurali DONMUS ile birebir (katı-büyüklükte ilk-bulunan);
    # esitlikler YALNIZ raporlanir, karari degistirmez.
    cm, ties, tie_pairs = Counter(), 0, Counter()
    for i, w in enumerate(wins):
        best, cands = -1.0, []
        for j, o in enumerate(wins):
            if i == j:
                continue
            if not (o["s"] + 3 <= w["s"] or w["s"] + 3 <= o["s"]):
                continue
            v = sim_fn(w, o)
            if v > best:
                best, cands = v, [o["label"]]
            elif v == best and o["label"] not in cands:
                cands.append(o["label"])
        if len(cands) > 1:
            ties += 1
            tie_pairs[tuple(sorted(cands))] += 1
        cm[(w["label"], cands[0])] += 1
    return cm, ties, tie_pairs


def wdist(W):
    vals = sorted(W.values())
    tot = sum(vals)
    top10 = sum(vals[-10:])
    return {"n": len(vals), "min": vals[0], "max": vals[-1],
            "top10_share": top10 / tot if tot else 0.0}


def report(name, cm, ties, tie_pairs, wd=None):
    acc = B.show(cm, name)
    print(f"  esitlik-karari: {ties} sorgu "
          f"(ciftler: {dict(tie_pairs)})")
    if wd:
        print(f"  agirlik: n={wd['n']} min={wd['min']:.2e} "
              f"max={wd['max']:.2e} baskin-pay(top10)="
              f"{wd['top10_share']:.3f}")
    return acc


def main():
    d = B.load()
    wins = B.build(d["events"])
    cm_b, t_b, tp_b = loo_audit(wins, lambda w, o: B.seq_sim(
        w["seq"], o["seq"]))
    a_b = report("Baseline-1 + hijyen (karar kurali sabit):",
                 cm_b, t_b, tp_b)
    # Quadratic: sorgu-basina LOO ogrenme (§9.71 ile ayni).
    cm_q, t_q, tp_q = Counter(), 0, Counter()
    for i, w in enumerate(wins):
        refs = [o for j, o in enumerate(wins) if j != i and
                (o["s"] + 3 <= w["s"] or w["s"] + 3 <= o["s"])]
        Wq = Q.learn_weights([o["seq"] for o in refs])
        best, cands = -1.0, []
        for o in refs:
            v = Q.learned_sim(w["seq"], o["seq"], Wq)
            if v > best:
                best, cands = v, [o["label"]]
            elif v == best and o["label"] not in cands:
                cands.append(o["label"])
        if len(cands) > 1:
            t_q += 1
            tp_q[tuple(sorted(cands))] += 1
        cm_q[(w["label"], cands[0])] += 1
    Wall = Q.learn_weights([w["seq"] for w in wins])
    a_q = report("Quadratic + hijyen (donmus agirliklar):",
                 cm_q, t_q, tp_q, wdist(Wall))
    kd = cm_q.get(("kurak", "normal"), 0)
    print(f"kurak->normal: baseline "
          f"{cm_b.get(('kurak', 'normal'), 0)}/28, quadratic {kd}/28")
    cm0, viol0 = B.infer(wins)
    chk = [("H1 deterministik",
            loo_audit(wins, lambda w, o: B.seq_sim(
                w["seq"], o["seq"]))[0] == cm_b),
           ("H2 denetim-tam",
            sum(cm_b.values()) == sum(cm_q.values()) == 175),
           ("H3 donmus-sadakat",
            cm_b == cm0 and viol0 == 0)]
    bad = [x for x, v in chk if not v]
    for x, v in chk:
        print(f"  {'OK' if v else 'BATTI'} {x}")
    if bad:
        raise SystemExit(f"BATTI: {bad}")
    print(f"OZET-HYGIENE: {' '.join(x for x, _ in chk)} "
          f"base={a_b:.3f} quad={a_q:.3f}")


if __name__ == "__main__":
    main()
