"""KPR1 surucu — ablasyon parametreli yerel step (v2 + legacy twin-kolu).

pl_core IMPORT-ONLY. C++ yok. Deterministik, RNG yok.
G-A sadakat: _lstep === pl_core.p3x_tick (bit-esit, reset dahil);
K2 regresyon: normal d0->7, d1->12 (KBHP N_sig tanimiyla).
coinc: nat (uretim kurali) | lock (bonus hep acik) | off (bonus hep kapali).
ablate: None | 'k1' (A-K1 surulmez) | 'k23' (K2/K3 surulmez).
amp: tum enjeksiyonlarin olcegi (A5/A6). delay: slot*d_step (A0 uygulamasi).
Legacy kolu pl_core primitive'leriyle (kbp_drive'e dokunmadan, bagimsiz kod).
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


def _lstep(n, t, coinc="nat"):
    snap = tuple(n.V)
    for k in range(1, 7):
        n.V[0] += P.DIFF * (snap[k] - n.V[0])
    for k in range(1, 7):
        n.V[k] += P.DIFF * (snap[0] - n.V[k])
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
    if coinc == "lock":
        bonus = True
    elif coinc == "off":
        bonus = False
    else:
        bonus = a_in and b_in
    eff_g = n.g[0] + (P.BONUS if bonus else 0.0)
    soma = n.V[0] * (1.0 + eff_g)
    n.soma = soma
    if soma > P.THR:
        n.n_fired += 1
        for i in range(7):
            n.V[i] = P.V_RESET
        n.soma = P.V_RESET
        return True, (a_in and b_in), eff_g, soma
    return False, (a_in and b_in), eff_g, soma


def k0_lstep_equiv():
    a, b = P.P3xNeuron(), P.P3xNeuron()
    for t in range(80):
        if t % 3 == 0:
            P.p3x_inject(a, P.P3X_A_K1, 0.5, t)
            P.p3x_inject(b, P.P3X_A_K1, 0.5, t)
        if t % 7 == 0:
            P.p3x_inject(a, P.P3X_B_K3, 0.3, t)
            P.p3x_inject(b, P.P3X_B_K3, 0.3, t)
        ra = P.p3x_tick(a, t)
        rb = _lstep(b, t)
        # ikisi de (fired, coinc, eff_g, soma) sirasiyla doner
        if ra != rb or a.V != b.V or a.g != b.g or a.soma != b.soma:
            return False
    return True


def run(slot, amp=1.0, d_step=0, ablate=None, coinc="nat"):
    units = [P.P3xNeuron() for _ in range(P.P3X_N)]
    evs = [(T0 + i * ISI + slot * d_step, slot) for i in range(N_PULSE)]
    per = {}
    for i in range(6):
        n = units[i]
        c = S5[i]
        g0, soma, fire, coinc_tr = [], [], [], []
        s_num, s_den = 0.0, 0.0
        for t in range(H):
            for (te, s) in evs:
                if te != t:
                    continue
                if ablate != "k1":
                    if s == c:
                        P.p3x_inject(n, P.P3X_A_K1, amp, t)
                    elif s == (c - 1) % 12 or s == (c + 1) % 12:
                        P.p3x_inject(n, P.P3X_A_K1, amp * RING, t)
                if ablate != "k23":
                    for k in (P.P3X_A_K2, P.P3X_A_K3,
                              P.P3X_B_K2, P.P3X_B_K3):
                        P.p3x_inject(n, k, amp, t)
            snap0 = n.V[0]
            snapK = [n.V[k] for k in range(1, 7)]
            f, co, eg, sm = _lstep(n, t, coinc)
            for kk in range(6):
                fl = P.DIFF * (snapK[kk] - snap0)
                if fl > 0:
                    s_den += fl
                    if kk == 0:
                        s_num += fl
            g0.append(eg)
            soma.append(sm)
            fire.append(1 if f else 0)
            coinc_tr.append(1 if co else 0)
        per[i] = {"g0": g0, "soma": soma, "fire": fire, "coinc": coinc_tr,
                  "fire_ticks": tuple(t for t, x in enumerate(fire) if x),
                  "S_share": (s_num / s_den) if s_den > 0 else 0.0}
    return per


def run_legacy(slot, amp=1.0, d_step=0, ablate=None):
    # kbp_drive.run_legacy'den BAGIMSIZ tái-implementasyon (twin-yerel kol).
    # ablate: None | 'k1' (K1 noronlari surulmez) | 'k23'.
    u = P.PatternUnit("ring")
    evs = [(T0 + i * ISI + slot * d_step, slot) for i in range(N_PULSE)]
    comp_of = {0: P.COMP_A, 1: P.COMP_B}
    g0, soma, fire, coinc = [], [], [], []
    n_k1 = n_ktot = 0
    for t in range(H):
        for (te, s) in evs:
            if te != t:
                continue
            for dal in (0, 1):
                comp = comp_of[dal]
                if ablate != "k1":
                    P.inject(u.k1[dal][s], comp, amp, t)
                    P.inject(u.k1[dal][(s - 1) % 12], comp, amp * RING, t)
                    P.inject(u.k1[dal][(s + 1) % 12], comp, amp * RING, t)
                if ablate != "k23":
                    P.inject(u.k2[dal], comp, amp, t)
                    P.inject(u.k3[dal], comp, amp, t)
        kf, f, co, eg, sm = P.step(u, t)
        for (_, nm, _) in kf:
            n_ktot += 1
            if nm == "k1":
                n_k1 += 1
        g0.append(eg)
        soma.append(sm)
        fire.append(1 if f else 0)
        coinc.append(1 if co else 0)
    return {"g0": g0, "soma": soma, "fire": fire, "coinc": coinc,
            "fire_ticks": tuple(t for t, x in enumerate(fire) if x),
            "S_share": (n_k1 / n_ktot) if n_ktot else 0.0}
