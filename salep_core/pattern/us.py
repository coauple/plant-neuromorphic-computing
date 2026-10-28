"""US birimi — US_SPEC.md §1. upl.py/pl_core degismez (import).

Sinif->dal eslemesi (K3->Dal-A, K1+K2->Dal-B) + ablasyonlu izdusum.
INH YOK. Ogrenme KAPALI (donuk agirliklar). RNG yok.
"""
import os
import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)
import pl_core as C
import upl as U


class UsUnit(object):
    PARAMS = {"dal_map": {"A": "K3", "B": ["K1", "K2"]}}

    def __init__(self, weights):
        self.u = U.UplUnit()
        self.u.set_weights(weights)  # frozen=True

    def run(self, sched, allow, horizon=300):
        p3fires = []
        for t in range(horizon):
            kf, _, _, _, _ = self.u.tick(t, sched.get(t, ()))
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
                    C.inject(self.u.p3, C.COMP_A,
                             1.0 * self.u.wp3[0].w, t)
                else:
                    C.inject(self.u.p3, C.COMP_B,
                             1.0 * self.u.wp3[1].w, t)
            f3, _, _, _ = C.tick(self.u.p3, t)
            if f3:
                p3fires.append(t)
        return p3fires
