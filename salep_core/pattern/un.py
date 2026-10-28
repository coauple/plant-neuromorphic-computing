"""UN birimi — UN_SPEC.md §1. upl.py/pl_core degismez (import).

K-tarafi upl.tick donuk-dal aynen; P3 = UnP3 (dal-basi doyan
iletim + pl_core tick). k=0 -> R==1 yapisal -> US ile ayni.
"""
import os
import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)
import pl_core as C
import upl as U

K_RES, R_REC = 0.5, 0.05


class UnP3(object):
    def __init__(self, k, r):
        self.n = C.make_neuron(0.08, 0.06, 0.04, 0.005, 0.004, 0.003)
        self.R = {C.COMP_A: 1.0, C.COMP_B: 1.0}
        self.rmin = {C.COMP_A: 1.0, C.COMP_B: 1.0}
        self.k, self.r = k, r

    def inject(self, comp, a, t):
        tr = a * self.R[comp]
        C.inject(self.n, comp, tr, t)
        self.R[comp] = max(0.0, self.R[comp] - self.k * a)
        self.rmin[comp] = min(self.rmin[comp], self.R[comp])

    def tick(self, t):
        for c in self.R:
            self.R[c] = min(1.0, self.R[c] + self.r)
        return C.tick(self.n, t)


class UnUnit(object):
    PARAMS = {"dal_map": {"A": "K3", "B": ["K1", "K2"]}}

    def __init__(self, weights, k, r):
        self.u = U.UplUnit()
        self.u.set_weights(weights)  # frozen=True (ogrenme yok)
        self.p3 = UnP3(k, r)

    def run(self, sched, allow, horizon=300):
        p3fires = []
        comp = {0: C.COMP_A, 1: C.COMP_B}
        for t in range(horizon):
            pulses = sched.get(t, ())
            inbits = {}
            for (dal, slot, a) in pulses:
                targets = [(self.u.k1[dal][slot],
                            self.u.wk1[dal][slot])]
                for d in (-1, 1):
                    s = (slot + d) % 12
                    targets.append((self.u.k1[dal][s],
                                    self.u.wk1[dal][s]))
                if dal == 0:
                    targets += [(self.u.k2[0], self.u.wk2[0]),
                                (self.u.k3[0], self.u.wk3[0])]
                else:
                    targets += [(self.u.k2[1], self.u.wk2[1]),
                                (self.u.k3[1], self.u.wk3[1])]
                for (uu, w) in targets:
                    C.inject(uu, comp[dal], a * w.w, t)
                inbits[dal] = inbits.get(dal, 0) + 1
            kf = []
            for (uu, w) in self.u._wunits():
                dal = self.u._dal_of(uu)
                f, _, _, _ = C.tick(uu, t)
                if f:
                    kf.append(uu)
            for unit in kf:
                d = self.u._dal_of(unit)
                if unit in [self.u.k1[d][s] for s in range(12)]:
                    cls = "K1"
                elif unit is self.u.k2[d]:
                    cls = "K2"
                elif unit is self.u.k3[d]:
                    cls = "K3"
                else:
                    continue
                if cls not in allow:
                    continue
                if cls == "K3":
                    self.p3.inject(C.COMP_A, 1.0 * self.u.wp3[0].w, t)
                else:
                    self.p3.inject(C.COMP_B, 1.0 * self.u.wp3[1].w, t)
            f3, _, _, _ = self.p3.tick(t)
            if f3:
                p3fires.append(t)
        return p3fires, {c: round(self.p3.rmin[c], 6) for c in self.p3.rmin}
