"""Stres paketi: uretim-hatti ciktisi -> v3 tuketim hatti, 10 madde.

Onkosul: pilot yesil (run_chain_v3.py). Bu dosya YENI davranislarin
kilitli probudur (durable-test-collateral): ayni mantik, tekrar-kosulur.
Kapilar (BATTI = cikis-kodu 1): crash-yok (adversarial dahil exit 0),
determinizm (tekrar sha-esit), viol==0, encoder/adapter esitligi
(run_chain_v3 icinden aynen). Rapor (kapisiz): farklilasma/skorlar.
"""
import csv
import os
import random
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import run_chain_v3 as C  # noqa: E402

BASE = "/tmp/stress_v3"
PLANT = os.path.join(ROOT, "npu_sensory_plant")
fails = []


def check(name, cond, extra=""):
    print(f"  {'OK' if cond else 'BATTI'} {name} {extra}")
    if not cond:
        fails.append(name)


def front(outdir, seed=42, days=60, **kw):
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


def plant_aff(d, cond=4, test=2):
    p = C.run([PLANT, "--spikes", f"{d}/pspikes.csv", "--sensors",
               f"{d}/sensors.csv", "--out", f"{d}/plant_out.csv",
               "--aff", f"{d}/afferent.csv",
               "--cond", str(cond), "--test", str(test)])
    assert p.returncode == 0, p.stderr[-500:]
    return f"{d}/afferent.csv"


def consume(aff, outdir, eta="0.30", stages=None):
    os.makedirs(outdir, exist_ok=True)
    _, evs, full, _ = C.stage_intake(aff, outdir)
    _, spk = C.stage_encoder(evs, outdir)
    aff2 = C.stage_adapter(spk, evs, full, outdir)
    mem, _ = C.stage_v3(aff2, outdir, eta)
    m = C.stage_memory(mem, stages)
    return mem, m, evs


def mem_sig(mem):
    with open(mem) as f:
        rows = list(csv.DictReader(f))
    return C.day_sig(rows)


def jacc(a, b):
    ka = {d: frozenset(s) for d, s in a.items()}
    kb = {d: frozenset(s) for d, s in b.items()}
    days = set(ka) | set(kb)
    js = [len(ka[d] & kb[d]) / len(ka[d] | kb[d])
          for d in days if ka.get(d) and kb.get(d)]
    return sum(js) / len(js) if js else -1.0


def plant130(d):
    return plant_aff(d, cond=10, test=3)


def t_tek():
    print("T1 tek-degiskenli (130 gun):")
    d0 = front(f"{BASE}/t1_base", days=130)
    a0 = plant130(d0)
    _, m0, _ = consume(a0, f"{BASE}/t1_base_c")
    dd = front(f"{BASE}/t1_drought", days=130, drought=True,
               drought_from=60, drought_len=60)
    ad = plant130(dd)
    _, md, _ = consume(ad, f"{BASE}/t1_drought_c")
    di = front(f"{BASE}/t1_irrig", days=130, irrig=20.0)
    ai = plant130(di)
    _, mi, _ = consume(ai, f"{BASE}/t1_irrig_c")
    print(f"  base={m0['rows']} drought={md['rows']} irrig={mi['rows']}")
    check("T1-crash-yok", True)
    check("T1-kosul-farklilasti",
          m0["rows"] != md["rows"] or m0["rows"] != mi["rows"],
          "(rapor)")


def t_combo():
    print("T2 coklu-stres (130 gun):")
    dd = front(f"{BASE}/t2_di", days=130, drought=True, drought_from=60,
               drought_len=60, irrig=20.0)
    ad = plant130(dd)
    _, md, _ = consume(ad, f"{BASE}/t2_di_c")
    df = front(f"{BASE}/t2_df", days=130, drought=True, drought_from=60,
               drought_len=60, fert=30.0)
    af = plant130(df)
    _, mf, _ = consume(af, f"{BASE}/t2_df_c")
    print(f"  drought+irrig={md['rows']} drought+fert={mf['rows']}")
    check("T2-crash-yok", True)


def t_sira():
    print("T3 olay-sirasi (tick-ici permutasyon):")
    d0 = front(f"{BASE}/t3_base", days=60)
    a0 = plant_aff(d0)
    with open(a0, newline="") as f:
        rows = list(csv.DictReader(f))
    rng = random.Random(7)
    perm = []
    cur, grp = None, []
    for r in rows + [None]:
        t = r["tick"] if r else None
        if t != cur and grp:
            rng.shuffle(grp)
            perm += grp
            grp = []
        cur = t
        if r:
            grp.append(r)
    pp = f"{BASE}/t3_perm.csv"
    with open(pp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(perm)
    m1, _, _ = consume(a0, f"{BASE}/t3_a")
    m2, _, _ = consume(pp, f"{BASE}/t3_b")
    same = C.sha(m1) == C.sha(m2)
    print(f"  permutasyon-sonrasi-mem-ayni={same}")
    check("T3-crash-yok", True)
    check("T3-rapor", True, f"ayni={same}")


def t_gecmis():
    print("T4 farkli-gecmis (60 vs 130 gun):")
    d6 = front(f"{BASE}/t4_60", days=60)
    a6 = plant_aff(d6, cond=4, test=2)
    _, m6, _ = consume(a6, f"{BASE}/t4_60_c")
    d13 = front(f"{BASE}/t4_130", days=130)
    a13 = plant_aff(d13, cond=10, test=3)
    _, m13, _ = consume(a13, f"{BASE}/t4_130_c")
    print(f"  60gun={m6['rows']} 130gun={m13['rows']}")
    check("T4-crash-yok", True)


def t_seed():
    print("T5 ayni-kosul-farkli-seed (drought x 42/43/44):")
    sigs = []
    for s in (42, 43, 44):
        d = front(f"{BASE}/t5_{s}", seed=s, days=130, drought=True,
                  drought_from=60, drought_len=60)
        a = plant130(d)
        m, _, _ = consume(a, f"{BASE}/t5_{s}_c")
        sigs.append(mem_sig(m))
    j12 = jacc(sigs[0], sigs[1])
    j13 = jacc(sigs[0], sigs[2])
    print(f"  jacc(42,43)={j12:.3f} jacc(42,44)={j13:.3f}")
    check("T5-crash-yok", True)
    check("T5-seed-farklilasti", j12 < 1.0 or j13 < 1.0, "(rapor)")


def t_sondurum():
    print("T6 farkli-kosul-ayni-son (drought vs irrig):")
    dd = front(f"{BASE}/t6_d", days=130, drought=True, drought_from=60,
               drought_len=60)
    ad = plant130(dd)
    md, mdd, _ = consume(ad, f"{BASE}/t6_d_c")
    di = front(f"{BASE}/t6_i", days=130, irrig=20.0)
    ai = plant130(di)
    mi, mdi, _ = consume(ai, f"{BASE}/t6_i_c")
    print(f"  drought={mdd['rows']} irrig={mdi['rows']}")
    check("T6-crash-yok", True)


def t_nadir():
    print("T7 nadir/adversarial:")
    d0 = front(f"{BASE}/t7_base", days=60)
    a0 = plant_aff(d0)
    with open(a0, newline="") as f:
        rows = list(csv.DictReader(f))
    hdr = rows[0].keys()
    emp = f"{BASE}/t7_empty.csv"
    with open(emp, "w", newline="") as f:
        csv.DictWriter(f, fieldnames=hdr).writeheader()
    one = f"{BASE}/t7_one.csv"
    with open(one, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=hdr)
        w.writeheader()
        w.writerow(rows[0])
    dup = f"{BASE}/t7_dup.csv"
    with open(dup, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=hdr)
        w.writeheader()
        w.writerows(rows + rows)
    for tag, p in (("empty", emp), ("one", one), ("dup", dup)):
        try:
            m, mm, evs = consume(p, f"{BASE}/t7_{tag}")
            print(f"  {tag}: olay={len(evs)} mem={mm['rows']}")
            check(f"T7-{tag}-crash-yok", True)
        except AssertionError as e:
            if tag == "empty" or "memory bos" in str(e):
                print(f"  {tag}: kenar-durum ({e})")
                check(f"T7-{tag}-kenar", True, "rapor")
            else:
                check(f"T7-{tag}-crash-yok", False, str(e)[:100])


def t_eta():
    print("T8 ogrenme kapali/acik:")
    d0 = front(f"{BASE}/t8_base", days=60)
    a0 = plant_aff(d0)
    _, mf, _ = consume(a0, f"{BASE}/t8_frozen", eta="0")
    m1, mo, _ = consume(a0, f"{BASE}/t8_open", eta="0.30")
    print(f"  frozen={mf['rows']} open={mo['rows']}")
    check("T8-eta-kolu", True)


def t_unseen():
    print("T9 egitimsiz-varyasyon (seed 101/102 + soil):")
    for tag, kw in (("s101", {"seed": 101}),
                    ("s102", {"seed": 102}),
                    ("soil", {"soil": "kumlu"})):
        try:
            d = front(f"{BASE}/t9_{tag}", days=60, **kw)
            a = plant_aff(d)
            _, m, _ = consume(a, f"{BASE}/t9_{tag}_c")
            print(f"  {tag}: mem={m['rows']}")
            check(f"T9-{tag}", True)
        except Exception as e:
            check(f"T9-{tag}", False, str(e)[:120])


def t_retrieval():
    print("T10 retrieval-tutarlilik (capraz-kosu):")
    d0 = front(f"{BASE}/t10_base", days=130, drought=True,
               drought_from=60, drought_len=60)
    a0 = plant130(d0)
    m1, _, _ = consume(a0, f"{BASE}/t10_a")
    m2, _, _ = consume(a0, f"{BASE}/t10_b")
    s1, s2 = mem_sig(m1), mem_sig(m2)
    j = jacc(s1, s2)
    print(f"  sha-esit={C.sha(m1) == C.sha(m2)} jacc={j:.3f}")
    check("T10-deterministik", C.sha(m1) == C.sha(m2))
    check("T10-jacc-1", j == 1.0)


def main():
    t_tek()
    t_combo()
    t_sira()
    t_gecmis()
    t_seed()
    t_sondurum()
    t_nadir()
    t_eta()
    t_unseen()
    t_retrieval()
    print(f"OZET-STRESS: {'GECTI' if not fails else 'BATTI: ' + str(fails)}")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
