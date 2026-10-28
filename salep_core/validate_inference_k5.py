"""Inference karsilastirma k=3/k=5 (§9.69).

Baseline-1 (validate_inference.py) DONDURULDU — bu dosya onu import
eder, degistirmez; yalniz K=5 ile ayni aptal inference'i calistirir.
Matris karsilastirmasi icin k=3 ciktisi dondurulmus dosyadan alinir.
Model/harness'e DOKUNULMAZ.
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import validate_inference as B  # noqa: E402 (dondurulmus baseline)


def main():
    d = B.load()
    B.K = 5
    wins = B.build(d["events"])
    cm, viol = B.infer(wins)
    acc = B.show(cm, "Baseline-1 k=5 (ayni aptal yontem):")
    print(f"sorgu: {len(wins)} pencere; sizinti-ihlali: {viol}")
    assert viol == 0, "sizinti!"
    print(f"OZET-INFER-K5: acc={acc:.3f} n={len(wins)}")


if __name__ == "__main__":
    main()
