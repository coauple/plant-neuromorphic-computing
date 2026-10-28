"""Duyusal Lob ozet grafigi: FAZ3 ogrenme + FAZ4 oz-orgutlenme + stres.

Girdi: sensory_lobe_learning.csv + sensory_selforg.csv +
  sensory_stress.csv + sensory_stress_hires.csv.
Cikti: sensory_lobe.png (4 panel, deep palet + whitegrid + dpi=300).

Panel 1 (FAZ3 agirlik): w0..w9(tick) egrileri (20'de 1 ornek) + KOSUL->TEST
  dikey ayraci.
Panel 2 (FAZ3 CR): p2fires bitmask + stage sutunundan TURETILEN
  kosullanma/test ates sayilari (uretilmis veri yok; log olcek).
Panel 3 (FAZ4 selforg): n_posts(tick) basamaklari + faz bantlari + n_posts
  sismelerinden cikarilan hire isaretleri (CSV ornekleme cozunurlugu 25).
Panel 4 (Stres): n_posts + 10 faz bandi + sensory_stress_hires.csv'deki
  TAM tick'li hire isaretleri (tau etiketli). Faz->ton listesi senaryo
  bilgisidir (ST_PH); senaryo degisirse bu yazi da guncellenir.
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

PNAMES = ["p2a", "p2b", "p2c", "p2d", "p2e",
          "p2f", "p2g", "p2h", "p2i", "p2j"]

learn = list(csv.DictReader(open("sensory_lobe_learning.csv")))
selforg = list(csv.DictReader(open("sensory_selforg.csv")))
stress = list(csv.DictReader(open("sensory_stress.csv")))
hires = list(csv.DictReader(open("sensory_stress_hires.csv")))

fig, ax = plt.subplots(2, 2, figsize=(14, 10))

# --- Panel 1: FAZ3 agirlik egrileri ---
lt = np.array([int(r["tick"]) for r in learn])
lst = np.array([int(r["stage"]) for r in learn])
step = 20
for k in range(10):
    w = np.array([float(r[f"w{k}"]) for r in learn])
    ax[0, 0].plot(lt[::step], w[::step], color=DEEP[k], lw=1.2,
                  label=PNAMES[k])
t_split = int(lt[lst == 1][0])
ax[0, 0].axvline(t_split, color="k", ls="--", lw=1)
ax[0, 0].text(t_split, 1.02, "KOSUL->TEST", transform= \
    ax[0, 0].get_xaxis_transform(), ha="center", va="bottom", fontsize=8)
ax[0, 0].set_title("FAZ3: P2 agirliklari w(tick)")
ax[0, 0].set_xlabel("tick")
ax[0, 0].set_ylabel("w")
ax[0, 0].legend(ncol=5, fontsize=8)

# --- Panel 2: FAZ3 CR (bitmask+stage'den turetilmis sayilar) ---
cond = np.zeros(10, dtype=float)
test = np.zeros(10, dtype=float)
for r in learn:
    bits = r["p2fires"]
    tgt = cond if int(r["stage"]) == 0 else test
    for k in range(10):
        if bits[k] == "1":
            tgt[k] += 1
print("CR turetilmis (kosullanma/test):")
for k in range(10):
    print(f"  {PNAMES[k]}: cond={int(cond[k])} test={int(test[k])}")
x = np.arange(10)
ax[0, 1].bar(x - 0.2, cond + 1, 0.4, color=DEEP[0], label="kosullanma")
ax[0, 1].bar(x + 0.2, test + 1, 0.4, color=DEEP[3], label="test (CR)")
ax[0, 1].set_yscale("log")
ax[0, 1].set_title("FAZ3: ates sayilari (log; +1)")
ax[0, 1].set_xlabel("post")
ax[0, 1].set_xticks(x)
ax[0, 1].set_xticklabels(PNAMES, fontsize=8)
ax[0, 1].legend(fontsize=8)

# --- Panel 3: FAZ4 selforg basamaklari ---
st = np.array([int(r["tick"]) for r in selforg])
sph = np.array([int(r["phase"]) for r in selforg])
snp = np.array([int(r["n_posts"]) for r in selforg])
for p in sorted(set(sph.tolist())):
    m = sph == p
    ax[1, 0].axvspan(st[m][0], st[m][-1] + 25,
                     color=DEEP[p - 1] if p <= len(DEEP) else "#EEEEEE",
                     alpha=0.18)
    ax[1, 0].text((st[m][0] + st[m][-1]) / 2, 14.6, f"F{p}", ha="center",
                  va="top", fontsize=9)
ax[1, 0].step(st, snp, where="post", color="k", lw=1.5)
for i in range(1, len(snp)):
    if snp[i] > snp[i - 1]:
        ax[1, 0].axvline(st[i], color=DEEP[3], ls=":", lw=1.2)
        ax[1, 0].text(st[i], snp[i] + 0.15, f"slot{snp[i]}", fontsize=8,
                      ha="left", va="bottom", color=DEEP[3])
ax[1, 0].set_title("FAZ4 selforg: n_posts (hire cozunurluk 25 tick)")
ax[1, 0].set_xlabel("tick")
ax[1, 0].set_ylabel("n_posts")
ax[1, 0].set_ylim(11.5, 15.2)

# --- Panel 4: stres basamaklari + tam hire isaretleri ---
rt = np.array([int(r["tick"]) for r in stress])
rph = np.array([int(r["phase"]) for r in stress])
rnp = np.array([int(r["n_posts"]) for r in stress])
for p in sorted(set(rph.tolist())):
    m = rph == p
    ax[1, 1].axvspan(rt[m][0], rt[m][-1] + 25, color=DEEP[(p - 1) % 10],
                     alpha=0.15)
    ax[1, 1].text((rt[m][0] + rt[m][-1]) / 2, 17.5, f"F{p}", ha="center",
                  va="top", fontsize=7)
ax[1, 1].step(rt, rnp, where="post", color="k", lw=1.5)
for h in hires:
    ht, htau, hslot = int(h["tick"]), int(h["tau"]), int(h["slot"])
    ax[1, 1].axvline(ht, color=DEEP[3], ls=":", lw=1.2)
    ax[1, 1].text(ht, hslot + 0.7, f"tau{htau}", fontsize=8, rotation=90,
                  ha="right", va="bottom", color=DEEP[3])
ax[1, 1].set_title("Stres: n_posts + hire (tam tick)")
ax[1, 1].set_xlabel("tick")
ax[1, 1].set_ylabel("n_posts")
ax[1, 1].set_ylim(11.5, 18.2)
fig.text(0.5, 0.01,
         "Fazlar: F1 bus{35} F2 +26 F3 +59 F4 +43 F5 +50 (5 ton) "
         "F6 bus{35} F7 sonda{26} F8 sonda{59} F9 sonda{43} F10 sonda{50}",
         ha="center", fontsize=8)

fig.tight_layout(rect=[0, 0.03, 1, 1])
fig.savefig("sensory_lobe.png", dpi=300)
print("sensory_lobe.png yazildi")
