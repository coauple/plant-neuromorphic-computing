"""P0b analizi — P0B_SPEC.md §4 Kilit ile kosudan ONCE yazildi.

1. Manifest kilidi: tren parametreleri SPEC degerlerine esit olmali
   (degilse sert hata — P0b ici ayar yapilmis demektir).
2. M1..M8 + kapilar + K1 karari (SPEC §6, uc cikisli).
Kapasite skoru (kosudan once kilitli formul):
  skor = M3(E6p-haric ayri imza) + M4(seviye@5/10/30)
         + M5(sifir-disi mesafe sayisi) + M7(sifir-disi mesafe sayisi)
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

# Pre-registered kilit degerler (P0B_SPEC.md §1) — analizor bunlari dayatir.
LOCK_TRAIN = {"n_pulse": 5, "isi": 12, "amp": 1.0, "t0": 50,
              "horizon": 200}

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


def main():
    man = json.load(open(os.path.join(OUT, "p0b_manifest.json")))["manifest"]
    assert man["train"] == LOCK_TRAIN, (
        f"KILIT IHLALI: manifest treni {man['train']} != {LOCK_TRAIN}")
    assert man["w_ring"] == 0.2, "KILIT IHLALI: w_ring"
    print(f"manifest kilidi OK: {man['train']}")

    with open(os.path.join(OUT, "p0b_runs.csv")) as f:
        rows = list(csv.DictReader(f))
    ring = [r for r in rows if r["mode"] == "ring"]
    res4 = [r for r in rows if r["mode"] == "resonant" and r["tau"] == "4"]
    grid = [r for r in rows if r["mode"] == "resonant" and r["tau"] != "4"]
    m = {}

    m["M1"] = all(r["repeat_ok"] == "1" for r in rows)
    g1 = m["M1"]

    no6 = lambda rs: [r for r in rs if r["exp"] != "E6p"]
    m["M3_ring"] = len(set(sig(r) for r in no6(ring)))
    m["M3_res4"] = len(set(sig(r) for r in no6(res4)))
    m["M3_by_exp"] = {}
    for exp in ("E1p", "E2p", "E3p", "E4p", "E5p", "E6p"):
        m["M3_by_exp"][exp] = {
            "ring": len(set(sig(r) for r in ring if r["exp"] == exp)),
            "res4": len(set(sig(r) for r in res4 if r["exp"] == exp))}

    e1r = [(r["dt"], round(float(r["max_soma"]), 6), r["n_fires"])
           for r in ring if r["exp"] == "E1p"]
    e1b = [(r["dt"], round(float(r["max_soma"]), 6), r["n_fires"])
           for r in res4 if r["exp"] == "E1p"]
    m["M4_E1_ring"], m["M4_E1_res4"] = e1r, e1b
    lv_r = set(s for (d, s, _) in e1r if d in ("5", "10", "30"))
    lv_b = set(s for (d, s, _) in e1b if d in ("5", "10", "30"))
    m["M4_levels"] = {"ring": len(lv_r), "res4": len(lv_b)}

    m["M5"] = {}
    for dt in ("5", "10", "30"):
        ab = next(r for r in ring if r["exp"] == "E2p" and r["dt"] == dt
                  and r["order"] == "AB")
        ba = next(r for r in ring if r["exp"] == "E2p" and r["dt"] == dt
                  and r["order"] == "BA")
        ab4 = next(r for r in res4 if r["exp"] == "E2p" and r["dt"] == dt
                   and r["order"] == "AB")
        ba4 = next(r for r in res4 if r["exp"] == "E2p" and r["dt"] == dt
                   and r["order"] == "BA")
        m["M5"][dt] = {"ring": dist(ab, ba), "res4": dist(ab4, ba4)}

    m["M6_ring"], m["M6_res4"] = {}, {}
    for k in range(12):
        g = [r for r in ring if r["exp"] == "E4p"
             and r["dphi"] == str(k * 30)]
        g4 = [r for r in res4 if r["exp"] == "E4p"
              and r["dphi"] == str(k * 30)]
        m["M6_ring"][k * 30] = len(set(sig(r) for r in g))
        m["M6_res4"][k * 30] = len(set(sig(r) for r in g4))
    m["M6_across"] = {"ring": len(set(
        sig(r) for r in ring if r["exp"] == "E4p")),
        "res4": len(set(sig(r) for r in res4 if r["exp"] == "E4p"))}

    base = {d: next(r for r in ring if r["exp"] == "E5p"
                    and r["dphi"] == str(d) and r["w_ring"] == "0.2")
            for d in (30, 90, 180)}
    base4 = {d: next(r for r in res4 if r["exp"] == "E5p"
                     and r["dphi"] == str(d) and r["w_ring"] == "0.2")
             for d in (30, 90, 180)}
    m["M7"] = {"ring": {"30v90": dist(base[30], base[90]),
                        "30v180": dist(base[30], base[180]),
                        "90v180": dist(base[90], base[180])},
               "res4": {"30v90": dist(base4[30], base4[90]),
                        "30v180": dist(base4[30], base4[180]),
                        "90v180": dist(base4[90], base4[180])}}

    e1grid = {}
    for r in grid:
        if r["exp"] == "E1p":
            e1grid.setdefault(r["tau"], []).append(
                (r["dt"], round(float(r["max_soma"]), 6), r["n_fires"]))
    m["M8_grid_provisional"] = {
        t: (len(set(s for (_, s, _) in v)),
            sum(1 for (_, _, n) in v if int(n) > 0)) for t, v in e1grid.items()}

    # Kilitli skor + uc-cikisli K1 karari (SPEC §6)
    def score(m3, lv, m5, m7):
        return (m3 + lv + sum(1 for v in m5.values() if v > 0)
                + sum(1 for v in m7.values() if v > 0))
    sc_r = score(m["M3_ring"], m["M4_levels"]["ring"],
                 {k: v["ring"] for k, v in m["M5"].items()}, m["M7"]["ring"])
    sc_b = score(m["M3_res4"], m["M4_levels"]["res4"],
                 {k: v["res4"] for k, v in m["M5"].items()}, m["M7"]["res4"])
    g5_r = max(m["M6_ring"].values()) == 1 and m["M6_across"]["ring"] > 1
    g5_b = max(m["M6_res4"].values()) == 1 and m["M6_across"]["res4"] > 1
    m["score"] = {"ring": sc_r, "res4": sc_b}
    if sc_b > sc_r and g5_b:
        decision = "K1-b"
    elif sc_r > sc_b and g5_r:
        decision = "RING"
    else:
        decision = "KARARSIZ"
    m["K1_decision"] = decision

    e6 = [r for r in ring if r["exp"] == "E6p"]
    g2 = all(int(r["n_fires"]) == 0 for r in e6)
    g3 = m["M4_levels"]["ring"] >= 3 or m["M4_levels"]["res4"] >= 3
    g4 = any(v["ring"] > 0 or v["res4"] > 0 for v in m["M5"].values())
    g5 = g5_r or g5_b
    g6 = m["M3_ring"] > 1 or m["M3_res4"] > 1
    m["gates"] = {"G1": "PASS" if g1 else "FAIL",
                  "G2p": ("PASS (tek-tren ateslemedi)"
                           if g2 else "FAIL (tek-tren atesledi: "
                           "suras-bagimli gating)"),
                  "G3p": "PASS" if g3 else "FAIL",
                  "G4p": "PASS" if g4 else "FAIL",
                  "G5p": "PASS" if g5 else "FAIL",
                  "G6p": "PASS" if g6 else "FAIL"}

    bad = []
    for nm in ("pl_core.py", "p0_run.py", "p0_analyze.py", "p0b_run.py",
               "p0b_analyze.py"):
        tree = ast.parse(open(os.path.join(ENC, nm)).read())
        for n in ast.walk(tree):
            mods = []
            if isinstance(n, ast.Import):
                mods = [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom) and n.module:
                mods = [n.module]
            for mod in mods:
                if mod.split(".")[0] in ("sim", "encoder", "web"):
                    bad.append((nm, mod))
    m["zero_link"] = bad

    with open(os.path.join(OUT, "p0b_metrics.json"), "w") as f:
        json.dump(m, f, indent=1, sort_keys=True)
    if HAS_PLOT:
        plt.figure()
        plt.plot([int(d) for (d, _, _) in e1r],
                 [s for (_, s, _) in e1r], "o-", label="K1-a RING")
        plt.plot([int(d) for (d, _, _) in e1b],
                 [s for (_, s, _) in e1b], "s--", label="K1-b tau=4")
        plt.xlabel("dt (tick)")
        plt.ylabel("max soma_V (P3)")
        plt.legend()
        plt.savefig(os.path.join(OUT, "p0b_dt_curve.png"), dpi=100)
        plt.close()

    print(f"P3 ates: {sum(int(r['n_fires']) for r in rows)}/{len(rows)}; "
          f"M3(E6p-haric): ring={m['M3_ring']} res4={m['M3_res4']}")
    print(f"M4 seviyeler: {m['M4_levels']}")
    print(f"M5: {json.dumps(m['M5'], sort_keys=True)}")
    print(f"M6 across: {m['M6_across']}")
    print(f"M7: {json.dumps(m['M7'], sort_keys=True)}")
    print(f"skor: ring={sc_r} res4={sc_b} -> K1 karari: {decision}")
    print("Kapilar: " + " ".join(f"{k}={v}" for k, v in m["gates"].items()))
    if bad:
        raise SystemExit(f"SIFIR-BAG IHLALI: {bad}")
    print("OZET-P0B-ANALYZE: " + " ".join(
        f"{k}={v.split()[0]}" for k, v in m["gates"].items())
        + f" K1={decision}")
    if not g1:
        raise SystemExit("G1 BATTI")


if __name__ == "__main__":
    main()
