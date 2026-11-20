"""Ritim / sessizlik probu (2026-11-21 00:49, Cumartesi; GOZLEM — kod DONUK).
Bkz. CLAUDE.md §9.117.

Soru: pattern lob kendi ritmini uretiyor mu? (Izhikevich 2006
polikronizasyon okumasindan cikan soru: ag kendi sesini girdiden
ayirabiliyor mu?)

Kullanim (salep_core icinden):
  g++ -std=c++17 -O2 -Isrc src/main_pattern_lobe.cpp -o npu_pattern_lobe
  python3 probe_rhythm_silence.py testb_afferent.csv
Ciktilar gecici bir klasore yazilir; mevcut artefaktlara DOKUNULMAZ.

Three tests on the frozen pattern lobe binary, each with K4 off/on
and learning off/on (eta 0 / 0.30):

  T1 silence        : no input for 20,000 ticks -> any spontaneous firing?
  T2 drive-then-stop: real TEST B afferent (300 events, ends ~tick 10961),
                      then 29,000 silent ticks -> does activity persist?
  T3 noise          : Poisson afferent events (rate and (post,tau) pairs
                      matched to TEST B, but random times) for 60,000 ticks,
                      10 seeds -> does the output have a spectral peak the
                      input does not have?

The binary is used as-is; nothing in the repo is changed.
"""
import csv
import os
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(HERE, "npu_pattern_lobe")
REAL = sys.argv[1]
WORK = tempfile.mkdtemp(prefix="rhythm_probe_")
N_UNITS = 29


def read_real():
    ev = []
    with open(REAL) as f:
        r = csv.reader(f)
        next(r)
        for row in r:
            ev.append((int(row[0]), int(row[1]), int(row[2])))
    return ev


def write_aff(path, events):
    with open(path, "w") as f:
        f.write("tick,post_id,tau_b\n")
        for t, p, tau in sorted(events):
            f.write(f"{t},{p},{tau}\n")


def run(name, events, eta, k4):
    tag = f"{name}_eta{eta}_k4{k4}"
    aff = os.path.join(WORK, tag + "_aff.csv")
    write_aff(aff, events)
    mem = os.path.join(WORK, tag + "_mem.csv")
    log = os.path.join(WORK, tag + "_log.csv")
    k4csv = os.path.join(WORK, tag + "_k4.csv")
    cmd = [BIN, "--aff", aff, "--mem", mem, "--log", log,
           "--eta", str(eta), "--k4", str(k4)]
    if k4:
        cmd += ["--k4csv", k4csv]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    # raster: ticks x units from fires_hex
    ticks, fires = [], []
    with open(log) as f:
        r = csv.reader(f)
        next(r)
        for row in r:
            ticks.append(int(row[0]))
            fires.append(int(row[3], 16))
    fires = np.array(fires, dtype=np.int64)
    raster = np.array([(fires >> u) & 1 for u in range(N_UNITS)]).T
    k4_rows = None
    if k4 and os.path.exists(k4csv):
        k4_rows = np.loadtxt(k4csv, delimiter=",", skiprows=1, usecols=(0, 3, 7))
        if k4_rows.ndim == 1:
            k4_rows = k4_rows.reshape(1, -1)
    return np.array(ticks), raster, k4_rows


def peak_ratio(x):
    """Largest spectral power / median power, excluding DC and very low f."""
    x = x - x.mean()
    p = np.abs(np.fft.rfft(x)) ** 2
    f = np.fft.rfftfreq(len(x))
    keep = f > 1.0 / 2000  # ignore periods longer than 2000 ticks
    p, f = p[keep], f[keep]
    i = int(np.argmax(p))
    return p[i] / np.median(p), (1.0 / f[i]) if f[i] > 0 else float("inf")


def smooth_spectrum_peak(x, seg=4096):
    """Welch-averaged spectrum (less noisy) -> peak/median and peak period."""
    x = x - x.mean()
    n = len(x) // seg
    acc = None
    win = np.hanning(seg)
    for k in range(n):
        s = x[k * seg:(k + 1) * seg] * win
        p = np.abs(np.fft.rfft(s)) ** 2
        acc = p if acc is None else acc + p
    f = np.fft.rfftfreq(seg)
    keep = f > 1.0 / 1000
    p, f = acc[keep] / n, f[keep]
    i = int(np.argmax(p))
    return p[i] / np.median(p), 1.0 / f[i]


def isi_cv(raster):
    cvs = []
    for u in range(raster.shape[1]):
        t = np.flatnonzero(raster[:, u])
        if len(t) >= 10:
            d = np.diff(t)
            cvs.append(d.std() / d.mean())
    return cvs


def main():
    real = read_real()
    last_real = max(t for t, _, _ in real)
    pairs = [(p, tau) for _, p, tau in real]
    rate = len(real) / (last_real - min(t for t, _, _ in real))
    print(f"TEST B: {len(real)} events, last tick {last_real}, rate {rate:.4f}/tick")
    configs = [(0, 0), (0, 1), (0.30, 0), (0.30, 1)]

    print("\n== T1 silence (no input for ticks 0..19999) ==")
    for eta, k4 in configs:
        ev = [(20000, 0, 35)]  # single event only to set sim length
        ticks, ras, k4r = run("silence", ev, eta, k4)
        pre = ras[ticks < 20000]
        k4act = 0 if k4r is None else int(((k4r[:, 0] < 20000) & (k4r[:, 1] > 0)).sum())
        print(f"  eta={eta:<4} k4={k4}: spikes before input = {int(pre.sum())}, "
              f"K4 active rows before input = {k4act}")

    print("\n== T2 drive then stop (real input, then silence to tick 40000) ==")
    for eta, k4 in configs:
        ev = list(real) + [(40000, 0, 35)]
        ticks, ras, k4r = run("drivestop", ev, eta, k4)
        during = ras[ticks <= last_real]
        after = ras[(ticks > last_real) & (ticks < 40000)]
        after_ticks = ticks[(ticks > last_real) & (ticks < 40000)]
        last_spike_after = (after_ticks[after.sum(1) > 0].max() - last_real
                            if after.sum() else None)
        if k4r is not None:
            m = (k4r[:, 0] > last_real) & (k4r[:, 0] < 40000) & (k4r[:, 1] > 0)
            k4_after = int(m.sum())
            k4_last = int(k4r[m, 0].max() - last_real) if m.any() else None
        else:
            k4_after, k4_last = 0, None
        print(f"  eta={eta:<4} k4={k4}: spikes during={int(during.sum())}, "
              f"after={int(after.sum())} (last at +{last_spike_after} ticks); "
              f"K4 active rows after={k4_after} (last at +{k4_last})")

    print("\n== T3 Poisson noise input (60,000 ticks, 10 seeds) ==")
    T = 60000
    for eta, k4 in configs:
        in_pr, out_pr, out_per, in_per, cvs_all, nspk = [], [], [], [], [], []
        ctrl_pr = []
        for seed in range(10):
            rng = np.random.default_rng(seed)
            n = rng.poisson(rate * T)
            times = np.sort(rng.integers(1, T, size=n))
            sel = rng.integers(0, len(pairs), size=n)
            ev = [(int(t), pairs[s][0], pairs[s][1]) for t, s in zip(times, sel)]
            ticks, ras, _ = run(f"noise{seed}", ev, eta, k4)
            inp = np.zeros(T + 1)
            np.add.at(inp, times, 1)
            pop = ras.sum(1).astype(float)
            pr_i, per_i = smooth_spectrum_peak(inp)
            pr_o, per_o = smooth_spectrum_peak(pop)
            # control: same number of output spikes at random times
            ctrl = np.zeros_like(pop)
            np.add.at(ctrl, rng.integers(0, len(pop), size=int(pop.sum())), 1)
            pr_c, _ = smooth_spectrum_peak(ctrl)
            in_pr.append(pr_i); out_pr.append(pr_o); ctrl_pr.append(pr_c)
            out_per.append(per_o); in_per.append(per_i)
            cvs_all += isi_cv(ras)
            nspk.append(int(pop.sum()))
        print(f"  eta={eta:<4} k4={k4}: out spikes/seed ~{int(np.mean(nspk))}; "
              f"peak/median power: input {np.mean(in_pr):.1f}, output {np.mean(out_pr):.1f}, "
              f"random-time control {np.mean(ctrl_pr):.1f}; "
              f"output peak period (ticks) per seed {[round(p) for p in out_per]}; "
              f"unit ISI CV median {np.median(cvs_all) if cvs_all else float('nan'):.2f} "
              f"(n={len(cvs_all)})")


if __name__ == "__main__":
    main()
