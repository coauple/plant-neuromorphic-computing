#!/usr/bin/env python3
"""bench/stage3_aggregate.py — ızgara toplama + yarı-AUC noktası (AŞAMA 3)."""
import csv
import glob
import os
import statistics as st
import sys

G = sys.argv[1]
cells = []
for auc in sorted(glob.glob(os.path.join(G, "p*_j*", "auc.csv"))):
    cell = os.path.basename(os.path.dirname(auc))
    p = int(cell.split("_")[0][1:])
    j = int(cell.split("_")[1][1:])
    rows = list(csv.DictReader(open(auc)))
    for m in ("S", "B1", "B2", "B3", "B4"):
        for t in ("4", "12"):
            v = [float(r["auc"]) for r in rows
                 if r["method"] == m and r["tau"] == t]
            cells.append((p, j, m, t, st.mean(v),
                          st.stdev(v) if len(v) > 1 else 0.0, len(v)))
with open(os.path.join(G, "grid_auc.csv"), "w") as f:
    f.write("pextra,jit,method,tau,mean,std,n\n")
    for p, j, m, t, mu, sd, n in cells:
        f.write(f"{p},{j},{m},{t},{mu:.6f},{sd:.6f},{n}\n")

# Yarı-AUC: temiz (0,0) ortalamasının yarısının altına düşen ilk seviye,
# her eksende diğeri 0 iken. Nokta-tahmini + o hücrenin GA'sı raporlanır.
print("== yari-AUC noktalari (eksen-basina) ==")
for m in ("S", "B1", "B2", "B3", "B4"):
    for t in ("4", "12"):
        base = next(c[4] for c in cells
                    if c[0] == 0 and c[1] == 0 and c[2] == m and c[3] == t)
        half = base / 2
        hp = next((c[0] for c in sorted(
            [c for c in cells if c[1] == 0 and c[2] == m and c[3] == t])
            if c[4] < half), None)
        hj = next((c[1] for c in sorted(
            [c for c in cells if c[0] == 0 and c[2] == m and c[3] == t],
            key=lambda c: c[1]) if c[4] < half), None)
        print(f"  {m} tau{t}: temiz={base:.3f} yari-pextra={hp} yari-jit={hj}")
print("OK stage3-aggregate")
