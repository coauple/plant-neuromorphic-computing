"""IDEN5 mekanizmasi — IDEN5_SPEC.md §1. iden2.py degismez.

K1 bank + K2 cifti (P0 yapisi) + 12 readout + WTA(INH=1.0).
K2[B] atesleri ortak-kip. pl_core + iden yardimcilari import.
RNG yok.
"""
import os
import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)
import pl_core as C
from iden import ring_inject, new_k1, new_readout

N_PULSE, ISI, HORIZON, FEED, INH = 5, 12, 200, 1.0, 1.0


def new_k2():
    P = C.K2
    return [C.make_neuron(P["root_leak"], P["bra"], P["brb"],
                          P["root_gd"], P["bra_gd"], P["brb_gd"])
            for _ in range(2)]


class Iden5Unit(object):
    def __init__(self, with_k2):
        self.with_k2 = with_k2
        self.k1 = new_k1()
        self.k2 = new_k2() if with_k2 else None
        self.ro = [new_readout() for _ in range(12)]

    def run(self, sched):
        ro_fire = [[] for _ in range(12)]
        for t in range(HORIZON):
            for (dal, slot, a) in sched.get(t, ()):
                ring_inject(self.k1, dal, slot, a, t)
                if self.with_k2:
                    comp = C.COMP_A if dal == 0 else C.COMP_B
                    C.inject(self.k2[dal], comp, a, t)
            for i in range(12):
                f, _, _, _ = C.tick(self.k1[0][i], t)
                if f:
                    C.inject(self.ro[i], C.COMP_A, FEED, t)
                f, _, _, _ = C.tick(self.k1[1][i], t)
                if f:
                    C.inject(self.ro[i], C.COMP_B, FEED, t)
            if self.with_k2:
                for dal in (0, 1):
                    f, _, _, _ = C.tick(self.k2[dal], t)
                    if f:
                        for r in self.ro:
                            C.inject(r, C.COMP_A if dal == 0 else C.COMP_B,
                                     FEED, t)
            fired_now = []
            for i in range(12):
                f, _, _, _ = C.tick(self.ro[i], t)
                if f:
                    ro_fire[i].append(t)
                    fired_now.append(i)
            for s in fired_now:
                for r in range(12):
                    if r != s:
                        C.inject(self.ro[r], C.COMP_ROOT, -INH, t)
        return ro_fire
