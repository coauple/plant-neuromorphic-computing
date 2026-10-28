"""Inference on v3 Pattern Memory — baglanti probu (Faz 4+).

En son Pattern Lobe (npu_pattern_unit_v3, F1 projeksiyon) ciktisini
sistemin inference tuketicisine baglar: TEST-B kablosu -> v3 -> memory
-> nearest-sequence retrieval. Protokol validate_infer_pattern.py ile
birebir (175 aday pencere, k=3, sizinti-denetimi, ground-truth YALNIZ
degerlendirme); day_sig/build/infer aynen yeniden kullanilir.
Kollar: ogrenen (eta 0.30, birincil) + frozen (eta 0, referans).
Dogruluk kapisi YOK (v2 probu ile ayni gerekce); kapilar: binary
determinizmi (cift-kosu sha) + inference determinizmi + sizintisizlik.
ADDITIVE-ONLY: validate_infer_pattern.py DEGISTIRILMEDI.
"""
import csv
import hashlib
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from validate_infer_pattern import build, day_sig, infer, show  # noqa: E402

EXE = os.path.join(ROOT, "npu_pattern_unit_v3")
AFF = os.path.join(ROOT, "testb_afferent.csv")
K = 3


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def run_mem(eta, tag):
    mem_p, log_p = f"/tmp/inf3_{tag}_mem.csv", f"/tmp/inf3_{tag}_log.csv"
    cmd = [EXE, "--aff", AFF, "--mem", mem_p, "--log", log_p,
           "--eta", eta]
    for run in (1, 2):
        mp = mem_p if run == 1 else mem_p + ".chk"
        lp = log_p if run == 1 else log_p + ".chk"
        c = [x.replace(mem_p, mp).replace(log_p, lp) for x in cmd]
        p = subprocess.run(c, cwd=ROOT, capture_output=True, text=True,
                           timeout=600)
        assert p.returncode == 0, p.stderr[-500:]
    det = sha(mem_p) == sha(mem_p + ".chk")
    return mem_p, det


def arm(tag, eta):
    mem_p, det = run_mem(eta, tag)
    with open(mem_p) as f:
        rows = list(csv.DictReader(f))
    wins = build(day_sig(rows))
    cm, viol = infer(wins)
    acc, n = show(cm, f"v3 Pattern-Memory inference [{tag}] (k={K}):")
    cm2, _ = infer(build(day_sig(rows)))
    chk = [("binary-deterministik", det),
           ("deterministik", cm == cm2),
           ("sizintisiz", viol == 0)]
    bad = [x for x, v in chk if not v]
    for x, v in chk:
        print(f"  {'OK' if v else 'BATTI'} {x}")
    if bad:
        raise SystemExit(f"BATTI: {bad}")
    return acc, n


def main():
    acc_l, n_l = arm("ogrenen", "0.30")
    acc_f, n_f = arm("frozen", "0")
    print(f"OZET-INFER-P3V3: ogrenen={acc_l:.3f}(n={n_l}) "
          f"frozen={acc_f:.3f}(n={n_f}) sensory-ref=0.554(n=175)")


if __name__ == "__main__":
    main()
