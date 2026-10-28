"""FDM hikayesi: makale/sunum kalitesinde 3 panelli ozet grafigi.

Panel 1 (raster): R1 superpoze 4+12 — dolgun event isaretleri + arka planda
  ideal nabiz pencereleri (axvspan, alpha~0.1): mavi = 4'luk nabizlar,
  turuncu = 12'lik nabizlar. Ateslerin pencerelere kilitlenmesi gorulur.
Panel 2 (faz dagilimi): havuz histogrami + dairesel KDE egrisi (Gaussian
  cekirdek, sarmal mesafeli) + faz merkezi (kalin kesik dikey cizgi).
  Seaborn 'deep' paleti (seaborn kurulu degil; hex degerleri gomulu).
Panel 3 (D9 faz sifreleme): ideal dogru (gri, kalin kesik) + olculen
  merkezler (yesil) + yayilim hata bandi (fill_between; yayilim ~0.01 tick
  oldugundan bant ince cikar — bu iyi haberdir, not olarak yazilir) +
  buyuk maks-hata vurgusu.

Yalnizca matplotlib+numpy (ek bagimlilik yok). dpi=300.
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

# Seaborn 'deep' paleti (kod karsiliklari):
DEEP_BLUE = "#4C72B0"
DEEP_ORANGE = "#DD8452"
DEEP_GREEN = "#55A868"
LIGHT_BLUE = "#A8C3E8"
LIGHT_ORANGE = "#F2C19B"

ev = list(csv.DictReader(open("fdm_events.csv")))
ds = list(csv.DictReader(open("fdm_dshift.csv")))

fig, ax = plt.subplots(1, 3, figsize=(21, 7))
fig.suptitle("FDM: Simultane Demux (PLIR + Populasyon + Faz Kilidi)",
             fontsize=18, fontweight="bold", y=0.99)

# ================= Panel 1: raster + ideal nabiz pencereleri =================
TWIN = 300
HALF_WIN = 2.0  # ideal nabiz penceresi: nabiz +-2 tick
for t in range(0, TWIN, 4):
    ax[0].axvspan(t - HALF_WIN, t + HALF_WIN, color=DEEP_BLUE, alpha=0.10,
                  linewidth=0, zorder=1)
for t in range(0, TWIN, 12):
    ax[0].axvspan(t - HALF_WIN, t + HALF_WIN, color=DEEP_ORANGE, alpha=0.13,
                  linewidth=0, zorder=1)

r1 = [r for r in ev if int(r["run"]) == 1 and int(r["tick"]) < TWIN]
for tau, col, off, lab in [(4, DEEP_BLUE, 0, "bant-4 (tau=4)"),
                           (12, DEEP_ORANGE, 10, "bant-12 (tau=12)")]:
    tx = [int(r["tick"]) for r in r1 if int(r["band_tau"]) == tau]
    ty = [int(r["member"]) + off for r in r1 if int(r["band_tau"]) == tau]
    ax[0].plot(tx, ty, "|", color=col, markersize=14, markeredgewidth=2.6,
               linestyle="None", label=lab, zorder=3)
ax[0].plot([], [], "|", color="gray", markersize=0,
           label="acik zemin: ideal nabiz penceresi")
ax[0].set_xlabel("tick", fontsize=14)
ax[0].set_ylabel("uye (0-7: bant-4, 10-17: bant-12)", fontsize=13)
ax[0].set_title("Superpoze Kilitlenme: iki bant, tek tel", fontsize=15,
                fontweight="bold")
ax[0].set_xlim(0, TWIN)
ax[0].set_ylim(-1, 18)
ax[0].tick_params(labelsize=11)
ax[0].legend(fontsize=11, loc="upper right")


def circular_kde(fires, tau, grid, bw=0.6):
    """Dairesel KDE: sarmal mesafeli Gaussian cekirdek, sayim olceginde."""
    fires = np.mod(np.asarray(fires, dtype=float), tau)
    d = np.abs(grid[None, :] - fires[:, None])
    d = np.minimum(d, tau - d)
    dens = np.exp(-0.5 * (d / bw) ** 2).sum(axis=0)
    dens *= len(fires) / (dens.sum() * (grid[1] - grid[0]))
    return dens


# ================= Panel 2: faz histogrami + KDE + merkez =================
for tau, col in [(4, DEEP_BLUE), (12, DEEP_ORANGE)]:
    bins = np.array([int(r["bin"]) for r in r1 if int(r["band_tau"]) == tau])
    h, edges = np.histogram(bins, bins=np.arange(tau + 1))
    xc = (edges[:-1] + edges[1:]) / 2
    ax[1].bar(xc, h, width=0.7, color=col, edgecolor="black", linewidth=1.2,
              alpha=0.75, label=f"tau={tau} (histogram)", zorder=2)
    grid = np.linspace(0, tau, 400, endpoint=False)
    kde = circular_kde(bins, tau, grid)
    ax[1].plot(grid, kde, color=col, linewidth=3.0,
               label=f"tau={tau} (KDE)", zorder=4)
    # Faz merkezi: dairesel ortalama
    ang = 2 * np.pi * bins / tau
    center = float(np.angle(np.exp(1j * ang).mean()) / (2 * np.pi) * tau % tau)
    top = h.max()
    ax[1].plot([center, center], [0, top * 1.12], color=col, linestyle="--",
               linewidth=3.0, zorder=5)
    ax[1].text(center, top * 1.16, f"merkez {center:.2f}", ha="center",
               fontsize=11, fontweight="bold", color=col)
ax[1].set_xlabel("faz bolmesi (t mod tau)", fontsize=14)
ax[1].set_ylabel("havuz ates sayisi (ilk 300 tick)", fontsize=13)
ax[1].set_title("Kilit Dagilimi: histogram + KDE + merkez", fontsize=15,
                fontweight="bold")
ax[1].tick_params(labelsize=11)
ax[1].legend(fontsize=11, loc="upper right")

# ================= Panel 3: D9 faz sifreleme + hata bandi =================
D = np.array([float(r["D"]) for r in ds])
C = np.array([float(r["center"]) for r in ds])
SP = np.array([float(r["member_spread"]) for r in ds])
base = C[0]
ideal = base + D
ax[2].plot(D, ideal, color="gray", linestyle="--", linewidth=3.0,
           label="ideal (y = x)", zorder=2)
ax[2].fill_between(D, C - SP, C + SP, color=DEEP_GREEN, alpha=0.25,
                   label="uye yayilimi bandi", zorder=2)
ax[2].plot(D, C, "o", color=DEEP_GREEN, markersize=11,
           markeredgecolor="black", markeredgewidth=1.5,
           label="olculen merkez", zorder=4)
for d, c in zip(D, C):
    ax[2].text(d, c + 0.18, f"{c:.2f}", ha="center", fontsize=11,
               fontweight="bold", color="#2E7D32")
err = np.abs((C - base - D + 4.5) % 9 - 4.5)
ax[2].text(0.04, 0.94, f"Maks hata: {err.max():.2f} tick",
           transform=ax[2].transAxes, fontsize=15, fontweight="bold",
           color="#1B5E20", va="top", ha="left",
           bbox=dict(boxstyle="round,pad=0.4", facecolor="#E8F5E9",
                     edgecolor="#2E7D32", linewidth=1.5))
ax[2].text(0.04, 0.83, "yayilim ~0.01 tick:\nbant cizgi kadar ince",
           transform=ax[2].transAxes, fontsize=11, va="top", ha="left",
           color="#333333")
ax[2].set_xlabel("D9 (giris gecikmesi, tick)", fontsize=14)
ax[2].set_ylabel("populasyon faz merkezi (tick)", fontsize=13)
ax[2].set_title("Faz Sifreleme: giris gecikmesi fazda okunur", fontsize=15,
                fontweight="bold")
ax[2].tick_params(labelsize=11)
ax[2].legend(fontsize=11, loc="lower right")

fig.tight_layout()
fig.savefig("fdm_simultaneous.png", dpi=300)
print("yazildi: fdm_simultaneous.png (dpi=300)")
print(f"R1 olay: {len(r1)} (ilk 300 tick)")
print(f"D9 hata: maks {err.max():.2f} tick, yayilim maks {SP.max():.3f} tick")
