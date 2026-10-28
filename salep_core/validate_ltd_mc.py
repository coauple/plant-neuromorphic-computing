"""§9.80-oncesi — LTD rejim haritasi MC'si (§0 geregi).

Formul (analiz-disi, cekirdek DEGISMEZ):
  dw = eta*S(w)*[G*Q - gama*D], D = q*(1-p)
  (co-fire -> LTP; post-alone -> LTD; pre-alone -> 0)
Ikilat denemeler: LTP_olay = 4/27000, LTD_olay = -gama/30
(orani: |LTD|/LTP = 22.5*gama).

MC: (c, a) hucresi = co-fire olasiligi c, post-alone olasiligi a;
T=2000 deneme, w0=0, S-tavan + 0-taban. Izgara c,a x {0.05,0.2,0.5},
gama merdiveni {0,0.04,0.1,0.2,0.5,1,2,4}.
Olcu: final-w yuzeyi, sifir-cokus payi, gama=0-siralama korelasyonu,
hucreler-arasi yayilim. Amac: weak/medium/strong rejimlerini
VERIDEN okumak (rastgele katsayi YOK).
"""
import itertools
import random

ETA = 0.2
RATE = 30.0
W_MAX = 2.0
T = 2000
LTP = (1.0 / RATE) * (4.0 / RATE ** 2)
LTD1 = 1.0 / RATE
CS = (0.05, 0.2, 0.5)
GAMS = (0.0, 0.005, 0.01, 0.02, 0.04, 0.08)
SEED = 5


def run_cell(c, a, gam, rng):
    w = 0.0
    for _ in range(T):
        u = rng.random()
        s = 1.0 - (w / W_MAX) ** 2
        if u < c:
            w += ETA * LTP * s
        elif u < c + a:
            w -= ETA * gam * LTD1 * s
        if w < 0:
            w = 0.0
        elif w > W_MAX:
            w = W_MAX
    return w


def main():
    cells = list(itertools.product(CS, CS))
    table = {}
    for gam in GAMS:
        rng = random.Random(SEED)
        ws = [run_cell(c, a, gam, rng) for c, a in cells]
        table[gam] = ws
    base = table[0.0]
    print("c,a      " + " ".join(f"g={g:<4g}" for g in GAMS))
    for i, (c, a) in enumerate(cells):
        print(f"({c:.2f},{a:.2f})  " + " ".join(
            f"{table[g][i]:6.3f}" for g in GAMS))
    # Sifir-cokus payi + sira-korelasyonu + yayilim.
    import math
    print("\ngama | cokus | rank-kor | yayilim(std)")
    order0 = sorted(range(len(cells)), key=lambda i: base[i])
    for gam in GAMS:
        ws = table[gam]
        col = sum(1 for v in ws if v == 0.0) / len(ws)
        order = sorted(range(len(cells)), key=lambda i: ws[i])
        # Spearman (sira esitlikleri kirilmadan, basit).
        rk = {v: r for r, v in enumerate(order)}
        rk0 = {v: r for r, v in enumerate(order0)}
        n = len(cells)
        mx = sum(rk.values()) / n
        m0 = sum(rk0.values()) / n
        cov = sum((rk[i] - mx) * (rk0[i] - m0) for i in range(n))
        v1 = sum((rk[i] - mx) ** 2 for i in range(n))
        v0 = sum((rk0[i] - m0) ** 2 for i in range(n))
        rho = cov / math.sqrt(v1 * v0) if v1 and v0 else 1.0
        mean = sum(ws) / n
        std = math.sqrt(sum((v - mean) ** 2 for v in ws) / n)
        print(f"{gam:<5g} | {col:.2f}  | {rho:+.3f}   | {std:.3f}")


if __name__ == "__main__":
    main()
