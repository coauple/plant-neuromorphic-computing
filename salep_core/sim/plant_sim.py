"""
Salep Sibernetiği - Dünya Fiziği + Bitki Fizyolojisi Simülatörü
================================================================

Mimari:
  A) WorldDriver   -> bitkiden bağımsız iklim (sıcaklık, ışık/fotoperiyot, yağış)
  B) Soil          -> toprak nemi, EC (tuzluluk/besin), O2 (drenaj/anaerobik risk)
  C) Plant         -> fenoloji durum makinesi + su/tuz fizyolojisi (turgor, kök sağlığı)
  D) Population    -> N bitki paralel, jitter'lı parametreler (genetik/mikro-ortam varyasyonu)

Önemli tasarım kararı: Simülatör "stres", "hastalık" gibi kavramları hiçbir yerde
yazmaz/etiketlemez. Sadece ölçülebilir fiziksel değişkenler (nem, EC, O2, sağlık,
kütle) üretir. NPU/SNN'in göreceği veri budur. "root_rot_event" / "salt_burn_event"
gibi etiketler sadece SENİN doğrulaman için ayrı bir "ground truth" kolonunda tutulur,
modelin girişine hiç verilmez.
"""

import csv
import datetime
import math
import os
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from enum import IntEnum

# Çıktı dizini — hardcoded /home/claude yerine proje-göreli
SIM_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(SIM_DIR, "out")


# ----------------------------------------------------------------------------
# A) DÜNYA FİZİĞİ (bitkiden tamamen bağımsız)
# ----------------------------------------------------------------------------

class WorldDriver:
    """Akdeniz/Ege tipi iklim: sıcak-kurak yaz, ılıman-yağışlı kış."""

    def __init__(self, seed: int, yearly_mean_temp=17.0, season_amp=11.0,
                 daily_amp=4.0, noise_std=1.2, observed=None):
        self.rng = np.random.default_rng(seed)
        self.yearly_mean_temp = yearly_mean_temp
        self.season_amp = season_amp
        self.daily_amp = daily_amp
        self.noise_std = noise_std
        # observed: ObservedWeather veya None (§9.26). Varsa o günün gerçek
        # değeri döner (RNG çekilmez — determinizm korunur); yoksa sentetik.
        self.observed = observed
        # Ortam nemi (VWC değil, hava kesri 0..1). Başlangıç 0.8 =
        # VPD süreklilik çapası (§9.46). step_rh ile evrilir.
        self.rh_frac = 0.8

    def temperature(self, day_frac: float) -> float:
        # day_frac: gün içindeki gerçek zaman (t/1 gün cinsinden float, örn. 143.5)
        if self.observed is not None:
            hit = self.observed.get(int(day_frac), int(day_frac) % 365)
            if hit is not None:
                return float(hit[0])
        annual = self.season_amp * np.sin(2 * np.pi * (day_frac - 100) / 365.0)
        diurnal = self.daily_amp * np.sin(2 * np.pi * day_frac)
        noise = self.rng.normal(0, self.noise_std)
        return self.yearly_mean_temp + annual + diurnal + noise

    def photoperiod_hours(self, day_of_year: int) -> float:
        # basit gün uzunluğu modeli (Ege enlemi ~38N)
        return 12 + 4.0 * np.sin(2 * np.pi * (day_of_year - 80) / 365.0)

    # TODO: DOĞRULANMADI — ortam nem kovası sayıları (§9.47).
    # Yağmur hedefi (+0.20 tam ıslanmada), sıcaklık cezası (-0.012/°C),
    # gevşeme (α=0.35/gün) ve buhar katsayısı (0.010) başlangıç
    # varsayımıdır; sera/tarla nem serisiyle kalibre edilmelidir.
    _RH_ALPHA = 0.35
    _RH_VAPOR = 0.010

    def step_rh(self, temp_c: float, rain_mm: float,
                vapor_pts: float = 0.0) -> float:
        """Ortam nem kovası (§9.47): yağmur doygunluğa çeker, sıcak
        kurutur, bitki buharı (transpirasyon, VWC puanı) nemlendirir.

        RNG ÇEKİLMEZ — legacy sıcaklık/yağış akışı birebir korunur
        (G2-güvenli). Bitki adımından SONRA çağrılır (bir gün gecikmeli
        geri-besleme — ayrık-zaman anlami açıktır).
        """
        target = min(1.0, max(0.05,
                              0.80 + 0.20 * min(1.0, rain_mm / 10.0)
                              - 0.012 * max(0.0, temp_c - 20.0)))
        self.rh_frac = min(1.0, max(0.01,
            self.rh_frac + self._RH_ALPHA * (target - self.rh_frac)
            + self._RH_VAPOR * max(0.0, vapor_pts)
            * (1.0 - self.rh_frac)))
        return self.rh_frac

    def day_curve(self, abs_day, day_of_year):
        """O günün (tmin, tmax) çapası veya None (§9.30, gösterim yedeği)."""
        if self.observed is not None:
            return self.observed.get_day_curve(int(abs_day),
                                               int(day_of_year) % 365)
        return None

    def uv_index(self, abs_day, day_of_year):
        """Gözlenen UV endeksi veya None (dosyada UV yoksa)."""
        if self.observed is not None:
            hit = self.observed.get_uv(int(abs_day), int(day_of_year) % 365)
            if hit is not None:
                return float(hit[0])
        return None

    def uv_deficit(self, abs_day, day_of_year) -> float:
        """UV açığı 0..1: (clear - obs) / clear (§9.27).

        Bulutluluk ölçüsüdür: açık günde 0, kapalıda 1'e yaklaşır.
        Gözlem yoksa veya clear <= 0 ise 0 (etkisiz, deterministik).
        """
        if self.observed is not None:
            hit = self.observed.get_uv(int(abs_day), int(day_of_year) % 365)
            if hit is not None:
                uv, clear = hit
                if clear > 0:
                    return float(min(1.0, max(0.0, (clear - uv) / clear)))
        return 0.0

    def rain_event_mm(self, day_of_year: int, abs_day=None) -> float:
        # Gözlenen gün varsa gerçek yağış (RNG çekilmez); yoksa sentetik.
        if self.observed is not None and abs_day is not None:
            hit = self.observed.get(int(abs_day), int(day_of_year) % 365)
            if hit is not None:
                return float(hit[1])
        # sonbahar/kış yağışlı, yaz neredeyse sıfır (tipik Akdeniz iklimi)
        season_prob = 0.35 + 0.30 * np.cos(2 * np.pi * (day_of_year - 15) / 365.0)
        season_prob = np.clip(season_prob, 0.02, 0.65)
        if self.rng.random() < season_prob:
            return float(self.rng.gamma(shape=2.0, scale=6.0))  # sağa çarpık: çoğu hafif, bazen sağanak
        return 0.0


# ----------------------------------------------------------------------------
# A2) GÖZLENEN HAVA — gerçek istasyon dosyası (Open-Meteo günlük CSV, §9.26)
# ----------------------------------------------------------------------------

_OBS_MDAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _doy_to_md(doy: int):
    """365-gün doy → (ay, gün). Artık-gün Feb 29 havuza girmez."""
    m = 0
    d = int(doy)
    while m < 11 and d >= _OBS_MDAYS[m]:
        d -= _OBS_MDAYS[m]
        m += 1
    return (m + 1, d + 1)


def reconstruct_hour_temp(tmin: float, tmax: float, hour: float) -> float:
    """Gün-içi sıcaklık rekonstrüksiyonu (§9.30, YALNIZ gösterim).

    O günün gerçek min/maks'ına oturan tek-kosinüs: 15:00'te maks,
    03:00'te min (gerçek min ~05:00'e göre ±2s faz farkı — belgeli
    yaklaşıklık). Fizik bunu KULLANMAZ (günlük ortalama adım sürer).
    """
    mid = (tmax + tmin) / 2.0
    amp = (tmax - tmin) / 2.0
    return mid + amp * math.cos(2 * math.pi * (hour - 15.0) / 24.0)


class ObservedWeather:
    """Gerçek gözlem: tam-tarih öncelikli, aynı-gün havuzu yedekli.

    get(abs_day, doy): önce year0 takvimindeki tam tarihi dener (örn.
    2026-03-14 → dosyadaki 2026-03-14 satırı); yoksa dosyanın başka
    yıllarındaki AYNI gün-ayın ortalamasını döner (örn. 2025-03-14);
    o da yoksa None döner (çağıran sentetik modele düşer).
    Öncelik sırası: tam-tarih > gün-ay havuzu > sentetik.
    """

    def __init__(self, exact: dict, pool: dict, year0: int,
                 uv_exact: dict | None = None, uv_pool: dict | None = None):
        self.exact = exact  # {datetime.date: (temp_c, rain_mm)}
        self.pool = pool    # {(ay, gun): [(temp_c, rain_mm), ...]}
        self.year0 = year0  # sim günü 0 = 1 Oca year0
        self.n_rows = len(exact)
        self.uv_exact = uv_exact or {}  # {date: (uv, clear)}
        self.uv_pool = uv_pool or {}    # {(ay, gun): [(uv, clear), ...]}
        self.n_uv = len(self.uv_exact)

    def get(self, abs_day, doy):
        try:
            date = (datetime.date(self.year0, 1, 1)
                    + datetime.timedelta(days=int(abs_day)))
        except (OverflowError, ValueError):
            return None
        hit = self.exact.get(date)
        if hit is not None:
            return (hit[0], hit[1])
        cands = self.pool.get(_doy_to_md(int(doy) % 365))
        if cands:
            n = len(cands)
            return (sum(c[0] for c in cands) / n,
                    sum(c[1] for c in cands) / n)
        return None

    def get_day_curve(self, abs_day, doy):
        """(tmin, tmax) veya None — gün-içi eğri çapası (§9.30).

        Zincir get() ile aynıdır (tam-tarih > gün-ay havuzu); min/maks
        sütunu yoksa veya o günde ikisi de boşsa None döner.
        """
        try:
            date = (datetime.date(self.year0, 1, 1)
                    + datetime.timedelta(days=int(abs_day)))
        except (OverflowError, ValueError):
            return None
        hit = self.exact.get(date)
        if hit is not None and hit[2] is not None and hit[3] is not None:
            return (hit[2], hit[3])
        cands = [c for c in
                 self.pool.get(_doy_to_md(int(doy) % 365), [])
                 if c[2] is not None and c[3] is not None]
        if cands:
            n = len(cands)
            return (sum(c[2] for c in cands) / n,
                    sum(c[3] for c in cands) / n)
        return None

    def get_uv(self, abs_day, doy):
        """(uv, clear) veya None. Zincir: tam-tarih > gün-ay havuzu."""
        try:
            date = (datetime.date(self.year0, 1, 1)
                    + datetime.timedelta(days=int(abs_day)))
        except (OverflowError, ValueError):
            return None
        hit = self.uv_exact.get(date)
        if hit is not None:
            return hit
        cands = self.uv_pool.get(_doy_to_md(int(doy) % 365))
        if cands:
            n = len(cands)
            return (sum(u for u, _ in cands) / n,
                    sum(c for _, c in cands) / n)
        return None


def load_observed_weather(path: str, year0: int | None = None) -> ObservedWeather:
    """Open-Meteo günlük CSV'sini okur, ObservedWeather döner.

    Beklenen sütunlar: `time` (YYYY-MM-DD), `temperature_2m_mean (°C)`,
    yağış için `rain_sum (mm)` (yoksa `precipitation_sum (mm)`).
    Başlık öncesi meta satırlar (Open-Meteo coğrafi bloğu) atlanır.
    year0 verilmezse dosyanın SON satırının yılı alınır (bu yıl).
    Sim günü 0 = 1 Oca year0; dosya-dışı günler sentetik modele düşer.

    HATA (ValueError, yüksek sesli): başlık/sütun yok, bozuk tarih,
    sayı değil veya NaN, sıcaklık [-60,60] dışında, yağış negatif,
    tekrarlı tarih, boş dosya.
    """
    with open(path, encoding="utf-8-sig") as fh:
        rows = [r for r in csv.reader(fh)
                if r and any(c.strip() for c in r)]
    hi = next((i for i, r in enumerate(rows)
               if r[0].strip() == "time"), None)
    if hi is None:
        raise ValueError(f"gözlenen-hava: 'time' başlığı yok ({path})")
    header = [c.strip() for c in rows[hi]]

    def col(*names):
        # Önce birebir, sonra önek (Open-Meteo birim eki değişkendir:
        # "(°C)", "()", "(undefined)"...).
        for n in names:
            if n in header:
                return header.index(n)
        for n in names:
            for h in header:
                if h.startswith(n):
                    return header.index(h)
        raise ValueError(f"gözlenen-hava: sütun yok {names} ({path})")

    def opt(*names):
        # İsteğe-bağlı sütun (gün-içi eğri için min/maks, §9.30): yoksa None,
        # ses yok — eğri o gün kapalı kalır, fizik/gösterim yedeğe düşer.
        for n in names:
            if n in header:
                return header.index(n)
        for n in names:
            for h in header:
                if h.startswith(n):
                    return header.index(h)
        return None

    i_time = col("time")
    i_temp = col("temperature_2m_mean (°C)", "temperature_2m_mean")
    i_rain = col("rain_sum (mm)", "rain_sum",
                 "precipitation_sum (mm)", "precipitation_sum")
    i_tmin = opt("temperature_2m_min (°C)", "temperature_2m_min")
    i_tmax = opt("temperature_2m_max (°C)", "temperature_2m_max")

    exact: dict = {}
    pool: dict = {}
    for ln, r in enumerate(rows[hi + 1:], start=hi + 2):
        try:
            date = datetime.date.fromisoformat(r[i_time].strip())
        except (ValueError, IndexError):
            raise ValueError(
                f"gözlenen-hava: satır {ln} tarih bozuk ({path})")
        try:
            temp = float(r[i_temp])
            rain = float(r[i_rain])
            tmin = float(r[i_tmin]) if i_tmin is not None else None
            tmax = float(r[i_tmax]) if i_tmax is not None else None
        except (ValueError, IndexError):
            raise ValueError(
                f"gözlenen-hava: satır {ln} sayı değil ({path})")
        if math.isnan(temp) or math.isnan(rain):
            raise ValueError(
                f"gözlenen-hava: satır {ln} NaN ({path})")
        if not (-60.0 <= temp <= 60.0):
            raise ValueError(
                f"gözlenen-hava: satır {ln} sıcaklık aralık-dışı ({path})")
        if rain < 0.0:
            raise ValueError(
                f"gözlenen-hava: satır {ln} yağış negatif ({path})")
        if ((tmin is not None and (math.isnan(tmin)
                                   or not (-60.0 <= tmin <= 60.0)))
                or (tmax is not None and (math.isnan(tmax)
                                          or not (-60.0 <= tmax <= 60.0)))
                or (tmin is not None and tmax is not None
                    and tmin > tmax)):
            raise ValueError(
                f"gözlenen-hava: satır {ln} min/maks bozuk ({path})")
        if date in exact:
            raise ValueError(
                f"gözlenen-hava: satır {ln} tekrarlı tarih ({path})")
        exact[date] = (temp, rain, tmin, tmax)
        if not (date.month == 2 and date.day == 29):
            pool.setdefault((date.month, date.day), []).append(
                (temp, rain, tmin, tmax))
    if not exact:
        raise ValueError(f"gözlenen-hava: veri satırı yok ({path})")
    if year0 is None:
        year0 = max(exact).year
    return ObservedWeather(exact, pool, int(year0))


def attach_observed_uv(obs: ObservedWeather | None, path: str) -> ObservedWeather:
    """UV dosyasını (Open-Meteo günlük: time + uv_index_max* +
    uv_index_clear_sky_max*) ObservedWeather'a işler.

    obs None ise sıcaklık/yağışsız taze nesne kurar (year0 = UV dosyasının
    son yılı; sıcaklık/yağış sentetikte kalır, yalnız UV gerçektir).
    Sertlik sıcaklıkla aynıdır (NaN, aralık-dışı, negatif, tekrar →
    ValueError). Geçerli aralık: 0 <= uv,clear <= 25.
    """
    with open(path, encoding="utf-8-sig") as fh:
        rows = [r for r in csv.reader(fh)
                if r and any(c.strip() for c in r)]
    hi = next((i for i, r in enumerate(rows)
               if r[0].strip() == "time"), None)
    if hi is None:
        raise ValueError(f"gözlenen-uv: 'time' başlığı yok ({path})")
    header = [c.strip() for c in rows[hi]]

    def col(*names):
        for n in names:
            if n in header:
                return header.index(n)
        for n in names:
            for h in header:
                if h.startswith(n):
                    return header.index(h)
        raise ValueError(f"gözlenen-uv: sütun yok {names} ({path})")

    i_time = col("time")
    i_uv = col("uv_index_max")
    i_clear = col("uv_index_clear_sky_max")

    uv_exact: dict = dict(obs.uv_exact) if obs is not None else {}
    uv_pool: dict = ({k: list(v) for k, v in obs.uv_pool.items()}
                     if obs is not None else {})
    for ln, r in enumerate(rows[hi + 1:], start=hi + 2):
        try:
            date = datetime.date.fromisoformat(r[i_time].strip())
        except (ValueError, IndexError):
            raise ValueError(
                f"gözlenen-uv: satır {ln} tarih bozuk ({path})")
        try:
            uv = float(r[i_uv])
            clear = float(r[i_clear])
        except (ValueError, IndexError):
            raise ValueError(
                f"gözlenen-uv: satır {ln} sayı değil ({path})")
        if math.isnan(uv) or math.isnan(clear):
            raise ValueError(
                f"gözlenen-uv: satır {ln} NaN ({path})")
        if not (0.0 <= uv <= 25.0) or not (0.0 <= clear <= 25.0):
            raise ValueError(
                f"gözlenen-uv: satır {ln} aralık-dışı ({path})")
        if date in uv_exact:
            raise ValueError(
                f"gözlenen-uv: satır {ln} tekrarlı tarih ({path})")
        uv_exact[date] = (uv, clear)
        if not (date.month == 2 and date.day == 29):
            uv_pool.setdefault((date.month, date.day), []).append((uv, clear))
    if not uv_exact:
        raise ValueError(f"gözlenen-uv: veri satırı yok ({path})")
    if obs is None:
        return ObservedWeather({}, {}, max(uv_exact).year,
                               uv_exact=uv_exact, uv_pool=uv_pool)
    obs.uv_exact = uv_exact
    obs.uv_pool = uv_pool
    obs.n_uv = len(uv_exact)
    return obs


# ----------------------------------------------------------------------------
# A3) ATMOSFERİK NEM — VPD (ders-kitabı fiziği, §9.46)
# ----------------------------------------------------------------------------

def svp_kpa(temp_c: float) -> float:
    """Doygun buhar basıncı (Tetens 1980 — ders-kitabı formülü,
    ampirik model iddiası değil)."""
    return 0.6108 * math.exp(17.27 * temp_c / (temp_c + 237.3))


def vpd_kpa(temp_c: float, rh_frac: float) -> float:
    """Buhar basıncı açığı: kurutucu gücün ölçüsü (kPa)."""
    rh = min(1.0, max(0.0, rh_frac))
    return svp_kpa(temp_c) * (1.0 - rh)


# Normalizasyon noktası: v1, 20°C/%80 RH'te legacy davranışa
# birebir kilitlenir (çarpan tam 1.0) — süreklilik çapası, yeni sayı yok.
_VPD_REF = vpd_kpa(20.0, 0.8)


# ----------------------------------------------------------------------------
# B) FENOLOJİ DURUMLARI
# ----------------------------------------------------------------------------

class Stage(IntEnum):
    DORMANT = 0
    SPROUTING = 1
    VEGETATIVE = 2
    FLOWERING = 3
    SENESCENCE = 4
    DEAD = 5


# ----------------------------------------------------------------------------
# C) BİTKİYE ÖZEL (jitter'lı, "genetik/mikro-ortam" parametreleri)
# ----------------------------------------------------------------------------

@dataclass
class PlantParams:
    # --- toprak/drenaj (mikro-ortam, saksı/parsel farkı) ---
    field_capacity: float = 55.0          # % - toprağın tutabildiği max nem
    drainage_coef: float = 0.18           # field_capacity üstü nemin ne hızla boşaldığı
    et_coef: float = 0.9                  # evapotranspirasyon katsayısı

    # --- EC / tuzluluk fizyolojisi ---
    ec_baseline: float = 0.9              # mS/cm, doğal toprak EC'si
    ec_burn_threshold: float = 3.4        # bu EC üstü kök için kimyasal/ozmotik yanık riski
    ec_burn_rate: float = 3.0             # eşik üstünde sağlık kaybı hızı

    # --- oksijen / kök çürüklüğü ---
    waterlog_threshold: float = 82.0      # bu nem üstü = anaerobik risk başlar
    waterlog_tolerance_ticks: int = 4     # kaç gün üst üste tolere edilir
    rot_rate: float = 2.2

    # --- su dengesi / turgor ---
    root_water_potential: float = -0.55   # bitkinin taban çekim gücü (negatif = emme)
    wilt_rate: float = 3.0                # su açığında yaprak sağlığı kaybı hızı
    recovery_rate: float = 1.5            # su dengesi pozitifken iyileşme hızı

    # --- fenoloji eşikleri ---
    sprout_temp_max: float = 22.0         # bu sıcaklığın altında + yağmur -> sürgün
    sprout_rain_min: float = 4.0
    stage_len_sprouting: int = 20
    flower_photoperiod_min: float = 12.6
    stage_len_flowering: int = 35
    senescence_temp_min: float = 27.0

    # --- büyüme ---
    photo_k: float = 0.06
    tuber_alloc_frac: float = 0.55        # üretilen enerjinin yumruya giden payı

    # --- boy (morfolojik, §9.27: model seçimi, verimi etkilemez) ---
    stem_growth_base: float = 0.02       # boy-atma evrelerinde taban boy artışı (model birimi/gün)
    uv_elong_gain: float = 1.0           # UV açığı tam iken hız 2x olur (oran = 1 + gain*deficit)

    # TODO: DOĞRULANMADI (fiziksel-v1 başlangıç varsayımı, §9.36) —
    # kök bölgesi derinliği, yalnız mm→VWC dönüşümünde kullanılır.
    # 0/negatif = legacy yol (mm doğrudan yüzde-puanına eklenir,
    # varsayılan fizik birebir aynı kalır); >0 = fiziksel-v1 yolu.
    # NOT: alan SONDA durur — jittered_params RNG çekiş sırasını
    # bozmamak için (G2 bayt-eşitliği) yeni alanlar hep en sona eklenir.
    root_depth_mm: float = 0.0

    # TODO: DOĞRULANMADI (fiziksel-v1 başlangıç varsayımı, §9.36) —
    # su-tutma kapasiteleri, VWC % ölçeğinde (soil_moisture ile aynı
    # birim, dönüşümsüz karşılaştırma için). 0.0 = tanımsız/inert
    # (legacy yol bu alanları okumaz). Üçü birlikte tanımlanır ve
    # theta_wp < theta_fc < theta_s olmalı (bekçi: soil_overrides).
    # Jitter marjı güvenli: ±%13'te bile sıralama bozulmaz
    # (34×0.87=29.6 > 18×1.13=20.3; 48×0.87=41.8 > 34×1.13=38.4).
    theta_s: float = 0.0                # saturasyon (≈porozite)
    theta_fc: float = 0.0               # tarla kapasitesi
    theta_wp: float = 0.0               # solma noktası

    # TODO: DOĞRULANMADI (fiziksel-v1 bitki alımı, adım 6, §9.36) —
    # transpirasyon ölçeği: pozitif su gradyanının ne kadarı günde
    # topraktan çekilir (VWC puanı / gradyan birimi). 1.0 başlangıç
    # varsayımıdır; tarla ölçümüyle kalibre edilmelidir.
    uptake_coef: float = 1.0

    # TODO: DOĞRULANMADI (don hasarı, §9.49) — donma-derece-günü başına
    # yaprak kaybı (puan/°C/gün). Salep yumrusu kışı geçirir, yaprak
    # dökümü kaba bir vekildir. G2-güvenlik ölçümü: afet CSV'sinde
    # min sıcaklık 2.75°C — temp<0 dalı kapılarda ölü koddur.
    frost_rate: float = 2.0


def jittered_params(base: PlantParams, rng: np.random.Generator, spread=0.13) -> PlantParams:
    """fdm.h'deki leak-jitter mantığı: her bitki ±%13 civarı farklı eşiklerle başlar."""
    out = PlantParams()
    for f in base.__dataclass_fields__:
        val = getattr(base, f)
        if isinstance(val, (int, float)) and f not in ("waterlog_tolerance_ticks", "stage_len_sprouting", "stage_len_flowering"):
            jitter = 1.0 + rng.uniform(-spread, spread)
            setattr(out, f, val * jitter)
        else:
            setattr(out, f, val)
    return out


# Toprak presetleri (§9.35): yalnız field_capacity + drainage_coef oynar
# (ET katsayısı sabit — yeni sayı disiplini). "tınlı" güncel öntanımlılara
# birebir eşittir (varsayılan koşu değişmez, G2 kilidi).
SOIL_PRESETS = {
    "kumlu": {"field_capacity": 30.0, "drainage_coef": 0.40},
    "tınlı": {"field_capacity": 55.0, "drainage_coef": 0.18},
    "killi": {"field_capacity": 70.0, "drainage_coef": 0.08},
    # TODO: DOĞRULANMADI (fiziksel-v1 başlangıç varsayımı, §9.36/§9.37) —
    # opt-in preset: fc/drenaj öntanımlıyla birebir aynı; root_depth_mm>0
    # mm→VWC dönüşümünü açar, thetalar kapasiteyi tanımlar (adım 3).
    # Başka fizik değişmez (drenaj/ET henüz legacy yolu kullanır).
    "fiziksel-v1": {"field_capacity": 55.0, "drainage_coef": 0.18,
                    "root_depth_mm": 200.0,
                    "theta_s": 48.0, "theta_fc": 34.0, "theta_wp": 18.0},
}


def _check_theta_consistency(d: dict) -> dict:
    """Kapasite bekçisi (adım 3, §9.37): theta anahtarlarından biri bile
    tanımlıysa üçü de >0 olmalı ve theta_wp < theta_fc < theta_s
    sağlanmalı; yoksa yüksek sesle ValueError. Anahtar yoksa dokunulmaz
    (legacy preset/dict'ler etkilenmez)."""
    thetas = {k: d[k] for k in ("theta_s", "theta_fc", "theta_wp")
              if k in d}
    if not thetas:
        return d
    if (len(thetas) < 3 or any(v <= 0 for v in thetas.values())
            or not (thetas["theta_wp"] < thetas["theta_fc"]
                    < thetas["theta_s"])):
        raise ValueError(
            f"tutarsız kapasite {thetas} "
            f"(0 < theta_wp < theta_fc < theta_s olmalı)")
    return d


def soil_overrides(soil) -> dict:
    """Preset adı → parametre sözlüğü; dict doğrudan verilebilir.

    Bilinmeyen ad yüksek sesle ValueError verir (sessiz varsayılan yok —
    binlerce kombinasyonlu eğitimde yanlış preset fark edilmelidir).
    Theta içeren tanımlar tutarlılık bekçisinden geçer (§9.37).
    """
    if soil is None:
        return {}
    if isinstance(soil, dict):
        return _check_theta_consistency(dict(soil))
    try:
        return _check_theta_consistency(dict(SOIL_PRESETS[soil]))
    except KeyError:
        raise ValueError(
            f"bilinmeyen toprak '{soil}' (kumlu/tınlı/killi ya da dict)")


# ----------------------------------------------------------------------------
# D) TEK BİTKİ - durum + fizyoloji
# ----------------------------------------------------------------------------

class Plant:
    def __init__(self, params: PlantParams, plant_id: int,
                 seed: int | None = None):
        self.p = params
        self.id = plant_id
        # Birey tohumu (canlı listeleme §9.54): yalnız kimlik/betimleme,
        # fiziğe girmez. None = kayıtsız (eski çağrılar birebir aynı).
        self.seed = seed
        self.stage = Stage.DORMANT
        self.stage_age = 0

        self.soil_moisture = 28.0
        self.ec_mass = params.ec_baseline * self.soil_moisture  # "tuz kütlesi", EC = mass/moisture
        self.o2_deficit_ticks = 0

        self.leaf_health = 100.0
        self.root_health = 100.0
        self.tuber_mass = 1.0
        self.water_balance = 0.0
        self.stem_height = 0.0           # boy (morfolojik model birimi, §9.27)
        self.wb_last = {}                # son adımın su defteri (adım 5):
        # {infil, et, drain, uptake, d_storage, residual} — uptake
        # 6. adımdan sonra dolar; residual = giren−çıkan−depolanan.
        self.salt_last = {}              # son adımın tuz defteri (§9.48):
        # {fert_in, leached, d_mass, residual}.

        # NPU'ya asla verilmeyecek, sadece senin doğrulaman için:
        self.ground_truth_events = []

    # ---- yardımcı: mevcut EC ----
    @property
    def ec(self) -> float:
        return self.ec_mass / max(self.soil_moisture, 1.0)

    def step(self, day_of_year: int, temp: float, photoperiod: float,
              rain_mm: float, irrigation_mm: float = 0.0, fertilizer_dose_mass: float = 0.0,
              uv_deficit: float = 0.0, rh_frac: float | None = None,
              drain_mult: float = 1.0, pathogen_boost: float = 0.0):
        p = self.p

        # ---- 0) VPD ÇARPANI (§9.46) ----
        # YALNIZ v1 yolunda (theta_s>0) ve RH verildiyse: kurutucu güç
        # referansa oranlanır (20°C/%80 → 1.0). Verilmezse 1.0 —
        # o günkü v1 davranışı birebir korunur. Legacy RH'yi görmez.
        _vpd_f = 1.0
        _vpd = 0.0
        if p.theta_s > 0 and rh_frac is not None:
            _vpd = vpd_kpa(temp, rh_frac)
            _vpd_f = _vpd / _VPD_REF

        # ---- 1) TOPRAK NEMİ ----
        _moist_before = self.soil_moisture  # su defteri (adım 5) için
        light_factor = np.clip(photoperiod / 14.0, 0.35, 1.0)
        # evapotranspirasyonun küçük bir tabanı var (yüzey buharlaşması tam sıfıra inmez),
        # bu sayede kuru toprakta da nem azalmaya devam eder (self-limiting olmasın diye)
        et = p.et_coef * max(0.0, temp) * 0.06 * light_factor * (0.25 + 0.75 * self.soil_moisture / 100.0)
        # TODO: DOĞRULANMADI (fiziksel-v1 başlangıç varsayımı, §9.36) —
        # root_depth_mm>0 iken su hacmi kök derinliğine bölünerek VWC
        # puanına çevrilir (10mm/200mm = +5 puan); 0 iken legacy yol
        # (mm doğrudan puan) birebir korunur. Katsayılar (0.7/0.9) aynı.
        _water_mm = rain_mm * 0.7 + irrigation_mm * 0.9
        if p.root_depth_mm > 0:
            infiltration = _water_mm / p.root_depth_mm * 100.0
        else:
            infiltration = _water_mm
        # TODO: DOĞRULANMADI (fiziksel-v1 drenajı, adım 4, §9.36) —
        # thetalar tanımlıysa (theta_s>0) drenaj θFC referanslıdır ve
        # saturasyon taşması clip'e gömülmeden sistemden çıkar
        # (derin drenaj/yüzey akışı); katsayı (drainage_coef) aynı,
        # yeni sayı yok. Tanımsızsa legacy yol birebir korunur.
        if p.theta_s > 0:
            # Sayısal çözünürlük seçimi (adım 7, §9.36 — ampirik sayı
            # değil, 24 sa/gün tanımsaldır): hızlı fizik 24 saat-altı
            # adımda bütünlenir, yavaş haller (fenoloji/büyüme) günlük
            # kalır. Günlük ort. sıcaklık sabit tutulur — diurnal
            # zorlama gelecek iştir (DÜRÜST SINIR). Legacy yol dokunulmaz.
            _N = 24
            _et_tot = 0.0
            _drain_tot = 0.0
            for _h in range(_N):
                _et_h = (p.et_coef * max(0.0, temp) * 0.06 * light_factor
                         * (0.25 + 0.75 * self.soil_moisture / 100.0)
                         * _vpd_f / _N)
                _wet_h = self.soil_moisture + infiltration / _N - _et_h
                _ov_h = max(0.0, _wet_h - p.theta_s)
                _d_h = (p.drainage_coef * drain_mult
                        * max(0.0, _wet_h - _ov_h - p.theta_fc) / _N
                        + _ov_h)
                self.soil_moisture = max(1.0, _wet_h - _d_h)
                _et_tot += _et_h
                _drain_tot += _d_h
            et = _et_tot
            drainage = _drain_tot
        else:
            drainage = (p.drainage_coef * drain_mult
                        * max(0.0, self.soil_moisture - p.field_capacity))

        # EC, drenajla birlikte yıkanır (leaching); yeni su gelmeden önce mevcut derişimle orantılı
        leached_mass = drainage * (self.ec_mass / max(self.soil_moisture, 1.0)) * 0.4

        if p.theta_s > 0:
            # v1: nem saat-altı döngüde zaten güncellendi — yalnız
            # güvenlik kelepçesi (genelde no-op).
            self.soil_moisture = float(np.clip(self.soil_moisture,
                                               1.0, 100.0))
        else:
            self.soil_moisture = float(np.clip(
                self.soil_moisture + infiltration - et - drainage,
                1.0, 100.0))

        # ---- 1b) SU DEFTERİ (adım 5, §9.40) ----
        # residual = infil − et − drain − uptake − Δdepo; clip'e
        # takılmayan günde tam 0 olur (uptake anahtarı 6. adımda dolar).
        self.wb_last = {
            "infil": float(infiltration),
            "et": float(et),
            "drain": float(drainage),
            "uptake": 0.0,
            "d_storage": float(self.soil_moisture - _moist_before),
            "residual": float(infiltration - et - drainage
                              - (self.soil_moisture - _moist_before)),
            "vpd_kpa": float(_vpd),
            "rh_frac": (None if rh_frac is None else float(rh_frac)),
        }

        # ---- 2) EC / TUZLULUK ----
        # gübre SABİT bir tuz kütlesi ekler (miktar toprağın o anki nemine göre ölçeklenmez) —
        # bu yüzden toprak zaten kuruyken verilen gübre, ıslak toprağa göre çok daha sert bir
        # EC sıçramasına yol açar (aynı kütle, daha az hacimde = daha yüksek derişim)
        _salt_before = self.ec_mass  # tuz defteri (§9.48) için
        self.ec_mass = max(0.0, self.ec_mass - leached_mass + fertilizer_dose_mass)

        # ---- 2b) TUZ DEFTERİ (§9.48) ----
        # residual = gübre_giren − yıkanan − Δkütle; tabana (0) takılmayan
        # günde tam 0 olur. Bitki tuz alımı modelde YOK (açık borç) —
        # çıkış yalnız yıkanmadır.
        self.salt_last = {
            "fert_in": float(fertilizer_dose_mass),
            "leached": float(leached_mass),
            "d_mass": float(self.ec_mass - _salt_before),
            "residual": float(fertilizer_dose_mass - leached_mass
                              - (self.ec_mass - _salt_before)),
        }
        # not: nem buharlaştıkça (et, drenaj YOK) tuz kütlesi sabit kalır ama hacim düşer
        # -> ec = mass/moisture otomatik yükselir (konsantrasyon etkisi), ayrıca kod yazmaya gerek yok

        # ---- 3) OKSİJEN / KÖK ÇÜRÜKLÜĞÜ ----
        # Göreli eşik taşıma (yeni sayı YOK, §9.39): legacy eşiğin
        # FC→100 aralığındaki göreli konumu v1'de FC→θs aralığına
        # taşınır (legacy 82 → oran 0.60 → v1'de 42.4). Böylece su
        # basması v1 dünyasında da ateşlenebilir.
        _wl = p.waterlog_threshold
        if p.theta_s > 0:
            _span = max(1e-9, 100.0 - p.field_capacity)
            _wl = (p.theta_fc + (p.waterlog_threshold - p.field_capacity)
                   / _span * (p.theta_s - p.theta_fc))
        if self.soil_moisture > _wl:
            self.o2_deficit_ticks += 1
        else:
            self.o2_deficit_ticks = max(0, self.o2_deficit_ticks - 1)

        if self.o2_deficit_ticks > p.waterlog_tolerance_ticks:
            excess = self.o2_deficit_ticks - p.waterlog_tolerance_ticks
            # dormant dönemde yumru fazla neme en savunmasız
            vulnerability = 1.8 if self.stage == Stage.DORMANT else 1.0
            self.root_health -= (p.rot_rate * vulnerability
                                     * (excess ** 0.5) * 0.1
                                     * (1.0 + pathogen_boost))
            if excess == 1:
                self.ground_truth_events.append((day_of_year, "root_rot_onset"))

        # ---- 4) EC YANIĞI (kimyasal/ozmotik kök hasarı) ----
        if self.ec > p.ec_burn_threshold:
            overshoot = self.ec - p.ec_burn_threshold
            self.root_health -= p.ec_burn_rate * overshoot * 0.15
            if overshoot > 0 and overshoot < p.ec_burn_rate * 0.2:
                self.ground_truth_events.append((day_of_year, "salt_burn_onset"))

        # ---- 5) SU ALIMI / TURGOR (ozmotik denge) ----
        # toprağın "su çekme gücü": kuruluk VE tuzluluk ikisi de suyu bitkiden kaçırır
        # (v1'de kuruluk referansı θFC'dir — legacy'de field_capacity).
        _fc_ref = p.theta_fc if p.theta_s > 0 else p.field_capacity
        dryness_term = -0.02 * max(0.0, _fc_ref - self.soil_moisture)
        osmotic_term = -0.35 * self.ec
        soil_water_potential = dryness_term + osmotic_term

        uptake_gradient = soil_water_potential - p.root_water_potential
        # kök sağlığı düşükse su çekme kapasitesi de düşer
        root_capacity = np.clip(self.root_health / 100.0, 0.05, 1.0)
        self.water_balance = uptake_gradient * root_capacity

        # TODO: DOĞRULANMADI (fiziksel-v1 bitki alımı, adım 6, §9.36) —
        # transpirasyon toprağı TÜKETİR: pozitif gradyanın uptake_coef
        # kadarlık kısmı, solma noktası üstündeki sudan çekilir ve su
        # defterine gider olarak işlenir. Legacy yolda alım toprağa
        # dokunmaz (birebir korunur).
        if p.theta_s > 0:
            _up = min(max(0.0, self.water_balance) * p.uptake_coef
                      * _vpd_f,
                      max(0.0, self.soil_moisture - p.theta_wp))
            self.soil_moisture = max(1.0, self.soil_moisture - _up)
            self.wb_last["uptake"] = float(_up)
            self.wb_last["d_storage"] = float(self.soil_moisture
                                              - _moist_before)
            self.wb_last["residual"] = float(
                self.wb_last["infil"] - self.wb_last["et"]
                - self.wb_last["drain"] - _up
                - (self.soil_moisture - _moist_before))

        if self.water_balance < -0.15:
            self.leaf_health -= p.wilt_rate * abs(self.water_balance)
        elif self.water_balance > 0 and self.stage in (Stage.VEGETATIVE, Stage.FLOWERING, Stage.SPROUTING):
            self.leaf_health = min(100.0, self.leaf_health + p.recovery_rate * self.water_balance)

        self.leaf_health = float(np.clip(self.leaf_health, 0.0, 100.0))
        self.root_health = float(np.clip(self.root_health, 0.0, 100.0))

        # ---- 5b) DON HASARI (§9.49, TODO: DOĞRULANMADI) ----
        # temp<0 iken yaprak donar (kaba vekil; yumru dayanır).
        # Kapılarda ölü kod (ölçülen min 2.75°C) — yalnız olay
        # motorunun soğuk-dalgası senaryolarında ateşlenir.
        if temp < 0.0:
            self.leaf_health = max(
                0.0, self.leaf_health - p.frost_rate * min(1.0, -temp))
            if not any(d == day_of_year and e == "frost_damage"
                       for d, e in self.ground_truth_events):
                self.ground_truth_events.append(
                    (day_of_year, "frost_damage"))

        # ---- 6) FENOLOJİ GEÇİŞLERİ ----
        self._advance_stage(day_of_year, temp, photoperiod, rain_mm)

        # ---- 7) ENERJİ / BÜYÜME ----
        if self.stage in (Stage.VEGETATIVE, Stage.FLOWERING) and self.leaf_health > 5:
            photo_rate = p.photo_k * light_factor * (self.leaf_health / 100.0)
            self.tuber_mass += photo_rate * p.tuber_alloc_frac * 0.1

        # ---- 9) BOY (morfolojik, §9.27) ----
        # Boy-atma evrelerinde uzar; UV açığı (bulutluluk) hızlandırır.
        # Yumru/verim hesabına girmez — yalnız morfolojik çıktı + ekran.
        if self.stage in (Stage.SPROUTING, Stage.VEGETATIVE, Stage.FLOWERING):
            self.stem_height += (p.stem_growth_base
                                 * (1.0 + p.uv_elong_gain * uv_deficit))

        # ---- 8a) KURUMA → UYKU (§9.31) ----
        # Yaprağı bitmiş ama yumrusu dolu bitki ÖLMEZ — yaz uykusuna yatar
        # (salep estivasyonu). Toprak-üstü kurur, yumru uyur. Yeni sayı yok:
        # eşikler mevcut (0.0 yaprak, 0.3 rezerv), sıfırlama SENESCENCE
        # kolundakiyle aynı (boy=0).
        if (self.leaf_health <= 0 and self.tuber_mass >= 0.3
                and self.stage in (Stage.SPROUTING, Stage.VEGETATIVE,
                                   Stage.FLOWERING, Stage.SENESCENCE)):
            self.stage, self.stage_age = Stage.DORMANT, 0
            self.stem_height = 0.0
            self.ground_truth_events.append((day_of_year, "drought_dormancy"))

        # ---- 8b) ÖLÜM KOŞULU (§9.31) ----
        # DEAD yalnız gerçek ölüm içindir: kök çürüklüğü/tuz yanığı
        # (root_health<=0) ya da rezervsiz açlık (yaprak bitik + yumru<0.3).
        # Koşul metni değişmedi — 8a kuruyan-rezervli bitkiyi DORMANT'a
        # çektiği için buraya artık o durum düşmez.
        if self.root_health <= 0 or (self.leaf_health <= 0 and self.stage != Stage.DORMANT and self.tuber_mass < 0.3):
            if self.stage != Stage.DEAD:
                self.ground_truth_events.append((day_of_year, "plant_death"))
            self.stage = Stage.DEAD

        self.stage_age += 1

    def _advance_stage(self, day_of_year, temp, photoperiod, rain_mm):
        p = self.p
        # Sürgün kapısı (§9.22 + §9.31): parantezler eski önceliği korur
        # ((yağmur & serin & güz) | ocak). §9.31 eki: yapraksız + yağmursuz
        # sürgün yok — iskelet uyanmaz, önce su gelir (yeni sayı yok:
        # 0.0 yaprak, mevcut sprout_rain_min). Ocak kapısı tuhaflığı yapraklı
        # bitkide aynen durur (G2 disiplini).
        gate = ((rain_mm > p.sprout_rain_min
                 and temp < p.sprout_temp_max and 240 < day_of_year)
                or day_of_year < 30)
        gate &= (self.leaf_health > 0 or rain_mm > p.sprout_rain_min)
        if self.stage == Stage.DEAD:
            # SONSUZ KOŞU (§9.22): DEAD yutucu durum değildir. Sürgün kapısı
            # DORMANT ile birebir aynıdır (yeni sayı yok); kapı açılınca
            # tohum/yumru bankasından taze birey başlar (toprak aynen durur,
            # değerler __init__ kanoniğidir).
            if gate:
                self.leaf_health = 100.0
                self.root_health = 100.0
                self.tuber_mass = 1.0
                self.stem_height = 0.0
                self.o2_deficit_ticks = 0
                self.ground_truth_events.append((day_of_year, "rebirth"))
                self.stage, self.stage_age = Stage.SPROUTING, 0
            return

        if self.stage == Stage.DORMANT:
            if gate:
                self.stage, self.stage_age = Stage.SPROUTING, 0

        elif self.stage == Stage.SPROUTING:
            if self.stage_age > p.stage_len_sprouting:
                self.stage, self.stage_age = Stage.VEGETATIVE, 0

        elif self.stage == Stage.VEGETATIVE:
            if photoperiod > p.flower_photoperiod_min and 60 < day_of_year < 150:
                self.stage, self.stage_age = Stage.FLOWERING, 0

        elif self.stage == Stage.FLOWERING:
            if self.stage_age > p.stage_len_flowering:
                self.stage, self.stage_age = Stage.SENESCENCE, 0

        elif self.stage == Stage.SENESCENCE:
            if temp > p.senescence_temp_min:
                self.stage, self.stage_age = Stage.DORMANT, 0
                self.leaf_health = 100.0  # yeni yaprak döngüsüne sıfırdan başlar
                self.stem_height = 0.0    # toprak-üstü kurur, yumru uyur (§9.27)


# ----------------------------------------------------------------------------
# POPÜLASYON KOŞUCUSU
# ----------------------------------------------------------------------------

def run_population(n_plants=12, n_days=365 * 2, seed=42,
                    scripted_events=None, weather_csv=None,
                    weather_year=None, weather_uv=None,
                    soil=None, param_spread=0.13) -> pd.DataFrame:
    """
    scripted_events: dict {day_of_year_absolute: {"irrigation_mm": x, "fertilizer_dose_mass": y}}
    Belirli günlerde müdahale (sulama kesme, gübre şoku vb.) enjekte etmek için.
    weather_csv: gerçek gözlem dosyası (Open-Meteo günlük, §9.26) veya None
    (None = sentetik model; varsayılan akış birebir aynı kalır).
    weather_uv: UV dosyası (Open-Meteo günlük, §9.27) veya None.
    soil: "kumlu"/"tınlı"/"killi" ya da parametre dict'i (§9.35);
    None = öntanımlı (tınlı ile birebir aynı, G2 kilidi).
    param_spread: bitki-arası dağılım (varsayılan 0.13); 0 = tam
    deterministik (eğitim süpürmeleri için).
    """
    scripted_events = scripted_events or {}
    observed = (load_observed_weather(weather_csv, weather_year)
                if weather_csv else None)
    if weather_uv:
        observed = attach_observed_uv(observed, weather_uv)
    world = WorldDriver(seed=seed, observed=observed)
    master_rng = np.random.default_rng(seed)
    base = PlantParams()
    for k, v in soil_overrides(soil).items():
        setattr(base, k, v)

    # Birey tohumları (§9.54): master akışa DOKUNULMAZ (G2-güvenli) —
    # SeedSequence kardeş akışı jitter çekiş sırasını değiştirmez.
    pseeds = [int(s.generate_state(1)[0]) % (2 ** 31)
              for s in np.random.SeedSequence(seed).spawn(n_plants)]
    plants = [Plant(jittered_params(base, master_rng, spread=param_spread), i,
                    seed=pseeds[i])
              for i in range(n_plants)]

    rows = []
    for t in range(n_days):
        day_of_year = t % 365
        temp = world.temperature(t)
        photo = world.photoperiod_hours(day_of_year)
        rain = world.rain_event_mm(day_of_year, abs_day=t)

        ev = scripted_events.get(t, {})
        irrigation = ev.get("irrigation_mm", 0.0)
        fert = ev.get("fertilizer_dose_mass", 0.0)
        if ev.get("force_no_rain", False):
            rain = 0.0

        # Ortam nemi: bitki adımından ÖNCEKİ günün kovası girer
        # (bir gün gecikmeli geri-besleme, §9.47). Legacy bitki RH'yi
        # görmez (theta_s==0 → çarpan 1.0), o yüzden bu geçiş G2-güvenlidir.
        rh = world.rh_frac
        for plant in plants:
            # Ölü bitki de adım atar: toprağı sürer, sürgün kapısı açılınca
            # rebirth ile döner (§9.22) — gün ızgarasında boşluk kalmaz.
            uv_def = world.uv_deficit(t, day_of_year)
            plant.step(day_of_year, temp, photo, rain,
                       irrigation_mm=irrigation, fertilizer_dose_mass=fert,
                       uv_deficit=uv_def, rh_frac=rh)
            uv_ix = world.uv_index(t, day_of_year)
            rows.append({
                "day": t, "plant_id": plant.id, "temp": round(temp, 2),
                "photoperiod": round(photo, 2), "rain_mm": round(rain, 2),
                "uv_index": (None if uv_ix is None else round(uv_ix, 2)),
                "uv_deficit": round(uv_def, 3),
                "stem_height": round(plant.stem_height, 3),
                "soil_moisture": round(plant.soil_moisture, 2),
                "soil_ec": round(plant.ec, 3),
                "o2_deficit_ticks": plant.o2_deficit_ticks,
                "leaf_health": round(plant.leaf_health, 2),
                "root_health": round(plant.root_health, 2),
                "tuber_mass": round(plant.tuber_mass, 3),
                "water_balance": round(plant.water_balance, 3),
                "stage": plant.stage.name,
                # NPU'ya VERİLMEYECEK doğrulama kolonu -> eğitim/test ayrımında bunu düşür
                "ground_truth_event": next(
                    (e for d, e in plant.ground_truth_events if d == day_of_year), ""
                ),
            })
        # Kova güncellemesi gün sonunda (tüm bitkilerden sonra):
        # yağmur+sıcaklık + popülasyonun ortalama transpirasyonu
        # (v1 alımı; legacy'de 0 → yalnız hava sürer).
        vapor = (sum(pl.wb_last.get("uptake", 0.0) for pl in plants)
                 / max(1, len(plants)))
        world.step_rh(temp, rain, vapor_pts=vapor)

    return pd.DataFrame(rows)


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    df = run_population()
    df.to_csv(os.path.join(OUT_DIR, "population_baseline.csv"), index=False)
    print(df.groupby("plant_id")["stage"].last())
    print(f"toplam satır: {len(df)}")
