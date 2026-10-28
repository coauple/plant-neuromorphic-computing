#!/usr/bin/env python3
"""bench/gen.py — sentetik dünya üreteçleri (AŞAMA 1).

Tasarım: tüm rastgelelik açık tamsayı LCG'den (fdm.h ile aynı sabitler:
a=1664525, c=1013904223, m=2**32). Tel genlikleri Q16.16 TAMSAYI olarak
hesaplanır ve CSV'ye tamsayı yazılır — C++ tarafı strtol ile kayıpsız okur.
Kayan-nokta yalnız seyrek-dünya geometrik aralıklarında (IEEE deterministik)
ve meta dosyasında kullanılır; çekiliş sırası sabit ve belgeli.

Demux tel modeli main_fdm.cpp:52-70'in birebir izdüşümüdür:
  - ritim darbesi: t>=d ve (t-d)%tau==0 olan tick'lerde
  - genlik jitter: j = LCG%(2r+1)-r, mult=(1000+j)/1000 (Q16.16 tamsayı)
  - ekstra darbe: tick-başına Bernoulli(pextra/100), genlik 0.7*PULSE jitter'lı
NOT: p_extra "tick-başına olasılık %" olarak tanımlıdır (main_fdm ile aynı);
"darbe sayısına oran" DEĞİLDİR. Bu tanım TEST_PLAN H3 ve tüm raporlarda aynen
kullanılır.

Kullanım:
  gen.py demux  --seed S --taus 4,12 --foreign 6,8,10 --segs-per-type 8 \
      --seg-ticks 300 --pextra 0 --jit 0 --out bench/results/stage1/demux_s2000
  gen.py sparse --seed S --ticks 30000 --x-gap 200 --L 8 --p 0.8 --j 2 \
      --q 0.002 --out bench/results/stage1/sparse_s2000
"""
import argparse
import math
import os
import sys

Q16 = 1 << 16
PULSE_Q16 = int(0.8 * Q16)          # 52428 (fixed_from_double ile aynı kesme)
PULSE07_Q16 = (PULSE_Q16 * int(0.7 * Q16)) >> 16  # fixed_mul(0.8, 0.7)


class LCG:
    def __init__(self, seed):
        self.s = int(seed) % (1 << 32)

    def next(self):
        self.s = (1664525 * self.s + 1013904223) % (1 << 32)
        return self.s

    def mod(self, n):
        return self.next() % n

    def uni(self):
        return self.next() / float(1 << 32)


def jit_amp(base_q16, r_pm, rng):
    """r_pm: per-mille yarı-aralık (20% -> 200, main_fdm %401 ile aynı)."""
    if r_pm <= 0:
        return base_q16
    j = rng.mod(2 * r_pm + 1) - r_pm
    mult = ((1000 + j) << 16) // 1000
    return (base_q16 * mult) >> 16


def gen_demux(a):
    rng = LCG(a.seed)
    taus = [int(x) for x in a.taus.split(",")]
    foreign = [int(x) for x in a.foreign.split(",")] if a.foreign else []
    r_pm = int(a.jit) * 10
    # Segment tipleri: her hedef tekil + hedef-çifti + her yabancı + sessizlik.
    types = [[t] for t in taus]
    if len(taus) >= 2:
        types.append(list(taus[:2]))
    for f in foreign:
        types.append([f])
    types.append([])
    segs = []
    for _ in range(a.segs_per_type):
        segs.extend([list(t) for t in types])
    # Fisher-Yates (LCG sırası belgeli: sondan başa).
    for i in range(len(segs) - 1, 0, -1):
        k = rng.mod(i + 1)
        segs[i], segs[k] = segs[k], segs[i]
    wire = {}
    seg_rows = []
    for si, rh in enumerate(segs):
        t0 = si * a.seg_ticks
        delays = {tau: rng.mod(tau) for tau in rh}  # rastgele başlangıç fazı
        for t in range(t0, t0 + a.seg_ticks):
            w = 0
            for tau in sorted(rh):
                if t >= t0 + delays[tau] and (t - t0 - delays[tau]) % tau == 0:
                    w += jit_amp(PULSE_Q16, r_pm, rng)
            if rng.mod(100) < a.pextra:
                w += jit_amp(PULSE07_Q16, r_pm, rng)
            if w:
                wire[t] = wire.get(t, 0) + w
        seg_rows.append((si, t0, "+".join(str(x) for x in sorted(rh)) or "none"))
    total = len(segs) * a.seg_ticks
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    with open(a.out + "_wire.csv", "w") as f:
        f.write("tick,wire_q16\n")
        for t in range(total):
            f.write(f"{t},{wire.get(t, 0)}\n")
    with open(a.out + "_windows.csv", "w") as f:
        f.write("wid,t0,t1,label," + ",".join(f"has{t}" for t in taus) + "\n")
        wid = 0
        for t0 in range(0, total, 100):
            si = t0 // a.seg_ticks
            lab = seg_rows[si][2]
            act = set(segs[si])
            f.write(f"{wid},{t0},{t0 + 100},{lab}," +
                    ",".join("1" if t in act else "0" for t in taus) + "\n")
            wid += 1
    with open(a.out + "_meta.txt", "w") as f:
        f.write(f"kind=demux seed={a.seed} taus={a.taus} foreign={a.foreign} "
                f"segs_per_type={a.segs_per_type} seg_ticks={a.seg_ticks} "
                f"pextra={a.pextra} jit={a.jit} total_ticks={total} "
                f"n_pulses={len(wire)}\n")


def gen_sparse(a):
    rng = LCG(a.seed)
    xs = []
    t = 0
    while True:
        u = rng.uni()
        gap = 1 + int(math.floor(-math.log(1.0 - u) * a.x_gap)) if u < 1.0 else 1
        t += gap
        if t >= a.ticks:
            break
        xs.append(t)
    if a.nox:  # X-yok kontrolü (Aşama 6 C2): X ve bağlı-Y yok, sahte-Y var.
        xs = []
    evs = [(t, "X", i) for i, t in enumerate(xs)]
    n_linked = 0
    for i, xt in enumerate(xs):
        if rng.uni() < a.p:
            off = a.L - a.j + int(math.floor(rng.uni() * (2 * a.j + 1)))
            yt = xt + off
            if 0 <= yt < a.ticks:
                evs.append((yt, "Y", i))
                n_linked += 1
    n_fake = 0
    for t in range(a.ticks):
        if rng.uni() < a.q:
            evs.append((t, "Y", -1))
            n_fake += 1
    evs.sort(key=lambda e: (e[0], 0 if e[1] == "X" else 1))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    with open(a.out + "_events.csv", "w") as f:
        f.write("tick,kind,link\n")
        for t, k, l in evs:
            f.write(f"{t},{k},{l}\n")
    with open(a.out + "_meta.txt", "w") as f:
        f.write(f"kind=sparse seed={a.seed} ticks={a.ticks} x_gap={a.x_gap} "
                f"L={a.L} p={a.p} j={a.j} q={a.q} n_x={len(xs)} "
                f"n_linked={n_linked} n_fake={n_fake}\n")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("demux")
    d.add_argument("--seed", type=int, required=True)
    d.add_argument("--taus", default="4,12")
    d.add_argument("--foreign", default="6,8,10")
    d.add_argument("--segs-per-type", type=int, default=8)
    d.add_argument("--seg-ticks", type=int, default=300)
    d.add_argument("--pextra", type=int, default=0)
    d.add_argument("--jit", type=int, default=0)
    d.add_argument("--out", required=True)
    s = sub.add_parser("sparse")
    s.add_argument("--seed", type=int, required=True)
    s.add_argument("--ticks", type=int, default=30000)
    s.add_argument("--x-gap", type=int, default=200)
    s.add_argument("--L", type=int, default=8)
    s.add_argument("--p", type=float, default=0.8)
    s.add_argument("--j", type=int, default=2)
    s.add_argument("--q", type=float, default=0.002)
    s.add_argument("--nox", action="store_true")
    s.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.cmd == "demux":
        gen_demux(a)
    else:
        gen_sparse(a)


if __name__ == "__main__":
    sys.exit(main())
