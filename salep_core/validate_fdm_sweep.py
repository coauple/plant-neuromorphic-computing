"""FDM persistence karakterizasyonu (§9.63) — seyrek tren kaybi.

Yontem (donuk kaynaklara DOKUNULMAZ): src/ Ag/tmp kopyalanir, yalniz
kopyadaki zaman-sabitleri yamanir, kopya hedefle derlenir. Bitki spike
trenleri SABIT (testb_spikes.csv).

Eksenler: L sizinti-tau (P1-kok 1..320 tick), W cakisma penceresi
(4..80), G gating-hafiza (4..800). Olcutler (F1-F6): baz bit-esitlik
capasi, her eksende uclar arasi bit-esitlik, seyrek A-capture araligi.

Bulgu: tum eksenler bit-esit -> atesleme ayni-tick kombinasyoneldir;
süreklilik makinesi bu rejimde sonuca katilmaz. Seyrek trenin zamansal
bilgisi kullanilmaz (kayip: capture ~%15).
"""
import csv
import hashlib
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

SW = "/tmp/fdm_sweep_run"
EXE_MAIN = os.path.join(ROOT, "src", "main_sensory_plant.cpp")
SPIKES = os.path.join(ROOT, "testb_spikes.csv")
SENSORS = os.path.join(ROOT, "testb_sensors.csv")
DENSE = os.path.join(ROOT, "aonly_dense_spikes.csv")


def build(tag, patches):
    d = os.path.join(SW, tag)
    if os.path.exists(d):
        shutil.rmtree(d)
    shutil.copytree(os.path.join(ROOT, "src"),
                    os.path.join(d, "src"))
    for rel, old, new in patches:
        p = os.path.join(d, rel)
        s = open(p).read()
        assert old in s, f"yama hedefi yok {tag}:{old}"
        open(p, "w").write(s.replace(old, new))
    exe = os.path.join(d, "npu")
    r = subprocess.run(["g++", "-std=c++17", "-O2",
                        f"-I{os.path.join(d, 'src')}", EXE_MAIN,
                        "-o", exe],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise SystemExit(f"derleme batti {tag}:\n{r.stderr[-1500:]}")
    return exe


def leak_patch(f):
    return [("src/sensory_lobe.h",
             "NeuronParams p = {0.08, 0.06, 0.04, 0.005, 0.004, 0.003};",
             "NeuronParams p = {%s};" %
             ", ".join(f"{x * f:.6f}"
                       for x in (0.08, 0.06, 0.04, 0.005, 0.004, 0.003))),
            ("src/sensory_lobe.h",
             "NeuronParams p = {0.04, 0.12, 0.04, 0.005, 0.004, 0.003};",
             "NeuronParams p = {%s};" %
             ", ".join(f"{x * f:.6f}"
                       for x in (0.04, 0.12, 0.04, 0.005, 0.004, 0.003)))]


def run(exe, tag, spikes=SPIKES, extra=()):
    out = os.path.join(SW, f"{tag}.csv")
    p = subprocess.run(
        [exe, "--spikes", spikes, "--sensors", SENSORS, "--out", out,
         "--cond", "22", "--test", "3"] + list(extra),
        capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        raise SystemExit(f"kosu batti {tag}")
    return out


def sig(path):
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    p1 = 0
    with open(path) as f:
        for row in csv.reader(f):
            p1 += (row[3] == "1") + (row[4] == "1")
    return h, p1


def main():
    os.makedirs(SW, exist_ok=True)
    outs = {}
    outs["base_repo"] = run(os.path.join(ROOT, "npu_sensory_plant"),
                            "base_repo")
    exe0 = build("base", [])
    outs["base_copy"] = run(exe0, "base_copy")
    outs["L1"] = run(build("L1", leak_patch(12.5 / 1)), "L1")
    outs["L320"] = run(build("L320", leak_patch(12.5 / 320)), "L320")
    outs["W4"] = run(build("W4", [("src/neuron.h",
                                   "COINCIDENCE_WINDOW_MS = 10;",
                                   "COINCIDENCE_WINDOW_MS = 4;")]), "W4")
    outs["W80"] = run(build("W80", [("src/neuron.h",
                                     "COINCIDENCE_WINDOW_MS = 10;",
                                     "COINCIDENCE_WINDOW_MS = 80;")]),
                      "W80")
    outs["G4"] = run(build("G4", [
        ("src/sensory_lobe.h",
         "NeuronParams p = {0.08, 0.06, 0.04, 0.005, 0.004, 0.003};",
         "NeuronParams p = {0.08, 0.06, 0.04, 0.125000, 0.100000,"
         " 0.075000};"),
        ("src/sensory_lobe.h",
         "NeuronParams p = {0.04, 0.12, 0.04, 0.005, 0.004, 0.003};",
         "NeuronParams p = {0.04, 0.12, 0.04, 0.250000, 0.200000,"
         " 0.150000};")]), "G4")
    outs["G800"] = run(build("G800", [
        ("src/sensory_lobe.h",
         "NeuronParams p = {0.08, 0.06, 0.04, 0.005, 0.004, 0.003};",
         "NeuronParams p = {0.08, 0.06, 0.04, 0.000625, 0.000500,"
         " 0.000375};"),
        ("src/sensory_lobe.h",
         "NeuronParams p = {0.04, 0.12, 0.04, 0.005, 0.004, 0.003};",
         "NeuronParams p = {0.04, 0.12, 0.04, 0.001250, 0.001000,"
         " 0.000750};")]), "G800")
    outs["DL1"] = run(build("DL1", leak_patch(12.5 / 1)), "DL1",
                      spikes=DENSE, extra=("--b-off", "--w0", "0.5"))
    outs["DL320"] = run(build("DL320", leak_patch(12.5 / 320)), "DL320",
                        spikes=DENSE, extra=("--b-off", "--w0", "0.5"))

    h = {k: sig(v) for k, v in outs.items()}
    with open(SPIKES) as f:
        nsp = sum(1 for line in f if line[:1].isdigit())
    cap = h["base_repo"][1] / nsp
    print(f"seyrek A-capture: {h['base_repo'][1]}/{nsp} = {cap:.3f}")

    ok = []
    ok.append(("F1 baz_bit_esit", h["base_repo"][0] == h["base_copy"][0]))
    ok.append(("F2 sizinti_duz", h["L1"][0] == h["L320"][0]))
    ok.append(("F3 pencere_duz", h["W4"][0] == h["W80"][0]))
    ok.append(("F4 gating_duz", h["G4"][0] == h["G800"][0]))
    ok.append(("F5 capture_bandi", 0.10 < cap < 0.25))
    ok.append(("F6 yogun_duz", h["DL1"][0] == h["DL320"][0]))
    bad = [k for k, v in ok if not v]
    for k, v in ok:
        print(f"  {'OK' if v else 'BATTI'} {k}")
    if bad:
        raise SystemExit(f"BATTI: {bad}")
    print("BULGU: atesleme ayni-tick kombinasyonel; sureklilik makinesi "
          "bu rejimde sonuca katilmiyor (L1==L320, W4==W80, G4==G800, "
          "yogun rejim dahil).")
    print("OZET-FDM-SWEEP: " + " ".join(k for k, _ in ok))


if __name__ == "__main__":
    main()
