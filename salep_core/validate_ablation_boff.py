"""Deney A-kismi — B-off ablation (§9.73).

Soru: B-dali olmadan 3-5 gunluk davranis ortaya cikiyor mu?
Yontem: donuk binary'e AYNI TEST B girdileri + --b-off (hazir
bayrak, emsal §9.60; kod DEGISMEZ). Ciktilar ayri (boff_*).
Beklenti (§9.60): seyrek A-tek-basina atesleyemez -> P2 ~0 ->
imza/inference davranisi YOK. Sifir-P2 bir ariza degil, sonucun
kendisidir (BULGU disiplini).

Kapilar (A1-A2): harness basarisi + bitki-girdisi korunumu
(bitki darbe sayisi ham ile ayni mertebede).
"""
import csv
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

BOFF_COND = os.path.join(ROOT, "boff_conditions.csv")
BOFF_AFF = os.path.join(ROOT, "boff_afferent.csv")
BOFF_DIAG = "/tmp/boff_diag.csv"


def main():
    exe = os.path.join(ROOT, "npu_sensory_plant")
    p = subprocess.run(
        [exe, "--spikes", os.path.join(ROOT, "testb_spikes.csv"),
         "--sensors", os.path.join(ROOT, "testb_sensors.csv"),
         "--out", BOFF_COND, "--cond", "22", "--test", "3",
         "--b-off",
         "--diag", BOFF_DIAG, "--aff", BOFF_AFF],
        cwd=ROOT, capture_output=True, text=True, timeout=600)
    ok_run = p.returncode == 0
    if not ok_run:
        raise SystemExit(f"harness batti:\n{p.stderr[-2000:]}")
    p1 = (0, 0)
    for line in p.stdout.splitlines():
        if line.startswith("OZET-PLANT: p1darbesi="):
            toks = line.split()
            p1 = tuple(int(x) for x in toks[1].split("=")[1].split("/"))
    with open(BOFF_AFF) as f:
        evs = list(csv.DictReader(f))
    print(f"boff: P1 darbesi={p1}, P2 kayit={len(evs)}")
    if evs:
        print("BULGU: B kapaliyken P2 atesi VAR (beklenti disi) — "
              "dagilim asagida")
        from collections import Counter
        print("  " + str(dict(Counter(r["label"] for r in evs))))
    else:
        print("BULGU: B kapaliyken P2 davranisi YOK — 3-5 gunluk "
              "imza/inference davranisi ortaya cikmiyor (B gerekli)")
    chk = [("A1 harness-OK", ok_run),
           ("A2 bitki-girdisi-korunur", p1 == (1908, 46))]
    bad = [x for x, v in chk if not v]
    for x, v in chk:
        print(f"  {'OK' if v else 'BATTI'} {x}")
    if bad:
        raise SystemExit(f"BATTI: {bad}")
    print("OZET-ABL-BOFF: " + " ".join(x for x, _ in chk)
          + f" P2={len(evs)}")


if __name__ == "__main__":
    main()
