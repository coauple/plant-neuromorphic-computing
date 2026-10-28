#!/usr/bin/env python3
"""bench/check_stage1.py — TEST_PLAN H1-H4 kapıları (AŞAMA 1).
H1: aynı seed yeniden üretimi bit-bit aynı (wire/windows/events).
H2: etiket bütünlüğü %100 + olay-link tutarlılığı.
H3: 30 seed ortasında Y|X oranı p±0.1, sahte-Y oranı q±%50 bandında.
H4: çekirdek/main dosyalarında bench başlangıcından yeni değişiklik yok.
"""
import csv
import glob
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "bench", "results", "stage1")
fails = []


def check(name, cond, extra=""):
    print(f"  {'OK' if cond else 'BATTI'} {name} {extra}")
    if not cond:
        fails.append(name)


def h1():
    # Aynı seed iki kez: RESULTS'taki + /tmp'ye taze üretim bit-bit aynı olmalı.
    for args in (["demux", "--seed", "2000", "--out", "/tmp/h1_demux"],
                 ["sparse", "--seed", "2000", "--out", "/tmp/h1_sparse"]):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "bench", "gen.py")]
                           + args, capture_output=True)
        assert r.returncode == 0, f"uretim hatasi: {args}"
    pairs = [("demux_s2000_wire.csv", "/tmp/h1_demux_wire.csv"),
             ("demux_s2000_windows.csv", "/tmp/h1_demux_windows.csv"),
             ("sparse_s2000_events.csv", "/tmp/h1_sparse_events.csv")]
    ok = True
    for a, b in pairs:
        r = subprocess.run(["cmp", "-s", os.path.join(RES, a), b])
        ok = ok and (r.returncode == 0)
    check("H1-determinizm", ok)


def h2():
    ok = True
    for wp in sorted(glob.glob(os.path.join(RES, "demux_*_windows.csv"))):
        with open(wp) as f:
            for r in csv.DictReader(f):
                if int(r["t1"]) - int(r["t0"]) != 100:
                    ok = False
                lab = r["label"]
                if (("4" in lab) != (r["has4"] == "1")) or \
                   (("12" in lab) != (r["has12"] == "1")):
                    ok = False
    for ep in sorted(glob.glob(os.path.join(RES, "sparse_*_events.csv"))):
        with open(ep) as f:
            rows = list(csv.DictReader(f))
        xids = {int(r["link"]) for r in rows if r["kind"] == "X"}
        xtick = {int(r["link"]): int(r["tick"]) for r in rows if r["kind"] == "X"}
        for r in rows:
            if r["kind"] not in ("X", "Y"):
                ok = False
            if r["kind"] == "Y" and int(r["link"]) >= 0:
                if int(r["link"]) not in xids:
                    ok = False
                elif not (0 <= int(r["tick"]) - xtick[int(r["link"])] <= 8 + 2):
                    ok = False
    check("H2-etiket-butunlugu", ok)


def h3():
    # 30 seed (2000-2029) sparse meta'larından gerçekleşen oranlar.
    rs, fs = [], []
    for s in range(2000, 2030):
        meta = os.path.join(RES, f"sparse_s{s}_meta.txt")
        kv = dict(kv.split("=") for kv in open(meta).read().split())
        nx, nl, nf = int(kv["n_x"]), int(kv["n_linked"]), int(kv["n_fake"])
        rs.append(nl / nx)
        fs.append(nf / int(kv["ticks"]))
    import statistics as st
    rm, fm = st.mean(rs), st.mean(fs)
    p, q = 0.8, 0.002
    print(f"  BILGI Y|X ort={rm:.3f} (hedef {p}), sahte ort={fm:.4f} (hedef {q})")
    check("H3-oranlar", abs(rm - p) <= 0.1 and abs(fm - q) <= 0.5 * q,
          f"n=30")


def h4(stamp):
    out = subprocess.run(["find", os.path.join(ROOT, "src"),
                          "-newermt", "@" + stamp, "-type", "f"],
                         capture_output=True, text=True)
    touched = [l for l in out.stdout.splitlines() if l]
    check("H4-cekirdek-degisikligi-yok", not touched, str(touched[:3]))


if __name__ == "__main__":
    stamp = sys.argv[1] if len(sys.argv) > 1 else "0"
    h1()
    h2()
    h3()
    h4(stamp)
    print("OZET-STAGE1: " + ("OK" if not fails else "BATTI " + ",".join(fails)))
    sys.exit(1 if fails else 0)
