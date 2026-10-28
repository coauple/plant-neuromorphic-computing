"""KBHP surucu — yerel step + tap'ler (v2 + legacy-3komp kolu).

pl_core IMPORT-ONLY. C++ yok. Deterministik, RNG yok.
Dinamikler pl_core ile bit-esit (G-A); okuma/parite/coinc EKSENLERI yalniz
enjeksiyon + raporlamada yasar:
  - R0/R1/R2 soma dinamigini DEGISTIRMEZ (soma daima g[0]+bonus; legacy
    formulune dokunulmaz). R1/R2 ek gating toplamlari raporlar.
  - parite sep: Dal-B enjeksiyonu yok (3 komp/olay); id: iki dal (5 komp/olay).
  - coinc-locked: bonus hep eklenir (yalniz yerel step).
Legacy kolu pl_core.tick/inject KULLANIR (kopya yok); R1/R2 legacy'de
g[0]+g[A] / g[0]+g[A]+g[B] raporudur, dinamik aynidir.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pl_core as P  # noqa: E402

H = 160
T0 = 5
N_PULSE = 8
ISI = 10
AMP = 1.0
RING = 0.2
S5 = list(P.S5_CENTERS)
CENTER_C = 4  # tek-slotGovde merkezi (S5 P3b) — tum birimler ayni kabloyu gorur


def _vstep(n, t, coinc_lock=False):
    # pl_core.p3x_tick bit-esdegeri + okuma toplamlari.
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
    coinc = (a_in and b_in) or coinc_lock
    eff_g = n.g[0] + (P.BONUS if coinc else 0.0)
    soma = n.V[0] * (1.0 + eff_g)
    n.soma = soma
    r1 = n.g[0] + n.g[1] + n.g[2] + n.g[3]
    r2 = r1 + n.g[4] + n.g[5] + n.g[6]
    if soma > P.THR:
        n.n_fired += 1
        for i in range(7):
            n.V[i] = P.V_RESET
        n.soma = P.V_RESET
        return True, coinc, eff_g, soma, r1, r2
    return False, coinc, eff_g, soma, r1, r2


def k0_vstep_equiv():
    a, b = P.P3xNeuron(), P.P3xNeuron()
    for t in range(80):
        if t % 3 == 0:
            P.p3x_inject(a, P.P3X_A_K1, 0.5, t)
            P.p3x_inject(b, P.P3X_A_K1, 0.5, t)
        if t % 7 == 0:
            P.p3x_inject(a, P.P3X_B_K3, 0.3, t)
            P.p3x_inject(b, P.P3X_B_K3, 0.3, t)
        ra = P.p3x_tick(a, t)
        rb = _vstep(b, t)[:4]
        if ra != rb or a.V != b.V or a.g != b.g or a.soma != b.soma:
            return False
    return True


def _evs_single(slot, d_step):
    return [(T0 + i * ISI + slot * d_step, slot) for i in range(N_PULSE)]


def run_v2(slot=None, pair=None, okuma="R0", parite="id", d_step=0,
           topoloji="T0", coinc_lock=False):
    # slot: tek-slot; pair: (X, Y) iki-slot (X->A-dali, Y->B-dali).
    # topoloji T1: sahip birimin K1A-merkezi X, K2/K3 {X,Y}-secici.
    units = [P.P3xNeuron() for _ in range(P.P3X_N)]
    if slot is not None:
        evs = [(t, s, None) for (t, s) in _evs_single(slot, d_step)]
    else:
        X, Y = pair
        evs = []
        for i in range(N_PULSE):
            evs.append((T0 + i * ISI + X * d_step, X, "A"))
            evs.append((T0 + i * ISI + Y * d_step, Y, "B"))
        evs.sort()
    centers = list(S5)
    selective = None
    if topoloji == "T1" and pair is not None:
        X, Y = pair
        selective = {X, Y}
    per = {}
    for i in range(6):
        n = units[i]
        c = centers[i]
        g0, r1t, r2t, soma, fire, coinc = [], [], [], [], [], []
        s_num, s_den = 0.0, 0.0
        for t in range(H):
            for (te, s, dal) in evs:
                if te != t:
                    continue
                if slot is not None:
                    # tek-slot: tum dallar ayni slotu gorur (uretim aynasi)
                    if s == c:
                        P.p3x_inject(n, P.P3X_A_K1, AMP, t)
                    elif s == (c - 1) % 12 or s == (c + 1) % 12:
                        P.p3x_inject(n, P.P3X_A_K1, AMP * RING, t)
                    P.p3x_inject(n, P.P3X_A_K2, AMP, t)
                    P.p3x_inject(n, P.P3X_A_K3, AMP, t)
                    if parite == "id":
                        P.p3x_inject(n, P.P3X_B_K2, AMP, t)
                        P.p3x_inject(n, P.P3X_B_K3, AMP, t)
                else:
                    # iki-slot: X->A, Y->B (dal-ayrik surus)
                    if dal == "A":
                        if s == c:
                            P.p3x_inject(n, P.P3X_A_K1, AMP, t)
                        elif s == (c - 1) % 12 or s == (c + 1) % 12:
                            P.p3x_inject(n, P.P3X_A_K1, AMP * RING, t)
                        if selective is None or s in selective:
                            P.p3x_inject(n, P.P3X_A_K2, AMP, t)
                            P.p3x_inject(n, P.P3X_A_K3, AMP, t)
                    else:
                        if selective is None or s in selective:
                            if parite == "id":
                                P.p3x_inject(n, P.P3X_B_K2, AMP, t)
                                P.p3x_inject(n, P.P3X_B_K3, AMP, t)
            snap0 = n.V[0]
            snapK = [n.V[k] for k in range(1, 7)]
            f, co, eg, sm, r1, r2 = _vstep(n, t, coinc_lock)
            for kk in range(6):
                fl = P.DIFF * (snapK[kk] - snap0)
                if fl > 0:
                    s_den += fl
                    if kk == 0:
                        s_num += fl
            g0.append(eg if okuma == "R0" else eg)
            r1t.append(r1)
            r2t.append(r2)
            soma.append(sm)
            fire.append(1 if f else 0)
            coinc.append(1 if co else 0)
        per[i] = {"g0": g0, "r1": r1t, "r2": r2t, "soma": soma,
                  "fire": fire, "coinc": coinc,
                  "fire_ticks": tuple(t for t, x in enumerate(fire) if x),
                  "S_share": (s_num / s_den) if s_den > 0 else 0.0}
    return per


def run_legacy(slot=None, pair=None, okuma="R0", parite="id", d_step=0):
    # twin-yerel 3-komp kolu: pl_core primitive'leri dogrudan.
    # okuma legacy'de rapor-duzeyi: R0=g[0], R1=g[0]+g[A], R2=g[0]+g[A]+g[B].
    u = P.PatternUnit("ring")
    if slot is not None:
        evs = [(t, s, None) for (t, s) in _evs_single(slot, d_step)]
    else:
        X, Y = pair
        evs = []
        for i in range(N_PULSE):
            evs.append((T0 + i * ISI + X * d_step, X, "A"))
            evs.append((T0 + i * ISI + Y * d_step, Y, "B"))
        evs.sort()
    g0, r1t, r2t, soma, fire, coinc, kbits = [], [], [], [], [], [], []
    n_k1 = n_ktot = 0
    for t in range(H):
        for (te, s, dal) in evs:
            if te != t:
                continue
            if slot is not None:
                for dd in (0, 1) if parite == "id" else (0,):
                    comp = P.COMP_A if dd == 0 else P.COMP_B
                    P.inject(u.k1[dd][s], comp, AMP, t)
                    P.inject(u.k1[dd][(s - 1) % 12], comp, AMP * RING, t)
                    P.inject(u.k1[dd][(s + 1) % 12], comp, AMP * RING, t)
                    P.inject(u.k2[dd], comp, AMP, t)
                    P.inject(u.k3[dd], comp, AMP, t)
            else:
                dd = 0 if dal == "A" else 1
                if parite == "sep" and dal == "B":
                    continue
                comp = P.COMP_A if dd == 0 else P.COMP_B
                P.inject(u.k1[dd][s], comp, AMP, t)
                P.inject(u.k1[dd][(s - 1) % 12], comp, AMP * RING, t)
                P.inject(u.k1[dd][(s + 1) % 12], comp, AMP * RING, t)
                P.inject(u.k2[dd], comp, AMP, t)
                P.inject(u.k3[dd], comp, AMP, t)
        kf, f, co, eg, sm = P.step(u, t)
        for (_, nm, _) in kf:
            n_ktot += 1
            if nm == "k1":
                n_k1 += 1
        p3 = u.p3
        g0.append(p3.g[0])
        r1t.append(p3.g[0] + p3.g[1])
        r2t.append(p3.g[0] + p3.g[1] + p3.g[2])
        soma.append(sm)
        fire.append(1 if f else 0)
        coinc.append(1 if co else 0)
        kbits.append(tuple(
            1 if any(x[0] == dd and x[1] == "k1" and x[2] == s
                     for x in kf) else 0
            for dd in (0, 1) for s in range(12)))
    return {"g0": g0, "r1": r1t, "r2": r2t, "soma": soma, "fire": fire,
            "coinc": coinc, "kbits": kbits,
            "fire_ticks": tuple(t for t, x in enumerate(fire) if x),
            "S_share": (n_k1 / n_ktot) if n_ktot else 0.0,
            "n_k1": n_k1, "n_ktot": n_ktot}


def cable_drive_v2(events, max_tick):
    # G-A: R0.id.d0 kablo-surusu (v2_drive esdegeri).
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
            f, _, _, _, _, _ = _vstep(units[i], t)
            if f:
                fires[i].append(t)
    return fires
