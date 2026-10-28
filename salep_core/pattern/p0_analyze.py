"""P0 analizi M1..M8 + kapilar G1..G6 — P0_SPEC.md §5/§6.

Girdi: p0_runs.csv. Cikti: p0_metrics.json + p0_*.png + OZET-P0-ANALYZE.
G1 disi kapilar olcum sonucudur (exit 0); FAIL veridir. Sessiz matriste
gecersiz kilinan kapilar VACUOUS isaretlenir (bos-gecme kanit degildir).
stdlib-only (+matplotlib varsa PNG); sim/encoder/web bagi YOK.
"""
import ast
import csv
import json
import os

import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)

OUT = os.path.join(ENC, "p0_out")

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_PLOT = True
except Exception:
    HAS_PLOT = False


def sig(r):
    return (int(r["n_fires"]), r["fire_ticks"], round(float(r["max_soma"]), 6),
            round(float(r["max_eff_g"]), 6), int(r["n_coinc"]),
            int(r["k_fires"]))


def dist(a, b):
    sa, sb = sig(a), sig(b)
    return (0 if sa == sb else 1) + abs(sa[2] - sb[2])


def load():
    with open(os.path.join(OUT, "p0_runs.csv")) as f:
        return list(csv.DictReader(f))


def zero_link_gate():
    # P0 dosyalari sim/encoder/web import etmemeli (AST kapisi).
    bad = []
    for nm in ("pl_core.py", "p0_run.py", "p0_analyze.py"):
        tree = ast.parse(open(os.path.join(ENC, nm)).read())
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names:
                    if a.name.split(".")[0] in ("sim", "encoder", "web"):
                        bad.append((nm, a.name))
            elif isinstance(n, ast.ImportFrom) and n.module:
                if n.module.split(".")[0] in ("sim", "encoder", "web"):
                    bad.append((nm, n.module))
    return bad


def main():
    rows = load()
    ring = [r for r in rows if r["mode"] == "ring"]
    res4 = [r for r in rows if r["mode"] == "resonant" and r["tau"] == "4"]
    grid = [r for r in rows if r["mode"] == "resonant" and r["tau"] != "4"]
    m = {}

    # M1/G1 determinizm
    m["M1_repeat_ok"] = all(r["repeat_ok"] == "1" for r in rows)
    g1 = m["M1_repeat_ok"]

    # M3 ayri imza sayisi (tam + deney kirilimi = duyarlilik)
    m["M3_all_ring"] = len(set(sig(r) for r in ring))
    m["M3_all_res4"] = len(set(sig(r) for r in res4))
    m["M3_by_exp"] = {}
    for exp in ("E1", "E2", "E3", "E4", "E5", "E6"):
        m["M3_by_exp"][exp] = {
            "ring": len(set(sig(r) for r in ring if r["exp"] == exp)),
            "res4": len(set(sig(r) for r in res4 if r["exp"] == exp))}

    # M4 dt egrisi (E1)
    m["M4_E1_ring"] = [(r["dt"], round(float(r["max_soma"]), 6),
                        r["n_fires"]) for r in ring if r["exp"] == "E1"]
    m["M4_E1_res4"] = [(r["dt"], round(float(r["max_soma"]), 6),
                        r["n_fires"]) for r in res4 if r["exp"] == "E1"]
    lv_ring = set(s for (d, s, _) in m["M4_E1_ring"] if d in ("5", "10", "30"))
    lv_res4 = set(s for (d, s, _) in m["M4_E1_res4"] if d in ("5", "10", "30"))
    m["M4_levels_ring"] = len(lv_ring)
    m["M4_levels_res4"] = len(lv_res4)

    # M5 sira asimetrisi (E2)
    m["M5"] = {}
    for dt in ("5", "10", "30"):
        ab = next(r for r in ring if r["exp"] == "E2" and r["dt"] == dt
                  and r["order"] == "AB")
        ba = next(r for r in ring if r["exp"] == "E2" and r["dt"] == dt
                  and r["order"] == "BA")
        ab4 = next(r for r in res4 if r["exp"] == "E2" and r["dt"] == dt
                   and r["order"] == "AB")
        ba4 = next(r for r in res4 if r["exp"] == "E2" and r["dt"] == dt
                   and r["order"] == "BA")
        m["M5"][dt] = {"ring": dist(ab, ba), "res4": dist(ab4, ba4)}

    # M6 dongusellik (E4): dphi-grubu ici tekil imza sayisi
    m["M6_within_dphi_ring"], m["M6_within_dphi_res4"] = {}, {}
    for k in range(12):
        grp = [r for r in ring if r["exp"] == "E4" and r["dphi"] == str(k * 30)]
        grp4 = [r for r in res4 if r["exp"] == "E4"
                and r["dphi"] == str(k * 30)]
        m["M6_within_dphi_ring"][k * 30] = len(set(sig(r) for r in grp))
        m["M6_within_dphi_res4"][k * 30] = len(set(sig(r) for r in grp4))
    across_ring = len(set(sig(r) for r in ring if r["exp"] == "E4"))
    m["M6_across_dphi_ring"] = across_ring

    # M7 komsuluk (E5, w_ring=0.2)
    m["M7"] = {}
    base = {d: next(r for r in ring if r["exp"] == "E5"
                    and r["dphi"] == str(d) and r["w_ring"] == "0.2")
            for d in (30, 90, 180)}
    m["M7"]["30v90"] = dist(base[30], base[90])
    m["M7"]["30v180"] = dist(base[30], base[180])
    m["M7"]["90v180"] = dist(base[90], base[180])

    # M8 yan yana + grid (gecici tarama etiketiyle)
    m["M8"] = {"ring": {k: m["M3_by_exp"][k]["ring"]
                        for k in m["M3_by_exp"]},
               "res4": {k: m["M3_by_exp"][k]["res4"]
                        for k in m["M3_by_exp"]}}
    e1grid = {}
    for r in grid:
        if r["exp"] == "E1":
            e1grid.setdefault(r["tau"], []).append(
                (r["dt"], round(float(r["max_soma"]), 6), r["n_fires"]))
    m["M8"]["E1_tau_grid_provisional"] = {
        t: (len(set(s for (_, s, _) in v)),
            sum(1 for (_, _, n) in v if int(n) > 0)) for t, v in e1grid.items()}

    # Kapilar (VACUOUS: sessizlikten bos-gecme; E1-E5 alt-kumeleri
    # ayri sayilir — tum matris degil, ilgili girdi sessizse FAIL
    # "olculdu" degil "sessiz-girdi"dir)
    def fires(sub):
        return sum(int(r["n_fires"]) for r in sub)
    p3_fires = fires(rows)
    e15 = [r for r in rows if r["exp"] in ("E1", "E2", "E3", "E4", "E5")]
    e15_silent = fires(e15) == 0
    e6a1 = [r for r in ring if r["exp"] == "E6" and r["amp"] == "1.0"]
    e6a2 = [r for r in ring if r["exp"] == "E6" and r["single"] == "A"
            and r["amp"] == "2.0"]
    g2a = all(int(r["n_fires"]) == 0 for r in e6a1)
    g2b = all(int(r["n_fires"]) == 0 for r in e6a2)
    g2 = g2a and g2b
    m["G2_per_amp"] = {"1.0_sessiz_gecis": bool(g2a), "2.0_tekA": bool(g2b)}
    vac = p3_fires == 0
    g3 = m["M4_levels_ring"] >= 3 or m["M4_levels_res4"] >= 3
    g4 = any(v["ring"] > 0 or v["res4"] > 0 for v in m["M5"].values())
    g5 = (max(m["M6_within_dphi_ring"].values()) == 1
          and m["M6_across_dphi_ring"] > 1)
    g6 = m["M3_all_ring"] > 1 or m["M3_all_res4"] > 1
    tag_sessiz = " (SESSIZ-GIRDI: E1-E5 sifir ates)" if e15_silent else ""
    gates = {"G1": ("PASS" if g1 else "FAIL", False, ""),
             "G2": ("PASS" if g2 else "FAIL", vac,
                    "" if g2b else " (tek-A@2.0 atesledi!)"),
             "G3": ("PASS" if g3 else "FAIL", vac, tag_sessiz),
             "G4": ("PASS" if g4 else "FAIL", vac, tag_sessiz),
             "G5": ("PASS" if g5 else "FAIL", vac, tag_sessiz),
             "G6": ("PASS" if g6 else "FAIL", vac,
                    " (varyasyon yalniz E6-amp'ten)" if g6 else "")}
    m["gates"] = {k: v[0] + (" (VACUOUS-sessiz)" if v[1] else "") + v[2]
                  for k, v in gates.items()}
    m["p3_total_fires"] = p3_fires
    m["zero_link_violations"] = zero_link_gate()

    with open(os.path.join(OUT, "p0_metrics.json"), "w") as f:
        json.dump(m, f, indent=1, sort_keys=True)

    if HAS_PLOT:
        e1r = [(int(d), s) for (d, s, _) in m["M4_E1_ring"]]
        e1b = [(int(d), s) for (d, s, _) in m["M4_E1_res4"]]
        plt.figure()
        plt.plot([d for (d, _) in e1r], [s for (_, s) in e1r], "o-",
                 label="K1-a RING")
        plt.plot([d for (d, _) in e1b], [s for (_, s) in e1b], "s--",
                 label="K1-b RESONANT tau=4 (gecici)")
        plt.xlabel("dt (tick)")
        plt.ylabel("max soma_V (P3)")
        plt.legend()
        plt.savefig(os.path.join(OUT, "p0_dt_curve.png"), dpi=100)
        plt.close()

    print(f"P3 toplam ates: {p3_fires} / {len(rows)} kosu")
    print(f"M3 ayri imza: ring={m['M3_all_ring']} res4={m['M3_all_res4']} "
          f"(elektriksel ayrisma; kapasite kaniti DEGIL)")
    print(f"M3 kirilim: {json.dumps(m['M3_by_exp'], sort_keys=True)}")
    print(f"M4 seviyeler@5/10/30: ring={m['M4_levels_ring']} "
          f"res4={m['M4_levels_res4']}")
    print(f"M5 sira: {json.dumps(m['M5'], sort_keys=True)}")
    print(f"M6 dphi-ici tekil: ring={m['M6_within_dphi_ring']} "
          f"across={across_ring}")
    print(f"M7: {json.dumps(m['M7'], sort_keys=True)}")
    print(f"M8 grid (GECICI tarama): "
          f"{json.dumps(m['M8']['E1_tau_grid_provisional'], sort_keys=True)}")
    print("Kapilar: " + " ".join(f"{k}={v}" for k, v in m["gates"].items()))
    if m["zero_link_violations"]:
        raise SystemExit(f"SIFIR-BAG IHLALI: {m['zero_link_violations']}")
    print("OZET-P0-ANALYZE: " + " ".join(f"{k}={v[0]}" for k, v in
                                         gates.items()))
    if not g1:
        raise SystemExit("G1 BATTI")


if __name__ == "__main__":
    main()
