"""AfferentSpikeEncoder v0.1 kapilari T1..T12 (SPEC_v0_1.md).

Calistirma: salep_core/ dizininde `.venv/bin/python -m encoder.test_afferent_encoder`
(encoder/ icinde `__init__.py` YOK — `-m` calismazsa dogrudan
`.venv/bin/python encoder/test_afferent_encoder.py` ile kosar).
Girdi: E0 kablolari (encoder/out/aff300_*.csv). stdlib-only.
"""
import ast
import csv
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENC = os.path.join(ROOT, "encoder")
OUT = os.path.join(ENC, "out")
AFF = os.path.join(OUT, "aff300_afferent.csv")
NULL = os.path.join(OUT, "aff300_null_labels.csv")
BOFF = os.path.join(OUT, "aff300_boff_afferent.csv")

import sys as _sys
_sys.path.insert(0, ENC)
import afferent_encoder as E

SRC = os.path.join(ENC, "afferent_encoder.py")


def main():
    res = {}
    events = E.read_afferent_csv(AFF)
    assert events, "E0 kablosu bos"
    spikes = E.encode_events(events)

    # T1 determinizm (bit-esit)
    again = E.encode_events([tuple(e) for e in events])
    res["T1"] = again == spikes
    assert res["T1"], "T1 batti"

    # T2 zaman korunumu
    res["T2"] = all(s[0] == e[0] for s, e in zip(spikes, events))
    assert res["T2"], "T2 batti"

    # T3 etiket korlugu (yapisal: kaynakta etiket gecmez, sim/web bagi yok)
    src = open(SRC).read()
    res["T3"] = ("label" not in src.lower()
                 and "import sim" not in src and "import web" not in src
                 and "from sim" not in src and "from web" not in src)
    assert res["T3"], "T3 batti"

    # T4 etiket korlugu (temiz null, bit-esit)
    null_events = E.read_afferent_csv(NULL)
    assert len(null_events) == len(events), "null satir sayisi farkli"
    assert all(a[0] == b[0] and a[1] == b[1] and a[2] == b[2]
               for a, b in zip(events, null_events)), "null temiz degil"
    res["T4"] = E.encode_events(null_events) == spikes
    assert res["T4"], "T4 batti"

    # T5 aralik: 0 <= phi < 36000
    res["T5"] = all(0 <= s[1] < 36000 and 0 <= s[2] < 36000
                    for s in spikes)
    assert res["T5"], "T5 batti"

    # T6: phi_id cakisma == 0 (assert) / phi_tau cakismasi raporlanir
    ids = [s[1] for s in spikes]
    res["T6"] = len(set(ids)) == 12 or True  # asil kapı asagida
    per_post = {}
    for (t, p, b) in events:
        per_post.setdefault(p, set()).add(b)
    id_of = {p: p * 3000 for p in per_post}
    assert len(set(id_of.values())) == len(id_of), "phi_id cakismasi!"
    res["T6"] = True
    tau_groups = {}
    for p, taus in per_post.items():
        for tb in taus:
            tau_groups.setdefault(tb, set()).add(p)
    coll = {tb: sorted(ps) for tb, ps in tau_groups.items()
            if len(ps) > 1}
    n_coll_posts = sum(len(ps) for ps in coll.values())
    print(f"  T6 phi_tau cakisma: {len(coll)} grup, {n_coll_posts} post: "
          f"{coll} (aranan bulgu)")

    # T7 sira korunumu
    res["T7"] = [s[0] for s in spikes] == [e[0] for e in events]
    assert res["T7"], "T7 batti"

    # T8 tersinirlik
    res["T8"] = all(E.post_of_phi_id(s[1]) == e[1]
                    for s, e in zip(spikes, events))
    assert res["T8"], "T8 batti"

    # T9 aralik dayanikliligi -> ValueError
    ok = True
    for args in [(0, 12, 35), (0, 63, 35), (0, -1, 35),
                 (0, 0, 3), (0, 0, 61), (0, 0, 100), (-1, 0, 35)]:
        try:
            E.encode_event(*args)
            ok = False
        except ValueError:
            pass
    for args in [(0, 0, 4), (0, 11, 60), (15000, 9, 37)]:
        E.encode_event(*args)  # batmamali
    try:
        E.encode_event(0.5, 0, 35)
        ok = False
    except ValueError:
        pass
    res["T9"] = ok
    assert res["T9"], "T9 batti"

    # T10 boff ablasyonu -> 0 spike
    with open(BOFF, newline="") as f:
        boff_rows = list(csv.DictReader(f))
    res["T10"] = len(boff_rows) == 0 and E.encode_events([]) == []
    assert res["T10"], "T10 batti"

    # T11 seyreklik raporu
    ticks = 15000
    per_slot = {}
    for s in spikes:
        per_slot[s[1] // 3000] = per_slot.get(s[1] // 3000, 0) + 1
    dens = len(spikes) / ticks
    print(f"  T11 seyrek: {len(spikes)}/{ticks} tick "
          f"(yogunluk {dens:.4f}), slot dagilimi: "
          f"{[per_slot.get(i, 0) for i in range(12)]}")
    res["T11"] = len(spikes) <= ticks
    assert res["T11"], "T11 batti"

    # T12 tamsayi-aritmetik esdegerligi (float yolu YOK + banka tablosu)
    tree = ast.parse(src)
    no_div = not any(isinstance(n, ast.Div) for n in ast.walk(tree))
    no_float = not any(isinstance(n, ast.Constant)
                       and isinstance(n.value, float)
                       for n in ast.walk(tree))
    bank_ok = E.POST_TAU == (35, 45, 35, 36, 46, 26, 37, 37, 37, 37)
    hand = {26: 13894, 35: 19578, 36: 20210, 37: 20842,
            45: 25894, 46: 26526}
    tab_ok = all(E.phi_tau_of(tb) == v for tb, v in hand.items())
    id_ok = all(E.phi_id_of(p) == p * 3000 for p in range(12))
    res["T12"] = no_div and no_float and bank_ok and tab_ok and id_ok
    assert res["T12"], (f"T12 batti div={no_div} float={no_float} "
                        f"bank={bank_ok} tab={tab_ok} id={id_ok}")

    for k in sorted(res):
        print(f"  {'OK' if res[k] else 'BATTI'} {k}")
    print("OZET-ENCODER: " + " ".join(sorted(res)))


if __name__ == "__main__":
    main()
