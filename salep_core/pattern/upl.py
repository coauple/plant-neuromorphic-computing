"""UPL agirlikli birim — UPL_SPEC.md §1. pl_core degismez.

30 sinaps (28 girdi + wP3A/B), quadratic kural §9.1 aynen,
RATE_WINDOW=30 halka sayaclar. RNG yok.
"""
import os
import sys as _sys
from collections import deque
ENC = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, ENC)
import pl_core as C

ETA, W_MAX, WIN, W0 = 0.3, 2.0, 30, 1.0


class QuadSyn(object):
    def __init__(self):
        self.w = W0
        self.pre = deque([0] * WIN, maxlen=WIN)
        self.post = deque([0] * WIN, maxlen=WIN)
        self.sp = 0
        self.so = 0

    def step(self, pre_bit, post_bit):
        self.sp += pre_bit - self.pre[0]
        self.so += post_bit - self.post[0]
        self.pre.append(pre_bit)
        self.post.append(post_bit)
        p, q = self.sp / WIN, self.so / WIN
        dw = ETA * min(p, q) * (p + q) ** 2 * (1.0 - (self.w / W_MAX) ** 2)
        self.w += dw
        return dw


class UplUnit(object):
    PARAMS = {"eta": ETA, "w_max": W_MAX, "win": WIN, "w0": W0}

    def __init__(self):
        self.frozen = False
        P1, P2, P3 = C.K1, C.K2, C.K3
        mk = lambda P: C.make_neuron(P["root_leak"], P["bra"], P["brb"],
                                     P["root_gd"], P["bra_gd"], P["brb_gd"])
        self.k1 = [[mk(P1) for _ in range(12)] for _ in range(2)]
        self.k2 = [mk(P2), mk(P2)]
        self.k3 = [mk(P3), mk(P3)]
        self.p3 = mk(P1)
        # 28 girdi agirligi: k1[dal][slot] + k2/k3[dal]
        self.wk1 = [[QuadSyn() for _ in range(12)] for _ in range(2)]
        self.wk2 = [QuadSyn(), QuadSyn()]
        self.wk3 = [QuadSyn(), QuadSyn()]
        self.wp3 = [QuadSyn(), QuadSyn()]

    def _wunits(self):
        units = []
        for dal in (0, 1):
            for s in range(12):
                units.append((self.k1[dal][s], self.wk1[dal][s]))
            units.append((self.k2[dal], self.wk2[dal]))
            units.append((self.k3[dal], self.wk3[dal]))
        return units

    def tick(self, t, pulses):
        # pulses: [(dal, slot, amp)] ham surus. Her sinaps kendi
        # hedefini olcekler (pre = dal-hatti darbesi, post = birim).
        comp = {0: C.COMP_A, 1: C.COMP_B}
        inbits = {}
        for (dal, slot, a) in pulses:
            targets = [(self.k1[dal][slot], self.wk1[dal][slot])]
            for d in (-1, 1):
                s = (slot + d) % 12
                targets.append((self.k1[dal][s], self.wk1[dal][s]))
            if dal == 0:
                targets += [(self.k2[0], self.wk2[0]),
                            (self.k3[0], self.wk3[0])]
            else:
                targets += [(self.k2[1], self.wk2[1]),
                            (self.k3[1], self.wk3[1])]
            for (u, w) in targets:
                C.inject(u, comp[dal], a * w.w, t)
            inbits[dal] = inbits.get(dal, 0) + 1
        kf = []
        for (u, w) in self._wunits():
            dal = self._dal_of(u)
            f, _, _, _ = C.tick(u, t)
            if not self.frozen:
                w.step(1 if inbits.get(dal) else 0, 1 if f else 0)
            if f:
                kf.append(u)
        # K->P3: atesleyen K birimi, dali ayirt edilerek besler
        for u in kf:
            dal = self._dal_of(u)
            C.inject(self.p3, comp[dal], 1.0 * self.wp3[dal].w, t)
        f3, coinc, eff_g, soma = C.tick(self.p3, t)
        if not self.frozen:
            for dal in (0, 1):
                self.wp3[dal].step(
                    1 if any(self._dal_of(u) == dal for u in kf) else 0,
                    1 if f3 else 0)
        return kf, f3, coinc, eff_g, soma

    def _dal0(self):
        return set([id(self.k1[0][s]) for s in range(12)]
                   + [id(self.k2[0]), id(self.k3[0])])

    def _dal_of(self, u):
        return 0 if id(u) in self._dal0() else 1

    def weights(self):
        return {"wk1": [[w.w for w in row] for row in self.wk1],
                "wk2": [w.w for w in self.wk2],
                "wk3": [w.w for w in self.wk3],
                "wp3": [w.w for w in self.wp3]}

    def set_weights(self, d):
        for dal in (0, 1):
            for s in range(12):
                self.wk1[dal][s].w = d["wk1"][dal][s]
            self.wk2[dal].w = d["wk2"][dal]
            self.wk3[dal].w = d["wk3"][dal]
            self.wp3[dal].w = d["wp3"][dal]
        self.frozen = True
