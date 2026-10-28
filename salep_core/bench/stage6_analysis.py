#!/usr/bin/env python3
"""bench/stage6_analysis.py — seyrek-dünya nedensellik metrikleri (AŞAMA 6).

Alarm tanımı (TÜM yöntemlerde aynı): tick dizisi. Eşleştirme (W=16):
  precision_L = bağlı-Y ile eşleşen alarm / alarm
  recall_L    = alarmla eşleşen bağlı-Y / bağlı-Y
  lead_L      = eşleşen (Y, önceki-en-son-alarm) farklarının ortalaması
Yöntemler: S (pre0 ateşleri), N1 (alt-örnekli X+L), N2 (gecikme histogramı),
N3 (aynı-hızda rastgele). Hız eşitleme YALNIZ kalibrasyon seed'lerinden:
  N1 rho = S_hızı/X_hızı; N2 eşiği = hıza uyan skor kantili; N3 lam = S_hızı.
"""
import csv
import os
import sys

import numpy as np

W = 16
WMAX = 32


class LCG:
    def __init__(self, seed):
        self.s = int(seed) % (1 << 32)

    def uni(self):
        self.s = (1664525 * self.s + 1013904223) % (1 << 32)
        return self.s / float(1 << 32)


def load_ev(p):
    rows = list(csv.DictReader(open(p)))
    X = [int(r["tick"]) for r in rows if r["kind"] == "X"]
    YL = [int(r["tick"]) for r in rows if r["kind"] == "Y" and int(r["link"]) >= 0]
    YA = [int(r["tick"]) for r in rows if r["kind"] == "Y"]
    return X, YL, YA


def load_tick(p):
    d = np.loadtxt(p, delimiter=",", skiprows=1)
    alarm = np.flatnonzero(d[:, 4] > 0)  # pre0
    return alarm, int(d.shape[0])


def pair_stats(alarms, YL, YA):
    alarms = np.asarray(sorted(set(int(a) for a in alarms)))
    YL = sorted(YL)
    YA = set(YA)
    if len(alarms) == 0:
        return 0.0, 0.0, -1.0, 0
    import bisect
    yl = sorted(YL)
    hit_a = 0
    for a in alarms:
        i = bisect.bisect_right(yl, a)
        if i < len(yl) and yl[i] - a <= W and yl[i] - a > 0:
            hit_a += 1
    prec = hit_a / len(alarms)
    hit_y = 0
    leads = []
    for y in yl:
        i = bisect.bisect_left(alarms, y) - 1
        if i >= 0 and 0 < y - alarms[i] <= W:
            hit_y += 1
            leads.append(y - alarms[i])
    rec = hit_y / max(1, len(yl))
    lead = float(np.mean(leads)) if leads else -1.0
    return prec, rec, lead, len(alarms)


def main():
    datadir, outdir, cal0, cal1, tst0, tst1, ticks_s = sys.argv[1:8]
    ticks = int(ticks_s)
    cal = list(range(int(cal0), int(cal1) + 1))
    tst = list(range(int(tst0), int(tst1) + 1))
    os.makedirs(outdir, exist_ok=True)
    # Kalibrasyon: S hızı, X hızı, N2 histogramı.
    s_rate, x_rate, hist = [], [], np.zeros(WMAX + 1)
    nx = 0
    for s in cal:
        pre = os.path.join(datadir, f"sparse_s{s}")
        X, YL, YA = load_ev(pre + "_events.csv")
        alarm, T = load_tick(pre + "_tick.csv")
        s_rate.append(len(alarm) / T)
        x_rate.append(len(X) / T)
        lk = {}
        for r in csv.DictReader(open(pre + "_events.csv")):
            if r["kind"] == "Y" and int(r["link"]) >= 0:
                lk.setdefault(int(r["link"]), int(r["tick"]))
        xd = {i: t for i, t in enumerate(X)}
        for i, yt in lk.items():
            d = yt - xd[i]
            if 0 <= d <= WMAX:
                hist[d] += 1
        nx += len(X)
    hist = hist / max(1, nx)
    S_RATE = float(np.mean(s_rate))
    X_RATE = float(np.mean(x_rate))
    RHO = min(1.0, S_RATE / max(1e-12, X_RATE))
    rho_cap = S_RATE > X_RATE
    # N2 eşiği: kalibrasyonda S hızını veren skor kantili.
    allscores = []
    for s in cal:
        pre = os.path.join(datadir, f"sparse_s{s}")
        X, _, _ = load_ev(pre + "_events.csv")
        import bisect
        xs = sorted(X)
        for t in range(ticks):
            i = bisect.bisect_left(xs, t) - 1
            if i >= 0 and 0 < t - xs[i] <= WMAX:
                allscores.append(hist[t - xs[i]])
    allscores = np.array(sorted(allscores))
    k = int((1.0 - S_RATE) * len(allscores))
    THR = float(allscores[min(max(k, 0), len(allscores) - 1)]) if len(allscores) else 1e9
    with open(os.path.join(outdir, "calibration.csv"), "w") as f:
        f.write(f"key,value\nS_RATE,{S_RATE:.6f}\nX_RATE,{X_RATE:.6f}\n"
                f"RHO,{RHO:.6f}\nrho_capped,{int(rho_cap)}\nTHR,{THR:.6f}\n")
    # Test.
    import bisect
    out = [("seed", "method", "prec_L", "rec_L", "lead_L", "n_alarm")]
    for s in tst:
        pre = os.path.join(datadir, f"sparse_s{s}")
        X, YL, YA = load_ev(pre + "_events.csv")
        alarm, T = load_tick(pre + "_tick.csv")
        out.append((s, "S", *pair_stats(alarm, YL, YA)))
        rng = LCG(s + 7000)
        n1 = sorted(x + 8 for x in X if rng.uni() < RHO and x + 8 < T)
        out.append((s, "N1", *pair_stats(n1, YL, YA)))
        xs = sorted(X)
        sc = np.zeros(T)
        for t in range(T):
            i = bisect.bisect_left(xs, t) - 1
            if i >= 0 and 0 < t - xs[i] <= WMAX:
                sc[t] = hist[t - xs[i]]
        n2 = sorted(int(t) for t in range(T) if sc[t] >= THR)
        out.append((s, "N2", *pair_stats(n2, YL, YA)))
        rng3 = LCG(s + 9000)
        n3 = sorted(t for t in range(T) if rng3.uni() < S_RATE)
        out.append((s, "N3", *pair_stats(n3, YL, YA)))
    with open(os.path.join(outdir, "metrics.csv"), "w") as f:
        f.write(",".join(out[0]) + "\n")
        for r in out[1:]:
            f.write(f"{r[0]},{r[1]},{r[2]:.4f},{r[3]:.4f},{r[4]:.2f},{r[5]}\n")
    import statistics as st
    print("== test (n=30): prec_L / rec_L / lead ==")
    for m in ("S", "N1", "N2", "N3"):
        p = [r[2] for r in out[1:] if r[1] == m]
        r = [r[3] for r in out[1:] if r[1] == m]
        l = [r[4] for r in out[1:] if r[1] == m and r[4] >= 0]
        print(f"  {m}: P={st.mean(p):.3f}±{st.stdev(p):.3f} "
              f"R={st.mean(r):.3f}±{st.stdev(r):.3f} "
              f"lead={st.mean(l):.1f}" if l else f"  {m}: P={st.mean(p):.3f} R={st.mean(r):.3f} lead=yok")
    print(f"  (kalibrasyon: S_RATE={S_RATE:.5f} RHO={RHO:.3f}{' CAP' if rho_cap else ''} THR={THR:.4f})")
    print("OK stage6-analysis")


if __name__ == "__main__":
    main()
