"""Bitki elektrofizyolojisi — stres/çevre → elektriksel atım (türetme).

Gerçek bitkiler: kuraklık/sıcaklık varyasyon potansiyeli (yavaş
depolarizasyon), mekanik uyaran/yaralanma aksiyon potansiyeli (hızlı
ateşleme), uyku döneminde sessizlik. Bu modül o davranışıBelgeli
basitlikle üretir:

- Zar potansiyeli V (mV, dinlenim -120): kuraklık+hasar+sıcaklıkla
  yavaş depolarizasyon (EMA — varyasyon potansiyeli taklidi).
- Hat 0 (stres ateşleme): hız stresle artar (oran kodlaması).
- Hat 1 (olay patlaması): yağmur/sulama başlangıcı + sıcak şoku
  kümeli patlama (aksiyon potansiyeli taklidi).

DİSİPLİN: yalnız GÖZLEM katmanı — bitki/world nesneleri ASLA
değiştirilmez (K5), fiziğe girmez; NPU'ya yalnız darbe bayrakları
gider, "stres" etiketi YOK (K7). RNG kendi tohumludur (master+gün+hat),
fizik akışına dokunmaz. ph/npk gibi DOĞRULANMADI-türetmedir.
Yalnız stdlib.
"""

REST_MV = -120.0     # dinlenim zar potansiyeli (mV)
VP_MAX_MV = 50.0     # varyasyon potansiyeli tavanı (depolarizasyon)
DAY_TICKS = 50       # NPU saati: 1 sim-günü = 50 tick (blok 500 = 10 gün)


def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def _stable_rng(master_seed, day, line):
    """Kararlı int tohum (PYTHONHASHSEED'ten bağımsız)."""
    import random
    s = (int(master_seed) % (2 ** 31)) * 1000003 + int(day) * 101 + int(line)
    return random.Random(s % (2 ** 63 - 1))


class ElectroState:
    """Günlük elektrofizyoloji hali (bitki başına bir örnek)."""

    def __init__(self):
        self.vp = 0.0          # varyasyon potansiyeli (mV, EMA hali)
        self.prev_rain = 0.0
        self.prev_irrig = 0.0

    def step(self, temp, rain_mm, irrig_mm, water_balance, leaf_health,
             root_health, stage_name, master_seed, day):
        """Bir sim-günü → (V_mV, hat0_hızı, hat1_patlama)."""
        drought = clamp(-water_balance / 2.0)
        damage = clamp(((100.0 - leaf_health) + (100.0 - root_health)) / 200.0)
        heat = clamp((temp - 32.0) / 10.0)
        cold = clamp((5.0 - temp) / 10.0)
        rain_on = 1.0 if (rain_mm > 4.0 and self.prev_rain < 1.0) else 0.0
        irrig_on = 1.0 if irrig_mm > 0.0 else 0.0
        stage_f = {"DORMANT": 0.25, "DEAD": 0.0}.get(stage_name, 1.0)

        target = VP_MAX_MV * clamp(0.6 * drought + 0.5 * damage
                                   + 0.4 * heat + 0.2 * cold)
        self.vp += (target - self.vp) * 0.2
        v_mv = REST_MV + self.vp

        rate0 = stage_f * (0.5 + 30.0 * drought + 20.0 * damage
                           + 15.0 * (heat + cold))
        burst1 = stage_f * (rain_on * 5.0 + irrig_on * 4.0
                            + (3.0 if heat >= 1.0 else 0.0))
        self.prev_rain = rain_mm
        self.prev_irrig = irrig_mm
        return v_mv, rate0, burst1

    @staticmethod
    def _poisson(rng, lam):
        """Günlük atım sayacı (Knuth; büyük λ'da normal yaklaşım)."""
        import math
        if lam <= 0:
            return 0
        if lam > 60:
            return max(0, int(round(rng.gauss(lam, math.sqrt(lam)))))
        threshold = math.exp(-lam)
        k, p = 0, 1.0
        while True:
            k += 1
            p *= rng.random()
            if p <= threshold:
                break
        return k - 1

    def spikes_for_day(self, rate0, burst1, master_seed, day):
        """Hız/patlama → tick bayrakları ({0: [...], 1: [...]}, 0-49)."""
        out = {0: [], 1: []}
        r0 = _stable_rng(master_seed, day, 0)
        n0 = min(DAY_TICKS, self._poisson(r0, rate0))
        # Hız → gün içine düzgün yayılmış atımlar.
        ticks = sorted(r0.sample(range(DAY_TICKS), min(n0, DAY_TICKS)))
        out[0] = ticks
        if burst1 > 0:
            r1 = _stable_rng(master_seed, day, 1)
            start = r1.randrange(DAY_TICKS)
            n1 = min(8, max(1, int(round(burst1))))
            out[1] = sorted((start + r1.randrange(4)) % DAY_TICKS
                            for _ in range(n1))
        return out
