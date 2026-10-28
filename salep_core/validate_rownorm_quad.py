"""Deney R — row-normalized quadratic (§9.78, LTD YOK).

Ayni protokol (§9.71): sorgu-basina etiketsiz LOO bigram ogrenme,
tek fark satir-normalizasyonu (rekabet): Wn(f,g) = W(f,g) /
toplam_g W(f,g'); bossa 0. Sik pre'nin kutlesi cok posta dagilir;
seyrek-ayirt-edici bigramlar gorece guclenir. Kural FORMULU
degismez (donmus learn_weights yeniden kullanilir); normalizasyon
metrik katmanindadir. Esitlik-denetimi dahili.

Rapor: confusion + accuracy + agirlik dagilimi + baskin-gecis payi.
"""
import sys
from collections import Counter

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import validate_inference as B  # noqa: E402 (donmus)
import validate_quadratic_assoc as Q  # noqa: E402 (donmus)


def rownorm(W):
    row = Counter()
    for (f, g), v in W.items():
        row[f] += v
    return {(f, g): (v / row[f] if row[f] else 0.0)
            for (f, g), v in W.items()}


def main():
    d = B.load()
    wins = B.build(d["events"])
    cm, ties, tie_pairs = Counter(), 0, Counter()
    for i, w in enumerate(wins):
        refs = [o for j, o in enumerate(wins) if j != i and
                (o["s"] + 3 <= w["s"] or w["s"] + 3 <= o["s"])]
        Wn = rownorm(Q.learn_weights([o["seq"] for o in refs]))
        best, cands = -1.0, []
        for o in refs:
            v = Q.learned_sim(w["seq"], o["seq"], Wn)
            if v > best:
                best, cands = v, [o["label"]]
            elif v == best and o["label"] not in cands:
                cands.append(o["label"])
        if len(cands) > 1:
            ties += 1
            tie_pairs[tuple(sorted(cands))] += 1
        cm[(w["label"], cands[0])] += 1
    acc = B.show(cm, "Row-normalized quadratic (LTD yok):")
    kd = cm.get(("kurak", "normal"), 0)
    kt = sum(v for (t, _), v in cm.items() if t == "kurak")
    print(f"kurak->normal (rownorm): {kd}/{kt}")
    print(f"esitlik-karari: {ties} sorgu "
          f"(ciftler: {dict(tie_pairs)})")
    Wall = rownorm(Q.learn_weights([w["seq"] for w in wins]))
    vals = sorted(Wall.values())
    tot = sum(vals)
    print(f"agirlik: n={len(vals)} min={vals[0]:.2e} "
          f"max={vals[-1]:.2e} baskin-pay(top10)="
          f"{sum(vals[-10:]) / tot:.3f}")
    chk = [("R1 deterministik", True),
           ("R2 sizintisiz", sum(cm.values()) == 175)]
    bad = [x for x, v in chk if not v]
    for x, v in chk:
        print(f"  {'OK' if v else 'BATTI'} {x}")
    if bad:
        raise SystemExit(f"BATTI: {bad}")
    print(f"OZET-ROWNORM: {' '.join(x for x, _ in chk)} "
          f"acc={acc:.3f} kurak-normal={kd}/{kt}")


if __name__ == "__main__":
    main()
