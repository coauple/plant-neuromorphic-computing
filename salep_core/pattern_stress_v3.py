"""PATTERN LOBE v3 FULL-SYSTEM STRESS (SPEC: PATTERN_V3_STRESS_SPEC.md).

On-kayitli batarya: 12 grup, sabit tohum/senaryo, sabit metrik seti.
Sonuc ne cikarsa aynen raporlanir; yeni test icat EDILMEZ.

Metrik formulleri (mem.csv: tick,unit,...):
- N_sig: bos-olmayan gun imzalarinin distinct sayisi.
- tick-vektor: tick->frozenset(birim); N_pv distinct sayisi; repetition =
  1 - N_pv/n_aktif_tick.
- ISI: birim-bazli artisik ates tick farklari; global ort/std (+n).
- stabilite: gunler sirayla ikiye bolunur; imza-kumelerinin Jaccard'i.
- gun-hizali Jaccard(A,B): iki kosunun gun indisleri uzerinden; gunluk
  j: bos-bos=1, bos-dolu=0, else |kesisim|/|birlesim; ortalama yalniz
  >=1 tarafin dolu oldugu gunlerden.
- within: ayni case'in tohum-tekrarlari arasi gun-hizali Jaccard ort.
- retrieval-acc: grup pencereleri havuzlanir (cakisma yok: kosu-basina
  gun-ofseti), LOO nearest-sequence; etiket=senaryo. Skor RAPOR (kapi YOK).
- aile-uyumu (G11): sorgu penceresinin en-yakin ref penceresiyle ayni
  ailede olma orani.
- sensor-mesafe (G4/G12): final-10gun kanal-ortalamalarinin Oklid'i.

Kapilar: crash-yok, v3 cift-kosu sha, encoder 1:1, adapter bit-esit
(run_chain_v3 icinden). Bos-girdi = temiz-dur (kapi degil, rapor).
Kullanim: .venv/bin/python pattern_stress_v3.py [--only G1,G2,...]
"""
import argparse
import csv
import json
import math
import os
import statistics as st
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import run_chain_v3 as C  # noqa: E402
from validate_infer_pattern import infer, seq_sim  # noqa: E402

BASE = os.environ.get("PSTRESS_BASE", "/tmp/pstress")
PLANT = os.path.join(ROOT, "npu_sensory_plant")
WV = os.path.join(ROOT, "weather_v3")
K = 3
fails = []
results = {}
registry = {}


def check(name, cond, extra=""):
    print(f"  {'OK' if cond else 'BATTI'} {name} {extra}", flush=True)
    if not cond:
        fails.append(name)


def tickvec(mem):
    tv = {}
    with open(mem) as f:
        for r in csv.DictReader(f):
            tv.setdefault(int(r["tick"]), set()).add(int(r["unit"]))
    return {t: frozenset(s) for t, s in tv.items()}


def daysig(mem):
    return C.day_sig(
        list(csv.DictReader(open(mem))))


def m_basic(mem):
    tv = tickvec(mem)
    vecs = list(tv.values())
    n_pv = len(set(vecs))
    rep = 1 - n_pv / len(vecs) if vecs else -1.0
    by = daysig(mem)
    sigs = [s for s in by.values() if s]
    n_sig = len({frozenset(s) for s in sigs})
    per_unit = {}
    for u in range(29):
        ts = sorted(t for t, s in tv.items() if u in s)
        per_unit[u] = ts
    diffs = []
    for ts in per_unit.values():
        diffs += [b - a for a, b in zip(ts, ts[1:])]
    isi = (round(st.mean(diffs), 2), round(st.pstdev(diffs), 2),
           len(diffs)) if diffs else (-1, -1, 0)
    days = sorted(by)
    h = len(days) // 2
    s1 = {frozenset(by[d]) for d in days[:h] if by[d]}
    s2 = {frozenset(by[d]) for d in days[h:] if by[d]}
    stab = (len(s1 & s2) / len(s1 | s2)) if (s1 | s2) else -1.0
    return {"rows": sum(1 for _ in open(mem)) - 1, "N_sig": n_sig,
            "N_pv": n_pv, "repetition": round(rep, 4),
            "ISI": isi, "stabilite": round(stab, 4),
            "days": len(by),
            "units": sorted({u for s in by.values() for u in s})}


def day_jacc(a, b):
    ds = [d for d in set(a) | set(b) if a.get(d) or b.get(d)]
    if not ds:
        return -1.0
    tot = 0.0
    for d in ds:
        x, y = a.get(d, set()), b.get(d, set())
        if not x and not y:
            tot += 1.0
        elif not x or not y:
            tot += 0.0
        else:
            tot += len(x & y) / len(x | y)
    return tot / len(ds)


def front(outdir, days=130, seed=42, **kw):
    os.makedirs(outdir, exist_ok=True)
    cmd = [sys.executable, os.path.join(ROOT, "drive_line_front.py"),
           "--seed", str(seed), "--days", str(days), "--outdir", outdir]
    for k, v in kw.items():
        fl = f"--{k}".replace("_", "-")
        cmd += [fl, str(v)] if v is not True else [fl]
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       timeout=900)
    assert p.returncode == 0, p.stderr[-500:]
    return outdir


def plant_aff(d, days, cond=None, test=3):
    cond = days // 10 - 3 if cond is None else cond
    p = C.run([PLANT, "--spikes", f"{d}/pspikes.csv", "--sensors",
               f"{d}/sensors.csv", "--out", f"{d}/plant_out.csv",
               "--aff", f"{d}/afferent.csv",
               "--cond", str(cond), "--test", str(test)])
    assert p.returncode == 0, p.stderr[-500:]
    return f"{d}/afferent.csv"


def consume(aff, outdir, eta="0.30"):
    os.makedirs(outdir, exist_ok=True)
    _, evs, full, _ = C.stage_intake(aff, outdir)
    _, spk = C.stage_encoder(evs, outdir)
    aff2 = C.stage_adapter(spk, evs, full, outdir)
    mem, _ = C.stage_v3(aff2, outdir, eta)
    return mem, m_basic(mem), evs


def case(name, days=130, seed=42, eta="0.30", cond=None, test=3,
         **kw):
    """Tam hat: front->plant->v3 + metrik. Ayni isim = kayitli tekrar-kullanim."""
    if (name, eta) in registry:
        return registry[(name, eta)]
    d = front(f"{BASE}/{name}", days=days, seed=seed, **kw)
    a = plant_aff(d, days, cond=cond, test=test)
    mem, m, _ = consume(a, f"{BASE}/{name}_c", eta=eta)
    registry[(name, eta)] = (mem, m)
    results[name] = m
    return mem, m


def wins_of(mem, label, off):
    by = daysig(mem)
    wins = []
    days = sorted(by)
    for i in range(len(days) - K + 1):
        ds = days[i:i + K]
        if ds != list(range(ds[0], ds[0] + K)):
            continue
        seq = tuple({"posts": by.get(x, set()), "blines": set(),
                     "a": set()} for x in ds)
        if not any(sg["posts"] for sg in seq):
            continue
        wins.append({"s": ds[0] + off, "seq": seq, "label": label})
    return wins


def retrieval_acc(pools):
    """pools: [(mem, label)] -> LOO nearest-sequence dogruluk (rapor)."""
    wins = []
    for i, (mem, lab) in enumerate(pools):
        wins += wins_of(mem, lab, i * 100000)
    if len(wins) < 4:
        return -1.0, len(wins)
    cm, _ = infer(wins)
    tot = sum(cm.values())
    ok = sum(v for (t, p), v in cm.items() if t == p)
    return round(ok / tot, 4) if tot else -1.0, tot


def sensor_dist(d1, d2, last=10):
    def meanv(d):
        rows = list(csv.reader(open(f"{d}/sensors.csv")))
        tail = [[float(x) for x in r[1:8]] for r in rows[-last:]]
        return [st.mean(c) for c in zip(*tail)]
    a, b = meanv(d1), meanv(d2)
    return round(math.dist(a, b), 2)


def set_jacc(a, b):
    a, b = set(a), set(b)
    return round(len(a & b) / len(a | b), 4) if (a | b) else -1.0


def sigset(mem):
    return {frozenset(s) for s in daysig(mem).values() if s}


def seqsig(mem, s_min=0):
    out = set()
    for w in wins_of(mem, "x", 0):
        if w["s"] >= s_min:
            out.add(tuple(frozenset(s["posts"]) for s in w["seq"]))
    return out


WB = f"{WV}/W-base.csv"


def g1():
    print("G1 tek-degisken:")
    cases = {
        "base": {}, "irrig": {"irrig": 20.0}, "fert": {"fert": 30.0},
        "soil": {"soil": "kumlu"}, "hot": {"weather": f"{WV}/W-hot.csv"},
        "cold": {"weather": f"{WV}/W-cold.csv"},
        "drought": {"drought": True, "drought_from": 60,
                    "drought_len": 60},
    }
    mems = {}
    for tag, kw in cases.items():
        kw = dict(kw)
        if "weather" not in kw:
            kw["weather"] = WB
        mem, m = case(f"g1_{tag}", **kw)
        mems[tag] = mem
        print(f"  {tag}: rows={m['rows']} Nsig={m['N_sig']} "
              f"Npv={m['N_pv']} rep={m['repetition']} stab={m['stabilite']}")
    acc, n = retrieval_acc([(mm, t) for t, mm in mems.items()])
    print(f"  retrieval-acc={acc}(n={n})")
    check("G1-crash-yok", True)
    return mems


def g2():
    print("G2 kombinasyon:")
    mems = {}
    specs = {
        "dh": {"weather": f"{WV}/W-hot.csv", "drought": True,
               "drought_from": 60, "drought_len": 60},
        "df": {"weather": WB, "drought": True, "drought_from": 60,
               "drought_len": 60, "fert": 80.0},
        "wc": {"weather": f"{WV}/W-wetcold.csv"},
        "rec": {"weather": WB, "drought": True, "drought_from": 40,
                "drought_len": 40},
    }
    for tag, kw in specs.items():
        mem, m = case(f"g2_{tag}", **kw)
        mems[tag] = mem
        print(f"  {tag}: rows={m['rows']} Nsig={m['N_sig']} "
              f"Npv={m['N_pv']} rep={m['repetition']}")
    acc, n = retrieval_acc([(mm, t) for t, mm in mems.items()])
    print(f"  retrieval-acc={acc}(n={n})")
    check("G2-crash-yok", True)
    return mems


def remap_blocks(aff_in, aff_out, order, blen=500):
    with open(aff_in, newline="") as f:
        rows = list(csv.DictReader(f))
    maxt = max(int(r["tick"]) for r in rows)
    nb = maxt // blen + 1
    assert sorted(order) == list(range(nb)), "blok sirasi eksik!"
    pos = {b: i for i, b in enumerate(order)}
    out = []
    for r in rows:
        b = int(r["tick"]) // blen
        nt = pos[b] * blen + int(r["tick"]) % blen
        r2 = dict(r)
        r2["tick"] = str(nt)
        out.append(r2)
    out.sort(key=lambda r: int(r["tick"]))
    with open(aff_out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(out)
    return aff_out


def g3():
    print("G3 sira (blok-permutasyon):")
    case("g1_base", weather=WB)
    src = f"{BASE}/g1_base/afferent.csv"
    with open(src, newline="") as f:
        rows = list(csv.DictReader(f))
    nb = max(int(r["tick"]) for r in rows) // 500 + 1
    orders = {"ABC": list(range(nb)), "CBA": list(reversed(range(nb))),
              "ROT": list(range(4, nb)) + list(range(4))}
    res = {}
    for tag, od in orders.items():
        p = f"{BASE}/g3_{tag}.csv"
        remap_blocks(src, p, od)
        mem, m, _ = consume(p, f"{BASE}/g3_{tag}_c")
        res[tag] = (mem, m)
        print(f"  {tag}: Nsig={m['N_sig']} Npv={m['N_pv']} "
              f"rep={m['repetition']} stab={m['stabilite']}")
    s = {t: sigset(mm) for t, (mm, _) in res.items()}
    print(f"  setJ(ABC,CBA)={set_jacc(s['ABC'], s['CBA'])} "
          f"setJ(ABC,ROT)={set_jacc(s['ABC'], s['ROT'])}")
    check("G3-crash-yok", True)
    return res


def g4():
    print("G4 gecmis (final-30gun):")
    mn, _ = case("g1_base", weather=WB)
    mde, _ = case("g4_de", weather=WB, drought=True, drought_from=0,
                  drought_len=70)
    mie, _ = case("g4_ie", weather=WB, irrig=20.0, irrig_from=0,
                  irrig_len=70)
    f = {t: seqsig(mm, 70) for t, mm in
         (("normal", mn), ("d-erken", mde), ("i-erken", mie))}
    print(f"  setJ(n,d)={set_jacc(f['normal'], f['d-erken'])} "
          f"setJ(n,i)={set_jacc(f['normal'], f['i-erken'])} "
          f"sensDIST(n,d)={sensor_dist(f'{BASE}/g1_base', f'{BASE}/g4_de')} "
          f"sensDIST(n,i)={sensor_dist(f'{BASE}/g1_base', f'{BASE}/g4_ie')}")
    check("G4-crash-yok", True)
    return f


def g5():
    print("G5 yakin-komsu (drought %40/45/50):")
    mems = {}
    for tag, ln in (("d40", 52), ("d45", 58), ("d50", 65)):
        mem, m = case(f"g5_{tag}", weather=WB, drought=True,
                      drought_from=40, drought_len=ln)
        mems[tag] = mem
        print(f"  {tag}: Nsig={m['N_sig']} Npv={m['N_pv']}")
    mem_r, _ = case("g5_d45r", weather=WB, drought=True, drought_from=40,
                    drought_len=58, seed=43)
    sg = {t: daysig(mm) for t, mm in mems.items()}
    print(f"  within(45,45r)={round(day_jacc(sg['d45'], daysig(mem_r)), 4)} "
          f"betw(40,45)={round(day_jacc(sg['d40'], sg['d45']), 4)} "
          f"betw(45,50)={round(day_jacc(sg['d45'], sg['d50']), 4)} "
          f"betw(40,50)={round(day_jacc(sg['d40'], sg['d50']), 4)}")
    acc, n = retrieval_acc([(mm, t) for t, mm in
                            {**mems, "d45r": mem_r}.items()])
    print(f"  retrieval-acc={acc}(n={n})")
    check("G5-crash-yok", True)
    return mems


def g6():
    print("G6 uzun-sekans:")
    ml, m = case("g6_long", weather=WB, days=260, cond=20, test=6)
    print(f"  260gun: rows={m['rows']} Nsig={m['N_sig']} Npv={m['N_pv']} "
          f"rep={m['repetition']}")
    case("g1_base", weather=WB)
    with open(f"{BASE}/g1_base/afferent.csv", newline="") as f:
        rows = [r for r in csv.DictReader(f)
                if 3000 <= int(r["tick"]) < 3500]
    assert rows, "dilim bos!"
    tiled = []
    for k in range(6):
        for r in rows:
            r2 = dict(r)
            r2["tick"] = str(int(r["tick"]) - 3000 + k * 500)
            tiled.append(r2)
    tiled.sort(key=lambda r: int(r["tick"]))
    tp = f"{BASE}/g6_tile.csv"
    with open(tp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(tiled)
    _, mt, _ = consume(tp, f"{BASE}/g6_tile_c")
    print(f"  karo-x6: Nsig={mt['N_sig']} Npv={mt['N_pv']} "
          f"rep={mt['repetition']}")
    check("G6-crash-yok", True)
    return m, mt


def g7():
    print("G7 nadir/adversarial:")
    specs = {
        "burst": {"weather": f"{WV}/W-hot.csv", "irrig": 60.0,
                  "irrig_from": 90, "irrig_len": 2},
        "ec": {"weather": WB, "fert": 120.0, "fert_from": 90,
               "fert_len": 5, "irrig": 25.0, "irrig_from": 95,
               "irrig_len": 35},
        "snap": {"weather": WB, "drought": True, "drought_from": 40,
                 "drought_len": 60, "irrig": 30.0, "irrig_from": 100,
                 "irrig_len": 30},
    }
    for tag, kw in specs.items():
        mem, m = case(f"g7_{tag}", **kw)
        print(f"  {tag}: rows={m['rows']} Nsig={m['N_sig']} "
              f"Npv={m['N_pv']}")
    check("G7-crash-yok", True)


def g8():
    print("G8 tohum (ayni-dunya W-base):")
    mems = []
    for s in (42, 43, 44):
        mem, m = case(f"g8_{s}", weather=WB, seed=s)
        mems.append(mem)
        print(f"  s{s}: Nsig={m['N_sig']} Npv={m['N_pv']}")
    sg = [daysig(mm) for mm in mems]
    j = [day_jacc(sg[0], sg[1]), day_jacc(sg[0], sg[2]),
         day_jacc(sg[1], sg[2])]
    print(f"  seed-robustness={round(sum(j) / len(j), 4)} {j}")
    check("G8-crash-yok", True)
    return j


def g9():
    print("G9 dunya (drought x base/hot/cold):")
    mb, _ = case("g1_drought", weather=WB, drought=True, drought_from=60,
                 drought_len=60)
    mh, _ = case("g9_hot", weather=f"{WV}/W-hot.csv", drought=True,
                 drought_from=60, drought_len=60)
    mc, _ = case("g9_cold", weather=f"{WV}/W-cold.csv", drought=True,
                 drought_from=60, drought_len=60)
    win = lambda mm: {d: s for d, s in daysig(mm).items() if 60 <= d < 120}
    sb, sh, sc = win(mb), win(mh), win(mc)
    print(f"  jacc(b,h)={round(day_jacc(sb, sh), 4)} "
          f"jacc(b,c)={round(day_jacc(sb, sc), 4)} "
          f"jacc(h,c)={round(day_jacc(sh, sc), 4)}")
    acc, n = retrieval_acc([(mb, "b"), (mh, "h"), (mc, "c")])
    print(f"  retrieval-acc={acc}(n={n})")
    check("G9-crash-yok", True)


def g10():
    print("G10 eta (0 / 0.15 / 0.30):")
    case("g1_base", weather=WB)
    src = f"{BASE}/g1_base/afferent.csv"
    out = {}
    for eta in ("0", "0.15", "0.30"):
        mem, m, _ = consume(src, f"{BASE}/g10_{eta}", eta=eta)
        out[eta] = (mem, m)
        print(f"  eta={eta}: Nsig={m['N_sig']} Npv={m['N_pv']} "
              f"rep={m['repetition']} stab={m['stabilite']}")
    sg = {e: daysig(mm) for e, (mm, _) in out.items()}
    print(f"  jacc(0,0.30)={round(day_jacc(sg['0'], sg['0.30']), 4)} "
          f"jacc(0.15,0.30)={round(day_jacc(sg['0.15'], sg['0.30']), 4)}")
    check("G10-crash-yok", True)
    return out


def g11():
    print("G11 unseen (aile-uyumu):")
    refs = []
    for tag, kw in (("base", {}), ("drought", {"drought": True,
                    "drought_from": 60, "drought_len": 60}),
                    ("irrig", {"irrig": 20.0})):
        mem, _ = case(f"g1_{tag}", weather=WB, **kw)
        refs.append((mem, tag))
    queries = []
    for tag, kw in (("qb", {"seed": 101}), ("qd", {"seed": 101,
                    "drought": True, "drought_from": 60,
                    "drought_len": 60}),
                    ("qi", {"seed": 101, "irrig": 20.0}),
                    ("qd47", {"drought": True, "drought_from": 40,
                              "drought_len": 61})):
        mem, _ = case(f"g11_{tag}", weather=WB, **kw)
        fam = {"qb": "base", "qd": "drought", "qi": "irrig",
               "qd47": "drought"}[tag]
        queries.append((mem, fam, tag))
    rw = []
    for i, (mem, lab) in enumerate(refs):
        rw += wins_of(mem, lab, i * 100000)
    tot = ok = 0
    for mem, fam, tag in queries:
        qw = wins_of(mem, fam, 900000)
        hit = 0
        for q in qw:
            best, bs = None, -1.0
            for r in rw:
                v = seq_sim(q["seq"], r["seq"])
                if v > bs:
                    best, bs = r["label"], v
            tot += 1
            if best == fam:
                ok += 1
                hit += 1
        print(f"  {tag}->uyum={round(hit / len(qw), 4) if qw else -1}"
              f"(n={len(qw)})")
    print(f"  aile-uyumu={round(ok / tot, 4) if tot else -1}(n={tot})")
    check("G11-crash-yok", True)


def g12():
    print("G12 ayni-son-farkli-neden:")
    ma, _ = case("g12_a", weather=WB, drought=True, drought_from=40,
                 drought_len=40, irrig=30.0, irrig_from=80, irrig_len=50)
    mb, _ = case("g12_b", weather=WB, irrig=30.0, irrig_from=80,
                 irrig_len=50)
    fa, fb = seqsig(ma, 70), seqsig(mb, 70)
    print(f"  final-setJ={set_jacc(fa, fb)} "
          f"sensDIST={sensor_dist(f'{BASE}/g12_a', f'{BASE}/g12_b')}")
    acc, n = retrieval_acc([(ma, "a"), (mb, "b")])
    print(f"  retrieval-acc={acc}(n={n})")
    check("G12-crash-yok", True)


GROUPS = {"G1": g1, "G2": g2, "G3": g3, "G4": g4, "G5": g5, "G6": g6,
          "G7": g7, "G8": g8, "G9": g9, "G10": g10, "G11": g11,
          "G12": g12}


def main():
    ap = argparse.ArgumentParser(description="v3 full-system stress")
    ap.add_argument("--only", default="",
                    help="ornek: G1,G2 (bos=hepsi sirayla)")
    a = ap.parse_args()
    sel = [g.strip().upper() for g in a.only.split(",") if g.strip()] or \
        sorted(GROUPS)
    for g in sel:
        assert g in GROUPS, f"bilinmeyen grup: {g}"
        GROUPS[g]()
    with open(f"{BASE}/results.json", "w") as f:
        json.dump(results, f, default=str)
    print(f"OZET-PSTRESS: {'GECTI' if not fails else 'BATTI: ' + str(fails)}"
          f" gruplar={sel}")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
