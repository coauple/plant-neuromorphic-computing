"""Multi-cycle climate realization — v1.1 (§9.53).

Her yaşam döngüsü yeni bir çevresel gerçekleşmedir (Ege sınırları
içinde), ama tohum mimarisi hiyerarşiktir:

  MASTER → SeedSequence.spawn(cycle) → 4 rol (climate/event/plant/soil)

Aynı master → bit-eşit tekrar. Farklı cycle → farklı yıl-tipi
(sıcaklık anomalisi, yağış çarpanı, genlik) + farklı olay zamanlaması
+ farklı genetik/initial. Takvim süreklidir (cycle'lar art arda
doy'lara oturur); bitki nesli iklim takvimine kilitli değildir
(start offset'leri bağımsız verilebilir).

Ege zarfı: WorldDriver'ın mevsimsel yapısı korunur (kış yağışlı,
yaz kurak); yıl-tipleri TODO-öncül aralıklardadır; sert sıcaklık
kelepçesi iddiayı değil güvenliği korur. Mevcut çekirdeğe DOKUNULMAZ
(yeni modül + yeni kwarg-yok çağrılar).
"""
import numpy as np
import pandas as pd

from sim.plant_sim import (Plant, PlantParams, WorldDriver,
                           jittered_params, soil_overrides)
from sim.events import EventEngine
from sim.sensor_map import SensorMapper
from sim.lobes.plant_npu import PlantNpuLobe
from sim.perturb import stress_index

# TODO: DOĞRULANMADI — Ege yıl-tipi öncülleri (§9.53). Aralıklar
# Akdeniz geçiş iklimi muhakemesidir, gözlem serisiyle kalibre edilecek.
TEMP_ANOMALY_RANGE = (-1.5, 1.5)   # °C, yıllık ortalama kayması
RAIN_FACTOR_RANGE = (0.7, 1.4)     # yıllık yağış çarpanı
AMP_DELTA_RANGE = (-2.0, 2.0)      # mevsim genliği kayması
MOIST0_RANGE = (20.0, 40.0)        # başlangıç nemi (toprak tohumu)
EC0_RANGE = (0.7, 1.2)             # başlangıç EC'si (toprak tohumu)
# Sert zarf: fiziksel iddia değil, güvenlik kelepçesi (Ege ekstremi).
EGE_TEMP_HARD = (-8.0, 48.0)


def derive_cycle_seeds(master_seed, n_cycles):
    """Master → cycle başına {climate, event, plant, soil} tohumları.

    SeedSequence.spawn: kardeş akışlar birbirinden bağımsızdır
    (cycle-1'in tohumunu değiştirmek cycle-0'ı etkilemez — TEST13).
    """
    spawns = np.random.SeedSequence(int(master_seed)).spawn(int(n_cycles))
    out = []
    for s in spawns:
        kids = [int(x.generate_state(1)[0]) % (2 ** 31) for x in s.spawn(4)]
        out.append(dict(zip(("climate", "event", "plant", "soil"), kids)))
    return out


def draw_year_type(climate_seed):
    """Yıl-tipi: Ege sınırları içinde yıllık karakter (deterministik)."""
    rng = np.random.default_rng(int(climate_seed))
    return {
        "temp_anomaly": float(rng.uniform(*TEMP_ANOMALY_RANGE)),
        "rain_factor": float(rng.uniform(*RAIN_FACTOR_RANGE)),
        "amp_delta": float(rng.uniform(*AMP_DELTA_RANGE)),
    }


def run_cycle(cycle_seeds, year_type=None, soil="fiziksel-v1",
              start_abs_day=0, days=365, moist0=None, param_spread=0.13):
    """Tek yaşam döngüsü. DÖNEN: (df, logs, meta)."""
    if year_type is None:
        year_type = draw_year_type(cycle_seeds["climate"])
    world = WorldDriver(
        cycle_seeds["climate"],
        yearly_mean_temp=17.0 + year_type["temp_anomaly"],
        season_amp=11.0 + year_type["amp_delta"])
    base = PlantParams()
    for k, v in soil_overrides(soil).items():
        setattr(base, k, v)
    prng = np.random.default_rng(cycle_seeds["plant"])
    srng = np.random.default_rng(cycle_seeds["soil"])
    pl = Plant(jittered_params(base, prng, spread=param_spread), 0)
    m0 = moist0 if moist0 is not None else float(
        srng.uniform(*MOIST0_RANGE))
    e0 = float(srng.uniform(*EC0_RANGE))
    pl.soil_moisture = m0
    pl.ec_mass = e0 * m0
    eng = EventEngine(seed=cycle_seeds["event"])
    mp = SensorMapper()
    lobe = PlantNpuLobe(every_n_frames=1)
    p = pl.p
    fc_ref = p.theta_fc if p.theta_s > 0 else p.field_capacity
    rows, logs = [], []
    m = m0
    for d in range(days):
        abs_day = start_abs_day + d
        doy = abs_day % 365
        temp = world.temperature(abs_day)
        rain = world.rain_event_mm(doy, abs_day=abs_day) \
            * year_type["rain_factor"]
        photo = world.photoperiod_hours(doy)
        f = eng.forecast(d, doy, temp, rain, m, fc_ref)
        tday = temp + f["temp_delta"]
        rday = rain + f["rain_extra"]
        rh = world.rh_frac
        pl.step(doy, tday, photo, rday,
                irrigation_mm=f["irrig_mm"],
                fertilizer_dose_mass=f["fert_mass"],
                drain_mult=f["drain_mult"],
                pathogen_boost=f["pathogen_boost"], rh_frac=rh)
        world.step_rh(tday, rday,
                      vapor_pts=pl.wb_last.get("uptake", 0.0))
        m = pl.soil_moisture
        snap = {"temp": tday, "rain_mm": rday,
                "soil_moisture": pl.soil_moisture, "soil_ec": pl.ec,
                "tuber_mass": pl.tuber_mass}
        lobe.on_frame(mp.update(snap))
        rows.append({
            "day": d, "abs_day": abs_day, "doy": doy,
            "temp": round(tday, 2), "rain": round(rday, 2),
            "rh": round(rh, 4),
            "soil_moisture": round(pl.soil_moisture, 3),
            "soil_ec": round(pl.ec, 4),
            "leaf": round(pl.leaf_health, 3),
            "root": round(pl.root_health, 3),
            "wb": round(pl.water_balance, 4),
            "stress": stress_index(pl.water_balance, pl.leaf_health,
                                   pl.root_health),
            "stage": pl.stage.name,
            "lobe_sets": lobe.sent_batches,
        })
    for e in eng.log:
        logs.append({**e})
    meta = {"seeds": dict(cycle_seeds), "year_type": year_type,
            "start_abs_day": start_abs_day, "moist0": round(m0, 2),
            "ec0": round(e0, 3)}
    return pd.DataFrame(rows), logs, meta


def run_multicycle(master_seed, n_cycles, days_per_cycle=365,
                   soil="fiziksel-v1", start_gap=0, seed_overrides=None):
    """Art arda dizilmiş N yaşam döngüsü (tek takvim, taze gerçekleşme).

    seed_overrides: {cycle_idx: {rol: tohum}} — bağımsızlık testleri için.
    DÖNEN: (birleşik df [cycle sütunlu], logs, metas).
    """
    seed_overrides = seed_overrides or {}
    seeds = derive_cycle_seeds(master_seed, n_cycles)
    frames, logs, metas = [], [], []
    for c in range(n_cycles):
        cs = dict(seeds[c])
        cs.update(seed_overrides.get(c, {}))
        df, lg, meta = run_cycle(
            cs, soil=soil,
            start_abs_day=c * (days_per_cycle + start_gap),
            days=days_per_cycle)
        df.insert(0, "cycle", c)
        frames.append(df)
        for e in lg:
            logs.append({"cycle": c, **e})
        metas.append(meta)
    out = pd.concat(frames, ignore_index=True) if frames \
        else pd.DataFrame()
    return out, logs, metas


def check_ege_envelope(df):
    """Sert zarf: tüm sıcaklıklar Ege ekstremi içinde mi?"""
    lo, hi = EGE_TEMP_HARD
    return bool(((df.temp >= lo) & (df.temp <= hi)).all())
