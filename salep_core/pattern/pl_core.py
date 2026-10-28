"""PatternUnit float ikizi — P0_SPEC.md §2/§3 tek dogruluk kaynagi.

`neuron.h` + `compartment.h` satir karsiliklari her blogun basinda.
RNG YOK. sim/encoder/web bagi YOK (stdlib disi import yok).
"""

DIFF = 0.15
THR = 1.0
V_REST = 0.0
V_RESET = -0.2
G_ACT = 0.15
G_INC = 0.2
WIN = 10
BONUS = 0.8

COMP_ROOT, COMP_A, COMP_B = 0, 1, 2


class Neuron(object):
    def __init__(self, leaks, gdecays, tau_isi=0, bw=0, plir_mode=0):
        # neuron_init / neuron_init_with_params karsiligi
        self.V = [V_REST, V_REST, V_REST]
        self.leak = list(leaks)          # [root, brA, brB]
        self.gdecay = list(gdecays)
        self.g = [0.0, 0.0, 0.0]
        self.parent = [-1, 0, 0]
        self.children = ([1, 2], [], [])
        self.A_last = -1
        self.B_last = -1
        self.tau_isi = tau_isi
        self.bw = bw
        self.plir_mode = plir_mode
        self.last_res_A = -1
        self.last_wire_A = -1
        self.soma = V_REST
        self.n_fired = 0


def make_neuron(root_leak, bra_leak, brb_leak, root_gd, bra_gd, brb_gd,
                tau_isi=0, bw=0, plir_mode=0):
    return Neuron((root_leak, bra_leak, brb_leak),
                  (root_gd, bra_gd, brb_gd),
                  tau_isi, bw, plir_mode)


def inject(n, comp, cur, t):
    # neuron_inject_current karsiligi (Dal A PLIR / ISI / kapisiz + Dal B duz)
    if comp == COMP_A and n.plir_mode != 0:
        if n.tau_isi <= 0 or n.bw <= 0:
            n.last_res_A = t
            n.V[comp] += cur
            n.A_last = t
            return True
        lock = 2 * n.tau_isi + n.bw
        if n.last_res_A < 0 or (t - n.last_res_A) > lock:
            n.last_res_A = t
            n.V[comp] += cur
            n.A_last = t
            return True
        isi = t - n.last_res_A
        diff = abs(isi - n.tau_isi)
        if diff >= n.bw:
            return False  # REDDET: ref korunur, voltaj + coincidence yok
        mu = (n.bw - diff) / n.bw
        n.last_res_A = t
        if mu <= 0:
            return False
        n.V[comp] += cur * mu
        n.A_last = t
        return True
    if comp == COMP_A and n.tau_isi > 0 and n.bw > 0:
        mu = 1.0
        if n.last_wire_A >= 0:
            isi = t - n.last_wire_A
            diff = abs(isi - n.tau_isi)
            mu = 0.0 if diff >= n.bw else (n.bw - diff) / n.bw
        n.last_wire_A = t
        if mu <= 0:
            return False
        n.V[comp] += cur * mu
        n.A_last = t
        return True
    n.V[comp] += cur
    if comp == COMP_A:
        n.A_last = t
        n.last_wire_A = t
    if comp == COMP_B:
        n.B_last = t
    return True


def tick(n, t):
    # neuron_tick karsiligi: difuzyon (snapshot) -> sizinti -> gating ->
    # soma + bonus -> atesleme. Donus: (fired, coinc, eff_g, soma_reset_oncesi)
    snap = (n.V[0], n.V[1], n.V[2])
    for i in range(3):
        if n.parent[i] >= 0:
            n.V[i] += DIFF * (snap[n.parent[i]] - n.V[i])
        for c in n.children[i]:
            n.V[i] += DIFF * (snap[c] - n.V[i])
    for i in range(3):  # compartment_apply_leak: V -= leak*(V-V_REST)
        n.V[i] -= n.leak[i] * (n.V[i] - V_REST)
    for i in range(3):  # compartment_update_gating
        if n.V[i] > G_ACT:
            n.g[i] += G_INC
        n.g[i] -= n.gdecay[i] * n.g[i]
        if n.g[i] < 0.0:
            n.g[i] = 0.0
    a_in = n.A_last >= 0 and (t - n.A_last) <= WIN
    b_in = n.B_last >= 0 and (t - n.B_last) <= WIN
    coinc = a_in and b_in
    eff_g = n.g[0] + (BONUS if coinc else 0.0)
    soma = n.V[0] * (1.0 + eff_g)
    n.soma = soma
    if soma > THR:
        n.n_fired += 1
        for i in range(3):
            n.V[i] = V_RESET
        n.soma = V_RESET
        return True, coinc, eff_g, soma
    return False, coinc, eff_g, soma


# --- K kanallari: farkliligin tamami (P0_SPEC.md §3) -------------------------
# Yazmayan alanlar neuron_init ontanimi.
K1 = dict(root_leak=0.08, bra=0.06, brb=0.04,
          root_gd=0.005, bra_gd=0.004, brb_gd=0.003)
K2 = dict(root_leak=0.08, bra=0.10, brb=0.04,
          root_gd=0.010, bra_gd=0.004, brb_gd=0.003)
K3 = dict(root_leak=0.08, bra=0.02, brb=0.04,
          root_gd=0.002, bra_gd=0.004, brb_gd=0.003)

TAU_GRID = (2, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24, 30)


def _k_neuron(P, tau_isi=0, bw=0, plir_mode=0):
    return make_neuron(P["root_leak"], P["bra"], P["brb"],
                       P["root_gd"], P["bra_gd"], P["brb_gd"],
                       tau_isi, bw, plir_mode)


class PatternUnit(object):
    def __init__(self, mode, tau=0):
        # mode: "ring" (K1 tau=0) ya da "resonant" (K1 tau=tau, plir=1, bw=1)
        # Resonant kosuda 24 K1 noronu da AYNI tau'yu tasir (SPEC §3).
        self.k1 = [[_k_neuron(K1) for _ in range(12)] for _ in range(2)]
        if mode == "resonant":
            self.k1 = [[_k_neuron(K1, tau, 1, 1) for _ in range(12)]
                       for _ in range(2)]
        elif mode != "ring":
            raise ValueError("mode ring/resonant olmali")
        self.k2 = [_k_neuron(K2), _k_neuron(K2)]
        self.k3 = [_k_neuron(K3), _k_neuron(K3)]
        self.p3 = make_neuron(0.08, 0.06, 0.04, 0.005, 0.004, 0.003)
        self.mode = mode
        self.tau = tau


def inject_phase(u, dal, slot, amp, w_ring, t):
    # Faz darbesi -> K bankasi (paralel, seri degil). comp: dal A->1, B->2.
    comp = COMP_A if dal == 0 else COMP_B
    inject(u.k1[dal][slot % 12], comp, amp, t)
    if w_ring != 0.0:
        inject(u.k1[dal][(slot - 1) % 12], comp, amp * w_ring, t)
        inject(u.k1[dal][(slot + 1) % 12], comp, amp * w_ring, t)
    inject(u.k2[dal], comp, amp, t)
    inject(u.k3[dal], comp, amp, t)


def step(u, t, amp_k=1.0):
    # Basamak: K katmani tick -> atesleyenler P3'e -> P3 tick (ayni t).
    k_fires = []
    for dal in (0, 1):
        for s in range(12):
            f, _, _, _ = tick(u.k1[dal][s], t)
            if f:
                k_fires.append((dal, "k1", s))
        for name, arr in (("k2", u.k2), ("k3", u.k3)):
            f, _, _, _ = tick(arr[dal], t)
            if f:
                k_fires.append((dal, name, -1))
    for (dal, _, _) in k_fires:
        inject(u.p3, COMP_A if dal == 0 else COMP_B, amp_k, t)
    fired, coinc, eff_g, soma = tick(u.p3, t)
    return k_fires, fired, coinc, eff_g, soma


def run_condition(mode, tau, phi_a_deg, phi_b_deg, dt, order="AB",
                  w_ring=0.2, amp=1.0, single=None, t0=50, horizon=200):
    # Tek P0 kosusu. Donus: dict iz (P3 soma/eff_g/coinc/ates + K ates).
    assert phi_a_deg % 30 == 0 and phi_b_deg % 30 == 0
    assert order in ("AB", "BA")
    u = PatternUnit(mode, tau)
    sa, sb = (phi_a_deg // 30) % 12, (phi_b_deg // 30) % 12
    sched = {}
    if single in (None, "B"):
        sched.setdefault(t0 if order == "AB" else t0 + dt, []).append(
            (0, sa, amp))
    if single in (None, "A"):
        sched.setdefault(t0 + dt if order == "AB" else t0, []).append(
            (1, sb, amp))
    soma_tr, eff_tr, coinc_tr, fire_tr, k_n = [], [], [], [], 0
    for t in range(horizon):
        for (dal, slot, a) in sched.get(t, ()):
            inject_phase(u, dal, slot, a, w_ring, t)
        k_fires, fired, coinc, eff_g, soma = step(u, t)
        k_n += len(k_fires)
        soma_tr.append(soma)
        eff_tr.append(eff_g)
        coinc_tr.append(1 if coinc else 0)
        fire_tr.append(1 if fired else 0)
    return {"fire_ticks": [t for t, f in enumerate(fire_tr) if f],
            "n_fires": sum(fire_tr),
            "max_soma": max(soma_tr),
            "max_eff_g": max(eff_tr),
            "n_coinc": sum(coinc_tr),
            "k_fires": k_n,
            "soma_tr": soma_tr,
            "eff_tr": eff_tr}


# --- PatternUnitV2: 7-kompartmanlı P3x float aynası (Faz 3, eklemeli) --------
# pattern_unit_v2.h karşılığı: p3x_init / p3x_inject / p3x_tick + S5 kablolama.
# RNG YOK. Mevcut PatternUnit/kapılar DEGISTIRILMEDI.
P3X_ROOT, P3X_A_K1, P3X_A_K2, P3X_A_K3 = 0, 1, 2, 3
P3X_B_K1, P3X_B_K2, P3X_B_K3 = 4, 5, 6
P3X_N, P3X_OPEN = 29, -1
P3X_LEAK = (0.08, 0.06, 0.10, 0.02, 0.04, 0.04, 0.04)
P3X_GD = (0.005, 0.004, 0.010, 0.002, 0.003, 0.003, 0.003)
S5_CENTERS = (1, 4, 7, 5, 6, 0)  # P3a..P3f (P3f ZAYIF); P3g.. OPEN


class P3xNeuron(object):
    def __init__(self):
        # p3x_init karsiligi
        self.V = [V_REST] * 7
        self.g = [0.0] * 7
        self.A_last = -1
        self.B_last = -1
        self.soma = V_REST
        self.n_fired = 0


def p3x_inject(n, k, cur, t):
    # p3x_inject karsiligi: K-kompartmanına dıs akım + dal girdi-zamanı
    n.V[k] += cur
    if 1 <= k <= 3:
        n.A_last = t
    elif 4 <= k <= 6:
        n.B_last = t


def p3x_tick(n, t):
    # p3x_tick karsiligi: yıldız difüzyon (root-once) -> sızıntı -> gating ->
    # soma + bonus -> ates. Donus: (fired, coinc, eff_g, soma_reset_oncesi)
    snap = tuple(n.V)
    for k in range(1, 7):  # root, 6 K-snap'ine sırayla
        n.V[0] += DIFF * (snap[k] - n.V[0])
    for k in range(1, 7):  # her K, root snap'ine
        n.V[k] += DIFF * (snap[0] - n.V[k])
    for i in range(7):
        n.V[i] -= P3X_LEAK[i] * (n.V[i] - V_REST)
    for i in range(7):
        if n.V[i] > G_ACT:
            n.g[i] += G_INC
        n.g[i] -= P3X_GD[i] * n.g[i]
        if n.g[i] < 0.0:
            n.g[i] = 0.0
    a_in = n.A_last >= 0 and (t - n.A_last) <= WIN
    b_in = n.B_last >= 0 and (t - n.B_last) <= WIN
    coinc = a_in and b_in
    eff_g = n.g[0] + (BONUS if coinc else 0.0)
    soma = n.V[0] * (1.0 + eff_g)
    n.soma = soma
    if soma > THR:
        n.n_fired += 1
        for i in range(7):
            n.V[i] = V_RESET
        n.soma = V_RESET
        return True, coinc, eff_g, soma
    return False, coinc, eff_g, soma


def v2_drive(events, max_tick):
    # Gercek kablo surusu (main_pattern_unit_v2.cpp aynası, float).
    # events: [(tick, post_id)] listesi. Donus: {unit: [ates tickleri]}.
    # Agirlik w0=1.0 sabit (I = 1.0*0.5); halka 0.2x; ogrenme YOK (Faz 2 rejimi).
    CUR, RING = 0.5, 0.1
    units = [P3xNeuron() for _ in range(P3X_N)]
    by_tick = {}
    for (t, p) in events:
        by_tick.setdefault(t, []).append(p)
    fires = {i: [] for i in range(P3X_N)}
    for t in range(max_tick + 1):
        for s in by_tick.get(t, ()):
            for i in range(6):  # P3a..P3f kablolu; P3g.. sessiz kapasite
                c = S5_CENTERS[i]
                if s == c:
                    p3x_inject(units[i], P3X_A_K1, CUR, t)
                elif s == (c - 1) % 12 or s == (c + 1) % 12:
                    p3x_inject(units[i], P3X_A_K1, RING, t)
                for k in (P3X_A_K2, P3X_A_K3, P3X_B_K2, P3X_B_K3):
                    p3x_inject(units[i], k, CUR, t)
        for i in range(P3X_N):
            f, _, _, _ = p3x_tick(units[i], t)
            if f:
                fires[i].append(t)
    return fires
