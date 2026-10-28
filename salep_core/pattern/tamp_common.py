"""T-AMP ortak K surucusu — P0b ring aynisi (T_AMP_SPEC.md §1).

pl_core.py'yi import eder, degistirmez. Her iki prototip ayni
K izini tuketir. RNG yok.
"""
import os
import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)
import pl_core as C

N_PULSE, ISI, AMP, W_RING, T0, HORIZON = 5, 12, 1.0, 0.2, 50, 200


def k_schedule(phi_a, phi_b, dt, order="AB", amp=AMP):
    sa, sb = (phi_a // 30) % 12, (phi_b // 30) % 12
    ta = T0 if order == "AB" else T0 + dt
    tb = T0 + dt if order == "AB" else T0
    sched = {}
    for k in range(N_PULSE):
        sched.setdefault(ta + k * ISI, []).append((0, sa, amp))
        sched.setdefault(tb + k * ISI, []).append((1, sb, amp))
    return sched


def new_k_layer():
    return C.PatternUnit("ring", 0)


def tick_k(u, t, sched):
    for (dal, slot, a) in sched.get(t, ()):
        C.inject_phase(u, dal, slot, a, W_RING, t)
    fires = []
    for dal in (0, 1):
        for s in range(12):
            f, _, _, _ = C.tick(u.k1[dal][s], t)
            if f:
                fires.append((dal, "k1", s))
        for name, arr in (("k2", u.k2), ("k3", u.k3)):
            f, _, _, _ = C.tick(arr[dal], t)
            if f:
                fires.append((dal, name, -1))
    return fires
