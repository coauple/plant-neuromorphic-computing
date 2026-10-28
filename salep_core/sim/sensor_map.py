"""Fiziksel değişkenler → 7 NPU sensörü (0-100) eşlemesi.

Gözlem gürültüsü (adım 8, §9.36): SensorMapper(noise_std>0) çıkışa
tohumlu Gauss gürültüsü ekler — YALNIZ gözlem katmanında, durum
değişkenlerine (ts EMA, hn/ph/npk halleri) geri beslenmez. Öntanımlı
0.0 = birebir aynı eşleme (kapılar etkilenmez). Yalnız stdlib.

Kalibrasyon tablosu:
| NPU | Kaynak        | Formül                                         | Eşik 50 ≈ |
|-----|---------------|------------------------------------------------|-----------|
| hs  | physics temp  | clamp((temp+5)/45*100), GÜN BOYU SABİT (A1)    | 17.5°C    |
| ts  | temp EMA      | ~7 günlük gecikme (toprak ısı ataleti)         | 17.5°C    |
| hn  | *türetilmiş*  | yağış sıçraması + sıcaklığa bağlı kuruma       | —         |
| tn  | soil_moisture  | doğrudan (0-100)                               | %50       |
| ph  | *türetilmiş*  | gübre→kayma, baseline'a tamponlanma            | —         |
| npk | *türetilmiş*  | fertilizer_dose + büyümeyle tükenme            | —         |
| ec  | soil_ec       | 0-5 mS/cm → 0-100, yanık eşiği 3.4 = 68 (ON)  | 2.5 mS/cm |
"""
import random  # stdlib (G11-safe)


def clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def map_hs(temp: float) -> int:
    """Hava sıcaklığı → hs (0-100). -5°C=0, 40°C=100."""
    return int(clamp((temp + 5.0) / 45.0 * 100.0))


def map_ts(temp: float, prev_ts: float, alpha: float = 0.14) -> float:
    """Toprak sıcaklığı → ts. ~7 günlük EMA (alpha≈1/7)."""
    return prev_ts + alpha * (map_hs(temp) - prev_ts)


# TODO: DOĞRULANMADI — hn modeli henüz plant_sim.py'de yok
def map_hn(rain_mm: float, temp: float, prev_hn: float) -> float:
    """Hava nemi → hn. Yağış sıçraması + sıcaklığa bağlı kuruma.

    Basit model: yağmurda ani nem artışı, sıcakta hızlı kuruma.
    Gerçek hava nemi plant_sim.py'de modellenmemiş — bu bir türetmedir.
    """
    spike = min(rain_mm * 8.0, 100.0)  # yağmurda ani nem artışı
    target = max(spike, 30.0)           # minimum ambient
    dry_rate = 0.05 + max(0, temp - 20) * 0.01  # sıcakta hızlı kuruma
    return clamp(prev_hn + (target - prev_hn) * dry_rate)


# TODO: DOĞRULANMADI — ph modeli henüz plant_sim.py'de yok
def map_ph(fert_dose: float, prev_ph: float, baseline: float = 45.0) -> float:
    """Toprak pH → ph. Gübreyle kayma, baseline'a tamponlanma.

    Basit tampon modeli: gübre asitlik kaydırır, toprak tamponu
    baseline'a döndürür. Gerçek pH dinamiği plant_sim.py'de yok.
    """
    acid_shift = fert_dose * 0.3  # gübre asitliği artırır
    buffered = prev_ph + (baseline - prev_ph) * 0.05 - acid_shift
    return clamp(buffered)


# TODO: DOĞRULANMADI — npk modeli henüz plant_sim.py'de yok
def map_npk(fert_dose: float, growth_demand: float, prev_npk: float) -> float:
    """Besin havuzu → npk. Gübreyle artış, büyümeyle tükenme.

    Basit kütle-dengesi modeli: gübre besin ekler, büyüme tüketir.
    Gerçek NPK dinamiği plant_sim.py'de modellenmemiş.
    """
    supply = fert_dose * 2.0
    depletion = growth_demand * 0.1
    return clamp(prev_npk + supply - depletion)


def map_tn(soil_moisture: float) -> int:
    """Toprak nemi → tn. Doğrudan (0-100)."""
    return int(clamp(soil_moisture))


def map_ec(soil_ec: float) -> int:
    """EC → ec. 0-5 mS/cm → 0-100. Yanık eşiği 3.4 mS/cm = 68."""
    return int(clamp(soil_ec / 5.0 * 100.0))


class SensorMapper:
    """Durum tutarak 7 sensör değerini üretir.

    Her update() çağrısında fizik snapshot'ından 7 NPU sensör
    değeri hesaplanır. Durum tutan kanallar (ts EMA, hn, ph, npk)
    bir önceki adımdan taşınır. noise_std>0 ise çıkışa tohumlu
    Gauss gürültüsü eklenir (gözlem katmanı; hallere işlemez).
    """

    def __init__(self, noise_std: float = 0.0, noise_seed=None):
        self.ts_ema = 50.0      # başlangıç toprak sıcaklığı
        self.hn_state = 50.0    # başlangıç nem
        self.ph_state = 45.0    # başlangıç pH
        self.npk_state = 40.0   # başlangıç NPK
        self.noise_std = float(noise_std)
        self._rng = random.Random(noise_seed)

    def _noisy(self, v: float) -> float:
        """Gözlem gürültüsü (kapalıysa birebir geçiş, RNG çekilmez)."""
        if self.noise_std <= 0:
            return v
        return clamp(v + self._rng.gauss(0.0, self.noise_std))

    def update(self, snapshot: dict, fert_dose: float = 0.0) -> dict[str, int]:
        """Fizik snapshot'ından 7 NPU sensör değeri üretir.

        snapshot["temp"] = physics_temp OLMALI (gün boyu sabit, A1);
        display_temp buraya girmez — titreyen sensör üretir.
        """
        temp = snapshot.get("temp", 20.0)
        rain = snapshot.get("rain_mm", 0.0)
        sm = snapshot.get("soil_moisture", 50.0)
        ec = snapshot.get("soil_ec", 1.0)
        growth = snapshot.get("tuber_mass", 0.0) * 0.01  # büyüme talebi proxy

        hs = int(self._noisy(map_hs(temp)))
        self.ts_ema = map_ts(temp, self.ts_ema)
        ts = int(self._noisy(clamp(self.ts_ema)))
        self.hn_state = map_hn(rain, temp, self.hn_state)
        hn = int(self._noisy(clamp(self.hn_state)))
        tn = int(self._noisy(map_tn(sm)))
        self.ph_state = map_ph(fert_dose, self.ph_state)
        ph = int(self._noisy(clamp(self.ph_state)))
        self.npk_state = map_npk(fert_dose, growth, self.npk_state)
        npk = int(self._noisy(clamp(self.npk_state)))
        ec_val = int(self._noisy(map_ec(ec)))

        return {"hs": hs, "ts": ts, "hn": hn, "tn": tn,
                "ph": ph, "npk": npk, "ec": ec_val}

    def reset(self):
        self.__init__()
