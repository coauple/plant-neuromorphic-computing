"""A-only sozlesme testi (§9.60): B tamamen kapaliyken A surusu.

Matris (seyrek=gercek bitki treni / yogun=sabit tau4+tau12):
  seyrek/banka, seyrek/w0.5, yogun/banka, yogun/w0.5
Hukum mantigi:
  yogun+w0.5 atesliyor + CR uretiyorsa -> kapasite VAR (mimari saglam),
  seyrek hicbir agirlikta ateslemiyorsa -> temporal persistence YETERSIZ,
  yogun banka-agirliginda ateslemiyorsa -> ogrenme B'siz baslayamaz
  (tavuk-yumurta: ates yoksa dw yok).

Calistirma: .venv/bin/python validate_aonly.py
Girdi: testb_{sensors}.csv + aonly_dense_spikes.csv (B okunmaz).
Olcutler (C1-C4).
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

COND_POSTS = ("p2a", "p2b", "p2c", "p2d", "p2e", "p2f", "p2g", "p2h",
              "p2i", "p2j")


def run(spikes, w0=None, tag="x"):
    exe = os.path.join(ROOT, "npu_sensory_plant")
    out = f"/tmp/aonly_{tag}.csv"
    cmd = [exe, "--spikes", os.path.join(ROOT, spikes),
           "--sensors", os.path.join(ROOT, "testb_sensors.csv"),
           "--out", out, "--cond", "22", "--test", "3", "--b-off"]
    if w0 is not None:
        cmd += ["--w0", str(w0)]
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       timeout=600)
    if p.returncode != 0:
        raise SystemExit(f"harness batti:\n{p.stderr[-2000:]}")
    return p.stdout


def parse(log):
    d = {"labels": []}
    for line in log.splitlines():
        if line.startswith("K t="):
            parts = line.split()
            if len(parts) >= 3:
                d["labels"].append(parts[2])
        elif line.startswith("OZET-PLANT: post_atis:"):
            d["cond"] = [int(x)
                         for x in line.split("post_atis:")[1].split()]
        elif line.startswith("OZET-PLANT: test_atis:"):
            d["test"] = [int(x)
                         for x in line.split("test_atis:")[1].split()]
    d["ncond"] = len(set(d["labels"]))
    return d


def main():
    r = {}
    r["seyrek_bank"] = parse(run("testb_spikes.csv", None, "ss"))
    r["seyrek_w05"] = parse(run("testb_spikes.csv", 0.5, "sw"))
    r["yogun_bank"] = parse(run("aonly_dense_spikes.csv", None, "ds"))
    r["yogun_w05"] = parse(run("aonly_dense_spikes.csv", 0.5, "dw"))
    for k, v in r.items():
        print(f"{k:12s} cond={sum(v['cond']):4d} test={sum(v['test']):3d} "
              f"kosul={v['ncond']} a={v['cond'][0]}")

    ok = []
    ok.append(("C1 kapasite_var",
               r["yogun_w05"]["cond"][0] > 100))
    ok.append(("C2 CR_var",
               r["yogun_w05"]["test"][0] > 0))
    ok.append(("C3 seyrek_persistence_yok",
               sum(r["seyrek_w05"]["cond"]) == 0))
    ok.append(("C4 tavuk_yumurta",
               sum(r["yogun_bank"]["cond"]) == 0))
    bad = [k for k, v in ok if not v]
    for k, v in ok:
        print(f"  {'OK' if v else 'BATTI'} {k}")
    if bad:
        raise SystemExit(f"BATTI: {bad}")
    print("HUKUM: mimari calisiyor (yogun+enerjik -> P2+CR), "
          "seyrek persistence yetersiz; B ilk atesler icin gerekli.")
    print("OZET-AONLY: " + " ".join(k for k, _ in ok))


if __name__ == "__main__":
    main()
