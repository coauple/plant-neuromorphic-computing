"""Monte Carlo: causality (nedensellik) deneyi kalibrasyonu (anayasa Madde 0).

C++ dinamiginin basit float ikizi: sizintili entegrator + ISI kapisi (pre),
cift-dal + coincidence bonusu (target), kuadratik G.Q.S (RATE_WINDOW=30).

Amac: PULSE, w0, ETA, aktif pencere, super-dongu sayisini koda gommeden
once dogrulamak. Cikti: kalibre sabitler + beklenen F1/F2/F3 + dw oranlari.

KALIBRE SONUC (2026-09-07, 2 super-dongu taramasi):
- PULSE 0.8 vs 1.0 ayni (kapidan gecen bantta doygun) -> 0.8.
- w0 yuksekse tek kanal da atesler, oran duser (w0=1.0 -> 1.19x).
- w0=0.3 + hedef sizinti yuksek = tam deadlock (F3=0) -> kac.
- SECIM: PULSE=0.8, w0=0.5, ETA=0.2, hedef leak=0.04 ->
  F1=6 F2=0 F3=12, oran=2.00x, C1=C2=0 C3>>0, s0/s2 buyur s1/s3 donuk.
- C++ TURU: w0=0.5 ile ilk C++ kosusu 1.88x verdi (F1=64, F3=120);
  MC orani kucuk-sayi iyimserligiymis. w0=0.4 -> C++ 2.11x (F1=44,
  F3=93), ogrenme canli (s0 +0.366, s2 +0.081). Nihai: w0=0.4.
- F2 tek basina hedefi atesletemiyor -> (B) orani yerine mutlak
  blok-kazanc karsilastirmasi (Faz3 kazanci > F1+F2).
- N_SUPER=20 (30.000 tick).
"""
import itertools
import numpy as np

TAUS = [4, 8, 12, 16]
BW = 2
WIN = 10          # COINCIDENCE_WINDOW_MS
BONUS = 0.8
RATE_WINDOW = 30
W_MAX = 2.0

# Faz bloklari: (ad, aktif_bas, aktif_bit, P0_periyot, P2_periyot)
# None = o pre'ye uyaran yok. Faz1/2 ortak hat (tek ritim); Faz3 pre-bazli.
PHASES = [
    ("F1", 40, 180, 4, None),
    ("F2", 40, 220, None, 12),
    ("F3", 40, 220, 4, 12),
]
BLOCK = 500


def mu(isi, tau, bw):
    if tau <= 0 or bw <= 0:
        return 1.0
    if isi is None:
        return 1.0
    return max(0.0, 1.0 - abs(isi - tau) / bw)


class Pre:
    def __init__(self, tau, leak):
        self.tau = tau
        self.leak = leak
        self.v = 0.0
        self.last = None
        self.fires = []

    def pulse(self, t, amp):
        isi = t - self.last if self.last is not None else None
        self.v += amp * mu(isi, self.tau, BW)
        self.last = t

    def tick(self, t):
        self.v -= self.leak * self.v
        if self.v > 1.0:
            self.v = -0.2
            self.fires.append(t)
            return True
        return False


class Target:
    def __init__(self, leak):
        self.leak = leak
        self.a = 0.0
        self.b = 0.0
        self.root = 0.0
        self.g = 0.0
        self.last_a = -10**9
        self.last_b = -10**9
        self.fires = []
        self.coinc_ticks = 0

    def inject(self, branch, t, cur):
        if branch == "a":
            self.a += cur
            self.last_a = t
        else:
            self.b += cur
            self.last_b = t

    def tick(self, t):
        # difuzyon kok<->dallar (%15)
        self.root += 0.15 * (self.a - self.root) + 0.15 * (self.b - self.root)
        self.a -= 0.15 * (self.a - self.root)
        self.b -= 0.15 * (self.b - self.root)
        for k in ("a", "b", "root"):
            v = getattr(self, k)
            setattr(self, k, v - self.leak * v)
        if self.root > 0.15:
            self.g += 0.2
        self.g -= 0.005 * self.g
        coinc = (t - self.last_a <= WIN) and (t - self.last_b <= WIN)
        if coinc:
            self.coinc_ticks += 1
        soma = self.root * (1.0 + self.g + (BONUS if coinc else 0.0))
        if soma > 1.0:
            self.a = self.b = self.root = -0.2
            self.fires.append(t)
            return True
        return False


def G(p, q):
    return min(p, q) / RATE_WINDOW


def Q(p, q):
    return ((p + q) / RATE_WINDOW) ** 2


def S(w):
    return max(0.0, 1.0 - (w / W_MAX) ** 2)


def run(pulse, w0, eta, n_super, leaks=(0.06, 0.06, 0.02, 0.02),
        target_leak=0.02):
    pres = [Pre(TAUS[i], leaks[i]) for i in range(4)]
    tgt = Target(target_leak)
    w = [w0] * 4
    # hedef dallar: s0,s1 -> A ; s2,s3 -> B
    tgt_branch = ["a", "a", "b", "b"]
    hist_pre = [[0] * RATE_WINDOW for _ in range(4)]
    hist_post = [0] * RATE_WINDOW
    head = 0
    dw_sum = {0: [0.0, 0.0, 0.0], 1: [0.0, 0.0, 0.0], 2: [0.0, 0.0, 0.0]}
    fires = {0: 0, 1: 0, 2: 0}
    coinc = {0: 0, 1: 0, 2: 0}
    pre_fires = {0: [0] * 4, 1: [0] * 4, 2: [0] * 4}
    t = 0
    for _ in range(n_super):
        for ph, (name, a0, a1, p0, p2) in enumerate(PHASES):
            c0 = tgt.coinc_ticks
            for bt in range(BLOCK):
                # uyaran: Faz1/2 ortak hat tek ritim; Faz3 pre-bazli
                stim = {}
                if p0 is not None and a0 <= bt <= a1 and \
                        (bt - a0) % p0 == 0:
                    stim[0] = pulse
                if p2 is not None and a0 <= bt <= a1 and \
                        (bt - a0) % p2 == 0:
                    stim[2] = pulse
                for i, amp in stim.items():
                    pres[i].pulse(t, amp)
                fired = [pr.tick(t) for pr in pres]
                for i, f in enumerate(fired):
                    if f:
                        tgt.inject(tgt_branch[i], t, w[i] * 0.5)
                        pre_fires[ph][i] += 1
                tf = tgt.tick(t)
                if tf:
                    fires[ph] += 1
                # ogrenme (odak: s0 ve s2; s1/s3 negatif kontrol)
                for i in range(4):
                    hist_pre[i][head] = 1 if fired[i] else 0
                hist_post[head] = 1 if tf else 0
                head = (head + 1) % RATE_WINDOW
                rp = [sum(h) for h in hist_pre]
                rq = sum(hist_post)
                for i in range(4):
                    dw = eta * G(rp[i], rq) * Q(rp[i], rq) * S(w[i])
                    if i == 0:
                        dw_sum[ph][0] += dw
                    elif i == 2:
                        dw_sum[ph][2] += dw
                    w[i] = min(W_MAX, w[i] + dw)
                t += 1
            coinc[ph] += tgt.coinc_ticks - c0
    return {"fires": fires, "coinc": coinc, "dw": dw_sum, "w": w,
            "pre": pre_fires}


if __name__ == "__main__":
    print("=== tarama (2 super-dongu, hizli on eleme) ===")
    for pulse, w0 in itertools.product([0.8, 1.0], [0.5, 1.0, 1.5]):
        r = run(pulse, w0, 0.2, 2)
        f = r["fires"]
        base = f[0] + f[1]
        ratio = f[2] / base if base else float("inf")
        print(f"PULSE={pulse} w0={w0}: F1={f[0]} F2={f[1]} F3={f[2]} "
              f"F3/(F1+F2)={ratio:.2f} coinc={r['coinc']} "
              f"w={[round(x, 4) for x in r['w']]}")
    print("\n=== secilen nokta dogrulama (w0=0.5, hedef leak=0.04) ===")
    r = run(0.8, 0.5, 0.2, 2, target_leak=0.04)
    f = r["fires"]
    print(f"F1={f[0]} F2={f[1]} F3={f[2]} oran={f[2] / (f[0] + f[1]):.2f} "
          f"coinc={r['coinc']} w={[round(x, 4) for x in r['w']]} "
          f"pre={r['pre']}")
