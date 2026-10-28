"""v3 tuketim hatti: hat-ciktisi -> encoder -> v3 F1 -> memory -> inference.

v3 SIMULATORE DOGRUDAN BAGLANMAZ; mevcut Sensory/Afferent/Encoder
uretim hattinin cikti kablosunu (orn. encoder/out/aff300_afferent.csv)
tuketir. Sim -> Sensory siniri aynen korunur (bu dosya sim'e dokunmaz).
Donuk encoder (v0.1) aynen kosar; spike'lar birebir ters-LUT ile v3
girisine cevrilir (bit-esit roundtrip kapili). v3 mimarisi DEGISTIRILMEDI
(29 P3, F1). Etiket zincire GIRMEZ; --stages yalniz degerlendirme
anahtaridir (verilmezse skor yok, tutarlilik kapilari aynen gecerli).
ADDITIVE-ONLY yeni dosya.
"""
import argparse
import csv
import hashlib
import os
import subprocess
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "encoder"))
import afferent_encoder as E  # noqa: E402
from validate_infer_pattern import day_sig, infer  # noqa: E402

V3 = os.environ.get("NPU_V3_EXE",
                   os.path.join(ROOT, "npu_pattern_lobe"))
E0 = os.path.join(ROOT, "encoder", "out", "aff300_afferent.csv")
K = 3


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def run(cmd):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                          timeout=900)


def stage_intake(aff_in, outdir):
    """S0: hat ciktisini oldugu gibi al (kopyala + sha + say)."""
    assert os.path.isfile(aff_in), f"hat kablosu yok: {aff_in}"
    aff_p = os.path.join(outdir, "line_afferent.csv")
    with open(aff_in, "rb") as f1, open(aff_p, "wb") as f2:
        f2.write(f1.read())
    evs = E.read_afferent_csv(aff_p)
    assert evs, "hat kablosu bos!"
    with open(aff_p, newline="") as f:
        full = list(csv.DictReader(f))
    return aff_p, evs, full, sha(aff_p)


def stage_encoder(evs, outdir):
    """S1: donuk encoder -> spike'lar (1:1, sira+tick korunumu kapili)."""
    spk = E.encode_events([tuple(e) for e in evs])
    assert len(spk) == len(evs), "encoder genisletme/kayip!"
    assert [s[0] for s in spk] == [e[0] for e in evs], "tick/sira bozuldu!"
    spk_p = os.path.join(outdir, "spikes.csv")
    E.write_spikes_csv(spk_p, spk)
    return spk_p, spk


def stage_adapter(spk, evs, full, outdir):
    """S2: spike -> (post, tau_b) birebir ters-LUT; v3 girisi."""
    inv = {}
    for tb in range(4, 61):
        ph = E.phi_tau_of(tb)
        assert ph not in inv, f"phi_tau cakisma: {tb}"
        inv[ph] = tb
    assert len(inv) == 57, "ters-LUT eksik!"
    back = []
    for (t, pid, ptau) in spk:
        assert pid % 3000 == 0, f"phi_id hizalanmamis: {pid}"
        assert ptau in inv, f"phi_tau banksiz: {ptau}"
        back.append((t, pid // 3000, inv[ptau]))
    assert back == [tuple(e) for e in evs], "roundtrip BIT-ESIT DEGIL!"
    aff_p = os.path.join(outdir, "aff_from_spikes.csv")
    with open(aff_p, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(("tick", "post_id", "tau_b", "a0lag", "a1lag",
                    "bmask", "bwin", "label", "w"))
        for (t, r) in zip(back, full):
            assert (int(r["tick"]), int(r["post_id"]),
                    int(r["tau_b"])) == t, "satir uyumsuz!"
            w.writerow((r["tick"], r["post_id"], r["tau_b"], r["a0lag"],
                        r["a1lag"], r["bmask"], r["bwin"], r["label"],
                        r["w"]))
    return aff_p


def stage_v3(aff_p, outdir, eta, k4="0"):
    """S3: pattern lob (cift-kosu sha determinizm kapili).

    k4="0" (varsayilan): frozen F1; mevcut cagiricilar bayt-bayt korunur.
    k4="1": REV4 nihai lob (K1-K3 + gercek K4 + S4 soma)."""
    mem_p = os.path.join(outdir, "mem.csv")
    log_p = os.path.join(outdir, "log.csv")
    p1 = run([V3, "--aff", aff_p, "--mem", mem_p, "--log", log_p,
              "--eta", eta, "--k4", k4])
    assert p1.returncode == 0, p1.stderr[-500:]
    p2 = run([V3, "--aff", aff_p, "--mem", mem_p + ".chk",
              "--log", log_p + ".chk", "--eta", eta, "--k4", k4])
    assert p2.returncode == 0, p2.stderr[-500:]
    assert sha(mem_p) == sha(mem_p + ".chk"), "lob DETERMINISTIK DEGIL!"
    oz = [l for l in p1.stdout.splitlines() if "OZET-PATTERN-LOB" in l]
    return mem_p, oz


def load_stages(path):
    stages = {}
    if path:
        with open(path, newline="") as f:
            for row in csv.reader(f):
                if len(row) >= 2 and row[0].lstrip("-").isdigit():
                    stages[int(row[0])] = row[1]
    return stages if stages else None


def stage_memory(mem_p, stages):
    """S4: Pattern Memory -> gun imzalari + retrieval (skor etiketsiz n/a)."""
    with open(mem_p) as f:
        rows = list(csv.DictReader(f))
    assert rows, "memory bos!"
    by_day = day_sig(rows)
    units = sorted({u for s in by_day.values() for u in s})
    wins = []
    days = sorted(by_day)
    for i in range(len(days) - K + 1):
        ds = days[i:i + K]
        if ds != list(range(ds[0], ds[0] + K)):
            continue
        seq = tuple({"posts": by_day.get(x, set()), "blines": set(),
                     "a": set()} for x in ds)
        if not any(sg["posts"] for sg in seq):
            continue
        lab = (Counter(stages.get(x, "?") for x in ds).most_common(1)[0][0]
               if stages else "?")
        wins.append({"s": ds[0], "seq": seq, "label": lab})
    cm, viol = infer(wins)
    cm2, _ = infer(wins)
    assert cm == cm2, "retrieval deterministik degil!"
    # NOT: viol seyreklik-kapsama olcusudur (yalniz-pencere sayisi),
    # sizinti degil — karsilastirici yapisal olarak ortusmeyenle sinirli
    # (infer). Kapi degil, rapor.
    tot = sum(cm.values())
    if stages and tot:
        ok = sum(v for (t, p), v in cm.items() if t == p)
        acc = f"{ok / tot:.3f}(n={tot})"
    else:
        acc = "n/a(etiket-yok)"
    return {"rows": len(rows), "days": len(by_day), "units": units,
            "nwins": len(wins), "viol": viol, "acc": acc}


def main():
    ap = argparse.ArgumentParser(
        description="v3 tuketim hatti: hat-ciktisi -> REV4 pattern lob "
                    "-> memory (sistem lobu; kutuphane stage_v3 k4=0 "
                    "varsayilaniyla donuk kalir)")
    ap.add_argument("--aff", default=E0,
                    help="uretim hattinin afferent cikti kablosu")
    ap.add_argument("--stages", default=None,
                    help="gun,stage CSV (yalniz degerlendirme; opsiyonel)")
    ap.add_argument("--eta", default="0.30")
    ap.add_argument("--k4", default="1",
                    help="sistem lobu: 1=REV4 nihai lob, 0=frozen F1")
    ap.add_argument("--outdir", default="/tmp/chain_v3")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    aff_p, evs, full, digest = stage_intake(a.aff, a.outdir)
    print(f"OZET-CHAIN S0 hat: kablo={a.aff} olay={len(evs)} "
          f"sha={digest[:12]}")

    _, spk = stage_encoder(evs, a.outdir)
    print(f"OZET-CHAIN S1 encoder: spike={len(spk)} 1:1 OK")

    aff2 = stage_adapter(spk, evs, full, a.outdir)
    print("OZET-CHAIN S2 adapter: roundtrip BIT-ESIT OK")

    mem_p, ov3 = stage_v3(aff2, a.outdir, a.eta, a.k4)
    print(f"OZET-CHAIN S3 lob(k4={a.k4}): {ov3[0][:160] if ov3 else ''}")

    m = stage_memory(mem_p, load_stages(a.stages))
    print(f"OZET-CHAIN S4 memory: rows={m['rows']} gun={m['days']} "
          f"units={m['units']} wins={m['nwins']} viol={m['viol']} "
          f"acc={m['acc']}")
    print("OZET-CHAIN: PILOT GECTI")


if __name__ == "__main__":
    main()
