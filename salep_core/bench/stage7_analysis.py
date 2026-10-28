#!/usr/bin/env python3
"""bench/stage7_analysis.py — gerçek veri: uyaran-öncesi/sonrası ayrışması.

Kayıtlar: work/ altındaki Ocimum wav+events çiftleri (alfabetik ilk 2 =
kalibrasyon, kalan = test). Pencereler 1 sn (100 tick @100 Hz):
  pre : [m-2,m) -> 2 pencere, etiket 0
  post: [m,m+5) -> 5 pencere, etiket 1 (ZAYIF etiket: yanıt garanti değil)
Skorlar:
  S    : exp_demux (tau12 tek-bant, pops 8, plir 1) pencere ateş toplamı
  B-var: pencere varyansı (100 Hz sinyal)
  B-hf : birinci-fark enerjisi (yüksek-frekans değişim)
THETA: kalibrasyon pre-pencerelerinde medyan|d| x 4 (min 1).
Çıktı: auc.csv (havuzlanmış + kayıt-başına), theta.txt.
"""
import csv
import glob
import os
import statistics as st
import struct
import sys
import wave

import numpy as np


def load_events(p):
    ts = []
    for l in open(p, errors="ignore"):
        l = l.strip()
        if not l or l.startswith("#"):
            continue
        parts = l.replace(",", " ").split()
        ts.append(float(parts[-1]))
    return ts


def load_ds(p):
    d = np.loadtxt(p, delimiter=",", skiprows=1)
    return d[:, 1]


def load_swin(p):
    rows = list(csv.DictReader(open(p)))
    return {int(r["t0"]): int(r["b0sum"]) for r in rows}


def auc_mw(y, s):
    y = np.asarray(y, dtype=bool)
    s = np.asarray(s)
    p, n = s[y], s[~y]
    if len(p) == 0 or len(n) == 0:
        return 0.5
    return float(((p[:, None] > n).sum() + 0.5 * (p[:, None] == n).sum())
                 / (len(p) * len(n)))


def main():
    work, outdir = sys.argv[1:3]
    mode = sys.argv[3] if len(sys.argv) > 3 else "full"
    os.makedirs(outdir, exist_ok=True)
    wavs = sorted(glob.glob(os.path.join(work, "*.wav")))
    cal, tst = wavs[:2], wavs[2:]
    print(f"kayit: kal={len(cal)} test={len(tst)}")
    # THETA: kalibrasyon pre-pencereleri.
    ds = {}
    for w in wavs:
        base = os.path.splitext(w)[0]
        ds[w] = load_ds(base + "_ds.csv")
    pre_d = []
    for w in cal:
        ev = load_events(os.path.splitext(w)[0] + "-events.txt")
        x = ds[w]
        for m in ev:
            t1 = int(m * 100)
            t0 = max(1, t1 - 200)
            d = np.abs(np.diff(x[t0:t1 + 1]))
            pre_d.extend(d.tolist())
    floor = float(np.median(pre_d)) if pre_d else 1.0
    theta = max(1, int(round(4 * floor)))
    with open(os.path.join(outdir, "theta.txt"), "w") as f:
        f.write(f"theta={theta} floor={floor:.2f}\n")
    print(f"THETA={theta} (floor={floor:.2f})")
    if mode == "theta":
        print("OK stage7-theta")
        return
    # Pencereler + skorlar (S tick CSV'leri stage7.sh'de üretildi).
    sw = {}
    for w in wavs:
        base = os.path.splitext(w)[0]
        sw[w] = load_swin(base + "_win.csv")
    rec_auc = []
    pool_y, pool = [], {"S": [], "B-var": [], "B-hf": []}
    for w in tst:
        ev = load_events(os.path.splitext(w)[0] + "-events.txt")
        x = ds[w]
        T = len(x)
        yy, ss = [], {"S": [], "B-var": [], "B-hf": []}
        for m in ev:
            wins = [(int((m - 2) * 100), 0), (int((m - 1) * 100), 0)]
            wins += [(int((m + k) * 100), 1) for k in range(5)]
            for t0, lab in wins:
                if t0 < 0 or t0 + 100 > T:
                    continue
                seg = x[t0:t0 + 100]
                yy.append(lab)
                ss["S"].append(sw[w].get(t0, 0))
                ss["B-var"].append(float(np.var(seg)))
                ss["B-hf"].append(float(np.sum(np.diff(seg) ** 2)))
        if len(set(yy)) < 2:
            continue
        rec_auc.append((os.path.basename(w),
                        auc_mw(yy, ss["S"]),
                        auc_mw(yy, ss["B-var"]),
                        auc_mw(yy, ss["B-hf"]), len(yy)))
        pool_y.extend(yy)
        for k in pool:
            pool[k].extend(ss[k])
    print("== test kayitlari (kayit-basina AUC) ==")
    for r in rec_auc:
        print(f"  {r[0][:40]}: S={r[1]:.3f} B-var={r[2]:.3f} B-hf={r[3]:.3f} (n={r[4]})")
    print("== havuzlanmis AUC ==")
    for k in pool:
        print(f"  {k}: {auc_mw(pool_y, pool[k]):.4f} (n={len(pool_y)})")
    with open(os.path.join(outdir, "auc.csv"), "w") as f:
        f.write("rec,S,Bvar,Bhf,n\n")
        for r in rec_auc:
            f.write(f"{r[0]},{r[1]:.4f},{r[2]:.4f},{r[3]:.4f},{r[4]}\n")
        f.write(f"POOLED,{auc_mw(pool_y, pool['S']):.4f},"
                f"{auc_mw(pool_y, pool['B-var']):.4f},"
                f"{auc_mw(pool_y, pool['B-hf']):.4f},{len(pool_y)}\n")
    print("OK stage7-analysis")


if __name__ == "__main__":
    main()
