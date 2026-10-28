"""KPR surucu — F1/F4/F8 yerel step + tap'ler.

pl_core IMPORT-ONLY. C++ yok. Deterministik, RNG yok.
C0 konfiguru pl_core.p3x_tick ile bit-esit (Faz 0).
Kilitli parametreler: G_ROOT=0.30, D_CHILD=0.15, ALPHA=0.3, w=1.0, THR=1.0.
Uyaran KBHP ile birebir: 8 darbe, ISI=10, t0=5, H=160, amp 1.0, ring 0.2,
iki dal, S5 (P3a..P3f). sep: Dal-B sessiz.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pl_core as P  # noqa: E402

H = 160
T0 = 5
N_PULSE = 8
ISI = 10
RING = 0.2
S5 = list(P.S5_CENTERS)
G_ROOT = 0.30
D_CHILD = 0.15
ALPHA = 0.3


def _kstep(n, t, cfg):
    # cfg: 'C0' | 'F1' | 'F1F4' | 'F1F8' | 'FULL'(F1+F4+F8).
    # C0: p3x_tick bit-esdegeri.
    if cfg == "C0":
        snap = tuple(n.V)
        for k in range(1, 7):
            n.V[0] += P.DIFF * (snap[k] - n.V[0])
        for k in range(1, 7):
            n.V[k] += P.DIFF * (snap[0] - n.V[k])
    else:
        snap = tuple(n.V)
        for k in range(1, 7):
            ref = 0.0 if (cfg in ("F1F4", "FULL") and k == P.P3X_A_K1) \
                else snap[0]
            n.V[0] += (G_ROOT / 6.0) * (snap[k] - ref)
        for k in range(1, 7):
            n.V[k] += D_CHILD * (snap[0] - snap[k])
    for i in range(7):
        n.V[i] -= P.P3X_LEAK[i] * (n.V[i] - P.V_REST)
    for i in range(7):
        if n.V[i] > P.G_ACT:
            n.g[i] += P.G_INC
        n.g[i] -= P.P3X_GD[i] * n.g[i]
        if n.g[i] < 0.0:
            n.g[i] = 0.0
    a_in = n.A_last >= 0 and (t - n.A_last) <= P.WIN
    b_in = n.B_last >= 0 and (t - n.B_last) <= P.WIN
    coinc = a_in and b_in
    eff_g = n.g[0] + (P.BONUS if coinc else 0.0)
    soma = n.V[0] * (1.0 + eff_g)
    if cfg in ("F1F8", "FULL"):
        soma += ALPHA * sum(n.V[1:7])
    n.soma = soma
    if soma > P.THR:
        n.n_fired += 1
        for i in range(7):
            n.V[i] = P.V_RESET
        n.soma = P.V_RESET
        return True, coinc, eff_g, soma
    return False, coinc, eff_g, soma


def impulse_weights(cfg):
    # Birim-darbe probu: her kompartmana tek 1.0 (t=10), kok ΔV(t=10).
    # A/B simetrisi = min/maks oran (C0 beklenti 0.614, F beklenti 1.000).
    w = []
    for k in range(1, 7):
        n = P.P3xNeuron()
        for t in range(12):
            if t == 10:
                P.p3x_inject(n, k, 1.0, t)
            _kstep(n, t, cfg)
            if t == 10:
                w.append(n.V[0])
    return w


def persistence(cfg):
    # K2/K3 rol koruması: tek-darbe sonrasi ΣV_K3 / ΣV_K2 (kalicilik orani).
    out = {}
    for k, nm in ((P.P3X_A_K2, "k2"), (P.P3X_A_K3, "k3")):
        n = P.P3xNeuron()
        s = 0.0
        for t in range(10, 160):
            if t == 10:
                P.p3x_inject(n, k, 1.0, t)
            _kstep(n, t, cfg)
            s += n.V[k]
        out[nm] = s
    return out["k3"] / max(out["k2"], 1e-12), out


def k0_step_equiv():
    a, b = P.P3xNeuron(), P.P3xNeuron()
    for t in range(80):
        if t % 3 == 0:
            P.p3x_inject(a, P.P3X_A_K1, 0.5, t)
            P.p3x_inject(b, P.P3X_A_K1, 0.5, t)
        if t % 7 == 0:
            P.p3x_inject(a, P.P3X_B_K3, 0.3, t)
            P.p3x_inject(b, P.P3X_B_K3, 0.3, t)
        ra = P.p3x_tick(a, t)
        rb = _kstep(b, t, "C0")
        if ra != rb or a.V != b.V or a.g != b.g or a.soma != b.soma:
            return False
    return True


def run(slot, amp=1.0, d_step=0, cfg="C0", sep=False):
    units = [P.P3xNeuron() for _ in range(P.P3X_N)]
    evs = [(T0 + i * ISI + slot * d_step, slot) for i in range(N_PULSE)]
    per = {}
    for i in range(6):
        n = units[i]
        c = S5[i]
        g0, soma, fire, coinc = [], [], [], []
        s_num, s_den = 0.0, 0.0
        for t in range(H):
            for (te, s) in evs:
                if te != t:
                    continue
                if s == c:
                    P.p3x_inject(n, P.P3X_A_K1, amp, t)
                elif s == (c - 1) % 12 or s == (c + 1) % 12:
                    P.p3x_inject(n, P.P3X_A_K1, amp * RING, t)
                P.p3x_inject(n, P.P3X_A_K2, amp, t)
                P.p3x_inject(n, P.P3X_A_K3, amp, t)
                if not sep:
                    P.p3x_inject(n, P.P3X_B_K2, amp, t)
                    P.p3x_inject(n, P.P3X_B_K3, amp, t)
            snap0 = n.V[0]
            snapK = [n.V[k] for k in range(1, 7)]
            f, co, eg, sm = _kstep(n, t, cfg)
            # S_share: konfigürasyonun KENDİ kök-formülüyle pozitif-sızıntı
            # payı (C0: D·(S−S0); F: G/6·(S−ref), F4'te A-K1 ref=0).
            for kk in range(6):
                if cfg == "C0":
                    fl = P.DIFF * (snapK[kk] - snap0)
                else:
                    ref = 0.0 if (cfg in ("F1F4", "FULL") and
                                  kk == 0) else snap0
                    fl = (G_ROOT / 6.0) * (snapK[kk] - ref)
                if fl > 0:
                    s_den += fl
                    if kk == 0:
                        s_num += fl
            g0.append(eg)
            soma.append(sm)
            fire.append(1 if f else 0)
            coinc.append(1 if co else 0)
        per[i] = {"g0": g0, "soma": soma, "fire": fire, "coinc": coinc,
                  "fire_ticks": tuple(t for t, x in enumerate(fire) if x),
                  "S_share": (s_num / s_den) if s_den > 0 else 0.0}
    return per
