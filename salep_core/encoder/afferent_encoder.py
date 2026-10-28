"""AfferentSpikeEncoder v0.1 — SPEC_v0_1.md sozlesmesi.

NPU tarafi: stdlib-only, sim/web bagi YOK. Tamsayi aritmetigi; 1 olay
-> 1 spike (genisletme yok). Girdi post kimligi + tani tasi; cikti
iki kanal: phi_id (sabit adres) + phi_tau (tani).
"""

import csv

PHASE_SLOTS = 12
PHI_FULL_X100 = 36000
PHI_ID_STEP_X100 = 3000
TAU_LO = 4
TAU_HI_EXCL = 61
TAU_SPAN = 57

POST_TAU = (35, 45, 35, 36, 46, 26, 37, 37, 37, 37)


def _check_tick(tick):
    if not isinstance(tick, int) or isinstance(tick, bool):
        raise ValueError("tick int olmali")
    if tick < 0:
        raise ValueError("tick negatif olamaz")


def _check_post(post_id):
    if not isinstance(post_id, int) or isinstance(post_id, bool):
        raise ValueError("post_id int olmali")
    if post_id < 0 or post_id >= PHASE_SLOTS:
        raise ValueError("post_id aralik disi [0, PHASE_SLOTS)")


def _check_tau(tau_b):
    if not isinstance(tau_b, int) or isinstance(tau_b, bool):
        raise ValueError("tau_b int olmali")
    if tau_b < TAU_LO or tau_b >= TAU_HI_EXCL:
        raise ValueError("tau_b aralik disi [TAU_LO, TAU_HI_EXCL)")


def phi_id_of(post_id):
    _check_post(post_id)
    return post_id * PHI_ID_STEP_X100


def phi_tau_of(tau_b):
    _check_tau(tau_b)
    return ((tau_b - TAU_LO) * PHI_FULL_X100) // TAU_SPAN


def encode_event(tick, post_id, tau_b):
    _check_tick(tick)
    return (tick, phi_id_of(post_id), phi_tau_of(tau_b))


def encode_events(events):
    return [encode_event(t, p, b) for (t, p, b) in events]


def read_afferent_csv(path):
    events = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            events.append((int(row["tick"]), int(row["post_id"]),
                           int(row["tau_b"])))
    return events


def write_spikes_csv(path, spikes):
    with open(path, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(("tick", "phi_id_x100", "phi_tau_x100"))
        w.writerows(spikes)


def post_of_phi_id(phi_id_x100):
    return phi_id_x100 // PHI_ID_STEP_X100
