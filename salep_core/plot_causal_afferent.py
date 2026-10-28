"""Afferent demo ozet grafigi: P2 olaylari -> nedensellik + tek-adim ongoru.

Girdi: causal_afferent_learning.csv.
Cikti: causal_afferent.png (4 panel, deep palet + whitegrid + dpi=300).

Panel 1 (Olaylar): faz bantlari + evX/evY/toplam-hedef ates adimlari.
Panel 2 (Ogrenme): w0/w2(tick) + faz bloklari.
Panel 3 (Ongoru): F3'te tahmin penceresi (pred) + Y olaylari.
Panel 4 (Zincir): ilk F3 blogunun ilk 300 tick'inde evX/pre0/evY/pre2/tgt
  raster (X->pre0->Y->pre2->tgt zinciri gozle gorulur).
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

DEEP = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3",
        "#937860", "#DA8BC3", "#8C8C8C", "#CCB974", "#64B5CD"]

rows = list(csv.DictReader(open("causal_afferent_learning.csv")))
tick = np.array([int(r["tick"]) for r in rows])
phase = np.array([int(r["phase"]) for r in rows])
evx = np.array([int(r["evX"]) for r in rows])
evy = np.array([int(r["evY"]) for r in rows])
pre0 = np.array([int(r["pre0"]) for r in rows])
pre2 = np.array([int(r["pre2"]) for r in rows])
tgt = np.array([int(r["tgt"]) for r in rows])
w0 = np.array([float(r["w0"]) for r in rows])
w2 = np.array([float(r["w2"]) for r in rows])
pred = np.array([int(r["pred"]) for r in rows])

SUPER = 3
BLOCK = 1000
PHNAMES = {1: "F1(X)", 2: "F2(Y)", 3: "F3(X+Y)"}

fig, ax = plt.subplots(2, 2, figsize=(14, 10))


def bands(a):
    t0 = 0
    for sup in range(SUPER):
        for ph in (1, 2, 3):
            t1 = t0 + BLOCK
            a.axvspan(t0, t1, color=DEEP[ph - 1], alpha=0.12)
            if sup == 0:
                a.text((t0 + t1) / 2, a.get_ylim()[1], PHNAMES[ph],
                       ha="center", va="top", fontsize=8)
            t0 = t1


# --- Panel 1: olaylar + hedef ---
bands(ax[0, 0])
ax[0, 0].step(tick, np.cumsum(evx), where="post", color=DEEP[0], lw=1.2,
              label="evX (kum)")
ax[0, 0].step(tick, np.cumsum(evy), where="post", color=DEEP[1], lw=1.2,
              label="evY (kum)")
ax[0, 0].step(tick, np.cumsum(tgt) * 10, where="post", color=DEEP[3],
              lw=1.2, label="hedef x10 (kum)")
ax[0, 0].set_title("Afferent: olaylar + hedef atesleri")
ax[0, 0].set_xlabel("tick")
ax[0, 0].legend(fontsize=8)

# --- Panel 2: agirliklar ---
bands(ax[0, 1])
ax[0, 1].plot(tick[::10], w0[::10], color=DEEP[0], lw=1.2, label="s0 (A)")
ax[0, 1].plot(tick[::10], w2[::10], color=DEEP[1], lw=1.2, label="s2 (B)")
ax[0, 1].set_title("Nedensellik: blok kazanclari w(tick)")
ax[0, 1].set_xlabel("tick")
ax[0, 1].set_ylabel("w")
ax[0, 1].legend(fontsize=8)

# --- Panel 3: ongoru penceresi (F3 super 0) ---
m3 = (phase == 3)
s0 = (tick >= 2000) & (tick < 3000)
ax[1, 0].fill_between(tick[s0], 0, 1.2, where=pred[s0] == 1,
                      color=DEEP[2], alpha=0.3, label="tahmin aktif")
ax[1, 0].eventplot(tick[s0 & (evy == 1)], lineoffsets=0.6, linelengths=0.5,
                   color=DEEP[3], label="Y olayi")
ax[1, 0].set_title("Ongoru: F3 penceresi + Y (super 0)")
ax[1, 0].set_xlabel("tick")
ax[1, 0].set_ylim(0, 1.2)
ax[1, 0].legend(fontsize=8)

# --- Panel 4: zincir raster (F3 super 0, ilk 300 tick) ---
z = (tick >= 2000) & (tick < 2300)
series = [(evx, "evX"), (pre0, "pre0"), (evy, "evY"), (pre2, "pre2"),
          (tgt, "tgt")]
for i, (s, name) in enumerate(series):
    ax[1, 1].eventplot(tick[z & (s == 1)], lineoffsets=i,
                       linelengths=0.7, color=DEEP[i])
ax[1, 1].set_yticks(range(5))
ax[1, 1].set_yticklabels([n for _, n in series], fontsize=8)
ax[1, 1].set_title("Zincir: X->pre0->Y->pre2->tgt (F3 ilk 300)")
ax[1, 1].set_xlabel("tick")

fig.tight_layout()
fig.savefig("causal_afferent.png", dpi=300)
print("causal_afferent.png yazildi")
