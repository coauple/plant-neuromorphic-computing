"""Thread-safe Frame snapshot — tüm katmanları birleştirir.

Frame = {
    world:   {temp, day_frac, sim_day, day_of_year, photoperiod, rain_mm,
              uv_index},
    plant:   {stage, leaf_health, root_health, tuber_mass, water_balance,
              soil_moisture, soil_ec, stem_height},
    visual:  {stem_h, leaf_scale, wilt, flower_count, root_tint, tuber_scale},
    sensors: {hs, ts, hn, tn, ph, npk, ec},
    npu:     {tick, wire, fire[9], w[9], cc[7]},
}

Not: ground_truth_event bu şemada YOK (anayasa §0, karar K6).
Not: "stres" etiketi yok (karar K7) — fiziksel stres plant.*, NPU substratı npu.*.
"""
import threading
import copy
from dataclasses import dataclass, field


@dataclass
class Frame:
    """Tek bir anlık snapshot — protokol bağımsız.

    Uzak istemci için serve.py (TCP/NDJSON) ile aynen yayınlanabilir.
    """
    # ---- Dünya ----
    sim_day: int = 0
    day_frac: float = 0.0
    day_of_year: int = 0
    temp: float = 20.0
    photoperiod: float = 12.0
    rain_mm: float = 0.0

    # ---- Bitki (fiziksel) ----
    stage: str = "DORMANT"
    leaf_health: float = 100.0
    root_health: float = 100.0
    tuber_mass: float = 0.0
    water_balance: float = 0.0
    soil_moisture: float = 50.0
    soil_ec: float = 1.0
    o2_deficit_ticks: int = 0
    stem_height: float = 0.0       # boy, morfolojik model birimi (§9.27)
    uv_index: float | None = None  # gözlenen UV, yoksa None (§9.27)

    # ---- Görsel türevler (3D bağlama için) ----
    stage_age: int = 0          # GİRDİ: plant.stage_age (sürekli lerp için)
    display_temp: float = 20.0  # GİRDİ: snapshot display_temp (HUD/güneş)
    # ---- v2 şeması girdileri (snapshot'tan doldurulur) ----
    temp_soil: float = 15.0
    sun_alt_deg: float = 0.0
    sun_az_deg: float = 0.0
    sky: str = "day"
    paused: bool = False
    speed: float = 1.0
    events: list = field(default_factory=list)
    stem_h: float = 0.0         # büyüme ↔ scale.y (evre içi sürekli)
    leaf_scale: float = 1.0     # leaf_health/fenoloji
    wilt: float = 0.0           # clamp(-water_balance - 0.15) → 0-1
    flower_count: int = 0       # FLOWERING'de 0 → 12 kademeli
    root_tint: float = 1.0      # root_health/100 (1=beyaz, 0=siyah)
    tuber_scale: float = 0.1    # tuber_mass^(1/3)
    soil_wet: float = 0.0       # nem + taze sulama + kuyruk ön-izlemesi
    # ---- v1 türevleri (compute_visuals doldurur) ----
    leaf_turgor: float = 1.0    # 1 - wilt (tanımlı)
    yellowing: float = 0.0      # SENESCENCE sararması (görsel ölçek)
    flower_open: float = 0.0    # salkım açıklığı 0-1 (tanımlı)
    root_necrotic: float = 0.0  # 1 - root_tint (tanımlı)
    salt_crust: float = 0.0     # EC tuz kabuğu (görsel ölçek)

    # ---- Eylem geri bildirimi (A3: kuyruk + uygulanan, QML'e ulaşır) ----
    applied_irrigation_mm: float = 0.0
    applied_fert_mass: float = 0.0
    pending_irrigation_mm: float = 0.0
    pending_fert_mass: float = 0.0

    # ---- Sensörler (7 kanal, 0-100) ----
    hs: int = 50
    ts: int = 50
    hn: int = 50
    tn: int = 50
    ph: int = 45
    npk: int = 40
    ec: int = 40

    # ---- NPU telemetrisi ----
    npu_tick: int = 0
    npu_wire: float = 0.0
    npu_fire: str = "000000000"       # 9 bit string
    npu_w: list = field(default_factory=lambda: [0.2] * 9)
    npu_cc: list = field(default_factory=lambda: [0] * 7)


# Görsel enterpolasyon sabitleri — SUNUM içindir, fizik iddiası değil (§0).
# Evre sınırlarında süreklilik korunur (SPROUTING sonu = VEGETATIVE başı vb.).
_SPROUT_RAMP = 20.0   # sürgün boyu günleri (görsel)
_VEG_RAMP = 30.0      # rozet olgunlaşma (görsel)
_FLOWER_RAMP = 35.0   # salkım açılımı (görsel)
_SENES_RAMP = 30.0    # gerileme (görsel)
_MAX_FLOWERS = 12


def _ramp(age: float, span: float) -> float:
    return max(0.0, min(1.0, age / span))


def compute_visuals(frame: Frame) -> Frame:
    """Fiziksel değerlerden görsel türevleri hesapla (sürekli, kademesiz)."""
    # Solma: water_balance < -0.15'te başlar
    frame.wilt = max(0.0, min(1.0, (-frame.water_balance - 0.15) * 2.0))
    # Yaprak ölçeği
    frame.leaf_scale = max(0.05, frame.leaf_health / 100.0)
    # Kök rengi (1=sağlıklı beyaz, 0=ölü siyah)
    frame.root_tint = max(0.0, frame.root_health / 100.0)
    # Yumru ölçeği (kütle → hacim → yarıçap)
    frame.tuber_scale = max(0.05, frame.tuber_mass ** (1 / 3) * 0.3)
    # Sap yüksekliği — evre içi sürekli uzama, sınırlarda sürekli
    age = frame.stage_age
    if frame.stage == "SPROUTING":
        frame.stem_h = 0.6 * _ramp(age, _SPROUT_RAMP)
    elif frame.stage == "VEGETATIVE":
        frame.stem_h = 0.6 + 0.2 * _ramp(age, _VEG_RAMP)
    elif frame.stage == "FLOWERING":
        frame.stem_h = 0.8 + 0.2 * _ramp(age, _FLOWER_RAMP)
    elif frame.stage == "SENESCENCE":
        frame.stem_h = 1.0 - 0.2 * _ramp(age, _SENES_RAMP)
    elif frame.stage == "DEAD":
        frame.stem_h = 0.3
    else:  # DORMANT
        frame.stem_h = 0.0
    # Çiçek — kademeli açılım 0 → 12
    if frame.stage == "FLOWERING":
        frame.flower_count = round(_MAX_FLOWERS * _ramp(age, _FLOWER_RAMP))
    else:
        frame.flower_count = 0
    # Toprak ıslaklığı: nem tabanı + taze sulama kabarması + kuyruk ön-izlemesi
    wet = (frame.soil_moisture / 100.0 * 0.7
           + min(frame.applied_irrigation_mm, 40.0) / 40.0 * 0.3
           + (0.15 if frame.pending_irrigation_mm > 0 else 0.0))
    frame.soil_wet = max(0.0, min(1.0, wet))
    # v1 türevleri (tanımlı dönüşümler; yellowing/salt görsel ölçek — §0)
    frame.leaf_turgor = 1.0 - frame.wilt
    if frame.stage == "SENESCENCE":
        frame.yellowing = max(0.0, (100.0 - frame.leaf_health) / 100.0)
    else:
        frame.yellowing = 0.0
    frame.flower_open = _ramp(age, _FLOWER_RAMP) \
        if frame.stage == "FLOWERING" else 0.0
    frame.root_necrotic = 1.0 - frame.root_tint
    ec = frame.soil_ec
    frame.salt_crust = 1.0 if ec > 3.4 else max(0.0, (ec - 1.5)
                                                / (3.4 - 1.5)) * 0.5
    return frame


# world_state.v2 JSON sözleşmesi sürümü (v1→v2: world.uv_index +
# plant.stem_height, §9.27; dondurma prosedürü üçlüsü birlikte değişti)
SCHEMA_VERSION = 2


def frame_to_dict(frame: "Frame", wall_t: float = 0.0) -> dict:
    """Frame → world_state.v2 sözlüğü (soket/JSON yayını için).

    ground_truth YOK (§0). lobes anahtarı yayıncı (serve.py) tarafından
    eklenir; burası yalnız dünya+bitki+görsel+sensör+eylem taşır.
    """
    return {
        "v": SCHEMA_VERSION,
        "wall_t": wall_t,
        "sim": {
            "day": frame.sim_day,
            "day_frac": frame.day_frac,
            "doy": frame.day_of_year,
            "paused": frame.paused,
            "speed": frame.speed,
        },
        "world": {
            "temp_air": frame.temp,
            "temp_air_display": frame.display_temp,
            "temp_soil": frame.temp_soil,
            "photoperiod_h": frame.photoperiod,
            "sun_alt_deg": frame.sun_alt_deg,
            "sun_az_deg": frame.sun_az_deg,
            "rain_mm": frame.rain_mm,
            "sky": frame.sky,
            "uv_index": frame.uv_index,
        },
        "plant": {
            "stage": frame.stage,
            "stage_age": frame.stage_age,
            "leaf_health": frame.leaf_health,
            "root_health": frame.root_health,
            "tuber_mass": frame.tuber_mass,
            "water_balance": frame.water_balance,
            "o2_deficit": frame.o2_deficit_ticks,
            "soil_moisture": frame.soil_moisture,
            "soil_ec": frame.soil_ec,
            "stem_height": frame.stem_height,
        },
        "visual": {
            "stem_h": frame.stem_h,
            "leaf_scale": frame.leaf_scale,
            "leaf_turgor": frame.leaf_turgor,
            "wilt": frame.wilt,
            "yellowing": frame.yellowing,
            "flower_count": frame.flower_count,
            "flower_open": frame.flower_open,
            "root_tint": frame.root_tint,
            "root_necrotic": frame.root_necrotic,
            "tuber_scale": frame.tuber_scale,
            "soil_wet": frame.soil_wet,
            "salt_crust": frame.salt_crust,
        },
        "sensors": {
            "hs": frame.hs, "ts": frame.ts, "hn": frame.hn,
            "tn": frame.tn, "ph": frame.ph, "npk": frame.npk,
            "ec": frame.ec,
        },
        "actions": {
            "pending_irrigation_mm": frame.pending_irrigation_mm,
            "pending_fert_mass": frame.pending_fert_mass,
            "applied_irrigation_mm": frame.applied_irrigation_mm,
            "applied_fert_mass": frame.applied_fert_mass,
        },
        "events": list(frame.events),
    }


class FrameBuffer:
    """Çift tamponlu thread-safe frame deposu.

    Fizik + NPU thread'leri write(), GUI thread read() çağırır.
    QML'e sadece GUI thread'inden dokunulur (Qt kuralı, K2).
    """

    def __init__(self):
        self._frame = Frame()
        self._lock = threading.Lock()

    def write(self, frame: Frame):
        with self._lock:
            self._frame = frame

    def read(self) -> Frame:
        with self._lock:
            return copy.copy(self._frame)
