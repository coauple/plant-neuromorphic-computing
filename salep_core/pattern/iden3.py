"""IDEN3 enstrumanli birim — IDEN3_SPEC.md §2. iden/iden2 degismez.

Iden2Unit ile ayni mekanizma + kayit: readout-basi coinc-tick ve
dal-basi girdi sayilari. pl_core + iden yardimcilari import.
RNG yok.
"""
import os
import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)
import pl_core as C
from iden import ring_inject, new_k1, new_readout

N_PULSE, ISI, T0, HORIZON, FEED, INH = 5, 12, 50, 200, 1.0, 1.0


def run_sched(sched):
    k1 = new_k1()
    ro = [new_readout() for _ in range(12)]
    ro_fire = [[] for _ in range(12)]
    ro_co = [0] * 12
    ro_in = [[0, 0] for _ in range(12)]
    for t in range(HORIZON):
        for (dal, slot, a) in sched.get(t, ()):
            ring_inject(k1, dal, slot, a, t)
        for i in range(12):
            f, _, _, _ = C.tick(k1[0][i], t)
            if f:
                C.inject(ro[i], C.COMP_A, FEED, t)
                ro_in[i][0] += 1
            f, _, _, _ = C.tick(k1[1][i], t)
            if f:
                C.inject(ro[i], C.COMP_B, FEED, t)
                ro_in[i][1] += 1
        fired_now = []
        for i in range(12):
            f, co, _, _ = C.tick(ro[i], t)
            if f:
                ro_fire[i].append(t)
                fired_now.append(i)
            if co:
                ro_co[i] += 1
        for s in fired_now:
            for r in range(12):
                if r != s:
                    C.inject(ro[r], C.COMP_ROOT, -INH, t)
    return ro_fire, ro_co, ro_in
