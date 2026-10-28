"""Interaction / synergy testi (§9.75).

Soru: post bilgisi varken A'nin ek bilgisi ne? A varken post'unki?
Yontem (bilgi-kuramsal, ogrenmesiz, model CALISMAZ):
- Birim: ayni 175 k=3 pencere. X_post = baskin post (pencere-ici
  olay sayisinda max; esitlikte kucuk id), X_A = 3-gun A-varlik
  paterni (gun basina A-gecmisli olay var/yok), Y = 6 kosul.
- Olcu: Miller-Madow duzeltmeli I(Post;Y), I(A;Y), I(Post,A;Y);
  etkilesim bilgisi II = I(Post,A;Y) - I(Post;Y) - I(A;Y)
  (II>0 sinerji, II<0 yedeklilik) + kosullu terimler
  I(A;Y|Post), I(Post;Y|A).
- Anlamlilik: A-sutunu permute (n=2000, tohum 99) -> p degeri.
  Karar permutasyondan cikar (yanlilik payi sifirlanir).
- Tamamlayici: gecirgenlik-onemi — post+A tahmincisinde A-kanali
  (30 perm) ve post-kumesi (30 perm) karistirilinca dogruluk
  dususu: dA|post, dPost|A.

Kapilar (S1-S2): determinizm, permutasyon gecerliligi.
"""
import math
import os
import random
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import validate_inference as B  # noqa: E402 (donmus, okunur)

N_PERM = 2000
SEED = 99
N_PI = 30


def features(events):
    by_day = {}
    for r in events:
        by_day.setdefault(int(r["tick"]) // 50, []).append(r)
    out = []
    for a, b, nm in B.WINDOWS:
        for s in range(a, b - 3 + 1):
            cnt = Counter()
            apat = []
            any_ev = False
            for x in range(s, s + 3):
                evs = by_day.get(x, [])
                any_ev = any_ev or bool(evs)
                for r in evs:
                    cnt[int(r["post_id"])] += 1
                apat.append(1 if any(int(r["a0lag"]) >= 0
                                     or int(r["a1lag"]) >= 0
                                     for r in evs) else 0)
            if not any_ev:
                continue
            dom = min([p for p, c in cnt.items()
                       if c == max(cnt.values())])
            out.append({"s": s, "post": dom, "A": tuple(apat),
                        "label": nm})
    return out


def mi(xs, ys):
    n = len(xs)
    j = Counter(zip(xs, ys))
    mx = Counter(xs)
    my = Counter(ys)
    h = 0.0
    for (x, y), c in j.items():
        h += (c / n) * math.log2((c * n) / (mx[x] * my[y]))
    # Miller-Madow (bit): yanli duzeltme.
    mxy = len(j)
    mxn, myn = len(mx), len(my)
    h -= (mxy - mxn - myn + 1) / (2 * n * math.log(2))
    return h


def interaction(rows):
    post = [r["post"] for r in rows]
    A = [r["A"] for r in rows]
    y = [r["label"] for r in rows]
    i_p = mi(post, y)
    i_a = mi(A, y)
    i_pa = mi(list(zip(post, A)), y)
    ii = i_pa - i_p - i_a
    return i_p, i_a, i_pa, ii, i_pa - i_p, i_pa - i_a


def main():
    d = B.load()
    rows = features(d["events"])
    assert len(rows) == 175, f"pencere sayisi {len(rows)}"
    i_p, i_a, i_pa, ii, a_given_post, p_given_a = interaction(rows)
    print(f"I(post;Y)={i_p:.3f} I(A;Y)={i_a:.3f} "
          f"I(post,A;Y)={i_pa:.3f}")
    print(f"II={ii:+.3f} (sinerji>0 / yedeklilik<0)")
    print(f"I(A;Y|post)={a_given_post:.3f} "
          f"I(post;Y|A)={p_given_a:.3f}")

    rng = random.Random(SEED)
    Aval = [r["A"] for r in rows]
    ge = 0
    for _ in range(N_PERM):
        prm = Aval[:]
        rng.shuffle(prm)
        cfg = [{"post": r["post"], "A": a} for r, a in zip(rows, prm)]
        _, _, i2, ii2, _, _ = interaction(
            [{**c, "label": r["label"]} for c, r in zip(cfg, rows)])
        ge += (ii2 >= ii)
    pval = (ge + 1) / (N_PERM + 1)
    print(f"permutasyon: {ge}/{N_PERM} >= gozlenen -> p={pval:.4f}")

    # Gecirgenlik-onemi: donmus post+A tahmincisinde kanal karistir.
    wins = B.build(d["events"])

    def loo_acc(ws):
        cm, viol = B.infer(ws)
        tot = sum(cm.values())
        ok = sum(v for (t, p), v in cm.items() if t == p)
        assert viol == 0
        return ok / tot

    base_acc = loo_acc(wins)
    assert abs(base_acc - 0.554) < 0.005, "baseline tutmadi"
    rng2 = random.Random(7)
    drops = {}
    for ch in ("A", "post"):
        tot = 0.0
        for _ in range(N_PI):
            bag = []
            for w in wins:
                bag.append(tuple(sorted(sg["a"] if ch == "A"
                                        else sg["posts"])
                                 for sg in w["seq"]))
            rng2.shuffle(bag)
            ws2 = []
            for w, bch in zip(wins, bag):
                sq = []
                for sg, bc in zip(w["seq"], bch):
                    ns = {"posts": set(sg["posts"]),
                          "blines": set(sg["blines"]),
                          "a": set(sg["a"])}
                    if ch == "A":
                        ns["a"] = set(bc)
                    else:
                        ns["posts"] = set(bc)
                    sq.append(ns)
                ws2.append({"s": w["s"], "seq": tuple(sq),
                            "label": w["label"]})
            tot += loo_acc(ws2)
        drops[ch] = base_acc - tot / N_PI
    print(f"gecirgenlik-dususu: dA|post={drops['A']:+.3f} "
          f"dPost|A={drops['post']:+.3f} (30'ar perm, taban 0.554)")

    chk = [("S1 deterministik",
            interaction(rows)[3] == ii),
           ("S2 permutasyon-gecerli",
            0.0 <= pval <= 1.0 and N_PERM == 2000)]
    bad = [x for x, v in chk if not v]
    for x, v in chk:
        print(f"  {'OK' if v else 'BATTI'} {x}")
    if bad:
        raise SystemExit(f"BATTI: {bad}")
    print(f"OZET-SYNERGY: {' '.join(x for x, _ in chk)} "
          f"II={ii:+.3f} p={pval:.4f}")


if __name__ == "__main__":
    main()
