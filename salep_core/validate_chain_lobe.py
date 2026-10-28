"""Sistem lob baglantisi duman testi (REV4 nihai lob, run_chain hatti).

Kapsar (BATTI=cikis 1):
  C1: run_chain main --k4 1 uctan-uca calisir (S0-S4, OZET-CHAIN).
  C2: run_chain main --k4 0 calisir (frozen F1 yolu sistemde korunur).
  C3: k4=1 cift-kosu mem sha esit (sistem-duzeyi determinizm).
  C4: kutuphane stage_v3 varsayilani k4=0'dir (imzasiz cagri == acik "0";
      mevcut F1 cagiricilari bayt-bayt korunur).

Kullanim: python3 validate_chain_lobe.py
Cikti: OZET-CHAIN-LOB: OK/BATTI.
"""

import csv
import hashlib
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
AFF = os.path.join(ROOT, "testb_afferent.csv")
OUT = "/tmp/chain_lobe_test"

fails = []


def check(name, cond, extra=""):
    print(f"  {'OK' if cond else 'BATTI'} {name} {extra}", flush=True)
    if not cond:
        fails.append(name)


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def run(cmd):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                          timeout=900)


def main():
    os.makedirs(OUT, exist_ok=True)
    assert os.path.isfile(AFF), "TEST-B kablosu yok!"

    # C1: sistem lobu (--k4 1) uctan-uca.
    p1 = run([sys.executable, "run_chain_v3.py", "--aff", AFF,
              "--eta", "0", "--k4", "1", "--outdir", f"{OUT}/on"])
    ok1 = (p1.returncode == 0 and "OZET-CHAIN: PILOT GECTI" in p1.stdout
           and "OZET-PATTERN-LOB" in p1.stdout)
    check("C1-sistem-lob-k4acik", ok1, p1.stderr[-200:] if not ok1 else "")

    # C2: frozen F1 yolu (--k4 0) sistemde calisir.
    p0 = run([sys.executable, "run_chain_v3.py", "--aff", AFF,
              "--eta", "0", "--k4", "0", "--outdir", f"{OUT}/off"])
    ok0 = (p0.returncode == 0 and "OZET-CHAIN: PILOT GECTI" in p0.stdout)
    check("C2-sistem-lob-k4kapali", ok0, p0.stderr[-200:] if not ok0 else "")

    # C3: k4=1 cift-kosu determinizm (mem sha).
    q1 = run([sys.executable, "run_chain_v3.py", "--aff", AFF,
              "--eta", "0", "--k4", "1", "--outdir", f"{OUT}/on2"])
    det = (q1.returncode == 0 and ok1 and
           sha(f"{OUT}/on/mem.csv") == sha(f"{OUT}/on2/mem.csv"))
    check("C3-sistem-determinizm", det, "")

    # C4: kutuphane varsayilani k4=0 (imzasiz == acik "0").
    sys.path.insert(0, ROOT)
    import run_chain_v3 as C
    for d in ("lib", "libdef", "libexp"):
        os.makedirs(f"{OUT}/{d}", exist_ok=True)
    aff_p, evs, full, _ = C.stage_intake(AFF, f"{OUT}/lib")
    _, spk = C.stage_encoder(evs, f"{OUT}/lib")
    aff2 = C.stage_adapter(spk, evs, full, f"{OUT}/lib")
    m_def, _ = C.stage_v3(aff2, f"{OUT}/libdef", "0")
    m_exp, _ = C.stage_v3(aff2, f"{OUT}/libexp", "0", "0")
    check("C4-kutuphane-varsayilan-k4kapali",
          sha(m_def) == sha(m_exp), "")

    # Ek bilgi: acik-kosuda mem 13 kolon (soma_k4,k4spk).
    with open(f"{OUT}/on/mem.csv") as f:
        cols = next(csv.reader(f))
    print(f"  BILGI on-mem-kolon={len(cols)} "
          f"{'soma_k4' in cols and 'k4spk' in cols}", flush=True)

    print(f"OZET-CHAIN-LOB: {'OK' if not fails else 'BATTI ' + ','.join(fails)}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
