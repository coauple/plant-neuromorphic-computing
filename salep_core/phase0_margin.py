"""Faz 0 margin altyapisi + V1-V5 (V3D_READOUT_SPEC.md).

Cekirdek/frozen/encoder/sensory DEGISTIRILMEZ. Okuma: pattern/readout_v3d.
Ciktilar stress_out_v2/ (stress_out/ DOKUNULMAZ).
Kullanim: .venv/bin/python phase0_margin.py [--only V0,V1,...]
"""
import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "pattern"))
import readout_v3d as R  # noqa: E402
import run_chain_v3 as C  # noqa: E402

BASE = "/tmp/pstress_d"
OUT2 = "/tmp/stress_out_v2"
V3D = os.path.join(ROOT, "npu_pattern_unit_v3d")
fails = []
rep = {}


def check(name, cond, extra=""):
    print(f"  {'OK' if cond else 'BATTI'} {name} {extra}", flush=True)
    if not cond:
        fails.append(name)


def md5(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def mem_of(case):
    return f"{BASE}/{case}_c/mem.csv"


def sig_of(case, ro="S0"):
    tv, by = R.load_mem(mem_of(case))
    return R.READOUTS[ro](tv, by)


def v0():
    print("V0 margin altyapisi:")
    g1 = ["g1_base", "g1_irrig", "g1_fert", "g1_soil", "g1_hot",
          "g1_drought"]
    affs = {c: f"{BASE}/{c}/afferent.csv" for c in g1}
    dig = {c: md5(p) for c, p in affs.items()}
    distinct = len(set(dig.values())) == len(dig)
    print(f"  kablo-md5-farkli={distinct}")
    check("V0-md5", distinct)
    # T: ayni-senaryo + ayni-tohum tekrar (mem vs chk).
    t = R.day_jacc(R.READOUTS["S0"](*R.load_mem(mem_of("g1_base"))),
                   R.READOUTS["S0"](
                       *R.load_mem(mem_of("g1_base") + ".chk")))
    # N: G8 uclusu.
    n12 = R.day_jacc(sig_of("g8_42"), sig_of("g8_43"))
    n13 = R.day_jacc(sig_of("g8_42"), sig_of("g8_44"))
    n23 = R.day_jacc(sig_of("g8_43"), sig_of("g8_44"))
    n = round((n12 + n13 + n23) / 3, 4)
    # B: md5-farkli kumede tum cifler.
    sg = {c: sig_of(c) for c in g1}
    pairs = []
    for i in range(len(g1)):
        for j in range(i + 1, len(g1)):
            pairs.append(R.day_jacc(sg[g1[i]], sg[g1[j]]))
    b = round(sum(pairs) / len(pairs), 4)
    margin = round(t - b, 4)
    print(f"  T={t} N={n} B={b} margin={margin} B<N={b < n} B!=N={b != n}")
    check("V0-TNB", t >= 0 and n >= 0 and b >= 0)
    check("V0-BNEQN", b != n)
    rep["V0"] = {"T": t, "N": n, "B": b, "margin": margin,
                 "md5_distinct": distinct}
    return t, n, b


def v1():
    print("V1 ROT-750 (gun-kati-disi):")
    src = f"{BASE}/g1_base/afferent.csv"
    with open(src, newline="") as f:
        rows = list(csv.DictReader(f))
    maxt = max(int(r["tick"]) for r in rows)
    nb = (maxt + 1) // 500  # yalniz TAM bloklar
    rot = list(range(1, nb)) + [0]
    pos = {b: i for i, b in enumerate(rot)}
    fixed = []
    for r in rows:
        b = int(r["tick"]) // 500
        if b >= nb:
            continue  # kismi blok duser
        # blok permutasyonu + 250 tick blok-ici kayma (gun-kati disi).
        nt = pos[b] * 500 + (int(r["tick"]) % 500 + 250) % 500
        r2 = dict(r)
        r2["tick"] = str(nt)
        fixed.append(r2)
    fixed.sort(key=lambda r: int(r["tick"]))
    pp = "/tmp/stress_out_v2/g3_rot750.csv"
    os.makedirs("/tmp/stress_out_v2", exist_ok=True)
    with open(pp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(fixed)
    os.makedirs("/tmp/stress_out_v2/rot750", exist_ok=True)
    _, evs, full, _ = C.stage_intake(pp, "/tmp/stress_out_v2/rot750")
    _, spk = C.stage_encoder(evs, "/tmp/stress_out_v2/rot750")
    aff2 = C.stage_adapter(spk, evs, full, "/tmp/stress_out_v2/rot750")
    mem, _ = C.stage_v3(aff2, "/tmp/stress_out_v2/rot750", "0.30")
    tv, by = R.load_mem(mem)
    s_abc = {frozenset(s) for s in R.READOUTS["S0"](*R.load_mem(
        mem_of("g1_base"))).values() if s}
    s_rot = {frozenset(s) for s in R.READOUTS["S0"](tv, by).values()
             if s}
    j = (len(s_abc & s_rot) / len(s_abc | s_rot)) if (s_abc | s_rot) \
        else -1.0
    print(f"  setJ(ABC,ROT750)={round(j, 4)}")
    check("V1-rot", j < 0.9, f"j={round(j, 4)}")
    rep["V1"] = {"setJ_ROT750": round(j, 4)}


def drive(days, seed, outdir, **kw):
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


def v2():
    print("V2 drought% aktif-pencere + kablo-assert:")
    digs = {}
    for tag, ln in (("d40", 52), ("d45", 58), ("d50", 65)):
        d = drive(130, 42, f"/tmp/stress_out_v2/v2_{tag}", weather=V2W,
                  drought=True, drought_from=47, drought_len=ln)
        p = C.run([os.path.join(ROOT, "npu_sensory_plant"), "--spikes",
                   f"{d}/pspikes.csv", "--sensors", f"{d}/sensors.csv",
                   "--out", f"{d}/plant_out.csv", "--aff",
                   f"{d}/afferent.csv", "--cond", "10", "--test", "3"])
        assert p.returncode == 0, p.stderr[-500:]
        digs[tag] = md5(f"{d}/afferent.csv")
    ok = len(set(digs.values())) == 3
    print(f"  md5-farkli={ok} {list(digs.values())}")
    check("V2-md5", ok)
    rep["V2"] = {"md5_distinct": ok,
                 "md5": {k: v[:12] for k, v in digs.items()}}


V2W = os.path.join(ROOT, "weather_v3", "W-base.csv")


def v3():
    print("V3 soguk karari:")
    import csv as _c
    rows = sum(1 for _ in open(mem_of("g1_cold"))) - 1 \
        if os.path.exists(mem_of("g1_cold")) else 0
    scoped = (rows == 0)
    print(f"  cold-rows={rows} kapsam-disi={scoped}")
    check("V3-karar", True, "kapsam-disi" if scoped else "canli")
    rep["V3"] = {"cold_rows": rows, "scoped_out": scoped}


def stab_new(mem):
    tv, by = R.load_mem(mem)
    days = sorted(by)
    h = len(days) // 2
    s1 = {frozenset(by[d]) for d in days[:h] if by[d]}
    s2 = {frozenset(by[d]) for d in days[h:] if by[d]}
    if not s1 or not s2:
        return -1.0
    i = len(s1 & s2)
    return round(0.5 * (i / len(s1) + i / len(s2)), 4)


def v4():
    print("V4 yeni stabilite:")
    import glob as _g
    vals = {}
    for mp in sorted(_g.glob(f"{BASE}/*_c/mem.csv")):
        tag = os.path.basename(os.path.dirname(mp))
        tag = tag[:-2] if tag.endswith("_c") else tag
        tv, by = R.load_mem(mp)
        days = sorted(by)
        h = len(days) // 2
        s1 = {frozenset(by[d]) for d in days[:h] if by[d]}
        s2 = {frozenset(by[d]) for d in days[h:] if by[d]}
        old = (len(s1 & s2) / len(s1 | s2)) if (s1 | s2) else -1.0
        vals[tag] = (round(old, 4), stab_new(mp))
    for tag in ["g1_base", "g1_drought", "g8_42"]:
        if tag in vals:
            print(f"  {tag}: eski={vals[tag][0]} yeni={vals[tag][1]}")
    check("V4-tanimli", True)
    rep["V4"] = {"not": "eski-jaccard yan yana; ornekler logda"}


def v5():
    print("V5 esit-uzunluk (tile vs kirpilmis-long):")
    tv, by = R.load_mem(mem_of("g6_long"))
    tv3k = {t: s for t, s in tv.items() if t <= 3000}
    vecs = [frozenset(s) for s in tv3k.values()]
    n_pv = len(set(vecs))
    rep_ = round(1 - n_pv / len(vecs), 4) if vecs else -1.0
    by3k = {}
    for t, s in tv3k.items():
        by3k.setdefault(t // 50, set()).update(s)
    n_sig = len({frozenset(s) for s in by3k.values() if s})
    print(f"  kirpilmis-long: Nsig={n_sig} Npv={n_pv} rep={rep_} "
          f"(tile: Nsig=12 Npv=50 rep=0.4845)")
    check("V5-rapor", True)
    rep["V5"] = {"long_Nsig": n_sig, "long_Npv": n_pv, "long_rep": rep_}


G1CASES = ["g1_base", "g1_irrig", "g1_fert", "g1_soil", "g1_hot",
           "g1_drought"]


def sigs_of(case, ro):
    tv, by = R.load_mem(mem_of(case))
    return R.READOUTS[ro](tv, by)


def phase1():
    print("Faz 1 readout tablosu:")
    rows = {}
    refs = [(sigs_of(c, "S0"), c.split("g1_")[1]) for c in G1CASES]
    qd_tv, qd_by = R.load_mem(mem_of("g11_qd47"))
    for ro in ["S0", "S1", "S2a", "S2b", "S3", "S0n"]:
        tv0, by0 = R.load_mem(mem_of("g1_base"))
        tvc, byc = R.load_mem(mem_of("g1_base") + ".chk")
        f = R.READOUTS[ro]
        t = R.day_jacc(f(tv0, by0), f(tvc, byc))
        sg = [f(*R.load_mem(mem_of(c))) for c in
              ["g8_42", "g8_43", "g8_44"]]
        n = round((R.day_jacc(sg[0], sg[1]) + R.day_jacc(sg[0], sg[2])
                   + R.day_jacc(sg[1], sg[2])) / 3, 4)
        sc = {c: sigs_of(c, ro) for c in G1CASES}
        prs = []
        for i in range(len(G1CASES)):
            for j in range(i + 1, len(G1CASES)):
                prs.append(R.day_jacc(sc[G1CASES[i]], sc[G1CASES[j]]))
        b = round(sum(prs) / len(prs), 4)
        acc, nn = R.ret_acc([(sc[c], c.split("g1_")[1]) for c in G1CASES])
        rq = [(sigs_of(c, ro), c.split("g1_")[1]) for c in
              ["g1_base", "g1_drought", "g1_irrig"]]
        fam = R.fam_agree(rq, [(f(qd_tv, qd_by), "drought", "qd47")])
        ns = len({s for s in f(tv0, by0).values() if s})
        rows[ro] = {"T": t, "N": n, "B": b, "margin": round(t - b, 4),
                    "ret_acc": acc, "ret_n": nn,
                    "fam_qd": fam["qd47"], "N_sig": ns}
        print(f"  {ro}: T={t} N={n} B={b} margin={round(t - b, 4)} "
              f"ret={acc}(n={nn}) qd={fam['qd47']} Nsig={ns}")
    check("F1-hesap", True)
    rep["F1"] = rows
    return rows


def main():
    ap = argparse.ArgumentParser(description="Faz 0 margin + Faz 1")
    ap.add_argument("--only", default="",
                    help="ornek: V0,V1 (bos=V0 sirasiyla; F1 ayri)")
    a = ap.parse_args()
    os.makedirs(OUT2, exist_ok=True)
    sel = [g.strip().upper() for g in a.only.split(",") if g.strip()] or \
        ["V0"]
    fn = {"V0": v0, "V1": v1, "V2": v2, "V3": v3, "V4": v4, "V5": v5,
          "F1": phase1}
    for g in sel:
        assert g in fn, f"bilinmeyen: {g}"
        fn[g]()
        if g == "V0" and ("V0-BNEQN" in fails or "V0-md5" in fails):
            print("V0 GECMEDI — DUR (Faz 1 acilmaz)")
            break
    mp = os.path.join(OUT2, "margin.json")
    merged = dict(rep)
    if os.path.exists(mp):
        with open(mp) as f:
            old = json.load(f)
        old.update(merged)
        merged = old
    with open(mp, "w") as f:
        json.dump(merged, f, default=str)
    print(f"OZET-MARGIN: {'GECTI' if not fails else 'BATTI: ' + str(fails)}"
          f" ({sel})")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
