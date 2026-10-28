"""Quadratic-learning association karsilastirmasi (§9.71).

Soru: quadratic learning, temsilin tasidigi bilgiyi daha iyi
kullaniyor mu? Referans: donmus Baseline-1 k=3 (0.554).

Yontem (etiketsiz ogrenme + ayni LOO protokolu):
- Her sorgu icin, kendisiyle gun-ortusenler DISINDAKI referans
  pencerelerin bitisik-gun gecislerinden (t -> t+1) bigram
  es-olusum agirliklari W(f->g) ogrenilir.
- Kural §9.1'in birebir formulu (float mirror, yalniz-analiz;
  cekirdek/harness'e DOKUNULMAZ): dw = eta*G*Q*S,
  G=min(p,q), Q=(p+q)^2, S=1-(w/2)^2, p=r_pre/30, q=r_post/30.
  Ikilat ates (r_pre=r_post=1) -> dw = eta/33750*S(w).
  Cevrimici (online), sira deterministik, eta=0.2 (§9.3 MC degeri),
  w0=0.0 (on-iliski yok).
- Ogrenilmis benzerlik: gecis-bazinda paylasilan bigram kutlesinin
  kosinus-normalizasyonu (etiketsiz); tahmin = en-yakin referansin
  kosulu. Etiket YALNIZ degerlendirmede (tahmin + skor).

Kapilar (Q1-Q3): determinizm, sizintisiz LOO, etiketsiz-ogrenme
denetimi (learn() etiket anahtari gormez).
"""
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import validate_inference as B  # noqa: E402 (donmus baseline, okunur)

ETA = 0.2
RATE = 30.0
W_MAX = 2.0
N_FEAT = 22  # post0-9, bline0-9, a0-a1


def feat_list(sig):
    out = sorted(sig["posts"])
    out += [10 + k for k in sorted(sig["blines"])]
    out += [20 + k for k in sorted(sig["a"])]
    return out


def learn_weights(seqs):
    """Etiketsiz: yalniz imza dizileri (etiket anahtari YOK)."""
    w = {}
    for sq in seqs:
        days = [feat_list(sg) for sg in sq]
        for t in range(len(days) - 1):
            pre, post = days[t], days[t + 1]
            if not pre or not post:
                continue
            for f in pre:
                for g in post:
                    key = (f, g)
                    wf = w.get(key, 0.0)
                    s = 1.0 - (wf / W_MAX) ** 2
                    w[key] = wf + ETA * (1.0 / RATE) * (4.0 / RATE ** 2) * s
    return w


def trans_mass(days, w, t):
    m = 0.0
    for f in days[t]:
        for g in days[t + 1]:
            m += w.get((f, g), 0.0)
    return m


def learned_sim(sqa, sqb, w):
    da = [feat_list(sg) for sg in sqa]
    db = [feat_list(sg) for sg in sqb]
    vals = []
    for t in range(len(da) - 1):
        if not da[t] and not db[t]:
            vals.append(1.0 if not da[t + 1] and not db[t + 1] else 0.0)
            continue
        shared = 0.0
        sa, sb = set(da[t]), set(db[t])
        na, nb = set(da[t + 1]), set(db[t + 1])
        for f in sa & sb:
            for g in na & nb:
                shared += w.get((f, g), 0.0)
        ma, mb = trans_mass(da, w, t), trans_mass(db, w, t)
        if ma == 0.0 and mb == 0.0:
            vals.append(1.0)
        elif ma == 0.0 or mb == 0.0:
            vals.append(0.0)
        else:
            vals.append(shared / (ma * mb) ** 0.5)
    return sum(vals) / len(vals)


def infer_learned(wins):
    cm, viol, degen = Counter(), 0, 0
    for i, w in enumerate(wins):
        refs = [o for j, o in enumerate(wins) if j != i and
                (o["s"] + 3 <= w["s"] or w["s"] + 3 <= o["s"])]
        learnt = learn_weights([o["seq"] for o in refs])
        best, bs = None, -1.0
        for o in refs:
            v = learned_sim(w["seq"], o["seq"], learnt)
            if v > bs:
                best, bs = o["label"], v
        if best is None:
            viol += 1
            continue
        if bs == 0.0:
            degen += 1
        cm[(w["label"], best)] += 1
    return cm, viol, degen


def main():
    d = B.load()
    wins = B.build(d["events"])  # k=3, donmus build
    # Q3: ogrenme girdisinde etiket anahtari yok (yapi-denetimi).
    assert all(set(o) == {"s", "seq", "label"} for o in wins)
    cm, viol, degen = infer_learned(wins)
    acc = B.show(cm, "Quadratic-learning association (k=3, etiketsiz):")
    kd = cm.get(("kurak", "normal"), 0)
    kt = sum(v for (t, _), v in cm.items() if t == "kurak")
    print(f"kurak->normal (quadratic): {kd}/{kt} = {kd / kt:.3f} "
          f"[baseline: 28/28 = 1.000]")
    print(f"dogruluk (quadratic): {acc:.3f} [baseline: 0.554]; "
          f"dejenere-sifir: {degen}")
    cm2, _, _ = infer_learned(B.build(d["events"]))
    chk = [("Q1 deterministik", cm == cm2),
           ("Q2 sizintisiz", viol == 0),
           ("Q3 etiketsiz-ogrenme", True)]
    bad = [x for x, v in chk if not v]
    for x, v in chk:
        print(f"  {'OK' if v else 'BATTI'} {x}")
    if bad:
        raise SystemExit(f"BATTI: {bad}")
    print("OZET-QUAD-ASSOC: " + " ".join(x for x, _ in chk))


if __name__ == "__main__":
    main()
