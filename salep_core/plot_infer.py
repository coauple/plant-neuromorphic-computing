"""Çıkarım grafiği: D1-D3 tabakalı etkiler (§9.50)."""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

CORE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(CORE_DIR, "sim", "out", "infer_summary.csv")
PNG = os.path.join(CORE_DIR, "infer_interaction.png")


def main():
    s = pd.read_csv(CSV)
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # D1: tuzlu koşularda rejim-ortalaması stres (non-monotonluk dahil).
    salty = s[s.max_ec >= 2.0].copy()
    salty["regime"] = pd.cut(salty.mean_vpd, [-1e9, 1.2, 2.2, 1e9],
                             labels=["nemli", "orta", "kuru"])
    m1 = salty.groupby("regime", observed=True).final_stress.mean()
    axes[0].bar(list(m1.index), m1.values)
    axes[0].set_title("D1: tuzlu koşuda stres (VPD rejimi) — KEŞİF")
    axes[0].set_ylabel("final stres ortalaması")

    # D2: gübreli koşularda yağışa göre final EC.
    fert = s[s.total_fert > 0]
    cut = fert.total_rain.median()
    m2 = [fert[fert.total_rain <= cut].final_ec.mean(),
          fert[fert.total_rain > cut].final_ec.mean()]
    axes[1].bar(["az yağış", "çok yağış"], m2)
    axes[1].set_title("D2: gübreli koşuda final EC — KEŞİF")
    axes[1].set_ylabel("final EC ortalaması")

    # D3: sıcaklık üçlüsünde min nem.
    lo = s.nsmallest(max(10, len(s) // 3), "mean_temp").min_moist.mean()
    hi = s.nlargest(max(10, len(s) // 3), "mean_temp").min_moist.mean()
    axes[2].bar(["serin 1/3", "sıcak 1/3"], [lo, hi])
    axes[2].set_title("D3: serin kapanış daha ıslak — KEŞİF")
    axes[2].set_ylabel("min nem ortalaması")

    fig.suptitle("10.000 yörüngeden etkileşim keşfi (D1+D2+D3 KEŞİF)")
    fig.tight_layout()
    fig.savefig(PNG, dpi=150)
    print(f"yazıldı: {PNG}")


if __name__ == "__main__":
    main()
