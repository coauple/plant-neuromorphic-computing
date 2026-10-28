"""Association izlenebilirligi (§9.61): afferent kablo + geriye-iz.

Kablo: AfferentEvent{tick, post_id, tau_b} + baglam (a0lag/a1lag =
P1 son-ates gecikmesi, pencere-disi -1; bmask = o tick B paterni;
label = kosul; w = ates-an agirligi). persistence'a DOKUNULMAZ.

Geriye-iz zinciri: A aktifti -> hangi B paterni -> hangi P2 dizisi ->
hangi kosul -> sonuc (w).

Calistirma: .venv/bin/python validate_assoc_trace.py
Olcutler (T1-T4): kablo butunlugu, A-topraklama (diag capraz),
tau_b butunlugu, her kosulda geriye-iz.
"""
import csv
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

BANK_TAU = {0: 35, 1: 45, 2: 35, 3: 36, 4: 46, 5: 26, 6: 37, 7: 37,
            8: 37, 9: 37}
COND_POSTS = ("p2a", "p2b", "p2c", "p2d", "p2e", "p2f", "p2g", "p2h",
              "p2i", "p2j")
WINDOW = 10


def run_all():
    exe = os.path.join(ROOT, "npu_sensory_plant")
    aff = os.path.join(ROOT, "testb_afferent.csv")
    p = subprocess.run(
        [exe, "--spikes", os.path.join(ROOT, "testb_spikes.csv"),
         "--sensors", os.path.join(ROOT, "testb_sensors.csv"),
         "--out", "/tmp/at_cond.csv", "--cond", "22", "--test", "3",
         "--diag", "/tmp/at_diag.csv", "--aff", aff],
        cwd=ROOT, capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        raise SystemExit(f"harness batti:\n{p.stderr[-2000:]}")
    return aff


def main():
    aff = run_all()
    cable = list(csv.DictReader(open(aff)))
    diag = list(csv.DictReader(open("/tmp/at_diag.csv")))
    assert cable, "T1 BATTI: kablo bos"
    print(f"kablo: {len(cable)} kayit")

    # T1: conditions CSV'deki her ates kayitta birebir var.
    cond = list(csv.reader(open(os.path.join(ROOT,
                                             "testb_conditions.csv"))))
    want = {}
    for row in cond:
        t = int(row[0])
        bits = row[5]
        for k, ch in enumerate(bits[:10]):
            if ch == "1":
                want.setdefault(t, set()).add(k)
    got = {}
    for r in cable:
        got.setdefault(int(r["tick"]), set()).add(int(r["post_id"]))
    assert want == got, "T1 BATTI: kablo/kosul uyumsuz"
    print(f"T1 OK kablo-butunluk ({len(want)} ates-ticki)")

    # T2: A-gecikmeleri diag P1 atesleriyle capraz-dogrulanir.
    p1f = ([int(r["p1f0"]) for r in diag],
           [int(r["p1f1"]) for r in diag])
    for r in cable:
        t = int(r["tick"])
        for li, key in ((0, "a0lag"), (1, "a1lag")):
            lag = int(r[key])
            if lag < 0:
                assert not any(p1f[li][max(0, t - WINDOW):t + 1]), \
                    f"T2 BATTI: t={t} {key}=-1 ama P1 atesi var"
            else:
                assert p1f[li][t - lag] == 1, \
                    f"T2 BATTI: t={t} {key}={lag} atesle uyusmuyor"
    print("T2 OK A-topraklama (diag capraz)")

    # T4: tau_b banka degeriyle birebir.
    assert all(int(r["tau_b"]) == BANK_TAU[int(r["post_id"])]
               for r in cable), "T4 BATTI: tau_b uyumsuz"
    print("T4 OK tau_b-butunluk")

    # T3: her kosulda geriye-iz (A -> B -> P2 -> kosul -> sonuc).
    from collections import Counter
    by_label = {}
    for r in cable:
        by_label.setdefault(r["label"], []).append(r)
    n_b = sum(1 for r in cable if set(r["bwin"]) != {"0"})
    n_pureb = sum(1 for r in cable
                  if set(r["bwin"]) != {"0"}
                  and int(r["a0lag"]) < 0 and int(r["a1lag"]) < 0)
    print(f"T3 geriye-iz ({len(by_label)} kosul; "
          f"B-paternli {n_b}, saf-B {n_pureb}):")
    for label in sorted(by_label):
        recs = by_label[label]
        ticks = sorted(int(r["tick"]) for r in recs)
        posts = sorted(set(int(r["post_id"]) for r in recs))
        a0 = [int(r["a0lag"]) for r in recs if int(r["a0lag"]) >= 0]
        a1 = [int(r["a1lag"]) for r in recs if int(r["a1lag"]) >= 0]
        top = Counter(r["bwin"] for r in recs).most_common(2)
        ws = [float(r["w"]) for r in recs]
        pn = ",".join(COND_POSTS[k] for k in posts)
        print(f"  {label}: A0~{min(a0) if a0 else '-'} "
              f"A1~{min(a1) if a1 else '-'} "
              f"B={','.join(f'{m}×{c}' for m, c in top)} "
              f"P2=[{pn}] w0={ws[0]:.3f}->w1={ws[-1]:.3f} "
              f"n={len(recs)} t~{ticks[0]}")
    print("OZET-ASSOC-TRACE: T1 T2 T4 + T3-rapor")


if __name__ == "__main__":
    main()
