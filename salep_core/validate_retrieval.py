"""§9.82 — Retrieval diagnostic (ogrenmesiz, ayarsiz).

Soru: nadir-ama-saf imzalari majority-attraction olmadan
dogrudan kullanirsak temsil tavanina (0.92) ne kadar
yaklasiriz? YENI MODEL DEGIL — §9.81 darboğazini sinif
dengesizligi/komsuluk-yogunlugu acisindan dogrulama.

Kollar (hepsi ayni 175 pencere, donmus temsil, ayni LOO,
ogrenme YOK, ayar YOK):
- exact: tam-eslesme (kapsama-disi abstain; 0.578 referansi).
- prior-neutral: sinif-basina en-iyi (6 aday, ham benzerlik).
- rarity: global argmax sim x (1/imza-sikligi) — seyrek imza
  agirlikli (formul sabit, ayar yok).
- balanced: global argmax sim x N/(6*N_sinif) (formul sabit).

Olcu (kol-basina): accuracy, confusion, sinif-recall,
kurak<->normal, esitlik-sayisi.

Kapilar (D1-D3): determinizm, exact-sadakat (64/175 + 0.578),
sizintisiz.
"""
import sys
from collections import Counter

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import validate_inference as B  # noqa: E402 (donmus)


def seqkey(seq):
    return tuple((frozenset(s["posts"]), frozenset(s["blines"]),
                  frozenset(s["a"])) for s in seq)


def refs_of(wins, i, w):
    return [o for j, o in enumerate(wins) if j != i and
            (o["s"] + 3 <= w["s"] or w["s"] + 3 <= o["s"])]


def argmax_first(scored):
    best, cands = -1.0, []
    for v, l in scored:
        if v > best:
            best, cands = v, [l]
        elif v == best and l not in cands:
            cands.append(l)
    return cands[0], len(cands) > 1


def run_exact(wins):
    cm, ties, cov, hit = Counter(), 0, 0, 0
    for i, w in enumerate(wins):
        cands = [o for o in refs_of(wins, i, w)
                 if seqkey(o["seq"]) == seqkey(w["seq"])]
        if not cands:
            continue
        cov += 1
        hit += (cands[0]["label"] == w["label"])
        cm[(w["label"], cands[0]["label"])] += 1
    return cm, ties, (cov, hit)


def run_prior_neutral(wins):
    cm, ties = Counter(), 0
    for i, w in enumerate(wins):
        per = {}
        for o in refs_of(wins, i, w):
            v = B.seq_sim(w["seq"], o["seq"])
            if o["label"] not in per or v > per[o["label"]][0]:
                per[o["label"]] = (v, o["label"])
        lab, t = argmax_first(list(per.values()))
        ties += t
        cm[(w["label"], lab)] += 1
    return cm, ties, None


def run_rarity(wins):
    freq = Counter(seqkey(w["seq"]) for w in wins)
    cm, ties = Counter(), 0
    for i, w in enumerate(wins):
        scored = [(B.seq_sim(w["seq"], o["seq"])
                   / freq[seqkey(o["seq"])], o["label"])
                  for o in refs_of(wins, i, w)]
        lab, t = argmax_first(scored)
        ties += t
        cm[(w["label"], lab)] += 1
    return cm, ties, None


def run_balanced(wins):
    ncls = Counter(w["label"] for w in wins)
    n = len(wins)
    wt = {l: n / (6 * c) for l, c in ncls.items()}
    cm, ties = Counter(), 0
    for i, w in enumerate(wins):
        scored = [(B.seq_sim(w["seq"], o["seq"]) * wt[o["label"]],
                   o["label"]) for o in refs_of(wins, i, w)]
        lab, t = argmax_first(scored)
        ties += t
        cm[(w["label"], lab)] += 1
    return cm, ties, None


def show(name, cm, ties, extra=""):
    tot = sum(cm.values())
    ok = sum(v for (t, p), v in cm.items() if t == p)
    B.show(cm, name)
    kd = cm.get(("kurak", "normal"), 0)
    dk = cm.get(("normal", "kurak"), 0)
    kt = sum(v for (t, _), v in cm.items() if t == "kurak")
    print(f"  dogruluk={ok}/{tot}={ok / tot:.3f} esitlik={ties} "
          f"D->N={kd}/{kt} N->D={dk}/25{extra}")
    return ok / tot


def main():
    d = B.load()
    wins = B.build(d["events"])
    cm_e, t_e, (cov, hit) = run_exact(wins)
    a_e = show("Exact-match (abstain):", cm_e, t_e,
               f" kapsama={cov}/175 kapsanan={hit}/{cov}="
               f"{hit / cov:.3f}")
    cm_p, t_p, _ = run_prior_neutral(wins)
    a_p = show("Prior-neutral (sinif-basina en-iyi):", cm_p, t_p)
    cm_r, t_r, _ = run_rarity(wins)
    a_r = show("Rarity-weighted (1/imza-sikligi):", cm_r, t_r)
    cm_b, t_b, _ = run_balanced(wins)
    a_b = show("Class-balanced (N/6N_c):", cm_b, t_b)
    chk = [("D1 deterministik",
            run_prior_neutral(wins)[0] == cm_p
            and run_rarity(wins)[0] == cm_r
            and run_balanced(wins)[0] == cm_b),
           ("D2 exact-sadakat",
            cov == 64 and abs(hit / cov - 0.578) < 0.005),
           ("D3 sizintisiz",
            all(sum(c.values()) == s for c, s in
                [(cm_p, 175), (cm_r, 175), (cm_b, 175)]))]
    bad = [x for x, v in chk if not v]
    for x, v in chk:
        print(f"  {'OK' if v else 'BATTI'} {x}")
    if bad:
        raise SystemExit(f"BATTI: {bad}")
    print(f"OZET-RETRIEVAL: {' '.join(x for x, _ in chk)} "
          f"exact={a_e:.3f} prior={a_p:.3f} rarity={a_r:.3f} "
          f"balanced={a_b:.3f}")


if __name__ == "__main__":
    main()
