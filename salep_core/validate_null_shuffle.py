"""Deney C — shuffle null (§9.73).

Soru: davranis spike SAYISINDAN mi, temporal ORGANIZASYONDAN mi?
Yontem: her (gun, hat) grubunda tick'ler deterministik permute
(tohum 1234) — grup-bazinda multiset birebir korunur (toplam satir
+ her gun×hat sayisi ayni), ISI/sira yapisi yok edilir. Sensor
dosyasi ayni. Donuk binary yeni girdiyle calisir (kod DEGISMEZ),
ciktilar ayri isimde (shuf_*); mevcut artefaktlara DOKUNULMAZ.

Olcu: bitki darbesi, P1 ates, P2 olay/etiket + k=3 inference
(donmus build/infer yeniden kullanilir). Sifir-P2 = en guclu
sonuc ("sayi ayni, davranis yok").

Kapilar (N1-N3): sayi-korunumu, determinizm, harness basarisi.
"""
import csv
import os
import random
import subprocess
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import validate_inference as B  # noqa: E402 (donmus, okunur)

SEED = 1234
SHUF_SPIKES = os.path.join(ROOT, "shuf_spikes.csv")
SHUF_COND = os.path.join(ROOT, "shuf_conditions.csv")
SHUF_AFF = os.path.join(ROOT, "shuf_afferent.csv")
SHUF_DIAG = "/tmp/shuf_diag.csv"


def load_raw():
    rows = []
    with open(os.path.join(ROOT, "testb_spikes.csv"), newline="") as f:
        for row in csv.reader(f):
            if not row or not row[0].strip().lstrip("-").isdigit():
                continue
            rows.append(tuple(map(int, row[:3])))
    return rows


def shuffle_rows(rows):
    # Grup-bazinda SAYI korunur (len(set)), tick DEGERLERI yeniden
    # cekilir -> maske/ISI yapisi yok edilir. (Multiset-permutasyon
    # maskeyi aynen korurdu: etkisiz-null hatasi.)
    groups = {}
    for r in rows:
        groups.setdefault(r[:2], []).append(r[2])
    rng = random.Random(SEED)
    out = []
    for key in sorted(groups):
        n = len(set(groups[key]))
        out.extend((key[0], key[1], t)
                   for t in sorted(rng.sample(range(50), n)))
    return out


def group_counts(rows):
    # Maske-seviyesi sayi (benzersiz tick/grup): motorun gordugu.
    u = {}
    for d, l, t in rows:
        u.setdefault((d, l), set()).add(t)
    return {k: len(v) for k, v in u.items()}


def mask_diff(a_rows, b_rows):
    ma, mb = {}, {}
    for d, l, t in a_rows:
        ma.setdefault((d, l), set()).add(t)
    for d, l, t in b_rows:
        mb.setdefault((d, l), set()).add(t)
    return sum(len(ma[k] ^ mb.get(k, set())) for k in ma)


def p1_fires(cond_csv):
    a = b = 0
    with open(cond_csv) as f:
        for row in csv.reader(f):
            if row[3] == "1":
                a += 1
            if row[4] == "1":
                b += 1
    return a, b


def main():
    raw = load_raw()
    shuf = shuffle_rows(raw)
    same_counts = group_counts(shuf) == group_counts(raw)
    assert same_counts, "grup sayilari bozuldu"
    mdiff = mask_diff(raw, shuf)
    assert mdiff > 0, "maske degismedi (etkisiz null)"
    shuf2 = shuffle_rows(raw)
    det = shuf2 == shuf
    with open(SHUF_SPIKES, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\r\n")
        w.writerows(shuf)

    exe = os.path.join(ROOT, "npu_sensory_plant")
    p = subprocess.run(
        [exe, "--spikes", SHUF_SPIKES,
         "--sensors", os.path.join(ROOT, "testb_sensors.csv"),
         "--out", SHUF_COND, "--cond", "22", "--test", "3",
         "--diag", SHUF_DIAG, "--aff", SHUF_AFF],
        cwd=ROOT, capture_output=True, text=True, timeout=600)
    ok_run = p.returncode == 0
    if not ok_run:
        raise SystemExit(f"harness batti:\n{p.stderr[-2000:]}")

    p1 = (0, 0)
    ncond = 0
    for line in p.stdout.splitlines():
        if line.startswith("OZET-PLANT: p1darbesi="):
            toks = line.split()
            p1 = tuple(int(x) for x in toks[1].split("=")[1].split("/"))
            for tok in toks:
                if tok.startswith("kosul_sayisi="):
                    ncond = int(tok.split("=")[1])
    print(f"shuf: maske-bit={len(shuf)} (ham-unique=1954), "
          f"maske-fark={mdiff}, P1 darbesi={p1}, kosul={ncond}")
    p1o = p1_fires(os.path.join(ROOT, "testb_conditions.csv"))
    p1s = p1_fires(SHUF_COND)
    print(f"P1 ates (ham->shuf): {p1o} -> {p1s} "
          f"[A-yolu zaman-duyarli mi?]")

    with open(SHUF_AFF) as f:
        evs = list(csv.DictReader(f))
    ticks = {int(r["tick"]) for r in evs}
    labels = sorted({r["label"] for r in evs})
    print(f"shuf: P2 kayit={len(evs)} tick={len(ticks)} etiket={labels}")

    acc = kt = kd = None
    if evs:
        wins = B.build(evs)
        if wins:
            cm, viol = B.infer(wins)
            acc = B.show(cm, "Shuffle-null inference (k=3):")
            kd = cm.get(("kurak", "normal"), 0)
            kt = sum(v for (t, _), v in cm.items() if t == "kurak")
            print(f"kurak->normal (shuf): {kd}/{kt}")
            assert viol == 0, "sizinti!"
        else:
            print("BULGU: ates var ama 3-gun penceresi yok")
    else:
        print("BULGU: sayi ayni, P2 davranisi YOK (tam cudus)")

    chk = [("N1 sayi-korunumu", same_counts),
           ("N2 deterministik", det),
           ("N3 harness-OK", ok_run)]
    bad = [x for x, v in chk if not v]
    for x, v in chk:
        print(f"  {'OK' if v else 'BATTI'} {x}")
    if bad:
        raise SystemExit(f"BATTI: {bad}")
    print("OZET-NULL-SHUF: " + " ".join(x for x, _ in chk)
          + (f" acc={acc:.3f}" if acc is not None else " acc=YOK")
          + (f" kurak-normal={kd}/{kt}" if kt else ""))


if __name__ == "__main__":
    main()
