"""T-AMP analizi — T_AMP_SPEC.md §5/§7. Kosudan ONCE yazildi (kilit).

1. Manifest kilidi (tren + A/B PARAMS + relay_L==7).
2. Kilitli mesafe formulleri:
   d_A = farkli-atesli-readout sayisi + soma Linf (12x200 iz)
   d_B = (ates-kumesi farki?1:0) + |Dmax_soma| + |Dmax_eff| + |Dilk_ates|
3. T-AMP: ayni-Dt capraz-faz mesafesi > ayni-faz genlik mesafesi,
   sistematik (3 Dt) + tekrarlanabilir + esit-surus raporlu.
4. B varis ongorusu: slot2/slot8 farki = 6L = 42 (kontrol).
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
LOCK_TRAIN = {"n_pulse": 5, "isi": 12, "t0": 50, "horizon": 200}
LOCK_A = {"n_readout": 12, "feed_amp": 1.0, "common_k2k3": True}
LOCK_B = {"chain": 12, "chain_amp": 2.0, "feed_amp": 1.0}

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_PLOT = True
except Exception:
    HAS_PLOT = False


def parse_state(s):
    if s == "-":
        return []
    return [tuple(map(int, p.split(","))) if p != "-" else () for p in
            s.split(";")]


def load_traces_a():
    tr = {}
    with open(os.path.join(OUT, "tamp_traces_a.csv")) as f:
        for r in csv.DictReader(f):
            tr.setdefault(int(r["rid"]), []).append(
                [float(r[f"ro{i}"]) for i in range(12)])
    return tr


def main():
    man = json.load(open(os.path.join(OUT, "tamp_manifest.json")))["manifest"]
    assert man["train"] == LOCK_TRAIN, f"KILIT: {man['train']}"
    assert man["A_PARAMS"] == LOCK_A, f"KILIT A: {man['A_PARAMS']}"
    assert man["B_PARAMS"] == LOCK_B, f"KILIT B: {man['B_PARAMS']}"
    assert man["relay_L"] == 7, f"KILIT L: {man['relay_L']}"
    print("manifest kilidi OK")

    with open(os.path.join(OUT, "tamp_runs.csv")) as f:
        rows = list(csv.DictReader(f))
    tra = load_traces_a()
    m = {}
    m["M1"] = all(r["repeat_ok"] == "1" for r in rows)

    def get(proto, exp, phi_b=None, dt=None, order=None, amp=None):
        out = [r for r in rows if r["proto"] == proto and r["exp"] == exp]
        if phi_b is not None:
            out = [r for r in out if r["phi_b"] == str(phi_b)]
        if dt is not None:
            out = [r for r in out if r["dt"] == str(dt)]
        if order is not None:
            out = [r for r in out if r["order"] == order]
        if amp is not None:
            out = [r for r in out if r["amp"] == str(amp)]
        assert len(out) == 1, (proto, exp, phi_b, dt, order, amp, len(out))
        return out[0]

    def d_A(r, s):
        fa, fb = parse_state(r["fire_state"]), parse_state(s["fire_state"])
        ndiff = sum(1 for a, b in zip(fa, fb) if set(a) != set(b))
        ta, tb = tra[int(r["rid"])], tra[int(s["rid"])]
        linf = max(abs(a - b) for ra, rb in zip(ta, tb)
                   for a, b in zip(ra, rb))
        return ndiff, round(linf, 6)

    def first(s):
        return int(s.split(",")[0]) if s != "-" else -1

    def d_B(r, s):
        fs = set() if r["fire_state"] == "-" else set(r["fire_state"].split(","))
        gs = set() if s["fire_state"] == "-" else set(s["fire_state"].split(","))
        return ((0 if fs == gs else 1), round(abs(float(r["max_soma"])
                                                  - float(s["max_soma"])), 6),
                round(abs(float(r["max_eff"]) - float(s["max_eff"])), 6),
                abs(first(r["fire_state"]) - first(s["fire_state"])))

    res = {}
    for proto, dd in (("A", d_A), ("B", d_B)):
        cross, ctl, nin = {}, {}, {}
        for dt in ("5", "10", "30"):
            a = get(proto, "CORE", 60, dt, "AB", 1.0)
            b = get(proto, "CORE", 240, dt, "AB", 1.0)
            c = get(proto, "AMPCTL", 60, 10, "AB", 1.0)
            d = get(proto, "AMPCTL", 60, 10, "AB", 1.25)
            cross[dt] = dd(a, b)
            nin[dt] = (a["n_in"], b["n_in"])
        ctl = dd(c, d)
        asy = {}
        for phi_b in (60, 240):
            for dt in ("5", "10", "30"):
                ab = get(proto, "CORE", phi_b, dt, "AB", 1.0)
                ba = get(proto, "ORD", phi_b, dt, "BA", 1.0)
                asy[(phi_b, dt)] = dd(ab, ba)
        sc = [get(proto, "SCALE", s * 30, 10, "AB", 1.0) for s in range(12)]
        if proto == "A":
            states = set((tuple(tuple(sorted(set(p))) if isinstance(p, tuple)
                                   else p for p in parse_state(r["fire_state"])),
                          round(float(r["max_soma"]), 6)) for r in sc)
        else:
            states = set((r["fire_state"], round(float(r["max_soma"]), 6))
                         for r in sc)
        res[proto] = {"cross": cross, "ampctl": ctl, "n_in": nin,
                      "asym": {f"{k[0]}@{k[1]}": v for k, v in asy.items()},
                      "n_scale_states": len(states)}
    m["sep"] = res

    # B varis ongorusu: B-dal ilk-zincir-cikisi farki == 42; A-dal kontrol ~0
    arr = {}
    for phi_b in (60, 240):
        r = get("B", "CORE", phi_b, 10, "AB", 1.0)
        arr[phi_b] = list(map(int, r["arrAB"].split(";")))
    m["arrival"] = {"phi60": arr[60], "phi240": arr[240],
                    "dB": arr[60][1] - arr[240][1],
                    "dA_control": arr[60][0] - arr[240][0],
                    "predicted_dB": 42}

    def tamp_pass(proto):
        r = res[proto]
        ctl_mag = (r["ampctl"][0] + r["ampctl"][1] if proto == "A"
                   else sum(r["ampctl"]))
        ok = True
        for dt in ("5", "10", "30"):
            c = r["cross"][dt]
            mag = (c[0] + c[1] if proto == "A" else sum(c))
            if not (mag > ctl_mag and mag > 0):
                ok = False
            if r["n_in"][dt][0] != r["n_in"][dt][1]:
                ok = False
        return ok, ctl_mag

    verdicts = {}
    for proto in ("A", "B"):
        ok, ctl = tamp_pass(proto)
        verdicts[proto] = ("KORUR" if ok else "KORUMAZ", ctl)
    m["verdicts"] = {k: {"hukum": v[0], "ampctl_mag": v[1]} for k, v in
                     verdicts.items()}
    m["complexity"] = {
        "A": "K29 + 12 readout = 41 noron; slot-basi 1 hat (+ortak-kip)",
        "B": "K29 + 24 role + P3 = 54 noron; faz-basi tap (12 konum)"}
    m["carrier"] = {
        "A": "hangi-readout (mekan) — olculen: aktif readout kumesi",
        "B": "varis-zamani (zaman) — olculen: zincir-cikis + P3 imzasi"}

    bad = []
    for nm in ("tamp_common.py", "tamp_a.py", "tamp_b.py", "tamp_run.py",
               "tamp_analyze.py"):
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

    with open(os.path.join(OUT, "tamp_metrics.json"), "w") as f:
        json.dump(m, f, indent=1, sort_keys=True, default=str)

    print(f"M1 determinizm: {'OK' if m['M1'] else 'BATTI'}")
    for proto in ("A", "B"):
        r = res[proto]
        print(f"[{proto}] capraz-faz: {r['cross']} | genlik-kontrol: "
              f"{r['ampctl']} | n_in: {r['n_in']}")
        print(f"[{proto}] asimetri: {r['asym']} | olcek-durum: "
              f"{r['n_scale_states']}/12")
    print(f"varis: {m['arrival']} (ongoru dB=42)")
    print("hukum: " + " ".join(f"{k}={v['hukum']}" for k, v in
                               m["verdicts"].items()))
    if bad:
        raise SystemExit(f"SIFIR-BAG IHLALI: {bad}")
    print("OZET-TAMP-ANALYZE: " + " ".join(
        f"{k}={v['hukum']}" for k, v in m["verdicts"].items()))
    if not m["M1"]:
        raise SystemExit("G1 BATTI")


if __name__ == "__main__":
    main()
