#!/usr/bin/env python3
"""
Salep Core — Sinaps Öğrenme Kuralı (Kuadratik Spike-Rate) Görselleştirme

synapse_learning.csv'yi okur, iki şeyi ayrı ayrı doğrulayan bir grafik üretir:
  (a) Büyüme: N0-N1 birlikte ateşlendikçe weight gerçekten artıyor mu?
  (b) Doygunluk: S bileşeni bir tavan koyuyor mu (runaway yok, weight < W_MAX)?

Kullanım:
  python3 plot_synapse.py synapse_learning.csv

Çıktı: synapse_learning.png
"""

import csv
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Proje palette'iyle tutarlı (bkz. plot_branch.py)
C_WEIGHT = "#2196F3"   # mavi — ana büyüklük
C_WMAX   = "#9E9E9E"   # gri — tavan referans çizgisi
C_DW     = "#FF9800"   # turuncu — değişim hızı
C_RPRE   = "#4CAF50"   # yeşil — N0 (pre) oranı
C_RPOST  = "#E91E63"   # pembe — N1 (post) oranı

W_MAX = 2.0


def read_csv(path):
    data = {"tick": [], "cycle": [], "r_pre": [], "r_post": [],
            "dw": [], "weight": []}
    with open(path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            data["tick"].append(int(row["tick"]))
            data["cycle"].append(int(row["cycle"]))
            data["r_pre"].append(int(row["r_pre"]))
            data["r_post"].append(int(row["r_post"]))
            data["dw"].append(float(row["dw"]))
            data["weight"].append(float(row["weight"]))
    return data


def per_cycle_stats(data):
    n_cycles = max(data["cycle"]) + 1
    mean_abs_dw = [0.0] * n_cycles
    counts = [0] * n_cycles
    weight_at_end = [0.0] * n_cycles
    for c, dw, w in zip(data["cycle"], data["dw"], data["weight"]):
        mean_abs_dw[c] += abs(dw)
        counts[c] += 1
        weight_at_end[c] = w
    mean_abs_dw = [s / n for s, n in zip(mean_abs_dw, counts)]
    return list(range(n_cycles)), mean_abs_dw, weight_at_end


def plot(data, out_path):
    cycles, mean_abs_dw, weight_at_end = per_cycle_stats(data)
    ticks = data["tick"]

    fig, axes = plt.subplots(3, 1, figsize=(13, 11))

    # --- Panel 1: (a) Büyüme — weight(t), tüm koşu ---
    ax1 = axes[0]
    ax1.plot(ticks, data["weight"], color=C_WEIGHT, lw=1.3, label="weight")
    ax1.axhline(y=W_MAX, color=C_WMAX, lw=1.2, ls="--", label=f"W_MAX = {W_MAX}")
    ax1.set_xlabel("Tick")
    ax1.set_ylabel("Sinaps ağırlığı")
    ax1.set_title("(a) Büyüme: N0-N1 tekrar tekrar birlikte ateşlendikçe weight artıyor mu?")
    ax1.legend(loc="lower right", fontsize=9)
    ax1.grid(True, alpha=0.3)

    # --- Panel 2: (b) Doygunluk — döngü başına ortalama |dw| (log ölçek) ---
    ax2 = axes[1]
    ax2.plot(cycles, mean_abs_dw, color=C_DW, marker="o", ms=4, lw=1.5,
              label="ortalama |dw| / tick (döngü içi)")
    ax2.set_yscale("log")
    ax2.set_xlabel("Döngü (cycle) indeksi")
    ax2.set_ylabel("Ortalama |dw| / tick (log)")
    ax2.set_title("(b) Doygunluk: S bileşeni öğrenme hızını sıfıra doğru bastırıyor mu?")
    ax2.legend(loc="upper right", fontsize=9)
    ax2.grid(True, alpha=0.3, which="both")

    # Metin kutusu: sayısal özet
    first_rate = mean_abs_dw[0]
    last_rate = mean_abs_dw[-1]
    final_w = weight_at_end[-1]
    ax2.text(0.02, 0.06,
              f"İlk döngü: {first_rate:.6f}  →  Son döngü: {last_rate:.6f}  "
              f"({first_rate / last_rate:.1f}x küçüldü)\n"
              f"Son weight: {final_w:.4f}  (W_MAX'ın %{100*final_w/W_MAX:.1f}'i)",
              transform=ax2.transAxes, fontsize=9, va="bottom",
              bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="gray", alpha=0.9))

    # --- Panel 3: Bağlam — r_pre / r_post ateşleme oranları (ilk 3 döngü) ---
    ax3 = axes[2]
    zoom_ticks = 1500  # ilk 3 döngü (500*3)
    ax3.plot(ticks[:zoom_ticks], data["r_pre"][:zoom_ticks], color=C_RPRE,
              lw=1.2, label="r_pre (N0 — hızlı ritim)")
    ax3.plot(ticks[:zoom_ticks], data["r_post"][:zoom_ticks], color=C_RPOST,
              lw=1.2, label="r_post (N1 — yavaş ritim)")
    ax3.set_xlabel("Tick (ilk 3 döngü — bağlam için)")
    ax3.set_ylabel("Pencere içi ateşleme sayısı")
    ax3.set_title("Bağlam: kayan pencere ateşleme oranları (RATE_WINDOW=30 tick)")
    ax3.legend(loc="upper right", fontsize=9)
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  → {out_path}")


if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "synapse_learning.csv"
    data = read_csv(csv_path)
    plot(data, csv_path.replace(".csv", ".png"))
