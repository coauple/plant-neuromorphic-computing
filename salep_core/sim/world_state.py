"""Canlı dünya durumu: SimClock + WorldDriver/Plant döngüsü.

K4 kuralı: sim_days_per_sec. Fizik günlük adım atar,
görsel iki gün arasında lerp eder → akıcı 60 FPS. NPU kendi tick
hızında bağımsız çalışır.

Zaman modeli (HİBRİT Adım 1):
- FİZİK: Plant.step günde 1 kez, temperature(tam_gün) ile kanonik
  sırada çağrılır → run_population ile aynı RNG akışı (sadakat).
  snapshot["temp"] = physics_temp (gün boyu SABİT — sensörler bunu okur).
- GÖRSEL: snapshot["display_temp"] = günlük baz + deterministik
  diurnal. Gürültü günde 1 kez örneklenir (fizik disiplini), diurnal
  fazı +0.375 gün kayık: tepe ~15:00, dip ~05:00 (A2 düzeltmesi).
  refresh_display() her fizik tick'inde tazeler; FPS'ten bağımsız,
  tekrarlanabilir (günlük baz gün başına önbelleklidir).
- EYLEM: sula/gübre bugünün anahtarına değil pending kuyruğuna yazar;
  bir sonraki step'te tüketilir (kayıp sulama kusurunun düzeltmesi).
"""
import threading
import time
import numpy as np
from sim.plant_sim import (WorldDriver, Plant, PlantParams, Stage,
                           load_observed_weather, attach_observed_uv,
                           reconstruct_hour_temp, soil_overrides)


# Canlı yayın başlangıcı (§9.56): 1 Ekim (güz yağmurlarıyla filizlenme;
# Ocak kapısı tuhaflığıyla 1 Ocak'ta filizlenme olmaz).
START_DAY = 273
# Canlı döngü kapanışı (§9.55): erken ölümde çıplak toprakta bekleme.
RESOW_DELAY_DAYS = 5


class SimClock:
    """Hız kontrollü simülasyon saati."""

    def __init__(self, speed: float = 1.0):
        self.speed = speed          # sim_days_per_sec (×1/×4/×16)
        self.paused = False
        self.sim_day = 0            # tam gün sayacı
        self.day_frac = 0.0         # gün-içi kesir (0.0-1.0)
        self._lock = threading.Lock()

    def tick(self, dt_real: float):
        """Gerçek zamandan sim-gün ilerlemesi."""
        if self.paused:
            return
        with self._lock:
            advance = dt_real * self.speed
            self.day_frac += advance
            while self.day_frac >= 1.0:
                self.day_frac -= 1.0
                self.sim_day += 1

    def set_speed(self, speed: float):
        with self._lock:
            self.speed = speed

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def get_day_info(self):
        with self._lock:
            return self.sim_day, self.day_frac


class WorldState:
    """Fizik thread'inde koşan dünya + bitki durumu.

    Anayasa uyumu:
    - ground_truth_event snapshot'a ASLA girmez (§0, K6)
    - Çekirdek değişmez (§9.9, K5)
    """

    def __init__(self, seed: int = 42, speed: float = 1.0,
                 weather_csv=None, weather_year=None, weather_uv=None,
                 soil=None, start_day: int = START_DAY):
        self._start_day = int(start_day)
        self.clock = SimClock(speed)
        self.clock.sim_day = self._start_day
        # Gerçek gözlem dosyası (§9.26) veya None (sentetik varsayılan).
        self._observed = (load_observed_weather(weather_csv, weather_year)
                          if weather_csv else None)
        if weather_uv:
            self._observed = attach_observed_uv(self._observed, weather_uv)
        self.world = WorldDriver(seed, observed=self._observed)
        # Display sürücüsü: diurnal örnekleme için AYRI RNG akışı.
        # Fizik akışı (temp→rain sırası) kanonik kalır, G2 sadakati bozulmaz.
        self.display_world = WorldDriver(seed + 1000)
        self.plant = Plant(PlantParams(), plant_id=0, seed=seed)
        self._soil = "varsayılan"
        self._soil_arg = soil
        self.set_soil(soil)
        self.seed = seed
        # Canlı döngü kapanışı (§9.55): döngü sayacı + ölüm bekleyişi.
        # Çekirdek (plant_sim) DEĞİŞMEZ — politika yalnız bu katmandadır.
        self.cycle_idx = 0
        self._dead_since = None
        self._last_stepped_day = self._start_day - 1
        self._lock = threading.Lock()
        # Senaryo enjeksiyonu (gelecek günler: kuraklık vb.)
        self.scripted_events: dict = {}
        # Pending eylem kuyruğu (bir sonraki step'te tüketilir, tek atımlık)
        self._pending_irrigation_mm = 0.0
        self._pending_fert_mass = 0.0
        # Son gübre dozu (sensor_map için)
        self._last_fert_dose = 0.0
        # Toprak sıcaklığı EMA'sı + olay halkası (v2 şeması)
        self.soil_temp = 15.0
        self._events: list = []
        # Display günlük-baz önbelleği (gün başına 1 gürültü örneği)
        self._disp_base_day: int | None = None
        self._disp_base_val: float = 0.0
        # Snapshot (thread-safe okuma için)
        self._snapshot: dict = {}

    def step_if_needed(self):
        """Gün değiştiyse Plant.step çağır.

        Fizik sıcaklığı kanonik tam-gün çağrısıdır (run_population ile
        aynı RNG sırası). Pending kuyruk bu adımda tüketilir.
        """
        day = self.clock.sim_day
        if day == self._last_stepped_day:
            return
        self._last_stepped_day = day
        doy = day % 365
        day_frac = self.clock.day_frac
        temp = self.world.temperature(day)  # kanonik: tam gün, diurnal=0
        photo = self.world.photoperiod_hours(doy)
        rain = self.world.rain_event_mm(doy, abs_day=day)

        # Senaryo enjeksiyonu (gelecek gün anahtarları)
        ev = self.scripted_events.get(day, {})
        irr = ev.get("irrigation_mm", 0.0)
        fert = ev.get("fertilizer_dose_mass", 0.0)
        if ev.get("force_no_rain"):
            rain = 0.0

        # A6: süresi geçen senaryo anahtarlarını buda
        for k in [k for k in self.scripted_events if k < day]:
            del self.scripted_events[k]

        # Pending kuyruğu tüket (tek atımlık eylemler: sula/gübre)
        with self._lock:
            irr += self._pending_irrigation_mm
            fert += self._pending_fert_mass
            applied_irr = self._pending_irrigation_mm
            applied_fert = self._pending_fert_mass
            self._pending_irrigation_mm = 0.0
            self._pending_fert_mass = 0.0

        self._last_fert_dose = fert
        uv_def = self.world.uv_deficit(day, doy)
        uv_ix = self.world.uv_index(day, doy)
        # Ortam nemi bir gün gecikmeli girer (§9.47); kova adım sonunda
        # güncellenir. Legacy bitki RH'yi görmez (G2-güvenli). Şemaya
        # yeni anahtar YOK (v2 donuk) — RH iç haldir, panel sonra.
        rh = self.world.rh_frac
        prev_stage = self.plant.stage
        self.plant.step(doy, temp, photo, rain, irr, fert,
                        uv_deficit=uv_def, rh_frac=rh)
        self._cycle_watch(day, prev_stage)
        self.world.step_rh(
            temp, rain,
            vapor_pts=self.plant.wb_last.get("uptake", 0.0))

        # Toprak sıcaklığı: hava sıcaklığının EMA'sı (τ≈7 gün, belgeli
        # türetme — ts sensör disipliniyle aynı; fizik iddiası değil).
        self.soil_temp += (temp - self.soil_temp) / 7.0
        sun_alt, sun_az, sky = self.sun_position(day_frac, photo)

        # Olay kaydı: YALNIZCA kullanıcı/senaryo eylemleri (model etiketi değil)
        if applied_irr > 0 or applied_fert > 0:
            self._events.append({
                "day": day,
                "kind": ("irrigation_applied" if applied_irr > 0
                         else "fertilizer_applied"),
                "mm": applied_irr,
                "mass": applied_fert,
            })
            self._events = self._events[-50:]

        with self._lock:
            self._snapshot = {
                "sim_day": day,
                "day_frac": day_frac,
                "day_of_year": doy,
                # temp = physics_temp: gün boyu SABİT, sensörler bunu okur (A1)
                "temp": temp,
                "physics_temp": temp,
                "display_temp": self._display_temp_locked(day, day_frac),
                "temp_soil": self.soil_temp,
                "photoperiod": photo,
                "sun_alt_deg": sun_alt,
                "sun_az_deg": sun_az,
                "sky": sky,
                "rain_mm": rain,
                "soil_moisture": self.plant.soil_moisture,
                "soil_ec": self.plant.ec,
                "stem_height": self.plant.stem_height,
                "uv_index": uv_ix,
                "uv_deficit": uv_def,
                "leaf_health": self.plant.leaf_health,
                "root_health": self.plant.root_health,
                "tuber_mass": self.plant.tuber_mass,
                "water_balance": self.plant.water_balance,
                "stage": self.plant.stage.name,
                "stage_age": self.plant.stage_age,
                "o2_deficit_ticks": self.plant.o2_deficit_ticks,
                "fert_dose": fert,
                "applied_irrigation_mm": applied_irr,
                "applied_fert_mass": applied_fert,
                "pending_irrigation_mm": self._pending_irrigation_mm,
                "pending_fert_mass": self._pending_fert_mass,
                "active_scenarios": len(self.scripted_events),
                "events": list(self._events),
                # ground_truth_event BURAYA GİRMEZ (anayasa §0)
            }

    def _cycle_seed(self, cycle_idx: int) -> int:
        """Döngü tohumu: master'dan deterministik kardeş akış (§9.55).

        Aynı (master, döngü) → aynı tohum; döngüler birbirini etkilemez.
        """
        kids = np.random.SeedSequence(int(self.seed)).spawn(
            int(cycle_idx) + 1)
        return int(kids[-1].generate_state(1)[0]) % (2 ** 31)

    def _note_event(self, day: int, kind: str, **fields):
        """Kareye düşen gözlemsel olay (panel/toast yolu; K6-safe).

        Yalnız gözle görülür durum (ölüm/ekim) yazılır — ground_truth
        ASLA taşınmaz, tohum zaten kamusal kimliktir (/seeds).
        """
        self._events.append({"day": day, "kind": kind, **fields})
        self._events = self._events[-50:]

    def _resow(self, day: int, reason: str):
        """Taze birey: yeni tohum, aynı saksı (toprak/nem durur).

        Fide dikimi: filizlenerek başlar (mevsim beklenmez — yazın
        ekilen tohumun güz yağmuruna kadar uyuması "takılma" hissi
        veriyordu). Nesne bizim canlı bireyimizdir; çekirdek
        kaynağı değişmez.
        """
        self.cycle_idx += 1
        seed = self._cycle_seed(self.cycle_idx)
        sm, ec_mass = self.plant.soil_moisture, self.plant.ec_mass
        self.plant = Plant(PlantParams(), plant_id=0, seed=seed)
        self.plant.stage, self.plant.stage_age = Stage.SPROUTING, 0
        self.set_soil(self._soil_arg)
        self.plant.soil_moisture = sm
        self.plant.ec_mass = ec_mass
        self._dead_since = None
        self._note_event(day, "resow", reason=reason, seed=seed)

    def _cycle_watch(self, day: int, prev_stage):
        """Canlı döngü kapanışı (§9.55) — çekirdek geçişlerini izler:

        - Doğal döngü sonu (sararma tamamlanıp yapraklar tazelenmişse):
          üretici yeniden eker — aynı gün taze birey, yeni tohum.
        - Erken ölüm (kök/koşul): ölüm ilan edilir, çıplak toprak
          RESOW_DELAY_DAYS gün bekler, sonra taze birey, yeni tohum.
        Çekirdeğin kendi diriltmesi (rebirth) bekleyişi sıfırlar.
        """
        stage = self.plant.stage
        if (prev_stage == Stage.DEAD and stage != Stage.DEAD
                and self._dead_since is not None):
            # Çekirdek bekleyişte diriltti (rebirth) — politika bekleyişi
            # korur: diriltme geri alınır, ölü bekleyiş sürer. Nesne bizim
            # canlı bireyimizdir; çekirdek kaynağı değişmez.
            self.plant.stage = Stage.DEAD
            self.plant.leaf_health = 0.0
            self.plant.root_health = 0.0
            self.plant.stage_age = 0
            return
        if stage == Stage.DEAD:
            if self._dead_since is None:
                self._dead_since = day
                cause = ("root_rot" if self.plant.root_health <= 0
                         else "starvation")
                self._note_event(day, "plant_death", cause=cause)
            elif day - self._dead_since >= RESOW_DELAY_DAYS:
                self._resow(day, reason="plant_death")
            return
        if self._dead_since is not None:
            self._dead_since = None
        if (prev_stage == Stage.SENESCENCE and stage == Stage.DORMANT
                and self.plant.leaf_health >= 100.0):
            self._resow(day, reason="cycle_complete")

    @staticmethod
    def sun_position(day_frac: float, photoperiod: float):
        """Güneş konumu (alt, az, gök): 12 ± photo/2 gün aralığı.

        Tepe ~12:00 (sıcaklık tepesi ~15:00, 3 saat gecikmeli — fiziksel).
        Azimut: doğum 90°(doğu) → öğlen 180°(güney) → batım 270°(batı).
        """
        import math
        sunrise = 12.0 - photoperiod / 2.0
        sunset = 12.0 + photoperiod / 2.0
        span = max(0.5, sunset - sunrise)
        hour = day_frac * 24.0
        day_t = (hour - sunrise) / span
        if day_t <= 0 or day_t >= 1:
            return -20.0, 0.0, "night"
        alt = 90.0 * math.sin(math.pi * day_t)
        az = 90.0 + 180.0 * day_t
        sky = "day" if alt > 10.0 else "dusk"
        return alt, az, sky

    # Diurnal faz kayması: tepe ~15:00 (frac 0.625), dip ~05:00.
    # sin(2π(f−φ)) tepeyi f=φ+0.25'e koyar → φ = 0.375.
    _DIURNAL_PHASE = 0.375

    def _display_base_locked(self, day: int) -> float:
        """Günlük baz sıcaklık — gün başına 1 gürültü örneği (önbellekli).

        Kilit altında çağrılır. Fizik RNG akışına dokunmaz.
        """
        if day != self._disp_base_day:
            self._disp_base_day = day
            self._disp_base_val = self.display_world.temperature(day)
        return self._disp_base_val

    def _display_temp_locked(self, day: int, day_frac: float) -> float:
        """Kilit-altı display sıcaklığı (§9.30).

        Gözlem dosyasında o günün min/maks'ı varsa gün-içi eğri
        (15:00 maks çapalı rekonstrüksiyon) döner; yoksa eski yol
        (günlük baz + deterministik diurnal) aynen çalışır.
        Fizik (snapshot temp) buradan BESLENMEZ — günlük ortalamadır.
        """
        import math
        curve = self.world.day_curve(day, day % 365)
        if curve is not None:
            return reconstruct_hour_temp(curve[0], curve[1],
                                         day_frac * 24.0)
        base = self._display_base_locked(day)
        amp = self.display_world.daily_amp
        return base + amp * math.sin(
            2 * math.pi * (day_frac - self._DIURNAL_PHASE))

    def sample_display_temp(self, t_continuous: float) -> float:
        """Sürekli zamandaki görünen sıcaklık (G10 kapısı bunu ölçer)."""
        day = int(t_continuous)
        frac = t_continuous - day
        with self._lock:
            return self._display_temp_locked(day, frac)

    def refresh_display(self):
        """Her fizik tick'inde: display_temp + day_frac + pending güncelle.

        snapshot["temp"] (physics) ELLEMEZ — sensörler kararlı değerden
        beslenir (A1). QML'e sadece GUI thread'inden dokunulur (K2); bu
        metot sözlüğü tazeler, QML bağlaması GUI pompasıyla akar.
        """
        day = self.clock.sim_day
        day_frac = self.clock.day_frac
        with self._lock:
            if not self._snapshot:
                return
            self._snapshot["day_frac"] = day_frac
            self._snapshot["display_temp"] = self._display_temp_locked(
                day, day_frac)
            self._snapshot["pending_irrigation_mm"] = \
                self._pending_irrigation_mm
            self._snapshot["pending_fert_mass"] = self._pending_fert_mass
            self._snapshot["active_scenarios"] = len(self.scripted_events)

    def get_snapshot(self) -> dict:
        with self._lock:
            return dict(self._snapshot)

    def describe_plants(self) -> list:
        """Canlı birey listesi (§9.54): tohum + ayırt edici parametreler.

        Çerçeve (v2) DIŞI kanaldır — şemaya anahtar eklenmez. ground_truth
        ASLA çıkmaz (K6).
        """
        with self._lock:
            p = self.plant.p
            return [{
                "plant_id": self.plant.id,
                "seed": self.plant.seed,
                "soil": self._soil_name(),
                "params": {
                    "field_capacity": p.field_capacity,
                    "drainage_coef": p.drainage_coef,
                    "et_coef": p.et_coef,
                    "root_depth_mm": p.root_depth_mm,
                    "theta_s": p.theta_s,
                    "theta_fc": p.theta_fc,
                    "theta_wp": p.theta_wp,
                    "uptake_coef": p.uptake_coef,
                },
            }]

    def get_last_fert_dose(self) -> float:
        return self._last_fert_dose

    def reset(self, seed: int | None = None):
        if seed is not None:
            self.seed = seed
        self.world = WorldDriver(self.seed, observed=self._observed)
        self.display_world = WorldDriver(self.seed + 1000)
        self.plant = Plant(PlantParams(), plant_id=0, seed=self.seed)
        self._soil = "varsayılan"
        self._soil_arg = None
        self.cycle_idx = 0
        self._dead_since = None
        self.clock.sim_day = self._start_day
        self.clock.day_frac = 0.0
        self._last_stepped_day = self._start_day - 1
        self._last_fert_dose = 0.0
        self.soil_temp = 15.0
        self._events = []
        with self._lock:
            self._pending_irrigation_mm = 0.0
            self._pending_fert_mass = 0.0
            self._disp_base_day = None
            self._disp_base_val = 0.0
        self._snapshot = {}

    def inject_scenario(self, events: dict):
        """Scripted events enjekte et (gelecek günler: kuraklık vb.)."""
        self.scripted_events.update(events)

    def inject_irrigation(self, mm: float):
        """Sulama: bir sonraki step'te uygulanır (latest-wins).

        Aynı gün üst üste basışlar TOPLANMAZ — en yeni değer kazanır
        (yayıncının latest-wins felsefesiyle aynı; G5e). Panel
        düğmeleri tek-atımlıktır: her basış o günün dozunu kurar.
        """
        with self._lock:
            self._pending_irrigation_mm = float(mm)

    def inject_fertilizer(self, mass: float):
        """Gübre: bir sonraki step'te uygulanır (latest-wins, G5e)."""
        with self._lock:
            self._pending_fert_mass = float(mass)

    def set_soil(self, soil):
        """Toprağı değiştir (preset adı ya da dict, §9.35).

        None = dokunma. Canlı deney + eğitim süpürmeleri için; mevcut
        nem/EC aynen durur (saksı değişir, içindeki su durur).
        """
        if soil is not None:
            self._soil_arg = soil
        if isinstance(soil, str):
            self._soil = soil
        elif soil is not None:
            self._soil = "özel-dict"
        for k, v in soil_overrides(soil).items():
            setattr(self.plant.p, k, v)

    def _soil_name(self) -> str:
        return self._soil
