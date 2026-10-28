"""IDEN mekanizmasi — IDEN_SPEC.md §1. Yalniz K1->readout + dagitik WTA.

pl_core.py'yi import eder, degistirmez. K2/K3 YOK (asama 1).
RNG yok. Inhibisyon: atesleyen readout diger 11'inin KOKune -INH.
"""
import os
import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)
import pl_core as C

N_PULSE, ISI, W_RING, T0, HORIZON = 5, 12, 0.2, 50, 200
FEED = 1.0
INH = 1.0


def new_k1():
    P = C.K1
    return [[C.make_neuron(P["root_leak"], P["bra"], P["brb"],
                           P["root_gd"], P["bra_gd"], P["brb_gd"])
             for _ in range(12)] for _ in range(2)]


def new_readout():
    return C.make_neuron(0.08, 0.06, 0.04, 0.005, 0.004, 0.003)


def ring_inject(k1, dal, slot, amp, t):
    # K1-only halka enjeksiyonu (K2/K3 YOK).
    comp = C.COMP_A if dal == 0 else C.COMP_B
    C.inject(k1[dal][slot % 12], comp, amp, t)
    if W_RING != 0.0:
        C.inject(k1[dal][(slot - 1) % 12], comp, amp * W_RING, t)
        C.inject(k1[dal][(slot + 1) % 12], comp, amp * W_RING, t)


class IdenUnit(object):
    PARAMS = {"feed": FEED, "inh": INH, "tick_order": "0..11",
              "inh_target": "root"}

    def __init__(self):
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
            for s in fired_now:
                for r in range(12):
                    if r != s:
                        C.inject(self.ro[r], C.COMP_ROOT, -INH, t)
        return ro_fire
