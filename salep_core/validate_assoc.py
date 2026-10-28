"""Association cekirdek dogrulama (§9.62): oruntu ayirimi (ogrenmesiz).

A = aktif durum surekliligi, B/P2 = baglam/kosul kimligi;
association = zaman-iliski (gun-penceresi imzasi + agirlikli Jaccard +
LOO 1-NN). Persistence/FDM'ye DOKUNULMAZ.

Her karar geriye-izlenebilir: komsu gunun A-B-P2 olaylari loglanir.

Calistirma: .venv/bin/python validate_assoc.py
Olcutler (S1-S4): genel dogruluk, sinif-recall, determinizm, iz raporu.
"""
import csv
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)


def main():
    from sim.assoc import (build_windows, classify, backward_chain,
                           window_label)
    with open(os.path.join(ROOT, "testb_afferent.csv")) as f:
        recs = list(csv.DictReader(f))
    assert recs, "kablo bos"
    wins = build_windows(recs)
    days = sorted(wins)
    res = classify(days, wins)
    res2 = classify(days, wins)

    tot = len(res)
    ok = sum(1 for d in days if res[d][0] == res[d][3])
    acc = ok / tot
    per = {}
    for d in days:
        pred, nb, s, true = res[d]
        a, b = per.get(true, (0, 0))
        per[true] = (a + (pred == true), b + 1)
    print(f"association: {ok}/{tot} = {acc:.3f}")
    for k in ("true", "decoy", "mixed"):
        a, b = per.get(k, (0, 0))
        print(f"  {k}: {a}/{b} = {a / b:.3f}" if b else f"  {k}: yok")

    checks = []
    checks.append(("S1 genel_dogruluk", acc >= 0.95))
    checks.append(("S2 true_recall",
                   per["true"][0] / per["true"][1] >= 0.95))
    checks.append(("S3 mixed_recall",
                   per["mixed"][0] / per["mixed"][1] >= 0.90))
    checks.append(("S4 decoy_recall",
                   per["decoy"][0] / per["decoy"][1] >= 0.75))
    checks.append(("S5 deterministik",
                   all(res[d][0] == res2[d][0] for d in days)))
    bad = [k for k, v in checks if not v]
    for k, v in checks:
        print(f"  {'OK' if v else 'BATTI'} {k}")
    if bad:
        raise SystemExit(f"BATTI: {bad}")

    by_day = {}
    for r in recs:
        by_day.setdefault(int(r["tick"]) // 50, []).append(r)
    print("geriye-iz (sinif basina bir karar):")
    shown = set()
    for d in days:
        pred, nb, s, true = res[d]
        if true in shown:
            continue
        shown.add(true)
        print(f"  gun {d} [{true}] -> komsu gun {nb} [{res[nb][3]}] "
              f"benzerlik={s:.3f}")
        for line in backward_chain(nb, wins, by_day)[:6]:
            print(f"    {line}")
    print("OZET-ASSOC: " + " ".join(k for k, _ in checks))


if __name__ == "__main__":
    main()
