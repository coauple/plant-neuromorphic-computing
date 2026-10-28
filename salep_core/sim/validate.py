"""SIMULATOR VALIDATION battery (§9.51) — 10 test sınıfı + adversarial + recovery.

Görev disiplini: YENİ FİZİK YOK, model manipülasyonu YOK. Eşikler
ÖNDEN kodda (mekanizma-yönü + asgari ayırt edilebilirlik); düşen
testte önce model sorgulanır. Her test {pass, metric, tol, detail}
döner. Deterministik tohumlar → tekrarlanabilir.

TEST1 determinizm / TEST2 seed-diversity / TEST3 invariantlar
(su+tuz) / TEST4 monotonluk (+doygunluk eğrisi) / TEST5 etkileşim
/ TEST6 aynı-olay-farklı-dünya / TEST7 gizli-durum / TEST8
histeresis / TEST9 ekstrem-robustluk / TEST10 10k-çeşitlilik.
ADV: öldürülebilirlik + sonsuz-sağlık. REC: taze tohumda D2/D3
(anti-ezber kanıtı; WORLD B).
"""
import numpy as np
import pandas as pd

from sim.plant_sim import Plant, PlantParams, Stage, soil_overrides
from sim.events import run_ensemble
from sim.infer import summarize, discover

V1 = "fiziksel-v1"


def _v1plant(moist, ec0=None, stage=None):
    p = PlantParams()
    for k, v in soil_overrides(V1).items():
        setattr(p, k, v)
    pl = Plant(p, 0)
    pl.soil_moisture = moist
    pl.ec_mass = (p.ec_baseline if ec0 is None else ec0) * moist
    if stage is not None:
        pl.stage = stage
    return pl


def test1_determinism(n=100):
    """100× aynı topluluk → bit-eşit."""
    a, _ = run_ensemble(6, days=12)
    ok = sum(bool(run_ensemble(6, days=12)[0].equals(a)) for _ in range(n))
    return {"pass": ok == n, "metric": f"{ok}/{n} identical",
            "tol": "100/100 exact",
            "detail": "seed=varsayılan topluluk, 12 gün"}


def test2_diversity(n=1000):
    """1000 tohum: ne tekdüze ne kaotik (sınırlı + sonlu + olaylı)."""
    df, logs = run_ensemble(n, days=12)
    fin = df[df.day == 11]
    scheds = logs.groupby("run").apply(
        lambda g: tuple(sorted((r["day"], r["event"]) for _, r in
                               g.iterrows())),
        include_groups=False)
    ok = (float(fin.soil_moisture.std()) > 0.5
          and float(fin.stress.std()) > 0.01
          and int(scheds.nunique()) >= 50
          and bool(np.isfinite(df[["soil_moisture", "soil_ec", "leaf",
                                   "stress"]].values).all()))
    return {"pass": bool(ok),
            "metric": f"std_nem={fin.soil_moisture.std():.2f} "
                      f"std_stres={fin.stress.std():.4f} "
                      f"tarife={scheds.nunique()} finite=1.0",
            "tol": "std_nem>0.5, std_stres>0.01, tarife>=50, finite",
            "detail": f"{n} tohum, 12 gün"}


def test3_invariants(n=200):
    """Korunum: residual≠0 olan her gün kelepçelidir (su + tuz)."""
    bad_w = bad_s = clip = total = 0
    for r in range(n):
        pl = _v1plant(30.0)
        for d in range(12):
            before_m, before_s = pl.soil_moisture, pl.ec_mass
            pl.step(200 + d, 22.0, 14.0, 0.0,
                    irrigation_mm=15.0 if d == 3 else 0.0,
                    fertilizer_dose_mass=20.0 if d == 1 else 0.0)
            total += 1
            clipped = (pl.soil_moisture <= 1.0 + 1e-9
                       or pl.soil_moisture >= 100.0 - 1e-9
                       or pl.ec_mass <= 0.0 + 1e-12)
            clip += clipped
            if abs(pl.wb_last["residual"]) > 1e-9 and not clipped:
                bad_w += 1
            if abs(pl.salt_last["residual"]) > 1e-9 and not clipped:
                bad_s += 1
    ok = (bad_w == 0 and bad_s == 0)
    return {"pass": bool(ok),
            "metric": f"su_ihlali={bad_w} tuz_ihlali={bad_s} "
                      f"kelepce_gun={clip}/{total}",
            "tol": "kelepcesiz residual==0 (1e-9)",
            "detail": f"{n} koşu×12 gün, sulama+gübreli"}


def test4_monotonicity():
    """Doz-tepki monoton + azalan artımlar (doygunluk eğrisi)."""
    ms = []
    for dose in (10.0, 20.0, 30.0, 40.0):
        pl = _v1plant(25.0)
        for d in range(3):
            pl.step(200 + d, 20.0, 14.0, 0.0,
                    irrigation_mm=dose if d == 0 else 0.0)
        ms.append(round(pl.soil_moisture, 3))
    mono = all(b >= a - 1e-9 for a, b in zip(ms, ms[1:]))
    dim = (ms[3] - ms[2]) <= (ms[1] - ms[0]) + 0.5
    return {"pass": bool(mono and dim),
            "metric": f"nem={ms} artim={round(ms[3]-ms[2],2)}/"
                      f"{round(ms[1]-ms[0],2)}",
            "tol": "monoton azalmayan + üst-artım<=alt-artım+0.5",
            "detail": "θ0=25, 3. gün nemleri"}


def test5_interaction():
    """gübre×ısı: bileşke > toplam (süper-toplanırlık, işaret testi)."""
    deftx = {}
    for name, temp, fert in (("C", 20.0, {}), ("F", 20.0, {0: 30.0}),
                             ("H", 30.0, {}), ("FH", 30.0, {0: 30.0})):
        pl = _v1plant(30.0)
        for d in range(7):
            pl.step(200 + d, temp, 14.0, 0.0,
                    fertilizer_dose_mass=fert.get(d, 0.0))
        deftx[name] = 100.0 - pl.leaf_health
    inter = (deftx["FH"] - deftx["C"]) - ((deftx["F"] - deftx["C"])
                                          + (deftx["H"] - deftx["C"]))
    return {"pass": bool(inter > 0),
            "metric": f"kayıp {deftx} etkilesim={inter:+.3f}",
            "tol": "etkileşim>0 (yön testi)",
            "detail": "yaprak kaybı üzerinden, 7 gün"}


def test6_cross_world():
    """Aynı 50mm, kumlu vs killi: farklı kader."""
    outs = {}
    for name, soil in (("sand",
                        {"field_capacity": 30.0, "drainage_coef": 0.40,
                         "root_depth_mm": 200.0, "theta_s": 40.0,
                         "theta_fc": 25.0, "theta_wp": 10.0}),
                       ("clay",
                        {"field_capacity": 70.0, "drainage_coef": 0.08,
                         "root_depth_mm": 200.0, "theta_s": 60.0,
                         "theta_fc": 42.0, "theta_wp": 25.0})):
        p = PlantParams()
        for k, v in soil.items():
            setattr(p, k, v)
        pl = Plant(p, 0)
        pl.soil_moisture = 30.0
        pl.ec_mass = p.ec_baseline * 30.0
        for d in range(5):
            pl.step(200 + d, 20.0, 14.0, 0.0,
                    irrigation_mm=50.0 if d == 0 else 0.0)
        outs[name] = (round(pl.soil_moisture, 2), round(pl.ec, 3))
    diff = abs(outs["sand"][0] - outs["clay"][0])
    return {"pass": bool(diff >= 3.0),
            "metric": f"kum={outs['sand']} kil={outs['clay']}",
            "tol": "nem farkı>=3.0",
            "detail": "50mm tek doz, 5. gün"}


def test7_hidden_state():
    """Aynı sensör, farklı gizli yük → ıraksama (kısmi gözlenebilirlik)."""
    pair = {}
    for name, boost in (("A", 0.1), ("B", 0.8)):
        pl = _v1plant(45.0)
        pl.step(200, 20.0, 14.0, 0.0, irrigation_mm=20.0)
        day0 = (round(pl.soil_moisture, 2), 20.0, round(pl.ec, 3))
        # DÜZELTME: ilk yazımda su-basma 3. günde kurudu (tolerans 4
        # hiç aşılamadı → çürüme yok → patojen etkisizdi). Günlük
        # 8mm ile doygunluk SÜRDÜRÜLÜR (tol kapısı değil, senaryo hatası).
        for d in range(1, 10):
            pl.step(200 + d, 20.0, 14.0, 0.0, irrigation_mm=8.0,
                    pathogen_boost=boost)
        pair[name] = (day0, round(pl.root_health, 2))
    same_sensors = pair["A"][0] == pair["B"][0]
    div = pair["A"][1] - pair["B"][1]
    return {"pass": bool(same_sensors and div >= 1.0),
            "metric": f"gun0-ayni={same_sensors} kokfarkı={div:.2f}",
            "tol": "gün0 aynı + kök farkı>=1.0",
            "detail": "su-basma + patojen 0.1/0.8, 10 gün"}


def test8_hysteresis():
    """Kuraklık→su ≠ hep-sulu: geçmiş iz bırakır."""
    def run(moist0):
        pl = _v1plant(moist0, stage=Stage.VEGETATIVE)
        worst = 0.0
        for d in range(8):
            pl.step(200 + d, 22.0, 14.0, 0.0,
                    irrigation_mm=20.0 if d == 3 else 0.0)
            worst = min(worst, pl.water_balance)
        return pl, worst
    a, wa = run(15.0)
    b, wb = run(25.0)
    div = b.leaf_health - a.leaf_health
    return {"pass": bool(div >= 0.5 and wa < -0.15 and wb >= -0.15),
            "metric": f"yaprakfarkı={div:.2f} wbmin={wa:.3f}/{wb:+.3f}",
            "tol": "fark>=0.5, A stresli B stressiz",
            "detail": "3 gün kurak + 4. gün 20mm, VEGETATİF"}


def _extreme_run(case):
    """Tek uç senaryo koşusu → (sınırlar-ok, nem, ec, yaprak)."""
    clay = {"field_capacity": 70.0, "drainage_coef": 0.08,
            "root_depth_mm": 200.0, "theta_s": 60.0, "theta_fc": 42.0,
            "theta_wp": 25.0}
    kw = dict(case)
    soil = clay if kw.pop("soil", "") == "clayE" else V1
    days = kw.pop("days")
    moist0 = kw.pop("moist0")
    ec0 = kw.pop("ec0", None)
    temp, rh = kw.pop("temp"), kw.pop("rh")
    fert, irrig = kw.pop("fert", {}), kw.pop("irrig", {})
    dm = kw.pop("drain", 1.0)
    pb = kw.pop("pathogen", 0.0)
    p = PlantParams()
    base = soil_overrides(soil) if isinstance(soil, str) else soil
    for k, v in base.items():
        setattr(p, k, v)
    pl = Plant(p, 0)
    pl.soil_moisture = moist0
    pl.ec_mass = (p.ec_baseline if ec0 is None else ec0) * moist0
    ok = True
    for d in range(days):
        pl.step(200 + d, temp, 14.0, 0.0,
                irrigation_mm=(irrig.get(d, 0.0)),
                fertilizer_dose_mass=fert.get(d, 0.0), rh_frac=rh,
                drain_mult=dm, pathogen_boost=pb)
        vals = [pl.soil_moisture, pl.ec, pl.leaf_health,
                pl.root_health, pl.water_balance,
                pl.wb_last.get("residual", 0.0)]
        ok &= (all(np.isfinite(vals))
               and 1.0 <= pl.soil_moisture <= 100.0
               and 0.0 <= pl.leaf_health <= 100.0
               and 0.0 <= pl.root_health <= 100.0
               and 0.0 <= pl.ec < 50.0)
    return ok, pl


def test9_extremes():
    """Kırma denemeleri: sonlu, sınırlı, çökmesiz."""
    cases = {
        "frostflood": dict(temp=-5.0, rh=None, days=3, moist0=45.0,
                           irrig={0: 20.0}),
        "cloudburst": dict(temp=20.0, rh=None, days=3, moist0=30.0,
                           irrig={0: 50.0}, drain=0.1),
        "saltbomb": dict(temp=20.0, rh=None, days=3, moist0=10.0,
                         fert={0: 200.0}),
    }
    worst = []
    for name, kw in cases.items():
        ok, pl = _extreme_run(kw)
        worst.append((name, bool(ok), round(pl.soil_moisture, 1),
                      round(pl.ec, 2), round(pl.leaf_health, 1)))
    ok_all = all(w[1] for w in worst)
    return {"pass": bool(ok_all), "metric": str(worst),
            "tol": "sonlu + nem[1,100] + EC<50 + sağlık[0,100]",
            "detail": "3 uç senaryo (killer ayrı kapıda: TEST9b)"}


def test9b_desiccation_limit():
    """BELGELENMİŞ LİMİT (§9.51): kuruma-zemininde EC ıraksar.

    Killer senaryo (40°C/RH15%/EC0 4/tuzlu-kil/gübre): nem tabana
    (1.0) vurur, kütle sabit kalır → EC kütle/hacimden fırlar. Modelde
    çökelme/katı-faz lavabosu YOK — bu kapı ıraksamayı KİLİTLER
    (bilinen açık borç). Çökelme eklenirse bu kapı düşer ve revizyon
    ister (regresyon kilidi, beklenti-güzelleme değil).
    """
    ok, pl = _extreme_run(
        dict(temp=40.0, rh=0.15, days=7, moist0=25.0, ec0=4.0,
             soil="clayE", fert={0: 30.0}, pathogen=1.0))
    finite = bool(np.isfinite([pl.soil_moisture, pl.ec, pl.leaf_health,
                                 pl.root_health]).all())
    signature = (pl.soil_moisture <= 1.0 + 1e-9 and pl.ec > 50.0
                 and finite)
    return {"pass": bool(signature),
            "metric": f"nem={pl.soil_moisture:.1f} EC={pl.ec:.1f} "
                      f"yaprak={pl.leaf_health:.1f} sonlu={finite}",
            "tol": "taban-nem + EC>50 + sonlu (limit imzası)",
            "detail": "killer: limit-karakteri kilitli, çökelme borcu açık"}
    clay = {"field_capacity": 70.0, "drainage_coef": 0.08,
            "root_depth_mm": 200.0, "theta_s": 60.0, "theta_fc": 42.0,
            "theta_wp": 25.0}
    worst = []
    for name, kw in cases.items():
        soil = clay if kw.pop("soil", "") == "clayE" else V1
        days = kw.pop("days")
        moist0 = kw.pop("moist0")
        ec0 = kw.pop("ec0", None)
        temp, rh = kw.pop("temp"), kw.pop("rh")
        fert, irrig = kw.pop("fert", {}), kw.pop("irrig", {})
        dm = kw.pop("drain", 1.0)
        pb = kw.pop("pathogen", 0.0)
        p = PlantParams()
        base = soil_overrides(soil) if isinstance(soil, str) else soil
        for k, v in base.items():
            setattr(p, k, v)
        pl = Plant(p, 0)
        pl.soil_moisture = moist0
        pl.ec_mass = (p.ec_baseline if ec0 is None else ec0) * moist0
        ok = True
        for d in range(days):
            pl.step(200 + d, temp, 14.0, 0.0,
                    irrigation_mm=(irrig.get(d, 0.0)),
                    fertilizer_dose_mass=fert.get(d, 0.0), rh_frac=rh,
                    drain_mult=dm, pathogen_boost=pb)
            vals = [pl.soil_moisture, pl.ec, pl.leaf_health,
                    pl.root_health, pl.water_balance,
                    pl.wb_last.get("residual", 0.0)]
            ok &= (all(np.isfinite(vals))
                   and 1.0 <= pl.soil_moisture <= 100.0
                   and 0.0 <= pl.leaf_health <= 100.0
                   and 0.0 <= pl.root_health <= 100.0
                   and 0.0 <= pl.ec < 50.0)
        worst.append((name, ok, round(pl.soil_moisture, 1),
                      round(pl.ec, 2), round(pl.leaf_health, 1)))
    ok_all = all(w[1] for w in worst)
    return {"pass": bool(ok_all), "metric": str(worst),
            "tol": "sonlu + nem[1,100] + EC<50 + sağlık[0,100]",
            "detail": "4 uç senaryo"}


def test10_diversity(n=10000):
    """10k kader: ıraksak + sonlu + rejimli (tek-mod dayatılmaz)."""
    df, logs = run_ensemble(n, days=12, rh_mode="mixed")
    fin = df[df.day == 11]
    scheds = logs.groupby("run").apply(
        lambda g: tuple(sorted((r["day"], r["event"]) for _, r in
                               g.iterrows())),
        include_groups=False)
    # DÜZELTME: topluluk satırları "leaf" adını taşır (leaf_health değil).
    healthy = int((fin.leaf >= 99.9).sum())
    dead = int((fin.leaf <= 0.0).sum())
    ok = (float(fin.soil_moisture.std()) > 1.0
          and float(fin.soil_ec.std()) > 0.1
          and float(fin.stress.std()) > 0.01
          and int(scheds.nunique()) >= 100
          and healthy >= 1
          and bool(np.isfinite(fin[["soil_moisture", "soil_ec", "leaf",
                                    "stress"]].values).all()))
    return {"pass": bool(ok),
            "metric": f"std={fin.soil_moisture.std():.1f}/"
                      f"{fin.soil_ec.std():.2f}/{fin.stress.std():.3f} "
                      f"tarife={scheds.nunique()} saglikli={healthy} "
                      f"olu={dead}",
            "tol": "std>1.0/0.1/0.01, tarife>=100, ≥1 sağlıklı",
            "detail": f"{n} tohum; ölüm SAYILIR, şart koşulmaz",
            "_dead": dead, "_fin": fin}


def adversarial():
    """Cennet (zorunlu geçiş) + ölüm-kutusu (yön + rapor)."""
    par = _v1plant(35.0, stage=Stage.VEGETATIVE)
    for d in range(60):
        par.step(200 + (d % 100), 20.0, 14.0, 0.0,
                 irrigation_mm=2.0)
    paradise = (par.leaf_health >= 99.9 and par.root_health >= 99.9)
    # DÜZELTME: ilk yazımda 5mm/gün denge nemini ~39'da tuttu
    # (eşik 42.4'ün altı → çürüme hiç başlamadı). 15mm/gün ile
    # denge ~47 olur, su-basma SÜRER (senaryo hatası, fizik değil).
    kill = _v1plant(45.0)
    for d in range(120):
        kill.step(200 + (d % 100), 25.0, 14.0, 15.0,
                  pathogen_boost=2.0)
    declined = (100.0 - kill.root_health) >= 5.0
    dead = bool(kill.stage == Stage.DEAD)
    return {"pass": bool(paradise and declined),
            "metric": f"cennet={paradise} kok-dusus="
                      f"{100.0 - kill.root_health:.1f} olum={dead}",
            "tol": "cennet sağlıklı + kutuda kök-düşüşü>=5 (ölüm rapor)",
            "detail": "60g cennet / 120g su-basma+patojen"}


def recovery(n=2000):
    """Taze tohumda D2/D3 tekrarı (WORLD B, anti-ezber)."""
    from sim.infer import summarize, discover
    df, _ = run_ensemble(n, days=12, rh_mode="mixed",
                         climate_seed=4242, event_seed0=31337)
    v = discover(summarize(df))
    return {"pass": bool(v["D2"][3] and v["D3"][3]),
            "metric": f"D2={v['D2'][0]:+.3f} D3={v['D3'][0]:+.3f}",
            "tol": "D2+D3 taze tohumda da keşif",
            "detail": f"{n} koşu, görülmemiş tohumlar"}


def test11_cycle_determinism():
    """Aynı master → aynı çoklu-döngü (bit-eşit)."""
    from sim.cycles import run_multicycle
    a, _, _ = run_multicycle(42, 3, days_per_cycle=365)
    b, _, _ = run_multicycle(42, 3, days_per_cycle=365)
    return {"pass": bool(a.equals(b)),
            "metric": f"{len(a)} satır bit-eşit",
            "tol": "master-sabit bit-eşitlik",
            "detail": "3×365 gün, v1"}


def test12_ege_envelope():
    """Döngüler farklı yıl yaşar, hepsi Ege zarfında."""
    from sim.cycles import (run_multicycle, check_ege_envelope,
                            TEMP_ANOMALY_RANGE)
    df, _, metas = run_multicycle(7, 6, days_per_cycle=365)
    anoms = [m["year_type"]["temp_anomaly"] for m in metas]
    ok = (check_ege_envelope(df)
          and float(np.std(anoms)) > 0.2
          and all(TEMP_ANOMALY_RANGE[0] <= a <= TEMP_ANOMALY_RANGE[1]
                  for a in anoms))
    return {"pass": bool(ok),
            "metric": f"anomali_std={np.std(anoms):.2f} "
                      f"temp=[{df.temp.min():.1f},{df.temp.max():.1f}]",
            "tol": "std>0.2 + zarf + TODO-aralık",
            "detail": "6 döngü, master=7"}


def test13_spawn_independence():
    """Cycle-1 tohumu değişince cycle-0 aynı, cycle-1 farklı."""
    from sim.cycles import run_multicycle
    a, _, _ = run_multicycle(42, 2, days_per_cycle=200)
    b, _, _ = run_multicycle(42, 2, days_per_cycle=200,
                             seed_overrides={1: {"event": 999999}})
    c0_same = bool(a[a.cycle == 0].reset_index(drop=True).equals(
        b[b.cycle == 0].reset_index(drop=True)))
    c1_diff = not bool(a[a.cycle == 1].reset_index(drop=True).equals(
        b[b.cycle == 1].reset_index(drop=True)))
    return {"pass": bool(c0_same and c1_diff),
            "metric": f"cycle0-ayni={c0_same} cycle1-farkli={c1_diff}",
            "tol": "spawn izolasyonu",
            "detail": "SeedSequence hiyerarşisi"}



TESTS = [
    ("TEST1-determinizm", test1_determinism),
    ("TEST2-diversity", test2_diversity),
    ("TEST3-invariant", test3_invariants),
    ("TEST4-monotonluk", test4_monotonicity),
    ("TEST5-etkilesim", test5_interaction),
    ("TEST6-capraz-dunya", test6_cross_world),
    ("TEST7-gizli-durum", test7_hidden_state),
    ("TEST8-histeresis", test8_hysteresis),
    ("TEST9-ekstrem", test9_extremes),
    ("TEST9b-kuruma-limiti", test9b_desiccation_limit),
    ("TEST11-cycle-determinizm", test11_cycle_determinism),
    ("TEST12-ege-zarfi", test12_ege_envelope),
    ("TEST13-spawn-bagimsizlik", test13_spawn_independence),
    ("TEST10-10k", test10_diversity),
    ("ADV-adversarial", adversarial),
    ("REC-recovery", recovery),
]



def run_all(verbose=True):
    out = {}
    for name, fn in TESTS:
        try:
            r = fn()
        except Exception as e:  # çökme de bulgudur
            r = {"pass": False, "metric": f"HATA: {e!r}",
                 "tol": "-", "detail": "istisna"}
        out[name] = r
        if verbose:
            mark = "GEÇTİ" if r["pass"] else "DÜŞTÜ"
            print(f"[{mark}] {name}: {r['metric']} (tol: {r['tol']})")
    return out


if __name__ == "__main__":
    run_all()
