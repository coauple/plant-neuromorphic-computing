"""Senaryo motoru: dogal dil / komut -> motor satirlari (SET/RESET/QUIT).

Kural tabanli, stdlib-only (live_term.py ve testler import eder).
C++ tarafindaki cevirici birebir yansitilir (main_plant_npu.cpp):

    sensor_to_spike(value, tau, t): v<50 OFF; t<d_sens ise False;
    ON ise ((t-d_sens) % tau) < burst(tau), burst: tau>=24->3,
    tau>=16->2, aksi halde 1.

Girdi ornekleri:
  /set hn 70            -> ["SET hn 70"]
  /scenario drought     -> ["SET hs 85", ..., "SET ec 40"]
  "toprak nemi 90 olsun"-> ["SET tn 90"]      (TR)
  "set air humidity to 80" -> ["SET hn 80"]   (EN)
  "sulama senaryosu baslat" -> sulama preset  (TR)
  "reset" / "sifirla"   -> ["RESET"]
Motor satirlari buyuk harflidir (SET/RESET/QUIT); sensor adlari kucuk.
"""
import re

SENS_THRESH = 50

# kanonik sensor adlari (C++ sensor_ptr_by_name ile ayni kume)
SENSORS = ("hs", "ts", "hn", "tn", "ph", "npk", "ec")
ALIASES = {"nem": "hn", "sicaklik": "hs", "sic": "hs",
           "humidity": "hn", "temperature": "hs", "temp": "hs"}

# post -> (kanal, tau): PNP_POST_CHAN + PNP_POST_BAND'den
# (sira: NEM,EC,SIC,TS,TN,PH,NPK,X1,X2; band 0->tau4, 1->tau12)
# NOT (§9.14 Duyusal Lob v2): P2 bankasi NEM..X2 <-> p2a.. eslemesi
# (p2a=NEM, p2b=SIC, p2c=replika, p2d/p2e=decoy, p2f=EC-negatif,
# p2g..p2j=TS/TN/PH/NPK). Tam v5 UI eslemesi sonraya; bu not sozlesmedir.
POST_MAP = {
    "NEM": ("hn", 12), "EC": ("ec", 12), "SIC": ("hs", 4),
    "TS": ("ts", 4), "TN": ("tn", 12), "PH": ("ph", 4),
    "NPK": ("npk", 12), "X1": ("hn", 4), "X2": ("hs", 12),
}

PRESETS = {
    "reset": {"hs": 75, "ts": 40, "hn": 60, "tn": 40, "ph": 40,
              "npk": 40, "ec": 40},
    "drought": {"hs": 85, "ts": 60, "hn": 20, "tn": 15, "ph": 40,
                "npk": 40, "ec": 40},
    "sulama": {"hs": 60, "ts": 55, "hn": 80, "tn": 90, "ph": 40,
               "npk": 40, "ec": 40},
    "soguk": {"hs": 20, "ts": 15, "hn": 60, "tn": 40, "ph": 40,
              "npk": 40, "ec": 40},
}
def _norm(s):
    """TR/EN duyarsiz karsilastirma: kucult + aksanlari duzlestir."""
    t = s.strip().lower()
    for a, b in (("İ", "i"), ("ı", "i"), ("ş", "s"), ("ğ", "g"),
                 ("ü", "u"), ("ö", "o"), ("ç", "c")):
        t = t.replace(a, b)
    return t


# TR senaryo takma adlari (anahtarlar _norm'lanmis)
SCENARIO_ALIASES = {"kuraklik": "drought", "kurak": "drought",
                    "drought": "drought", "sulama": "sulama",
                    "irrigation": "sulama", "soguk": "soguk",
                    "cold": "soguk", "sogutma": "soguk",
                    "reset": "reset", "sifirlama": "reset",
                    "varsayilan": "reset", "default": "reset"}


def sensor_burst(tau):
    """C++ sensor_burst ile birebir."""
    if tau >= 24:
        return 3
    if tau >= 16:
        return 2
    return 1


def sensor_to_spike(value, tau, t, d_sens=0):
    """C++ sensor_to_spike ile birebir (CPU cevirici, yalniz harness)."""
    if value < SENS_THRESH:
        return False
    if t < d_sens:
        return False
    return ((t - d_sens) % tau) < sensor_burst(tau)


def canon_sensor(name):
    """Kullanici yazimini kanonik sensor adina cevirir; bilinmiyorsa None."""
    n = name.strip().lower()
    if n in SENSORS:
        return n
    return ALIASES.get(n)


def preset_lines(name):
    """Preset adi -> motor SET satirlari (bilinmiyorsa ValueError)."""
    key = SCENARIO_ALIASES.get(_norm(name))
    if key is None or key not in PRESETS:
        raise ValueError(f"bilinmeyen senaryo: {name!r}")
    return [f"SET {k} {PRESETS[key][k]}" for k in SENSORS]


def _parse_set_cmd(text):
    m = re.match(r"^\s*/set\s+(\w+)\s+(\d+)\s*$", text, re.IGNORECASE)
    if not m:
        return None
    s = canon_sensor(m.group(1))
    v = int(m.group(2))
    if s is None or not 0 <= v <= 100:
        raise ValueError(f"hatali /set: {text!r} "
                         "(sensor: hs|ts|hn|tn|ph|npk|ec, deger 0-100)")
    return [f"SET {s} {v}"]


def _parse_scenario_cmd(text):
    m = re.match(r"^\s*/scenario\s+(\w+)\s*$", text, re.IGNORECASE)
    if not m:
        return None
    return preset_lines(m.group(1))


OFF_VERB = re.compile(r"kapa|kapat|\bclose\b|\bdisable\b|\bkes\b",
                      re.IGNORECASE)
ON_VERB = re.compile(r"açık|acik|\baç\b|\bopen\b|\benable\b",
                     re.IGNORECASE)


def _parse_gate_cmd(text):
    """/sensor-off|on <sensor> -> SENSOR_OFF/ON satiri."""
    m = re.match(r"^\s*/sensor[-_]off\s+(\w+)\s*$", text, re.IGNORECASE)
    if m:
        s = canon_sensor(m.group(1))
        if s is None:
            raise ValueError(f"hatali /sensor-off: {text!r} "
                             "(sensor: hs|ts|hn|tn|ph|npk|ec)")
        return [f"SENSOR_OFF {s}"]
    m = re.match(r"^\s*/sensor[-_]on\s+(\w+)\s*$", text, re.IGNORECASE)
    if m:
        s = canon_sensor(m.group(1))
        if s is None:
            raise ValueError(f"hatali /sensor-on: {text!r} "
                             "(sensor: hs|ts|hn|tn|ph|npk|ec)")
        return [f"SENSOR_ON {s}"]
    return None


def _parse_gate_natural(text):
    """'hn kapa' / 'disable soil moisture' -> SENSOR_OFF/ON; degilse None."""
    off = OFF_VERB.search(text) is not None
    on = ON_VERB.search(text) is not None
    if not off and not on:
        return None
    for w in re.findall(r"[A-Za-zçğıöşüÇĞİÖŞÜ]+", text):
        s = canon_sensor(w)
        if s is not None:
            tag = "SENSOR_OFF" if off else "SENSOR_ON"
            return [f"{tag} {s}"]
    for rx, sensor in NL_RULES:
        if rx.search(text):
            tag = "SENSOR_OFF" if off else "SENSOR_ON"
            return [f"{tag} {sensor}"]
    return None


# --- dogal dil: TR/EN regex kurallari ---
# sira onemli: en ozel (toprak ...) once, genel sonra.
NL_RULES = [
    (re.compile(r"toprak\s*nem", re.IGNORECASE), "tn"),
    (re.compile(r"soil\s*moisture", re.IGNORECASE), "tn"),
    (re.compile(r"toprak\s*s[ıi]cak", re.IGNORECASE), "ts"),
    (re.compile(r"soil\s*temp", re.IGNORECASE), "ts"),
    (re.compile(r"\bnem\b|hava\s*nem|humidity", re.IGNORECASE), "hn"),
    (re.compile(r"s[ıi]cakl[ıi]k|hava\s*s[ıi]cak|temperature|\bheat\b|\btemp\b",
                re.IGNORECASE), "hs"),
    (re.compile(r"\bnpk\b", re.IGNORECASE), "npk"),
    (re.compile(r"\bph\b", re.IGNORECASE), "ph"),
    (re.compile(r"\bec\b", re.IGNORECASE), "ec"),
]

NL_VALUE = re.compile(r"(\d{1,3})")
NL_SCENARIO = re.compile(
    r"(kurakl[ıi]k|drought|sulama|irrigation|soguk|sogutma|cold|"
    r"s[ıi]f[ıi]rla|reset|varsay[ıi]lan|default)", re.IGNORECASE)

# --- yon fiilleri (degersiz dogal dil -> varsayilan siddet) ---
# Yalniz sayi ICERMEYEN girdide ateslenir ("nem 70" eski yoldan gider).
# (hedef sensor, varsayilan deger); degerler preset'lerle tutarli.
DIR_RULES = [
    (re.compile(r"ısın|isin|ısıt|isit|warming|heat", re.IGNORECASE),
     [("hs", 85)]),   # "hava aniden isindi" -> ani isinma
    (re.compile(r"so[gğ]udu|serin|cool", re.IGNORECASE), [("hs", 20)]),
    (re.compile(r"kuru|kurak|drying|\bdry\b", re.IGNORECASE), [("tn", 15)]),
    (re.compile(r"ya[gğ]mur|\brain\b", re.IGNORECASE),
     [("hn", 80), ("tn", 90)]),  # sulama preset'iyle ayni yonde
]


def _parse_direction(text):
    """Degersiz yon fiili -> SET satirlari; degilse None."""
    if NL_VALUE.search(text) is not None:
        return None  # degerli girdi sensor dongusune aittir
    for rx, pairs in DIR_RULES:
        if rx.search(text):
            return [f"SET {s} {v}" for s, v in pairs]
    return None


def _parse_natural(text):
    s = text.strip()
    if re.match(r"(?i)^\s*(reset|s[ıi]f[ıi]rla|quit|exit)\s*$", s):
        if re.match(r"(?i)^\s*(quit|exit)\s*$", s):
            return ["QUIT"]
        return ["RESET"]
    m = NL_SCENARIO.search(s)
    if m and NL_VALUE.search(s) is None:
        word = m.group(1)
        # "soguk" tek basina sayisizsa senaryodur; "soguk 30" ise sensor degeri
        return preset_lines(word)
    dl = _parse_direction(s)
    if dl is not None:
        return dl
    gl = _parse_gate_natural(s)
    if gl is not None:
        return gl
    for rx, sensor in NL_RULES:
        if rx.search(s):
            vm = NL_VALUE.search(s)
            if not vm:
                raise ValueError(f"deger bulunamadi: {text!r} "
                                 "(ornek: 'nem 70 yap')")
            v = int(vm.group(1))
            if not 0 <= v <= 100:
                raise ValueError(f"deger 0-100 olmali: {text!r}")
            return [f"SET {sensor} {v}"]
    return None


def to_motor_lines(text):
    """Kullanici girdisi -> motor satir listesi.

    Bilinmeyen girdide ValueError. Bos/yorum (#) satiri -> [].
    """
    if text is None:
        return []
    s = text.strip()
    if not s or s.startswith("#"):
        return []
    for parser in (_parse_set_cmd, _parse_gate_cmd, _parse_scenario_cmd,
                   _parse_natural):
        lines = parser(s)
        if lines is not None:
            return lines
    raise ValueError(f"anlasilmadi: {text!r} "
                     "(/set, /scenario ya da 'nem 70' gibi dogal dil)")


def _lines_to_profile(lines):
    """Motor SET satirlari -> {sensor: deger} sozlugu."""
    prof = {}
    for ln in lines:
        m = re.match(r"^SET\s+(\w+)\s+(\d+)$", ln)
        if m:
            prof[m.group(1)] = int(m.group(2))
    return prof


def interpret(text):
    """Kullanici girdisi -> CPU Tercuman zarfi (geriye donuk uyumlu).

    Donus: {"kind", "motor_lines", "speech", "brief"}.
    kind: "scenario"|"set"|"natural"|"reset"|"quit"|"sensor_off"|
      "sensor_on"|"comment"|"unknown".
    Anlasilmayan girdi ValueError DEGIL "unknown" doner (canli terminalde
    ham ERR basilmaz). interpreter tembel ice aktarilir (dairesel import
    yok).
    """
    import interpreter  # tembel: interpreter bu modulu ice aktarir
    s = (text or "").strip()
    if not s or s.startswith("#"):
        return {"kind": "comment", "motor_lines": [],
                "speech": [], "brief": ""}
    try:
        lines = to_motor_lines(s)
    except ValueError:
        return {"kind": "unknown", "motor_lines": [],
                "speech": interpreter.unknown_speech(s),
                "brief": "anlaşılmadı"}
    if lines == ["QUIT"]:
        return {"kind": "quit", "motor_lines": lines,
                "speech": ["Oturum kapatılıyor. NPU serbest koşuya "
                           "bırakıldı."],
                "brief": "çıkış"}
    if lines == ["RESET"]:
        return {"kind": "reset", "motor_lines": lines,
                "speech": interpreter.describe_reset(),
                "brief": "reset"}
    if lines and lines[0].startswith("SENSOR_OFF"):
        sens = lines[0].split()[1]
        return {"kind": "sensor_off", "motor_lines": lines,
                "speech": interpreter.describe_gate_off(sens),
                "brief": f"{sens} kapalı"}
    if lines and lines[0].startswith("SENSOR_ON"):
        sens = lines[0].split()[1]
        return {"kind": "sensor_on", "motor_lines": lines,
                "speech": interpreter.describe_gate_on(sens),
                "brief": f"{sens} açık"}
    if _parse_set_cmd(s) is not None:
        m = re.match(r"^\s*/set\s+(\w+)\s+(\d+)\s*$", s, re.IGNORECASE)
        sens, val = canon_sensor(m.group(1)), int(m.group(2))
        return {"kind": "set", "motor_lines": lines,
                "speech": interpreter.describe_set(sens, val),
                "brief": f"{sens}={val}"}
    if re.match(r"^\s*/scenario\s+(\w+)\s*$", s, re.IGNORECASE):
        key = SCENARIO_ALIASES.get(
            _norm(re.match(r"^\s*/scenario\s+(\w+)\s*$", s,
                           re.IGNORECASE).group(1)))
        return {"kind": "scenario", "motor_lines": lines,
                "speech": interpreter.describe_scenario(
                    key, _lines_to_profile(lines)),
                "brief": f"senaryo: {key}"}
    sm = NL_SCENARIO.search(s)
    if sm is not None and NL_VALUE.search(s) is None:
        key = SCENARIO_ALIASES.get(_norm(sm.group(1)))
        return {"kind": "scenario", "motor_lines": lines,
                "speech": interpreter.describe_scenario(
                    key, _lines_to_profile(lines)),
                "brief": f"senaryo: {key}"}
    return {"kind": "natural", "motor_lines": lines,
            "speech": interpreter.describe_natural(s, lines),
            "brief": "doğal dil"}


if __name__ == "__main__":
    # --- sensor_to_spike sifreleme (C++ birebirligi) ---
    assert sensor_to_spike(49, 12, 0) is False      # esik alti OFF
    assert sensor_to_spike(50, 12, 0) is True       # esik ON
    assert sensor_to_spike(60, 12, 5, d_sens=10) is False  # gecikme
    assert sensor_to_spike(75, 4, 0) is True        # tau4 burst=1
    assert sensor_to_spike(75, 4, 1) is False
    assert sensor_to_spike(75, 4, 4) is True        # periyot
    assert sensor_to_spike(60, 12, 11) is False
    assert sensor_to_spike(60, 12, 12) is True
    assert [sensor_to_spike(60, 16, t) for t in range(18)].count(True) == 4
    assert [sensor_to_spike(60, 24, t) for t in range(26)].count(True) == 5
    assert sensor_burst(4) == 1 and sensor_burst(16) == 2
    assert sensor_burst(24) == 3
    # --- /set ---
    assert to_motor_lines("/set hn 70") == ["SET hn 70"]
    assert to_motor_lines("/SET HS 85") == ["SET hs 85"]
    assert to_motor_lines("/set nem 60") == ["SET hn 60"]  # eski ad
    try:
        to_motor_lines("/set hn 101")
        raise AssertionError("101 kabul edilmemeli")
    except ValueError:
        pass
    try:
        to_motor_lines("/set xx 50")
        raise AssertionError("bilinmeyen sensor kabul edilmemeli")
    except ValueError:
        pass
    # --- /scenario ---
    assert to_motor_lines("/scenario drought")[0] == "SET hs 85"
    assert len(to_motor_lines("/scenario sulama")) == 7
    try:
        to_motor_lines("/scenario volkan")
        raise AssertionError("bilinmeyen senaryo kabul edilmemeli")
    except ValueError:
        pass
    # --- TR dogal dil ---
    assert to_motor_lines("nem 70 yap") == ["SET hn 70"]
    assert to_motor_lines("toprak nemi 90 olsun") == ["SET tn 90"]
    assert to_motor_lines("sıcaklık 75") == ["SET hs 75"]
    assert to_motor_lines("sulama senaryosu baslat") == preset_lines("sulama")
    assert to_motor_lines("kuraklık") == preset_lines("drought")
    assert to_motor_lines("sıfırla") == ["RESET"]
    # --- EN dogal dil ---
    assert to_motor_lines("set air humidity to 80") == ["SET hn 80"]
    assert to_motor_lines("soil moisture 90") == ["SET tn 90"]
    assert to_motor_lines("cold scenario") == preset_lines("soguk")
    assert to_motor_lines("reset") == ["RESET"]
    assert to_motor_lines("# yorum") == []
    assert to_motor_lines("   ") == []
    try:
        to_motor_lines("bugun hava guzel")
        raise AssertionError("anlamsiz girdi kabul edilmemeli")
    except ValueError:
        pass
    # --- post haritasi tutarliligi ---
    assert POST_MAP["X1"] == ("hn", 4) and POST_MAP["X2"] == ("hs", 12)
    # --- yon fiilleri (degersiz dogal dil; degerliler eski yolda) ---
    assert to_motor_lines("Hava aniden ısındı") == ["SET hs 85"]
    assert to_motor_lines("hava sogudu") == ["SET hs 20"]
    assert to_motor_lines("toprak kurudu") == ["SET tn 15"]
    assert to_motor_lines("yagmur yagiyor") == ["SET hn 80", "SET tn 90"]
    assert to_motor_lines("nem 70 yap") == ["SET hn 70"]  # degisti mi?
    assert to_motor_lines("kuraklık") == preset_lines("drought")
    # --- interpret zarfi (interpreter ile uctan uca) ---
    r = interpret("/set hn 70")
    assert r["kind"] == "set" and r["motor_lines"] == ["SET hn 70"]
    assert r["brief"] == "hn=70" and len(r["speech"]) == 2
    r = interpret("Hava aniden ısındı")
    assert r["kind"] == "natural" and r["motor_lines"] == ["SET hs 85"]
    r = interpret("bugün hava güzel")
    assert r["kind"] == "unknown" and r["motor_lines"] == []
    # --- kapi komutlari ---
    assert to_motor_lines("/sensor-off hn") == ["SENSOR_OFF hn"]
    assert to_motor_lines("/sensor_on ec") == ["SENSOR_ON ec"]
    assert to_motor_lines("hn kapa") == ["SENSOR_OFF hn"]
    assert to_motor_lines("disable soil moisture") == ["SENSOR_OFF tn"]
    assert to_motor_lines("hn aç") == ["SENSOR_ON hn"]
    try:
        to_motor_lines("/sensor-off xx")
        raise AssertionError("bilinmeyen sensor kabul edilmemeli")
    except ValueError:
        pass
    print("scenario_engine: tum assert testleri gecti")
