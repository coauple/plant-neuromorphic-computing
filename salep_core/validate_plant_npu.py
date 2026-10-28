"""Bitki NPU kalibrasyonu (anayasa Kural 0): Duyusal Lob + Kosul Lobu.

C++ neuron_tick / PLIR / kuadratik ogrenme kurallarinin float ikizi.
Hicbir sayi (S_b, w0, eta) C++'a gomulmeden once burada kesinlesir.

Model:
- Member: validate_fdm.py'den birebir (PLIR kapisi, Dal A + kok difuzyonu,
  bos Dal B yuku, gating, soma=root*(1+g)).
- ConditionNeuron: iki dalli post (A=faz girisi, B=sensor girisi),
  snapshot-then-apply difuzyon (kok once: A'dan sonra B'den; sonra dallar
  parent snapshot'tan) -> per-kompartman leak -> gating (V>0.15 ise +0.2;
  decay root 0.005 / A 0.004 / B 0.003) -> soma=root*(1+g+0.8*coinc) > 1.0
  -> ates, global reset -0.2. PLIR disi: post dallari kapisizdir.
- Ogrenme: dw = eta*G*Q*S, RATE_WINDOW=30, W_MAX=2.0, SCALE=0.5.

Topoloji:
  tel (4+12 + gurultu)
   |- bant-4 pop (8, PLIR) -- temsilci m=0 -- syn --> Post2 [SICAKLIK] B<-SIC (periyot 4)
   |- bant-12 pop (8, PLIR) -- temsilci m=0 -- syn --> Post0 [NEM] B<-NEM (periyot 12)
                                                        --> Post1 [EC]  B<-EC  (periyot 12, negatif kontrol)

Senaryo (Pavlov, tek oturum):
  Asama 1 KOSULLANMA: 10 x 500 tick, tel surekli, NEM=60 EC=40 SIC=75
  Asama 2 KOSUL TESTI: 3 x 500 tick, tel surekli, sensorler 0
Ogrenme tum oturum boyunca aktiftir.

Secim kriterleri (esikler veri gorulmeden sabitlendi):
  1. US->UR: kosullanmada Post0/Post2 ates > 0
  2. CS baslangicta etkisiz: sensorlu oncesi 500 tick'lik tel-yalniz
     probeda (w0 agirliklari, ogrenme dondurulmus) Post0/Post2 ates == 0
  3. Kosul kazanimi: KOSULLANMA sonu Post0/Post2 Delta-w >= +0.3
  4. Negatif kontrol: Post1 |Delta-w| < 0.02
  5. CR: TEST'te Post0/Post2 ates > 0; Post1 == 0

Tarama: S_b x w0 x eta (once 2 blok + 1 test ile hizli on eleme,
sonra secilen noktada tam kosu).

KALIBRE SONUC (2026-09-09, 24 kosu):
- SECIM: S_b=1.0, w0=0.2, eta=0.2 -> tam kosuda 5/5 kriter OK.
- Tam kosu: cond_ates=[415,0,1020] dw=[+1.5581,+0.0000,+1.8000]
  test_ates (CR)=[62,0,121] probe=[0,0,0].
- w0 notu: ilk grid {0.3,0.4} SIC probunda kaldi (4'luk bant temsilci
  ates sikligi yuksek -> w0>=0.3'te A tek basina atesletiyor); w0=0.2
  (~24 kosuluk grid) iki bandda da CS-etkisiz + guclu CR verdi.
  Esikler sabit kaldi, yalniz w0 grid'i genisletildi.
- SIC w W_MAX=2.0 tavanina ulasti (S(w) tavani calisiyor); MC yaklasik
  ongorudur, kesin dogrulayici C++ kosusudur.
"""

import itertools

import numpy as np

# --- cekirdek sabitleri (mevcut, miras) ---
WIN_COINC = 10
BONUS = 0.8
THR = 1.0
V_RESET = -0.2
DIFF = 0.15
RATE_WINDOW = 30
W_MAX = 2.0
SCALE = 0.5
BAND_LEAK = {4: (0.06, 0.08), 12: (0.015, 0.02)}
TAUS = [4, 12]
N_POP = 8
PULSE = 0.8
SENS_THRESH = 50

# --- secim esikleri (veri gorulmeden sabitlendi) ---
DW_GAIN_MIN = 0.3
DW_NEG_MAX = 0.02


def band_leak(tau):
    return BAND_LEAK[tau]


class Member:
    """validate_fdm.py Member ile birebir: PLIR + Dal A + kok."""

    def __init__(self, tau, bw=1, leak_jitter=0.0, rng=None):
        self.tau = tau
        self.bw = bw
        br, rt = band_leak(tau)
        j = 1.0 + rng.uniform(-leak_jitter, leak_jitter) if rng else 1.0
        self.leak_a = br * j
        self.leak_r = rt * j
        self.lock_lost = 2 * tau + bw
        self.reset()

    def reset(self):
        self.a = 0.0
        self.b = 0.0
        self.root = 0.0
        self.g = 0.0
        self.ref = None
        self.fires = []

    def pulse(self, t, amp):
        if amp <= 0:
            return False
        isi = t - self.ref if self.ref is not None else None
        if isi is None or isi > self.lock_lost:
            mu = 1.0
        else:
            d = abs(isi - self.tau)
            if d >= self.bw:
                return False
            mu = (self.bw - d) / self.bw
        self.a += amp * mu
        self.ref = t
        return True

    def tick(self, t):
        sa, sb, sr = self.a, self.b, self.root
        r = sr + DIFF * (sa - sr)
        r = r + DIFF * (sb - r)
        self.root = r
        self.a = sa + DIFF * (sr - sa)
        self.b = sb + DIFF * (sr - sb)
        self.a -= self.leak_a * self.a
        self.b -= self.leak_a * self.b
        self.root -= self.leak_r * self.root
        if self.root > 0.15:
            self.g += 0.2
        self.g -= 0.005 * self.g
        if self.g < 0:
            self.g = 0.0
        if self.root * (1.0 + self.g) > THR:
            self.a = self.b = self.root = V_RESET
            self.fires.append(t)
            return True
        return False


class ConditionNeuron:
    """Iki dalli kosul noronu (post): A=faz, B=sensor (kapisiz)."""

    LEAK_R, LEAK_A, LEAK_B = 0.04, 0.04, 0.04
    DEC_R, DEC_A, DEC_B = 0.005, 0.004, 0.003

    def __init__(self):
        self.reset()

    def reset(self):
        self.a = 0.0
        self.b = 0.0
        self.root = 0.0
        self.gr = 0.0
        self.ga = 0.0
        self.gb = 0.0
        self.last_a = -10 ** 9
        self.last_b = -10 ** 9
        self.fires = []

    def inject_a(self, t, cur):
        self.a += cur
        self.last_a = t

    def inject_b(self, t, cur):
        self.b += cur
        self.last_b = t

    def tick(self, t):
        sa, sb, sr = self.a, self.b, self.root
        r = sr + DIFF * (sa - sr)
        r = r + DIFF * (sb - r)
        self.root = r
        self.a = sa + DIFF * (sr - sa)
        self.b = sb + DIFF * (sr - sb)
        self.a -= self.LEAK_A * self.a
        self.b -= self.LEAK_B * self.b
        self.root -= self.LEAK_R * self.root
        for v, d, nm in ((self.root, self.DEC_R, "gr"),
                         (self.a, self.DEC_A, "ga"),
                         (self.b, self.DEC_B, "gb")):
            g = getattr(self, nm)
            if v > 0.15:
                g += 0.2
            g -= d * g
            setattr(self, nm, max(0.0, g))
        coinc = (t - self.last_a <= WIN_COINC) and (t - self.last_b <= WIN_COINC)
        if self.root * (1.0 + self.gr + (BONUS if coinc else 0.0)) > THR:
            self.a = self.b = self.root = V_RESET
            self.fires.append(t)
            return True, coinc
        return False, coinc


def G(p, q):
    return min(p, q) / RATE_WINDOW


def Q(p, q):
    return ((p + q) / RATE_WINDOW) ** 2


def S(w):
    return max(0.0, 1.0 - (w / W_MAX) ** 2)


def make_wire(T, delays, pulse=PULSE, noise_p=0.02, amp_jit=0.2, seed=0):
    rng = np.random.default_rng(seed)
    wire = np.zeros(T)
    for bi, tau in enumerate(TAUS):
        for t in range(delays[bi], T, tau):
            a = pulse
            if amp_jit > 0:
                a *= 1.0 + rng.uniform(-amp_jit, amp_jit)
            wire[t] += a
    if noise_p > 0:
        for t in range(T):
            if rng.random() < noise_p:
                a = pulse * 0.7
                if amp_jit > 0:
                    a *= 1.0 + rng.uniform(-amp_jit, amp_jit)
                wire[t] += a
    return wire


# post -> (bant_tau, sensor_adi)
POST_CFG = [(12, "nem"), (12, "ec"), (4, "sic")]


def run_session(S_b, w0, eta, n_cond=10, n_test=3, block=500,
                sens_cond=None, seed=7, leak_jitter=0.15):
    """Tam Pavlov oturumu. Donus: olcut dict'i."""
    if sens_cond is None:
        sens_cond = {"nem": 60, "ec": 40, "sic": 75}
    return _run_learning(S_b, w0, eta, n_cond, n_test, block, sens_cond,
                         seed, leak_jitter)


def _run_learning(S_b, w0, eta, n_cond, n_test, block, sens_cond, seed,
                  leak_jitter):
    """Gercek ogrenmeli kosu (post-bazli rate pencereleriyle)."""
    T = (n_cond + n_test) * block
    wire = make_wire(T, [0, 0], seed=seed)
    rng = np.random.default_rng(seed + 1)
    pops = [[Member(tau, rng=rng, leak_jitter=leak_jitter) for _ in range(N_POP)]
            for tau in TAUS]
    posts = [ConditionNeuron() for _ in range(3)]
    w = [w0] * 3
    hpre = [[0] * RATE_WINDOW for _ in range(3)]
    hpost = [[0] * RATE_WINDOW for _ in range(3)]
    head = 0
    cond_f = [0, 0, 0]
    test_f = [0, 0, 0]
    w_after_cond = None
    for t in range(T):
        stage = 0 if t < n_cond * block else 1
        amp = wire[t]
        if amp > 0:
            for pop in pops:
                for m in pop:
                    m.pulse(t, amp)
        rep = []
        for bi in range(2):
            f = [m.tick(t) for m in pops[bi]]
            rep.append(f[0])
        rep_of_post = [rep[1], rep[1], rep[0]]
        pf = []
        for k in range(3):
            tau, sname = POST_CFG[k]
            if rep_of_post[k]:
                posts[k].inject_a(t, w[k] * SCALE)
            if stage == 0 and sens_cond[sname] >= SENS_THRESH:
                if (t % tau) == 0:
                    posts[k].inject_b(t, S_b)
            fired, _ = posts[k].tick(t)
            pf.append(fired)
            if stage == 0:
                cond_f[k] += 1 if fired else 0
            else:
                test_f[k] += 1 if fired else 0
        for k in range(3):
            hpre[k][head] = 1 if rep_of_post[k] else 0
            hpost[k][head] = 1 if pf[k] else 0
        head = (head + 1) % RATE_WINDOW
        rp = [sum(h) for h in hpre]
        rq = [sum(h) for h in hpost]
        for k in range(3):
            dw = eta * G(rp[k], rq[k]) * Q(rp[k], rq[k]) * S(w[k])
            w[k] = min(W_MAX, w[k] + dw)
        if t == n_cond * block - 1:
            w_after_cond = list(w)
    dw_cond = [w_after_cond[k] - w0 for k in range(3)]
    return {"cond_fires": cond_f, "test_fires": test_f,
            "w_after_cond": w_after_cond, "w_end": list(w),
            "dw_cond": dw_cond}


def probe_cs_alone(w0, S_b, block=500, seed=7):
    """Kriter 2: tel-yalniz probeda (sensorler kapali, ogrenme donuk)
    A tek basina post'u atesletmemeli."""
    wire = make_wire(block, [0, 0], seed=seed)
    rng = np.random.default_rng(seed + 1)
    pops = [[Member(tau, rng=rng, leak_jitter=0.15) for _ in range(N_POP)]
            for tau in TAUS]
    posts = [ConditionNeuron() for _ in range(3)]
    fires = [0, 0, 0]
    for t in range(block):
        amp = wire[t]
        if amp > 0:
            for pop in pops:
                for m in pop:
                    m.pulse(t, amp)
        rep = []
        for bi in range(2):
            f = [m.tick(t) for m in pops[bi]]
            rep.append(f[0])
        rep_of_post = [rep[1], rep[1], rep[0]]
        for k in range(3):
            if rep_of_post[k]:
                posts[k].inject_a(t, w0 * SCALE)
            if posts[k].tick(t)[0]:
                fires[k] += 1
    return fires


def criteria(r, probe):
    c1 = r["cond_fires"][0] > 0 and r["cond_fires"][2] > 0
    c2 = probe[0] == 0 and probe[2] == 0
    c3 = r["dw_cond"][0] >= DW_GAIN_MIN and r["dw_cond"][2] >= DW_GAIN_MIN
    c4 = abs(r["dw_cond"][1]) < DW_NEG_MAX
    c5 = (r["test_fires"][0] > 0 and r["test_fires"][2] > 0
          and r["test_fires"][1] == 0)
    return [c1, c2, c3, c4, c5]


if __name__ == "__main__":
    print("=== on eleme (2 kosullanma + 1 test blogu) ===")
    grid = list(itertools.product([0.4, 0.6, 0.8, 1.0], [0.2, 0.3, 0.4],
                                  [0.1, 0.2]))
    pre = []
    for S_b, w0, eta in grid:
        r = run_session(S_b, w0, eta, n_cond=2, n_test=1)
        probe = probe_cs_alone(w0, S_b)
        c = criteria(r, probe)
        ok = all(c)
        pre.append((ok, S_b, w0, eta, r, probe, c))
        print(f"S_b={S_b} w0={w0} eta={eta}: cond_ates={r['cond_fires']} "
              f"dw={[round(x, 4) for x in r['dw_cond']]} "
              f"test_ates={r['test_fires']} probe={probe} "
              f"kriter={['1' if x else '0' for x in c]} "
              f"{'GECTI' if ok else 'kaldi'}")
    cand = [p for p in pre if p[0]]
    print(f"\n=== on eleme: {len(cand)}/{len(pre)} aday ===")
    if cand:
        # en guclu CR + en buyuk kazanimli aday
        cand.sort(key=lambda p: (p[4]["test_fires"][0] + p[4]["test_fires"][2],
                                 p[4]["dw_cond"][0] + p[4]["dw_cond"][2]),
                  reverse=True)
        _, S_b, w0, eta, _, _, _ = cand[0]
        print(f"secilen: S_b={S_b} w0={w0} eta={eta} -> tam kosu")
        r = run_session(S_b, w0, eta)
        probe = probe_cs_alone(w0, S_b)
        c = criteria(r, probe)
        print(f"tam kosu: cond_ates={r['cond_fires']} "
              f"dw={[round(x, 4) for x in r['dw_cond']]} "
              f"test_ates={r['test_fires']} probe={probe}")
        print(f"kriterler 1-5: {c} -> {'TUMU OK' if all(c) else 'BASARISIZ'}")
        print("\n--- KALIBRE SONUC ---")
        print(f"S_b={S_b} w0={w0} eta={eta}")
        print(f"beklenen dw: NEM={r['dw_cond'][0]:+.4f} "
              f"EC={r['dw_cond'][1]:+.4f} SIC={r['dw_cond'][2]:+.4f}")
        print(f"beklenen CR atesleri: NEM={r['test_fires'][0]} "
              f"EC={r['test_fires'][1]} SIC={r['test_fires'][2]}")
        print("NOT: MC yaklasik ongoru; kesin dogrulayici C++ kosusudur "
              "(validate_causality.py'de MC 2.00x -> C++ 2.11x tecrubesi).")
    else:
        print("ADAY YOK: esikler veri gorulmeden sabitlendi; grid genisletme "
              "karari insaat kapisinda verilecek.")
