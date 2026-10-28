"""MC-once: P2 olay akisi -> pre patlama adaptoru -> nedensellik (anayasa §0).

Ikiz cekirdek validate_causality'den aynen (Pre/Target/G/Q/S, kalibre
nokta: PULSE=0.8, w0=0.4, ETA=0.2, hedef leak=0.04). Tek yenilik ADAPTOR:
P2 atesi (yavas ritim, olculen kilitli ISI) pre tau'sunda KISA PATLAMAYA
cevrilir (hizli pre'ye BSA); olay ZAMANLAMASI korunur (patlama olay
tick'inde baslar).
Senaryo: X olay treni (periyot 35) + Y = X + LAG; F1 X-yalniz, F2
Y-yalniz, F3 X+Y. Kalibrasyon: LAG + patlama boylari (n0@tau4, n2@tau12).
Calistirma: python3 validate_causal_afferent.py
"""
import validate_causality as vc

PERIOD = 12
BLOCK = 1000
W0A, W1A = 40, 940
N_SUPER = 3
PULSE = 0.8
W0 = 0.4
ETA = 0.2
LEAKS = (0.06, 0.06, 0.02, 0.02)
TGT_LEAK = 0.04
WIN = vc.WIN
RW = vc.RATE_WINDOW


def trains(phase, lag):
    xs = list(range(W0A, W1A + 1, PERIOD))
    ys = [t + lag for t in xs if t + lag <= W1A]
    if phase == 0:
        return xs, []
    if phase == 1:
        return [], ys
    return xs, ys


def run_point(n0, n2, lag):
    pres = [vc.Pre(vc.TAUS[i], LEAKS[i]) for i in range(4)]
    tgt = vc.Target(TGT_LEAK)
    w = [W0] * 4
    branch = ["a", "a", "b", "b"]
    hist_pre = [[0] * RW for _ in range(4)]
    hist_post = [0] * RW
    head = 0
    fires = {0: 0, 1: 0, 2: 0}
    coinc = {0: 0, 1: 0, 2: 0}
    pf = {0: [0] * 4, 1: [0] * 4, 2: [0] * 4}
    pre_ev = {0: 0, 1: 0, 2: 0}  # faz basina P2 olay sayisi (1:1 izleme)
    pticks = {0: [], 2: []}  # ongorucu icin neden-kanal ates tick'leri
    t = 0
    for _ in range(N_SUPER):
        for ph in range(3):
            xs, ys = trains(ph, lag)
            # patlama cizelgesi (olay tick'i + pre-tau adimlari)
            sched = {}
            for e in xs:
                pre_ev[ph] += 1
                for j in range(n0):
                    sched.setdefault(e + 4 * j, []).append((0, PULSE))
            for e in ys:
                if ph != 1:
                    pre_ev[ph] += 0
                for j in range(n2):
                    sched.setdefault(e + 12 * j, []).append((2, PULSE))
            c0 = tgt.coinc_ticks
            for bt in range(BLOCK):
                for i, amp in sched.get(bt, []):
                    pres[i].pulse(t, amp)
                fired = [pr.tick(t) for pr in pres]
                for i, f in enumerate(fired):
                    if f:
                        tgt.inject(branch[i], t, w[i] * 0.5)
                        pf[ph][i] += 1
                        if i in pticks:
                            pticks[i].append(t)
                tf = tgt.tick(t)
                if tf:
                    fires[ph] += 1
                for i in range(4):
                    hist_pre[i][head] = 1 if fired[i] else 0
                hist_post[head] = 1 if tf else 0
                head = (head + 1) % RW
                rp = [sum(h) for h in hist_pre]
                rq = sum(hist_post)
                for i in range(4):
                    dw = ETA * vc.G(rp[i], rq) * vc.Q(rp[i], rq) * \
                        vc.S(w[i])
                    w[i] = min(vc.W_MAX, w[i] + dw)
                t += 1
            coinc[ph] += tgt.coinc_ticks - c0
    return {"fires": fires, "coinc": coinc, "w": w, "pre": pf,
            "events": pre_ev, "pticks": pticks}


SEL_LAG, SEL_N0, SEL_N2 = 8, 2, 2


def test_a1_contrast():
    # F3 (X+Y) atesler, tekliler susar; coincidence yalniz F3'te.
    r = run_point(SEL_N0, SEL_N2, SEL_LAG)
    f = r["fires"]
    assert f[0] == 0 and f[1] == 0, f"tekil faz susmali: {f}"
    assert f[2] >= 10, f"F3 ateslemeli: {f}"
    assert r["coinc"][0] + r["coinc"][1] == 0, "C1=C2=0 olmali"
    assert r["coinc"][2] > 0, "C3>>0 olmali"
    print(f"A1: F1={f[0]} F2={f[1]} F3={f[2]} coincF3={r['coinc'][2]} OK")


def test_a2_negatif():
    # s1/s3 hic uyarilmaz: ates 0 + agirlik donuk.
    r = run_point(SEL_N0, SEL_N2, SEL_LAG)
    for ph in range(3):
        assert r["pre"][ph][1] == 0 and r["pre"][ph][3] == 0, \
            "negatif pre ateslememeli"
    assert r["w"][1] == W0 and r["w"][3] == W0, "s1/s3 donuk olmali"
    print("A2: negatif kontrol (s1/s3 ates 0, w donuk) OK")


def test_a3_ogrenme():
    # s0/s2 F3'te buyur (coincidence ogrenmesi canli).
    r = run_point(SEL_N0, SEL_N2, SEL_LAG)
    assert r["w"][0] > W0 and r["w"][2] > W0, \
        f"s0/s2 buyumeli: {r['w']}"
    print(f"A3: w s0={r['w'][0]:.4f} s2={r['w'][2]:.4f} (w0={W0}) OK")


PRED_W = 16  # tahmin penceresi (LAG8 + pre ates gecikmesi payi)


def predict_mc(cause_ticks, y_times, window):
    active_until = -10**9
    last_c = -10**9
    windows = 0
    y_ev = 0
    pred_y = 0
    lead_sum = 0
    lead_n = 0
    ci = set(cause_ticks)
    for t in sorted(set(cause_ticks) | set(y_times)):
        if t in ci:
            if t > active_until:
                windows += 1
            active_until = t + window
            last_c = t
        if t in set(y_times):
            y_ev += 1
            if t <= active_until:
                pred_y += 1
                lead_sum += t - last_c
                lead_n += 1
    return {"windows": windows, "y": y_ev, "pred": pred_y,
            "lead": lead_sum / lead_n if lead_n else None}


def phase_y(ph, lag):
    # Global tick karsiligi: super s, faz ph -> [(s*3+ph)*BLOCK, ...].
    out = []
    for s in range(N_SUPER):
        base = (s * 3 + ph) * BLOCK
        _, ys = trains(ph, lag)
        out += [base + t for t in ys]
    return out


def phase_cause(pticks, ph):
    out = []
    for s in range(N_SUPER):
        lo = (s * 3 + ph) * BLOCK
        out += [t for t in pticks if lo <= t < lo + BLOCK]
    return out


def test_p1_recall():
    # F3: Y olaylarinin tamami ongorulmus olmali (hatirlatma).
    r = run_point(SEL_N0, SEL_N2, SEL_LAG)
    s = predict_mc(phase_cause(r["pticks"][0], 2),
                   phase_y(2, SEL_LAG), PRED_W)
    assert s["y"] > 0, "F3'te Y olmali"
    assert s["pred"] / s["y"] >= 0.95, f"recall dusuk: {s}"
    print(f"P1: F3 recall={s['pred']}/{s['y']} "
          f"({s['pred']/s['y']:.3f}) OK")


def test_p2_bos_dunya():
    # F1: tahminler acilir (mekanizma calisir) ama Y gelmez (dunya sessiz).
    r = run_point(SEL_N0, SEL_N2, SEL_LAG)
    s = predict_mc(phase_cause(r["pticks"][0], 0), phase_y(0, SEL_LAG),
                   PRED_W)
    assert s["windows"] > 0, "F1'de tahmin acilmali"
    assert s["y"] == 0 and s["pred"] == 0, \
        "F1'de Y yok, isabet de yok"
    print(f"P1b: F1 pencere={s['windows']}, Y=0 (bos-dunya gozlemi) OK")


def test_p3_lead():
    # Tahmin etkiyi ONCEDEN yakalar (lead pozitif + pencere-ici).
    r = run_point(SEL_N0, SEL_N2, SEL_LAG)
    s = predict_mc(phase_cause(r["pticks"][0], 2),
                   phase_y(2, SEL_LAG), PRED_W)
    assert s["lead"] is not None and 1 <= s["lead"] <= PRED_W, \
        f"lead pencere-disi: {s['lead']}"
    print(f"P3: ortalama lead={s['lead']:.2f} tick (pencere {PRED_W}) OK")


if __name__ == "__main__":
    test_a1_contrast()
    test_a2_negatif()
    test_a3_ogrenme()
    test_p1_recall()
    test_p2_bos_dunya()
    test_p3_lead()
    print("validate_causal_afferent: A1-A3 + P1-P3 OK")
    for lag in (5, 8):
        for n0, n2 in ((2, 2), (3, 2)):
            assert (n0 - 1) * 4 <= PERIOD and (n2 - 1) * 12 <= PERIOD, \
                "patlama sinirda bitebilir (birikimli cakis tutarli)"
            r = run_point(n0, n2, lag)
            f = r["fires"]
            base = f[0] + f[1]
            ratio = f[2] / base if base else float("inf")
            nev = sum(r["events"][ph] for ph in (0, 1, 2)) // 3 or 1
            print(f"LAG={lag} n0={n0} n2={n2}: F1={f[0]} F2={f[1]} "
                  f"F3={f[2]} oran={ratio:.2f} coinc={r['coinc']} "
                  f"preF3={r['pre'][2]} w={[round(x, 4) for x in r['w']]}")
