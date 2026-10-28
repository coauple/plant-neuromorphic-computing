"""Inference on Pattern Memory (b3 giris bileti) — Faz 4+.

Ayni protokol (validate_inference.py birebir):
  TEST B gunleri, 175 aday pencere, k=3, nearest-sequence, sizinti-denetimi,
  ground-truth YALNIZ degerlendirme. Tek fark: gun imzasi afferent olaylardan
  degil v2 Pattern Memory kayitlarindan (o gun atesleyen P3 birimleri kumesi).
  similarity() AYNI fonksiyon (sim.assoc); blines/a bos-kume oldugundan tum
  ciftere sabit +0.5 eklenir — siralama degismez, yani esdeger saf birim-Jaccard.
Kollar: ogrenen (eta 0.30, birincil) + frozen (eta 0, referans). Dogruluk
kapisi YOK (A/B/C bulgusu); kapilar: determinizm + sizintisizlik.
"""
import csv
import os
import subprocess
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from validate_sensory_repr import WINDOWS  # noqa: E402
from sim.assoc import similarity  # noqa: E402

EXE = os.path.join(ROOT, "npu_pattern_unit_v2")
AFF = os.path.join(ROOT, "testb_afferent.csv")
K = 3
ORDER = ["normal", "kurak", "siddetli", "sulama", "recovery", "yaz"]
SHORT = {"normal": "N", "kurak": "D", "siddetli": "S", "sulama": "I",
         "recovery": "R", "yaz": "Y"}


def run_mem(eta, tag):
    mem_p, log_p = f"/tmp/inf_{tag}_mem.csv", f"/tmp/inf_{tag}_log.csv"
    p = subprocess.run([EXE, "--aff", AFF, "--mem", mem_p, "--log", log_p,
                        "--eta", eta], cwd=ROOT, capture_output=True,
                       text=True, timeout=600)
    assert p.returncode == 0, p.stderr[-500:]
    return mem_p


def day_sig(mem_rows):
    by_day = {}
    for r in mem_rows:
        by_day.setdefault(int(r["tick"]) // 50, set()).add(int(r["unit"]))
    return by_day


def build(by_day):
    wins = []
    for a, b, nm in WINDOWS:
        for s in range(a, b - K + 1):
            seq = tuple({"posts": by_day.get(x, set()), "blines": set(),
                         "a": set()} for x in range(s, s + K))
            if not any(sg["posts"] for sg in seq):
                continue
            wins.append({"s": s, "seq": seq, "label": nm})
    return wins


def seq_sim(a, b):
    return sum(similarity(x, y) for x, y in zip(a, b)) / len(a)


def infer(wins):
    cm, viol = Counter(), 0
    for i, w in enumerate(wins):
        best, bs = None, -1.0
        for j, o in enumerate(wins):
            if i == j:
                continue
            if not (o["s"] + K <= w["s"] or w["s"] + K <= o["s"]):
                continue
            v = seq_sim(w["seq"], o["seq"])
            if v > bs:
                best, bs = o["label"], v
        if best is None:
            viol += 1
            continue
        cm[(w["label"], best)] += 1
    return cm, viol


def show(cm, title):
    print(title)
    print("        " + " ".join(f"{SHORT[c]:>4s}" for c in ORDER))
    tot = ok = 0
    for t in ORDER:
        row = [cm.get((t, p), 0) for p in ORDER]
        tot += sum(row)
        ok += cm.get((t, t), 0)
        print(f"akt {SHORT[t]} | " + " ".join(f"{v:4d}" for v in row))
    print(f"dogruluk: {ok}/{tot} = {ok / tot:.3f}")
    return ok / tot, tot


def arm(tag, eta):
    mem_p = run_mem(eta, tag)
    with open(mem_p) as f:
        rows = list(csv.DictReader(f))
    wins = build(day_sig(rows))
    cm, viol = infer(wins)
    acc, n = show(cm, f"Pattern-Memory inference [{tag}] (k={K}):")
    cm2, _ = infer(build(day_sig(rows)))
    chk = [("deterministik", cm == cm2), ("sizintisiz", viol == 0)]
    bad = [x for x, v in chk if not v]
    for x, v in chk:
        print(f"  {'OK' if v else 'BATTI'} {x}")
    if bad:
        raise SystemExit(f"BATTI: {bad}")
    return acc, n


def main():
    acc_l, n_l = arm("ogrenen", "0.30")
    acc_f, n_f = arm("frozen", "0")
    print(f"OZET-INFER-P3: ogrenen={acc_l:.3f}(n={n_l}) "
          f"frozen={acc_f:.3f}(n={n_f}) sensory-ref=0.554(n=175)")


if __name__ == "__main__":
    main()
