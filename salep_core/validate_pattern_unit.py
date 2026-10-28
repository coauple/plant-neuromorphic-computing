"""Pattern Unit v2 dogrulama (C++ gercek, Python analiz) — Faz 3.

Zincir: testb_afferent.csv -> npu_pattern_unit_v2 -> v2_*_mem/log.csv
+ OZET-PATTERN-V2. Semantic yorum YOK; label lobe'a girmez.
Kapilar (S6 haritasi):
  V1-v2 build-parity (yeni binary) · V2-v2 determinizm · V3-v2 encoder
  esdegerligi · V4-v2 zincir (cok-P3x + kapasite sessizligi) · V5-v2 boff ·
  V6-v2 mining (populasyon vektorleri) · V7-v2 evre dagilimi ·
  V8-v2 agirlik rejimi (ogrenme KAPALI kilidi, wkdev==0) ·
  M1 ayna (float ikiz: ates-kumesi + sessizlik-kumesi esitligi; sayilar rapor).
"""
import csv
import os
import subprocess
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
EXE = os.path.join(ROOT, "npu_pattern_unit_v2")
AFF = os.path.join(ROOT, "testb_afferent.csv")
BOFF = os.path.join(ROOT, "boff_afferent.csv")
MEM = os.path.join(ROOT, "v2_testb_mem.csv")
LOG = os.path.join(ROOT, "v2_testb_log.csv")
STAGES = [("normal", 0, 30), ("kurak", 30, 60), ("siddetli", 60, 100),
          ("ara", 100, 130), ("yaz", 130, 170), ("sulama", 170, 180),
          ("recovery", 180, 220), ("test", 220, 250)]
WIRED = set(range(6))  # P3a..P3f (S5); P3g.. sessiz kapasite


def run(args):
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                          timeout=600)


def stage_of(tick):
    for (nm, a, b) in STAGES:
        if a <= tick // 50 < b:
            return nm
    return "dis"


def main():
    fails = []

    def check(name, cond, extra=""):
        print(f"  {'OK' if cond else 'BATTI'} {name} {extra}")
        if not cond:
            fails.append(name)

    # V1-v2 derleme paritesi: taze derle, ayni kablo, bit-esit mem/log.
    exe2 = "/tmp/npu_pattern_unit_v2_v"
    p = run(["g++", "-std=c++17", "-O2", "-Isrc",
             "src/main_pattern_unit_v2.cpp", "-o", exe2])
    check("V1-build", p.returncode == 0, p.stderr[-300:])
    p1 = run([EXE, "--aff", AFF, "--mem", MEM, "--log", LOG])
    ozet = [l for l in p1.stdout.splitlines() if "OZET-PATTERN-V2" in l]
    check("V1-run", p1.returncode == 0 and len(ozet) == 1, ozet)
    p2 = run([exe2, "--aff", AFF, "--mem", "/tmp/v2m_v.csv", "--log",
              "/tmp/v2l_v.csv"])
    with open(MEM, "rb") as f1, open("/tmp/v2m_v.csv", "rb") as f2:
        same = f1.read() == f2.read()
    with open(LOG, "rb") as f1, open("/tmp/v2l_v.csv", "rb") as f2:
        same = same and f1.read() == f2.read()
    check("V1-parity", same, "kaynak=ikili")

    # V2-v2 determinizm (2. kosu bit-esit).
    p3 = run([EXE, "--aff", AFF, "--mem", "/tmp/v2m_d.csv", "--log",
              "/tmp/v2l_d.csv"])
    with open(MEM, "rb") as f1, open("/tmp/v2m_d.csv", "rb") as f2:
        d1 = f1.read() == f2.read()
    with open(LOG, "rb") as f1, open("/tmp/v2l_d.csv", "rb") as f2:
        d1 = d1 and f1.read() == f2.read()
    check("V2-determinism", d1, "2x bit-esit")

    # V3-v2 encoder esdegerligi (SPEC_v0_1 portu, ilk olay/tick).
    log = list(csv.DictReader(open(LOG)))
    aff = list(csv.DictReader(open(AFF)))
    aff_by_tick = {}
    for r in aff:
        aff_by_tick.setdefault(int(r["tick"]), []).append(
            (int(r["post_id"]), int(r["tau_b"])))
    ok3, n3 = True, 0
    for row in log:
        t = int(row["tick"])
        if t in aff_by_tick:
            p0, b0 = aff_by_tick[t][0]
            if p0 >= 12:
                ok3 = False
                break
            if (int(row["phi_id"]) != p0 * 3000 or
                    int(row["phi_tau"]) != ((b0 - 4) * 36000) // 57):
                ok3 = False
                break
            n3 += 1
    check("V3-encoder", ok3 and n3 == len(aff_by_tick),
          f"{n3}/{len(aff_by_tick)} olay-ticki")

    # V4-v2 zincir: olay sayisi + mem=toplam ates + ates-kumesi + sessizlik.
    mem = list(csv.DictReader(open(MEM)))
    oz = ozet[0]
    firing = set(int(r["unit"]) for r in mem)
    per_unit = Counter(int(r["unit"]) for r in mem)
    n_ev = int(oz.split("olay=")[1].split()[0])
    check("V4-chain",
          n_ev == len(aff) and len(mem) == sum(per_unit.values())
          and firing == WIRED,
          f"olay={n_ev} mem={len(mem)} ates-kumesi={sorted(firing)} "
          f"sessiz=P3g..P3ac")

    # V5-v2 boff: tum 29 sessiz, mem=0.
    pb = run([EXE, "--aff", BOFF, "--mem", "/tmp/v2m_b.csv", "--log",
              "/tmp/v2l_b.csv"])
    bo = [l for l in pb.stdout.splitlines() if "OZET-PATTERN-V2" in l][0]
    barr = [int(x) for x in bo.split("ates=[")[1].split("]")[0].split(",")]
    check("V5-boff", "mem=0" in bo and all(v == 0 for v in barr),
          bo.strip()[:100])

    # V6-v2 mining: populasyon vektorleri + tekrar + sessiz-devamsizlik.
    vec = Counter()
    for r in log:
        m = int(r["fires_hex"], 16)
        if m:
            vec[m] += 1
    reps = sum(v - 1 for v in vec.values() if v > 1)
    silent_seen = any(m >> 6 for m in vec)
    check("V6-mining", len(vec) >= 5 and reps >= 10 and not silent_seen,
          f"{len(vec)} vektor, {reps} tekrar, sessiz-gorulme={silent_seen}")

    # V7-v2 evre dagilimi (birim-basina >1 evre, toplam >1 evre).
    ticks = [int(r["tick"]) for r in mem]
    per_stage = Counter(stage_of(t) for t in ticks)
    check("V7-stages", len(per_stage) > 1, dict(per_stage))

    # V8-v2 agirlik rejimi: ogrenme KAPALI kilidi (wkdev==0).
    wkdev = float(oz.split("wkdev=")[1].split()[0])
    check("V8-weights", wkdev == 0.0, f"wkdev={wkdev} (rejim: sabit w0)")

    # V8L ogrenen rejim (--eta 0.30): determinizm + wkdev>0 + sessizlik.
    pl = run([EXE, "--aff", AFF, "--mem", "/tmp/v2m_l.csv", "--log",
              "/tmp/v2l_l.csv", "--eta", "0.30"])
    lo = [l for l in pl.stdout.splitlines() if "OZET-PATTERN-V2" in l][0]
    pl2 = run([EXE, "--aff", AFF, "--mem", "/tmp/v2m_l2.csv", "--log",
               "/tmp/v2l_l2.csv", "--eta", "0.30"])
    with open("/tmp/v2m_l.csv", "rb") as f1, open("/tmp/v2m_l2.csv",
                                                  "rb") as f2:
        ldet = f1.read() == f2.read()
    with open("/tmp/v2l_l.csv", "rb") as f1, open("/tmp/v2l_l2.csv",
                                                  "rb") as f2:
        ldet = ldet and f1.read() == f2.read()
    lwk = float(lo.split("wkdev=")[1].split()[0])
    lm = list(csv.DictReader(open("/tmp/v2m_l.csv")))
    lfire = set(int(r["unit"]) for r in lm)
    wtab = {}
    for l in pl.stdout.splitlines():
        if l.startswith("W "):
            _, us, ks, ws = l.split()
            wtab[(int(us), ks)] = float(ws)
    check("V8L-learn", ldet and lwk > 0 and lfire == WIRED,
          f"det={ldet} wkdev={lwk:.4f} ates-kumesi={sorted(lfire)} "
          f"mem={len(lm)}")
    with open("/tmp/v2_wtab.txt", "w") as f:
        for (us, ks), ws in sorted(wtab.items()):
            f.write(f"{us} {ks} {ws:.6f}\n")

    # M1 ayna: float ikiz ates/sessizlik kumeleri + sayi raporu.
    sys.path.insert(0, os.path.join(ROOT, "pattern"))
    from pl_core import v2_drive
    evs = [(int(r["tick"]), int(r["post_id"])) for r in aff]
    mf = v2_drive(evs, max(t for t, _ in evs))
    m_firing = set(i for i in mf if mf[i])
    cpp_counts = {u: per_unit.get(u, 0) for u in sorted(firing)}
    py_counts = {u: len(mf[u]) for u in sorted(m_firing)}
    check("M1-mirror", m_firing == firing,
          f"cpp={cpp_counts} py={py_counts}")

    print("OZET-PATTERN-UNIT-VALIDATE: " + " ".join(
        ["V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8", "V8L", "M1"])
        + (" OK" if not fails else " BATTI:" + ",".join(fails)))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
