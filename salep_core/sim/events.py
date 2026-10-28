"""Stokastik World/Event katmanı (§9.49).

Tasarım: deterministik çekirdeğe DOKUNULMAZ (yeni kwarg'lar öntanımlıda
birebir eski davranıştır). Bu katman YALNIZ zorlama üretir (sıcaklık
deltası, yağış, sulama/gübre eylemleri, drenaj çarpanı, patojen yükü)
ve bitki adımını bu zorlamayla sürer. Rastgelelik tohumludur, olay
kümesi KAPALIDIR (katalog dışı "uzaylı" olayı üretilemez).

Belirsizlik katmanları (kullanıcı mimarisi):
 1. ölçüm: SensorMapper gürültüsü (adım 8, ayrı).
 2. parametre: jitter spread (mevcut) + TODO-sayılar.
 3. çevresel: bu modüldeki tehlike çekişleri.
 4. gizli: patojen yükü (gözlenmez, yalnız kök-çürüklüğünü büyütür).
 5. şok: soğuk dalgası→don (fizik dalı §9.49), aşırı yağış.

Kaskadlar AYRI kodlanmaz, mevcut fizikten DOĞAR: gübre→EC↑,
yağmur→seyrelme/yıkama, doygunluk→P(drenaj-arızası)↑→O₂↓→kök↓,
soğuk→sıcaklık<0→don dalı. pH kayması modelde YOK (GEP) — uydurulmaz.

TODO: DOĞRULANMADI — tehlike oranları gösterim öncülüdür (§9.49).
"""
import numpy as np
import pandas as pd

from sim.plant_sim import Plant, PlantParams, WorldDriver, soil_overrides
from sim.sensor_map import SensorMapper
from sim.lobes.plant_npu import PlantNpuLobe
from sim.perturb import stress_index

# TODO: DOĞRULANMADI — gösterim öncülleri, tarla serisiyle kalibre edilecek.
P_HEAT_SUMMER = 0.05
P_COLD_WINTER = 0.05
P_RAIN_SUMMER = 0.03
P_RAIN_WINTER = 0.06
P_DRAIN_FAIL = 0.25    # doygunluk ≥3 gün sürerse (killi zeminde +0.15)
P_PATHOGEN = 0.10      # doygun + ılık (T>15) ise
P_FERT = 0.02          # eylem öncülü: gübreleme (30 kütle)
P_IRRIG = 0.03         # eylem öncülü: sulama (15 mm)
RH_REGIMES = (0.3, 0.5, 0.8)  # karışık rejim adayları (VPD yayılımı için)

# TODO: DOĞRULANMADI — perturb.V1_CLAY ile aynı batarya-yerel gösterim.
V1_CLAY_E = {"field_capacity": 70.0, "drainage_coef": 0.08,
             "root_depth_mm": 200.0,
             "theta_s": 60.0, "theta_fc": 42.0, "theta_wp": 25.0}


class EventEngine:
    """Günlük tehlike çekişleri + gizli durum.

    Gizli durum (çerçeveye çıkmaz): drenaj-arızası sayacı, patojen yükü
    (yavaş söner ×0.9/gün), doygunluk serisi. forecast() dünkü bitki
    halinden bugünün zorlamasını üretir.
    """

    def __init__(self, seed):
        self.rng = np.random.default_rng(seed)
        self.log = []  # (day, event, detail)
        self.sat_streak = 0
        self.drain_fail_left = 0
        self.pathogen = 0.0
        self._heat_left = 0
        self._cold_left = 0

    def _emit(self, day, event, detail=""):
        self.log.append({"day": day, "event": event, "detail": detail})

    def forecast(self, day, doy, temp, rain, moist, fc_ref, clay=False):
        """Bugünün zorlaması. DÖNEN: temp_delta/rain_extra/irrig/fert/
        drain_mult/pathogen_boost/no_rain anahtarlı sözlük."""
        f = {"temp_delta": 0.0, "rain_extra": 0.0, "irrig_mm": 0.0,
             "fert_mass": 0.0, "drain_mult": 1.0, "pathogen_boost": 0.0,
             "no_rain": False}
        doy = doy % 365
        summer = 150 < doy < 250
        winter = doy > 300 or doy < 60

        if self._heat_left > 0:
            f["temp_delta"] += 8.0
            self._heat_left -= 1
        elif summer and self.rng.random() < P_HEAT_SUMMER:
            self._heat_left = 2
            f["temp_delta"] += 8.0
            self._emit(day, "heat_wave", "+8C/3g")

        if self._cold_left > 0:
            f["temp_delta"] -= 10.0
            self._cold_left -= 1
        elif winter and self.rng.random() < P_COLD_WINTER:
            self._cold_left = 2
            f["temp_delta"] -= 10.0
            self._emit(day, "cold_snap", "-10C/3g")

        p_rain = P_RAIN_WINTER if winter else P_RAIN_SUMMER
        if not summer and not winter:
            p_rain = (P_RAIN_SUMMER + P_RAIN_WINTER) / 2.0
        if self.rng.random() < p_rain:
            f["rain_extra"] = 25.0
            self._emit(day, "heavy_rain", "+25mm")

        # Durum-koşullu: doygunluk serisi arızayı davet eder.
        self.sat_streak = self.sat_streak + 1 if moist > fc_ref else 0
        if self.drain_fail_left > 0:
            f["drain_mult"] = 0.3
            self.drain_fail_left -= 1
        elif self.sat_streak >= 3:
            p = P_DRAIN_FAIL + (0.15 if clay else 0.0)
            if self.rng.random() < p:
                self.drain_fail_left = 4
                f["drain_mult"] = 0.3
                self._emit(day, "drainage_failure", "x0.3/5g")

        # Gizli yük: doygun+ılıkta filizlenir, yavaş söner.
        self.pathogen *= 0.9
        if moist > fc_ref and temp > 15.0:
            if self.rng.random() < P_PATHOGEN:
                self.pathogen = min(2.0, self.pathogen + 1.0)
                self._emit(day, "pathogen_pressure",
                           f"yuk={self.pathogen:.1f}")
        f["pathogen_boost"] = float(self.pathogen)
        return f


def _mkplant(soil, moist):
    p = PlantParams()
    base = soil_overrides(soil) if isinstance(soil, str) else dict(soil)
    for k, v in base.items():
        setattr(p, k, v)
    pl = Plant(p, 0)
    pl.soil_moisture = moist
    pl.ec_mass = p.ec_baseline * moist
    return pl, p


def _row(run, day, temp, pl, lobe_sets, rh=""):
    return {
        "run": run, "day": day, "temp": temp,
        "soil_moisture": round(pl.soil_moisture, 3),
        "soil_ec": round(pl.ec, 4),
        "leaf": round(pl.leaf_health, 3),
        "root": round(pl.root_health, 3),
        "wb": round(pl.water_balance, 4),
        "stress": stress_index(pl.water_balance, pl.leaf_health,
                               pl.root_health),
        "stage": pl.stage.name,
        "lobe_sets": lobe_sets,
        "rh": rh,
        "salt_res": round(pl.salt_last.get("residual", 0.0), 12),
        "o2": pl.o2_deficit_ticks,
    }


def run_ensemble(n_runs, days=12, soil="fiziksel-v1", climate_seed=777,
                 event_seed0=9000, doy0=200, moist0=30.0,
                 rh_mode=None):
    """Topluluk koşusu: PAYLAŞILAN taban iklim + koşu-başına olay akışı.

    Aynı başlangıç, farklı olay zincirleri (kullanıcının RUN mantığı).
    rh_mode="mixed": koşu-başına tohumlu RH rejimi (0.3/0.5/0.8) —
    VPD yayılımı çıkarım verisi içindir; None = VPD çarpanı 1.0
    (eski davranış birebir). Stokastik gübre/sulama eylemleri her
    koşuda çekilir (eylem uzayını kapsamak için).
    DÖNEN: (yörüngeler DataFrame, olay günlüğü DataFrame).
    """
    from sim.plant_sim import vpd_kpa
    clim = WorldDriver(seed=climate_seed)
    # DÜZELTME (§9.50): sıcaklık da doy0+t takviminden alınır (önce
    # abs_day=t Ocak soğuğuydu, yağmur/fotoperiyot Temmuzdu — tutarsız
    # taban iklimi; VPD yayılımını sıkıştırıyordu).
    base = [(clim.temperature(doy0 + t),
             clim.rain_event_mm((doy0 + t) % 365, abs_day=doy0 + t),
             clim.photoperiod_hours((doy0 + t) % 365))
            for t in range(days)]
    trajs, logs = [], []
    for r in range(n_runs):
        eng = EventEngine(seed=event_seed0 + r)
        arng = np.random.default_rng(event_seed0 + r + 777001)
        rh_reg = (RH_REGIMES[int(arng.integers(0, len(RH_REGIMES)))]
                  if rh_mode == "mixed" else None)
        pl, p = _mkplant(soil, moist0)
        fc_ref = p.theta_fc if p.theta_s > 0 else p.field_capacity
        mp = SensorMapper()
        lobe = PlantNpuLobe(every_n_frames=1)
        m = moist0
        for d in range(days):
            t0, r0, ph = base[d]
            f = eng.forecast(d, doy0 + d, t0, r0, m, fc_ref)
            rain = r0 + f["rain_extra"]
            tday = t0 + f["temp_delta"]
            fert = f["fert_mass"]
            irr = f["irrig_mm"]
            if eng.rng.random() < P_FERT:
                fert += 30.0
                eng._emit(d, "action_fert", "30 kutle")
            if eng.rng.random() < P_IRRIG:
                irr += 15.0
                eng._emit(d, "action_irrig", "15mm")
            pl.step(doy0 + d, tday, ph, rain,
                    irrigation_mm=irr,
                    fertilizer_dose_mass=fert,
                    drain_mult=f["drain_mult"],
                    pathogen_boost=f["pathogen_boost"],
                    rh_frac=rh_reg)
            m = pl.soil_moisture
            snap = {"temp": t0, "rain_mm": rain,
                    "soil_moisture": pl.soil_moisture, "soil_ec": pl.ec,
                    "tuber_mass": pl.tuber_mass}
            lobe.on_frame(mp.update(snap))
            row = _row(f"ENS-{r}", d, round(tday, 2),
                       pl, lobe.sent_batches)
            row.update({
                "rh": ("" if rh_reg is None else rh_reg),
                "vpd": ("" if rh_reg is None
                        else round(vpd_kpa(tday, rh_reg), 3)),
                "rain": round(rain, 2),
                "fert": round(fert, 1),
                "irrig": round(irr, 1),
            })
            trajs.append(row)
        for e in eng.log:
            logs.append({"run": f"ENS-{r}", **e})
    return pd.DataFrame(trajs), pd.DataFrame(logs)


def preset_runs(days=12, climate_seed=777, doy0=200, moist0=30.0):
    """Kullanıcının 4 RUN senaryosu (deterministik zorlama metinleri)."""
    clim = WorldDriver(seed=climate_seed)
    # DÜZELTME (§9.50): sıcaklık da doy0+t takviminden alınır (önce
    # abs_day=t Ocak soğuğuydu, yağmur/fotoperiyot Temmuzdu — tutarsız
    # taban iklimi; VPD yayılımını sıkıştırıyordu).
    base = [(clim.temperature(doy0 + t),
             clim.rain_event_mm((doy0 + t) % 365, abs_day=doy0 + t),
             clim.photoperiod_hours((doy0 + t) % 365))
            for t in range(days)]
    scripts = {
        # gübre → yağmur → soğuk
        "RUN1": {2: {"fert": 30.0}, 5: {"rain_extra": 20.0},
                 6: {"rain_extra": 20.0}, 8: {"temp_delta": -12.0},
                 9: {"temp_delta": -12.0}},
        # gübre → kuraklık → sıcak
        "RUN2": {2: {"fert": 30.0}, 8: {"temp_delta": 10.0},
                 9: {"temp_delta": 10.0}},
        # gübre → normal hava
        "RUN3": {2: {"fert": 30.0}},
        # gübre → aşırı yağış → kötü drenaj (killi zemin)
        "RUN4": {2: {"fert": 30.0}, 5: {"rain_extra": 35.0,
                                              "drain_mult": 0.3},
                 6: {"rain_extra": 35.0, "drain_mult": 0.3},
                 **{d: {"drain_mult": 0.3} for d in (7, 8, 9)}},
    }
    soils = {"RUN4": V1_CLAY_E}
    out, logs = {}, []
    for name, script in scripts.items():
        pl, _p = _mkplant(soils.get(name, "fiziksel-v1"), moist0)
        mp = SensorMapper()
        lobe = PlantNpuLobe(every_n_frames=1)
        rows = []
        for d in range(days):
            t0, r0, ph = base[d]
            f = dict(script.get(d, {}))
            rain = r0 + f.get("rain_extra", 0.0)
            pl.step(doy0 + d, t0 + f.get("temp_delta", 0.0), ph, rain,
                    irrigation_mm=f.get("irrig", 0.0),
                    fertilizer_dose_mass=f.get("fert", 0.0),
                    drain_mult=f.get("drain_mult", 1.0))
            snap = {"temp": t0, "rain_mm": rain,
                    "soil_moisture": pl.soil_moisture, "soil_ec": pl.ec,
                    "tuber_mass": pl.tuber_mass}
            lobe.on_frame(mp.update(snap))
            rows.append(_row(name, d, round(t0, 2), pl,
                             lobe.sent_batches))
            if d in script:
                logs.append({"run": name, "day": d, "event": "scheduled",
                             "detail": str(sorted(f))})
        out[name] = rows
    return out, logs
