"""Çıkarım fazı 1. tur (§9.50): topluluk yörüngelerinden etkileşim keşfi.

Doktrin: keşif hipotezleri ÖNDEN yazılır (D1..D3) — veri görüldükten
sonra "bak etkileşim varmış" denmez. Bu modül HİÇBİR fizik bilmez;
yalnız yörünge özetleri üzerinden tabakalı koşullu etkiler hesaplar
(ortalama farkı + önyüklemeli %95 GA). Nedensel iddia YOKTUR —
çıktı "bu koşulda bu fark gözlendi"dir; çıkarım motorunun girdisidir.

D1 (EC×VPD): yüksek-tuz koşularda stres VPD'ye bağlı mı?
D2 (gübre×yağmur): aynı gübre farklı suda farklı EC sonucu mu?
D3 (soğuk→ıslak): düşük sıcaklık daha ıslak kapanış mı?
"""
import numpy as np
import pandas as pd

SUMMARY_COLS = ["run", "mean_temp", "mean_vpd", "max_ec", "min_moist",
                "final_leaf", "final_stress", "final_ec", "total_fert",
                "total_rain"]


def summarize(df):
    """Günlük yörüngeler → koşu-başına özet tablo."""
    df = df.copy()
    df["vpd_num"] = pd.to_numeric(df.get("vpd", ""), errors="coerce")
    rows = []
    for run, g in df.groupby("run"):
        vpd = g["vpd_num"].dropna()
        rows.append({
            "run": run,
            "mean_temp": round(float(g["temp"].mean()), 3),
            "mean_vpd": (round(float(vpd.mean()), 3)
                         if len(vpd) else float("nan")),
            "max_ec": round(float(g["soil_ec"].max()), 3),
            "min_moist": round(float(g["soil_moisture"].min()), 3),
            "final_leaf": round(float(g.iloc[-1]["leaf"]), 3),
            "final_stress": round(float(g.iloc[-1]["stress"]), 4),
            "final_ec": round(float(g.iloc[-1]["soil_ec"]), 3),
            "total_fert": round(float(g["fert"].sum()), 1),
            "total_rain": round(float(g["rain"].sum()), 2),
        })
    return pd.DataFrame(rows, columns=SUMMARY_COLS)


def _contrast(a, b):
    """Ortalama farkı + önyüklemeli %95 GA (tohumlu, B=500)."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    diff = float(a.mean() - b.mean())
    rng = np.random.default_rng(0)
    boots = [float(rng.choice(a, len(a), replace=True).mean()
                   - rng.choice(b, len(b), replace=True).mean())
             for _ in range(500)]
    return diff, round(float(np.quantile(boots, 0.025)), 4), \
        round(float(np.quantile(boots, 0.975)), 4)


# Keşif hipotezleri — ÖNDEN (§9.50). Eşikler mekanizma-yönündedir
# (yön + asgari ayırt edilebilirlik), büyüklük iddiası yoktur.
DISCOVERIES = [
    ("D1", "EC etkisi VPD'ye bağlıdır",
     lambda s: _d1(s), 0.02),
    ("D2", "aynı gübre farklı suda farklı EC sonucu verir",
     lambda s: _d2(s), 0.10),
    ("D3", "serin kapanış daha ıslaktır (düşük kayıp)",
     lambda s: _d3(s), 0.50),
]


def _d1(s):
    salty = s[s.max_ec >= 2.0]
    if len(salty) < 10:
        return 0.0, 0.0, 0.0
    cut = salty.mean_vpd.median()
    hi = salty[salty.mean_vpd > cut].final_stress
    lo = salty[salty.mean_vpd <= cut].final_stress
    if len(hi) < 5 or len(lo) < 5:
        return 0.0, 0.0, 0.0
    return _contrast(hi, lo)


def _d2(s):
    fert = s[s.total_fert > 0]
    if len(fert) < 10:
        return 0.0, 0.0, 0.0
    cut = fert.total_rain.median()
    dry = fert[fert.total_rain <= cut].final_ec
    wet = fert[fert.total_rain > cut].final_ec
    if len(dry) < 5 or len(wet) < 5:
        return 0.0, 0.0, 0.0
    return _contrast(dry, wet)


def _d3(s):
    if len(s) < 30:
        return 0.0, 0.0, 0.0
    lo_t = s.nsmallest(max(10, len(s) // 3), "mean_temp").min_moist
    hi_t = s.nlargest(max(10, len(s) // 3), "mean_temp").min_moist
    return _contrast(lo_t, hi_t)


def discover(summary):
    """{Did: (kontrast, ga_alt, ga_ust, gecti)}."""
    out = {}
    for did, _desc, fn, bar in DISCOVERIES:
        diff, lo, hi = fn(summary)
        out[did] = (round(diff, 4), lo, hi, bool(diff > bar))
    return out


if __name__ == "__main__":
    import os
    import sys
    import time
    from sim.events import run_ensemble
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 10000
    t0 = time.time()
    df, logs = run_ensemble(N, days=12, rh_mode="mixed")
    print(f"{N} koşu: {time.time()-t0:.1f}sn "
          f"({len(df)} satır, {len(logs)} olay)")
    s = summarize(df)
    outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "out")
    df.to_csv(os.path.join(outdir, "infer_runs.csv"), index=False)
    s.to_csv(os.path.join(outdir, "infer_summary.csv"), index=False)
    for did, desc, _fn, bar in DISCOVERIES:
        diff, lo, hi, ok = discover(s)[did]
        print(f"{did} {desc}: kontrast={diff:+.4f} "
              f"GA=[{lo:+.4f},{hi:+.4f}] bar={bar} -> "
              f"{'KEŞİF' if ok else 'YOK'}")
