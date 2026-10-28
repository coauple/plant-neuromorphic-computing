"""IDEN3 analizi — IDEN3_SPEC.md §3. Kosudan ONCE yazildi (kilit).

Manifest kilidi + kontrol assert'leri (darbe/enerji esitligi) +
hukum (DOGRULANDI/CURUTULDU/KISMEN). stdlib-only.
"""
import ast
import csv
import json
import os

import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)

OUT = os.path.join(ENC, "p0_out")
LOCK = {"dts": [0, 2, 5, 8, 10, 15, 20, 30], "phi_a": 120, "phi_b": 90,
        "amp": 4.0, "inh": 1.0,
        "train": {"n_pulse": 5, "isi": 12, "t0": 50, "horizon": 200}}


def winner(fire_state):
    cols = [tuple(map(int, p.split(","))) if p != "-" else ()
            for p in fire_state.split(";")]
    scored = [(len(c), -(c[0] if c else 10 ** 9), -i) for i, c in
              enumerate(cols)]
    best = max(range(12), key=lambda i: scored[i])
    return best if cols[best] else None


def main():
    man = json.load(open(os.path.join(OUT, "iden3_manifest.json")))["manifest"]
    for k, v in LOCK.items():
        assert man[k] == v, f"KILIT IHLALI {k}: {man[k]}"
    print("manifest kilidi OK")

    with open(os.path.join(OUT, "iden3_runs.csv")) as f:
        rows = list(csv.DictReader(f))
    assert all(r["repeat_ok"] == "1" for r in rows), "determinizm BATTI"

    # Kontrol: darbe sayisi + enerji dt-boyu esit mi?
    npulse = set(r["n_pulses"] for r in rows)
    energy = set(r["energy"] for r in rows)
    assert len(npulse) == 1 and len(energy) == 1, (
        f"KONTROL BOZUK: {npulse} {energy}")
    print(f"kontrol OK: darbe={npulse.pop()}, enerji={energy.pop()} ( sabit)")

    # Girdi sayilari (K-atesi) dt-boyu esit mi? (rapor; esitlik beklenir)
    rin = {}
    for r in rows:
        rin[int(r["dt"])] = r["ro_in"]
    same_in = len(set(rin.values())) == 1
    print(f"K-girdi esitligi: {'ESIT' if same_in else 'FARKLI (rapor)'}")

    tab = {}
    for r in rows:
        dt = int(r["dt"])
        co = list(map(int, r["coinc"].split(";")))
        tab[dt] = {"winner": winner(r["fire_state"]),
                   "co3": co[3], "co4": co[4]}
    for dt, v in sorted(tab.items()):
        print(f"  dt={dt}: kazanan={v['winner']} co3={v['co3']} "
              f"co4={v['co4']}")
    winners = set(v["winner"] for v in tab.values())
    if len(winners) > 1:
        verdict = "DOGRULANDI (kazanan dt ile degisiyor)"
    else:
        verdict = "CURUTULDU (kazanan sabit)"
    # Kismi dal: degisim yalniz 1 dt'deyse yine degisimdir (yukarida).
    print(f"HUKUM: {verdict}")
    with open(os.path.join(OUT, "iden3_metrics.json"), "w") as f:
        json.dump({"winners": {k: v["winner"] for k, v in sorted(tab.items())},
                   "coinc": {k: (v["co3"], v["co4"]) for k, v in
                             sorted(tab.items())},
                   "k_inputs_equal": same_in, "HUKUM": verdict},
                  f, indent=1, sort_keys=True, default=str)

    bad = []
    for nm in ("iden3.py", "iden3_run.py", "iden3_analyze.py"):
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
    if bad:
        raise SystemExit(f"SIFIR-BAG IHLALI: {bad}")
    print("OZET-IDEN3-ANALYZE: OK")


if __name__ == "__main__":
    main()
