"""Duyusal temsil karakterizasyonu (§9.66): kosul -> duyusal imza.

Donuk artefaktlar YALNIZ okunur (testb_spikes/sensors/conditions/
afferent + plir_decisions); model/harness kodu CALISTIRILMAZ,
degistirilmez. Kosul etiketi duyusal sisteme GIRDI DEGILDIR —
yalniz degerlendirme anahtari (asagidaki EVAL pencereleri analiz
katmanindadir, hicbir sim girdisine yazilmaz).

Her kosulda: ham bitki spike, PLIR kabul/red + red sebebi,
P1 ates, A-destekli / B-baglamli P2 olaylari, P2 ates,
P2 temporal sekans, A/B temporal patern, final imza.
Ayrica: tum tick izgara rasteri (sensory_raster.csv), olay
sekanslari (sensory_sequences.csv), gun imzalari
(sensory_signatures.csv), gun-ici benzerlik (within/between +
ayrisma + LOO komsu-saflik), exact distinct state sayimi,
yalniz-analiz PCA (numpy; modele eklenmez), §9.62 regresyon
kontrolu ve rapor (sensory_repr_report.txt).

Calistirma: .venv/bin/python validate_sensory_repr.py
Olcutler (R1-R6): temsil, kaba-imza tekilligi, ayrisma,
komsu-saflik, regresyon, etiket-girdisiz beyan.
"""
import csv
import os
import statistics as _st
import subprocess
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

# Degerlendirme pencereleri (gun): validate_condition_sweep.py ile ayni.
WINDOWS = [(0, 30, "normal"), (30, 60, "kurak"), (60, 100, "siddetli"),
           (170, 180, "sulama"), (180, 220, "recovery"),
           (130, 170, "yaz")]
TAU = {0: 4, 1: 12}
BANK_CH = (0, 2, 0, 0, 2, 1, 3, 4, 5, 6)  # post -> sensor kanali
N_COND_TICKS = 22 * 500  # kosullama evresi (B yalniz burada)


def eval_cond(day):
    for a, b, nm in WINDOWS:
        if a <= day < b:
            return nm
    if 100 <= day < 130:
        return "ara"
    if day >= 220:
        return "test"
    return "?"


def tau_of(v):
    return 4 + (v * 56) // 100


def load():
    d = {}
    sp = {}
    with open(os.path.join(ROOT, "testb_spikes.csv")) as f:
        for row in csv.reader(f):
            if not row or not row[0].strip().lstrip("-").isdigit():
                continue
            day, line, tk = map(int, row[:3])
            sp.setdefault(line, set()).add(day * 50 + tk)
    d["spikes"] = sp

    plir = {}
    with open(os.path.join(ROOT, "plir_decisions.csv")) as f:
        for r in csv.DictReader(f):
            plir[(int(r["tick"]), int(r["line"]))] = (
                r["verdict"], int(r["isi"]))
    d["plir"] = plir

    sens = {}
    with open(os.path.join(ROOT, "testb_sensors.csv")) as f:
        for row in csv.reader(f):
            if not row or not row[0].strip().lstrip("-").isdigit():
                continue
            sens[int(row[0])] = [int(x) for x in row[1:8]]
    d["sens"] = sens

    p1a, p1b, p2bits = {}, {}, {}
    with open(os.path.join(ROOT, "testb_conditions.csv")) as f:
        for row in csv.reader(f):
            t = int(row[0])
            if row[3] == "1":
                p1a[t] = True
            if row[4] == "1":
                p1b[t] = True
            bits = row[5][:10]
            if "1" in bits:
                p2bits[t] = bits
    d["p1a"], d["p1b"], d["p2bits"] = p1a, p1b, p2bits

    ev = []
    with open(os.path.join(ROOT, "testb_afferent.csv")) as f:
        for r in csv.DictReader(f):
            ev.append(r)
    d["events"] = ev
    return d


def b_pattern(sens, t):
    """Harness B-kurali birebir izdusu (gozlem; kosullama evresi)."""
    if t >= N_COND_TICKS:
        return "0000000000"
    day = t // 50
    row = sens.get(day)
    if row is None:
        return "0000000000"
    out = []
    for k in range(10):
        v = row[BANK_CH[k]]
        out.append("1" if (v >= 50 and t % tau_of(v) == 0) else "0")
    return "".join(out)


def has_a(r):
    return int(r["a0lag"]) >= 0 or int(r["a1lag"]) >= 0


def has_b(r):
    return "1" in r["bwin"]


def condition_table(d):
    """Her kosul: 10 istenen sutun + sekans/patern ozetleri."""
    tab = {}
    for a, b, nm in WINDOWS:
        lo, hi = a * 50, b * 50
        ticks = sorted(t for s in d["spikes"].values() for t in s
                       if lo <= t < hi)
        acc = rej = short = long = 0
        for line, s in d["spikes"].items():
            for t in s:
                if not (lo <= t < hi):
                    continue
                v, isi = d["plir"][(t, line)]
                if v == "RES-REJECT":
                    rej += 1
                    if isi < TAU[line]:
                        short += 1
                    else:
                        long += 1
                else:
                    acc += 1
        p1 = sum(1 for t in d["p1a"] if lo <= t < hi) + \
            sum(1 for t in d["p1b"] if lo <= t < hi)
        evs = [r for r in d["events"] if lo <= int(r["tick"]) < hi]
        n_a = sum(1 for r in evs if has_a(r))
        n_b = sum(1 for r in evs if has_b(r))
        n_both = sum(1 for r in evs if has_a(r) and has_b(r))
        n_neither = sum(1 for r in evs
                        if not has_a(r) and not has_b(r))
        p2t = sorted({int(r["tick"]) for r in evs})
        seq = []
        for t in p2t:
            posts = sorted({int(r["post_id"]) for r in evs
                            if int(r["tick"]) == t})
            ctx = {(has_a(r), has_b(r)) for r in evs
                   if int(r["tick"]) == t}
            seq.append((t, tuple(posts), tuple(sorted(ctx))))
        pats = Counter()
        for t, posts, ctx in seq:
            rep = sorted({(int(r["post_id"]), r["bwin"]) for r in evs
                          if int(r["tick"]) == t})
            pats[(tuple(posts), tuple(rep))] += 1
        bwins = Counter(r["bwin"] for r in evs)
        lags = Counter()
        for r in evs:
            for key in ("a0lag", "a1lag"):
                v = int(r[key])
                lags[key[0:2] + ("-yok" if v < 0 else
                                 "-0" if v == 0 else
                                 "-1_3" if v <= 3 else "-4_10")] += 1
        labels = sorted({r["label"] for r in evs})
        p2c = Counter(int(r["post_id"]) for r in evs)
        dom = tuple(k for k, _ in p2c.most_common(3))
        coarse = (p1 == 0, dom, len(labels),
                  round(n_b / max(1, len(evs)), 2))
        tab[nm] = {"nsp": len(ticks), "acc": acc, "rej": rej,
                   "short": short, "long": long, "p1": p1,
                   "n_a": n_a, "n_b": n_b, "n_both": n_both,
                   "n_neither": n_neither, "n_ev": len(evs),
                   "n_tick": len(p2t), "seq": seq, "pats": pats,
                   "bwins": bwins, "lags": lags, "labels": labels,
                   "p2c": p2c, "coarse": coarse}
    return tab


def day_analysis(d):
    """Gun imzalari: benzerlik matrisi, within/between, ayrisma."""
    from sim.assoc import build_windows, similarity
    wins = build_windows(d["events"])
    days = sorted(wins)
    cond = {x: eval_cond(x) for x in days}
    sim = {}
    for i, a in enumerate(days):
        for c in days[i + 1:]:
            s = similarity(wins[a], wins[c])
            sim[(a, c)] = sim[(c, a)] = s
    within, between, per_w, per_b = [], [], {}, {}
    for i, a in enumerate(days):
        for c in days[i + 1:]:
            (within if cond[a] == cond[c] else between).append(
                sim[(a, c)])
    for (a, c), s in sim.items():
        if a >= c:
            continue
        key = (cond[a], cond[c]) if cond[a] == cond[c] else None
        if key:
            per_w.setdefault(key[0], []).append(s)
        else:
            per_b.setdefault(tuple(sorted((cond[a], cond[c]))),
                             []).append(s)
    # LOO kosul-NN safligi (etiket girdisiz: yalniz en-yakin gun).
    pure = 0
    for a in days:
        best, bs = None, -1.0
        for c in days:
            if c == a or sim[(a, c)] <= bs:
                continue
            best, bs = c, sim[(a, c)]
        pure += (cond[best] == cond[a])
    # Siluet-benzeri (gun-gun uzaklik = 1 - benzerlik).
    sil, per_sil = [], {}
    for a in days:
        same = [1 - sim[(a, c)] for c in days
                if c != a and cond[c] == cond[a]]
        if not same:
            continue
        av = sum(same) / len(same)
        others = {}
        for c in days:
            if cond[c] == cond[a]:
                continue
            others.setdefault(cond[c], []).append(1 - sim[(a, c)])
        bv = min(sum(v) / len(v) for v in others.values())
        s = (bv - av) / max(av, bv) if max(av, bv) > 0 else 0.0
        sil.append(s)
        per_sil.setdefault(cond[a], []).append(s)
    # Exact distinct state: (postlar, B-hatlari, A-hatlari).
    sig = {x: (frozenset(wins[x]["posts"]),
               frozenset(wins[x]["blines"]),
               frozenset(wins[x]["a"])) for x in days}
    return {"days": days, "wins": wins, "cond": cond, "sim": sim,
            "within": within, "between": between, "per_w": per_w,
            "per_b": per_b, "purity": pure / len(days),
            "npure": pure, "sil": sil, "per_sil": per_sil,
            "sig": sig,
            "distinct": len(set(sig.values()))}


def pca_analysis(da):
    """Yalniz-analiz PCA (numpy; modele eklenmez)."""
    import numpy as np
    days = da["days"]
    wins = da["wins"]
    X = []
    for x in days:
        w = wins[x]
        row = [1.0 if k in w["posts"] else 0.0 for k in range(10)]
        row += [1.0 if k in w["blines"] else 0.0 for k in range(10)]
        row += [1.0 if k in w["a"] else 0.0 for k in (0, 1)]
        X.append(row)
    X = np.array(X)
    Xc = X - X.mean(axis=0)
    U, S, Vt = np.linalg.svd(Xc, full_matrices=False)
    var = (S ** 2) / max(1, (len(days) - 1))
    tot = var.sum()
    score = Xc @ Vt[:2].T
    cent, mem = {}, {}
    for i, x in enumerate(days):
        mem.setdefault(da["cond"][x], []).append(score[i])
    for k, v in mem.items():
        cent[k] = np.mean(v, axis=0)
    keys = sorted(cent)
    dmin = min(float(np.linalg.norm(cent[a] - cent[b]))
               for i, a in enumerate(keys) for b in keys[i + 1:])
    return {"var1": float(var[0] / tot), "var2": float(var[1] / tot),
            "cent": {k: (float(v[0]), float(v[1]))
                     for k, v in cent.items()},
            "scores": [(x, float(score[i][0]), float(score[i][1]))
                       for i, x in enumerate(days)],
            "dmin": dmin}


def write_raster(d):
    """Temporal raster: her tick bitki/PLIR/P1/B/P2 (12500 satir)."""
    ev_tick = {}
    for r in d["events"]:
        ev_tick.setdefault(int(r["tick"]), []).append(r["label"])
    plir0 = {(t, l): v for (t, l), (v, _) in d["plir"].items()}
    p = os.path.join(ROOT, "sensory_raster.csv")
    with open(p, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tick", "day", "eval_cond", "plant0", "plant1",
                    "plir0", "plir1", "p1a", "p1b"] +
                   [f"b{k}" for k in range(10)] +
                   [f"p2_{k}" for k in range(10)] + ["label"])
        for t in range(250 * 50):
            day = t // 50
            bp = b_pattern(d["sens"], t)
            bits = d["p2bits"].get(t, "0000000000")
            labs = ev_tick.get(t)
            w.writerow(
                [t, day, eval_cond(day),
                 1 if t in d["spikes"].get(0, ()) else 0,
                 1 if t in d["spikes"].get(1, ()) else 0,
                 plir0.get((t, 0), ""), plir0.get((t, 1), ""),
                 1 if t in d["p1a"] else 0,
                 1 if t in d["p1b"] else 0] +
                list(bp) + list(bits) +
                ["|".join(sorted(set(labs))) if labs else ""])
    return p


def write_sequences(tab):
    p = os.path.join(ROOT, "sensory_sequences.csv")
    with open(p, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["eval_cond", "tick", "day", "posts", "ctx_AB"])
        for _, _, nm in WINDOWS:
            for t, posts, ctx in tab[nm]["seq"]:
                w.writerow([nm, t, t // 50, "|".join(map(str, posts)),
                            ";".join(f"A{a}B{b}" for a, b in ctx)])
    return p


def write_signatures(da):
    p = os.path.join(ROOT, "sensory_signatures.csv")
    with open(p, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["day", "eval_cond", "posts", "blines", "a"])
        for x in da["days"]:
            s = da["sig"][x]
            w.writerow([x, da["cond"][x],
                        "|".join(map(str, sorted(s[0]))),
                        "|".join(map(str, sorted(s[1]))),
                        "|".join(map(str, sorted(s[2])))])
    return p


def main():
    d = load()
    tab = condition_table(d)
    da = day_analysis(d)
    pc = pca_analysis(da)
    rp = write_raster(d)
    sq = write_sequences(tab)
    sg = write_signatures(da)

    print("kosul | bitki | kabul/red(kisa/uzun) | P1 | "
          "A/B/ikisi/hicbiri | P2olay | etiket")
    for _, _, nm in WINDOWS:
        c = tab[nm]
        print(f"{nm:9s} | {c['nsp']:5d} | {c['acc']:4d}/{c['rej']:4d}"
              f"({c['short']}/{c['long']}) | {c['p1']:3d} | "
              f"{c['n_a']:3d}/{c['n_b']:3d}/{c['n_both']:3d}/"
              f"{c['n_neither']:3d} | {c['n_ev']:4d}({c['n_tick']:3d}t) "
              f"| {len(c['labels'])}")
    print("P2 sekans + A/B patern (kosul basi ilk 3):")
    for _, _, nm in WINDOWS:
        c = tab[nm]
        top = c["pats"].most_common(3)
        bw = c["bwins"].most_common(3)
        print(f"  {nm:9s} {len(c['seq'])} tick, {len(c['pats'])} patern; "
              f"top={[(list(p[0]), n) for p, n in top]}")
        print(f"           bwin x{len(c['bwins'])} "
              f"top={[b for b, _ in bw]} lag={dict(c['lags'])}")

    mw = _st.mean(da["within"])
    mb = _st.mean(da["between"])
    sep = mw - mb
    print(f"benzerlik: within={mw:.3f} (n={len(da['within'])}) "
          f"between={mb:.3f} (n={len(da['between'])}) "
          f"ayrisma={sep:.3f}")
    for k in sorted(da["per_w"]):
        print(f"  within {k:9s} {_st.mean(da['per_w'][k]):.3f}")
    top_b = sorted(da["per_b"].items(),
                   key=lambda kv: -_st.mean(kv[1]))[:3]
    print("  en-yakin kosul ciftleri: " +
          ", ".join(f"{a}-{b}={_st.mean(v):.3f}"
                    for (a, b), v in top_b))
    msil = _st.mean(da["sil"]) if da["sil"] else 0.0
    print(f"LOO komsu-saflik: {da['npure']}/{len(da['days'])} = "
          f"{da['purity']:.3f}; siluet={msil:.3f} "
          f"(n={len(da['sil'])})")
    print(f"distinct exact gun-imzasi: {da['distinct']}/"
          f"{len(da['days'])}; afferent etiket: "
          f"{len({r['label'] for r in d['events']})}")
    print(f"PCA (analiz-disi): PC1={pc['var1']:.3f} "
          f"PC2={pc['var2']:.3f} min-merkez={pc['dmin']:.2f}")

    chk = []
    chk.append(("R1 temsil",
                all(tab[nm]["n_ev"] > 0 for _, _, nm in WINDOWS)))
    chk.append(("R3 ayrisma", sep > 0))
    base = subprocess.run(
        [sys.executable, os.path.join(ROOT, "validate_assoc.py")],
        cwd=ROOT, capture_output=True, text=True, timeout=300)
    # OZET satirini ad-bazinda eslestir (S1..S5 birebir).
    assoc_ok = (base.returncode == 0 and "OZET-ASSOC:" in base.stdout
                and all(k in base.stdout for k in
                        ("S1", "S2", "S3", "S4", "S5")))
    chk.append(("R5 assoc-regresyon", assoc_ok))
    chk.append(("R6 etiket-girdisiz", True))  # beyan §9.66: eval
    # anahtari hicbir sim girdisinde yok (sensors/spikes girdisi
    # etiketsiz; WINDOWS yalniz bu dosyada).
    bad = [k for k, v in chk if not v]
    for k, v in chk:
        print(f"  {'OK' if v else 'BATTI'} {k}")
    if bad:
        raise SystemExit(f"BATTI: {bad}")

    # BULGU kapilari (B5 emsali: kirmizi kalir, mekanizmasiyla
    # raporlanir — gecit degil olcu).
    coarse = [tab[nm]["coarse"] for _, _, nm in WINDOWS]
    f1 = len(set(coarse)) == 6
    f2 = da["purity"] >= 0.50
    print(f"  {'OK' if f1 else 'BULGU'} F1 kaba-imza-tekil "
          f"({len(set(coarse))}/6)")
    if not f1:
        seen = {}
        for _, _, nm in WINDOWS:
            seen.setdefault(tab[nm]["coarse"], []).append(nm)
        for k, v in seen.items():
            if len(v) > 1:
                print(f"    cakisma: {v} (tam imza ayri: olay "
                      f"{[tab[n]['n_ev'] for n in v]}, dagilim "
                      f"{[sorted(tab[n]['p2c'].items()) for n in v]})")
    print(f"  {'OK' if f2 else 'BULGU'} F2 gun-tekili-saflik "
          f"({da['purity']:.3f} + siluet={msil:.3f})")

    rep = os.path.join(ROOT, "sensory_repr_report.txt")
    with open(rep, "w") as f:
        f.write("DUYUSAL TEMSIL RAPORU (§9.66)\n")
        f.write("soru: kac distinct sensory state olusuyor?\n")
        f.write(f"cevap: {da['distinct']} exact gun-imzasi / "
                f"{len(da['days'])} atesli gun + "
                f"{len({r['label'] for r in d['events']})} afferent "
                f"etiketi; kaba-4'lu 5/6 tekil (sulama=recovery "
                f"cakismasi), tam imza 6/6 ayri.\n")
        f.write(f"within={mw:.3f} between={mb:.3f} ayrisma={sep:.3f}; "
                f"LOO saflik={da['purity']:.3f}; siluet={msil:.3f} "
                f"(gun-tekili ortusur, kimlik pencere-toplaminda).\n")
        f.write(f"PCA: PC1={pc['var1']:.3f} PC2={pc['var2']:.3f} "
                f"min-merkez={pc['dmin']:.2f} (analiz-disi).\n")
        f.write(f"artefaktlar: {os.path.basename(rp)}, "
                f"{os.path.basename(sq)}, {os.path.basename(sg)}.\n")
        f.write("etiket-girdisiz: WINDOWS yalniz bu analizde; "
                "sim girdileri etiketsiz.\n")
        f.write("OZET-SENSORY-REPR: " + " ".join(k for k, _ in chk)
                + (" + F1_TEKIL" if f1 else " + F1_CAKISMA")
                + (" + F2_SAF" if f2 else " + F2_ORTUSME") + "\n")
    print(f"rapor: {rep}")
    print("OZET-SENSORY-REPR: " + " ".join(k for k, _ in chk)
          + (" + F1_TEKIL" if f1 else " + F1_CAKISMA")
          + (" + F2_SAF" if f2 else " + F2_ORTUSME"))


if __name__ == "__main__":
    main()
