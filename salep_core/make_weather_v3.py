"""weather_v3 sentezi (SPEC on-kayit): W-base/hot/cold/wet + U-hi/lo.

130 gun, 2025-01-01'den. W-base: 12->27C dogrusal + yagmur gunleri
(20,21,50,80,110 x8mm). Turevler birebir ayni yagmurla (sicaklik-tek).
U dosyalari: time + uv_index_max + uv_index_clear_sky_max (0..25).
ADDITIVE-ONLY; sim dosyalari okur, degistirmez.
"""
import csv
import datetime
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "weather_v3")
DAYS = 130
RAIN_DAYS = {20: 8.0, 21: 8.0, 50: 8.0, 80: 8.0, 110: 8.0}


def base_temp(d):
    return 12.0 + (27.0 - 12.0) * d / (DAYS - 1)


def write_w(name, temp_fn, rain_fn):
    with open(os.path.join(OUT, name), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(("time", "temperature_2m_mean (C)",
                    "rain_sum (mm)"))
        for d in range(DAYS):
            day = datetime.date(2025, 1, 1) + datetime.timedelta(days=d)
            w.writerow((day.isoformat(), f"{temp_fn(d):.1f}",
                        f"{rain_fn(d):.1f}"))


def write_u(name, uv_fn, clear=9.0):
    with open(os.path.join(OUT, name), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(("time", "uv_index_max", "uv_index_clear_sky_max"))
        for d in range(DAYS):
            day = datetime.date(2025, 1, 1) + datetime.timedelta(days=d)
            w.writerow((day.isoformat(), f"{uv_fn(d):.1f}", f"{clear:.1f}"))


def main():
    os.makedirs(OUT, exist_ok=True)
    rain = lambda d: RAIN_DAYS.get(d, 0.0)  # noqa: E731
    write_w("W-base.csv", base_temp, rain)
    write_w("W-hot.csv", lambda d: base_temp(d) + 6.0, rain)
    write_w("W-cold.csv", lambda d: base_temp(d) - 6.0, rain)
    write_w("W-wet.csv", base_temp,
            lambda d: RAIN_DAYS.get(d, 0.0) * 3.0 +
            (8.0 if d in (30, 31, 90, 91) else 0.0))
    write_w("W-wetcold.csv", lambda d: base_temp(d) - 6.0,
            lambda d: RAIN_DAYS.get(d, 0.0) * 3.0 +
            (8.0 if d in (30, 31, 90, 91) else 0.0))
    write_u("U-hi.csv", lambda d: 9.0)
    write_u("U-lo.csv", lambda d: 1.5)
    # A2 siddet basamaklari (STIMULUS_SNR_SPEC): S1 yagmur[20,21,50]+0C,
    # S2 yagmur[20,21]+3C (S3 = W-dry).
    write_w("W-s1.csv", base_temp,
            lambda d: RAIN_DAYS.get(d, 0.0) if d in (20, 21, 50) else 0.0)
    write_w("W-s2.csv", lambda d: base_temp(d) + 3.0,
            lambda d: RAIN_DAYS.get(d, 0.0) if d in (20, 21) else 0.0)
    print(f"OZET-WEATHER: 9 dosya -> {OUT}")


if __name__ == "__main__":
    main()
