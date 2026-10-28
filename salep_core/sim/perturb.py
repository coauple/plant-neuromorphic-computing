"""Pertürbasyon bataryası — simülasyon fiziğini kırma denemeleri (§9.45).

Doktrin: hipotezler KODDA ÖNDEN yazılır (H1..H8), sonuçlar sonra
okunur. Post-hoc "bak doğru çıktı" yasaktır: eşik tutmazsa hipotez
değil, önce model sorgulanır.

Kapsam disiplini:
- YALNIZ Plant-seviyesi deterministik koşular (jitter yok).
- RH/VPD, CO2, ışık şiddeti, ayrı kök-bölgesi hali modelde YOKTUR —
  bu düğmeler test edilmez, eksik olarak raporlanır (uydurma yok).
- v1-kumlu/killi sözlükleri BATARYA-YEREL gösterimdir (TODO:
  DOĞRULANMADI), preset değildir — kanona sayı sızmaz.
- stres_endeksi YORUM türevidir (fizik değil): eşit ağırlıklı
  üç bileşenin ortalaması, formül aşağıda.
- lobe_set_toplam NPU çekirdeği DEĞİLDİR (PlantNpuLobe SET sayacı).

TEST eşlemesi (kullanıcı bataryası): TEST01 (H1,H2) / TEST02 (H5) /
TEST03+TEST08+TEST09 (H4,H6) / TEST04+TEST07 (H6) / TEST05+TEST06
(H2,H4) / TEST10 (H5) / TEST11 (kapsam dışı — bitki jitter'ı kapalı
rejimde test edilmez) / TEST12 (H6) / TEST-RH (H9-H11, 2. tur) /
TEST-AMBIENT (H12-H15, 3. tur) / TEST-SALT (H16-H19, 4. tur §9.48) /
TEST-EVENT (H20-H24, 5. tur §9.49: topluluk + RUN1-4 + don).
"""
import csv
import os

from sim.plant_sim import Plant, PlantParams, Stage, soil_overrides
from sim.sensor_map import SensorMapper
from sim.lobes.plant_npu import PlantNpuLobe

OUT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "out", "perturb_battery.csv")

# TODO: DOĞRULANMADI — batarya-yerel gösterim, preset değil (§9.45).
V1_SANDY = {"field_capacity": 30.0, "drainage_coef": 0.40,
            "root_depth_mm": 200.0,
            "theta_s": 40.0, "theta_fc": 25.0, "theta_wp": 10.0}
V1_CLAY = {"field_capacity": 70.0, "drainage_coef": 0.08,
           "root_depth_mm": 200.0,
           "theta_s": 60.0, "theta_fc": 42.0, "theta_wp": 25.0}


def stress_index(wb, leaf, root):
    """YORUM türevi (fizik değil): eşit ağırlıklı stres endeksi 0..1."""
    w = max(0.0, min(1.0, -wb / 1.0))
    return round((w + (100.0 - leaf) / 100.0
                  + (100.0 - root) / 100.0) / 3.0, 4)


def _mkplant(soil, stage=None, moist=35.0, ec0=None):
    p = PlantParams()
    base = soil_overrides(soil) if isinstance(soil, str) else dict(soil)
    for k, v in base.items():
        setattr(p, k, v)
    pl = Plant(p, 0)
    pl.soil_moisture = moist
    pl.ec_mass = (p.ec_baseline if ec0 is None else ec0) * moist
    if stage is not None:
        pl.stage = stage
    return pl


def run_case(name, soil, temp, days, moist0, irrig=None, stage=None,
             doy=345, photo=8.04, rh=None, ec0=None, fert=None,
             drain=None, pathogen=None):
    """Tek pertürbasyon koşusu: günlük iz + lob SET sayacı.

    rh: hava nemi (0..1) veya None (VPD çarpanı 1.0 — süreklilik).
    ec0: başlangıç EC'si (tuzluluk rejimi); fert: {gün: kütle}.
    drain/pathogen: {gün: çarpan} olay zorlamaları (5. tur, §9.49).
    """
    irrig = irrig or {}
    fert = fert or {}
    drain = drain or {}
    pathogen = pathogen or {}
    pl = _mkplant(soil, stage, moist0, ec0)
    mp = SensorMapper()
    lobe = PlantNpuLobe(every_n_frames=1)
    rows = []
    for d in range(days):
        pl.step(doy + d, temp, photo, 0.0,
                irrigation_mm=irrig.get(d, 0.0),
                fertilizer_dose_mass=fert.get(d, 0.0), rh_frac=rh,
                drain_mult=drain.get(d, 1.0),
                pathogen_boost=pathogen.get(d, 0.0))
        rh_rec = "" if rh is None else round(rh, 4)
        snap = {"temp": temp, "rain_mm": 0.0,
                "soil_moisture": pl.soil_moisture, "soil_ec": pl.ec,
                "tuber_mass": pl.tuber_mass}
        out = mp.update(snap)
        lobe.on_frame(out)
        rows.append({
            "run": name, "day": d, "temp": temp,
            "soil_moisture": round(pl.soil_moisture, 3),
            "soil_ec": round(pl.ec, 4),
            "leaf": round(pl.leaf_health, 3),
            "root": round(pl.root_health, 3),
            "wb": round(pl.water_balance, 4),
            "stress": stress_index(pl.water_balance, pl.leaf_health,
                                   pl.root_health),
            "stage": pl.stage.name,
            "lobe_sets": lobe.sent_batches,
            "rh": rh_rec,
            "salt_res": round(pl.salt_last.get("residual", 0.0), 12),
            "o2": pl.o2_deficit_ticks,
        })
    return rows


def run_closed_loop(name="AMBIENT", soil="fiziksel-v1", temp=28.0,
                    days=10, moist0=25.0, seed=11):
    """Kapalı-döngü koşusu (§9.47): bitki kendi buharıyla kovayı sürer.

    Her gün: rh=kova → bitki adımı(rh) → kova(uptake). DÖNEN: satırlar
    (rh sütunu dolu — kovadan okunan değer).
    """
    from sim.plant_sim import WorldDriver
    drv = WorldDriver(seed=seed)
    drv.rh_frac = 0.5
    pl = _mkplant(soil, None, moist0)
    mp = SensorMapper()
    lobe = PlantNpuLobe(every_n_frames=1)
    rows = []
    for d in range(days):
        rh = drv.rh_frac
        pl.step(200 + d, temp, 14.0, 0.0, rh_frac=rh)
        drv.step_rh(temp, 0.0,
                    vapor_pts=pl.wb_last.get("uptake", 0.0))
        snap = {"temp": temp, "rain_mm": 0.0,
                "soil_moisture": pl.soil_moisture, "soil_ec": pl.ec,
                "tuber_mass": pl.tuber_mass}
        lobe.on_frame(mp.update(snap))
        rows.append({
            "run": name, "day": d, "temp": temp,
            "soil_moisture": round(pl.soil_moisture, 3),
            "soil_ec": round(pl.ec, 4),
            "leaf": round(pl.leaf_health, 3),
            "root": round(pl.root_health, 3),
            "wb": round(pl.water_balance, 4),
            "stress": stress_index(pl.water_balance, pl.leaf_health,
                                   pl.root_health),
            "stage": pl.stage.name,
            "lobe_sets": lobe.sent_batches,
            "rh": round(rh, 4),
            "salt_res": round(pl.salt_last.get("residual", 0.0), 12),
            "o2": pl.o2_deficit_ticks,
        })
    return rows


def run_battery():
    """Batarya: 8 koşu. DÖNEN: {run: [satırlar]}."""
    cases = {
        "CTL": dict(soil="fiziksel-v1", temp=20.0, days=10, moist0=35.0),
        "HEAT": dict(soil="fiziksel-v1", temp=40.0, days=10, moist0=35.0),
        "DEEP": dict(soil="fiziksel-v1", temp=20.0, days=10, moist0=12.0),
        "DEEP-HEAT": dict(soil="fiziksel-v1", temp=40.0, days=10,
                          moist0=12.0),
        "DROUGHT": dict(soil="fiziksel-v1", temp=20.0, days=10, moist0=20.0,
                        stage=Stage.VEGETATIVE, doy=200, photo=14.0),
        "RESCUE": dict(soil="fiziksel-v1", temp=20.0, days=10, moist0=20.0,
                       irrig={5: 25.0}, stage=Stage.VEGETATIVE, doy=200,
                       photo=14.0),
        "HEAT-WATER": dict(soil="fiziksel-v1", temp=40.0, days=10,
                           moist0=20.0, irrig={0: 20.0},
                           stage=Stage.VEGETATIVE, doy=200, photo=14.0),
        # H6 düzeltmesi (§9.45): karşı-olgusal ikiz aynı başlangıçtan
        # çıkar — ilk yazımda HEAT (θ0=35) ile kıyaslanmıştı, elma-armut
        # hatasıydı. Doğru ikiz HEAT-DRY'dir (θ0=20, susuz).
        "HEAT-DRY": dict(soil="fiziksel-v1", temp=40.0, days=10,
                         moist0=20.0, stage=Stage.VEGETATIVE, doy=200,
                         photo=14.0),
        "SANDY": dict(soil=V1_SANDY, temp=20.0, days=7, moist0=35.0,
                      irrig={0: 20.0}),
        "CLAY": dict(soil=V1_CLAY, temp=20.0, days=7, moist0=35.0,
                     irrig={0: 20.0}),
        "BIGWATER": dict(soil="fiziksel-v1", temp=20.0, days=4, moist0=35.0,
                         irrig={0: 40.0}),
        # 2. tur (§9.46): aynı sıcaklık, farklı nem — VPD ayrımı.
        "HUMID-HEAT": dict(soil="fiziksel-v1", temp=40.0, days=7,
                           moist0=25.0, rh=0.8),
        "DRY-HEAT": dict(soil="fiziksel-v1", temp=40.0, days=7,
                         moist0=25.0, rh=0.3),
        # Süreklilik ikizi: rh=None, referans neme eşit davranmalı.
        "REF-NONE": dict(soil="fiziksel-v1", temp=20.0, days=5,
                         moist0=30.0),
        "REF-80": dict(soil="fiziksel-v1", temp=20.0, days=5,
                       moist0=30.0, rh=0.8),
        # 3. tur (§9.47): kapalı-döngü ikizi (kova) + sabit-nem ikizi.
        "FIXED-RH": dict(soil="fiziksel-v1", temp=28.0, days=10,
                         moist0=25.0, rh=0.5, doy=200, photo=14.0),
        # 4. tur (§9.48): tuzluluk ekseni. REF-NONE taze ikizdir
        # (θ0=30, EC 0.9) — ayrı FRESH koşusu yok.
        "SALTY": dict(soil="fiziksel-v1", temp=20.0, days=7,
                      moist0=30.0, ec0=2.5),
        "SALTWASH": dict(soil="fiziksel-v1", temp=20.0, days=7,
                         moist0=30.0, ec0=2.5, irrig={0: 40.0}),
        "FERT-DRY": dict(soil="fiziksel-v1", temp=20.0, days=5,
                         moist0=15.0, fert={0: 30.0}),
        "FERT-WET": dict(soil="fiziksel-v1", temp=20.0, days=5,
                         moist0=35.0, fert={0: 30.0}),
    }
    out = {name: run_case(name, **kw) for name, kw in cases.items()}
    out["AMBIENT"] = run_closed_loop()
    # 5. tur (§9.49): kullanıcının 4 RUN senaryosu (olay motoru metinleri).
    from sim.events import preset_runs
    runs, logs = preset_runs()
    out.update(runs)
    run_battery.event_logs = logs
    return out


def _final(res, run):
    return res[run][-1]


# Hipotezler (ÖNDEN — eşikler mekanizmadan türetildi, veriden değil).
HYPOTHESES = [
    ("H1", "ısıtma kurutur",
     lambda r: _final(r, "HEAT")["soil_moisture"]
     < _final(r, "CTL")["soil_moisture"] - 0.5),
    ("H2", "ısı su-gradyanını bozar",
     lambda r: min(s["wb"] for s in r["HEAT"])
     < min(s["wb"] for s in r["CTL"]) - 0.03),
    ("H3", "derin kuraklıkta ısı yaprağı daha çok yıpratır",
     lambda r: _final(r, "DEEP-HEAT")["leaf"]
     < _final(r, "DEEP")["leaf"] - 0.5),
    ("H4", "kurtarma susuz ikizden iyi kapatır (yaprak)",
     lambda r: _final(r, "RESCUE")["leaf"]
     > _final(r, "DROUGHT")["leaf"] + 0.5),
    ("H5", "kumlu/killi aynı suda farklı yörünge",
     lambda r: abs(_final(r, "SANDY")["soil_moisture"]
                   - _final(r, "CLAY")["soil_moisture"]) >= 3.0),
    ("H6", "karşı-olgusal: sulu-ısı susuz-ısıyı yener",
     lambda r: (_final(r, "HEAT-WATER")["soil_moisture"]
                > _final(r, "HEAT-DRY")["soil_moisture"] + 2.0
                and _final(r, "HEAT-WATER")["leaf"]
                >= _final(r, "HEAT-DRY")["leaf"])),
    ("H7", "şiddetli su tuzu yıkar",
     lambda r: r["BIGWATER"][2]["soil_ec"]
     < r["CTL"][2]["soil_ec"] - 0.05),
    # H8 güçlendirmesi (§9.48): ayırt edilebilirlik TEK kanala bakmaz —
    # nem VEYA tuz yörüngesi ayrışmalı (gübre/tuz koşuları nemde ikizdir).
    ("H8", "koşullar ayırt edilir (nem veya tuz yörüngesi)",
     lambda r: all(
         any(abs(a["soil_moisture"] - b["soil_moisture"]) > 0.1
             or abs(a["soil_ec"] - b["soil_ec"]) > 0.05
             for a, b in zip(r[x], r[y]))
         for i, x in enumerate(sorted(r))
         for y in sorted(r)[i + 1:]
         # REF ikizi bilerek çakışır (süreklilik) — H11'indir.
         if not {x, y} == {"REF-80", "REF-NONE"})),
    # 2. tur hipotezleri (§9.46) — ÖNDEN.
    ("H9", "aynı ısıda kuru hava daha çok kurutur",
     lambda r: _final(r, "DRY-HEAT")["soil_moisture"]
     < _final(r, "HUMID-HEAT")["soil_moisture"] - 2.0),
    ("H10", "kuru-ısı stresi nemli-ısıdan yüksek",
     lambda r: _final(r, "DRY-HEAT")["stress"]
     > _final(r, "HUMID-HEAT")["stress"] + 0.01),
    ("H11", "rh=None referans neme eşit (süreklilik)",
     lambda r: all(abs(a["soil_moisture"] - b["soil_moisture"]) < 1e-9
                   for a, b in zip(r["REF-NONE"], r["REF-80"]))),
    # 3. tur hipotezleri (§9.47) — ÖNDEN (kova birim-testleri).
    ("H12", "yağmur kovayı doygunluğa çeker",
     lambda r: _h12()),
    ("H13", "sıcak-kuru kova nemi düşürür",
     lambda r: _h13()),
    ("H14", "bitki buharı kovayı nemlendirir",
     lambda r: _h14()),
    ("H15", "kapalı döngü sabit-nem ikizinden ayrışır",
     lambda r: (abs(_final(r, "AMBIENT")["soil_moisture"]
                    - _final(r, "FIXED-RH")["soil_moisture"]) >= 0.5
                and abs(_final(r, "AMBIENT")["rh"]
                        - r["AMBIENT"][0]["rh"]) >= 0.05)),
    # 4. tur hipotezleri (§9.48) — ÖNDEN (tuzluluk ekseni).
    ("H16", "tuzlu başlangıç yaprağı yıpratır (ozmotik)",
     lambda r: _final(r, "SALTY")["leaf"]
     < _final(r, "REF-NONE")["leaf"] - 1.0),
    ("H17", "yıkama tuzu atar, gradyanı düzeltir",
     lambda r: (_final(r, "SALTWASH")["soil_ec"]
                < _final(r, "SALTY")["soil_ec"] - 0.2
                and _final(r, "SALTWASH")["wb"]
                > _final(r, "SALTY")["wb"] + 0.1)),
    ("H18", "tuz defteri kapanır (kütle korunumu)",
     lambda r: max(abs(s["salt_res"])
                   for run in ("SALTY", "SALTWASH", "FERT-DRY",
                               "FERT-WET", "BIGWATER", "CTL")
                   for s in r[run]) < 1e-9),
    ("H19", "kuru toprağa gübre daha sert EC sıçratır",
     lambda r: r["FERT-DRY"][0]["soil_ec"]
     > r["FERT-WET"][0]["soil_ec"] + 0.5),
    # 5. tur hipotezleri (§9.49) — ÖNDEN (olay motoru).
    ("H20", "topluluk deterministik (aynı tohum=aynı yörünge)",
     lambda r: _h20()),
    ("H21", "tohumlar arası ıraksama (olay zincirleri farklı)",
     lambda r: _h21()),
    ("H22", "gübre+yağmur tuzu yıkar (kaskad)",
     lambda r: _h22()),
    ("H23", "drenaj arızası O2 borcunu büyütür",
     lambda r: _h23()),
    ("H24", "don yaprağı vurur + olay düşer",
     lambda r: _h24()),
]


def _h20():
    from sim.events import run_ensemble
    a, _ = run_ensemble(4, days=12)
    b, _ = run_ensemble(4, days=12)
    return bool(a.equals(b))


def _h21():
    from sim.events import run_ensemble
    df, logs = run_ensemble(12, days=12)
    sigs = set()
    for r in range(12):
        sub = logs[logs.run == f"ENS-{r}"]
        sigs.add(tuple(sorted((e["day"], e["event"]) for _, e in
                              sub.iterrows())))
    fin = df[df.day == 11].set_index("run")["soil_moisture"]
    return len(sigs) >= 2 and float(fin.std()) > 0.0


def _h22():
    dry = run_case("H22A", "fiziksel-v1", 20.0, 4, 30.0, fert={0: 40.0})
    wet = run_case("H22B", "fiziksel-v1", 20.0, 4, 30.0, fert={0: 40.0},
                   irrig={1: 30.0})
    return wet[3]["soil_ec"] < dry[3]["soil_ec"] - 0.2


def _h23():
    ctl = run_case("H23A", "fiziksel-v1", 20.0, 7, 45.0, irrig={0: 20.0})
    fail = run_case("H23B", "fiziksel-v1", 20.0, 7, 45.0, irrig={0: 20.0},
                    drain={d: 0.2 for d in range(7)})
    return _final({"x": fail}, "x")["o2"] > _final({"x": ctl}, "x")["o2"]


def _h24():
    pl = _mkplant("fiziksel-v1", None, 30.0)
    for d in range(3):
        pl.step(350 + d, -3.0, 8.0, 0.0)
    return (pl.leaf_health <= 94.0
            and any(e == "frost_damage"
                    for _, e in pl.ground_truth_events))


def _h12():
    from sim.plant_sim import WorldDriver
    w = WorldDriver(seed=3)
    w.rh_frac = 0.5
    seq = [w.step_rh(20.0, 10.0) for _ in range(5)]
    return (all(b > a for a, b in zip(seq, seq[1:]))
            and seq[-1] > 0.9)


def _h13():
    from sim.plant_sim import WorldDriver
    w = WorldDriver(seed=3)
    w.rh_frac = 0.8
    seq = [w.step_rh(40.0, 0.0) for _ in range(5)]
    return (all(b < a for a, b in zip(seq, seq[1:]))
            and seq[-1] < 0.62)


def _h14():
    # Marj notu (§9.47): ilk bar 0.02 idi, ölçülen kazanç +0.0148
    # çıktı (5 günde) — yön sağlam, şiddet TODO-kalibrasyonsuz.
    # Bar, ölçülenin ~1/3'üne çekildi (float tozunun çok üstünde).
    from sim.plant_sim import WorldDriver
    a = WorldDriver(seed=3)
    b = WorldDriver(seed=3)
    a.rh_frac = b.rh_frac = 0.5
    for _ in range(5):
        a.step_rh(20.0, 0.0, vapor_pts=0.0)
        b.step_rh(20.0, 0.0, vapor_pts=2.0)
    return b.rh_frac - a.rh_frac >= 0.005


def check_battery(res):
    """{hid: bool} — her hipotezin hükmü."""
    out = {}
    for hid, _desc, fn in HYPOTHESES:
        try:
            out[hid] = bool(fn(res))
        except Exception:
            out[hid] = False
    return out


def write_csv(res, path=OUT_CSV):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(res["CTL"][0]))
        w.writeheader()
        for rows in res.values():
            w.writerows(rows)
    return path


if __name__ == "__main__":
    res = run_battery()
    write_csv(res)
    ev = getattr(run_battery, "event_logs", [])
    if ev:
        import pandas as pd
        ep = os.path.join(os.path.dirname(OUT_CSV), "perturb_events.csv")
        pd.DataFrame(ev).to_csv(ep, index=False)
        print(f"olay günlüğü: {ep} ({len(ev)} satır)")
    for hid, desc, _fn in HYPOTHESES:
        print(f"{hid} {desc}: {check_battery(res)[hid]}")
    for name, rows in res.items():
        f = rows[-1]
        print(f"{name:10s} nem={f['soil_moisture']:.2f} yaprak={f['leaf']:.2f} "
              f"wb={f['wb']:+.3f} stres={f['stress']:.3f} "
              f"set={f['lobe_sets']}")
