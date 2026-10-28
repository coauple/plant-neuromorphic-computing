#!/usr/bin/env python3
"""
Salep Core — Dallanma (Branching) Testi Görselleştirme

3 CSV dosyasını okur, her biri için 4 panelli grafik üretir:
  1) Voltajlar: root_v, branchA_v, branchB_v, soma_v + spike çizgileri
  2) Gating: root, branchA, branchB
  3) Enjeksiyon
  4) Eşzamanlılık (coincidence) durumu

Kullanım:
  python3 plot_branch.py branch_s1.csv branch_s2.csv branch_s3.csv

Çıktılar: branch_s1.png, branch_s2.png, branch_s3.png, branch_comparison.png
"""

import csv
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

# --- Renkler ---
C_ROOT   = "#2196F3"
C_BR_A   = "#FF9800"
C_BR_B   = "#4CAF50"
C_SOMA   = "#E91E63"
C_FIRE   = "#F44336"
C_GATE_R = "#2196F3"
C_GATE_A = "#FF9800"
C_GATE_B = "#4CAF50"
C_INJ    = "#607D8B"
C_COINC  = "#9C27B0"

# Faz bölgeleri
PHASES = [(50, 80, "blue", "Faz 1"), (150, 180, "red", "Faz 2"), (220, 250, "green", "Faz 3")]

SCENARIO_TITLES = {
    "branch_s1": "Senaryo 1: Sadece Dal A (faz dalı)",
    "branch_s2": "Senaryo 2: Sadece Dal B (sensör dalı)",
    "branch_s3": "Senaryo 3: Her iki dal (eşzamanlı)",
}

def read_csv(path):
    data = {"ticks":[], "root_v":[], "branchA_v":[], "branchB_v":[],
            "root_gating":[], "branchA_gating":[], "branchB_gating":[],
            "soma_v":[], "fire_ticks":[], "inject_ticks":[], "coincidence":[]}
    with open(path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            t = int(row["tick"])
            data["ticks"].append(t)
            data["root_v"].append(float(row["root_v"]))
            data["branchA_v"].append(float(row["branchA_v"]))
            data["branchB_v"].append(float(row["branchB_v"]))
            data["root_gating"].append(float(row["root_gating"]))
            data["branchA_gating"].append(float(row["branchA_gating"]))
            data["branchB_gating"].append(float(row["branchB_gating"]))
            data["soma_v"].append(float(row["soma_v"]))
            if int(row["fired"]) == 1:
                data["fire_ticks"].append(t)
            if int(row["injected"]) == 1:
                data["inject_ticks"].append(t)
            data["coincidence"].append(int(row["coincidence"]))
    return data


def plot_single(data, csv_path):
    """Tek senaryo için 4-panelli grafik."""
    base = csv_path.rsplit("/", 1)[-1].replace(".csv", "")
    title = SCENARIO_TITLES.get(base, base)

    fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=True,
                              gridspec_kw={"height_ratios": [3, 2, 1, 1]})
    ticks = data["ticks"]

    # Panel 1: Voltajlar
    ax1 = axes[0]
    ax1.plot(ticks, data["branchA_v"], color=C_BR_A, lw=1.2, label="Dal A (faz)", alpha=0.85)
    ax1.plot(ticks, data["branchB_v"], color=C_BR_B, lw=1.2, label="Dal B (sensör)", alpha=0.85)
    ax1.plot(ticks, data["root_v"],    color=C_ROOT, lw=1.2, label="root_v (kök)")
    ax1.plot(ticks, data["soma_v"],    color=C_SOMA, lw=1.5, label="soma_v", ls="--")
    ax1.axhline(y=1.0, color="gray", lw=0.8, ls=":", label="eşik (1.0)")
    for i, ft in enumerate(data["fire_ticks"]):
        ax1.axvline(x=ft, color=C_FIRE, lw=1.5, alpha=0.7,
                    label="spike" if i == 0 else "")
    ax1.set_ylabel("Voltaj")
    ax1.set_title(f"Salep Core — {title}")
    ax1.legend(loc="upper right", fontsize=8, ncol=3)
    ax1.grid(True, alpha=0.3)

    # Panel 2: Gating
    ax2 = axes[1]
    ax2.plot(ticks, data["root_gating"],    color=C_GATE_R, lw=1.2, label="root_gating")
    ax2.plot(ticks, data["branchA_gating"], color=C_GATE_A, lw=1.2, label="branchA_gating")
    ax2.plot(ticks, data["branchB_gating"], color=C_GATE_B, lw=1.2, label="branchB_gating")
    for ft in data["fire_ticks"]:
        ax2.axvline(x=ft, color=C_FIRE, lw=1.5, alpha=0.4)
    ax2.set_ylabel("Gating State")
    ax2.legend(loc="upper right", fontsize=8)
    ax2.grid(True, alpha=0.3)

    # Panel 3: Enjeksiyon
    ax3 = axes[2]
    inj_sig = [1 if t in data["inject_ticks"] else 0 for t in ticks]
    ax3.fill_between(ticks, inj_sig, step="mid", alpha=0.5, color=C_INJ)
    ax3.set_ylabel("Enjeksiyon")
    ax3.set_yticks([0, 1])
    ax3.set_yticklabels(["yok", "var"])
    ax3.grid(True, alpha=0.3)

    # Panel 4: Eşzamanlılık
    ax4 = axes[3]
    ax4.fill_between(ticks, data["coincidence"], step="mid", alpha=0.5, color=C_COINC)
    ax4.set_ylabel("Eşzamanlılık")
    ax4.set_yticks([0, 1])
    ax4.set_yticklabels(["yok", "var"])
    ax4.set_xlabel("Tick (ms)")
    ax4.grid(True, alpha=0.3)

    # Faz bölgeleri
    for ax in axes:
        for start, end, color, _ in PHASES:
            ax.axvspan(start, end, alpha=0.06, color=color)
    for start, end, color, label in PHASES:
        mid = (start + end) / 2
        ax1.text(mid, ax1.get_ylim()[1] * 0.92, label, ha="center", fontsize=8, color=color, alpha=0.7)

    plt.tight_layout()
    out = csv_path.replace(".csv", ".png")
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  → {out}")
    return data


def plot_comparison(all_data, csv_paths):
    """3 senaryonun soma_v'sini yan yana karşılaştır."""
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True, sharey=True)

    labels = ["Senaryo 1: Sadece Dal A", "Senaryo 2: Sadece Dal B", "Senaryo 3: İkisi birden"]
    colors = [C_BR_A, C_BR_B, C_COINC]

    for i, (data, label, color) in enumerate(zip(all_data, labels, colors)):
        ax = axes[i]
        ticks = data["ticks"]
        ax.plot(ticks, data["soma_v"], color=color, lw=1.5, label=f"soma_v ({label})")
        ax.axhline(y=1.0, color="gray", lw=0.8, ls=":")
        for ft in data["fire_ticks"]:
            ax.axvline(x=ft, color=C_FIRE, lw=1.5, alpha=0.7)
        ax.set_ylabel("Soma Voltajı")
        ax.set_title(label)
        ax.grid(True, alpha=0.3)

        # Faz bölgeleri
        for start, end, c, _ in PHASES:
            ax.axvspan(start, end, alpha=0.06, color=c)

        # Ateşleme sayısı ve ilk ateşleme tick'i
        fc = len(data["fire_ticks"])
        ff = data["fire_ticks"][0] if data["fire_ticks"] else -1
        ax.text(0.98, 0.92, f"Ateşleme: {fc}  |  İlk: tick {ff}",
                transform=ax.transAxes, ha="right", va="top", fontsize=9,
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.8))

    axes[-1].set_xlabel("Tick (ms)")
    fig.suptitle("Salep Core — Dallanma Eşzamanlılık Karşılaştırması", fontsize=14, y=1.01)
    plt.tight_layout()
    plt.savefig("branch_comparison.png", dpi=300, bbox_inches="tight")
    plt.close()
    print("  → branch_comparison.png")


# --- Main ---
if __name__ == "__main__":
    csv_files = sys.argv[1:] if len(sys.argv) > 1 else \
                ["branch_s1.csv", "branch_s2.csv", "branch_s3.csv"]

    print("Grafikler üretiliyor:")
    all_data = []
    for path in csv_files:
        d = plot_single(read_csv(path), path)
        all_data.append(d)

    if len(all_data) == 3:
        plot_comparison(all_data, csv_files)
    print("Tamamlandı.")
