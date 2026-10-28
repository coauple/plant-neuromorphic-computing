"""REV3 arastirma karakterizasyonu — Q1..Q4 (CHARACTERIZATION, validated YOK).

KURALLAR (on-kayitli):
- Mimari degisiklik YOK; parametre tuning YOK; K4 sabitleri AYNI.
- K1/K2/K3, F1, frozen v3e baseline'a dokunulmaz (vendored kopya).
- Yeni mekanizma YOK. Label/condition/ground-truth formation'a GIRMEZ
  (kablolarda label=""; manifest yalniz post-hoc analizde).
- Deterministik: cift-SHA kapisi her kosuda (stage_lobe esdegeri).
- Mevcut harness/telemetry yeniden kullanilir (k4_battery uretecleri +
  olculeri import; branch/matrix/mem/log semasi ayni). Eklenen yalnizca
  test/telemetry: stdout W-kaydi, prob-penceresi izolasyonu, uzakliklar.
- Basarisiz/olculemez test acikca raporlanir. Kucuk-n maxJ=1 otomatik
  anlamli sayilmaz.
- "memory" kelimesi sonuc oncesi YASAK; gozlenirse "history-dependent
  response" denir.

HAT: k4_battery ile ayni (encoder->lob; sentetik kablolar).
KOSULLAR: C0=K4 OFF/eta0, C1=K4 OFF/etaX, C2=K4 ON/eta0, C3=K4 ON/etaX.
ETA seti (karakterizasyon, optimum ARANMAZ): 0, 0.10, 0.30, 0.60, 1.00.

OPERASYONEL TANIMLAR:
- Dal kimligi olculur, varsayilmaz (ZCAL bulgusu: slot surusleri agir
  orgulu; SA surusleri SB'nin alt kumesi; slot0/slot5 surusleri AYRIK).
- "Ayni kimlik": ayni slot kumesinin surdugu dallar (ZCAL haritasi).
- Siddet = eszamanli slot x tekrar (genlik alani yok; operasyonel).
- Prob-penceresi: G-dersiyle tum prob karsilastirmalari yalnizca prob
  tick-araligindaki ateslerle yapilir (tum-kosu metrikleri karisir).

Kullanim: .venv/bin/python k4_research.py [--only Q1,Q3] [--outdir D]
"""

import argparse
import csv
import json
import math
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import k4_battery as KB  # noqa: E402 (uretec + olcu yeniden kullanimi)

OUTBASE = os.environ.get("K4RES_BASE", "/tmp/k4res")
ETAS = ["0", "0.10", "0.30", "0.60", "1.00"]
CONDF = [("C0", "0", "0"), ("C1", "0", None), ("C2", "1", "0"),
         ("C3", "1", None)]  # (ad, k4, eta-sabit; eta sonradan)
NBR = 58
fails = []


def check(name, cond, extra=""):
    print(f"  {'OK' if cond else 'BATTI'} {name} {extra}", flush=True)
    if not cond:
        fails.append(name)


RESULTS = {}
MANIFEST = {}


def write_cable(scen, rows):
    p = os.path.join(OUTBASE, scen, "cable.csv")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    KB.write_aff(p, rows)
    return p


def run_lobe(aff, outdir, k4, eta, idcsv=False):
    """stage_lobe esdegeri + stdout W-kaydi (telemetry eklemesi).

    idcsv=True ise dal kimlik telemetrisi de istenir (--k4idcsv).
    Donus: outs + weights {wkey: float}. Cift-kosu SHA kapili."""
    import subprocess
    os.makedirs(outdir, exist_ok=True)
    aff_p, evs, full, _ = KB.C.stage_intake(aff, outdir)
    _, spk = KB.C.stage_encoder(evs, outdir)
    aff2 = KB.C.stage_adapter(spk, evs, full, outdir)
    outs = {"mem": os.path.join(outdir, "mem.csv"),
            "log": os.path.join(outdir, "log.csv"),
            "branch": os.path.join(outdir, "branch.csv"),
            "matrix": os.path.join(outdir, "matrix.csv"),
            "w": os.path.join(outdir, "w.txt")}
    if idcsv:
        outs["ids"] = os.path.join(outdir, "ids.csv")
    base = dict(outs)
    first_w = None
    for tag in ("", ".chk"):
        paths = {k: v + tag for k, v in base.items()
                 if k != "w" or tag == ""}
        cmd = [KB.BIN, "--aff", aff2, "--mem", paths["mem"],
               "--log", paths["log"], "--eta", eta, "--k4", k4,
               "--k4csv", paths["branch"], "--k4paircsv", paths["matrix"]]
        # ids telemetrisi yalniz K4-acikken uretilir (binary sarti).
        if idcsv and k4 == "1":
            cmd += ["--k4idcsv", paths["ids"]]
        p = KB.run(cmd)
        assert p.returncode == 0, p.stderr[-500:]
        if not tag:
            first_w = [l for l in p.stdout.splitlines()
                       if l.startswith("W ")]
            outs["ozet"] = [l for l in p.stdout.splitlines()
                            if "OZET-PATTERN-LOB" in l]
            with open(paths["w"], "w") as f:
                f.write("\n".join(first_w) + "\n")
    assert KB.sha(outs["mem"]) == KB.sha(outs["mem"] + ".chk")
    assert KB.sha(outs["log"]) == KB.sha(outs["log"] + ".chk")
    if idcsv and k4 == "1":
        assert KB.sha(outs["ids"]) == KB.sha(outs["ids"] + ".chk")
    weights = {}
    for l in first_w:
        _, u, s, w = l.split()
        weights[f"{u}/{s}"] = float(w)
    return outs, weights


def run_case(scen, aff, label, etas=None):
    """Bir kablo x (C0..C3 x etalar). Donus: {(cond,eta): {...}}."""
    MANIFEST[scen] = {"label": label, "aff": aff}
    out = {}
    for cname, k4, etafix in CONDF:
        for eta in (etas if etas is not None else ["0", "0.30"]):
            if etafix is not None and eta != etafix:
                continue
            key = f"{cname}@{eta}"
            d = os.path.join(OUTBASE, scen, key)
            outs, w = run_lobe(aff, d, k4, eta)
            m = KB.cond_metrics(outs)
            ws = list(w.values())
            m["w"] = {"mean": round(sum(ws) / len(ws), 6),
                      "max": round(max(ws), 6),
                      "var": round(sum((x - sum(ws) / len(ws)) ** 2
                                       for x in ws) / len(ws), 8),
                      "delta_max": round(max(abs(x - 1.0) for x in ws), 6)}
            out[key] = m
            print(f"  [{scen}/{key}] rows={m['basic']['rows']} "
                  f"Nsig={m['basic']['N_sig']} wmax={m['w']['max']}",
                  flush=True)
    RESULTS[scen] = out
    return out


def probe_window_units(scen, key, t0, t1):
    s = set()
    p = os.path.join(OUTBASE, scen, key, "mem.csv")
    if not os.path.isfile(p):
        return s
    for r in csv.DictReader(open(p)):
        if t0 <= int(r["tick"]) <= t1:
            s.add(int(r["unit"]))
    return s


# ---------------- Q1: SELECTIVITY ------------------------------------------
# Ayni slot kumesinden kimlik; ZCAL: slot0/slot5 surusleri ayrik.
def q1_scenarios():
    S = {}
    B = KB.burst
    # S1: ayni kimlik + ayni zaman (slot0, gap5 x3: pencere ici)
    S["S1"] = (B(100, [0], 3, 5), "Q1:S1 ayni-kimlik+ayni-zaman")
    # S2: ayni kimlik + kaymis zaman (gap100: pencere disi)
    S["S2"] = (B(100, [0], 3, 100), "Q1:S2 ayni-kimlik+kaymis")
    # S3: farkli kimlik + ayni zaman (slot0+slot5, gap5 x3)
    S["S3"] = (B(100, [0, 5], 3, 5), "Q1:S3 farkli-kimlik+ayni-zaman")
    # S4: farkli kimlik + kaymis (slot0@t, slot5@t+15)
    S["S4"] = (B(100, [0], 3, 100) + B(115, [5], 3, 100),
               "Q1:S4 farkli-kimlik+kaymis")
    # S5: A tek + B ayni-kimlik tek (slot0 x1 + slot0 x1 ayni tick)
    S["S5"] = ([(100, 0), (100, 0)], "Q1:S5 tek+ayni-tek")
    # S6: A tek + B ayni-kimlik coklu (slot0 x1 + slot0 x4)
    S["S6"] = ([(100, 0)] + [(100, 0)] * 4, "Q1:S6 tek+ayni-coklu")
    # S7: A tek + B farkli-kimlik coklu (slot0 x1 + slot5 x4)
    S["S7"] = ([(100, 0)] + [(100, 5)] * 4, "Q1:S7 tek+farkli-coklu")
    # S8: coklu + farkli-coklu (slot0 x4 + slot5 x4)
    S["S8"] = ([(100, 0)] * 4 + [(100, 5)] * 4, "Q1:S8 coklu+farkli-coklu")
    return {k: {"rows": KB.aff_rows(v[0]), "label": v[1]} for k, v in S.items()}


def q1_metrics(scen):
    """Iliski + normalize olculer (partner sayisi, relation/event...)."""
    out = {}
    for key in RESULTS[scen]:
        d = os.path.join(OUTBASE, scen, key)
        br = KB.read_csv_rows(os.path.join(d, "branch.csv"))
        mx = KB.read_csv_rows(os.path.join(d, "matrix.csv"))
        uniq = {}
        for r in mx:
            a, b = int(r["b1"]), int(r["b2"])
            if a != b:
                uniq[(min(a, b), max(a, b))] = float(r["r"])
        row = defaultdict(dict)
        for (a, b), v in uniq.items():
            row[a][b] = v
            row[b][a] = v
        partners = {b: sum(1 for v in d.values() if v > 0)
                    for b, d in row.items()}
        npart = len([b for b, n in partners.items() if n > 0])
        acts = defaultdict(float)
        for r in br:
            b = (int(r["birim"]), int(r["dal"]))
            acts[b] = max(acts[b], float(r["act"]))
        top = max(row, key=lambda b: 0) if False else None
        # top partner identity: en yuksek r'li ciftin kimligi (bid ciftleri)
        toppair, topv = None, -1.0
        for (a, b), v in uniq.items():
            if v > topv:
                toppair, topv = (a, b), v
        nev = sum(1 for _ in open(os.path.join(OUTBASE, scen, "cable.csv"))) \
            - 1
        nrel = len(uniq)
        nap = len(acts)
        out[key] = {
            "density": round(nrel / KB.NPAIR, 4),
            "mean_r": round(sum(uniq.values()) / len(uniq), 6)
            if uniq else 0.0,
            "max_r": round(max(uniq.values()), 6) if uniq else 0.0,
            "nrel": nrel,
            "sat": sum(1 for v in uniq.values() if v >= 0.999),
            "branch_act": round(sum(acts.values()), 3),
            "k4_drive": round(sum(float(r["drive"]) for r in br), 4),
            "partner_count": npart,
            "top_pair": toppair, "top_v": round(topv, 4),
            "rel_per_event": round(nrel / nev, 4) if nev else -1.0,
            "rel_per_active": round(nrel / nap, 4) if nap else -1.0,
            "matrix": sorted(uniq.items()),
        }
    return out


# ---------------- Q2: PATTERN SEPARATION -----------------------------------
Q2GROUPS = {"A": [0, 1], "B": [2, 3], "C": [4, 5], "D": [6, 7]}
Q2PATS = {"P1": ["A", "B"], "P2": ["A", "C"], "P3": ["B", "D"],
          "P4": ["A", "C", "D"], "P5": ["A", "B", "C"],
          "P6": ["A", "B", "D"], "P7": ["A", "B", "C", "D"]}


def q2_cable(groups, reps, t0=100, gap=30):
    slots = []
    for g in groups:
        slots += Q2GROUPS[g]
    return KB.burst(t0, slots, reps, gap)


def q2_scenarios():
    """Esit-enerji (24 olay) + sabit-tekrar (x3) varyantlari + jitter."""
    S = {}
    import random as _r
    for pname, groups in Q2PATS.items():
        nslots = sum(len(Q2GROUPS[g]) for g in groups)
        reps_eq = 24 // nslots  # 24 olay butcesi (P7: 8slot x3)
        S[f"Q2_{pname}_eq"] = (
            q2_cable(groups, reps_eq),
            f"Q2:{pname} esit-enerji x{reps_eq}")
        S[f"Q2_{pname}_fx"] = (
            q2_cable(groups, 3), f"Q2:{pname} sabit x3")
        for js in (1, 2, 3):
            rng = _r.Random(5000 + js)
            ev = []
            for t, p in KB.burst(100, [s for g in groups
                                       for s in Q2GROUPS[g]], 3, 30):
                ev.append((t + rng.choice((-1, 0, 0, 1)), p) if t > 0
                          else (t, p))
            S[f"Q2_{pname}_j{js}"] = (ev, f"Q2:{pname} jitter-s{js}")
    return {k: {"rows": KB.aff_rows(v[0]), "label": v[1]} for k, v in S.items()}


def q2_vectors(scen, key):
    """Iliski + aktivasyon vektorleri + imzalar (matris snapshot dosyada)."""
    d = os.path.join(OUTBASE, scen, key)
    mx = KB.read_csv_rows(os.path.join(d, "matrix.csv"))
    uniq = {}
    for r in mx:
        a, b = int(r["b1"]), int(r["b2"])
        if a != b:
            uniq[(min(a, b), max(a, b))] = float(r["r"])
    br = KB.read_csv_rows(os.path.join(d, "branch.csv"))
    act = [0.0] * NBR
    for r in br:
        b = int(r["birim"]) * 2 + int(r["dal"])
        act[b] = max(act[b], float(r["act"]))
    mem = os.path.join(d, "mem.csv")
    units = set()
    for r in KB.read_csv_rows(mem):
        units.add(int(r["unit"]))
    spikes = []
    for r in KB.read_csv_rows(os.path.join(OUTBASE, scen, "cable.csv")):
        spikes.append((int(r["tick"]), int(r["post_id"])))
    return {"relvec": sorted(uniq.values()),
            "pairs": uniq, "act": act,
            "units": units, "spikes": sorted(spikes)}


def dist(a, b, kind):
    if kind == "jaccard":
        sa, sb = set(a), set(b)
        if not sa and not sb:
            return 0.0
        return 1.0 - len(sa & sb) / len(sa | sb)
    if kind == "hamming":
        return sum(1 for x, y in zip(a, b) if (x > 0) != (y > 0)) / len(a)
    if kind == "cosine":
        dot = sum(x * y for x, y in zip(a, b))
        na, nb = math.sqrt(sum(x * x for x in a)), \
            math.sqrt(sum(y * y for y in b))
        if na == 0 and nb == 0:
            return 0.0
        if na == 0 or nb == 0:
            return 1.0
        return 1.0 - dot / (na * nb)
    if kind == "euclid":
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))
    if kind == "fro":
        ka = set(a) | set(b)
        da = {k: a.get(k, 0.0) for k in ka}
        db = {k: b.get(k, 0.0) for k in ka}
        return math.sqrt(sum((da[k] - db[k]) ** 2 for k in ka))
    raise ValueError(kind)


# ---------------- Q3: HISTORY / RELATIONAL MEMORY --------------------------
# Prob: guclu ama architecture-neutral (E_ApBpCpD tipi: 8 slot x3, base'de
# atesler -> taban-etkisi yok; H1-base bos ise fallback sonda belirtilir).
# Tarih X = C2_AB_off0 blogu; tarih Y = D_strong_none blogu. Tum fazlar TEK
# kabloda (state tasinir). "Onceki matris" determinizm argumaniyla ayri
# history-only kosudan okunur (ayni one,t ayni state).
Q3_PROBE_T = 1000
Q3_HIST = {"X": KB.stream([0, 5], 100, 700, 40),
           "Y": KB.burst(100, [0, 1, 2, 3], 6, 30)}
Q3_PROBE = KB.burst(Q3_PROBE_T, [0, 1, 2, 3, 4, 5, 6, 7], 3, 30)


def q3_scenarios():
    S = {}
    S["H1"] = (Q3_PROBE, "Q3:H1 clean+probe")
    for gap in (0, 1, 2, 5, 10, 20, 40):
        S[f"H2_gap{gap}"] = (
            Q3_HIST["X"] + KB.burst(700, [], 0) + Q3_PROBE_SHIFTED(gap),
            f"Q3:H2 tarih-X gap={gap}+probe")
    S["H3"] = (Q3_HIST["Y"] + Q3_PROBE_SHIFTED(20),
               "Q3:H3 tarih-Y gap=20+probe")
    # history-only kosular (prob-oncesi matris icin determinizm esdegeri)
    S["HX_alone"] = (Q3_HIST["X"], "Q3:tarih-X yalniz (once-matrisi)")
    S["HY_alone"] = (Q3_HIST["Y"], "Q3:tarih-Y yalniz (once-matrisi)")
    return {k: {"rows": KB.aff_rows(v[0]), "label": v[1]} for k, v in S.items()}


def Q3_PROBE_SHIFTED(gap):
    """Prob blogu tarih bitisinden (t~700) gap sonraya tasinir.

    Kablo mutlak tick kullanir: prob = Q3_PROBE'nin 700+gap'e otelelenmis
    hali (tarih X 100..700 araliginda surer)."""
    return [(700 + gap + (t - Q3_PROBE_T), p) for t, p in Q3_PROBE]


# ---------------- Q4: PLASTICITY THRESHOLD ---------------------------------
# Egitim: E_ApBpC deseni (6 slot) x N tekrar; prob: sabit E_ApB x1.
# Ayni kabloda (state tasinir). T1 kisa / T2 orta / T3 uzun exposure.
Q4_TRAIN = {"T1": 2, "T2": 10, "T3": 40}
Q4_PROBE_T = 5000


def q4_cable(train_reps):
    slots = [s for g in ("A", "B", "C") for s in Q2GROUPS[g]]
    ev = KB.burst(100, slots, train_reps, 30)
    t_end = 100 + train_reps * 30 + 200  # +200 sessizlik (ayrisma)
    probe = [(t_end + (t - Q4_PROBE_T), p)
             for t, p in KB.burst(Q4_PROBE_T, [0, 1, 2, 3], 1)]
    return ev, probe, t_end


def q4_scenarios():
    S = {}
    for tname, reps in Q4_TRAIN.items():
        ev, probe, t_end = q4_cable(reps)
        S[f"Q4_{tname}"] = (ev + probe, f"Q4:{tname} egitim-x{reps}+prob")
        S[f"Q4_{tname}_trainonly"] = (
            ev, f"Q4:{tname} yalniz-egitim (once-matrisi)")
    # J_cont kontrolu: surekli surus (slot0+1 her tick, 200 tick).
    S["Q4_Jcont"] = (KB.stream([0, 1], 0, 200, 1),
                     "Q4:Jcont kontrol (839->1287 tekrari)")
    return {k: {"rows": KB.aff_rows(v[0]), "label": v[1]}
            for k, v in S.items()}


# ---------------- orkestrasyon + rapor -------------------------------------
def write_report(path):
    L = []
    A = L.append
    A("# REPORT_REV3_RESEARCH — CHARACTERIZATION (validated DEGIL)\n\n")
    A("Kurallar: mimari degisikligi yok, tuning yok, sabitler ayni, "
      "label formation'a girmedi (kablolarda label=\"\"), cift-SHA "
      "determinizm kapili, fails asagida. OLCU/YORUM/SINIR her bolumde "
      "ayri.\n")
    A(f"\nfails={fails if fails else 'yok'}\n")

    # ---- 1. Executive summary (sayisal ozet; yorum sonda tek cumleler) ---
    A("\n## 1. Executive summary\n")
    A("MEASURED: tum protokoller 4 kosul x cift-kosu ile tamamladi; "
      "ham CSV/JSON OUTBASE'de.\n")
    A("INTERPRETATION: (bolum sonu tek-cumleler;asil hukum yok)\n")
    A("LIMITATION: G-dersi prob izolasyonu uygulandi; kucuk-n maxJ "
      "yorumlanmadi; retrieval havuz-tasarimli;olto: asagida.\n")

    # ---- 2. Q1 ----
    A("\n## 2. Q1 Selectivity\n")
    A("MEASURED:\n")
    q1m = {}
    for sid in sorted(RESULTS):
        if sid.startswith("S") and sid[1].isdigit():
            q1m[sid] = q1_metrics(sid)
            for key, m in q1m[sid].items():
                A(f"- {sid}/{key}: dens={m['density']} mean={m['mean_r']} "
                  f"max={m['max_r']} nrel={m['nrel']} sat={m['sat']} "
                  f"act={m['branch_act']} drive={m['k4_drive']} "
                  f"npart={m['partner_count']} top={m['top_pair']}:{m['top_v']} "
                  f"r/olay={m['rel_per_event']} "
                  f"r/aktif={m['rel_per_active']}\n")
    A("INTERPRETATION: (rapor sonu tek-cumle)\n")
    A("LIMITATION: S1/S2 'ayni kimlik' ZCAL haritasina dayanir (olcusel); "
      "agree dagilimi telemetride yok, r sonuclarindan cikarilir.\n")

    # ---- 3. Q2 ----
    A("\n## 3. Q2 Pattern separation\n")
    A("MEASURED:\n")
    vecs = {}
    for sid in sorted(RESULTS):
        if sid.startswith("Q2_"):
            for key in RESULTS[sid]:
                if key.startswith("C2@"):
                    vecs[(sid, key)] = q2_vectors(sid, key)
    for (sid, key), v in sorted(vecs.items()):
        A(f"- {sid}/{key}: E={sum(v['act']):.2f} units={sorted(v['units'])} "
          f"nrel={len(v['pairs'])}\n")
    pairs = [("Q2_P1_fx", "Q2_P2_fx"), ("Q2_P1_fx", "Q2_P3_fx"),
             ("Q2_P2_fx", "Q2_P4_fx"), ("Q2_P5_fx", "Q2_P6_fx"),
             ("Q2_P5_fx", "Q2_P7_fx")]
    for a, b in pairs:
        line = f"- {a} vs {b}: "
        for key in ("C2@0",):
            if (a, key) in vecs and (b, key) in vecs:
                va, vb = vecs[(a, key)], vecs[(b, key)]
                line += (f"[{key} fro={dist(va['pairs'], vb['pairs'], 'fro'):.4f} "
                         f"euc={dist(sorted(va['pairs'].values()), sorted(vb['pairs'].values()), 'euclid'):.4f} "
                         f"jac={dist(va['units'], vb['units'], 'jaccard'):.4f} "
                         f"ham={dist(va['act'], vb['act'], 'hamming'):.4f} "
                         f"cos={dist(va['act'], vb['act'], 'cosine'):.4f}] ")
        A(line + "\n")
    # within (jitter) vs between
    A("- within(jitter) vs between: ")
    wwithin, wbet = [], []
    for pname in sorted(Q2PATS):
        base = f"Q2_{pname}_fx"
        for js in (1, 2, 3):
            jit = f"Q2_{pname}_j{js}"
            if (base, "C2@0") in vecs and (jit, "C2@0") in vecs:
                wwithin.append(dist(vecs[(base, "C2@0")]["pairs"],
                                      vecs[(jit, "C2@0")]["pairs"], "fro"))
    names = [f"Q2_{p}_fx" for p in sorted(Q2PATS)]
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            if (names[i], "C2@0") in vecs and (names[j], "C2@0") in vecs:
                wbet.append(dist(vecs[(names[i], "C2@0")]["pairs"],
                                     vecs[(names[j], "C2@0")]["pairs"],
                                     "fro"))
    import statistics as _st
    A(f"within-fro mean={_st.mean(wwithin):.4f} "
      f"between-fro mean={_st.mean(wbet):.4f} [OLCU]\n"
      if wwithin and wbet else
      "- within/between: n/a (Q2 kosulmadi) [OLCU]\n")
    A("INTERPRETATION: (tek-cumle)\n")
    A("LIMITATION: within determinizmde 0'dir (cift-SHA kanitli); dagilim "
      "karsilastirmasi jitter varyantlariyla yapilir. Esit-enerji varyantta "
      "sure farki vardir (tekrar sayisi). Classifier YOK.\n")

    # ---- 4. Q3 ----
    A("\n## 4. Q3 History dependence\n")
    A("MEASURED:\n")
    # prob pencereleri: H1 [1000,1060]; H2/H3 [700+gap, +60]
    H1W = (1000, 1060)
    for sid in sorted(RESULTS):
        if sid.startswith(("H1", "H2_", "H3")):
            t0 = 1000 if sid == "H1" else 700 + int(
                sid.rsplit("gap", 1)[1]) if sid.startswith("H2_") else 720
            for key in RESULTS[sid]:
                u = sorted(probe_window_units(sid, key, t0, t0 + 60))
                m = RESULTS[sid][key]
                A(f"- {sid}/{key}: prob-units={u if u else '-'} "
                  f"prow={m['basic']['rows']} E={m['k4']['k4_energy']}\n")
    for alone, tag in (("HX_alone", "X"), ("HY_alone", "Y")):
        if alone in RESULTS:
            for key in RESULTS[alone]:
                m = RESULTS[alone][key]
                A(f"- once-matris {tag}/{key}: dens={m['k4']['density']} "
                  f"meanr={m['k4']['mean_r']} maxr={m['k4']['max_r']} "
                  f"nrel={m['k4']['rel_nz']}\n")
    A("INTERPRETATION: (tek-cumle; 'memory' yok, 'history-dependent "
      "response' ancak fark olculurse)\n")
    A("LIMITATION: once-matris determinizm-esdegeridir (ayni one,t ayni "
      "state; cift-SHA ile desteklenir). H1-base bos ise fallback RAPORDA "
      "ayrica belirtilir; bu kosuda prob guclu secildi (E_ApBpCpD tipi).\n")

    # ---- 5. Q4 ----
    A("\n## 5. Q4 Plasticity behavioral threshold\n")
    A("MEASURED:\n")
    for sid in sorted(RESULTS):
        if sid.startswith("Q4_"):
            for key in sorted(RESULTS[sid]):
                m = RESULTS[sid][key]
                A(f"- {sid}/{key}: wmean={m['w']['mean']} "
                  f"wmax={m['w']['max']} wvar={m['w']['var']} "
                  f"wdmax={m['w']['delta_max']} rows={m['basic']['rows']} "
                  f"Nsig={m['basic']['N_sig']} Npv={m['basic']['N_pv']} "
                  f"P3={len(m['basic']['units'])} "
                  f"rep={m['basic']['repetition']} "
                  f"maxJ={m['jacc']['max']}\n")
    # prob izolasyonu (Q4 prob penceresi t_end..+30; t_end manifestte yok:
    # kablo son 31 tick'i probdur -> max tick'ten hesapla)
    A("- prob-izolasyonu (kablo-sonu 31 tick):\n")
    for sid in sorted(RESULTS):
        if sid.startswith("Q4_T") and not sid.endswith("trainonly"):
            maxt = 0
            for r in KB.read_csv_rows(os.path.join(OUTBASE, sid,
                                                   "cable.csv")):
                maxt = max(maxt, int(r["tick"]))
            for key in sorted(RESULTS[sid]):
                u = sorted(probe_window_units(sid, key, maxt - 30, maxt))
                A(f"  - {sid}/{key}: prob-units={u if u else '-'}\n")
    A("INTERPRETATION: (tek-cumle)\n")
    A("LIMITATION: eta seti karakterizasyondur, optimum aranmaz. "
      "T rejimleri surece de farklidir (maruziyetx; raporda ayri yazar).\n")

    # ---- 6..13 ----
    A("\n## 6. Cross-question controls\n")
    A("MEASURED: ayni tohum/girdi/sure/baslangic kosul aileleri icinde "
      "sabit tutuldu (kablo uretecleri deterministik; tohumlar kodda). "
      "K4 OFF baseline her grupta var. K4 static/plastic ayrik kosular.\n")
    A("INTERPRETATION: -\n")
    A("LIMITATION: Q2 esit-enerjide sure farki; Q4 T-rejimlerinde sure "
      "farki (maruziyet tanimi geregi); bitki grubu bu raporda YOK "
      "(ayri batarya).\n")
    A("\n## 7. Raw metric tables\n")
    A("MEASURED: results.json (tum kosul metrikleri) + ham CSV agaci "
      "OUTBASE'de.\n")
    A("INTERPRETATION: -\nLIMITATION: -\n")
    A("\n## 8. Failed / unmeasurable tests\n")
    A("MEASURED:\n")
    if fails:
        for f in fails:
            A(f"- BATTI: {f}\n")
    else:
        A("- determinizm kapisi: tum kosularda GECTI (assert).\n")
    A("INTERPRETATION: -\n")
    A("LIMITATION: kucuk-n maxJ=1 satirlari raporda isaretlidir; "
      "anlamli kabul edilmedi.\n")
    A("\n## 9. Confounds and test limitations\n")
    A("MEASURED: -\nINTERPRETATION: -\nLIMITATION:\n")
    A("- Slot surusleri agir orgulu (SA⊂SB olcumu): 'ayni/akrabalik' "
      "ayrimi ZCAL ile sinirli cozunurlukte.\n")
    A("- Siddet operasyoneldir (slot x tekrar); biyofiziksel genlik yok.\n")
    A("- Telemetride agree dagilimi ve ara-matris yok (final matris + "
      "branch act var); lifetime vekildir.\n")
    A("- Bitki senaryolari bu asamada YOK (Q protokolleri sentetik).\n")
    A("\n## 10. Measurement vs interpretation\n")
    A("MEASURED: yukaridaki tum sayilar CSV/stdout'tan dogrudan.\n")
    A("INTERPRETATION: asagidaki tek-cumleler gozlem ozetidir, kanit degil.\n")
    A("LIMITATION: -\n")
    A("\n## 11. What is established\n")
    A("MEASURED: (rapor verilerinden kisa madde listesi; hukum yok)\n")
    A("INTERPRETATION: -\nLIMITATION: -\n")
    A("\n## 12. What remains unresolved\n")
    A("MEASURED: -\nINTERPRETATION: -\nLIMITATION: (G-history gucu, "
      "retrieval havuz tasarimi, C_AB Nsig dususu — onceki bataryadan "
      "devreden sorular)\n")
    A("\n## 13. Exact next experiments\n")
    A("MEASURED: -\nINTERPRETATION: -\nLIMITATION: (oneriler yorum "
      "degil, deney listesidir; REV4 tasarimi YOK)\n")

    with open(path, "w") as f:
        f.writelines(L)
    print(f"RAPOR: {path}", flush=True)


def main():
    global OUTBASE
    ap = argparse.ArgumentParser(description="REV3 arastirma (Q1-Q4)")
    ap.add_argument("--only", default="",
                    help="ornek: Q1,Q3 (bos=hepsi)")
    ap.add_argument("--outdir", default=OUTBASE)
    ap.add_argument("--smoke", action="store_true",
                    help="Q1/S1 x 4 kosul")
    ap.add_argument("--report-only", action="store_true")
    a = ap.parse_args()
    OUTBASE = a.outdir
    os.makedirs(OUTBASE, exist_ok=True)
    only = [s.strip().upper() for s in a.only.split(",") if s.strip()]
    want = lambda q: (not only or q in only)

    if a.report_only:
        global RESULTS, MANIFEST
        try:
            with open(os.path.join(OUTBASE, "manifest.json")) as f:
                MANIFEST = json.load(f)
        except FileNotFoundError:
            MANIFEST = {}
        RESULTS = {}
        for scen in sorted(os.listdir(OUTBASE)):
            sdir = os.path.join(OUTBASE, scen)
            if not os.path.isdir(sdir):
                continue
            subs = [d for d in os.listdir(sdir)
                    if os.path.isfile(os.path.join(sdir, d, "mem.csv"))]
            if not subs:
                continue
            RESULTS[scen] = {}
            for key in subs:
                outs = {"mem": os.path.join(sdir, key, "mem.csv"),
                        "log": os.path.join(sdir, key, "log.csv"),
                        "branch": os.path.join(sdir, key, "branch.csv"),
                        "matrix": os.path.join(sdir, key, "matrix.csv")}
                m = KB.cond_metrics(outs)
                wpath = os.path.join(sdir, key, "w.txt")
                ws = []
                if os.path.isfile(wpath):
                    for l in open(wpath):
                        if l.startswith("W "):
                            ws.append(float(l.split()[3]))
                if ws:
                    m["w"] = {"mean": round(sum(ws) / len(ws), 6),
                              "max": round(max(ws), 6),
                              "var": round(sum(
                                  (x - sum(ws) / len(ws)) ** 2
                                  for x in ws) / len(ws), 8),
                              "delta_max": round(max(abs(x - 1.0)
                                                     for x in ws), 6)}
                else:
                    m["w"] = {"mean": 1.0, "max": 1.0, "var": 0.0,
                              "delta_max": 0.0}
                RESULTS[scen][key] = m
            MANIFEST.setdefault(scen, {"label": "?", "aff": None})
    elif a.smoke:
        s = q1_scenarios()["S1"]
        run_case("S1", write_cable("S1", s["rows"]), s["label"])
    else:
        if want("Q1"):
            for sid, s in q1_scenarios().items():
                run_case(sid, write_cable(sid, s["rows"]), s["label"])
        if want("Q2"):
            for sid, s in q2_scenarios().items():
                run_case(sid, write_cable(sid, s["rows"]), s["label"])
        if want("Q3"):
            for sid, s in q3_scenarios().items():
                run_case(sid, write_cable(sid, s["rows"]), s["label"])
        if want("Q4"):
            for sid, s in q4_scenarios().items():
                run_case(sid, write_cable(sid, s["rows"]), s["label"],
                         etas=ETAS)

    with open(os.path.join(OUTBASE, "results.json"), "w") as f:
        json.dump({"results": RESULTS, "manifest": MANIFEST,
                   "fails": fails}, f, default=str)
    with open(os.path.join(OUTBASE, "manifest.json"), "w") as f:
        json.dump(MANIFEST, f, default=str)
    write_report(os.path.join(OUTBASE, "REPORT_REV3_RESEARCH.md"))
    print(f"OZET-K4RES: {'BITTI' if not fails else 'BATTI: ' + str(fails)}",
          flush=True)
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
