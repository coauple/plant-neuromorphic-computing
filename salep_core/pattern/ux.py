"""Tek-surus dogrulanmis hucre — uj2/us2 ortak (UN K-dongusuyle ayni).

K-dongusu un.py ile birebir (bit-esit K atesleri); P3 + INH tek
tick. UplUnit.tick KULLANILMAZ (cift-surus kaynagi). pl_core/upl
import, degisiklik yok. RNG yok.
"""
import os
import sys as _sys
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)
import pl_core as C
import upl as U


def classify(u, unit):
    d = u._dal_of(unit)
    if unit in [u.k1[d][s] for s in range(12)]:
        return "K1", d
    if unit is u.k2[d]:
        return "K2", d
    if unit is u.k3[d]:
        return "K3", d
    return None, d


def run_cell(weights, sched, allow, mode, use_inh, inh_amp=1.0,
             horizon=300):
    # mode "uj": koken-dal yonlendirme; "us": sinif->dal eslemesi.
    assert mode in ("uj", "us")
    u = U.UplUnit()
    u.set_weights(weights)  # frozen=True
    p3 = C.make_neuron(0.08, 0.06, 0.04, 0.005, 0.004, 0.003)
    inh = C.make_neuron(0.08, 0.06, 0.04, 0.005, 0.004, 0.003)
    comp = {0: C.COMP_A, 1: C.COMP_B}
    fires = []
    for t in range(horizon):
        for (dal, slot, a) in sched.get(t, ()):
            targets = [(u.k1[dal][slot], u.wk1[dal][slot])]
            for dd in (-1, 1):
                s = (slot + dd) % 12
                targets.append((u.k1[dal][s], u.wk1[dal][s]))
            targets += [(u.k2[dal], u.wk2[dal]),
                        (u.k3[dal], u.wk3[dal])]
            for (uu, w) in targets:
                C.inject(uu, comp[dal], a * w.w, t)
        kf = []
        for (uu, w) in u._wunits():
            f, _, _, _ = C.tick(uu, t)
            if f:
                kf.append(uu)
        routed = []
        for unit in kf:
            cls, d = classify(u, unit)
            if cls is None or cls not in allow:
                continue
            routed.append((cls, d))
        if use_inh:
            for (cls, d) in routed:
                if cls == "K3":
                    C.inject(inh, comp[d], 1.0, t)
            f_inh, _, _, _ = C.tick(inh, t)
        else:
            f_inh = False
        for (cls, d) in routed:
            if mode == "uj":
                C.inject(p3, comp[d], 1.0 * u.wp3[d].w, t)
            else:
                if cls == "K3":
                    C.inject(p3, C.COMP_A, 1.0 * u.wp3[0].w, t)
                else:
                    C.inject(p3, C.COMP_B, 1.0 * u.wp3[1].w, t)
        if use_inh and f_inh:
            C.inject(p3, C.COMP_ROOT, -inh_amp, t)
        f3, _, _, _ = C.tick(p3, t)
        if f3:
            fires.append(t)
    return fires
