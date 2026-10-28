"""Monte Carlo: simultane FDM (PLIR + populasyon + faz kilidi) kalibrasyonu.

Anayasa Madde 0: hicbir sayisal iddia (N_POP, bw, LOCK_LOST_LIMIT, PULSE,
gurultu seviyesi, faz-hatasi esigi) C++'a gomulmeden once burada dogrulanir.

KOK NEDEN (teyit): eski ISI kapisi `last_wire_tick_A`'yi teldeki HER darbede
tazeler -> 4+12 superpoze telde tau=12 noronu ISI=4 gorur -> kapi hep soner.
PLIR: `last_resonant_tick_A` yalniz KABUL edilen darbede guncellenir ->
yabanci darbe hafizayi kirletmez, voltaja enerji birakmaz.

Model: C++ noron dinamiginin float ikizi (sizintili entegrator + difuzyon
%15 + gating + soma=root*(1+g); Dal B bos -> coincidence bonusu yok,
tipki phase_group SAPMA NOTU gibi). Dal A girisi PLIR veya eski-ISI kapili.

KALIBRE SONUC (19 deney; tum sayilar bu dosyayi kosturarak tekrar
uretilebilir. 2026-09-08 revizyonu: tick C++ neuron_tick birebir ikizi
(c CANLI + komsu SNAPSHOT; bos Dal B yuk etkisi dahil). Tek-noron probu
C++ ile ayni ates dizisini veriyor ([13,39]); tam tablo C++ ile ~0.01
duyarlilikta ortusuyor):
- FDM_BW=1 (D11: asal cifte tau9 hit 0.83 vs bw2 0.39; D15: +-1 zaman
  jitterinda bw2 daha direncli (tau12 0.57 vs 0.28) ama test kosulu
  deterministik izgara -> bw1; bw=2 TDM yolunda aynen kalir).
- LOCK_LOST=2*tau+bw (D3/D12/D16/D18: ucu de yeniden kilitlenir; 26 =
  gurultu-bagisikligi ile kisa-bosluk hizi arasi uzlasi).
- PULSE=0.8 (D4), N_POP=8 (D5: 4..14 duz), LEAK_JITTER=+-0.15,
  S2=%2 ekstra darbe + +-%20 genlik jitter (D6).
- C++ KRITERLERI (hepsi asagidaki D17/D13/D14 sayilarindan):
  (A) kilit: S1+S2 conc>=0.40 ve cov>=0.40 (D17: R1 0.49/0.81 cov
  0.98/0.98; R3 0.79/0.50 cov 0.67/0.50; S2 0.41/0.71, 0.52/0.46).
  (A2) mutlak faz tahmini: C++ merkezi asagidaki MC merkezinden +-0.5
  tick icinde (tolerans gerekcesi D14: jitter-cekilis varyansi 0.11-0.41).
  S1 merkezleri (D17): {4,12}: 1.50 / 2.18; {4,9}: 1.16 / 0.65.
  (C) {4,9} D9-kaydirma hatasi<=1 tick (D13: <=0.12 olculdu).
  (D) (i) S2 merkezi S1'den +-0.5 icinde (D17 S1->S2 kayma <=0.18);
  (ii) uye yayilimi<=1.5 tick (D9/D14: uyeler sikica anlasir, ~0.01).
- MUTLAK-IZGARA hit KAPI DEGIL (tani): ates karakteristigi gecikmeli
  (L~1-2 tick); izgara+-1 isabeti gecikme-karisik. Kilit=conc+cov, faz=A2+C.
- DURUST SINIRLAR: (i) harmonik cifte yavas-bant faz takibi YOK (D7:
  ilk-darbe capasi); (ii) seyrek-yabanci tele alt-harmonik suruklenme
  (D19; yeniden-kilit bedeli); (iii) 3-bantta tau16 capalanamiyor (D17
  hit=0.00) -> C++'da 3. bant YOK; (iv) {4,9}-yavas kilit tohum-duyarli
  (D10 vs D17: conc 0.20 vs 0.50; C++ tek deterministik cekilisle gecer,
  marj raporlanir).
"""

import numpy as np

WIN_COINC = 10
BONUS = 0.8
THR = 1.0
V_RESET = -0.2
DIFF = 0.15

# Bant bazinda sizinti (C++ make_pre_params ikizi: yavas bant = dusuk leak).
# (brA_leak, root_leak); Dal B bos oldugundan onun leak'i onemsiz.
BAND_LEAK = {4: (0.06, 0.08), 9: (0.03, 0.04), 12: (0.015, 0.02),
             16: (0.01, 0.01)}


def band_leak(tau):
    if tau in BAND_LEAK:
        return BAND_LEAK[tau]
    keys = sorted(BAND_LEAK)
    return BAND_LEAK[min(keys, key=lambda k: abs(k - tau))]


def mu_old(isi, tau, bw):
    if tau <= 0 or bw <= 0 or isi is None or isi < 0:
        return 1.0
    return max(0.0, 1.0 - abs(isi - tau) / bw)


class Member:
    """Tek noron uyesi: Dal A + kok (+bos Dal B difuzyonu)."""

    def __init__(self, tau, bw, leak_jitter=0.0, rng=None, plir=True,
                 lock_lost=None):
        self.tau = tau
        self.bw = bw
        self.plir = plir
        br, rt = band_leak(tau)
        j = 1.0
        if leak_jitter > 0 and rng is not None:
            j = 1.0 + rng.uniform(-leak_jitter, leak_jitter)
        self.leak_a = br * j
        self.leak_r = rt * j
        self.lock_lost = lock_lost if lock_lost is not None else 2 * tau + bw
        self.reset()

    def reset(self):
        self.a = 0.0
        self.b = 0.0
        self.root = 0.0
        self.g = 0.0
        self.ref = None      # PLIR: son KABUL edilen darbe
        self.wire = None     # eski ISI: son TEL darbesi
        self.fires = []

    def pulse(self, t, amp):
        """Ortak teldeki darbe (amp=0 -> darbe yok). Kabul/red kararı."""
        if amp <= 0:
            return False
        if self.plir:
            isi = t - self.ref if self.ref is not None else None
            if isi is None or isi > self.lock_lost:
                mu = 1.0  # taze kabul / yeniden kilitlenme
            else:
                d = abs(isi - self.tau)
                if d >= self.bw:
                    return False  # REDDET: ref korunur, voltaj yok
                mu = (self.bw - d) / self.bw
            self.a += amp * mu
            self.ref = t
            return True
        mu = mu_old(t - self.wire if self.wire is not None else None,
                    self.tau, self.bw)
        self.wire = t
        if mu <= 0:
            return False
        self.a += amp * mu
        return True

    def tick(self, t):
        # C++ neuron_tick birebir ikizi: c CANLI, komsu SNAPSHOT.
        # Sira: kok once (cocuklari snap'ten, ikinci cocuk guncellenmis
        # koku gorur), sonra dallar (ebeveyn snap'inden).
        # Bos Dal B onemli: kokun akimini emen bir yuk (sink) gibi davranir.
        sa, sb, sr = self.a, self.b, self.root
        r = sr + DIFF * (sa - sr)
        r = r + DIFF * (sb - r)
        self.root = r
        self.a = sa + DIFF * (sr - sa)
        self.b = sb + DIFF * (sr - sb)
        self.a -= self.leak_a * self.a
        self.b -= self.leak_a * self.b
        self.root -= self.leak_r * self.root
        if self.root > 0.15:
            self.g += 0.2
        self.g -= 0.005 * self.g
        if self.g < 0:
            self.g = 0.0
        soma = self.root * (1.0 + self.g)
        if soma > THR:
            self.a = self.b = self.root = V_RESET
            self.fires.append(t)
            return True
        return False


def make_wire(tau_list, T, delays, pulse=0.8, noise_p=0.0, amp_jit=0.0,
              drop=None, seed=0, gap=None):
    """Superpoze tel: wire[t] = toplam genlik. drop=(band, her_kacinci):
    bant-disi dayaniklilik icin o bandin her k'inci darbesini atar.
    gap=(t0,t1): pencere-boslugu (yeniden kilit testi)."""
    rng = np.random.default_rng(seed)
    wire = np.zeros(T)
    for bi, tau in enumerate(tau_list):
        d = delays[bi]
        k = 0
        for t in range(T):
            if (t - d) % tau == 0 and t >= d:
                if drop is not None and bi == drop[0] and k % drop[1] == 0:
                    k += 1
                    continue
                a = pulse
                if amp_jit > 0:
                    a *= 1.0 + rng.uniform(-amp_jit, amp_jit)
                wire[t] += a
                k += 1
    if gap is not None:
        wire[gap[0]:gap[1]] = 0.0
    if noise_p > 0:
        for t in range(T):
            if rng.random() < noise_p:
                a = pulse * 0.7
                if amp_jit > 0:
                    a *= 1.0 + rng.uniform(-amp_jit, amp_jit)
                wire[t] += a
    return wire


def circ_center(fires, tau):
    """Ateslerin tau-uzerinde dairesel merkezi (tick birimi)."""
    if not fires:
        return None
    ang = 2 * np.pi * (np.mod(fires, tau) / tau)
    m = np.exp(1j * ang).mean()
    return float(np.angle(m) / (2 * np.pi) * tau % tau)


def wrap_err(a, b, tau):
    d = (a - b) % tau
    if d > tau / 2:
        d -= tau
    return d


def concentration(fires, tau):
    if not fires:
        return 0.0
    bins = np.mod(fires, tau)
    hist, _ = np.histogram(bins, bins=np.arange(tau + 1))
    return float(hist.max() / len(fires))


def run_pop(tau_list, wire, bw=2, n_pop=8, leak_jitter=0.15, pulse_floor=0.0,
            seed=0, plir=True, lock_lost=None):
    """Her bant icin n_pop uyeli populasyon; ortak teli surer.
    Donus: {band: {fires(liste, uyeler havuzu), conc, center, per_member}}."""
    rng = np.random.default_rng(seed)
    T = len(wire)
    pops = []
    for tau in tau_list:
        pops.append([Member(tau, bw, leak_jitter, rng, plir, lock_lost)
                     for _ in range(n_pop)])
    for t in range(T):
        amp = wire[t]
        if amp > pulse_floor:
            for pop in pops:
                for m in pop:
                    m.pulse(t, amp)
        for pop in pops:
            for m in pop:
                m.tick(t)
    out = {}
    for bi, tau in enumerate(tau_list):
        pool = []
        per = []
        for m in pops[bi]:
            pool.extend(m.fires)
            per.append(list(m.fires))
        out[bi] = {"fires": pool, "conc": concentration(pool, tau),
                   "center": circ_center(pool, tau), "per_member": per}
    return out


def cross_conc(fires, tau_other):
    """Bir grubun ateslerinin RAKIP periyottaki konsantrasyonu (sizinti)."""
    return concentration(fires, tau_other)


def exp1_root_cause():
    print("=== DENEY 1: kok neden (eski-ISI vs PLIR, superpoze 4+12) ===")
    wire = make_wire([4, 12], 1200, [0, 0])
    for name, plir in [("eski-ISI", False), ("PLIR", True)]:
        r = run_pop([4, 12], wire, plir=plir, n_pop=1, leak_jitter=0.0,
                    seed=1)
        f4, f12 = r[0]["fires"], r[1]["fires"]
        print(f"{name}: bant4 ates={len(f4)} conc4={r[0]['conc']:.2f} | "
              f"bant12 ates={len(f12)} conc12={r[1]['conc']:.2f}")
    print("beklenti: eski-ISI bant12 ~sifir/atesleyemez; PLIR iki bant da kilitli")


def exp2_bw():
    print("\n=== DENEY 2: bw taramasi (superpoze 4+12, PLIR) ===")
    wire = make_wire([4, 12], 2000, [0, 0])
    for bw in [2, 3, 4]:
        r = run_pop([4, 12], wire, bw=bw, seed=2)
        leak412 = cross_conc(r[0]["fires"], 12)
        leak124 = cross_conc(r[1]["fires"], 4)
        print(f"bw={bw}: conc4={r[0]['conc']:.2f} conc12={r[1]['conc']:.2f} "
              f"capraz(4->12per)={leak412:.2f} capraz(12->4per)={leak124:.2f} "
              f"ates=({len(r[0]['fires'])},{len(r[1]['fires'])})")


def exp3_lock():
    print("\n=== DENEY 3: LOCK_LOST taramasi (kayip darbe + bosluk) ===")
    # (i) her 3. darbe dusen 12'lik + 4'luk kargasa
    wire = make_wire([4, 12], 2000, [0, 0], drop=(1, 3))
    # (ii) 400 tick bosluk sonrasi yeniden kilit
    wire_gap = make_wire([4, 12], 2400, [0, 0], gap=(1000, 1400))
    for mult, extra in [(1, 0), (2, 0), (2, 2), (3, 0)]:
        ll = 12 * mult + extra
        r = run_pop([12], wire, n_pop=4, seed=3, lock_lost=ll)
        fires = r[0]["fires"]
        late = [f for f in fires if f > 1400]
        rg = run_pop([12], wire_gap, n_pop=4, seed=3, lock_lost=ll)
        fires_g = rg[0]["fires"]
        post = [f for f in fires_g if f > 1400]
        print(f"LOCK={ll} (mult={mult},extra={extra}): kayipli conc={r[0]['conc']:.2f} "
              f"ates={len(fires)} | bosluk-sonrasi ates={len(post)} "
              f"conc_gap={rg[0]['conc']:.2f}")


def exp4_pulse():
    print("\n=== DENEY 4: PULSE taramasi (superpoze 4+12, PLIR) ===")
    for p in [0.6, 0.8, 1.0]:
        wire = make_wire([4, 12], 2000, [0, 0], pulse=p)
        r = run_pop([4, 12], wire, seed=4)
        print(f"PULSE={p}: bant4 ates={len(r[0]['fires'])} "
              f"conc4={r[0]['conc']:.2f} | bant12 ates={len(r[1]['fires'])} "
              f"conc12={r[1]['conc']:.2f}")


def exp5_jitter_npop():
    print("\n=== DENEY 5: leak-jitter x N_POP (S1 temiz tel) ===")
    wire = make_wire([4, 12], 2000, [0, 0])
    for jit in [0.0, 0.15, 0.3]:
        row = []
        for n in [4, 6, 8, 12, 14]:
            r = run_pop([4, 12], wire, n_pop=n, leak_jitter=jit, seed=5)
            row.append(f"N={n}:({r[0]['conc']:.2f},{r[1]['conc']:.2f})")
        print(f"jit={jit}: " + " ".join(row))
    print("(sirasiyla conc4,conc12)")


def exp6_noise():
    print("\n=== DENEY 6: S2 gurultu (superpoze 4+12 + rastgele darbe) ===")
    for nz in [0.0, 0.01, 0.02, 0.03, 0.05]:
        wire = make_wire([4, 12], 2400, [0, 0], noise_p=nz, amp_jit=0.2,
                         seed=60)
        r = run_pop([4, 12], wire, seed=6)
        print(f"gurultu={nz * 100:.0f}%: conc4={r[0]['conc']:.2f} "
              f"conc12={r[1]['conc']:.2f} ates=({len(r[0]['fires'])},"
              f"{len(r[1]['fires'])}) capraz124={cross_conc(r[1]['fires'], 4):.2f}")


def exp7_dshift():
    print("\n=== DENEY 7: D kaydirma (faz sifreleme, 12'lik gecikme) ===")
    print("grup merkezi kaymasi Delta(olc) vs Delta(D); hata<=1 tick beklenir")
    base = run_pop([12], make_wire([4, 12], 2400, [2, 0]), seed=7)[0]["center"]
    for d in [0, 2, 4, 6, 8, 10]:
        wire = make_wire([4, 12], 2400, [2, d])
        r = run_pop([12], wire, seed=7)[0]
        c = r["center"]
        err = abs(wrap_err(c - base, d - 0, 12))
        print(f"D12={d}: merkez={c:.2f} kayma_hatasi={err:.2f} tick "
              f"conc={r['conc']:.2f} ates={len(r['fires'])}")


def exp8_three_band():
    print("\n=== DENEY 8: 3 bant {4,9,16} + asal cift {4,9} ===")
    for taus, delays in [([4, 9], [0, 0]), ([4, 9, 16], [0, 3, 7])]:
        wire = make_wire(taus, 3600, delays)
        r = run_pop(taus, wire, seed=8)
        parts = []
        for bi, tau in enumerate(taus):
            parts.append(f"tau={tau}: ates={len(r[bi]['fires'])} "
                         f"conc={r[bi]['conc']:.2f}")
        print(" | ".join(parts))
    wire_n = make_wire([4, 9, 16], 3600, [0, 3, 7], noise_p=0.02,
                       amp_jit=0.2, seed=80)
    r = run_pop([4, 9, 16], wire_n, seed=8)
    parts = []
    for bi, tau in enumerate([4, 9, 16]):
        parts.append(f"tau={tau}: ates={len(r[bi]['fires'])} "
                     f"conc={r[bi]['conc']:.2f}")
    print("S2(%2) 3-bant: " + " | ".join(parts))


def exp9_group_vs_single():
    print("\n=== DENEY 9: grup vs tek-uye (S2 %2, D kaydirma) ===")
    errs_single, errs_group = [], []
    for d in [0, 2, 4, 6, 8, 10]:
        wire = make_wire([4, 12], 2400, [2, d], noise_p=0.02, amp_jit=0.2,
                         seed=90 + d)
        r = run_pop([12], wire, seed=9)
        g = r[0]
        base_off = 0  # ayni D'de tek-uye merkezleri dagilimi olculur
        singles = [circ_center(f, 12) for f in g["per_member"] if f]
        singles = [s for s in singles if s is not None]
        if len(singles) > 1:
            ang = 2 * np.pi * (np.array(singles) / 12)
            rbar = abs(np.exp(1j * ang).mean())
            spread = float(np.sqrt(-2 * np.log(max(rbar, 1e-9))) / (2 * np.pi) * 12)
        else:
            spread = 0.0
        errs_single.append(spread)
        errs_group.append(0.0)  # grup tek merkez verir; karsilastirma yayilim
        print(f"D12={d}: grup_merkez={g['center']:.2f} conc={g['conc']:.2f} "
              f"uye_yayilimi={spread:.2f} tick (n={len(singles)})")
    print(f"ortalama uye yayilimi={np.mean(errs_single):.2f} tick; "
          "grup tek-merkez kestirimi bu yayilimin ortalamasidir")


def hit_rate(fires, tau, delay, tol=1):
    """Ateslerin kendi ritim izgarasina (+-tol tick) isabet orani."""
    if not fires:
        return 0.0
    ok = sum(1 for t in fires if abs(wrap_err(t, delay, tau)) <= tol)
    return ok / len(fires)


def coverage(fires, tau, delay, T, tol=2):
    """Kendi darbelerinin kacinda +-tol icinde ates var."""
    if T <= 0:
        return 0.0
    pulses = [t for t in range(T) if (t - delay) % tau == 0 and t >= delay]
    if not pulses:
        return 0.0
    fs = set(fires)
    ok = sum(1 for p in pulses
             if any((p + o in fs) for o in range(-tol, tol + 1)))
    return ok / len(pulses)


def exp10_hit_metrics():
    print("\n=== DENEY 10: isabet-orani metrigi (hit rate + coverage) ===")
    for taus, delays, T in [([4, 12], [0, 0], 2000),
                            ([4, 9], [0, 0], 3600),
                            ([4, 9, 16], [0, 3, 7], 3600)]:
        wire = make_wire(taus, T, delays)
        r = run_pop(taus, wire, seed=10)
        for bi, tau in enumerate(taus):
            f = r[bi]["fires"]
            print(f"taus={taus} tau={tau}: hit={hit_rate(f, tau, delays[bi]):.2f} "
                  f"cov={coverage(f, tau, delays[bi], T):.2f} "
                  f"conc={r[bi]['conc']:.2f} ates={len(f)}")


def exp11_bw_coprime():
    print("\n=== DENEY 11: bw=1 vs 2, asal cift {4,9} (yabanci-kabul sayimi) ===")
    wire = make_wire([4, 9], 3600, [0, 0])
    for bw in [1, 2]:
        r = run_pop([4, 9], wire, bw=bw, n_pop=4, leak_jitter=0.0, seed=11)
        for bi, tau in enumerate([4, 9]):
            f = r[bi]["fires"]
            print(f"bw={bw} tau={tau}: hit={hit_rate(f, tau, 0):.2f} "
                  f"conc={r[bi]['conc']:.2f} ates={len(f)}")


def exp12_lock_short_gap():
    print("\n=== DENEY 12: LOCK ayirt-etme (kisa bosluk 20 tick) ===")
    for gaplen in [20, 60]:
        wire = make_wire([12], 1200, [0], gap=(500, 500 + gaplen))
        row = []
        for ll in [12, 26, 36]:
            r = run_pop([12], wire, n_pop=4, seed=12, lock_lost=ll)
            post = [f for f in r[0]["fires"] if f > 500 + gaplen]
            # ilk yeniden-kilit gecikmesi: bosluk bitiminden ilk atese
            boot = (min(post) - (500 + gaplen)) if post else -1
            row.append(f"LOCK={ll}: bootsuz_at={len(post)} ilk_ates_gecikme={boot}")
        print(f"bosluk={gaplen}: " + " | ".join(row))


def exp13_fastband_dshift():
    print("\n=== DENEY 13: HIZLI bant D-kaydirma (tau=4, delays=[d,0]) ===")
    base = run_pop([4], make_wire([4, 12], 2400, [0, 0]), seed=13)[0]["center"]
    for d in [0, 1, 2, 3]:
        wire = make_wire([4, 12], 2400, [d, 0])
        r = run_pop([4], wire, seed=13)[0]
        err = abs(wrap_err(r["center"] - base, d, 4))
        print(f"D4={d}: merkez={r['center']:.2f} kayma_hatasi={err:.2f} "
              f"hit={hit_rate(r['fires'], 4, d):.2f} conc={r['conc']:.2f}")
    print("--- asal ciftte YAVAS bant D-kaydirma (tau=9, delays=[0,d]) ---")
    base9 = run_pop([9], make_wire([4, 9], 3600, [0, 0]), seed=13)[0]["center"]
    for d in [0, 2, 4, 6]:
        wire = make_wire([4, 9], 3600, [0, d])
        r = run_pop([9], wire, seed=13)[0]
        err = abs(wrap_err(r["center"] - base9, d, 9))
        print(f"D9={d}: merkez={r['center']:.2f} kayma_hatasi={err:.2f} "
              f"hit={hit_rate(r['fires'], 9, d):.2f} conc={r['conc']:.2f}")


def exp14_stability():
    print("\n=== DENEY 14: merkez kararliligi (S2 %2, 6 tohum; grup vs tek-uye) ===")
    for tau, taus, delays in [(12, [4, 12], [2, 5]), (4, [4, 12], [2, 5])]:
        gcenters, mcenters = [], []
        for s in range(6):
            wire = make_wire(taus, 2400, delays, noise_p=0.02, amp_jit=0.2,
                             seed=140 + s)
            r = run_pop([tau], wire, seed=s)
            g = r[0]
            gcenters.append(g["center"])
            for f in g["per_member"]:
                c = circ_center(f, tau)
                if c is not None:
                    mcenters.append(c)
        ga = np.array(gcenters)
        g_rbar = abs(np.exp(1j * 2 * np.pi * ga / tau).mean())
        g_std = float(np.sqrt(-2 * np.log(max(g_rbar, 1e-9)))) / (
            2 * np.pi) * tau
        ma = np.array(mcenters)
        m_rbar = abs(np.exp(1j * 2 * np.pi * ma / tau).mean())
        m_std = float(np.sqrt(-2 * np.log(max(m_rbar, 1e-9)))) / (
            2 * np.pi) * tau
        print(f"tau={tau}: grup-merkez dagilimi={g_std:.2f} tick "
              f"tek-uye dagilimi={m_std:.2f} tick")


def exp15_timing_jitter():
    print("\n=== DENEY 15: zaman-jitter (+-1 tick) bw=1 vs 2 ===")
    rng = np.random.default_rng(150)
    for bw in [1, 2]:
        for taus, delays in [([4, 12], [0, 0]), ([4, 9], [0, 0])]:
            T = 2400
            wire = np.zeros(T)
            for bi, tau in enumerate(taus):
                for t in range(T):
                    if (t - delays[bi]) % tau == 0 and t >= delays[bi]:
                        tj = t + int(rng.integers(-1, 2))
                        if 0 <= tj < T:
                            wire[tj] += 0.8
            r = run_pop(taus, wire, bw=bw, n_pop=4, leak_jitter=0.0, seed=15)
            parts = []
            for bi, tau in enumerate(taus):
                f = r[bi]["fires"]
                parts.append(f"tau={tau}: hit={hit_rate(f, tau, delays[bi]):.2f} "
                             f"conc={r[bi]['conc']:.2f}")
            print(f"bw={bw} taus={taus}: " + " | ".join(parts))


def exp16_midgap_noise():
    print("\n=== DENEY 16: bant-ortasi gurultu darbesi, LOCK karari ===")
    # 12'lik izgara + her periyotta ortaya tek yabanci darbe (+6)
    T = 1200
    wire = np.zeros(T)
    for t in range(T):
        if t % 12 == 0:
            wire[t] += 0.8
        if t % 12 == 6:
            wire[t] += 0.8
    for ll in [12, 26, 38]:
        r = run_pop([12], wire, n_pop=4, leak_jitter=0.0, seed=16,
                    lock_lost=ll)
        f = r[0]["fires"]
        print(f"LOCK={ll}: hit={hit_rate(f, 12, 0):.2f} conc={r[0]['conc']:.2f} "
              f"ates={len(f)}")


def exp17_bw1_confirm():
    print("\n=== DENEY 17: bw=1 konfirme (S1+S2, tum senaryolar) ===")
    cfgs = [("S1 4+12", [4, 12], [0, 0], 2000, {}),
            ("S2 4+12", [4, 12], [0, 0], 2400,
             {"noise_p": 0.02, "amp_jit": 0.2, "seed": 170}),
            ("S1 4+9", [4, 9], [0, 0], 3600, {}),
            ("S2 4+9", [4, 9], [0, 0], 3600,
             {"noise_p": 0.02, "amp_jit": 0.2, "seed": 171}),
            ("S1 4+9+16", [4, 9, 16], [0, 3, 7], 3600, {})]
    for name, taus, delays, T, kw in cfgs:
        wire = make_wire(taus, T, delays, **kw)
        r = run_pop(taus, wire, bw=1, seed=17)
        parts = []
        for bi, tau in enumerate(taus):
            f = r[bi]["fires"]
            c = r[bi]["center"]
            parts.append(f"tau={tau}: hit={hit_rate(f, tau, delays[bi]):.2f} "
                         f"cov={coverage(f, tau, delays[bi], T):.2f} "
                         f"conc={r[bi]['conc']:.2f} merkez={c:.2f}")
        print(f"{name}: " + " | ".join(parts))


def exp18_gap_noise_lock():
    print("\n=== DENEY 18: bosluk-ici gurultu (30 tick bosluk + ortada darbe) ===")
    T = 1200
    for ll in [12, 26, 38]:
        wire = np.zeros(T)
        for t in range(T):
            if t % 12 == 0 and not 480 <= t < 510:
                wire[t] += 0.8
        wire[495] += 0.8  # bosluk ortasinda yabanci darbe
        r = run_pop([12], wire, n_pop=4, leak_jitter=0.0, seed=18,
                    lock_lost=ll)
        f = r[0]["fires"]
        post = sorted(t for t in f if t >= 510)
        first = post[0] - 510 if post else -1
        resume_hits = sum(1 for t in post if t % 12 == 0 and t < 510 + 60)
        print(f"LOCK={ll}: ilk-ates-gecikme={first} "
              f"izgara-isabeti(60tickte)={resume_hits} "
              f"hit={hit_rate(f, 12, 0):.2f}")


def exp19_foreign_only():
    print("\n=== DENEY 19: yabanci-tek-bant kontrolu (capraz ates) ===")
    T = 2000
    for taus, delays, probe, pdelay in [([4], [0], 12, 0),
                                        ([12], [0], 4, 0),
                                        ([4], [0], 9, 0),
                                        ([9], [0], 4, 0)]:
        wire = make_wire(taus, T, delays)
        r = run_pop([probe], wire, bw=1, n_pop=4, leak_jitter=0.0, seed=19)
        f = r[0]["fires"]
        print(f"tel={taus} probe_tau={probe}: capraz_ates={len(f)} "
              f"(beklenen ~0)")


if __name__ == "__main__":
    exp1_root_cause()
    exp2_bw()
    exp3_lock()
    exp4_pulse()
    exp5_jitter_npop()
    exp6_noise()
    exp7_dshift()
    exp8_three_band()
    exp9_group_vs_single()
    exp10_hit_metrics()
    exp11_bw_coprime()
    exp12_lock_short_gap()
    exp13_fastband_dshift()
    exp14_stability()
    exp15_timing_jitter()
    exp16_midgap_noise()
    exp17_bw1_confirm()
    exp18_gap_noise_lock()
    exp19_foreign_only()
    print("\n=== MC TAMAMLANDI ===")
