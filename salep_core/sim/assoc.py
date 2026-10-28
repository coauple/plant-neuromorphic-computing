"""Association cekirdegi — zaman-bagimli oruntu ayirimi (ogrenmesiz).

Girdi: afferent kablo (tick, post_id, tau_b, a0/a1lag, bwin, label, w).
Gorev dagilimi (kullanici karari): A = aktif durum surekliligi,
B/P2 = baglam/kosul kimligi, association = bunlarin zaman-iliskisi.

Yontem: gun-penceresi imzasi = (atesleyen postlar, aktif B hatlari,
aktif A hatlari); benzerlik = agirlikli Jaccard (0.5/0.3/0.2).
Siniflandirma: leave-one-out 1-NN. Etiket: yalniz-gercek / yalniz-decoy
/ karisik (banka tanimindan; ogrenme YOK, yalniz ayirt-etme).

Persistence/FDM parametrelerine DOKUNULMAZ — bu katman kabloyu okur.
Yalniz stdlib.
"""

REALS = frozenset((0, 1, 2, 5, 6, 7, 8, 9))
DECOY = frozenset((3, 4))
W_POST, W_BLINE, W_A = 0.5, 0.3, 0.2


def window_label(posts):
    r = posts & REALS
    d = posts & DECOY
    if r and d:
        return "mixed"
    if r:
        return "true"
    if d:
        return "decoy"
    return "silent"


def build_windows(records, ticks_per_day=50):
    """Kablo kayitlari -> gun: {posts, blines, a}."""
    wins = {}
    for r in records:
        d = int(r["tick"]) // ticks_per_day
        w = wins.setdefault(d, {"posts": set(), "blines": set(),
                                "a": set()})
        w["posts"].add(int(r["post_id"]))
        for k, ch in enumerate(r["bwin"]):
            if ch == "1":
                w["blines"].add(k)
        if int(r["a0lag"]) >= 0:
            w["a"].add(0)
        if int(r["a1lag"]) >= 0:
            w["a"].add(1)
    return wins


def _jaccard(a, b):
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def similarity(wa, wb):
    """Imza benzerligi 0..1 (post + B-hatti + A)."""
    return (W_POST * _jaccard(wa["posts"], wb["posts"])
            + W_BLINE * _jaccard(wa["blines"], wb["blines"])
            + W_A * _jaccard(wa["a"], wb["a"]))


def nearest_neighbor(days, wins, day):
    """Leave-one-out en yakin gun (gun, benzerlik)."""
    best, bs = None, -1.0
    for o in days:
        if o == day:
            continue
        s = similarity(wins[day], wins[o])
        if s > bs:
            best, bs = o, s
    return best, bs


def classify(days, wins):
    """Her gun -> (tahmin_etiket, komsu_gun, benzerlik, gercek_etiket)."""
    out = {}
    for d in days:
        nb, s = nearest_neighbor(days, wins, d)
        out[d] = (window_label(wins[nb]["posts"]), nb, s,
                  window_label(wins[d]["posts"]))
    return out


def backward_chain(day, wins, records_by_day):
    """Kararin geriye-izi: komsu gunun A-B-P2 olaylari."""
    lines = []
    for r in records_by_day.get(day, []):
        lines.append(
            f"t={r['tick']} P{r['post_id']}(tau{r['tau_b']}) "
            f"A=({r['a0lag']},{r['a1lag']}) B={r['bwin']} "
            f"{r['label']} w={r['w']}")
    return lines
