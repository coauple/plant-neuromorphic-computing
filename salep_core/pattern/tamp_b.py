"""T-AMP Prototip B — temporal (T_AMP_SPEC.md §3).

Dal basina 12 roleli zincir (standart morfoloji). Slot-s, s
konumuna anatomik tap'lanir; sinyal s->..->11->P3 akar. Gecikme
spike hop'larindan dogar (CPU delay hesabi YOK). Role baglanti
genligi 2.0 (bilesen gerekcesi SPEC §3); P3 besleme 1.0.
"""
from tamp_common import tick_k, new_k_layer, HORIZON
import pl_core as C

CHAIN_AMP = 2.0
FEED_AMP = 1.0


def new_relay():
    # Entegrator rol (K3-usulu dusuk sizinti): role gorevi 1-spike
    # cevirmedir; rezonator morfolojisi bu gorevde sessiz (olculdu).
    P = C.K3
    return C.make_neuron(P["root_leak"], P["bra"], P["brb"],
                         P["root_gd"], P["bra_gd"], P["brb_gd"])


def relay_check():
    # Bilesen onkosulu: izole tek-darbe -> tam 1 spike; L olculur.
    r = new_relay()
    C.inject(r, C.COMP_A, CHAIN_AMP, 0)
    ticks = []
    for t in range(40):
        f, _, _, _ = C.tick(r, t)
        if f:
            ticks.append(t)
    assert len(ticks) == 1, f"role onkosulu tutmadi: {ticks}"
    return ticks[0]


class PrototypeB(object):
    PARAMS = {"chain": 12, "chain_amp": CHAIN_AMP, "feed_amp": FEED_AMP}

    def __init__(self):
        self.k = new_k_layer()
        self.ch = [[new_relay() for _ in range(12)] for _ in range(2)]
        self.p3 = C.make_neuron(0.08, 0.06, 0.04, 0.005, 0.004, 0.003)

    def run(self, sched):
        soma_tr, eff_tr, fire, n_in = [], [], [], 0
        chain_out = {0: [], 1: []}
        for t in range(HORIZON):
            kf = tick_k(self.k, t, sched)
            for (dal, name, s) in kf:
                if name == "k1":
                    C.inject(self.ch[dal][s], C.COMP_A, CHAIN_AMP, t)
                else:
                    C.inject(self.p3,
                             C.COMP_A if dal == 0 else C.COMP_B, FEED_AMP, t)
                    n_in += 1
            # TERS sira (11->0): one cikan hop ayni tick'te zinciri
            # sifir-gecikmeyle bosaltmasin; her hop tam 1 tick gecikir.
            for dal in (0, 1):
                for i in range(11, -1, -1):
                    f, _, _, _ = C.tick(self.ch[dal][i], t)
                    if f:
                        if i < 11:
                            C.inject(self.ch[dal][i + 1], C.COMP_A,
                                     CHAIN_AMP, t)
                        else:
                            C.inject(self.p3,
                                     C.COMP_A if dal == 0 else C.COMP_B,
                                     FEED_AMP, t)
                            n_in += 1
                            chain_out[dal].append(t)
            f, coinc, eff_g, soma = C.tick(self.p3, t)
            soma_tr.append(soma)
            eff_tr.append(eff_g)
            if f:
                fire.append(t)
        return {"soma_tr": soma_tr, "eff_tr": eff_tr, "fire": fire,
                "n_in": n_in, "n_fires": len(fire),
                "max_soma": max(soma_tr), "max_eff": max(eff_tr),
                "chain_out": chain_out}
