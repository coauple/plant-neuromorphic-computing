"""UPU madenciligi — UPU_SPEC.md §2 kilitli prosedur.

Cikti: upu_instances.json (ciftler, binler, episode'lar + tren
istatistigi). Karar kurallari SPEC'teki sirayla uygulanir.
stdlib-only; kablo salt-okunur.
"""
import csv
import json
import os
from collections import Counter

ROOT = "/home/metehan/Masaüstü/Bitki nöromorfik/salep_core"
ENC = os.path.join(ROOT, "pattern")
OUT = os.path.join(ENC, "p0_out")
AFF = os.path.join(ROOT, "encoder", "out", "aff300_afferent.csv")


def load():
    evs = []
    with open(AFF, newline="") as f:
        for r in csv.DictReader(f):
            evs.append((int(r["tick"]), int(r["post_id"])))
    return sorted(evs)


def episodes(evs, x, y):
    by_post = {}
    for (t, p) in evs:
        by_post.setdefault(p, []).append(t)
    out = []
    for t0 in by_post.get(x, []):
        xt = [t for t in by_post[x] if t0 <= t <= t0 + 60]
        yt = [t for t in by_post[y] if t0 <= t <= t0 + 120]
        if len(xt) >= 2 and len(yt) >= 2:
            out.append({"t0": t0,
                        "x": [t - t0 for t in xt],
                        "y": [t - t0 for t in yt],
                        "dt": yt[0] - t0})
    return out


def main():
    evs = load()
    counts = Counter(p for (_, p) in evs)
    print(f"kablo: {len(evs)} olay, post dagilimi: {dict(sorted(counts.items()))}")

    cands = {}
    for x in sorted(counts):
        for y in sorted(counts):
            if x != y:
                cands[(x, y)] = episodes(evs, x, y)
    pop = sorted(((len(v), k) for k, v in cands.items()), reverse=True)
    print("en kalabalik 5 cift: " + str([(k, n) for (n, k) in pop[:5]]))

    pair = (4, 7) if len(cands.get((4, 7), [])) > 0 else pop[0][1]
    print(f"secilen cift: {pair} ({len(cands[pair])} episode)")
    eps = cands[pair]
    dts = Counter(e["dt"] for e in eps)
    bins = None
    if 5 in dts and 20 in dts:
        bins = (5, 20)
    else:
        keys = sorted(dts)
        best = None
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                if keys[j] - keys[i] >= 10:
                    tot = dts[keys[i]] + dts[keys[j]]
                    if best is None or tot > best[0]:
                        best = (tot, (keys[i], keys[j]))
        bins = best[1] if best else None
    if bins is None:
        print("ABORT: kullanilabilir bin yok")
        raise SystemExit("UPU-ABORT: bin yok")

    sel = {b: [e for e in eps if e["dt"] == b][:5] for b in bins}
    print(f"binler: {bins} (sayilar: {[len(sel[b]) for b in bins]})")
    for b in bins:
        spans = [(max(e["x"]) if e["x"] else 0,
                  max(e["y"]) if e["y"] else 0,
                  len(e["x"]), len(e["y"])) for e in sel[b]]
        print(f"  dt={b}: tren (Xgenislik,Ygenislik,Xn,Yn): {spans}")

    # Kimlik cifti
    ipair = (4, 8) if len(cands.get((4, 8), [])) > 0 else None
    if ipair is None:
        rest = sorted(((len(cands[(4, y)]), y) for y in counts
                       if y != 4 and y != pair[1]), reverse=True)
        ipair = (4, rest[0][1]) if rest and rest[0][0] > 0 else None
    print(f"kimlik cifti: {ipair} "
          f"({len(cands[ipair]) if ipair else 0} episode)")
    ieps = []
    if ipair:
        ieps = cands[ipair][:5]

    with open(os.path.join(OUT, "upu_instances.json"), "w") as f:
        json.dump({"pair": list(pair), "bins": list(bins),
                   "episodes": {str(b): sel[b] for b in bins},
                   "ipair": list(ipair) if ipair else None,
                   "ipair_episodes": ieps}, f, indent=1)
    print("OZET-UPU-MINE: OK")


if __name__ == "__main__":
    main()
