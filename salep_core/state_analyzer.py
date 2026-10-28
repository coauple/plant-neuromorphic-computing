"""Oturum durumu cozuleyici: telemetri + profil -> sinif/barlar (saf fonksiyon).

C++ verisinden hesaplar, gomulu iddia yok:
- ortam sinifi: profil + esik-50 ON/OFF desenini en yakin presete
  uzaklikla eslestirir (drought/sulama/soguk/reset).
- vitality: pencere ici ates sayisi, kanal basina tasiyici yogunlugu.
- ogrenme %: w degerini OTURUM ici olculen min/max ile olcekler
  (sabit tavan gomulmez).
Calistirma: python3 state_analyzer.py
"""

SENSORS = ("hs", "ts", "hn", "tn", "ph", "npk", "ec")
SENS_THRESH = 50

PRESETS = {
    "drought": {"hs": 85, "ts": 60, "hn": 20, "tn": 15, "ph": 40,
                "npk": 40, "ec": 40},
    "sulama": {"hs": 60, "ts": 55, "hn": 80, "tn": 90, "ph": 40,
               "npk": 40, "ec": 40},
    "soguk": {"hs": 20, "ts": 15, "hn": 60, "tn": 40, "ph": 40,
              "npk": 40, "ec": 40},
    "reset": {"hs": 75, "ts": 40, "hn": 60, "tn": 40, "ph": 40,
              "npk": 40, "ec": 40},
}

ENV_TR = {"drought": "KURAKLIK RİSKİ", "sulama": "SULAMA ETKİSİ",
          "soguk": "SOĞUK BASKI", "reset": "NOMİNAL"}


def on_off_pattern(profile):
    """{sensor: deger} -> {sensor: bool ON} deseni."""
    return {s: profile.get(s, 0) >= SENS_THRESH for s in SENSORS}


def classify_env(profile):
    """En yakin preset: (ad, on_off_uyum_orani). Uzaklik = |v-p| toplami."""
    best, best_d = "reset", None
    for name, preset in PRESETS.items():
        d = sum(abs(profile.get(s, 0) - preset[s]) for s in SENSORS)
        if best_d is None or d < best_d:
            best, best_d = name, d
    agree = sum(1 for s in SENSORS
                if (profile.get(s, 0) >= SENS_THRESH) ==
                (PRESETS[best][s] >= SENS_THRESH))
    return best, agree / len(SENSORS)


def vitality(fire_counts, window):
    """Pencere ici ates: {post: oran/tick}. fire_counts={post: n}."""
    if window <= 0:
        return {k: 0.0 for k in fire_counts}
    return {k: v / window for k, v in fire_counts.items()}


def carrier_density(cc_sums, window):
    """Kanal basina ortalama tasiyici: {kanal: ort/tick}."""
    if window <= 0:
        return {k: 0.0 for k in cc_sums}
    return {k: v / window for k, v in cc_sums.items()}


def learning_pct(w_now, w_min, w_max):
    """Oturum min/max ile olcekli ogrenme % (tavan gomulmez)."""
    if w_min is None or w_max is None:
        return 0.0  # olcek henuz yok (ilk telemetri oncesi)
    if w_max - w_min < 1e-9:
        return 0.0
    return max(0.0, min(1.0, (w_now - w_min) / (w_max - w_min)))


if __name__ == "__main__":
    # --- ortam sinifi: bilinen profiller ---
    name, agree = classify_env(dict(PRESETS["drought"]))
    assert name == "drought" and agree == 1.0
    name, agree = classify_env({"hs": 85, "ts": 60, "hn": 20, "tn": 15,
                                "ph": 40, "npk": 40, "ec": 40})
    assert name == "drought"
    name, _ = classify_env({"hs": 0, "ts": 0, "hn": 0, "tn": 0,
                            "ph": 0, "npk": 0, "ec": 0})
    assert name == "soguk"  # uzaklikla en yakin (hepsi dusuk)
    assert ENV_TR["drought"] == "KURAKLIK RİSKİ"
    # --- desen ---
    pat = on_off_pattern({"hs": 85, "ts": 60, "hn": 20, "tn": 15,
                          "ph": 40, "npk": 40, "ec": 40})
    assert pat == {"hs": True, "ts": True, "hn": False, "tn": False,
                   "ph": False, "npk": False, "ec": False}
    # --- vitality / yogunluk ---
    assert vitality({"NEM": 5}, 100) == {"NEM": 0.05}
    assert vitality({"NEM": 5}, 0) == {"NEM": 0.0}
    assert carrier_density({"hn": 200}, 100) == {"hn": 2.0}
    # --- ogrenme % (oturum min/max) ---
    assert learning_pct(1.3, 0.2, 2.0) == abs((1.3 - 0.2) / 1.8)
    assert learning_pct(0.2, 0.2, 0.2) == 0.0
    assert learning_pct(5.0, 0.2, 2.0) == 1.0  # tavan disi kirpilir
    print("state_analyzer: tum assert testleri gecti")
