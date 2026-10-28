"""Asama A kosucusu (PATTERN_MEMORY_USE_SPEC.md).

Audit (tum memler) -> memory_column_audit.csv; readout tablosu
(S0..S3+E1+E2+X1+X2) -> memory_readouts.csv. Cikti stress_out_v2/.
Cekirdek/frozen/encoder/C++ DEGISTIRILMEZ. phase0_margin.py ve
readout_v3d.py DEGISTIRILMEZ (sha kayda gecer).
"""
import csv
import glob
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "pattern"))
import readout_v3d as R  # noqa: E402
import memory_readouts as M  # noqa: E402

BASE = "/tmp/pstress_d"
OUT2 = os.path.join(ROOT, "stress_out_v2")
G1CASES = ["g1_base", "g1_irrig", "g1_fert", "g1_soil", "g1_hot",
           "g1_drought"]
fails = []


def check(name, cond, extra=""):
    print(f"  {'OK' if cond else 'BATTI'} {name} {extra}", flush=True)
    if not cond:
        fails.append(name)


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def mem_of(case):
    return f"{BASE}/{case}_c/mem.csv"


def sigs(case, ro, path=None):
    tv, by = R.load_mem(mem_of(case))
    if ro in R.READOUTS:
        return R.READOUTS[ro](tv, by)
    return M.MEMREADOUTS[ro](tv, by, path or mem_of(case))


def audit():
    rows = []
    for mp in sorted(glob.glob(f"{BASE}/*_c/mem.csv")):
        tag = os.path.basename(os.path.dirname(mp))[:-2]
        a = M.column_audit(mp)
        a["case"] = tag
        rows.append(a)
    with open(os.path.join(OUT2, "memory_column_audit.csv"), "w",
              newline="") as f:
        w = csv.DictWriter(f, fieldnames=["case", "rows"] +
                           M.AUDIT_COLS + ["eff_min", "eff_max"])
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in
                        ["case", "rows"] + M.AUDIT_COLS +
                        ["eff_min", "eff_max"]})
    n_const = sum(1 for r in rows if r["rows"] > 0 and all(
        r[c] == 1 for c in M.AUDIT_COLS if c != "eff_g"))
    print(f"  audit: {len(rows)} case, 8-sabit-dolu={n_const}")
    return rows


def x2_loo(pools_s3, pools_e1):
    """pools_*: [(sig, label)]. LOO iki-asamali karar. Donus: (acc, n)."""
    allw3, allw1 = [], []
    for i, (sig, lab) in enumerate(pools_s3):
        allw3 += [(w, lab) for w in R.wins_from_sig(sig, lab, i * 100000)]
    for i, (sig, lab) in enumerate(pools_e1):
        allw1 += [(w, lab) for w in R.wins_from_sig(sig, lab, i * 100000)]
    ok = tot = 0
    e1_by_sl = {}
    for (e, l) in allw1:
        e1_by_sl.setdefault((e["s"], l), []).append(e)
    for idx, (q3, lab) in enumerate(allw3):
        qel = e1_by_sl.get((q3["s"], lab), [None])[0]
        if qel is None:
            continue
        qe = qel
        cand3 = [(w, l) for (w, l) in allw3 if not (
            w["s"] == q3["s"] and l == lab)]
        cand3 = [x for x in cand3 if
                 x[0]["s"] + 3 <= q3["s"] or q3["s"] + 3 <= x[0]["s"]]
        if not cand3:
            continue
        scored = sorted(
            ((R.seq_sim(q3["seq"], w["seq"]), w, l) for w, l in cand3),
            key=lambda t: -t[0])
        top = {l for _, _, l in scored[:3]}
        beste, bse = None, -1.0
        for (e, l) in allw1:
            if l not in top or (e["s"] == qe["s"] and l == lab):
                continue
            if not (e["s"] + 3 <= qe["s"] or qe["s"] + 3 <= e["s"]):
                continue
            v = R.seq_sim(qe["seq"], e["seq"])
            if v > bse:
                beste, bse = l, v
        tot += 1
        if beste == lab:
            ok += 1
    return (round(ok / tot, 4), tot) if tot else (-1.0, 0)


def table():
    qd_tv, qd_by = R.load_mem(mem_of("g11_qd47"))
    qd_e1 = M.sig_E1(qd_tv, qd_by, mem_of("g11_qd47"))
    rows = {}
    for ro in ["S0", "S1", "S2a", "S2b", "S3", "E1", "E2", "X1"]:
        tv0, by0 = R.load_mem(mem_of("g1_base"))
        tvc, byc = R.load_mem(mem_of("g1_base") + ".chk")
        if ro in R.READOUTS:
            f = R.READOUTS[ro]
            s0 = f(tv0, by0)
            sc = f(tvc, byc)
            sm = {c: sigs(c, ro) for c in
                  ["g8_42", "g8_43", "g8_44"]}
            sg = {c: sigs(c, ro) for c in G1CASES}
        else:
            p0, pc = mem_of("g1_base"), mem_of("g1_base") + ".chk"
            t0, b0 = R.load_mem(p0)
            tc, bc = R.load_mem(pc)
            s0 = M.MEMREADOUTS[ro](t0, b0, p0)
            sc = M.MEMREADOUTS[ro](tc, bc, pc)
            sm = {}
            for c in ["g8_42", "g8_43", "g8_44"]:
                t, b = R.load_mem(mem_of(c))
                sm[c] = M.MEMREADOUTS[ro](t, b, mem_of(c))
            sg = {}
            for c in G1CASES:
                t, b = R.load_mem(mem_of(c))
                sg[c] = M.MEMREADOUTS[ro](t, b, mem_of(c))
        t = R.day_jacc(s0, sc)
        ks = ["g8_42", "g8_43", "g8_44"]
        n = round((R.day_jacc(sm[ks[0]], sm[ks[1]]) +
                   R.day_jacc(sm[ks[0]], sm[ks[2]]) +
                   R.day_jacc(sm[ks[1]], sm[ks[2]])) / 3, 4)
        prs = []
        for i in range(len(G1CASES)):
            for j in range(i + 1, len(G1CASES)):
                prs.append(R.day_jacc(sg[G1CASES[i]], sg[G1CASES[j]]))
        b = round(sum(prs) / len(prs), 4)
        acc, nn = R.ret_acc([(sg[c], c.split("g1_")[1]) for c in G1CASES])
        rq = []
        for c in ["g1_base", "g1_drought", "g1_irrig"]:
            tvq, byq = R.load_mem(mem_of(c))
            if ro in R.READOUTS:
                rq.append((R.READOUTS[ro](tvq, byq), c.split("g1_")[1]))
            else:
                rq.append((M.MEMREADOUTS[ro](tvq, byq, mem_of(c)),
                           c.split("g1_")[1]))
        if ro in R.READOUTS:
            qq = R.READOUTS[ro](qd_tv, qd_by)
        else:
            qq = M.MEMREADOUTS[ro](qd_tv, qd_by, mem_of("g11_qd47"))
        fam = R.fam_agree(rq, [(qq, "drought", "qd47")])
        # NOT: sorgu+ref AYNi uzayda (F1 semasi); karsilastirilabilir.
        ns = len({s for s in s0.values() if s})
        rows[ro] = {"T": t, "N": n, "B": b, "margin": round(t - b, 4),
                    "ret_acc": acc, "ret_n": nn,
                    "fam_qd": fam["qd47"], "N_sig": ns}
        print(f"  {ro}: T={t} N={n} B={b} margin={round(t - b, 4)} "
              f"ret={acc}(n={nn}) qd={fam['qd47']} Nsig={ns}", flush=True)
    # X2: karar-duzeyi (T/N/B/Nsig X1-uzayindan).
    tv0, by0 = R.load_mem(mem_of("g1_base"))
    p0 = mem_of("g1_base")
    x1 = M.sig_X1(tv0, by0, p0)
    r3 = [(sigs(c, "S3"), c.split("g1_")[1]) for c in
          ["g1_base", "g1_drought", "g1_irrig"]]
    re1 = []
    for c in ["g1_base", "g1_drought", "g1_irrig"]:
        t, b = R.load_mem(mem_of(c))
        re1.append((M.sig_E1(t, b, mem_of(c)), c.split("g1_")[1]))
    q3 = R.READOUTS["S3"](qd_tv, qd_by)
    votes = {"qd47": M.x2_query(q3, qd_e1, r3, re1)}
    # X2 ret: G1 uclusu uzerinde LOO.
    r3g = [(sigs(c, "S3"), c.split("g1_")[1]) for c in G1CASES]
    r1g = []
    for c in G1CASES:
        t, b = R.load_mem(mem_of(c))
        r1g.append((M.sig_E1(t, b, mem_of(c)), c.split("g1_")[1]))
    acc2, n2 = x2_loo(r3g, r1g)
    rows["X2"] = {"T": rows["X1"]["T"], "N": rows["X1"]["N"],
                  "B": rows["X1"]["B"],
                  "margin": rows["X1"]["margin"], "ret_acc": acc2,
                  "ret_n": n2,
                  "fam_qd": 1.0 if votes["qd47"] == "drought" else 0.0,
                  "N_sig": rows["X1"]["N_sig"]}
    print(f"  X2: ret={acc2}(n={n2}) qd={rows['X2']['fam_qd']} "
          f"(T/N/B X1-uzayi)", flush=True)
    return rows


def main():
    os.makedirs(OUT2, exist_ok=True)
    print("A1 audit:")
    audit()
    print("A2 tablo:")
    rows = table()
    with open(os.path.join(OUT2, "memory_readouts.csv"), "w",
              newline="") as f:
        import csv as _c
        w = _c.DictWriter(f, fieldnames=["ro", "T", "N", "B", "margin",
                                         "ret_acc", "ret_n", "fam_qd",
                                         "N_sig"])
        w.writeheader()
        for ro, d in rows.items():
            w.writerow({"ro": ro, **d})
    print("A3 regresyon kilidi (degisiklik YOK beklentisi):")
    for p in [os.path.join(ROOT, "pattern", "readout_v3d.py"),
              os.path.join(ROOT, "phase0_margin.py")]:
        print(f"  sha {os.path.basename(p)}={sha(p)[:12]}")
    win = [ro for ro, d in rows.items()
           if d["fam_qd"] >= 0.40 and d["margin"] > 0 and d["B"] < d["N"]
           and d["ret_acc"] >= 0.2301]
    print(f"OZET-MEMREAD: kazanan={win if win else 'YOK'}")
    check("A-kapi", bool(win), str(win))
    with open(os.path.join(OUT2, "memory_readouts.json"), "w") as f:
        json.dump(rows, f, default=str)
    raise SystemExit(0)


if __name__ == "__main__":
    main()
