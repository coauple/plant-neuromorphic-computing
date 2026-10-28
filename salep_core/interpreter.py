"""CPU Tercuman ses katmani: komut/profil -> Turkce aciklama cumleleri.

Kural tabanli, stdlib-only (scenario_engine.interpret kullanir).
C++ tarafina dokunmaz; yalniz konusur. Calistirma: python3 interpreter.py
"""

import scenario_engine as se

SENS_THRESH = 50

# kanonik sensor -> TR ad (scenario_engine.SENSORS ile ayni kume)
SENSOR_TR = {
    "hs": "Hava Sıcaklığı", "ts": "Toprak Sıcaklığı",
    "hn": "Hava Nemi", "tn": "Toprak Nemi",
    "ph": "Toprak pH", "npk": "Toprak NPK", "ec": "EC/Tuzluluk",
}

# sensor -> grounding post tau'su (POST_MAP'taki NEM/EC/SIC/TS/TN/PH/NPK
# postlarindan; X1/X2 capraz postlardir, buraya girmez)
SENSOR_TAU = {"hs": 4, "ts": 4, "hn": 12, "tn": 12,
              "ph": 4, "npk": 12, "ec": 12}

SCENARIO_TR = {
    "drought": "KURAKLIK", "sulama": "SULAMA",
    "soguk": "SOĞUK DALGA", "reset": "VARSAYILAN",
}


def on_off(val):
    """v>=50 ON (esik, main_plant_npu.cpp ile ayni)."""
    return "ON" if val >= SENS_THRESH else "OFF"


def channel_tag(sensor, val):
    """'hs=85(ON,τ4,b=1)' bicimi kisa kanal etiketi."""
    tau = SENSOR_TAU[sensor]
    return f"{sensor}={val}({on_off(val)},τ{tau},b={se.sensor_burst(tau)})"


def describe_profile(values):
    """{sensor: deger} -> TR profil satirlari."""
    out = []
    for s in se.SENSORS:
        if s in values:
            v = values[s]
            out.append(f"{SENSOR_TR[s]} {v} → {on_off(v)} "
                       f"(eşik {SENS_THRESH}, τ{SENSOR_TAU[s]} faz şifresi, "
                       f"burst {se.sensor_burst(SENSOR_TAU[s])})")
    return out


def describe_set(sensor, val):
    """Tek sensor komutu -> CPU Tercuman cumleleri."""
    tau = SENSOR_TAU[sensor]
    state = on_off(val)
    if state == "ON":
        dest = (f"{tau}. bant faz şifreleri CS olarak, ON-US dalıyla "
                f"birlikte postlara gönderiliyor.")
    else:
        dest = (f"kanal eşik altına indi; OFF-US hattı aktif, "
                f"{tau}. bant CS'i desteksiz kaldı.")
    return [f"{SENSOR_TR[sensor]} {val} olarak ayarlandı → {state}.",
            dest]


def describe_reset():
    """RESET -> CPU Tercuman cumlesi."""
    return ["Profil sıfırlandı: hs=75(ON) hn=60(ON), diğerleri 40(OFF).",
            "NPU kanalları varsayılan faz şifrelerine döndü."]


def describe_pause():
    """STOP -> CPU Tercuman cumlesi."""
    return ["Sistem duraklatıldı. Motor dondu (tick işlemiyor), "
            "profil ve ağırlıklar korunuyor."]


def describe_resume():
    """CONTINUE -> CPU Tercuman cumlesi."""
    return ["Sistem devam ediyor. Motor kaldığı tick'ten sürüyor."]


def describe_gate_off(sensor):
    """SENSOR_OFF -> CPU Tercuman cumlesi."""
    return [f"{SENSOR_TR[sensor]} kanalı kapatıldı — afferent kapı açık, "
            f"CS üretilmiyor (profil değeri korunuyor)."]


def describe_gate_on(sensor):
    """SENSOR_ON -> CPU Tercuman cumlesi."""
    return [f"{SENSOR_TR[sensor]} kanalı açıldı — afferent kapı kapalı, "
            f"faz şifreleri yeniden akıyor."]


def describe_scenario(name, profile):
    """Preset senaryo -> CPU Tercuman cumleleri."""
    tr = SCENARIO_TR.get(name, name.upper())
    tags = " ".join(channel_tag(s, profile[s])
                    for s in se.SENSORS if s in profile)
    lines = [f"Senaryo algılandı: {tr}.",
             f"Kanal profili: {tags}"]
    offs = [s for s in se.SENSORS
            if s in profile and profile[s] < SENS_THRESH]
    if offs:
        lines.append("Eşik altı kanallar OFF-US hattında: " +
                     ", ".join(SENSOR_TR[s] for s in offs) +
                     " — ters koşullar da donanımda temsil ediliyor.")
    lines.append("NPU'ya faz şifreleri fırlatılıyor; çapraz postlar "
                 "(X1/X2) eşzamanlılık avında.")
    return lines


def describe_natural(text, motor_lines):
    """Dogal dil girdisi + urettigi SET'ler -> CPU Tercuman cumleleri."""
    prof = se._lines_to_profile(motor_lines)
    bits = []
    for s, v in prof.items():
        if v >= SENS_THRESH:
            bits.append(f"{SENSOR_TR[s]} kanalı ON'a geçti "
                        f"({s}={v}; τ{SENSOR_TAU[s]} faz şifreleri CS)")
        else:
            bits.append(f"{SENSOR_TR[s]} eşik altında kaldı "
                        f"({s}={v}; OFF-US hattı)")
    head = f"Yorum: {text.strip()} → " + \
        ", ".join(f"{s}={v}" for s, v in prof.items()) + "."
    return [head] + bits


def unknown_speech(text):
    """Anlasilmayan girdi -> yardim (ERR DEGIL)."""
    return ["Komut Yorumlayıcı sözlüğünde eşleşme yok. "
            "Deneyin: 'nem 70', '/scenario drought', "
            "'reset', '/set hs 80'."]


if __name__ == "__main__":
    # --- POST_MAP tutarliligi (grounding post tau'lari) ---
    ground = {ch: tau for post, (ch, tau) in se.POST_MAP.items()
              if post not in ("X1", "X2")}
    assert ground == {"hn": 12, "ec": 12, "hs": 4, "ts": 4,
                      "tn": 12, "ph": 4, "npk": 12}
    assert set(SENSOR_TAU) == set(se.SENSORS)
    for s, t in SENSOR_TAU.items():
        assert ground[s] == t, s

    # --- on_off esigi (C++ ile ayni) ---
    assert on_off(49) == "OFF" and on_off(50) == "ON"

    # --- describe_set ---
    sp = describe_set("hs", 85)
    assert "ON" in sp[0] and "Hava Sıcaklığı" in sp[0]
    sp = describe_set("tn", 15)
    assert "OFF" in sp[0] and "OFF-US" in sp[1]

    # --- describe_scenario (drought) ---
    prof = {s: v for s, v in
            zip(se.SENSORS, (85, 60, 20, 15, 40, 40, 40))}
    sp = describe_scenario("drought", prof)
    assert sp[0] == "Senaryo algılandı: KURAKLIK."
    assert "hs=85(ON,τ4,b=1)" in sp[1] and "tn=15(OFF" in sp[1]

    # --- describe_natural (plan ornegi) ---
    sp = describe_natural("Hava aniden ısındı", ["SET hs 85"])
    assert "hs=85" in sp[0]
    assert any("ON'a geçti" in x for x in sp[1:])

    # --- kapi konusmalari ---
    assert "kapatıldı" in describe_gate_off("tn")[0]
    assert "açıldı" in describe_gate_on("tn")[0]
    assert "duraklatıldı" in describe_pause()[0]
    assert "devam ediyor" in describe_resume()[0]

    # --- unknown ERR degil ---
    sp = unknown_speech("bugün hava güzel")
    assert any("nem 70" in x for x in sp)

    # --- interpret ile uctan uca (TR/EN) ---
    r = se.interpret("Hava aniden ısındı")
    assert r["kind"] == "natural" and r["motor_lines"] == ["SET hs 85"], r
    r = se.interpret("/scenario drought")
    assert r["kind"] == "scenario" and len(r["motor_lines"]) == 7, r
    assert r["speech"][0] == "Senaryo algılandı: KURAKLIK."
    r = se.interpret("/set hs 80")
    assert r["kind"] == "set" and r["brief"] == "hs=80", r
    r = se.interpret("reset")
    assert r["kind"] == "reset", r
    r = se.interpret("quit")
    assert r["kind"] == "quit" and r["motor_lines"] == ["QUIT"], r
    r = se.interpret("bugün hava güzel")
    assert r["kind"] == "unknown" and r["motor_lines"] == [], r
    r = se.interpret("# yorum")
    assert r["kind"] == "comment", r
    r = se.interpret("set air humidity to 80")
    assert r["kind"] == "natural" and r["motor_lines"] == ["SET hn 80"], r
    # --- kapi komutlari (plan ornekleri) ---
    r = se.interpret("/sensor-off hn")
    assert r["kind"] == "sensor_off"
    assert r["motor_lines"] == ["SENSOR_OFF hn"], r
    assert "kapatıldı" in r["speech"][0]
    r = se.interpret("/sensor-on hn")
    assert r["kind"] == "sensor_on"
    assert r["motor_lines"] == ["SENSOR_ON hn"], r
    r = se.interpret("hn kapa")
    assert r["kind"] == "sensor_off"
    assert r["motor_lines"] == ["SENSOR_OFF hn"], r
    r = se.interpret("disable soil moisture")
    assert r["kind"] == "sensor_off"
    assert r["motor_lines"] == ["SENSOR_OFF tn"], r
    print("interpreter: tum assert testleri gecti")
