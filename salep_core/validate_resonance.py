"""Monte Carlo v2: per-tick sizintili entegrator + ISI kapisi.
Revizyon gerekcesi: v1 darbe-arasi sizintiyi sabit 4 tick saydi; yavas
ritimde (p=16) gercek sizinti daha buyuk. Bu surum her tick sizinti
uygular ve ates kontrolu her tick yapar.

KALIBRE SONUC (2026-09-07): PULSE=0.6 yavas bantta (p=16) hic ates
uretemedi (sizinti birikimi onluyor). PULSE=0.8 ile 4 bant da kendi
fazasinda atesliyor ve capraz sizinti sifir (donemler arasi fark >=4,
BW=2). Karar: PERIODS=[4,8,12,16], BW=2, PULSE=0.8 C++ tarafina gomuldu.
"""
import numpy as np

PERIODS = [4, 8, 12, 16]
WINDOWS = [(50, 120), (150, 220), (250, 320), (350, 420)]
CYCLE = 500
N_CYCLES = 20
LEAK = 0.06
THR = 1.0
PULSE = 0.8


def mu(isi, tau, bw):
    if tau <= 0 or bw <= 0:
        return 1.0
    if isi is None or isi < 0:
        return 1.0
    return max(0.0, 1.0 - abs(isi - tau) / bw)


def run_neuron(tau, bw, leak=LEAK, pulse=PULSE):
    fires = np.zeros(4, dtype=int)
    v = 0.0
    last_pulse = None
    for cyc in range(N_CYCLES):
        base = cyc * CYCLE
        pulse_set = set()
        for wi, (a, b) in enumerate(WINDOWS):
            p = PERIODS[wi]
            t = a
            while t <= b:
                pulse_set.add(t)
                t += p
        for t in range(CYCLE):
            if t in pulse_set:
                isi = (base + t) - last_pulse if last_pulse is not None else None
                v += pulse * mu(isi, tau, bw)
                last_pulse = base + t
            v -= leak * v
            if v > THR:
                for wi, (a, b) in enumerate(WINDOWS):
                    if a <= t <= b + 30:
                        fires[wi] += 1
                        break
                v = -0.2
    return fires


if __name__ == "__main__":
    for bw in [1, 2, 3]:
        print(f"=== BW={bw} PULSE={PULSE} LEAK={LEAK} ===")
        mat = []
        for i, tau in enumerate(PERIODS):
            f = run_neuron(tau, bw)
            mat.append(f)
            tot = f.sum()
            own = f[i] / tot if tot else 0
            rival = np.delete(f, i).max() if tot else 0
            ratio = f[i] / rival if rival else float("inf")
            print(f"tau={tau:2d}: {f} tot={tot} own%={own:.2f} oran={ratio:.2f}")
        print()
    # nabiz siddet taramasi: yavas bant atesleyebiliyor mu?
    print("=== PULSE taramasi (tau=16, kendi fazi p=16) ===")
    for p in [0.6, 0.8, 1.0]:
        f = run_neuron(16, 2, pulse=p)
        print(f"PULSE={p}: {f}")
    print("=== LEAK taramasi (tau=16, PULSE=0.8) ===")
    for lk in [0.06, 0.04, 0.02]:
        f = run_neuron(16, 2, leak=lk, pulse=0.8)
        print(f"LEAK={lk}: {f}")
