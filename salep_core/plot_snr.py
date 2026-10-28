"""SNR merdiven grafigi (STIMULUS_SNR_SPEC.md A0).

Girdi: stress_out_snr/snr_ensemble.csv + snr_gates.json.
Cikti: stress_out_snr/snr_ladder.png (katman merdiveni + kapi cizgileri;
eski vs yeni kuraklik yan yana).
"""
import csv
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(ROOT, "stress_out_snr")
FEATS = ["ec_mean", "tn_mean", "ch0_n", "ch1_bdays", "cable_n", "lob_n",
         "effD"]


def main():
    rows = list(csv.DictReader(
        open(os.path.join(OUTD, "snr_ensemble.csv"))))
    gates = json.load(open(os.path.join(OUTD, "snr_gates.json")))["snr"]
    scens = [s for s in ("dryold", "drynew") if s in gates]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), sharey=False)
    for ax, sc in zip(axes, scens):
        vals = []
        for k in FEATS:
            v = gates[sc][k]
            vals.append(min(v, 50) if v != float("inf") else 50)
        ax.bar(FEATS, vals)
        ax.axhline(10, linestyle="--", label="G-SNR kapi (10)")
        ax.set_xticks(range(len(FEATS)))
        ax.set_xticklabels(FEATS, rotation=45, ha="right", fontsize=8)
        ax.set_title(f"SNR({sc}) — inf=50 kirpildi")
        ax.legend(fontsize=8)
    fig.suptitle("Uyaran merdiveni: eski (bos) vs fiziksel kuraklik")
    fig.tight_layout()
    fig.savefig(os.path.join(OUTD, "snr_ladder.png"), dpi=100)
    print("OZET-PLOT: snr_ladder.png")


if __name__ == "__main__":
    main()
