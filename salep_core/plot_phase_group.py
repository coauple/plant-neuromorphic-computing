"""Faz grubu sonuclari: faz izleri + ates rasteri + 4x4 secicilik haritasi."""
import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

CYCLE = 500
WINDOWS = [(50, 120), (150, 220), (250, 320), (350, 420)]
TAUS = [4, 8, 12, 16]

rows = list(csv.DictReader(open("phase_group_learning.csv")))
n = len(rows)
tick = np.array([int(r["tick"]) for r in rows])
pre = np.array([[int(r[f"p{i}_fired"]) for r in rows] for i in range(4)])
post = np.array([int(r["post_fired"]) for r in rows])
w = np.array([[float(r[f"w{i}"]) for r in rows] for i in range(4)])
va = np.array([[float(r[f"p{i}_branchA_v"]) for r in rows] for i in range(4)])

fig, ax = plt.subplots(4, 1, figsize=(12, 10))
# NOT: imshow (kategorik eksen) paylasimli x'i (-0.5, 3.5)'e sikistirip
# panelleri bos gosteriyordu; o yuzden isi haritasi bagimsiz. Panel 0
# (2 dongu yakin plan) bagimsiz; raster + agirlik tum kosuyu paylasir.
ax[1].sharex(ax[2])

# 1) Dal-A voltaj izleri (rezonans izleri, ilk 2 dongu)
m = tick < 2 * CYCLE
for i in range(4):
    ax[0].plot(tick[m], va[i][m], label=f"P{i} tau={TAUS[i]}", linewidth=1.4)
for a, b in WINDOWS:
    ax[0].axvspan(a, b, color="gray", alpha=0.12)
    ax[0].axvspan(a + CYCLE, b + CYCLE, color="gray", alpha=0.12)
ax[0].set_ylabel("Dal-A voltaji")
ax[0].set_xlim(0, 2 * CYCLE)  # rezonans izleri: ilk 2 dongu
ax[0].legend(ncol=4, fontsize=8)
ax[0].set_title("Faz grubu: rezonans izleri (2 dongu) + ates rasteri + agirliklar")

# 2) Ates rasteri (tum kosu)
for i in range(4):
    t = tick[pre[i] == 1]
    ax[1].scatter(t, np.full_like(t, 4 - i), s=14, label=f"P{i}")
t = tick[post == 1]
ax[1].scatter(t, np.full_like(t, 0), s=18, label="post", marker="x")
ax[1].set_yticks([0, 1, 2, 3, 4])
ax[1].set_yticklabels(["post", "P3", "P2", "P1", "P0"])
ax[1].set_ylabel("ates")
ax[1].legend(ncol=5, fontsize=8)

# 3) Agirliklar
for i in range(4):
    ax[2].plot(tick, w[i], label=f"syn[{i}]", linewidth=1.4)
ax[2].set_ylabel("agirlik")
ax[2].legend(ncol=4, fontsize=8)

# 4) 4x4 karisiklik matrisi (atis faz atamasi: pencere+30 pay)
conf = np.zeros((4, 4), dtype=int)
for r in rows:
    ct = int(r["tick"]) % CYCLE
    ph = 0 if ct < 150 else (1 if ct < 250 else (2 if ct < 350 else 3))
    for i in range(4):
        if int(r[f"p{i}_fired"]):
            conf[i, ph] += 1
im = ax[3].imshow(conf, cmap="Greens")
for i in range(4):
    for j in range(4):
        ax[3].text(j, i, str(conf[i, j]), ha="center", va="center")
ax[3].set_xticks(range(4))
ax[3].set_yticks(range(4))
ax[3].set_xticklabels([f"faz{j}" for j in range(4)])
ax[3].set_yticklabels([f"P{i} t={TAUS[i]}" for i in range(4)])
ax[3].set_title("Secicilik (satir=noron, sutun=faz)")
ax[3].set_ylabel("noron")
fig.colorbar(im, ax=ax[3], shrink=0.6)

fig.tight_layout()
fig.savefig("phase_group_learning.png", dpi=100)
print("yazildi: phase_group_learning.png")
print("karisiklik:\n", conf)
