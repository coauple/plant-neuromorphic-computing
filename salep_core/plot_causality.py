"""Nedensellik hikayesi: 3 panelli ozet grafigi.

NOT: seaborn ortama kurulu degil; ayni whitegrid gorunumu matplotlib'in
gomulu 'seaborn-v0_8-whitegrid' stiliyle elde ediliyor (ek bagimlilik yok).

Panel 1: faz basina toplam target atesi (bar) + 2.11x amplifikasyon oku.
Panel 2: agirlik evrimi (cizgi) + faz blok golgelendirme; w1/w3 kesik cizgi.
Panel 3: s0/s2 toplam blok kazanclari, faz turune gore gruplu bar.
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

BLOCK = 500
N_SUPER = 20
PHASE_COLORS = ["#cfe3ff", "#d3f0d3", "#ffe3c2"]
PHASE_NAMES = ["F1\n(sadece Dal A)", "F2\n(sadece Dal B)", "F3\n(A+B eszamanli)"]

rows = list(csv.DictReader(open("causality_learning.csv")))
tick = np.array([int(r["tick"]) for r in rows])
phase = np.array([int(r["phase"]) for r in rows])
tgt = np.array([int(r["target_fired"]) for r in rows])
w = np.array([[float(r[f"w{i}"]) for r in rows] for i in range(4)])

# Panel 1 verisi
fires = [int(tgt[phase == ph + 1].sum()) for ph in range(3)]
base = fires[0] + fires[1]
ampl = fires[2] / base if base else float("nan")

# Panel 3 verisi: (super, faz) blogu bas/son agirlik farklarinin toplami
gains = np.zeros((4, 3))
for s in range(N_SUPER):
    for ph in range(3):
        m = (np.array([int(r["super"]) for r in rows]) == s) & (phase == ph + 1)
        idx = np.flatnonzero(m)
        if len(idx):
            for i in range(4):
                gains[i, ph] += w[i][idx[-1]] - w[i][idx[0]]

fig, ax = plt.subplots(1, 3, figsize=(18, 6))
fig.suptitle("Nedensellik Koprusu: Birliktelik Atesi ve Ogrenmeye Kazinmasi",
             fontsize=16, fontweight="bold")

# --- Panel 1: eszamanlilik amplifikasyonu ---
bars = ax[0].bar([0, 1, 2], fires,
                 color=["#5b8dd9", "#6fbf6f", "#e07b39"],
                 edgecolor="black", linewidth=1.2, width=0.6)
ax[0].set_xticks([0, 1, 2])
ax[0].set_xticklabels(PHASE_NAMES, fontsize=11)
ax[0].set_ylabel("Toplam target atesi", fontsize=12)
ax[0].set_title("Eszamanlilik Amplifikasyonu", fontsize=13, fontweight="bold")
for x, v in zip([0, 1, 2], fires):
    ax[0].text(x, v + 1.5, str(v), ha="center", fontsize=12,
               fontweight="bold")
ax[0].annotate(f"{ampl:.2f}x Amplifikasyon", xy=(2, fires[2]),
               xytext=(1.0, fires[2] + 22),
               fontsize=12, fontweight="bold", color="#b34a00", ha="center",
               arrowprops=dict(arrowstyle="->", color="#b34a00", lw=2))
ax[0].set_ylim(0, fires[2] + 35)

# --- Panel 2: agirliklarin evrimi ---
for s in range(N_SUPER):
    for ph in range(3):
        ax[1].axvspan((s * 3 + ph) * BLOCK, (s * 3 + ph + 1) * BLOCK,
                      color=PHASE_COLORS[ph], alpha=0.35, linewidth=0)
styles = ["-", "--", "-", "--"]
labels = ["s0 (P0->Dal A)", "s1 (negatif kontrol)", "s2 (P2->Dal B)",
          "s3 (negatif kontrol)"]
for i in range(4):
    ax[1].plot(tick, w[i], label=labels[i], linestyle=styles[i], linewidth=2)
ax[1].set_xlabel("tick", fontsize=12)
ax[1].set_ylabel("agirlik", fontsize=12)
ax[1].set_title("Agirliklarin Evrimi (F3 bloklarinda adim)", fontsize=13,
                fontweight="bold")
ax[1].legend(fontsize=10, loc="upper left")

# --- Panel 3: faz basina toplam kazanc (s0, s2) ---
x = np.arange(3)
bw = 0.35
ax[2].bar(x - bw / 2, gains[0], bw, label="s0 (P0->Dal A)", color="#2c6fbb",
          edgecolor="black")
ax[2].bar(x + bw / 2, gains[2], bw, label="s2 (P2->Dal B)", color="#2e9e4f",
          edgecolor="black")
ax[2].set_xticks(x)
ax[2].set_xticklabels(PHASE_NAMES, fontsize=11)
ax[2].set_ylabel("Toplam agirlik artisi (dw)", fontsize=12)
ax[2].set_title("Nedenselligin Kazinmasi: Faz 3 Patlamasi", fontsize=13,
                fontweight="bold")
ax[2].legend(fontsize=10)
for xi, v in zip(x - bw / 2, gains[0]):
    ax[2].text(xi, v + 0.008, f"{v:.3f}", ha="center", fontsize=10)
for xi, v in zip(x + bw / 2, gains[2]):
    if v > 0.001:
        ax[2].text(xi, v + 0.008, f"{v:.3f}", ha="center", fontsize=10)

fig.tight_layout()
fig.savefig("causality_learning.png", dpi=300)
print("yazildi: causality_learning.png (dpi=300)")
print(f"ates: F1={fires[0]} F2={fires[1]} F3={fires[2]} ampl={ampl:.2f}x")
print(f"s0 kazanc: F1={gains[0,0]:+.4f} F2={gains[0,1]:+.4f} "
      f"F3={gains[0,2]:+.4f}")
print(f"s2 kazanc: F1={gains[2,0]:+.4f} F2={gains[2,1]:+.4f} "
      f"F3={gains[2,2]:+.4f}")
