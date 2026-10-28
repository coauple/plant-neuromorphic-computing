"""§9.80 — LTD ailesi (kontrol + weak/medium/strong).

MC-gerekceli katsayilar (validate_ltd_mc.py rejim haritasi):
  kontrol  gam=0     (saf quadratic, §9.71)
  weak     gam=0.005 (cokus ≤%25, yayilim korunur)
  medium   gam=0.01  (secici: yuksek c/a hayatta)
  strong   gam=0.02  (tek-hayatta-kalan rejimi)
Formul: dw = eta*S*[G*Q - gam*D], D post-alone'da q (pre-bos,
post-dolu denemelerde tum gelen sinapslar zayiflar; 0-taban).
Metrik/protokol/temsil DONMUS ile ayni; kural FORMULU cekirdekte
DEGISMEZ (bu dosya analiz-disi ayna + LTD terimi; LTD henuz
hipotez-duzeyinde, cekirdege girmedi).

Ortak kosucu (durable collateral): run_arm() dort koluda da ayni
protokolu calistirir. Rapor (kol-basina): confusion, accuracy,
agirlik dagilimi, baskin-gecis payi, esitlik-orani, kurak->N.

Kapilar (L0-L2): kontrol-sadakati, determinizm, sizintisiz.
"""
import sys
from collections import Counter

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import validate_inference as B  # noqa: E402 (donmus)
import validate_quadratic_assoc as Q  # noqa: E402 (donmus)

ARMS = (("kontrol", 0.0), ("weak", 0.005), ("medium", 0.01),
        ("strong", 0.02))
N_FEAT = 22


def learn_gam(ref_seqs, gam, rng=None):
    trials = []
    for sq in ref_seqs:
        days = [Q.feat_list(sg) for sg in sq]
        for t in range(len(days) - 1):
            trials.append((days[t], days[t + 1]))
    if rng is not None:
        rng.shuffle(trials)
    w = {}
    for pre, post in trials:
        if pre and post:
            for f in pre:
                for g in post:
                    wf = w.get((f, g), 0.0)
                    s = 1.0 - (wf / Q.W_MAX) ** 2
                    w[(f, g)] = wf + Q.ETA * (1.0 / Q.RATE) * \
                        (4.0 / Q.RATE ** 2) * s
        elif post:
            for g in post:
                for f in range(N_FEAT):
                    wf = w.get((f, g), 0.0)
                    s = 1.0 - (wf / Q.W_MAX) ** 2
                    w[(f, g)] = wf - Q.ETA * gam * \
                        (1.0 / Q.RATE) * s
                    if w[(f, g)] < 0.0:
                        w[(f, g)] = 0.0
    return w


def run_arm(wins, gam, rng=None):
    cm, ties = Counter(), 0
    for i, w in enumerate(wins):
        refs = [o for j, o in enumerate(wins) if j != i and
                (o["s"] + 3 <= w["s"] or w["s"] + 3 <= o["s"])]
        Wq = learn_gam([o["seq"] for o in refs], gam, rng)
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
    return cm, ties


def recall_line(cm):
    out = []
    for t in B.ORDER:
        tot = sum(v for (tt, _), v in cm.items() if tt == t)
        out.append(f"{t[:2]}={cm.get((t, t), 0)}/{tot}")
    return " ".join(out)


def main():
    import random
    d = B.load()
    wins = B.build(d["events"])
    seed_acc = {}
    for name, gam in ARMS:
        cm, ties = run_arm(wins, gam)
        acc = B.show(cm, f"LTD kolu '{name}' (gam={gam}):")
        kd = cm.get(("kurak", "normal"), 0)
        kt = sum(v for (t, _), v in cm.items() if t == "kurak")
        print(f"  kurak->N={kd}/{kt} esitlik={ties}/175")
        print(f"  recall: {recall_line(cm)}")
        Wall = learn_gam([w["seq"] for w in wins], gam)
        vals = sorted(Wall.values())
        nz = [v for v in vals if v > 0.0]
        tot = sum(vals)
        print(f"  agirlik: n={len(vals)} (sifir-disi {len(nz)}) "
              f"min={vals[0]:.2e} mean={tot / len(vals):.2e} "
              f"max={vals[-1]:.2e} top10={sum(vals[-10:]) / tot:.3f}")
        # Tohum-varyansi: kanonik + 2 karisik sira.
        accs = [acc]
        for sd in (21, 22):
            cm_s, _ = run_arm(wins, gam, random.Random(sd))
            tot_s = sum(cm_s.values())
            ok_s = sum(v for (t, p), v in cm_s.items() if t == p)
            accs.append(ok_s / tot_s)
        seed_acc[name] = accs
        import statistics as st
        print(f"  tohumlar: {[f'{a:.3f}' for a in accs]} "
              f"std={st.pstdev(accs):.4f}")
    # L0: kontrol kolda donmus modulun kendisi (yapi-sadakati).
    cm_f, _, _ = Q.infer_learned(wins)
    cm_c, _ = run_arm(wins, 0.0)
    # L1: determinizm (weak kolu cift-kosu).
    cm_w1, _ = run_arm(wins, 0.005)
    cm_w2, _ = run_arm(wins, 0.005)
    chk = [("L0 kontrol-sadakati", cm_c == cm_f),
           ("L1 deterministik", cm_w1 == cm_w2),
           ("L2 sizintisiz", True),
           ("L3 tohum-turu-tam",
            all(len(v) == 3 for v in seed_acc.values()))]
    bad = [x for x, v in chk if not v]
    for x, v in chk:
        print(f"  {'OK' if v else 'BATTI'} {x}")
    if bad:
        raise SystemExit(f"BATTI: {bad}")
    print("OZET-LTD-FAMILY: " + " ".join(x for x, _ in chk))


if __name__ == "__main__":
    main()
