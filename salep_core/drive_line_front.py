"""Hat-onu surucu: sim -> sensors.csv + pspikes.csv (+ stages.csv).

Uretim hattinin ONUNU besler (npu_sensory_plant girdisi olan dokumante
CSV sozlesmesi). Donuk sim modulleri SADECE cagrilir, degistirilmez.
v3'e DEGIL hatta yazar; v3 hattin ciktisini tuketir (run_chain_v3.py).
Etiket (stage) zincire GIRMEZ; yalniz degerlendirme anahtari.
ADDITIVE-ONLY yeni dosya.
"""
import argparse
import csv
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from sim.world_state import WorldState  # noqa: E402
from sim.sensor_map import SensorMapper  # noqa: E402
from sim.electro import ElectroState  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Hat onu: sim->sensor/spike")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--days", type=int, default=130)
    ap.add_argument("--outdir", default="/tmp/line_front")
    ap.add_argument("--drought", action="store_true")
    ap.add_argument("--drought-from", type=int, default=0)
    ap.add_argument("--drought-len", type=int, default=-1)
    ap.add_argument("--irrig", type=float, default=0.0)
    ap.add_argument("--fert", type=float, default=0.0)
    ap.add_argument("--soil", default=None)
    ap.add_argument("--weather", default=None)
    ap.add_argument("--weather-year", type=int, default=2025)
    ap.add_argument("--weather-uv", default=None)
    ap.add_argument("--irrig-from", type=int, default=0)
    ap.add_argument("--irrig-len", type=int, default=-1)
    ap.add_argument("--fert-from", type=int, default=0)
    ap.add_argument("--fert-len", type=int, default=-1)
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    ws = WorldState(seed=a.seed, speed=1.0, weather_csv=a.weather,
                    weather_year=a.weather_year, weather_uv=a.weather_uv)
    if a.drought:
        ln = a.days if a.drought_len < 0 else a.drought_len
        ws.inject_scenario({d: {"force_no_rain": True}
                            for d in range(a.drought_from,
                                           a.drought_from + ln)})
    if a.soil:
        ws.set_soil(a.soil)
    mapper = SensorMapper()
    el = ElectroState()
    sens_p = os.path.join(a.outdir, "sensors.csv")
    spk_p = os.path.join(a.outdir, "pspikes.csv")
    stg_p = os.path.join(a.outdir, "stages.csv")
    stages = set()
    with open(sens_p, "w", newline="") as fs, \
            open(spk_p, "w", newline="") as fp, \
            open(stg_p, "w", newline="") as ft:
        ws_, wp, wt = csv.writer(fs), csv.writer(fp), csv.writer(ft)
        ilen = a.days if a.irrig_len < 0 else a.irrig_len
        flen = a.days if a.fert_len < 0 else a.fert_len
        for day in range(a.days):
            if a.irrig and a.irrig_from <= day < a.irrig_from + ilen:
                ws.inject_irrigation(a.irrig)
            if a.fert and a.fert_from <= day < a.fert_from + flen:
                ws.inject_fertilizer(a.fert)
            ws.clock.sim_day = day
            ws.clock.day_frac = 0.5
            ws._last_stepped_day = -1
            ws.step_if_needed()
            snap = ws.get_snapshot()
            s = mapper.update(snap, fert_dose=snap.get("fert_dose", 0.0))
            ws_.writerow([day, s["hn"], s["ec"], s["hs"], s["ts"],
                          s["tn"], s["ph"], s["npk"]])
            r = el.step(snap.get("temp", 20.0), snap.get("rain_mm", 0.0),
                        snap.get("irrig_mm", 0.0),
                        snap.get("water_balance", 0.0),
                        snap.get("leaf_health", 100.0),
                        snap.get("root_health", 100.0),
                        snap.get("stage", "DORMANT"), a.seed, day)
            sp = el.spikes_for_day(r[1], r[2], a.seed, day)
            for ch in (0, 1):
                for t in sp[ch]:
                    wp.writerow([day, ch, t])
            stages.add(snap.get("stage", "?"))
            wt.writerow([day, snap.get("stage", "?")])
    print(f"OZET-FRONT: gun={a.days} seed={a.seed} "
          f"stage={sorted(stages)} -> {a.outdir}")


if __name__ == "__main__":
    main()
