"""§9.81 — Representation ceiling diagnostic.

Soru: sinif bilgisi, herhangi ogrenilmis agirlik ONCESINDE
temsilin icinde var mi? Darbogaz temsil mi, metrik/cikarim mi?
Donmus 175 pencere (k=3), model/kural DEGISMEZ, accuracy-ayari
YOK (metrik kumesi onceden sabit, secim iddiasi yok).

Olcu:
- exact-signature class purity (tam dizi-imzasi bazinda sinif
  dagilimi; agirliksiz, metrikten bagimsiz tavan gostergesi).
- Ogrenmesiz sabit metriklerle LOO: frozen-assoc (0.5/0.3/0.2,
  referans), uniform-Jaccard (1/3,1/3,1/3), Hamming (66-bit),
  exact-match (kapsama + kapsanan-dogruluk).
- Within/between-class uzaklik (her metrik).
- Confusion (frozen referans + en-ayirt-edici sabit metrik).

Kapilar (C1-C3): determinizm, donmus-sadakat (0.554 birebir),
sizintisiz.
"""
import sys
from collections import Counter

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import validate_inference as B  # noqa: E402 (donmus)
from sim.assoc import _jaccard  # noqa: E402

N_FEAT = 22


def flatsig(seq):
    bits = []
    for sg in seq:
        bits += [1 if k in sg["posts"] else 0 for k in range(10)]
        bits += [1 if k in sg["blines"] else 0 for k in range(10)]
        bits += [1 if k in sg["a"] else 0 for k in (0, 1)]
    return bits


def seqkey(seq):
    return tuple((frozenset(s["posts"]), frozenset(s["blines"]),
                  frozenset(s["a"])) for s in seq)


def wsim(wp, wb, wa):
    def f(a, b):
        return (wp * _jaccard(a["posts"], b["posts"])
                + wb * _jaccard(a["blines"], b["blines"])
                + wa * _jaccard(a["a"], b["a"]))
    return f


def seq_mean(sim):
    def f(sa, sb):
        return sum(sim(x, y) for x, y in zip(sa, sb)) / len(sa)
    return f


def ham_sim(bits_a, bits_b):
    d = sum(1 for x, y in zip(bits_a, bits_b) if x != y)
    return 1.0 - d / len(bits_a)


METRICS = {
    "frozen-assoc": None,  # B.seq_sim (referans)
    "uniform": None,
    "hamming": None,
    "exact": None,
}


def loo(wins, sim):
    cm = Counter()
    for i, w in enumerate(wins):
        best, bs = None, -1.0
        for j, o in enumerate(wins):
            if i == j:
                continue
            if not (o["s"] + 3 <= w["s"] or w["s"] + 3 <= o["s"]):
                continue
            v = sim(w, o)
            if v > bs:
                best, bs = o["label"], v
        cm[(w["label"], best)] += 1
    return cm


def main():
    d = B.load()
    wins = B.build(d["events"])
    for w in wins:
        w["flat"] = flatsig(w["seq"])
    uni = seq_mean(wsim(1 / 3, 1 / 3, 1 / 3))
    sims = {
        "frozen-assoc": lambda w, o: B.seq_sim(w["seq"], o["seq"]),
        "uniform": lambda w, o: uni(w["seq"], o["seq"]),
        "hamming": lambda w, o: ham_sim(w["flat"], o["flat"]),
        "exact": lambda w, o: 1.0 if seqkey(w["seq"]) == seqkey(
            o["seq"]) else 0.0,
    }
    # Purity (metrikten bagimsiz).
    groups = {}
    for w in wins:
        groups.setdefault(seqkey(w["seq"]), []).append(w["label"])
    print(f"distinct dizi-imzasi: {len(groups)}/175")
    pure = sum(1 for v in groups.values() if len(set(v)) == 1)
    cov = sum(len(v) for v in groups.values() if len(set(v)) == 1)
    wpure = sum(max(Counter(v).values()) for v in groups.values())
    print(f"saf-imza: {pure}/{len(groups)} imza, kapsama {cov}/175, "
          f"agirlikli saflik={wpure / 175:.3f}")
    # Sinif-paylasimli imza ornegi (en kalabalik karisik 3).
    mixed = sorted(((len(v), k, Counter(v)) for k, v in groups.items()
                    if len(set(v)) > 1), reverse=True)[:3]
    for n, k, c in mixed:
        print(f"  karisik x{n}: {dict(c)}")
    res = {}
    for nm, sim in sims.items():
        if nm == "exact":
            # Kapsama: aynisindan en az bir ortusmesiz aday var mi?
            hit = tot = 0
            for i, w in enumerate(wins):
                cands = [o for j, o in enumerate(wins) if j != i and
                         (o["s"] + 3 <= w["s"] or w["s"] + 3 <= o["s"])
                         and seqkey(o["seq"]) == seqkey(w["seq"])]
                if not cands:
                    continue
                tot += 1
                hit += (cands[0]["label"] == w["label"])
            print(f"exact: kapsama {tot}/175, kapsanan-dogruluk="
                  f"{hit}/{tot}={hit / tot:.3f}" if tot else
                  "exact: kapsama 0")
            res[nm] = (None, tot)
            continue
        cm = loo(wins, sim)
        tot = sum(cm.values())
        ok = sum(v for (t, p), v in cm.items() if t == p)
        res[nm] = (cm, tot)
        print(f"{nm}: {ok}/{tot}={ok / tot:.3f}")
    # Within/between (frozen + hamming).
    for nm in ("frozen-assoc", "hamming"):
        sim = sims[nm]
        wit, bet = [], []
        for i in range(len(wins)):
            for j in range(i + 1, len(wins)):
                v = sim(wins[i], wins[j])
                (wit if wins[i]["label"] == wins[j]["label"]
                 else bet).append(v)
        import statistics as st
        print(f"  {nm}: within={st.mean(wit):.3f} "
              f"between={st.mean(bet):.3f}")
    cm_f = res["frozen-assoc"][0]
    B.show(cm_f, "Ceiling — frozen-assoc confusion (referans):")
    cm_u = res["uniform"][0]
    B.show(cm_u, "Ceiling — uniform-Jaccard confusion:")
    cm0, _ = B.infer(wins)
    chk = [("C1 deterministik",
            loo(wins, sims["uniform"]) == cm_u),
           ("C2 donmus-sadakat", cm_f == cm0),
           ("C3 sizintisiz",
            all(sum(c.values()) == 175 for c, _ in
                [v for v in res.values() if v[0] is not None]))]
    bad = [x for x, v in chk if not v]
    for x, v in chk:
        print(f"  {'OK' if v else 'BATTI'} {x}")
    if bad:
        raise SystemExit(f"BATTI: {bad}")
    print("OZET-REPR-CEIL: " + " ".join(x for x, _ in chk))


if __name__ == "__main__":
    main()
