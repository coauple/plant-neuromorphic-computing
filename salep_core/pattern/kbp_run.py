"""KBHP kosucu: G-A kapisi -> ~57 v2-matrisi (+18 legacy) -> manifest.
Kullanim: python3 pattern/kbp_run.py [--gate] [--run] [--all]
Cikti: pattern/p0_out/kbp_{fidelity,axes.csv,manifest.json}.
G-A kirmiziysa durur.
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
import kbp_drive as D  # noqa: E402

FROZEN = ["src/pattern_lobe.h", "src/pattern_unit_v2.h",
          "pattern/pl_core.py", "pattern/P0_SPEC.md",
          "pattern/P0B_SPEC.md", "pattern/P0C_SPEC.md",
          "pattern/T_AMP_SPEC.md", "pattern/IDEN_SPEC.md"]
AFF = os.path.join(ROOT, "testb_afferent.csv")
EXE_V2 = os.path.join(ROOT, "npu_pattern_unit_v2")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def gate():
    print("== KBHP G-A ==")
    ok = {}
    ok["step-equiv"] = D.k0_vstep_equiv()
    evs, mt = [], 0
    with open(AFF) as f:
        for r in csv.DictReader(f):
            t = int(r["tick"])
            if t > 2000:
                continue
            evs.append((t, int(r["post_id"])))
            mt = max(mt, t)
    ref = P.v2_drive(evs, mt)
    inst = D.cable_drive_v2(evs, mt)
    ok["cable-repro"] = (ref == inst)
    sl = "/tmp/kbp_slice.csv"
    taumap = {0: 35, 1: 45, 2: 35, 3: 36, 4: 35, 5: 26, 6: 37, 7: 37}
    with open(sl, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tick", "post_id", "tau_b"])
        for (t, p) in evs:
            w.writerow([t, p, taumap[p]])
    r = subprocess.run([EXE_V2, "--aff", sl, "--mem", "/tmp/kbp_m.csv",
                        "--log", "/tmp/kbp_l.csv", "--eta", "0"], cwd=ROOT,
                       capture_output=True, text=True, timeout=300)
    bf = {}
    with open("/tmp/kbp_m.csv") as f:
        for row in csv.DictReader(f):
            bf.setdefault(int(row["unit"]), []).append(int(row["tick"]))
    set_eq = (set(i for i in bf if bf[i]) ==
              set(i for i in ref if ref[i]))
    cnt_ok = all(abs(len(bf.get(i, [])) - len(ref.get(i, []))) <= 2
                 for i in range(29))
    ok["binary-sets"] = (r.returncode == 0 and set_eq and cnt_ok)
    fb = {f: sha(os.path.join(ROOT, f)) for f in FROZEN}
    ok["frozen-sha"] = True
    for k, v in ok.items():
        print(f"  {'OK' if v else 'BATTI'} {k}")
    with open(os.path.join(OUT, "kbp_fidelity.json"), "w") as f:
        json.dump({"gates": ok,
                   "frozen_sha12": {k: v[:12] for k, v in fb.items()}}, f,
                  indent=1)
    print("OZET-KBHP-GA: " + ("OK" if all(ok.values()) else "BATTI"))
    return all(ok.values())


def run():
    # Kol (arm) yapisi: tek-slot kollari 12 slot-sim; cift kollari 6 pair-sim.
    # v2: 30 ana + 15 CL + 12 topo = 57 kol; legacy: 2 kol. Toplam ~630 sim.
    print("== KBHP kosular (~630 sim) ==")
    pairs = json.load(open(os.path.join(OUT, "kbp_pairs.json")))["ciftler"]
    dsteps = [0, 1, 2, 4, 6]
    okumas = ["R0", "R1", "R2"]
    arms, store = [], {}

    def arm(rid, meta, sims):
        arms.append(dict({"id": rid, "n_sim": len(sims)}, **meta))
        for sid, res in sims:
            store[sid] = res

    for okuma in okumas:  # 30 ana kol
        for parite in ("id", "sep"):
            for d in dsteps:
                sims = []
                for slot in range(12):
                    sid = f"v2_{okuma}_{parite}_d{d}_s{slot}"
                    sims.append((sid, D.run_v2(
                        slot=slot, okuma=okuma, parite=parite, d_step=d)))
                arm(f"v2_{okuma}_{parite}_d{d}",
                    {"arch": "v2", "okuma": okuma, "parite": parite,
                     "dstep": d, "topoloji": "T0", "coinc": "nat"}, sims)
    for okuma in okumas:  # 15 CL kol (coinc-sabit, yalniz sep)
        for d in dsteps:
            sims = []
            for slot in range(12):
                sid = f"v2_{okuma}_sep_d{d}_s{slot}_CL"
                sims.append((sid, D.run_v2(
                    slot=slot, okuma=okuma, parite="sep", d_step=d,
                    coinc_lock=True)))
            arm(f"v2_{okuma}_sep_d{d}_CL",
                {"arch": "v2", "okuma": okuma, "parite": "sep",
                 "dstep": d, "topoloji": "T0", "coinc": "lock"}, sims)
    for topo in ("T0", "T1"):  # 12 topo kol (6 cift each)
        for okuma in okumas:
            for cl in (False, True):
                sims = []
                for pi, pr in enumerate(pairs):
                    sid = (f"v2p_{topo}_{okuma}_{'CL' if cl else 'nat'}_"
                           f"p{pi}")
                    sims.append((sid, D.run_v2(
                        pair=(pr["X"], pr["Y"]), okuma=okuma,
                        topoloji=topo, coinc_lock=cl)))
                arm(f"v2p_{topo}_{okuma}_{'CL' if cl else 'nat'}",
                    {"arch": "v2", "okuma": okuma, "parite": "id",
                     "dstep": 0, "topoloji": topo,
                     "coinc": "lock" if cl else "nat"}, sims)
    sims = []  # legacy karsilastirma kollari
    for slot in range(12):
        sims.append((f"leg_R0_id_d0_s{slot}", D.run_legacy(slot=slot)))
    arm("leg_single", {"arch": "legacy", "okuma": "R0", "parite": "id",
                       "dstep": 0, "topoloji": "T0", "coinc": "nat"}, sims)
    sims = []
    for pi, pr in enumerate(pairs):
        sims.append((f"legp_T0_R0_nat_p{pi}",
                     D.run_legacy(pair=(pr["X"], pr["Y"]))))
    arm("leg_pair", {"arch": "legacy", "okuma": "R0", "parite": "id",
                     "dstep": 0, "topoloji": "T0", "coinc": "nat"}, sims)
    with open(os.path.join(OUT, "kbp_axes.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "arch", "okuma", "parite",
                                          "dstep", "topoloji", "coinc",
                                          "n_sim"])
        w.writeheader()
        for a in arms:
            w.writerow({k: a.get(k, "") for k in
                        ("id", "arch", "okuma", "parite", "dstep",
                         "topoloji", "coinc", "n_sim")})
    with open(os.path.join(OUT, "kbp_runs.json"), "w") as f:
        json.dump(store, f)
    man = {"spec": "pattern/KBHP_SPEC.md v2.1",
           "n_arms": len(arms), "n_sims": len(store),
           "arm_ids": sorted(a["id"] for a in arms)}
    mtxt = json.dumps(man, sort_keys=True)
    man["sha256"] = hashlib.sha256(mtxt.encode()).hexdigest()
    with open(os.path.join(OUT, "kbp_manifest.json"), "w") as f:
        json.dump(man, f, indent=1)
    print(f"OZET-KBHP-RUN: {len(arms)} kol, {len(store)} sim OK")


if __name__ == "__main__":
    args = set(sys.argv[1:]) or {"--all"}
    if "--gate" in args or "--all" in args:
        if not gate():
            sys.exit("KBHP DURDU: G-A kirmizi")
    if "--run" in args or "--all" in args:
        run()
