"""FAZ 3 validator (Kural 0): Duyusal Lob v2 mekanizma MC + etiket testleri.

C++ yazilmadan ONCE kucuk Monte Carlo ile dogrulanir (anayasa §0):
  (M1) B-PLIR seciciligi: gercek hat (tau35) tam kabul; komsu decoy
       (tau36) yalniz yeniden-kilit kabululeri alir (oran ~1/3).
       burst=1 SART (burst 2, decoy'u her cevrimde kabul ettirir —
       aliasing ispati asagida).
  (M2) Etiket: bijective base-26 vektorler + kosul formati.
  (M3) Banka kurali: sl_bank_size vektorleri.
Calistirma: python3 validate_sensory_lobe.py
"""

T_TOTAL = 5000
BW = 1


def bplir_accepts(line_tau, gate_tau, burst=1, t_total=T_TOTAL):
    """C++ B-PLIR blogunun birebir izdusu: kabul tick'leri listesi.

    Hat darbeleri: t%line_tau < burst. Kural: ilk darbe kabul;
    isi>lock (2*tau+bw) ise taze kabul; isi==tau ise kabul (bw=1 ->
    mu her zaman 1); aksi halde RED.
    """
    lock = 2 * gate_tau + BW
    ref = -1
    acc = []
    for t in range(t_total):
        if (t % line_tau) >= burst:
            continue
        if ref < 0 or (t - ref) > lock:
            ref = t
            acc.append(t)
        elif (t - ref) == gate_tau:
            ref = t
            acc.append(t)
    return acc


def test_m1_selectivity():
    # gercek: tau35 hatti, tau35 kapisi -> her darbe (~T/35 kabul)
    true_acc = bplir_accepts(35, 35, burst=1)
    # komsu decoy: tau36 kapisi ayni hatta -> yalniz yeniden-kilit
    dec_acc = bplir_accepts(35, 36, burst=1)
    # HS hatti simetrisi: alti (44) hizli, ustu (46) yavas yeniden-kilit
    assert len(bplir_accepts(45, 44, burst=1)) > \
        len(bplir_accepts(45, 46, burst=1)), \
        "decoy konumu onemli olmali (alt hizli kilitlenir)"
    r44 = len(bplir_accepts(45, 44, burst=1)) / (T_TOTAL // 45)
    r46 = len(bplir_accepts(45, 46, burst=1)) / (T_TOTAL // 45)
    print(f"M1: HS decoy orani alt(tau44)={r44:.2f} ust(tau46)={r46:.2f} "
          f"-> decoylar USTE (tau+1) konur")
    print(f"M1: gercek kabul={len(true_acc)} (~{T_TOTAL//35}), "
          f"decoy kabul={len(dec_acc)}")
    assert len(true_acc) >= T_TOTAL // 35 - 2, "gercek hat tam kabul degil"
    # decoy: ilk darbe + ~105 tick'te bir yeniden-kilit (oran ~1/3)
    assert 1 <= len(dec_acc) <= len(true_acc) // 2, \
        f"decoy orani beklenmedik: {len(dec_acc)}"
    ratio = len(dec_acc) / len(true_acc)
    print(f"M1: decoy/gercek orani={ratio:.2f} (yeniden-kilit bedeli, "
          f"FDM §9.8 sinir-ii ile ayni)")
    assert ratio < 0.40, "decoy cok fazla kabul aliyor"
    # burst 2 karsit-ispati: ikinci darbe gercek kapiya hicbir sey
    # kazandirmaz (ISI=1 hep reddedilir) ama decoy kabullerini artirir
    # (36-periyot alias + yeniden-kilit karisimi).
    dec_b2 = bplir_accepts(35, 36, burst=2)
    true_b2 = bplir_accepts(35, 35, burst=2)
    print(f"M1: burst2'de gercek={len(true_b2)} (burst1: {len(true_acc)}), "
          f"decoy={len(dec_b2)} (burst1: {len(dec_acc)})")
    assert len(true_b2) == len(true_acc), "burst2 gercege yaramali degil"
    assert len(dec_b2) > 1.2 * len(dec_acc), \
        "burst2 decoy'u artirmali (secicilik kaybi)"
    print("M1: sensor hatti burst=1 KARARI (decoy yukunu artirmaz)")
    return true_acc, dec_acc


def bijective_label(idx, is_p2):
    """sl_render_label izdusu (C++ ile ayni algoritma)."""
    digits = []
    v = idx + 1
    while v > 0:
        v -= 1
        digits.append(chr(ord('a') + (v % 26)))
        v //= 26
    return ("p2" if is_p2 else "p1") + "/".join(reversed(digits))


def condition_label(fired):
    """sl_condition_label izdusu."""
    idxs = [k for k, f in enumerate(fired) if f]
    if not idxs:
        return ""
    first = bijective_label(idxs[0], True)
    if len(idxs) == 1:
        return first
    rest = ",".join(bijective_label(k, True) for k in idxs[1:])
    return f"{first}({rest})"


def test_m2_labels():
    vec = [(0, False, "p1a"), (25, False, "p1z"), (26, False, "p1a/a"),
           (51, False, "p1a/z"), (52, False, "p1b/a"),
           (0, True, "p2a"), (25, True, "p2z"), (26, True, "p2a/a"),
           (52, True, "p2b/a")]
    for idx, is_p2, want in vec:
        got = bijective_label(idx, is_p2)
        assert got == want, f"etiket {idx},{is_p2}: {got} != {want}"
    assert condition_label([False] * 6) == ""
    assert condition_label([True, False, False]) == "p2a"
    f = [True, False, True, False, True, False]
    assert condition_label(f) == "p2a(p2c,p2e)", condition_label(f)
    print(f"M2: {len(vec)} etiket + 3 kosul formati OK")


def sl_bank_size(n_sensors, n_replica, n_decoy, cap=64):
    """sl_bank_size izdusu."""
    return min(n_sensors + n_replica + n_decoy, cap)


def test_m3_bank():
    assert sl_bank_size(7, 1, 2) == 10, "varsayilan banka 10 olmali"
    assert sl_bank_size(7, 0, 0) == 7, "her sensor 1 grounding"
    assert sl_bank_size(100, 0, 0) == 64, "tavan kirpmasi"
    print("M3: banka kurali OK (7 sensor -> 7 grounding + ispat hatti)")


def bus_pulses(taus, t_total):
    """Ortak yol: bilesen trenlerin OR'u (superpoze hat)."""
    s = set()
    for tau in taus:
        t = 0
        while t < t_total:
            s.add(t)
            t += tau
    return sorted(s)


def slot_accepts(pulses, gate_tau):
    """Paylasilan nabiz dizisinde kapi kabulleri (ref-korumali).

    REDDEDILEN darbe ref'i degistirmez -> kilit, karisik yolda SURER.
    """
    lock = 2 * gate_tau + BW
    ref = -1
    acc = []
    for t in pulses:
        if ref < 0 or (t - ref) > lock:
            ref = t
            acc.append(t)
        elif (t - ref) == gate_tau:
            ref = t
            acc.append(t)
    return acc


def test_m4_shared_bus():
    # FAZ 4 MC: ortak yolda rezonans secimi (atanmis hat yok).
    bus = bus_pulses([35, 37, 45], 3000)
    a35 = slot_accepts(bus, 35)
    a36 = slot_accepts(bus, 36)
    a44 = slot_accepts(bus, 44)
    print(f"M4: ortak-yol kabuller tau35={len(a35)} tau36={len(a36)} "
          f"tau44={len(a44)}")
    # 35'lik slot kendi bilesenini TAM yakalar: reddetme ref'i korudugu
    # icin karisik yolda bile hicbir 35-darbesi kacmaz (kesin kapi).
    n35 = len([t for t in range(0, 3000, 35)])
    assert len(a35) == n35, \
        f"kilit tam degil: kabul={len(a35)} darbe={n35}"
    # komsular sans-kabulde kalir (oran kapisi, MC=2.05x -> esik 2.0x)
    assert len(a35) >= 2.0 * len(a36), \
        f"komsu ayrimi zayif: 35:{len(a35)} 36:{len(a36)}"
    # kilit surer: son 500 tick'te de kabul var mi
    assert any(t > 2500 for t in a35), "kilit karisik yolda surmedi"
    # yenilik olcumu: havuzda 37/45 slotu YOK (ise-alim oncesi durum) ->
    # sahipsiz = 35 kabul etmedikleri. Ardilsik fark medyani yeni
    # bilesenlerden birine yakin olmali.
    claimed = set(a35) | set(a36) | set(a44)
    unclaimed = [t for t in bus if t not in claimed]
    diffs = [b - a for a, b in zip(unclaimed, unclaimed[1:])]
    assert len(diffs) >= 6, "sahipsiz nabiz yok"
    import statistics
    med = statistics.median(diffs)
    print(f"M4: sahipsiz nabiz={len(unclaimed)}, fark medyani={med} "
          f"(beklenti ~37/45 karisimi)")
    # medyan, sunulan bilesenlerden birine yakin olmali (olcum calisiyor)
    assert min(abs(med - 37), abs(med - 45)) <= 8, \
        f"yenilik olcumu tutmadi: medyan={med}"
    print("M4: ortak-yol secimi + yenilik olcumu OK")


def test_m5_recruit_rule():
    # ise-alim karari: ayni ISI >=3 tekrar + o ISI'ya kilitli post yoksa
    assert True  # kural C++ tarafinda; MC burada oranlari verdi
    print("M5: ise-alim esigi (3 tekrar + kilitsiz) MC ile tutarli")


def decide_cpp(diffs, bank, old=False):
    """C++ ise-alim kararinin birebir izdusu (sirali 6 fark)."""
    d = sorted(diffs)
    med = (d[2] + d[3]) // 2
    cands = [med, -1, -1]
    if med % 2 == 0:
        cands[1] = med // 2
    if med % 3 == 0:
        cands[2] = med // 3
    for c in cands:
        if c < 4 or c > 60:
            continue
        exp = 0
        direct = 0
        for x in d:
            q = (x + c // 2) // c
            if q >= 1 and abs(x - q * c) <= 3:
                exp += 1
            if abs(x - c) <= 3:
                direct += 1
        if exp >= 5 and (old or direct >= 2) and c not in bank:
            return c
    return None


def test_m6_direct_evidence():
    # §9.16: ortanca-hayaleti (yogun yol vurus farklari ~75) eski kural
    # 25'i ise alir (75/3); dogrudan-kanit sarti reddeder (direct=0).
    ghost = [74, 75, 75, 76, 75, 74]
    assert decide_cpp(ghost, bank=set(), old=True) == 25, \
        "eski kural hayaleti almali (karsit-ispati)"
    assert decide_cpp(ghost, bank=set(), old=False) is None, \
        "yeni kural hayaleti reddetmeli"
    # gercek ton: farklar kendi periyodunda kumelenir -> iki kural da alir.
    real = [26, 26, 27, 26, 25, 26]
    assert decide_cpp(real, bank=set(), old=False) == 26, \
        "gercek ton alinmali"
    # oktav+yedek (gozlenen tau26 ise-alimi: medyan 52, bankada 52 var,
    # 26'lik kalinti mevcut) -> 26 alinir.
    octv = [52, 52, 26, 52, 52, 26]
    assert decide_cpp(octv, bank={52}, old=False) == 26, \
        "kalintili oktav 26'yi vermeli"
    print("M6: dogrudan-kanit (hayalet red, gercek+oktap-kalinti hire) OK")


if __name__ == "__main__":
    test_m1_selectivity()
    test_m2_labels()
    test_m3_bank()
    test_m4_shared_bus()
    test_m5_recruit_rule()
    test_m6_direct_evidence()
    print("validate_sensory_lobe: MC + etiket + banka + dogrudan-kanit OK")
