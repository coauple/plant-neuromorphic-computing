#!/usr/bin/env python3
"""bench/stage2_analysis.py — demux metrikleri (AŞAMA 2/3/5 ortak).

Girdi: gen.py tel+pencere CSV'leri + exp_demux tick CSV'leri.
Yöntemler (aynı girdi, pencere skoru = 100-tick trailing skor):
  S  : bant ateş toplamı (C++ fdm_tick çıktısı)
  B1 : sum(p[i] & p[i-tau]) — gecikme-hattı coincidence
  B2 : sum(x[i]*x[i-tau]) — pencere otokorelasyonu
  B3 : |DFT(f=1/tau)|^2 — Goertzel-enerji (kayan nokta-dot)
  B4 : ISI histogramı tau±1 hücresi — darbe-aralık sayacı
Eşikler YALNIZ kalibrasyon seed'lerinden (Youden J); testte uygulanır.
Çıktı: auc.csv, latency.csv, harmonic.csv, thresholds.csv (+ konsol özeti).
"""
import csv
import glob
import math
import os
import sys

import numpy as np

W = 100
BW = 1


def load_wire(p):
    d = np.loadtxt(p, delimiter=",", skiprows=1)
    return d[:, 1] / 65536.0


def load_windows(p):
    rows = list(csv.DictReader(open(p)))
    return rows


def load_stick(p, nband):
    d = np.loadtxt(p, delimiter=",", skiprows=1)
    return d[:, 1:1 + nband]


def trail_sum(v):
    c = np.concatenate([[0.0], np.cumsum(v)])
    return c[W:] - c[:-W]


def scores_for_seed(wire, stick, taus):
    """tick+win skorları: dict[(method,tau)] -> (per_tick, per_win_vec_fn)."""
    T = len(wire)
    pres = (wire > 0).astype(float)
    pt = np.flatnonzero(wire > 0)
    isi_end = pt[1:]
    isi_val = np.diff(pt)
    def full(v):
        return np.concatenate([np.zeros(W - 1), trail_sum(v)])

    out = {}
    for bi, tau in enumerate(taus):
        S_tick = full(stick[:, bi])
        r1 = np.zeros(T)
        r1[tau:] = pres[tau:] * pres[:-tau]
        b1 = full(r1)
        r2 = np.zeros(T)
        r2[tau:] = wire[tau:] * wire[:-tau]
        b2 = full(r2)
        k = np.arange(W)
        cw = np.cos(2 * np.pi * k / tau)
        sw = np.sin(2 * np.pi * k / tau)
        # Kayan pencere dot (Goertzel-enerjisi eşdeğeri).
        n = T - W + 1
        strided = np.lib.stride_tricks.as_strided(
            wire, shape=(n, W), strides=(wire.strides[0], wire.strides[0]))
        e = (strided @ cw) ** 2 + (strided @ sw) ** 2
        b3 = np.concatenate([np.zeros(W - 1), e])
        m = (isi_val >= tau - BW) & (isi_val <= tau + BW)
        cnt = np.zeros(T)
        np.add.at(cnt, isi_end[m], 1)
        b4 = full(cnt)
        out[tau] = {"S": S_tick, "B1": b1, "B2": b2, "B3": b3, "B4": b4}
    return out


def auc_mw(y, s):
    y = np.asarray(y, dtype=bool)
    s = np.asarray(s)
    p, n = s[y], s[~y]
    if len(p) == 0 or len(n) == 0:
        return 0.5
    return float(((p[:, None] > n).sum() + 0.5 * (p[:, None] == n).sum())
                 / (len(p) * len(n)))


def youden_thr(y, s):
    y = np.asarray(y, dtype=bool)
    s = np.asarray(s)
    cand = np.unique(s)
    best, bt = -1.0, cand.max() + 1e-9
    for t in np.concatenate([[cand.min() - 1e-9], cand]):
        pred = s >= t
        tp = (pred & y).sum()
        fp = (pred & ~y).sum()
        se = tp / max(1, y.sum())
        sp = 1.0 - fp / max(1, (~y).sum())
        if se + sp - 1 > best:
            best, bt = se + sp - 1, t
    return float(bt)


def main():
    datadir, outdir, taus_s, cal0, cal1, tst0, tst1 = sys.argv[1:8]
    taus = [int(x) for x in taus_s.split(",")]
    cal = list(range(int(cal0), int(cal1) + 1))
    tst = list(range(int(tst0), int(tst1) + 1))
    os.makedirs(outdir, exist_ok=True)

    def seed_scores(s):
        pre = os.path.join(datadir, f"demux_s{s}")
        wire = load_wire(pre + "_wire.csv")
        rows = load_windows(pre + "_windows.csv")
        stick = load_stick(pre + "_tick.csv", len(taus))
        tk = scores_for_seed(wire, stick, taus)
        wends = [int(r["t1"]) - 1 for r in rows]
        return rows, tk, wends

    # Eşikler: kalibrasyon havuzu.
    cal_y, cal_s = {}, {}
    for s in cal:
        rows, tk, wends = seed_scores(s)
        for tau in taus:
            key = f"has{tau}"
            y = [int(r[key]) for r in rows]
            for m, tv in tk[tau].items():
                cal_y.setdefault((m, tau), []).extend(y)
                cal_s.setdefault((m, tau), []).extend([tv[e] for e in wends])
    thr = {k: youden_thr(cal_y[k], np.array(cal_s[k])) for k in cal_y}
    with open(os.path.join(outdir, "thresholds.csv"), "w") as f:
        f.write("method,tau,thr\n")
        for (m, t), v in sorted(thr.items()):
            f.write(f"{m},{t},{v:.6f}\n")

    # Test: AUC + harmonik + gecikme.
    aucs, harms, lats = [], [], []
    for s in tst:
        rows, tk, wends = seed_scores(s)
        lab = [r["label"] for r in rows]
        for tau in taus:
            y = np.array([int(r[f"has{tau}"]) for r in rows])
            for m, tv in tk[tau].items():
                wv = np.array([tv[e] for e in wends])
                aucs.append((s, m, tau, auc_mw(y, wv)))
                # Harmonik: combo(+) vs diğer-tekil (tau12 için 4-only vb.)
                other = [t for t in taus if t != tau][0] if len(taus) > 1 else None
                if other is not None:
                    pos = np.array([("+" in l) for l in lab])
                    neg = np.array([l == str(other) for l in lab])
                    sel = pos | neg
                    harms.append((s, m, tau, auc_mw(pos[sel], wv[sel])))
        # Gecikme: hedef-aktif segment başlangıçları (300-tick hizalı).
        for tau in taus:
            y = [int(r[f"has{tau}"]) for r in rows]
            nseg = len(rows) // 3
            for sg in range(nseg):
                segy = y[sg * 3:(sg + 1) * 3]
                prev = y[(sg - 1) * 3:sg * 3] if sg > 0 else [0]
                if max(segy) == 1 and max(prev) == 0:
                    on = sg * 300
                    for m, tv in tk[tau].items():
                        det = np.flatnonzero(tv[on:on + 300] >= thr[(m, tau)])
                        lat = int(det[0]) if len(det) else 300
                        lats.append((s, m, tau, lat,
                                     1 if len(det) else 0))
    with open(os.path.join(outdir, "auc.csv"), "w") as f:
        f.write("seed,method,tau,auc\n")
        for s, m, t, v in aucs:
            f.write(f"{s},{m},{t},{v:.6f}\n")
    with open(os.path.join(outdir, "harmonic.csv"), "w") as f:
        f.write("seed,method,tau,auc_sub\n")
        for s, m, t, v in harms:
            f.write(f"{s},{m},{t},{v:.6f}\n")
    with open(os.path.join(outdir, "latency.csv"), "w") as f:
        f.write("seed,method,tau,lat,det\n")
        for s, m, t, l, d in lats:
            f.write(f"{s},{m},{t},{l},{d}\n")
    # Konsol özeti.
    import statistics as st
    print("== AUC (test ort±std) ==")
    for tau in taus:
        for m in ("S", "B1", "B2", "B3", "B4"):
            v = [a[3] for a in aucs if a[1] == m and a[2] == tau]
            print(f"  tau{tau} {m}: {st.mean(v):.4f}±{st.stdev(v):.4f}")
    print("== gecikme medyan [tick] (D2 bari: 3*tau) ==")
    for tau in taus:
        for m in ("S", "B1", "B2", "B3", "B4"):
            v = sorted(l[3] for l in lats if l[1] == m and l[2] == tau)
            det = sum(l[4] for l in lats if l[1] == m and l[2] == tau)
            print(f"  tau{tau} {m}: med={v[len(v)//2]} det={det}/{len(v)}")
    print("OK stage2-analysis")


if __name__ == "__main__":
    main()
