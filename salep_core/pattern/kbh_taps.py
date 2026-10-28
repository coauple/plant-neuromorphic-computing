"""KBH enstrumante surucu (legacy + v2) — Faz 0/1/2 altyapisi.

pl_core IMPORT-ONLY (degistirmez). C++ yok. Deterministik, RNG yok.
v2 leak/parametre eksenleri icin _ptick: pl_core.p3x_tick ile esdegerligi
K0b icinde dogrulanmis yerel kopya (yalniz A2-blind/A3'te override ile
kullanilir; diger tum v2 kosulari pl_core.p3x_tick/p3x_inject kullanir).
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pattern"))

import pl_core as P  # noqa: E402

HORIZON = 200
T0 = 50
N_PULSE = 8
ISI = 10
RING = 0.2
DISTRACTOR_OFF = 6

S5 = list(P.S5_CENTERS)  # [1,4,7,5,6,0], P3a..P3f; P3g.. OPEN


def _ptick(n, t, leaks=None, gds=None):
    # pl_core.p3x_tick esdegeri (leaks/gds None ise P3X sabitleri).
    # K0b: override'siz bit-esitlik dogrulanir.
    lk = leaks or P.P3X_LEAK
    gd = gds or P.P3X_GD
    snap = tuple(n.V)
    for k in range(1, 7):
        n.V[0] += P.DIFF * (snap[k] - n.V[0])
    for k in range(1, 7):
        n.V[k] += P.DIFF * (snap[0] - n.V[k])
    for i in range(7):
        n.V[i] -= lk[i] * (n.V[i] - P.V_REST)
    for i in range(7):
        if n.V[i] > P.G_ACT:
            n.g[i] += P.G_INC
        n.g[i] -= gd[i] * n.g[i]
        if n.g[i] < 0.0:
            n.g[i] = 0.0
    a_in = n.A_last >= 0 and (t - n.A_last) <= P.WIN
    b_in = n.B_last >= 0 and (t - n.B_last) <= P.WIN
    coinc = a_in and b_in
    eff_g = n.g[0] + (P.BONUS if coinc else 0.0)
    soma = n.V[0] * (1.0 + eff_g)
    n.soma = soma
    if soma > P.THR:
        n.n_fired += 1
        for i in range(7):
            n.V[i] = P.V_RESET
        n.soma = P.V_RESET
        return True, coinc, eff_g, soma
    return False, coinc, eff_g, soma


def k0_ptick_equiv():
    # _ptick(None-override) === p3x_tick, bir prob uzerinde bit-esit.
    a, b = P.P3xNeuron(), P.P3xNeuron()
    for t in range(60):
        if t % 3 == 0:
            P.p3x_inject(a, P.P3X_A_K1, 0.5, t)
            P.p3x_inject(b, P.P3X_A_K1, 0.5, t)
        if t % 7 == 0:
            P.p3x_inject(a, P.P3X_B_K3, 0.3, t)
            P.p3x_inject(b, P.P3X_B_K3, 0.3, t)
        ra = P.p3x_tick(a, t)
        rb = _ptick(b, t)
        if ra != rb or a.V != b.V or a.g != b.g or a.soma != b.soma:
            return False
    return True


def _sched(slot, n_pulse=N_PULSE, isi=ISI, t0=T0, delay=0,
           dual=False, distractor=DISTRACTOR_OFF):
    # [(tick, slot)] varis-listesi (A0 gecikmesi varista uygulanir).
    evs = [(t0 + i * isi + delay, slot) for i in range(n_pulse)]
    if dual:
        evs += [(t0 + i * isi + delay, (slot + distractor) % 12)
                for i in range(n_pulse)]
    return sorted(evs)


def legacy_run(slot, amp, w_ring=RING, dals=(0, 1), delay=0, dual=False,
               k1_gain=1.0, k2k3_gain=1.0, k2k3_mode="asymmetric",
               leak_override=None):
    # A2 ekseni (SPEC): off=sessiz; blind=dal-geneli surus + SIMETRIK
    # parametre (brB:=brA sinifi); selective=yalniz tren-slotu surer (ontanim
    # parametre); asymmetric=dal-geneli + A!=B ontanim (uretim aynasi).
    u = P.PatternUnit("ring")
    if k2k3_mode == "blind":
        for dal in (0, 1):
            for arr in (u.k2, u.k3):
                arr[dal].leak[P.COMP_B] = arr[dal].leak[P.COMP_A]
                arr[dal].gdecay[P.COMP_B] = arr[dal].gdecay[P.COMP_A]
    if leak_override is not None:
        for dal in dals:
            comp = P.COMP_A if dal == 0 else P.COMP_B
            u.k1[dal][slot].leak[comp] = leak_override
    evs = _sched(slot, delay=delay, dual=dual)
    comp_of = {0: P.COMP_A, 1: P.COMP_B}
    trace = {"k1V": [], "k1g": [], "k2V": [], "k3V": [],
             "soma": [], "eff": [], "coinc": [], "fire": [],
             "kbits": []}
    for t in range(HORIZON):
        for (te, s) in evs:
            if te != t:
                continue
            for dal in dals:
                comp = comp_of[dal]
                a1 = amp * k1_gain
                P.inject(u.k1[dal][s], comp, a1, t)
                if w_ring:
                    ar = amp * w_ring * k1_gain
                    P.inject(u.k1[dal][(s - 1) % 12], comp, ar, t)
                    P.inject(u.k1[dal][(s + 1) % 12], comp, ar, t)
                if k2k3_mode != "off":
                    if k2k3_mode == "selective" and s != slot:
                        continue
                    a2 = amp * k2k3_gain
                    P.inject(u.k2[dal], comp, a2, t)
                    P.inject(u.k3[dal], comp, a2, t)
        kf, fired, coinc, eff_g, soma = P.step(u, t)
        cA = u.k1[0][slot]
        trace["k1V"].append(cA.V[1])
        trace["k1g"].append(cA.g[1])
        trace["k2V"].append(u.k2[0].V[1])
        trace["k3V"].append(u.k3[0].V[1])
        trace["soma"].append(soma)
        trace["eff"].append(eff_g)
        trace["coinc"].append(1 if coinc else 0)
        trace["fire"].append(1 if fired else 0)
        trace["kbits"].append(tuple(
            1 if any(f[0] == dal and f[1] == "k1" and f[2] == s
                     for f in kf) else 0
            for dal in (0, 1) for s in range(12)))
    trace["fire_ticks"] = tuple(t for t, f in enumerate(trace["fire"]) if f)
    return trace


def v2_run(slot, amp, w_ring=RING, delay=0, dual=False,
           k1_gain=1.0, k2k3_gain=1.0, k2k3_mode="blind",
           leak_override=None, use_ptick=False):
    # S5 kablolama: 6 birim; B-K1 yapisal kablosuz (SPEC A2c notu).
    # A2: off=sessiz; blind=dal-geneli + SIMETRIK parametre (B:=A sinifi);
    # selective=K2/K3 yalniz merkez-eslesen olayda (slot==merkez, ontanim
    # parametre); asymmetric=dal-geneli + A!=B ontanim (uretim aynasi).
    # leak_override: A-K1 leak (yapısal saha: _ptick ile).
    units = [P.P3xNeuron() for _ in range(P.P3X_N)]
    evs = _sched(slot, delay=delay, dual=dual)
    leaks = None
    if leak_override is not None:
        leaks = list(P.P3X_LEAK)
        leaks[P.P3X_A_K1] = leak_override
        use_ptick = True
    gds = None
    if k2k3_mode == "blind":
        leaks = list(leaks or P.P3X_LEAK)
        leaks[P.P3X_B_K2] = P.P3X_LEAK[P.P3X_A_K2]
        leaks[P.P3X_B_K3] = P.P3X_LEAK[P.P3X_A_K3]
        gds = list(P.P3X_GD)
        gds[P.P3X_B_K2] = P.P3X_GD[P.P3X_A_K2]
        gds[P.P3X_B_K3] = P.P3X_GD[P.P3X_A_K3]
        use_ptick = True
    per_unit = {}
    for i in range(6):
        c = S5[i]
        V1, g1, soma, eff, coinc, fire = [], [], [], [], [], []
        n = units[i]
        for t in range(HORIZON):
            for (te, s) in evs:
                if te != t:
                    continue
                if s == c:
                    P.p3x_inject(n, P.P3X_A_K1, amp * k1_gain, t)
                elif s == (c - 1) % 12 or s == (c + 1) % 12:
                    P.p3x_inject(n, P.P3X_A_K1, amp * w_ring * k1_gain, t)
                drive_k23 = (k2k3_mode != "off" and
                             not (k2k3_mode == "selective" and s != c))
                if drive_k23:
                    a2 = amp * k2k3_gain
                    for k in (P.P3X_A_K2, P.P3X_A_K3,
                              P.P3X_B_K2, P.P3X_B_K3):
                        P.p3x_inject(n, k, a2, t)
            if use_ptick:
                f, co, eg, sm = _ptick(n, t, leaks, gds)
            else:
                f, co, eg, sm = P.p3x_tick(n, t)
            V1.append(n.V[P.P3X_A_K1])
            g1.append(n.g[P.P3X_A_K1])
            soma.append(sm)
            eff.append(eg)
            coinc.append(1 if co else 0)
            fire.append(1 if f else 0)
        per_unit[i] = {"k1V": V1, "k1g": g1, "soma": soma, "eff": eff,
                       "coinc": coinc, "fire": fire,
                       "fire_ticks": tuple(t for t, f in enumerate(fire)
                                           if f)}
    return per_unit


def v2_reference_drive(events, max_tick):
    # pl_core.v2_drive birebir aynasi (K0b). CUR/RING twin sabitleri.
    units = [P.P3xNeuron() for _ in range(P.P3X_N)]
    by_tick = {}
    for (t, p) in events:
        by_tick.setdefault(t, []).append(p)
    fires = {i: [] for i in range(P.P3X_N)}
    for t in range(max_tick + 1):
        for s in by_tick.get(t, ()):
            for i in range(6):
                c = S5[i]
                if s == c:
                    P.p3x_inject(units[i], P.P3X_A_K1, 0.5, t)
                elif s == (c - 1) % 12 or s == (c + 1) % 12:
                    P.p3x_inject(units[i], P.P3X_A_K1, 0.1, t)
                for k in (P.P3X_A_K2, P.P3X_A_K3,
                          P.P3X_B_K2, P.P3X_B_K3):
                    P.p3x_inject(units[i], k, 0.5, t)
        for i in range(P.P3X_N):
            f, _, _, _ = P.p3x_tick(units[i], t)
            if f:
                fires[i].append(t)
    return fires
