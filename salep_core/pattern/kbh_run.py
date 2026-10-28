"""KBH kosucu: Faz 0 (sadakat) -> Faz 1 (tap) -> Faz 2 (merdiven).
Kullanim: python3 pattern/kbh_run.py [--phase0] [--phase1] [--phase2] [--all]
Cikti: pattern/p0_out/kbh_*. K0 kirmiziysa durur (sys.exit 1).
Faz 1: 48 sim (12 slot x {1.0,4.0} x {legacy,v2}), kontrol knob'lari.
Faz 2 eksenleri (SPEC): A0 d_step{0..3}; A1a w_ring{0,.2,.4};
A1b oran{0.25,.5,1,2,4} (k1_gain=oran); A1c readout{1,12} (analiz-boyutu,
amp=1.0 alt-kumesi); A2 mod{off,blind,selective,asymmetric} CIFt uyaranli;
A3 leak{.02,.06,.10} x slot{1,4,7,5} x analog{0,1} (analog analiz-boyutu);
G greedy (veri-belirler, ~120).
"""
import csv
import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pattern"))
OUT = os.path.join(ROOT, "pattern", "p0_out")

import pl_core as P  # noqa: E402
import kbh_taps as T  # noqa: E402

FROZEN = ["src/pattern_lobe.h", "src/pattern_unit_v2.h",
          "pattern/pl_core.py", "pattern/P0_SPEC.md",
          "pattern/P0B_SPEC.md", "pattern/P0C_SPEC.md",
          "pattern/T_AMP_SPEC.md", "pattern/IDEN_SPEC.md"]
AFF = os.path.join(ROOT, "testb_afferent.csv")
EXE_V2 = os.path.join(ROOT, "npu_pattern_unit_v2")
EXE_LEG = os.path.join(ROOT, "npu_pattern_lobe")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def snap_dirs():
    out = {}
    for d in ("pattern/p0_out", "encoder/out"):
        dp = os.path.join(ROOT, d)
        out[d] = sorted(os.listdir(dp)) if os.path.isdir(dp) else []
    return out


def load_aff(path, tick_max=None):
    evs = []
    with open(path) as f:
        for r in csv.DictReader(f):
            t = int(r["tick"])
            if tick_max is not None and t > tick_max:
                continue
            evs.append((t, int(r["post_id"]), int(r["tau_b"])))
    return evs


def legacy_cable_drive(evs, max_tick):
    # main_pattern_lobe.cpp aynasi (twin olcegi: C++ agirlik*0.5 esdegeri).
    # Ogrenme YOK (twin-dogal; K0d ±2 bunu da kapsar).
    u = P.PatternUnit("ring")
    kfires = [0, 0, 0]
    pfires = 0
    mem = 0
    for t in range(max_tick + 1):
        for (te, s, _) in evs:
            if te != t:
                continue
            for dal in (0, 1):
                comp = P.COMP_A if dal == 0 else P.COMP_B
                P.inject(u.k1[dal][s], comp, 0.5, t)
                P.inject(u.k1[dal][(s - 1) % 12], comp, 0.1, t)
                P.inject(u.k1[dal][(s + 1) % 12], comp, 0.1, t)
                P.inject(u.k2[dal], comp, 0.5, t)
                P.inject(u.k3[dal], comp, 0.5, t)
        kf, fired, _, _, _ = P.step(u, t, amp_k=0.5)
        for (dal, name, _) in kf:
            kfires[{"k1": 0, "k2": 1, "k3": 2}[name]] += 1
        if fired:
            pfires += 1
            mem += 1
    return {"olay": len(evs), "k": kfires, "p3": pfires, "mem": mem}


def phase0():
    print("== KBH Faz 0 ==")
    ok = {}
    fb = {f: sha(os.path.join(ROOT, f)) for f in FROZEN}
    db = snap_dirs()

    # K0a: taps-legacy tesisati ⇄ bagimsiz referans (ayni primitive, farkli dongu)
    ref = P.PatternUnit("ring")
    fire_ref, soma_ref = [], []
    for t in range(T.HORIZON):
        if T.T0 <= t < T.T0 + T.N_PULSE * T.ISI and (t - T.T0) % T.ISI == 0:
            P.inject_phase(ref, 0, 4, 1.0, T.RING, t)
            P.inject_phase(ref, 1, 4, 1.0, T.RING, t)
        kf, fired, co, eg, sm = P.step(ref, t)
        fire_ref.append(1 if fired else 0)
        soma_ref.append(sm)
    tr = T.legacy_run(4, 1.0)
    ok["K0a"] = (tr["fire"] == fire_ref and tr["soma"] == soma_ref)

    # K0a2: run_condition capraz-kontrol (UAC emsali cift)
    rc = P.run_condition("ring", 0, 120, 210, 30)
    ok["K0a2"] = (isinstance(rc["n_fires"], int) and rc["n_coinc"] >= 0)

    # K0b: taps-v2 ⇄ pl_core.v2_drive + _ptick esdegerlik
    evs2000 = [(t, p) for (t, p, _) in load_aff(AFF, 2000)]
    mt = max(t for t, _ in evs2000)
    ref_v2 = P.v2_drive(evs2000, mt)
    inst_v2 = T.v2_reference_drive(evs2000, mt)
    ok["K0b"] = (ref_v2 == inst_v2) and T.k0_ptick_equiv()

    # K0c: enstrumante-v2 ⇄ binary (kume esit, sayi ±2)
    sl = "/tmp/kbh_slice.csv"
    taumap = {0: 35, 1: 45, 2: 35, 3: 36, 4: 35, 5: 26, 6: 37, 7: 37}
    with open(sl, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tick", "post_id", "tau_b"])
        for (t, p, _) in load_aff(AFF, 2000):
            w.writerow([t, p, taumap[p]])
    r = subprocess.run([EXE_V2, "--aff", sl, "--mem", "/tmp/kbh_v2m.csv",
                        "--log", "/tmp/kbh_v2l.csv"], cwd=ROOT,
                       capture_output=True, text=True, timeout=300)
    bin_fires = {}
    with open("/tmp/kbh_v2m.csv") as f:
        for row in csv.DictReader(f):
            bin_fires.setdefault(int(row["unit"]), []).append(
                int(row["tick"]))
    set_eq = (set(i for i in bin_fires if bin_fires[i]) ==
              set(i for i in ref_v2 if ref_v2[i]))
    cnt_ok = all(abs(len(bin_fires.get(i, [])) - len(ref_v2.get(i, []))) <= 2
                 for i in range(29))
    ok["K0c"] = (r.returncode == 0 and set_eq and cnt_ok)

    # K0d: enstrumante-legacy ⇄ binary OZET ±2
    evs = load_aff(AFF, 2000)
    ic = legacy_cable_drive(evs, 2000)
    r = subprocess.run([EXE_LEG, "--aff", sl, "--mem", "/tmp/kbh_lm.csv",
                        "--log", "/tmp/kbh_ll.csv"], cwd=ROOT,
                       capture_output=True, text=True, timeout=300)
    oz = [l for l in r.stdout.splitlines() if "OZET-PATTERN" in l]
    import re as _re
    m = _re.search(r"olay=(\d+) k_atis=(\d+)\+(\d+)\+(\d+) p3_atis=(\d+) mem=(\d+)",
                   oz[0]) if oz else None
    if m:
        b = [int(x) for x in m.groups()]
        i = [ic["olay"]] + ic["k"] + [ic["p3"], ic["mem"]]
        ok["K0d"] = all(abs(x - y) <= 2 for x, y in zip(b, i))
        det = (b, i)
    else:
        ok["K0d"] = False
        det = None
    print("  K0d binary-vs-enstrumante:", det)

    # K0f: determinizm (taps 2x)
    t1 = T.legacy_run(4, 1.0)
    t2 = T.legacy_run(4, 1.0)
    v1 = T.v2_run(4, 1.0)
    v2 = T.v2_run(4, 1.0)
    ok["K0f"] = (t1 == t2 and v1 == v2)

    # K0e: donuk manifest
    fa = {f: sha(os.path.join(ROOT, f)) for f in FROZEN}
    da = snap_dirs()
    newf = {d: sorted(set(da[d]) - set(db[d]) - {"kbh_fidelity.json"})
            for d in da}
    ok["K0e"] = (fa == fb and all(not v for v in newf.values()))

    for k, v in ok.items():
        print(f"  {'OK' if v else 'BATTI'} {k}")
    with open(os.path.join(OUT, "kbh_fidelity.json"), "w") as f:
        json.dump({"gates": ok, "frozen_sha12": {k: v[:12] for k, v in fa.items()},
                   "k0d_detail": det}, f, indent=1)
    print("OZET-KBH-F0: " + ("OK" if all(ok.values()) else
                             "BATTI:" + ",".join(k for k, v in ok.items()
                                                 if not v)))
    return all(ok.values())


def sim_id(axis, arch, slot, **kw):
    parts = [axis, arch, f"s{slot}"]
    parts += [f"{k}{v}" for k, v in sorted(kw.items())]
    return "_".join(str(p) for p in parts)


def run_legacy(slot, amp, **kw):
    return T.legacy_run(slot, amp, **kw)


def run_v2(slot, amp, **kw):
    return T.v2_run(slot, amp, **kw)


def phase1():
    print("== KBH Faz 1 (48 sim) ==")
    taps, traces = [], {}
    for arch in ("legacy", "v2"):
        for slot in range(12):
            for amp in (1.0, 4.0):
                rid = sim_id("F1", arch, slot, amp=amp)
                tr = run_legacy(slot, amp) if arch == "legacy" else \
                    run_v2(slot, amp)
                taps.append({"id": rid, "axis": "F1", "arch": arch,
                             "slot": slot, "amp": amp})
                traces[rid] = tr
                print(f"  {rid} fire={tr['fire_ticks'] if arch == 'legacy' else [tr[i]['fire_ticks'] for i in range(6)]}")
    with open(os.path.join(OUT, "kbh_taps.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "axis", "arch", "slot",
                                          "amp"])
        w.writeheader()
        w.writerows(taps)
    with open(os.path.join(OUT, "kbh_traces.json"), "w") as f:
        json.dump(traces, f)
    print("OZET-KBH-F1: 48 sim OK")
    return taps, traces


def phase2():
    print("== KBH Faz 2 (OFAT) ==")
    runs = []
    try:
        with open(os.path.join(OUT, "kbh_traces.json")) as f:
            traces = json.load(f)
    except FileNotFoundError:
        traces = {}
    try:
        with open(os.path.join(OUT, "kbh_taps.csv")) as f:
            taps = list(csv.DictReader(f))
    except FileNotFoundError:
        taps, traces = [], {}
    if not taps:
        taps, traces = phase1()

    def add(axis, arch, slot, amp, tr, **kw):
        rid = sim_id(axis, arch, slot, amp=amp, **kw)
        runs.append({"id": rid, "axis": axis, "arch": arch, "slot": slot,
                     "amp": amp, **{k: str(v) for k, v in kw.items()}})
        traces[rid] = tr

    for arch in ("legacy", "v2"):
        R = run_legacy if arch == "legacy" else run_v2
        for slot in range(12):
            for d in (0, 1, 2, 3):  # A0
                add("A0", arch, slot, 1.0, R(slot, 1.0, delay=slot * d),
                    dstep=d)
            for wr in (0.0, 0.2, 0.4):  # A1a
                add("A1a", arch, slot, 1.0, R(slot, 1.0, w_ring=wr),
                    wring=wr)
            for r in (0.25, 0.5, 1.0, 2.0, 4.0):  # A1b
                add("A1b", arch, slot, 1.0, R(slot, 1.0, k1_gain=r),
                    ratio=r)
            for m in ("off", "blind", "selective", "asymmetric"):  # A2
                add("A2", arch, slot, 1.0,
                    R(slot, 1.0, dual=True, k2k3_mode=m), mode=m)
    for slot in (1, 4, 7, 5):  # A3 (temsilci slotlar, iki mimari)
        for arch2 in ("legacy", "v2"):
            R2 = run_legacy if arch2 == "legacy" else run_v2
            for lk in (0.02, 0.06, 0.10):
                add("A3", arch2, slot, 1.0, R2(slot, 1.0, leak_override=lk),
                    leak=lk)
    with open(os.path.join(OUT, "kbh_runs.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "axis", "arch", "slot",
                                          "amp", "dstep", "wring", "ratio",
                                          "mode", "leak"])
        w.writeheader()
        for r in runs:
            row = {k: r.get(k, "") for k in
                   ("id", "axis", "arch", "slot", "amp", "dstep", "wring",
                    "ratio", "mode", "leak")}
            w.writerow(row)
    with open(os.path.join(OUT, "kbh_traces.json"), "w") as f:
        json.dump(traces, f)
    print(f"OZET-KBH-F2-OFAT: {len(runs)} sim OK")
    return runs, traces


if __name__ == "__main__":
    args = set(sys.argv[1:]) or {"--all"}
    cont = True
    if "--phase0" in args or "--all" in args:
        cont = phase0()
    if not cont:
        sys.exit("KBH DURDU: K0 kirmizi")
    if "--phase1" in args or "--all" in args:
        phase1()
    if "--phase2" in args or "--all" in args:
        phase2()
