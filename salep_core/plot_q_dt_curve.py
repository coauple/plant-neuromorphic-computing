"""Q(dt) taramasi: 12'lik ritim faz kaymasi (d12) karsisinda Faz-3 ogrenme
kazanci + eszamanlilik amplifikasyonu.

TARAMA: DTS = [0,2,4,6,8,10,12,15,20] (9 gecikme). Her dt icin
`./npu_causality --d12=DT` subprocess ile kosulur (npu_runner disiplini:
ASAN_OPTIONS=detect_leaks=0, cekirdekte heap yok §2.2), `causality_learning.csv`
okunup hasat yapilir:
  - F1/F2/F3: phase==1/2/3 bloklarindaki toplam target atesi
  - ampl = F3/(F1+F2) (nedensellik bagi: birlikteyken ates orani)
  - dw_s0_F3 / dw_s2_F3: 20 super x Faz-3 blogu bas/son agirlik farki toplami
    (plot_causality.py Panel-3 ile ayni metrik)
Cikti: q_dt_curve.csv + q_dt_curve.png (2 panel) + konsola durust bulgu.

NOT: tarama causality_learning.csv'yi uzerine yazar; son adimda kalibre
kosusu (argumansiz) tekrar calistirilip CSV bayt-bayt eski haline dondurulur
(regresyon §9.7-E korunur).

BULGU SINIFLANDIRMA (esikler kodda sabit, veri gorulmeden once konuldu):
  - can: dw_total ve ampl IKMISINDE de tepe dt<=4'te ve dt>=10'daki en dusuk
    deger tepenin %70'inden kucuk (>=%30 dusus).
  - 4-periyodik dalgalanma: dt%4 grup ortalamalari arasi fark, genel
    ortalamanin %10'undan buyuk.
  - duz: ikisi de tutmazsa (yayilim <%10) -> duz raporlanir.
"""

import csv
import os
import subprocess
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

try:
    plt.style.use("seaborn-v0_8-whitegrid")
except OSError:
    plt.style.use("ggplot")

CORE_DIR = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(CORE_DIR, "npu_causality")
CSV = os.path.join(CORE_DIR, "causality_learning.csv")
OUT_CSV = os.path.join(CORE_DIR, "q_dt_curve.csv")
OUT_PNG = os.path.join(CORE_DIR, "q_dt_curve.png")

DTS = [0, 2, 4, 6, 8, 10, 12, 15, 20]
N_SUPER = 20
COINC_WIN = 10  # neuron.h COINCIDENCE_WINDOW_MS

# Derin (deep) palet — tek Panel-1'de uc egri, Panel-2'de amplifikasyon.
C_S0 = "#1b4f72"
C_S2 = "#1e8449"
C_TOT = "#6c3483"
C_AMPL = "#b03a2e"


def run_dt(dt):
    env = dict(os.environ)
    env["ASAN_OPTIONS"] = "detect_leaks=0"
    p = subprocess.run([BIN, f"--d12={dt}"], cwd=CORE_DIR,
                       capture_output=True, text=True, timeout=300, env=env)
    if p.returncode != 0:
        print(f"HATA: npu_causality --d12={dt} cikis {p.returncode}\n"
              f"{p.stderr[-2000:]}", file=sys.stderr)
        sys.exit(1)
    return p.stdout


def harvest():
    rows = list(csv.DictReader(open(CSV)))
    fires = []
    for ph in (1, 2, 3):
        fires.append(sum(int(r["target_fired"]) for r in rows
                         if int(r["phase"]) == ph))
    base = fires[0] + fires[1]
    ampl = fires[2] / base if base else float("nan")
    dw0 = dw2 = 0.0
    for s in range(N_SUPER):
        idx = [i for i, r in enumerate(rows)
               if int(r["super"]) == s and int(r["phase"]) == 3]
        if idx:
            dw0 += float(rows[idx[-1]]["w0"]) - float(rows[idx[0]]["w0"])
            dw2 += float(rows[idx[-1]]["w2"]) - float(rows[idx[0]]["w2"])
    return fires, ampl, dw0, dw2


def classify(dts, dw_tot, ampl):
    dts = np.array(dts, dtype=float)
    dw_tot = np.array(dw_tot, dtype=float)
    ampl = np.array(ampl, dtype=float)
    out = {}
    # Can testi: tepe erken (dt<=4), dt>=10'daki dip tepenin %70 alti.
    peak_dw = dw_tot[dts <= 4].max()
    dip_dw = dw_tot[dts >= 10].min()
    peak_a = ampl[dts <= 4].max()
    dip_a = ampl[dts >= 10].min()
    out["bell_dw"] = bool(dip_dw < 0.70 * peak_dw)
    out["bell_ampl"] = bool(dip_a < 0.70 * peak_a)
    out["bell"] = bool(out["bell_dw"] and out["bell_ampl"])
    # 4-periyodik: dt%4 grup ortalamalari farki > genel ortalamanin %10'u.
    groups = {}
    for d, v in zip(dts, dw_tot):
        groups.setdefault(int(d) % 4, []).append(v)
    means = {k: float(np.mean(v)) for k, v in groups.items()}
    spread = (max(means.values()) - min(means.values())) / float(
        np.mean(dw_tot))
    out["ripple4_spread"] = float(spread)
    out["ripple4"] = bool(spread > 0.10)
    # Duzluk: toplam yayilim (max-min)/mean.
    out["spread_tot"] = float((dw_tot.max() - dw_tot.min()) /
                              float(np.mean(dw_tot)))
    out["spread_ampl"] = float((ampl.max() - ampl.min()) /
                               float(np.mean(ampl)))
    out["flat"] = bool(out["spread_tot"] < 0.10 and
                       out["spread_ampl"] < 0.10)
    if out["bell"]:
        out["verdict"] = "can"
    elif out["ripple4"]:
        out["verdict"] = "4-periyodik dalgalanma"
    elif out["flat"]:
        out["verdict"] = "~duz"
    else:
        out["verdict"] = "arada (zayif egim/dalga, esik alti)"
    out["group_means"] = means
    return out


def main():
    if not os.path.isfile(BIN):
        print(f"HATA: {BIN} yok; once derleyin.", file=sys.stderr)
        sys.exit(1)
    recs = []
    for dt in DTS:
        run_dt(dt)
        (f1, f2, f3), ampl, dw0, dw2 = harvest()
        recs.append((dt, f1, f2, f3, ampl, dw0, dw2, dw0 + dw2))
    # Kalibre durumuna don: argumansiz kosu CSV'yi bayt-bayt geri yazar.
    env = dict(os.environ)
    env["ASAN_OPTIONS"] = "detect_leaks=0"
    p = subprocess.run([BIN], cwd=CORE_DIR, capture_output=True, text=True,
                       timeout=300, env=env)
    if p.returncode != 0:
        print("UYARI: kalibre geri-yukleme kosusu basarisiz\n"
              f"{p.stderr[-2000:]}", file=sys.stderr)

    with open(OUT_CSV, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["dt", "F1", "F2", "F3", "ampl", "dw_s0_F3", "dw_s2_F3",
                    "dw_total_F3"])
        for r in recs:
            w.writerow([r[0], r[1], r[2], r[3], f"{r[4]:.6f}",
                        f"{r[5]:+.6f}", f"{r[6]:+.6f}", f"{r[7]:+.6f}"])
    print(f"yazildi: {os.path.basename(OUT_CSV)} ({len(recs)} satir)")

    arr = np.array(recs, dtype=float)
    dts, ampl = arr[:, 0], arr[:, 4]
    dw0, dw2, dwtot = arr[:, 5], arr[:, 6], arr[:, 7]

    fig, ax = plt.subplots(1, 2, figsize=(16, 6))
    fig.suptitle("Q(dt) Taramasi: Faz Kaymasina Karsi Ogrenme Kazanci ve "
                 "Amplifikasyon", fontsize=15, fontweight="bold")

    # --- Panel 1: dw(dt) egrileri ---
    ax[0].axvspan(COINC_WIN, max(DTS), color="#e5e8e8", alpha=0.55,
                  linewidth=0, label="pencere-disi (dt>10)", zorder=0)
    ax[0].plot(dts, dw0, marker="o", linewidth=2.5, color=C_S0,
               label="s0 (P0->Dal A)")
    ax[0].plot(dts, dw2, marker="s", linewidth=2.5, color=C_S2,
               label="s2 (P2->Dal B)")
    ax[0].plot(dts, dwtot, marker="^", linewidth=2.5, color=C_TOT,
               label="toplam (s0+s2)")
    ax[0].axvline(COINC_WIN, color="#e74c3c", linestyle="--", linewidth=2,
                  label="COINCIDENCE_WINDOW_MS=10")
    ax[0].set_xlabel("dt (12'lik ritim faz kaymasi, tick)", fontsize=12)
    ax[0].set_ylabel("Faz-3 blok kazanci (dw)", fontsize=12)
    ax[0].set_title("Ogrenme Kazanci Q(dt)", fontsize=13, fontweight="bold")
    ax[0].set_xticks(DTS)
    ax[0].legend(fontsize=10, loc="best")

    # --- Panel 2: amplifikasyon(dt) — nedensellik bagi ---
    ax[1].axvspan(COINC_WIN, max(DTS), color="#e5e8e8", alpha=0.55,
                  linewidth=0, label="pencere-disi (dt>10)", zorder=0)
    ax[1].plot(dts, ampl, marker="D", linewidth=2.5, color=C_AMPL,
               label="ampl = F3/(F1+F2)")
    ax[1].axhline(ampl[0], color="gray", linestyle=":", linewidth=1.5,
                  label=f"kalibre referans ({ampl[0]:.2f}x)")
    ax[1].axvline(COINC_WIN, color="#e74c3c", linestyle="--", linewidth=2,
                  label="COINCIDENCE_WINDOW_MS=10")
    ax[1].set_xlabel("dt (12'lik ritim faz kaymasi, tick)", fontsize=12)
    ax[1].set_ylabel("Amplifikasyon (x)", fontsize=12)
    ax[1].set_title("Eszamanlilik Amplifikasyonu (Nedensellik Bagi)",
                    fontsize=13, fontweight="bold")
    ax[1].set_xticks(DTS)
    ax[1].legend(fontsize=10, loc="best")

    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=300)
    print(f"yazildi: {os.path.basename(OUT_PNG)} (dpi=300)")

    print("\ndt  F1  F2  F3  ampl    dw_s0      dw_s2      dw_tot")
    for r in recs:
        print(f"{r[0]:>2}  {r[1]:>2}  {r[2]:>2}  {r[3]:>2}  {r[4]:.2f}x  "
              f"{r[5]:+.4f}  {r[6]:+.4f}  {r[7]:+.4f}")

    cls = classify(dts, dwtot, ampl)
    print(f"\nyayilim: dw_total %{100*cls['spread_tot']:.1f}, "
          f"ampl %{100*cls['spread_ampl']:.1f}")
    print(f"can testi: dw dip/tepe={cls['bell_dw']}, ampl "
          f"dip/tepe={cls['bell_ampl']}")
    print(f"dt%4 grup ortalamalari: "
          + ", ".join(f"%{k}={v:.4f}"
                      for k, v in sorted(cls["group_means"].items()))
          + f" (yayilim %{100*cls['ripple4_spread']:.1f})")
    print(f"DURUST BULGU: egri '{cls['verdict']}' cikti "
          f"(can yok: {not cls['bell']}; 4-dalga yok: {not cls['ripple4']}; "
          f"duz: {cls['flat']}).")


if __name__ == "__main__":
    main()
