"""REV3 takip arastirmasi — W1/W2/W3 (CHARACTERIZATION, validated YOK).

KURALLAR (birinci batarya ile ayni + ek):
- Mimari degisiklik YOK; tuning YOK; sabitler AYNI. Tek binary degisikligi:
  --k4idcsv salt-okunur kimlik telemetrisi (duruma etkisi yok; J kapisi
  kayitli hash'le yeniden kanitli).
- Label formation'a GIRMEZ. Deterministik + cift-SHA. OLCU/YORUM/SINIR
  ayri. "memory" yasagi surer. REV4 YOK.

W1 ZAYIF-PROB HISTORY: guclu prob tavan yapmisti (23-27/29). Ayni H1/H2/H3
  protokol, zayif ama taban-ustu prob (E_ApB tipi: base'de ~3 satir).
  Tarih X/Y birinci bataryadakiyle AYNI (karsilastirilabilirlik).
W2 WITHIN-r MEKANIZMASI: C_AB_off{0,5,11} + idcsv agree serileri. Soru:
  ayni-akim ciftlerinin r'si capraz offset ile NEDEN degisiyor? Adaylar:
  (a) K4-drive geri-beslemesi (kimlik kayar), (b) ates/reset kimlik
  silmesi. Olcut: agree dagilimi (aktif/sessiz-uzlasma), ates sayisi,
  drive duzeyi, coin kapsama.
W3 RETRIEVAL REDESIGN: once kosul-ici (ayni pattern x jitter) yakinlik,
  sonra kosullar-arasi ayrim. LOO 1-NN (degerlendirme, egitim DEGIL) +
  uzaklik dagilimlari. Bitki tohumu varyanti (A_base s42/43/44) ek.

Kullanim: .venv/bin/python k4_research2.py [--only W1,W3] [--outdir D]
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
import k4_battery as KB  # noqa: E402
import k4_research as KR  # noqa: E402

OUTBASE = os.environ.get("K4RES2_BASE", "/tmp/k4res2")
fails = []
RESULTS = {}
MANIFEST = {}


def check(name, cond, extra=""):
    print(f"  {'OK' if cond else 'BATTI'} {name} {extra}", flush=True)
    if not cond:
        fails.append(name)


def write_cable(scen, rows):
    p = os.path.join(OUTBASE, scen, "cable.csv")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    KB.write_aff(p, rows)
    return p


def run_case2(scen, aff, label, etas=None, idcsv=False):
    """KR.run_case esdegeri + idcsv destegi (sonuclar bu dosyada)."""
    MANIFEST[scen] = {"label": label, "aff": aff}
    out = {}
    for cname, k4, etafix in KR.CONDF:
        for eta in (etas if etas is not None else ["0", "0.30"]):
            if etafix is not None and eta != etafix:
                continue
            key = f"{cname}@{eta}"
            d = os.path.join(OUTBASE, scen, key)
            outs, w = KR.run_lobe(aff, d, k4, eta, idcsv=idcsv)
            m = KB.cond_metrics(outs)
            ws = list(w.values())
            m["w"] = {"mean": round(sum(ws) / len(ws), 6),
                      "max": round(max(ws), 6),
                      "delta_max": round(max(abs(x - 1.0) for x in ws), 6)}
            out[key] = m
            print(f"  [{scen}/{key}] rows={m['basic']['rows']} "
                  f"Nsig={m['basic']['N_sig']}", flush=True)
    RESULTS[scen] = out
    return out


def probe_units(scen, key, t0, t1):
    return KR.probe_window_units(scen, key, t0, t1)


# ---------------- W1: zayif-prob history -----------------------------------
# Prob: E_ApB deseni (slot {0,1,2,3} x2 gap30; base'de ~3 satir: taban-ustu,
# tavan-alti). Tarih X/Y: Q3 ile AYNI bloklar (karsilastirilabilirlik).
W1_PROBE_REL = KB.burst(0, [0, 1, 2, 3], 2, 30)  # gorece tickler
W1_HIST = {"X": KB.stream([0, 5], 100, 700, 40),
           "Y": KB.burst(100, [0, 1, 2, 3], 6, 30)}


def w1_scenarios():
    S = {}
    S["W1_H1"] = ([(100 + t, p) for t, p in W1_PROBE_REL],
                  "W1:H1 clean+zayif-prob")
    for gap in (0, 5, 10, 20, 40):
        ev = list(W1_HIST["X"]) + [(700 + gap + t, p)
                                   for t, p in W1_PROBE_REL]
        S[f"W1_H2_gap{gap}"] = (ev, f"W1:H2 tarih-X gap={gap}+zayif-prob")
    ev = list(W1_HIST["Y"]) + [(720 + t, p) for t, p in W1_PROBE_REL]
    S["W1_H3"] = (ev, "W1:H3 tarih-Y gap=20+zayif-prob")
    return {k: {"rows": KB.aff_rows(v[0]), "label": v[1]} for k, v in S.items()}


def w1_probe_start(scen):
    if scen == "W1_H1":
        return 100
    if scen.startswith("W1_H2_gap"):
        return 700 + int(scen.rsplit("gap", 1)[1])
    return 720  # W1_H3


# ---------------- W2: within-r mekanizmasi ---------------------------------
def w2_agree_stats(scen, key):
    """idcsv agree serileri: olay-penceresi ici agree dagilimi.

    Donus: {cift-turu: {agree: sayi}} + ates sayisi + ortalama drive.
    Cift turu: ZCAL-olcusuz, kablo-tanimli akimlara gore: bu kosularda
    A-akim slot {0,1}, B-akim slot {2,3} (C_AB); dal->akim bagi icin
    branch.csv act zamanlamasi kullanilir (sonradan-analiz)."""
    d = os.path.join(OUTBASE, scen, key)
    idrows = KB.read_csv_rows(os.path.join(d, "ids.csv"))
    snap = defaultdict(dict)
    for r in idrows:
        snap[int(r["tick"])][(int(r["birim"]), int(r["dal"]))] = (
            int(r["a0"]), int(r["a1"]), int(r["a2"]))
    mx = KB.read_csv_rows(os.path.join(d, "matrix.csv"))
    uniq = {}
    for r in mx:
        a, b = int(r["b1"]), int(r["b2"])
        if a != b:
            uniq[(min(a, b), max(a, b))] = float(r["r"])
    top = sorted(uniq, key=lambda k: -uniq[k])[:40]
    bid = lambda u, dd: u * 2 + dd
    # akim bagi: dalin act tick'leri hangi izgara ile cakisiyor?
    grid0 = list(range(0, 600, 40))
    grid1 = list(range(11 if "off11" in scen else
                       (5 if "off5" in scen else 0), 600, 40))
    br = KB.read_csv_rows(os.path.join(d, "branch.csv"))
    actt = defaultdict(list)
    for r in br:
        actt[(int(r["birim"]), int(r["dal"]))].append(int(r["tick"]))

    def near(ts, grid):
        return sum(1 for t in ts if any(0 <= t - e <= 15 for e in grid))

    link = {}
    for b, ts in actt.items():
        n0, n1 = near(ts, grid0), near(ts, grid1)
        link[b] = 0 if n0 >= n1 else 1
    agree_hist = defaultdict(lambda: defaultdict(int))
    for (a, b) in top:
        ba = (a // 2, a % 2)
        bb = (b // 2, b % 2)
        la, lb = link.get(ba, -1), link.get(bb, -1)
        kind = ("within" if la == lb and la >= 0 else
                "cross" if la >= 0 and lb >= 0 else "unlinked")
        for t, branches in snap.items():
            if ba in branches and bb in branches:
                pa, pb = branches[ba], branches[bb]
                ag = sum(1 for x, y in zip(pa, pb) if x == y)
                # yalniz en az bir taraf aktifse say (sessiz-deniz disinda)
                if max(pa + pb) > 0:
                    agree_hist[kind][ag] += 1
    mem = os.path.join(d, "mem.csv")
    nfire = sum(1 for _ in open(mem)) - 1
    drv = [float(r["drive"]) for r in br]
    return {"agree": {k: dict(v) for k, v in agree_hist.items()},
            "nfires": nfire,
            "mean_drive": round(sum(drv) / len(drv), 6) if drv else 0.0,
            "n_top": len(top)}


# ---------------- W3: retrieval redesign -----------------------------------
def w3_items(cond_key="C2@0", prefix="Q2_", src=None):
    """Madde listesi: (etiket, relvec-pairs, act, units). Etiket post-hoc."""
    items = []
    if src is None:
        src = os.environ.get("K4RES_Q2BASE", "/tmp/k4res")
    for sid in sorted(os.listdir(src)):
        if not sid.startswith(prefix):
            continue
        d = os.path.join(src, sid, cond_key)
        if not os.path.isfile(os.path.join(d, "mem.csv")):
            continue
        # etiket: pattern adi (Q2_P1_fx -> P1; jitter varyanti ayni etiket;
        # W3_seed* -> hepsi "seed" (tohumlar arasi mesafe = within)).
        tag = "seed" if sid.startswith("W3_seed") else (
            sid.split("_")[1] if "_" in sid else sid)
        mx = KB.read_csv_rows(os.path.join(d, "matrix.csv"))
        uniq = {}
        for r in mx:
            a, b = int(r["b1"]), int(r["b2"])
            if a != b:
                uniq[(min(a, b), max(a, b))] = float(r["r"])
        br = KB.read_csv_rows(os.path.join(d, "branch.csv"))
        act = [0.0] * 58
        for r in br:
            act[int(r["birim"]) * 2 + int(r["dal"])] = max(
                act[int(r["birim"]) * 2 + int(r["dal"])], float(r["act"]))
        units = {int(r["unit"]) for r in
                 KB.read_csv_rows(os.path.join(d, "mem.csv"))}
        items.append({"id": f"{sid}/{cond_key}", "tag": tag,
                      "pairs": uniq, "act": act, "units": units})
    return items


def w3_nn(items, dist_fn, key):
    """LOO 1-NN dogrulugu (degerlendirme; egitim yok)."""
    if len(items) < 3:
        return -1.0, 0
    ok, n = 0, 0
    for i, it in enumerate(items):
        best, bd = None, None
        for j, ot in enumerate(items):
            if i == j:
                continue
            dd = dist_fn(it, ot, key)
            if bd is None or dd < bd:
                best, bd = ot, dd
        n += 1
        ok += 1 if best["tag"] == it["tag"] else 0
    return round(ok / n, 4), n


def w3_dists(items, dist_fn, key):
    """within (ayni etiket) vs between dagilimi."""
    import statistics as _st
    w, b = [], []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            d = dist_fn(items[i], items[j], key)
            (w if items[i]["tag"] == items[j]["tag"] else b).append(d)
    return (round(_st.mean(w), 4) if w else -1.0,
            round(_st.mean(b), 4) if b else -1.0, len(w), len(b))


def _d_fro(a, b, _k):
    return KR.dist(a["pairs"], b["pairs"], "fro")


def _d_jac(a, b, _k):
    return KR.dist(a["units"], b["units"], "jaccard")


def _d_cos(a, b, _k):
    return KR.dist(a["act"], b["act"], "cosine")


def w3_plant_seeds():
    """A_base x tohum {42,43,44} (bitki hatti; kosul-ici tohum saglamligi)."""
    for seed in (42, 43, 44):
        sid = f"W3_seed{seed}"
        d = KB.front(os.path.join(OUTBASE, sid, "front"), seed=seed,
                     days=KB.DAYS)
        aff = KB.plant_aff(d, cond=KB.DAYS // 10 - 3)
        run_case2(sid, aff, f"W3:bitki tohumu s={seed}")


# ---------------- rapor ------------------------------------------------------
def write_report2(path):
    L = []
    A = L.append
    A("# REPORT_REV3_RESEARCH2 — W1/W2/W3 (validated YOK)\n\n")
    A("Kurallar birinci batarya ile ayni. Tek binary farki: --k4idcsv "
      "salt-okunur telemetri (J kayitli hash'le yeniden kanitli). "
      "OLCU/YORUM/SINIR ayri.\n")
    A(f"\nfails={fails if fails else 'yok'}\n")

    A("\n## W1 zayif-prob history\n")
    A("MEASURED:\n")
    for sid in sorted(RESULTS):
        if sid.startswith(("W1_H1", "W1_H2", "W1_H3")):
            t0 = {"W1_H1": 100}.get(sid, 700 + int(
                sid.rsplit("gap", 1)[1]) if "gap" in sid else 720)
            for key in sorted(RESULTS[sid]):
                u = sorted(probe_units(sid, key, t0, t0 + 90))
                m = RESULTS[sid][key]
                A(f"- {sid}/{key}: prob-units={u if u else '-'} "
                  f"E={m['k4']['k4_energy']}\n")
    A("INTERPRETATION: (tek-cumle)\n")
    A("LIMITATION: H1 prob konumu (t=100) H2/H3'ten farkli (mutlak tick "
      "dinamige girmez; cift-SHA determinizmi gecerli). Tavan/taban "
      "kontrolu satirlarda gorunur.\n")

    A("\n## W2 within-r-offset mekanizmasi\n")
    A("MEASURED:\n")
    for sid in sorted(RESULTS):
        if sid.startswith("W2_"):
            for key in sorted(RESULTS[sid]):
                st = w2_agree_stats(sid, key)
                A(f"- {sid}/{key}: agree={st['agree']} "
                  f"nfires={st['nfires']} meandrive={st['mean_drive']}\n")
    A("INTERPRETATION: (tek-cumle)\n")
    A("LIMITATION: r(t) ara-degeri telemetride yok; buyume act(t) ve "
      "final-r uzerinden cikarilir. Dal-akim bagi act-zamanlamasindandir "
      "(sonradan-analiz).\n")

    A("\n## W3 retrieval redesign\n")
    A("MEASURED:\n")
    for cond_key, cname in (("C2@0", "K4"), ("C0@0", "noK4")):
        items = w3_items(cond_key)
        for dk, fn in (("fro", _d_fro), ("jac", _d_jac), ("cos", _d_cos)):
            acc, n = w3_nn(items, fn, dk)
            w, b, nw, nb = w3_dists(items, fn, dk)
            A(f"- {cname}/{dk}: NN-acc={acc}(n={n}) within={w}(n={nw}) "
              f"between={b}(n={nb})\n")
    A("- bitki tohumu varyanti (W3_seed42/43/44, C2@0):\n")
    seed_items = w3_items("C2@0", prefix="W3_seed", src=OUTBASE)
    for dk, fn in (("fro", _d_fro), ("jac", _d_jac)):
        w, b, nw, nb = w3_dists(seed_items, fn, dk)
        A(f"  - seed within={w}(n={nw}) between-seed={b}(n={nb})\n")
    A("INTERPRETATION: (tek-cumle)\n")
    A("LIMITATION: 1-NN degerlendirmedir, egitim degil. Bitki varyanti "
      "yalniz 1 kosul x 3 tohumdur.\n")

    A("\n## Kontroller / ham / basarisiz / sinirlar\n")
    A("MEASURED: ayni tohum/girdi/sure/baslangic; K4 OFF baseline her "
      "grupta; ham CSV/JSON OUTBASE'de.\n")
    A("INTERPRETATION: -\nLIMITATION: kucuk-n maxJ yorumlanmadi.\n")
    A("\n## Olcu / yorum\n")
    A("MEASURED: sayilar CSV/stdout'tan dogrudan.\n")
    A("INTERPRETATION: tek-cumleler gozlem ozetidir.\n")
    A("\n## Kurulan / acik / sonraki\n")
    A("MEASURED: -\nINTERPRETATION: -\nLIMITATION: (asagida)\n")

    with open(path, "w") as f:
        f.writelines(L)
    print(f"RAPOR: {path}", flush=True)


def main():
    global OUTBASE
    ap = argparse.ArgumentParser(description="REV3 takip (W1-W3)")
    ap.add_argument("--only", default="")
    ap.add_argument("--outdir", default=OUTBASE)
    ap.add_argument("--smoke", action="store_true",
                    help="W1_H1 x 4 kosul")
    ap.add_argument("--report-only", action="store_true")
    a = ap.parse_args()
    OUTBASE = a.outdir
    KR.OUTBASE = a.outdir
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
                m["w"] = {"mean": 1.0, "max": 1.0, "delta_max": 0.0}
                if ws:
                    m["w"] = {"mean": round(sum(ws) / len(ws), 6),
                              "max": round(max(ws), 6),
                              "delta_max": round(max(abs(x - 1.0)
                                                     for x in ws), 6)}
                RESULTS[scen][key] = m
            MANIFEST.setdefault(scen, {"label": "?", "aff": None})
    elif a.smoke:
        s = w1_scenarios()["W1_H1"]
        run_case2("W1_H1", write_cable("W1_H1", s["rows"]), s["label"])
    else:
        if want("W1"):
            for sid, s in w1_scenarios().items():
                run_case2(sid, write_cable(sid, s["rows"]), s["label"])
        if want("W2"):
            for sid, off in (("W2_off0", 0), ("W2_off5", 5),
                             ("W2_off11", 11)):
                ev = KB.stream([0, 1], 0, 600, 40) + KB.stream(
                    [2, 3], off, 600, 40)
                run_case2(sid, write_cable(
                    sid, KB.aff_rows(ev)),
                    f"W2:C_AB off={off}+idcsv", idcsv=True)
        if want("W3"):
            w3_plant_seeds()

    with open(os.path.join(OUTBASE, "results.json"), "w") as f:
        json.dump({"results": RESULTS, "manifest": MANIFEST,
                   "fails": fails}, f, default=str)
    with open(os.path.join(OUTBASE, "manifest.json"), "w") as f:
        json.dump(MANIFEST, f, default=str)
    write_report2(os.path.join(OUTBASE, "REPORT_REV3_RESEARCH2.md"))
    print(f"OZET-K4RES2: {'BITTI' if not fails else 'BATTI: ' + str(fails)}",
          flush=True)
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
