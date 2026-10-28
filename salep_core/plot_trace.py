#!/usr/bin/env python3
"""
Salep Core — Tek Nöron Trace Görselleştirme (v2)

CSV dosyasını okur, 3 alt grafikte çizer:
  1) Voltajlar : root_v, child_v, soma_v + ateşleme dikey çizgileri
  2) Gating    : root_gating, child_gating
  3) Enjeksiyon: injected (0/1 basamak fonksiyonu)

Kullanım:
  python3 plot_trace.py neuron_trace.csv             # dense
  python3 plot_trace.py neuron_trace_event.csv       # event-driven (awake sütunlu)

Çıktı: <girdi_adı>.png (300 DPI)
"""

import csv
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# --- CSV oku ----------------------------------------------------------------

csv_path = sys.argv[1] if len(sys.argv) > 1 else "neuron_trace.csv"

ticks        = []
root_v       = []
child_v      = []
root_gating  = []
child_gating = []
soma_v       = []
fire_ticks   = []
inject_ticks = []
awake_signal = []  # event-driven CSV'de var, dense'de yok

with open(csv_path, "r") as f:
    reader = csv.DictReader(f)
    has_awake = "awake" in reader.fieldnames
    for row in reader:
        t = int(row["tick"])
        ticks.append(t)
        root_v.append(float(row["root_v"]))
        child_v.append(float(row["child_v"]))
        root_gating.append(float(row["root_gating"]))
        child_gating.append(float(row["child_gating"]))
        soma_v.append(float(row["soma_v"]))
        if int(row["fired"]) == 1:
            fire_ticks.append(t)
        if int(row["injected"]) == 1:
            inject_ticks.append(t)
        if has_awake:
            awake_signal.append(int(row["awake"]))

# --- Grafik ------------------------------------------------------------------

n_panels = 4 if has_awake else 3
height_ratios = [3, 2, 1, 1] if has_awake else [3, 2, 1]
fig, axes = plt.subplots(n_panels, 1, figsize=(14, 3 * n_panels),
                          sharex=True, gridspec_kw={"height_ratios": height_ratios})

C_ROOT   = "#2196F3"
C_CHILD  = "#FF9800"
C_SOMA   = "#E91E63"
C_FIRE   = "#F44336"
C_GATE_R = "#4CAF50"
C_GATE_C = "#9C27B0"
C_INJ    = "#607D8B"
C_AWAKE  = "#00BCD4"

# Faz bölgeleri (güncellenmiş: Faz 3 artık 220-250)
phases = [(50, 80, "blue", "Faz 1"), (150, 180, "red", "Faz 2"), (220, 250, "green", "Faz 3")]

# ------ Voltajlar ------
ax1 = axes[0]
ax1.plot(ticks, child_v, color=C_CHILD, linewidth=1.2, label="child_v (distal)", alpha=0.85)
ax1.plot(ticks, root_v,  color=C_ROOT,  linewidth=1.2, label="root_v (proksimal)")
ax1.plot(ticks, soma_v,  color=C_SOMA,  linewidth=1.5, label="soma_v", linestyle="--")
ax1.axhline(y=1.0, color="gray", linewidth=0.8, linestyle=":", label="eşik (1.0)")

for ft in fire_ticks:
    ax1.axvline(x=ft, color=C_FIRE, linewidth=1.5, alpha=0.7,
                linestyle="-", label="spike" if ft == fire_ticks[0] else "")

ax1.set_ylabel("Voltaj (sabit nokta birim)")
mode_label = "Olay-Güdümlü" if has_awake else "Dense"
ax1.set_title(f"Salep Core — Tek Dendritik Nöron ({mode_label}, 500 tick)")
ax1.legend(loc="upper right", fontsize=8, ncol=3)
ax1.grid(True, alpha=0.3)

# ------ Gating ------
ax2 = axes[1]
ax2.plot(ticks, root_gating,  color=C_GATE_R, linewidth=1.2, label="root_gating")
ax2.plot(ticks, child_gating, color=C_GATE_C, linewidth=1.2, label="child_gating")
for ft in fire_ticks:
    ax2.axvline(x=ft, color=C_FIRE, linewidth=1.5, alpha=0.4, linestyle="-")
ax2.set_ylabel("Gating State")
ax2.legend(loc="upper right", fontsize=8)
ax2.grid(True, alpha=0.3)

# ------ Enjeksiyon ------
ax3 = axes[2]
injected_signal = [1 if t in inject_ticks else 0 for t in ticks]
ax3.fill_between(ticks, injected_signal, step="mid", alpha=0.5, color=C_INJ)
ax3.set_ylabel("Enjeksiyon")
ax3.set_yticks([0, 1])
ax3.set_yticklabels(["yok", "var"])
ax3.grid(True, alpha=0.3)

# ------ Uyanık/Uyku (sadece event-driven) ------
if has_awake:
    ax4 = axes[3]
    ax4.fill_between(ticks, awake_signal, step="mid", alpha=0.5, color=C_AWAKE)
    ax4.set_ylabel("Durum")
    ax4.set_yticks([0, 1])
    ax4.set_yticklabels(["uyku", "uyanık"])
    ax4.set_xlabel("Tick (ms)")
    ax4.grid(True, alpha=0.3)
else:
    ax3.set_xlabel("Tick (ms)")

# Faz bölgeleri + etiketler
for ax in axes:
    for start, end, color, _ in phases:
        ax.axvspan(start, end, alpha=0.06, color=color)

for start, end, color, label in phases:
    mid = (start + end) / 2
    ax1.text(mid, ax1.get_ylim()[1] * 0.92, label, ha="center", fontsize=8, color=color, alpha=0.7)

plt.tight_layout()
out_path = csv_path.replace(".csv", ".png")
plt.savefig(out_path, dpi=300, bbox_inches="tight")
print(f"Grafik kaydedildi: {out_path}")
