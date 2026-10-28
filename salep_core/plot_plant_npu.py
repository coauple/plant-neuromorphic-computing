"""Bitki NPU ozet grafigi: Rail-F kilit + grounding + capraz Post7/8.

Girdi: plant_learning.csv + plant_conditions.csv + plant_dualrail.csv.
Cikti: plant_npu.png (3 panel, deep palet + whitegrid + dpi=300).

Panel 1 (Rail-F kilit): bant basina faz histogrami (ates tick mod tau) +
  konsantrasyon; 4 ve 12 icin ayri alt-paneller.
Panel 2 (Grounding): w(blok) egrileri (Post0/1/2, KOSULLANMA->TEST dikey
  ayrac + "sensorler kapali" etiketi); sag eksende CR skoru (TEST atesleri).
Panel 3 (Capraz + sensor profili): X1/X2 (Post7/8) agirlik egrileri w(tick,
  orneklenmis) + blok bazinda sensor ON profili (s_nem/s_ec/s_sic ortalamasi).
Diger PNG'lere dokunulmaz.
"""
import csv

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

try:
    plt.style.use("seaborn-v0_8-whitegrid")
except OSError:
    plt.style.use("ggplot")

# deep palet (seaborn-deep esdegeri, sabit)
DEEP = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3",
        "#937860", "#DA8BC3", "#8C8C8C", "#CCB974", "#64B5CD"]

learn = list(csv.DictReader(open("plant_learning.csv")))
cond = list(csv.DictReader(open("plant_conditions.csv")))
dual = list(csv.DictReader(open("plant_dualrail.csv")))

tick = np.array([int(r["tick"]) for r in learn])
fb4 = np.array([int(r["fire_b4"]) for r in learn])
fb12 = np.array([int(r["fire_b12"]) for r in learn])

POST_NAMES = ["Post0 [NEM]", "Post1 [EC]", "Post2 [SIC]"]
POST_COLORS = [DEEP[0], "#999999", DEEP[1]]

# --- Panel 1 verisi: faz histogramlari (uye ates havuzu) ---
hist4 = np.zeros(4)
for t, c in zip(tick, fb4):
    hist4[t % 4] += c
hist12 = np.zeros(12)
for t, c in zip(tick, fb12):
    hist12[t % 12] += c
conc4 = hist4.max() / hist4.sum() if hist4.sum() else 0.0
conc12 = hist12.max() / hist12.sum() if hist12.sum() else 0.0

# --- Panel 2 verisi: w(blok) + CR ---
nblocks = 13  # 10 kosullanma + 3 test
w = np.zeros((3, nblocks))
fires_blk = np.zeros((3, nblocks), dtype=int)
for r in cond:
    s, b, k = int(r["stage"]), int(r["block"]), int(r["post"])
    idx = b if s == 0 else 10 + b
    w[k, idx] = float(r["w_end"])
    fires_blk[k, idx] = int(r["fires"])
dw_cond = w[:, 9] - 0.2
cr = fires_blk[:, 10:].sum(axis=1)

# --- Panel 3 verisi: capraz X1/X2 + sensor profili ---
BLK = 500
ntot = len(learn)
nb = ntot // BLK
t_blk = np.arange(nb)
w7 = np.array([float(r["w7"]) for r in dual])
w8 = np.array([float(r["w8"]) for r in dual])
w7_blk = w7[:nb * BLK].reshape(nb, BLK).mean(axis=1)
w8_blk = w8[:nb * BLK].reshape(nb, BLK).mean(axis=1)
f7_blk = np.array([int(r["p7_fired"]) for r in dual])[:nb * BLK].reshape(nb, BLK).sum(axis=1)
f8_blk = np.array([int(r["p8_fired"]) for r in dual])[:nb * BLK].reshape(nb, BLK).sum(axis=1)
s_nem = np.array([int(r["s_nem"]) for r in learn])[:nb * BLK].reshape(nb, BLK).mean(axis=1)
s_ec = np.array([int(r["s_ec"]) for r in learn])[:nb * BLK].reshape(nb, BLK).mean(axis=1)
s_sic = np.array([int(r["s_sic"]) for r in learn])[:nb * BLK].reshape(nb, BLK).mean(axis=1)
dw_x1 = w7_blk[-1] - 0.2
dw_x2 = w8_blk[-1] - 0.2

fig = plt.figure(figsize=(18, 11))
fig.suptitle("Bitki NPU: Rail-F Kilit + Grounding + Capraz Post7/8",
             fontsize=16, fontweight="bold")
gs = fig.add_gridspec(2, 2, height_ratios=[1, 1], hspace=0.45, wspace=0.25)

# --- Panel 1: Rail-F kilit haritasi ---
from matplotlib.gridspec import GridSpecFromSubplotSpec
inner = GridSpecFromSubplotSpec(2, 1, subplot_spec=gs[0, 0], hspace=0.55)
a41 = fig.add_subplot(inner[0])
a41.bar(np.arange(4), hist4, color=DEEP[0], edgecolor="black")
a41.set_xticks(np.arange(4))
a41.set_xlabel("faz (tick mod 4)")
a41.set_ylabel("havuz atesi")
a41.set_title(f"Rail-F Bant-4 kilit (conc={conc4:.2f})", fontweight="bold")
a12 = fig.add_subplot(inner[1])
a12.bar(np.arange(12), hist12, color=DEEP[2], edgecolor="black")
a12.set_xticks(np.arange(12))
a12.set_xlabel("faz (tick mod 12)")
a12.set_ylabel("havuz atesi")
a12.set_title(f"Rail-F Bant-12 kilit (conc={conc12:.2f})", fontweight="bold")

# --- Panel 2: grounding kazanma ---
ax2 = fig.add_subplot(gs[0, 1])
for k in range(3):
    style = "--" if k == 1 else "-"
    ax2.plot(np.arange(nblocks), w[k], label=POST_NAMES[k],
             color=POST_COLORS[k], linestyle=style, linewidth=2,
             marker="o", markersize=3)
ax2.axvline(9.5, color="red", linestyle=":", linewidth=2)
ax2.text(9.5, w.max() * 1.01,
         "sensorler kapali", color="red", fontsize=11, ha="center",
         va="bottom", fontweight="bold")
ax2.set_xlabel("blok (0-9 kosullanma, 10-12 test)", fontsize=12)
ax2.set_ylabel("agirlik w", fontsize=12)
ax2.set_title("Grounding Kazanma (Post0/1/2)", fontsize=13, fontweight="bold")
ax2.legend(fontsize=10, loc="upper left")
for k in range(3):
    ax2.text(12.1, w[k, -1], f"dw={dw_cond[k]:+.2f}", color=POST_COLORS[k],
             fontsize=10, va="center", fontweight="bold")
ax2.set_xlim(-0.5, 16.2)

ax2r = ax2.twinx()
bars = ax2r.bar([13.8, 14.4, 15.0], cr, width=0.5,
                color=POST_COLORS, edgecolor="black", alpha=0.55)
ax2r.set_ylabel("CR skoru (TEST atesleri)", fontsize=12)
ax2r.set_xticks([13.8, 14.4, 15.0])
ax2r.set_xticklabels(["NEM", "EC", "SIC"], fontsize=10)
for xi, v in zip([13.8, 14.4, 15.0], cr):
    ax2r.text(xi, v + 1.5, str(int(v)), ha="center", fontsize=11,
              fontweight="bold")

# --- Panel 3: capraz X1/X2 + sensor profili ---
ax3 = fig.add_subplot(gs[1, :])
ax3.plot(t_blk, w7_blk, label=f"X1 (Post7<-HN) dw={dw_x1:+.2f}",
         color=DEEP[4], linewidth=2, marker="o", markersize=3)
ax3.plot(t_blk, w8_blk, label=f"X2 (Post8<-HS) dw={dw_x2:+.2f}",
         color=DEEP[3], linewidth=2, marker="s", markersize=3)
ax3.axvline(9.5, color="red", linestyle=":", linewidth=2)
ax3.set_xlabel("blok (0-9 kosullanma, 10-12 test)", fontsize=12)
ax3.set_ylabel("capraz agirlik w", fontsize=12)
ax3.set_title("Capraz Post7/8 (X1/X2) + Sensor Profili", fontsize=13,
              fontweight="bold")
ax3.set_xlim(-0.5, nb - 0.5)

ax3r = ax3.twinx()
ax3r.plot(t_blk, s_nem, label="s_nem ON-oran", color=DEEP[0],
          linestyle="--", linewidth=1.5)
ax3r.plot(t_blk, s_ec, label="s_ec ON-oran", color="#999999",
          linestyle="--", linewidth=1.5)
ax3r.plot(t_blk, s_sic, label="s_sic ON-oran", color=DEEP[1],
          linestyle="--", linewidth=1.5)
ax3r.set_ylabel("sensor ON orani (blok ort.)", fontsize=12)
ax3r.set_ylim(-0.05, 1.05)
h1, l1 = ax3.get_legend_handles_labels()
h2, l2 = ax3r.get_legend_handles_labels()
ax3r.legend(h1 + h2, l1 + l2, fontsize=9, loc="center right")

fig.subplots_adjust(top=0.92, bottom=0.07, left=0.06, right=0.94,
                    hspace=0.55, wspace=0.30)
fig.savefig("plant_npu.png", dpi=300)
print("yazildi: plant_npu.png (dpi=300, 3 panel)")
print(f"kilit: conc4={conc4:.2f} conc12={conc12:.2f}")
for k in range(3):
    print(f"{POST_NAMES[k]}: dw_kosullanma={dw_cond[k]:+.4f} CR={int(cr[k])}")
print(f"X1: dw={dw_x1:+.4f} toplam_ates={int(f7_blk.sum())} | "
      f"X2: dw={dw_x2:+.4f} toplam_ates={int(f8_blk.sum())}")
