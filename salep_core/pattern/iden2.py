"""IDEN2 mekanizmasi — IDEN2_SPEC.md §1. iden.py'ye DOKUNULMAZ.

Ayni K1-only halka + readout; fark: INH yapilandirilabilir
(0 = WTA kapali). pl_core import, degisiklik yok. RNG yok.
"""
import os
import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)
import pl_core as C
from iden import ring_inject, new_k1, new_readout

N_PULSE, ISI, T0, HORIZON, FEED = 5, 12, 50, 200, 1.0


class Iden2Unit(object):
    def __init__(self, inh):
        self.inh = inh
        self.k1 = new_k1()
        self.ro = [new_readout() for _ in range(12)]

    def run(self, sched):
        ro_fire = [[] for _ in range(12)]
        for t in range(HORIZON):
            for (dal, slot, a) in sched.get(t, ()):
                ring_inject(self.k1, dal, slot, a, t)
            for i in range(12):
                f, _, _, _ = C.tick(self.k1[0][i], t)
                if f:
                    C.inject(self.ro[i], C.COMP_A, FEED, t)
                f, _, _, _ = C.tick(self.k1[1][i], t)
                if f:
                    C.inject(self.ro[i], C.COMP_B, FEED, t)
            fired_now = []
            for i in range(12):
                f, _, _, _ = C.tick(self.ro[i], t)
                if f:
                    ro_fire[i].append(t)
                    fired_now.append(i)
            if self.inh != 0.0:
                for s in fired_now:
                    for r in range(12):
                        if r != s:
                            C.inject(self.ro[r], C.COMP_ROOT, -self.inh, t)
        return ro_fire
