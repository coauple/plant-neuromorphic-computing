"""Tek başına NPU'suz koşu — Salep Dijital İkizi (W2).

    WorldState + SensorMapper + Frame ile days gün koşar; NpuBridge
    KULLANILMAZ (NPU'suz tam çalışır). Her günde K6 sızıntı assert'i,
    sonunda özet basar.

    Çalıştırma:
        cd salep_core
        .venv/bin/python -m sim.run [--days 365] [--seed 42]

    Anayasa: §9.20 (W2); K6 sızıntı yasağı; G11 import sınırı.
"""

import argparse
import sys

from sim.world_state import WorldState
from sim.sensor_map import SensorMapper
from sim.frame import Frame, FrameBuffer, compute_visuals

LEAK_KEYS = ("ground_truth", "root_rot", "salt_burn", "plant_death")


def run(days=365, seed=42, verbose=True, weather_csv=None,
        weather_year=None, weather_uv=None):
    """NPU'suz koşu; özet sözlüğü döner, sızıntıda assert fırlatır."""
    ws = WorldState(seed=seed, speed=1.0, weather_csv=weather_csv,
                    weather_year=weather_year, weather_uv=weather_uv)
    mapper = SensorMapper()
    fb = FrameBuffer()

    stages = []
    sens_min = {}
    sens_max = {}
    for day in range(days):
        ws.clock.sim_day = day
        ws.clock.day_frac = 0.5
        ws._last_stepped_day = -1
        ws.step_if_needed()
        snap = ws.get_snapshot()

        fert = snap.get("fert_dose", 0.0)
        sensors = mapper.update(snap, fert_dose=fert)

        f = Frame()
        f.sim_day = snap["sim_day"]
        f.day_of_year = snap["day_of_year"]
        f.temp = snap["temp"]
        f.photoperiod = snap["photoperiod"]
        f.rain_mm = snap["rain_mm"]
        f.stage = snap["stage"]
        f.leaf_health = snap["leaf_health"]
        f.root_health = snap["root_health"]
        f.tuber_mass = snap["tuber_mass"]
        f.water_balance = snap["water_balance"]
        f.soil_moisture = snap["soil_moisture"]
        f.soil_ec = snap["soil_ec"]
        f.o2_deficit_ticks = snap["o2_deficit_ticks"]
        f.stem_height = snap.get("stem_height", 0.0)
        f.uv_index = snap.get("uv_index")
        for k, v in sensors.items():
            setattr(f, k, v)

        f = compute_visuals(f)
        fb.write(f)

        frame_str = str(vars(fb.read())).lower()
        for bad in LEAK_KEYS:
            assert bad not in frame_str, \
                f"run BAŞARISIZ: {bad} frame'e sızdı! gün={day}"

        stages.append(snap["stage"])
        for k, v in sensors.items():
            sens_min[k] = v if k not in sens_min else min(sens_min[k], v)
            sens_max[k] = v if k not in sens_max else max(sens_max[k], v)

        if verbose and (day + 1) % 100 == 0:
            print(f"  ... gün {day + 1}/{days} stage={snap['stage']}")

    final = fb.read()
    stage_run = []
    for s in stages:
        if not stage_run or stage_run[-1] != s:
            stage_run.append(s)
    summary = {
        "days": days,
        "seed": seed,
        "weather_csv": weather_csv,
        "weather_year": weather_year,
        "final_day": final.sim_day,
        "final_stage": final.stage,
        "stage_run": stage_run,
        "sens_min": sens_min,
        "sens_max": sens_max,
        "tuber_mass": final.tuber_mass,
        "soil_moisture": final.soil_moisture,
    }
    if verbose:
        print(f"✅ run TAMAMLANDI: {days} gün (NPU'suz), "
              f"son stage={final.stage}, "
              f"stage seyri={'→'.join(stage_run)}, "
              f"sızıntı yok")
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description="NPU'suz tek başına koşu (W2)")
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--weather-csv", default=None,
                    help="gerçek gözlem dosyası (Open-Meteo günlük, §9.26)")
    ap.add_argument("--weather-year", type=int, default=None,
                    help="sim günü 0 = 1 Oca bu yıl (varsayılan: dosyanın son yılı)")
    ap.add_argument("--weather-uv", default=None,
                    help="UV gözlem dosyası (Open-Meteo günlük, §9.27)")
    args = ap.parse_args(argv)
    if args.days < 1:
        print("HATA: --days >= 1 olmalı", file=sys.stderr)
        return 1
    run(days=args.days, seed=args.seed, weather_csv=args.weather_csv,
        weather_year=args.weather_year, weather_uv=args.weather_uv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
