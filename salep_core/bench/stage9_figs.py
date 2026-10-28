#!/usr/bin/env python3
"""bench/stage9_figs.py — 7 şekil, 300 dpi, Türkçe eksenler (AŞAMA 9)."""
import csv
import glob
import os
import statistics as st
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

B = sys.argv[1]
F = os.path.join(B, "figures")
os.makedirs(F, exist_ok=True)
plt.rcParams.update({"figure.dpi": 300, "font.size": 9})


def f1():
    # Örnek zaman serisi + bant ateşleri (seed 2000, ilk 600 tick).
    D = os.path.join(B, "results", "stage2", "data")
    w = np.loadtxt(D + "/demux_s2000_wire.csv", delimiter=",", skiprows=1)[:600, 1]
    t = np.loadtxt(D + "/demux_s2000_tick.csv", delimiter=",", skiprows=1)[:600, 1:3]
    rows = list(csv.DictReader(open(D + "/demux_s2000_windows.csv")))[:6]
    fig, ax = plt.subplots(2, 1, figsize=(8, 4), sharex=True)
    ax[0].stem(np.flatnonzero(w > 0), w[w > 0] / 65536, basefmt=" ",
               markerfmt="C0.", linefmt="C0-", label="tel darbeleri")
    for r in rows:
        ax[0].axvspan(int(r["t0"]), int(r["t1"]), alpha=0.08, color="k")
        ax[0].text(int(r["t0"]) + 4, 2.3, r["label"], fontsize=7)
    ax[0].set_ylabel("tel genliği")
    ax[0].legend(fontsize=7)
    ax[1].eventplot([np.flatnonzero(t[:, 0] > 0), np.flatnonzero(t[:, 1] > 0)],
                    colors=["C0", "C1"], linelengths=0.8)
    ax[1].set_yticks([0, 1])
    ax[1].set_yticklabels(["bant tau=4", "bant tau=12"])
    ax[1].set_xlabel("tick")
    ax[1].set_ylabel("S ateşleri")
    fig.suptitle("Demux örneği: ortak tel ve bant ateşleri (seed 2000)")
    fig.tight_layout()
    fig.savefig(F + "/fig1_demux_ornek.png")
    plt.close(fig)


def f2():
    # Ağırlıkların öğrenme boyunca yükselişi (snapshot causality CSV).
    p = os.path.join(B, "baseline_snapshot", "causality", "causality_learning.csv")
    d = np.loadtxt(p, delimiter=",", skiprows=1)
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.plot(d[:, 0], d[:, 8], label="w0 (4-kanalı)", lw=1)
    ax.plot(d[:, 0], d[:, 9], label="w2 (12-kanalı)", lw=1)
    ax.set_xlabel("tick")
    ax.set_ylabel("ağırlık")
    ax.set_title("Nedensellik demosunda ağırlık yörüngesi (güncel kod, 20 super)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(F + "/fig2_agirlik.png")
    plt.close(fig)


def f3():
    # Gürültü eğrileri (S vs baseline, hata çubuklu).
    rows = list(csv.DictReader(open(
        os.path.join(B, "results", "stage3", "grid_auc.csv"))))
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.5), sharey=True)
    for i, tau in enumerate(("4", "12")):
        for m, c in (("S", "k"), ("B1", "C0"), ("B2", "C1"), ("B3", "C2"),
                      ("B4", "C3")):
            xs, ys, es = [], [], []
            for p in (0, 2, 5, 10, 20, 30):
                r = [x for x in rows if x["pextra"] == str(p) and x["jit"] == "0"
                     and x["method"] == m and x["tau"] == tau][0]
                xs.append(p)
                ys.append(float(r["mean"]))
                es.append(1.96 * float(r["std"]) / np.sqrt(30))
            ax[i].errorbar(xs, ys, yerr=es, marker=".", color=c, label=m,
                           capsize=2, lw=1)
        ax[i].set_xlabel("ekstra darbe % (jit=0)")
        ax[i].set_title(f"tau={tau}")
    ax[0].set_ylabel("AUC (test ort, %95 GA)")
    ax[0].legend(fontsize=7, ncol=5)
    fig.suptitle("Gürültü dayanımı: S ve baseline'lar")
    fig.tight_layout()
    fig.savefig(F + "/fig3_gurultu.png")
    plt.close(fig)


def f4():
    # Ablasyon çubuk grafiği (demux düşüşleri; nedensellik taban-etkisi notu).
    rows = list(csv.DictReader(open(
        os.path.join(B, "results", "stage4", "ablation_demux.csv"))))
    rows = [r for r in rows if r["mekanizma"] not in ("baz", "notrace")]
    x = np.arange(len(rows))
    d4 = [float(r["dusuk_tau4"]) for r in rows]
    d12 = [float(r["dusuk_tau12"]) for r in rows]
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.bar(x - 0.2, d4, 0.4, label="tau=4 düşüşü (+=kötüleşme)")
    ax.bar(x + 0.2, d12, 0.4, label="tau=12 düşüşü")
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([r["mekanizma"] for r in rows])
    ax.set_ylabel("AUC düşüşü (baz − ablasyon)")
    ax.set_title("Ablasyon: demux AUC etkisi (negatif = iyileşme)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(F + "/fig4_ablasyon.png")
    plt.close(fig)


def f5():
    # Genelleme: tau'ya göre AUC.
    cfgs = ["tau5", "tau6", "tau7", "tau9", "tau10", "tau11", "tau13",
            "tau14", "tau15"]
    xs, ys, es = [], [], []
    for c in cfgs:
        rows = list(csv.DictReader(open(
            os.path.join(B, "results", "stage5", c, "auc.csv"))))
        t = c[3:]
        v = [float(r["auc"]) for r in rows if r["method"] == "S" and r["tau"] == t]
        xs.append(int(t))
        ys.append(st.mean(v))
        es.append(1.96 * st.stdev(v) / np.sqrt(len(v)) if len(v) > 1 else 0)
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.errorbar(xs, ys, yerr=es, marker="o", color="k", capsize=3)
    ax.axhline(0.7, color="r", ls="--", lw=1, label="bozulma eşiği 0.7")
    ax.axhline(0.9, color="g", ls=":", lw=1, label="D1 barı 0.9")
    for x, y in zip(xs, ys):
        ax.text(x, y + 0.008, f"{y:.3f}", ha="center", fontsize=7)
    ax.set_xlabel("tau (kalibre-dışı, ayarsız)")
    ax.set_ylabel("S AUC (test ort, %95 GA)")
    ax.set_title("Genelleme: tekil tau'lar")
    ax.set_ylim(0.6, 1.05)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(F + "/fig5_genelleme.png")
    plt.close(fig)


def f6():
    # Seyrek dünya precision-recall (hücre başına gruplu).
    cells = sorted(glob.glob(os.path.join(B, "results", "stage6", "p*",
                                           "metrics.csv")))
    tags = [c.split("/")[-2] for c in cells]
    P = {m: [] for m in ("S", "N1", "N2", "N3")}
    for c in cells:
        rows = list(csv.DictReader(open(c)))
        for m in P:
            v = [float(r["prec_L"]) for r in rows if r["method"] == m]
            P[m].append(st.mean(v))
    x = np.arange(len(tags))
    fig, ax = plt.subplots(figsize=(10, 3.8))
    for i, m in enumerate(("S", "N1", "N2", "N3")):
        ax.bar(x + (i - 1.5) * 0.2, P[m], 0.2, label=m)
    ax.set_xticks(x)
    ax.set_xticklabels([t.replace("_", "\n") for t in tags], fontsize=7)
    ax.set_ylabel("precision_L (test ort)")
    ax.set_title("Seyrek dünya: yöntem × hücre precision'ı (S tüm hücrelerde 0)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(F + "/fig6_seyrek_pr.png")
    plt.close(fig)


def f7():
    # Gerçek veri: kayıt-başına AUC noktaları + havuz çizgisi.
    rows = list(csv.DictReader(open(
        os.path.join(B, "results", "stage7", "auc.csv"))))
    rec = [r for r in rows if r["rec"] != "POOLED"]
    pool = [r for r in rows if r["rec"] == "POOLED"][0]
    fig, ax = plt.subplots(figsize=(8, 3.8))
    xs = np.arange(len(rec))
    ax.scatter(xs, [float(r["S"]) for r in rec], s=12, label="S (kayıt)", zorder=3)
    ax.scatter(xs, [float(r["Bvar"]) for r in rec], s=12, label="B-var (kayıt)")
    ax.scatter(xs, [float(r["Bhf"]) for r in rec], s=12, label="B-hf (kayıt)")
    for k, c in (("S", "C0"), ("Bvar", "C1"), ("Bhf", "C2")):
        ax.axhline(float(pool[k]), color=c, ls="--", lw=1)
    ax.axhline(0.5, color="k", lw=0.8)
    ax.set_xlabel("test kaydı (36 Ocimum)")
    ax.set_ylabel("AUC (pre vs post)")
    ax.set_title("Gerçek veri: kayıt-başına ve havuzlanmış AUC (kesikli=havuz)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(F + "/fig7_gercek.png")
    plt.close(fig)


for i, fn in enumerate((f1, f2, f3, f4, f5, f6, f7), 1):
    fn()
    print(f"OK fig{i}")
