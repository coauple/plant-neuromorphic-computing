"""UJ birimi — UJ_SPEC.md §1. upl.py degismez (import).

Egitilmis agirliklar (donuk) + INH ara-noronu + ablasyonlu
izdusum. Ogrenme KAPALI. RNG yok.
"""
import os
import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)
import pl_core as C
import upl as U

INH_AMP = 1.0


def new_inh():
    return C.make_neuron(0.08, 0.06, 0.04, 0.005, 0.004, 0.003)


class UjUnit(object):
    PARAMS = {"inh_amp": INH_AMP, "learning": False}

    def __init__(self, weights):
        self.u = U.UplUnit()
        self.u.set_weights(weights)  # frozen=True
        self.inh = new_inh()

    def run(self, sched, allow, horizon=300):
        # allow: {"K1","K2","K3"} alt-kumesi izdusume gecer.
        p3fires = []
        for t in range(horizon):
            kf, _, _, _, _ = self.u.tick(t, sched.get(t, ()))
            by_cls = {"K1": [], "K2": [], "K3": []}
            for unit in kf:
                d = self.u._dal_of(unit)
                if unit in [self.u.k1[d][s] for s in range(12)]:
                    by_cls["K1"].append((unit, d))
                elif unit is self.u.k2[d]:
                    by_cls["K2"].append((unit, d))
                elif unit is self.u.k3[d]:
                    by_cls["K3"].append((unit, d))
            for (unit, d) in by_cls["K3"]:
                if "K3" in allow:
                    C.inject(self.inh, C.COMP_A if d == 0 else C.COMP_B,
                             1.0, t)
            f_inh, _, _, _ = C.tick(self.inh, t)
            for cls in ("K1", "K2", "K3"):
                if cls in allow:
                    for (unit, d) in by_cls[cls]:
                        C.inject(self.u.p3,
                                 C.COMP_A if d == 0 else C.COMP_B,
                                 1.0 * self.u.wp3[d].w, t)
            if f_inh:
                C.inject(self.u.p3, C.COMP_ROOT, -INH_AMP, t)
            f3, _, _, _ = C.tick(self.u.p3, t)
            if f3:
                p3fires.append(t)
        return p3fires
