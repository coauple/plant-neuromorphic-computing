"""KPR1 analiz: N_sig / amp_break / S_share / Δ_d + 3 yonlu hukum.
Kullanim: python3 pattern/kpr1_analyze.py
Cikti: pattern/p0_out/kpr1_budget.json (+ stdout tablosu).
N_sig: KBHP R0 imzasiyla AYNI (birim-basina g0[::10]+ates-demeti x6 / legacy).
"""
import csv
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "pattern", "p0_out")


def rnd(v, nd=9):
    if isinstance(v, (list, tuple)):
        return tuple(round(float(x), nd) for x in v)
    return round(float(v), nd)


def load():
    with open(os.path.join(OUT, "kpr1_runs.json")) as f:
        store = json.load(f)
    arms = {}
    with open(os.path.join(OUT, "kpr1_axes.csv")) as f:
        for r in csv.DictReader(f):
            arms[r["id"]] = r
    return store, arms


def n_sig_v2(sims):
    sigs = []
    for tr in sims:
        sigs.append(tuple((rnd(tr[str(u)]["g0"][::10]),
                           tuple(tr[str(u)]["fire_ticks"]))
                          for u in range(6)))
    return len(set(sigs))


def n_sig_leg(sims):
    sigs = [(rnd(tr["g0"][::10]), tuple(tr["fire_ticks"])) for tr in sims]
    return len(set(sigs))


def s_share_v2(sims):
    vals = [tr[str(u)]["S_share"] for tr in sims for u in range(6)]
    return sum(vals) / max(1, len(vals))


def s_share_leg(sims):
    vals = [tr["S_share"] for tr in sims]
    return sum(vals) / max(1, len(vals))


def main():
    store, arms = load()
    rep = {"arms": {}}
    for aid, a in arms.items():
        arch = a["arch"]
        # sim id kurali (run() ile ayni): kpr_{kol}_d{d}[_a{amp}]_s{s}
        ids = []
        for s in range(12):
            sid = f"kpr_{a['kol']}_d{a['dstep']}"
            if a.get("amp"):
                sid += f"_a{a['amp']}"
            sid += f"_s{s}"
            ids.append(sid)
        sims = [store[i] for i in ids]
        if arch == "v2":
            rep["arms"][aid] = {"N_sig": n_sig_v2(sims),
                                "S_share": round(s_share_v2(sims), 4)}
        else:
            rep["arms"][aid] = {"N_sig": n_sig_leg(sims),
                                "S_share": round(s_share_leg(sims), 4)}
    g = rep["arms"]
    dd = {}
    for kol in ("A0", "A1", "A2", "A3", "A4", "L1", "L2"):
        n0 = g.get(f"kpr_{kol}_d0", {}).get("N_sig")
        n1 = g.get(f"kpr_{kol}_d1", {}).get("N_sig")
        if n0 is not None and n1 is not None:
            dd[kol] = n1 - n0
    rep["delta_d"] = dd
    br = {}
    for kol in ("A5", "A6"):
        for d in ("0", "1"):
            cand = [(float(a),
                     g[f"kpr_{kol}_d{d}_a{a}"]["N_sig"])
                    for a in ("0.05", "0.1", "0.2", "0.3", "0.5", "1.0")]
            below = [a for a, n in cand if n < 10]
            br[f"{kol}_d{d}"] = {"amp_break": max(below) if below else None,
                                 "egri": cand}
    rep["amp_break"] = br
    B = g["kpr_A1_d1"]["N_sig"]
    C = g["kpr_A2_d1"]["N_sig"]
    N = g["kpr_A0_d1"]["N_sig"]
    if B == 12:
        verdict = "HAYIR: K1, 12/12 ICIN GEREKLI DEGIL -> Asama 2 YANLIS HEDEF"
    else:
        verdict = "EVET: K1 tasiyici -> Asama 2 hakli hedef"
    if C == 12:
        verdict += " + BUYUK BULGU: K2/K3 gereksiz"
    rep["hukum"] = {"B": B, "C": C, "N": N, "karar": verdict}
    with open(os.path.join(OUT, "kpr1_budget.json"), "w") as f:
        json.dump(rep, f, indent=1)
    print("kol: N_sig d0 | N_sig d1 | Δ_d | S_share")
    for kol in ("A0", "A1", "A2", "A3", "A4", "L1", "L2"):
        r0 = g.get(f"kpr_{kol}_d0", {})
        r1 = g.get(f"kpr_{kol}_d1", {})
        print(f"  {kol}: {r0.get('N_sig')} | {r1.get('N_sig')} | "
              f"{dd.get(kol)} | {r1.get('S_share')}")
    for k, v in br.items():
        print(f"  {k}: amp_break={v['amp_break']} egri={v['egri']}")
    print("HUKUM:", verdict)
    print("OZET-KPR1-ANALIZ: budget yazildi")


if __name__ == "__main__":
    main()
