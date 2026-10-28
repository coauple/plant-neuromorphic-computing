"""Elektro katman karakterizasyonu (§9.58): durum uzayi -> imza.

Tekil merdivenler (kuraklik / sicaklik / kok-yaprak hasari / yagmur /
sulama) + kombinasyonlar; her kosulda 29 gun yerlesme, 30. gun olcum:
zar potansiyeli (mV) + hat-0 hizi + hat-1 patlamasi + spike sayilari.

Yontem notu: EC/su-baskini cekirdekte kok hasari uzerinden gorundugu
icin kok-sagligi vekiliyle temsil edilir (deneysel esleme, model
iddiasi degil). Yagmur/sulama epizodiktir (yerlesme sonrasi tek gun).

Calistirma: .venv/bin/python validate_electro_sweep.py
Uretir: electro_sweep.csv
Olcutler (S1-S6): merdiven monotonluklari, olay patlamasi, imza
ayrisabilirligi (20 kosulda 16 ayri imza + 4 belgeli cakisma),
uctan-uca capalar.
"""
import csv
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

BASE = dict(temp=20.0, rain_mm=0.0, irrig_mm=0.0, water_balance=0.0,
            leaf_health=100.0, root_health=100.0, stage_name="VEGETATIVE",
            master_seed=7)
SET = 29

CONDS = [
    ("normal", None, None),
    ("hafif_kurak", dict(water_balance=-0.5), None),
    ("orta_kurak", dict(water_balance=-1.0), None),
    ("siddetli_kurak", dict(water_balance=-2.0), None),
    ("sicak30", dict(temp=30.0), None),
    ("sicak35", dict(temp=35.0), None),
    ("sicak40", dict(temp=40.0), None),
    ("soguk2", dict(temp=2.0), None),
    ("kok80", dict(root_health=80.0), None),
    ("kok50", dict(root_health=50.0), None),
    ("kok20", dict(root_health=20.0), None),
    ("yaprak50", dict(leaf_health=50.0), None),
    ("yagmur8", None, dict(rain_mm=8.0)),
    ("yagmur30", None, dict(rain_mm=30.0)),
    ("sulama10", None, dict(irrig_mm=10.0)),
    ("su_baskini", dict(root_health=70.0), dict(rain_mm=60.0)),
    ("k35_kurak", dict(temp=35.0, water_balance=-1.5), None),
    ("k40_kurak_kok", dict(temp=40.0, water_balance=-1.5,
                            root_health=50.0), None),
    ("isi_kurak_ec", dict(temp=35.0, water_balance=-1.5,
                           root_health=50.0, leaf_health=70.0), None),
    ("nem_baski", dict(root_health=70.0, water_balance=0.3),
     dict(rain_mm=30.0)),
]

# Belgeli korlukler (imza cakismasi — model siniri, §9.58):
# yaprak/kok hasar ayirimi yok; yagmur siddeti kodlanmaz (yalniz baslangic);
# baski/baskin ozdes; 30°C esik alti.
KNOWN_COLLISIONS = [
    frozenset(("kok50", "yaprak50")),
    frozenset(("yagmur8", "yagmur30")),
    frozenset(("su_baskini", "nem_baski")),
    frozenset(("normal", "sicak30")),
]


def measure(name, background=None, stimulus=None):
    from sim.electro import ElectroState
    el = ElectroState()
    bg = dict(BASE)
    bg.update(background or {})
    for d in range(SET):
        el.step(day=d, **bg)
    args = dict(bg)
    args.update(stimulus or {})
    v, r0, b1 = el.step(day=SET, **args)
    sp = el.spikes_for_day(r0, b1, 7, SET)
    return {"kosul": name, "V_mV": round(v, 1), "rate0": round(r0, 2),
            "burst1": round(b1, 2), "n0": len(sp[0]),
            "n1": tuple(sorted(sp[1]))}


def main():
    rows = [measure(n, bg, st) for n, bg, st in CONDS]
    with open(os.path.join(ROOT, "electro_sweep.csv"), "w",
              newline="") as f:
        w = csv.DictWriter(f, fieldnames=["kosul", "V_mV", "rate0",
                                          "burst1", "n0", "n1"])
        w.writeheader()
        w.writerows(rows)
    by = {r["kosul"]: r for r in rows}
    for r in rows:
        print(f"{r['kosul']:14s} V={r['V_mV']:7.1f} h0={r['rate0']:5.2f} "
              f"b1={r['burst1']:.1f} n0={r['n0']:2d} n1={list(r['n1'])}")

    ok = []
    dr = [by[k]["rate0"] for k in ("normal", "hafif_kurak", "orta_kurak",
                                   "siddetli_kurak")]
    ok.append(("S1 kuraklik_monoton",
               all(b >= a for a, b in zip(dr, dr[1:])) and dr[-1] > 20))
    tr = [by[k]["rate0"] for k in ("normal", "sicak35", "sicak40")]
    ok.append(("S2 sicaklik_monoton",
               tr[1] > tr[0] and tr[2] > tr[1]))
    kr = [by[k]["rate0"] for k in ("kok80", "kok50", "kok20")]
    ok.append(("S3 hasar_monoton",
               all(b >= a for a, b in zip(kr, kr[1:]))))
    ev = all(by[k]["n1"] and not by[k]["n0"]
             for k in ("yagmur8", "yagmur30", "sulama10"))
    ok.append(("S4 olay_patlamasi", bool(ev)))

    sig = {}
    for r in rows:
        key = (r["V_mV"], r["rate0"], r["burst1"], r["n0"], r["n1"])
        sig.setdefault(key, []).append(r["kosul"])
    dupes = sorted([sorted(v) for v in sig.values() if len(v) > 1])
    known = sorted([sorted(s) for s in KNOWN_COLLISIONS])
    ok.append(("S5 ayrisabilirlik_16_20",
               len(sig) == 16 and dupes == known))
    if dupes != known:
        print(f"  cakisma farki: {dupes}")

    from sim.world_state import WorldState
    from sim.electro import ElectroState
    w = WorldState(seed=1, start_day=0)
    evm = {d: {"force_no_rain": True} for d in range(55, 115)}
    evm[110] = {"force_no_rain": True, "fertilizer_dose_mass": 130.0}
    w.inject_scenario(evm)
    anchor = {}
    for d in range(0, 116):
        w.clock.sim_day = d
        w.clock.day_frac = 0.5
        w.step_if_needed()
        if d in (50, 115):
            s = w.get_snapshot()
            p = w.plant
            el = ElectroState()
            _, r0, _ = el.step(
                s["temp"], s["rain_mm"], s["applied_irrigation_mm"],
                p.water_balance, p.leaf_health, p.root_health,
                p.stage.name, 1, d)
            anchor[d] = r0
    print(f"  capa: saglikli-gun50 h0={anchor[50]:.1f}, "
          f"felaket-gun115 h0={anchor[115]:.1f}")
    ok.append(("S6 uctan_uca_capa",
               anchor[50] < 3.0 < anchor[115]))

    bad = [k for k, v in ok if not v]
    for k, v in ok:
        print(f"  {'OK' if v else 'BATTI'} {k}")
    if bad:
        raise SystemExit(f"BATTI: {bad}")
    print("OZET-ELECTRO-SWEEP: " + " ".join(k for k, _ in ok))


if __name__ == "__main__":
    main()
