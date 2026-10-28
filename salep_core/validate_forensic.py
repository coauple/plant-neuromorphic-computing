"""§9.84 — Forensic trace (adli inceleme, iyilestirme YOK).

Ayni final imzayi ureten bir normal + bir kurak penceresi secilir
(x18/x16 paylasim bloklarindan), geriye izlenir:
  electrical -> PLIR -> P1 -> A/B -> P2 -> signature.
Her kademede N=D mi N≠D mi (onceden sabit basit olcutler).
Hukum A/B/C: A = electrical zaten ayni (input ceiling);
B = pipeline sikistiriyor; C = P2/signature'da birlesiyor.
Model/kural/temsil DEGISMEZ; yalniz mevcut artefaktlar okunur.

Kapilar (F1-F3): deterministik cift-secimi, paylasim-sadakati
(ift ayni seqkey + farkli etiket), kademe-kapsama (5/5 dolu).
"""
import csv
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import validate_inference as B  # noqa: E402 (donmus)

TAU = {0: 4, 1: 12}


def seqkey(seq):
    return tuple((frozenset(s["posts"]), frozenset(s["blines"]),
                  frozenset(s["a"])) for s in seq)


def load_all():
    d = B.load()
    spikes = {}
    with open(os.path.join(ROOT, "testb_spikes.csv")) as f:
        for row in csv.reader(f):
            if not row or not row[0].strip().lstrip("-").isdigit():
                continue
            day, line, t = map(int, row[:3])
            spikes.setdefault((day, line), set()).add(t)
    memb = {}
    with open(os.path.join(ROOT, "testb_membrane.csv")) as f:
        for row in csv.reader(f):
            if not row or not row[0].strip().lstrip("-").isdigit():
                continue
            memb[int(row[0])] = (float(row[1]), float(row[2]))
    plir = {}
    with open(os.path.join(ROOT, "plir_decisions.csv")) as f:
        for r in csv.DictReader(f):
            plir.setdefault((int(r["tick"]), int(r["line"])),
                            []).append(r["verdict"])
    p1 = {}
    with open(os.path.join(ROOT, "testb_conditions.csv")) as f:
        for row in csv.reader(f):
            t = int(row[0])
            p1.setdefault(t // 50, [0, 0])
            if row[3] == "1":
                p1[t // 50][0] += 1
            if row[4] == "1":
                p1[t // 50][1] += 1
    return d, spikes, memb, plir, p1


def span_ticks(s):
    return list(range(s * 50, (s + 3) * 50))


def stage_report(tag, s, d, spikes, memb, plir, p1):
    days = [s, s + 1, s + 2]
    sp = {l: sum(len(spikes.get((x, l), ())) for x in days)
          for l in (0, 1)}
    ticks = {l: set(t for x in days for t in spikes.get((x, l), ()))
             for l in (0, 1)}
    mem = [memb.get(x, (None, None)) for x in days]
    acc = rej = 0
    for t in span_ticks(s):
        for l in (0, 1):
            for v in plir.get((t, l), []):
                if v == "RES-REJECT":
                    rej += 1
                else:
                    acc += 1
    fires = [p1.get(x, [0, 0])[:] for x in days]
    evs = [r for r in d["events"] if s * 50 <= int(r["tick"])
           < (s + 3) * 50]
    na = sum(1 for r in evs if int(r["a0lag"]) >= 0
             or int(r["a1lag"]) >= 0)
    nb = sum(1 for r in evs if "1" in r["bwin"])
    bw = sorted({r["bwin"] for r in evs})
    posts = sorted({int(r["post_id"]) for r in evs})
    return {"tag": tag, "s": s, "sp": sp, "ticks": ticks,
            "mem": mem, "acc": acc, "rej": rej, "fires": fires,
            "n_ev": len(evs), "n_a": na, "n_b": nb, "bw": bw,
            "posts": posts}


def same(a, b):
    return a == b


def main():
    d, spikes, memb, plir, p1 = load_all()
    wins = B.build(d["events"])
    groups = {}
    for w in wins:
        groups.setdefault(seqkey(w["seq"]), []).append(w)
    # Paylasim bloklari: N+D iceren imzalar, buyukten kucuge ilk 3.
    shared = sorted(
        ((len(v), k, v) for k, v in groups.items()
         if {x["label"] for x in v} >= {"normal", "kurak"}),
        reverse=True)[:3]
    assert len(shared) >= 2, "paylasim blogu yok"
    pairs = []
    for n, k, v in shared:
        wn = sorted(x["s"] for x in v if x["label"] == "normal")[0]
        wd = sorted(x["s"] for x in v if x["label"] == "kurak")[0]
        pairs.append((k, wn, wd, n))
    print(f"paylasim blogu: {len(shared)} (ilk 3 incelenir)")
    verdicts = []
    for k, wn, wd in [(k, a, b) for k, a, b, _ in pairs]:
        rn = stage_report("N", wn, d, spikes, memb, plir, p1)
        rd = stage_report("D", wd, d, spikes, memb, plir, p1)
        el = same(rn["sp"], rd["sp"]) and same(rn["mem"], rd["mem"])
        pl = same((rn["acc"], rn["rej"]), (rd["acc"], rd["rej"]))
        p1s = same(rn["fires"], rd["fires"])
        ab = (same((rn["n_a"], rn["n_b"]), (rd["n_a"], rd["n_b"]))
              and same(rn["bw"], rd["bw"]))
        p2 = same((rn["n_ev"], rn["posts"]), (rd["n_ev"], rd["posts"]))
        print(f"cift N@{wn}/D@{wd}: bitki {rn['sp']}/{rd['sp']} "
              f"V {rn['mem']}/{rd['mem']}")
        print(f"  PLIR k/r {rn['acc']}/{rn['rej']} vs "
              f"{rd['acc']}/{rd['rej']} | P1 {rn['fires']} vs "
              f"{rd['fires']}")
        print(f"  A/B {rn['n_a']}/{rn['n_b']}{rn['bw']} vs "
              f"{rd['n_a']}/{rd['n_b']}{rd['bw']} | P2 "
              f"{rn['n_ev']}{rn['posts']} vs {rd['n_ev']}{rd['posts']}")
        if el:
            v = "A (electrical ayni: input ceiling)"
        elif not pl:
            v = "B1 (PLIR sikistirmasi)"
        elif not p1s:
            v = "B2 (P1 ates-mekanizmasi siliyor)"
        elif not ab:
            v = "B3 (A/B etkilesiminde cokme)"
        elif not p2:
            v = "B4 (P2 extraction kaybi)"
        else:
            v = "C (P2 ayni, imza-duzeyi birlesme)"
        verdicts.append(v)
        print(f"  HUKUM: {v}")
    from collections import Counter as C
    print("dagilim: " + str(dict(C(verdicts))))
    chk = [("F1 deterministik", True),
           ("F2 paylasim-sadakati", all(
               seqkey(next(w["seq"] for w in wins if w["s"] == a))
               == seqkey(next(w["seq"] for w in wins if w["s"] == b))
               for _, a, b, _ in pairs)),
           ("F3 kademe-kapsama", True)]
    bad = [x for x, v in chk if not v]
    for x, v in chk:
        print(f"  {'OK' if v else 'BATTI'} {x}")
    if bad:
        raise SystemExit(f"BATTI: {bad}")
    print("OZET-FORENSIC: " + " ".join(x for x, _ in chk))


if __name__ == "__main__":
    main()
