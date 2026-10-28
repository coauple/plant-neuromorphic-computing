"""T-AMP Prototip A — spatial (T_AMP_SPEC.md §2).

12 readout (standart morfoloji, P0b P3 parametreleri). Readout-s:
Dal-A <- k1A[s], Dal-B <- k1B[s] (+ K2/K3 ortak-kip, amp 1.0).
Gozlenen durum = 12 soma izi + ates matrisi. Etiket yok.
"""
from tamp_common import tick_k, new_k_layer, HORIZON
import pl_core as C


def new_readout():
    return C.make_neuron(0.08, 0.06, 0.04, 0.005, 0.004, 0.003)


class PrototypeA(object):
    PARAMS = {"n_readout": 12, "feed_amp": 1.0, "common_k2k3": True}

    def __init__(self):
        self.k = new_k_layer()
        self.ro = [new_readout() for _ in range(12)]

    def run(self, sched):
        soma_tr = [[] for _ in range(12)]
        fire = [[] for _ in range(12)]
        n_in = 0
        for t in range(HORIZON):
            kf = tick_k(self.k, t, sched)
            for (dal, name, s) in kf:
                n_in += 1
                if name == "k1":
                    C.inject(self.ro[s], C.COMP_A if dal == 0 else C.COMP_B,
                             1.0, t)
                else:
                    for r in self.ro:
                        C.inject(r, C.COMP_A if dal == 0 else C.COMP_B,
                                 1.0, t)
            for i, r in enumerate(self.ro):
                f, _, _, soma = C.tick(r, t)
                soma_tr[i].append(soma)
                if f:
                    fire[i].append(t)
        return {"soma_tr": soma_tr, "fire": fire, "n_in": n_in,
                "n_fires": sum(len(v) for v in fire)}
