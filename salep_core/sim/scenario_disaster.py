"""
Senaryo: "Kuraklıktan soldu, gübre verildi, EC fırladı, kökleri yandı."
Tek bitki üzerinde, yaz ortasında (doğal olarak zaten kurak) sulama YOK,
gün 110'da tek seferlik ağır gübre dozu enjekte ediliyor.

Bu dosya G2 doğrulama kapısının referans senaryosudur.
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")  # headless uyumlu
import matplotlib.pyplot as plt
from sim.plant_sim import run_population

SIM_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(SIM_DIR, "out")

DROUGHT_START, DROUGHT_END = 55, 115
FERTILIZER_DAY = 110  # kuraklığın sonuna doğru, toprak zaten kuruyken

scripted_events = {d: {"force_no_rain": True} for d in range(DROUGHT_START, DROUGHT_END)}
scripted_events[FERTILIZER_DAY] = {"force_no_rain": True, "fertilizer_dose_mass": 130.0}


def run_disaster(save=True):
    df = run_population(n_plants=1, n_days=200, seed=1, scripted_events=scripted_events)

    if save:
        os.makedirs(OUT_DIR, exist_ok=True)
        df.to_csv(os.path.join(OUT_DIR, "disaster_scenario.csv"), index=False)

    events = df[df["ground_truth_event"] != ""]
    print("Ground truth olaylar (NPU'ya verilmez, sadece doğrulama için):")
    print(events[["day", "ground_truth_event"]].to_string(index=False))

    fig, axes = plt.subplots(4, 1, figsize=(10, 11), sharex=True)

    axes[0].plot(df["day"], df["soil_moisture"], color="tab:blue")
    axes[0].axvspan(DROUGHT_START, DROUGHT_END, color="orange", alpha=0.15, label="kuraklık (yağmur zorla kesildi)")
    axes[0].axvline(FERTILIZER_DAY, color="red", ls="--", alpha=0.6, label="gübre dozu")
    axes[0].set_ylabel("Toprak nemi (%)")
    axes[0].legend(loc="upper right", fontsize=8)

    axes[1].plot(df["day"], df["soil_ec"], color="tab:orange")
    axes[1].axhline(3.4, color="red", ls=":", alpha=0.6, label="EC yanık eşiği")
    axes[1].axvline(FERTILIZER_DAY, color="red", ls="--", alpha=0.6)
    axes[1].set_ylabel("Toprak EC (mS/cm)")
    axes[1].legend(loc="upper right")

    axes[2].plot(df["day"], df["leaf_health"], color="tab:green", label="yaprak sağlığı")
    axes[2].plot(df["day"], df["root_health"], color="tab:brown", label="kök sağlığı")
    axes[2].axvline(FERTILIZER_DAY, color="red", ls="--", alpha=0.6)
    axes[2].set_ylabel("Sağlık (0-100)")
    axes[2].legend(loc="upper right")

    axes[3].plot(df["day"], df["water_balance"], color="tab:purple")
    axes[3].axhline(0, color="gray", lw=0.8)
    axes[3].axvline(FERTILIZER_DAY, color="red", ls="--", alpha=0.6)
    axes[3].set_ylabel("Su dengesi\n(- : kaybediyor)")
    axes[3].set_xlabel("Gün")

    for e_day, e_name in zip(events["day"], events["ground_truth_event"]):
        for ax in axes:
            ax.axvline(e_day, color="black", ls=":", alpha=0.25)

    plt.suptitle("Senaryo: Yaz kuraklığı + tek seferlik gübre şoku -> tuz yanığı")
    plt.tight_layout()

    if save:
        plt.savefig(os.path.join(OUT_DIR, "disaster_scenario.png"), dpi=130)
        print(f"\nGrafik kaydedildi: {os.path.join(OUT_DIR, 'disaster_scenario.png')}")
    plt.close(fig)
    return df


if __name__ == "__main__":
    run_disaster()
