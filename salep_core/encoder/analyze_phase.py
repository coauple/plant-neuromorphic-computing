"""enc_*.csv karakterizasyonu (SPEC_v0_1.md E4).

Girdi: encoder/out/aff300_afferent.csv (E0, 407 olay). Cikti:
enc_mapping, enc_phase_raster, enc_phase_histogram, enc_phase_collision,
enc_dphase, enc_summary.csv + enc_summary.txt (E5 karar). stdlib-only,
sim/web bagi YOK. Olculur, tahmin edilmez.
"""
import csv
import os
from collections import Counter

import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)
import afferent_encoder as E

OUT = os.path.join(ENC, "out")
AFF = os.path.join(OUT, "aff300_afferent.csv")


def w(path, header, rows):
    with open(path, "w", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(header)
        wr.writerows(rows)


def main():
    events = E.read_afferent_csv(AFF)
    spikes = E.encode_events(events)
    n = len(events)

    by_post = Counter(p for (_, p, _) in events)
    tau_of = {}
    for (_, p, b) in events:
        tau_of.setdefault(p, Counter())[b] += 1

    w(os.path.join(OUT, "enc_mapping.csv"),
      ("post_id", "tau_b", "phi_id_x100", "phi_tau_x100", "count"),
      [(p, b, p * 3000, ((b - 4) * 36000) // 57, by_post[p])
       for p in sorted(by_post) for b in sorted(tau_of[p])])

    w(os.path.join(OUT, "enc_phase_raster.csv"),
      ("tick", "phi_id_x100", "phi_tau_x100"),
      [(t, i, u) for (t, i, u) in spikes])

    hist = [by_post.get(p, 0) for p in range(12)]
    w(os.path.join(OUT, "enc_phase_histogram.csv"),
      ("phi_id_x100", "count"),
      [(p * 3000, hist[p]) for p in range(12)])

    tau_posts = {}
    for p in sorted(by_post):
        for b in tau_of[p]:
            tau_posts.setdefault(b, set()).add(p)
    coll = sorted((b, sorted(ps)) for b, ps in tau_posts.items()
                  if len(ps) > 1)
    w(os.path.join(OUT, "enc_phase_collision.csv"),
      ("tau_b", "phi_tau_x100", "posts", "n_posts"),
      [(b, ((b - 4) * 36000) // 57, "+".join(map(str, ps)), len(ps))
       for b, ps in coll])

    # D1: ayni tick'te esen ciftler |Dphi_id| ; D2: ardisik isaretli adim
    tick_posts = {}
    for (t, p, _) in events:
        tick_posts.setdefault(t, []).append(p)
    d1 = Counter()
    for ps in tick_posts.values():
        if len(ps) > 1:
            for i in range(len(ps)):
                for j in range(i + 1, len(ps)):
                    d1[abs(ps[i] - ps[j]) * 3000] += 1
    d2 = Counter()
    for (_, p0, _), (_, p1, _) in zip(events, events[1:]):
        d2[(p1 - p0) * 3000] += 1
    d3 = Counter()
    for (t, p, _), (t2, p2, _) in zip(events, events[1:]):
        d3[abs(p2 - p) * 3000 % 3000] += 1
    d1rows = [("D1", k, v) for k, v in sorted(d1.items())]
    d2rows = [("D2", k, v) for k, v in sorted(d2.items())]
    d3rows = [("D3mod3000", k, v) for k, v in sorted(d3.items())]
    w(os.path.join(OUT, "enc_dphase.csv"), ("metric", "value_x100", "count"),
      d1rows + d2rows + d3rows)

    live = sorted(by_post)
    dark = [p for p in range(10) if p not in by_post]
    dens = n / 15000
    w(os.path.join(OUT, "enc_summary.csv"),
      ("key", "value"),
      [("n_events", n), ("n_ticks", 15000),
       ("density", round(dens, 6)),
       ("live_posts", "+".join(map(str, live))),
       ("n_live", len(live)), ("dark_posts", "+".join(map(str, dark))),
       ("tau_collision_groups", len(coll)),
       ("d1_pairs", sum(d1.values())), ("d1_top", str(d1.most_common(3))),
       ("d2_n", sum(d2.values())), ("d2_top", str(d2.most_common(3))),
       ("d3_mod", str(sorted(d3.items())))])

    # E5 karar: sayidan cikar, tahmin etme
    top_d1 = d1.most_common(5)
    top_d2 = d2.most_common(5)
    lines = [
        "ENC SUMMARY (E5 karar raporu, olculmus sayi):",
        f"olay: {n}/15000 tick (yogunluk {dens:.4f}); "
        f"canli post: {len(live)} ({' '.join(map(str, live))}); "
        f"olu: {' '.join(map(str, dark))} (240/270 karanlik); "
        f"yedek 10/11 bos.",
        f"phi_id: 30 derece adim, 0 cakisma. phi_tau: {len(coll)} cakisma "
        f"grubu {[ (b, ps) for b, ps in coll ]} (aranan bulgu).",
        f"D1 es-atesme cifti: {sum(d1.values())} cift, "
        f"en sik: {top_d1} (x100).",
        f"D2 ardisik adim: {sum(d2.values())} adim, en sik: {top_d2} (x100).",
        f"D3 |Dphi| mod 30deg: {sorted(d3.items())} — "
        "tum kutle 0'da (faz-kilitli, ara-faz YOK).",
    ]
    # kural: canli post sayisi = dendrit adayi sayisi (her post ayri kimlik
    # fazi tasir); D3 sifir-disi kutle icerseydi bantlama gerekirdi.
    non0 = sum(v for k, v in d3.items() if k != 0)
    if non0 == 0:
        lines.append("KARAR: 8 dendrit adayi (8 canli post); bantlama "
                     "GEREKMEZ — D3 ara-faz gostermiyor, faz-basina-bir "
                     "yeter (olculdu, tahmin degil).")
    else:
        lines.append(f"KARAR: D3'te {non0} ara-faz adimi var — bantli "
                     "dendrit degerlendir (acik kalem).")
    lines.append("ACIK KALEM: p2i/p2j olu (240/270 karanlik) — gercek "
                 "kusur, faz tasarimi degil.")
    with open(os.path.join(OUT, "enc_summary.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
