"""Temporal-window testi (§9.67): pencere boyu -> kosul ayrimi.

Hipotez: tek-gun snapshot'i yetersiz; pencere-ici sequence/toplam
daha anlamlidir. Pencereler k = 1/3/5/10/20 gun, kayar (adim 1),
etiket = merkez-gunun degerlendirme kosulu (yalniz analiz
anahtari; sim girdisine girmez). Sessiz pencereler disarida
(atesli-gun disipliniyle tutarli).

Olcu (her k): LOO dogruluk (sızıntısız: kendisiyle gun-ortusmeyen
pencereler arasindan en-yakin), siluet, within/between, confusion.
Model/harness CALISTIRILMAZ, degistirilmez.

Calistirma: .venv/bin/python validate_temporal_window.py
Kapilar (W0-W2): k=1 F2-tutarlilik, determinizm, sızıntı-denetimi.
Egri BÜLBÜ-vari raporlanir (monotonluk one-surulmez, olculur).
"""
import os
import statistics as _st
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from validate_sensory_repr import WINDOWS, eval_cond, load  # noqa: E402
from sim.assoc import similarity  # noqa: E402

KS = (1, 3, 5, 10, 20)
N_DAYS = 250


def windows_for(k, events):
    """k-gun kayar pencereler: (baslangic_gunu, imza, etiket)."""
    by_day = {}
    for r in events:
        by_day.setdefault(int(r["tick"]) // 50, []).append(r)
    out = []
    for s in range(0, N_DAYS - k + 1):
        label = eval_cond(s + k // 2)
        if label in ("test", "?"):
            continue
        posts, bl, a = set(), set(), set()
        for x in range(s, s + k):
            for r in by_day.get(x, []):
                posts.add(int(r["post_id"]))
                for i, ch in enumerate(r["bwin"]):
                    if ch == "1":
                        bl.add(i)
                if int(r["a0lag"]) >= 0:
                    a.add(0)
                if int(r["a1lag"]) >= 0:
                    a.add(1)
        if not posts:
            continue
        out.append({"s": s, "sig": {"posts": posts, "blines": bl,
                                    "a": a}, "label": label})
    return out


def metrics(wins):
    n = len(wins)
    sim = {}
    for i in range(n):
        for j in range(i + 1, n):
            s = similarity(wins[i]["sig"], wins[j]["sig"])
            sim[(i, j)] = sim[(j, i)] = s
    within, between = [], []
    for i in range(n):
        for j in range(i + 1, n):
            (within if wins[i]["label"] == wins[j]["label"]
             else between).append(sim[(i, j)])
    # Sizintisiz LOO: gun-ortusmeyen komsular.
    cm, ok, fb = Counter(), 0, 0
    for i, w in enumerate(wins):
        best, bs = None, -1.0
        si = w["s"]
        for j, o in enumerate(wins):
            if i == j:
                continue
            if not (o["s"] + o["k"] <= si or si + w["k"] <= o["s"]):
                continue  # gun ortusmesi -> sizinti, aday degil
            if sim[(i, j)] > bs:
                best, bs = o["label"], sim[(i, j)]
        if best is None:  # aday yoksa sayma (sisme olmasin)
            fb += 1
            continue
        cm[(w["label"], best)] += 1
        ok += (best == w["label"])
    # Siluet (tum cifler; ortusme notu raporda).
    sil = []
    for i, w in enumerate(wins):
        same = [1 - sim[(i, j)] for j in range(n)
                if j != i and wins[j]["label"] == w["label"]]
        if not same:
            continue
        av = sum(same) / len(same)
        others = {}
        for j in range(n):
            if wins[j]["label"] == w["label"]:
                continue
            others.setdefault(wins[j]["label"], []).append(
                1 - sim[(i, j)])
        if not others:
            continue
        bv = min(sum(v) / len(v) for v in others.values())
        sil.append((bv - av) / max(av, bv) if max(av, bv) > 0 else 0.0)
    nn = n - fb
    return {"n": n, "nn": nn, "fb": fb, "acc": ok / nn if nn else 0.0,
            "ok": ok, "within": within, "between": between,
            "sil": sil, "cm": cm}


def main():
    d = load()
    res = {}
    for k in KS:
        wins = windows_for(k, d["events"])
        for w in wins:
            w["k"] = k
        res[k] = (wins, metrics(wins))
    # W0: k=1 onceki F2 ile birebir (0.473).
    acc1 = res[1][1]["acc"]
    # W1: determinizm (cift-kos).
    wins2 = windows_for(5, d["events"])
    for w in wins2:
        w["k"] = 5
    det = abs(metrics(wins2)["acc"] - res[5][1]["acc"]) == 0.0
    # W2: sizinti-denetimi (adaysiz sorgu yok).
    leak = all(res[k][1]["fb"] == 0 for k in KS)

    print("k | pencere | LOO-acc | within | between | siluet")
    for k in KS:
        m = res[k][1]
        print(f"{k:2d} | {m['n']:7d} | {m['ok']:3d}/{m['n']:3d}="
              f"{m['acc']:.3f} | {_st.mean(m['within']):.3f} | "
              f"{_st.mean(m['between']):.3f} | "
              f"{_st.mean(m['sil']):+.3f}")
    print("sinif dagilimi (k: etiket->pencere):")
    for k in KS:
        c = Counter(w["label"] for w in res[k][0])
        print(f"  k={k:2d} " + " ".join(f"{l}={c[l]}"
                                        for l in sorted(c)))
    print("sinif detayi (dogruluk + uygun-ayni-sinif komsusu olanlar):")
    for k in KS:
        wins, m = res[k]
        tot = Counter()
        hit = Counter()
        elig = Counter()
        for i, w in enumerate(wins):
            tot[w["label"]] += 1
            has = any(i != j and o["label"] == w["label"] and
                      (o["s"] + k <= w["s"] or w["s"] + k <= o["s"])
                      for j, o in enumerate(wins))
            elig[w["label"]] += has
        for (t, p), n in m["cm"].items():
            if t == p:
                hit[t] += n
        print(f"  k={k:2d} " + " ".join(
            f"{l}:{hit[l]}/{tot[l]}(u={elig[l]})"
            for l in sorted(tot)))
    print("confusion (gercek->tahmin, yalniz karismalar):")
    for k in KS:
        m = res[k][1]
        mix = sorted((t, p, n) for (t, p), n in m["cm"].items()
                     if t != p and n > 0)
        print(f"  k={k:2d} dogru={m['ok']} " +
              (" ".join(f"{t}>{p}:{n}" for t, p, n in mix[:8])
               or "sifir-karisma"))

    chk = [("W0 k1-F2-tutarli", abs(acc1 - 0.473) < 0.005),
           ("W1 deterministik", det),
           ("W2 sizintisiz", leak)]
    bad = [x for x, v in chk if not v]
    for x, v in chk:
        print(f"  {'OK' if v else 'BATTI'} {x}")
    if bad:
        raise SystemExit(f"BATTI: {bad}")
    curve = " ".join(f"{k}:{res[k][1]['acc']:.3f}" for k in KS)
    print(f"EGRI: {curve}")
    print("OZET-WINDOW: " + " ".join(x for x, _ in chk))


if __name__ == "__main__":
    main()
