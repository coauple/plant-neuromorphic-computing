"""Sessizlik-maskeli similarity probu (§9.70) — baseline'dan AYRI.

Suphe (§9.68): hizali-ortalama benzerlikte iki pencerenin de sessiz
oldugu gunler (bos-bos = 1.0) ayirt-edici bilgiyi seyreltir; kurak
pencereler bu yuzden normal'e emiliyor olabilir.

Prob: benzerlik yalniz EN AZ BIRI atesli gunler uzerinden
ortalanir (ikisi de sessizse pozisyon yok sayilir; tum pozisyon
sessizse benzerlik 0). k=3, 6 sinif, sizintisiz LOO. Baseline
dosyasina DOKUNULMAZ (build yeniden kullanilir, infer burada).
Sonuclar baseline'dan ayri tutulur (bu dosyanin ciktisi).
"""
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import validate_inference as B  # noqa: E402 (dondurulmus baseline)
from sim.assoc import similarity  # noqa: E402


def masked_sim(a, b):
    vals = [similarity(x, y) for x, y in zip(a, b)
            if x["posts"] or y["posts"]]
    return sum(vals) / len(vals) if vals else 0.0


def infer_masked(wins):
    k = 3
    cm, viol = Counter(), 0
    for i, w in enumerate(wins):
        best, bs = None, -1.0
        for j, o in enumerate(wins):
            if i == j:
                continue
            if not (o["s"] + k <= w["s"] or w["s"] + k <= o["s"]):
                continue
            v = masked_sim(w["seq"], o["seq"])
            if v > bs:
                best, bs = o["label"], v
        if best is None:
            viol += 1
            continue
        cm[(w["label"], best)] += 1
    return cm, viol


def main():
    d = B.load()
    wins = B.build(d["events"])  # k=3, dondurulmus build
    cm, viol = infer_masked(wins)
    acc = B.show(cm, "Sessizlik-maskeli prob (k=3, baseline-disi):")
    kd = cm.get(("kurak", "normal"), 0)
    kt = sum(v for (t, _), v in cm.items() if t == "kurak")
    print(f"kurak->normal (maskeli): {kd}/{kt} = {kd / kt:.3f} "
          f"[baseline: 28/28 = 1.000]")
    print(f"dogruluk (maskeli): {acc:.3f} [baseline: 0.554]")
    assert viol == 0, "sizinti!"
    print("OZET-SILMASK: " + f"acc={acc:.3f} kurak-normal={kd}/{kt}")


if __name__ == "__main__":
    main()
