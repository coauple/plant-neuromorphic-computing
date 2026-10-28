"""Pertürbasyon bataryası grafiği: 4 panel zaman serisi (§9.45)."""
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

CORE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(CORE_DIR, "sim", "out", "perturb_battery.csv")
PNG = os.path.join(CORE_DIR, "perturb_battery.png")


def main():
    def _f(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    series = {}
    with open(CSV, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            s = series.setdefault(row["run"], {})
            s.setdefault("day", []).append(int(row["day"]))
            for k in ("soil_moisture", "wb", "leaf", "stress", "rh",
                      "soil_ec"):
                s.setdefault(k, []).append(_f(row.get(k, "")))

    fig, axes = plt.subplots(2, 3, figsize=(18, 9))
    panels = [("soil_moisture", "Toprak nemi (VWC %)"),
              ("wb", "Su gradyanı (wb)"),
              ("leaf", "Yaprak sağlığı"),
              ("stress", "Stres endeksi (yorum)"),
              ("rh", "Ortam RH (kova; boş=dış düğme)"),
              ("soil_ec", "Toprak EC (mS/cm)")]
    for ax, (key, title) in zip(axes.flat, panels):
        for name, s in sorted(series.items()):
            pts = [(d, v) for d, v in zip(s["day"], s[key])
                   if v is not None]
            if pts:
                ax.plot([p[0] for p in pts], [p[1] for p in pts],
                        marker="o", ms=3, label=name)
        ax.set_title(title)
        ax.set_xlabel("gün")
        ax.grid(True, alpha=0.3)
    axes[0, 0].legend(ncol=2, fontsize=7)
    fig.suptitle("Pertürbasyon bataryası — 24 hipotez, 25 koşu "
                 "(H6 ikizi + VPD + AMBIENT + tuz + RUN1-4 dahil)")
    fig.tight_layout()
    fig.savefig(PNG, dpi=150)
    print(f"yazıldı: {PNG}")


if __name__ == "__main__":
    main()
