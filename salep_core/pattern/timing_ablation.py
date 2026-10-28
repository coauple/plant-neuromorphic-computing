"""Zaman ablasyonu (STIMULUS_SNR_SPEC.md G-ABL + V0).

Kanonik kablo (base_s42 afferent): V0 kimlik-tekrar bit-esitlik KAPISI;
NOPOS (post_id:=mod, tick/tau aynen); NOCNT (tick-basi ilk olay).
Beklenti: aile coker (cokmezse bulgu). Cikti: stress_out_snr/ablation.csv.
"""
import csv
import hashlib
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "pattern"))
import run_chain_v3 as C  # noqa: E402
import readout_v3d as R  # noqa: E402
import memory_readouts as M  # noqa: E402

BASE = "/tmp/snr"
OUTD = os.path.join(ROOT, "stress_out_snr")
SRC = f"{BASE}/base_s42/afferent.csv"
EXE = os.path.join(ROOT, "npu_pattern_unit_v3d")


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def consume(aff, outdir):
    os.makedirs(outdir, exist_ok=True)
    _, evs, full, _ = C.stage_intake(aff, outdir)
    _, spk = C.stage_encoder(evs, outdir)
    aff2 = C.stage_adapter(spk, evs, full, outdir)
    old = C.V3
    C.V3 = EXE
    try:
        mem, _ = C.stage_v3(aff2, outdir, "0.30")
    finally:
        C.V3 = old
    return mem, evs


def eff_sig(mem):
    tv, by = R.load_mem(mem)
    return M.sig_E1(tv, by, mem)


def fam_vs_dry(mem_q, ref_base, ref_dry):
    """Sorgu mem'i base/drynew ref'lerine karsi: donus (label, skorlar)."""
    tv, by = R.load_mem(mem_q)
    q = M.sig_E1(tv, by, mem_q)
    qw = R.wins_from_sig(q, "q", 900000)
    out = {}
    for lab, rm in (("base", ref_base), ("dry", ref_dry)):
        tv, by = R.load_mem(rm)
        rw = R.wins_from_sig(M.sig_E1(tv, by, rm), lab, 0)
        best = 0.0
        for w in qw:
            bs = max([R.seq_sim(w["seq"], r["seq"]) for r in rw] or [0])
            best = max(best, bs)
        out[lab] = round(best, 4)
    lab = "base" if out["base"] >= out["dry"] else "dry"
    return lab, out


def main():
    os.makedirs(OUTD, exist_ok=True)
    assert os.path.exists(SRC), "once snr_audit base kosmali"
    with open(SRC, newline="") as f:
        rows = list(csv.DictReader(f))
    # V0: kimlik-tekrar bit-esitlik.
    m0, _ = consume(SRC, "/tmp/snr_abl_v0")
    ref = sha(f"{BASE}/base_s42/c/mem.csv")
    v0 = sha(m0) == ref
    print(f"  {'OK' if v0 else 'BATTI'} V0-bit-esit {sha(m0)[:12]}", flush=True)
    assert v0, "V0 KAPISI: tekrar uremiyor!"
    # NOPOS / NOCNT.
    mode = Counter(r["post_id"] for r in rows).most_common(1)[0][0]
    ab = []
    nop = f"/tmp/snr_abl_nopos.csv"
    with open(nop, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            r2 = dict(r)
            r2["post_id"] = mode
            w.writerow(r2)
    seen = set()
    noc = f"/tmp/snr_abl_nocnt.csv"
    with open(noc, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            if r["tick"] in seen:
                continue
            seen.add(r["tick"])
            w.writerow(r)
    rb = f"{BASE}/base_s42/c/mem.csv"
    rd = f"{BASE}/drynew_s42/c/mem.csv"
    assert os.path.exists(rd), "once snr_audit drynew kosmali"
    for tag, pp in (("NOPOS", nop), ("NOCNT", noc)):
        mem, evs = consume(pp, f"/tmp/snr_abl_{tag.lower()}")
        lab, sc = fam_vs_dry(mem, rb, rd)
        ab.append({"abl": tag, "events": len(evs), "label": lab,
                   "s_base": sc["base"], "s_dry": sc["dry"]})
        print(f"  {tag}: olay={len(evs)} -> {lab} {sc}", flush=True)
    with open(os.path.join(OUTD, "ablation.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["abl", "events", "label",
                                          "s_base", "s_dry"])
        w.writeheader()
        w.writerows(ab)
    print("OZET-ABL: biten")


if __name__ == "__main__":
    main()
