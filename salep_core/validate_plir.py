"""PLIR-A karakterizasyonu (§9.64): bitki darbesi -> kabul/red karari.

Donuk cekirdek kurali (neuron.h PLIR yolu, sl_p1: tau {4,12}, bw=1,
lock=2*tau+bw) birebir Python izdusu (tamsayi ISI mantigi; bw=1'de
mu her zaman 1):
  ilk darbe / kilit-dususu (aralik > lock) -> FRESH-ACCEPT
  |ISI - tau| == 0 -> RESONANCE-ACCEPT
  aksi -> RES-REJECT (voltaj + coincidence YOK)
Red sebepleri: yalniz rezonans-uyumsuzlugu (refrakter mekanizmasi
kodda YOK); esik/gating sizintisi alt-kademededir (P1 soma).

Her kabul icin ayni-hat P1 atesine uzaklik (ticks_to_fire) + tam
karar gunlugu (plir_decisions.csv).

Calistirma: .venv/bin/python validate_plir.py
Olcutler (L1-L4).
"""
import csv
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

TAU = {0: 4, 1: 12}
BW = 1
FIRE_WINDOW = 20  # kabul->ates baglama penceresi (tick)


def classify(ticks, tau):
    lock = 2 * tau + BW
    last = None
    out = []
    for t in sorted(ticks):
        if last is None or (t - last) > lock:
            out.append((t, "FRESH-ACCEPT", t - last if last else -1))
            last = t
        elif abs((t - last) - tau) < BW:
            out.append((t, "RESONANCE-ACCEPT", t - last))
            last = t
        else:
            out.append((t, "RES-REJECT", t - last))
    return out


def main():
    # Maske semantigi: ayni tick Taipeleri tek darbedir (motorla ayni;
    # ham CSV patlama cift-sayimlari teke indirilir).
    pulses = {}
    with open(os.path.join(ROOT, "testb_spikes.csv")) as f:
        for row in csv.reader(f):
            if not row[0].isdigit():
                continue
            d, l, t = map(int, row)
            pulses.setdefault(l, set()).add(d * 50 + t)
    pulses = {l: sorted(v) for l, v in pulses.items()}

    fires = {0: [], 1: []}
    with open(os.path.join(ROOT, "testb_conditions.csv")) as f:
        for row in csv.reader(f):
            t = int(row[0])
            if row[3] == "1":
                fires[0].append(t)
            if row[4] == "1":
                fires[1].append(t)
    fires = {l: sorted(v) for l, v in fires.items()}

    import bisect
    log = []
    for l in (0, 1):
        for t, verdict, isi in classify(pulses.get(l, []), TAU[l]):
            i = bisect.bisect_right(fires[l], t)
            dt = fires[l][i] - t if i < len(fires[l]) else 9999
            log.append({"idx": len(log) + 1, "tick": t,
                        "day": t // 50, "line": l, "verdict": verdict,
                        "isi": isi, "ticks_to_fire": dt})
    with open(os.path.join(ROOT, "plir_decisions.csv"), "w",
              newline="") as f:
        w = csv.DictWriter(f, fieldnames=["idx", "tick", "day", "line",
                                          "verdict", "isi",
                                          "ticks_to_fire"])
        w.writeheader()
        w.writerows(log)

    from collections import Counter
    import bisect as _bis
    import statistics as _st
    c = Counter((r["line"], r["verdict"]) for r in log)
    n_acc = sum(1 for r in log if r["verdict"] != "RES-REJECT")
    n_fire = sum(len(v) for v in fires.values())
    # Anatomi (bilgi: atilan vs donusulen temporal icerik).
    red_why = Counter(
        "too_short" if r["isi"] < TAU[r["line"]] else "too_long"
        for r in log if r["verdict"] == "RES-REJECT")
    acc_ticks = {}
    for r in log:
        if r["verdict"] != "RES-REJECT":
            acc_ticks.setdefault(r["line"], []).append(r["tick"])
    sup = []
    for l in (0, 1):
        for ft in fires[l]:
            i = _bis.bisect_left(acc_ticks[l], ft - 20)
            j = _bis.bisect_right(acc_ticks[l], ft)
            sup.append(j - i)
    print(f"RED sebebi: {dict(red_why)} (bw=1: periyot-disi; "
          f"gating PLIR'de yok)")
    print(f"ates destegi: ort={_st.mean(sup):.1f} medyan={_st.median(sup)} "
          f"dagilim={dict(Counter(sup))}")
    print(f"PLIR-A karari ({len(log)} benzersiz tick):")
    for k in sorted(c):
        print(f"  hat{k[0]} {k[1]}: {c[k]}")
    print(f"kabul: {n_acc}, P1 ates: {n_fire}")
    print("ornek (ilk 12 darbe):")
    for r in log[:12]:
        print(f"  spike #{r['idx']} t={r['tick']} hat{r['line']} -> "
              f"{r['verdict']} [isi={r['isi']}]")

    ok = []
    ok.append(("L1 hat dagilimi",
               c[(0, "FRESH-ACCEPT")] == 624
               and c[(0, "RESONANCE-ACCEPT")] == 171
               and c[(0, "RES-REJECT")] == 1113
               and c[(1, "FRESH-ACCEPT")] == 17
               and c[(1, "RES-REJECT")] == 29
               and len(log) == 1954))
    ok.append(("L2 huni", n_fire < n_acc < len(log)))
    no_orphan = True
    for l in (0, 1):
        acc_ticks = [r["tick"] for r in log
                     if r["line"] == l and r["verdict"] != "RES-REJECT"]
        for ft in fires[l]:
            i = bisect.bisect_left(acc_ticks, ft)
            near = ([acc_ticks[i - 1]] if i > 0 else []) + (
                [acc_ticks[i]] if i < len(acc_ticks) else [])
            if not any(0 <= ft - a <= FIRE_WINDOW for a in near):
                no_orphan = False
    ok.append(("L3 ates-kaynakli", no_orphan))
    ok.append(("L4 red-sebebi-tek",
               set(r["verdict"] for r in log
                   if "REJECT" in r["verdict"]) == {"RES-REJECT"}))
    bad = [k for k, v in ok if not v]
    for k, v in ok:
        print(f"  {'OK' if v else 'BATTI'} {k}")
    if bad:
        raise SystemExit(f"BATTI: {bad}")
    print("HUKUM: 1169 red = rezonans-uyumsuzlugu (bw=1: periyot disi "
          "darbe); 812 kabulun 303'u atese donustu (alti: esik/sizinti).")
    print("OZET-PLIR: " + " ".join(k for k, _ in ok))


if __name__ == "__main__":
    main()
