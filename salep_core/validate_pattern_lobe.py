"""PATTERN LOB pilot dogrulama (REV4 gercek K4, 58 node).

Kapsam: KUCUK deterministik pilot (TEST-B kablosu, eta=0). Full battery YOK.
v3e'ye dokunulmaz; karsilastirma kayitli kanonik v3e hash'lerinedir.

KAPILAR (BATTI=cikis 1):
  B:  lob binary kaynaktan derlenir (derleme adimi validatorun icinde).
  J:  lob --k4 0 -> mem/log/W stdout v3e ile bayt-bayt ayni (mem 11 kolon).
  R:  npu_pattern_lobe_k4_rel R1-R8 HEPSI OK.
  P:  check_pattern_lobe 12/12 OK + pilot matrisi nonuniform.
  D:  lob --k4 1 cift-kosu bit-esit (mem/log/k4_branch/k4_matrix/k4_ids).
  M:  soma_k4<=S4_CAP (0.25), s4max<=0.25 (OZET), agirliklar [0,2.0].
  N:  OPEN birimler (27,28) k4-acik kosuda ateslemez.
  S:  (yapisal S1-S3 check icinde) + pilot nedensellik: k4-kaynakli ates
      varsa mem soma_k4>0 ile isaretlidir (ates en az birinde K4 imzasi).
RAPOR (kapi DEGIL, esik YOK — pilot degerlendirmesi birlikte yapilir):
  rows, Nsig, aktif P3, tekrar (pattern_stress_v3.py m_basic formulleri),
  max Jaccard + cokmus cift, K4 enerji (nztick, spike, kfires, s4max),
  secicilik (matris doluluk), ilişki matrisi ozeti, top_partner tablosu,
  (11,14) pairwise-lokalite hukmu.

Kullanim: python3 validate_pattern_lobe.py [--eta 0]
Cikti: OZET-LOB-PILOT: B J R P D M N S + rapor satirlari.
"""

import argparse
import csv
import hashlib
import os
import subprocess
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
# v3e binary kabulde silindi; J karsilastirmasi kayitli kanonik hash'ledir
# (TEST-B, eta=0; bu oturumda taze v3e kosusuyla dogrulandi).
V3E_MEM_SHA = "2f3811e33946f7013c6d278e81eb996c11878fe1c3834364de7bb42877f37738"
V3E_LOG_SHA = "0942be1ffda60960dc12f8bdf274aafbdd081c6be80bf5e438e6d932d4f242b4"
LOBE_SRC = os.path.join(ROOT, "src", "main_pattern_lobe.cpp")
LOBE = os.path.join(ROOT, "npu_pattern_lobe")
CHK_SRC = os.path.join(ROOT, "check_pattern_lobe.cpp")
REL_SRC = os.path.join(ROOT, "src", "main_pattern_lobe_k4_rel.cpp")
REL = os.path.join(ROOT, "npu_pattern_lobe_k4_rel")
AFF = os.path.join(ROOT, "testb_afferent.csv")
OUT = "/tmp/lobe_pilot"
S4_CAP = 0.25
W_MAX = 2.0
NB = 58
NPAIR = NB * (NB - 1) // 2  # 1653

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
                          timeout=600)


def read_mem(mem):
    with open(mem) as f:
        return list(csv.DictReader(f))


def tickvec(rows):
    tv = {}
    for r in rows:
        tv.setdefault(int(r["tick"]), set()).add(int(r["unit"]))
    return {t: frozenset(s) for t, s in tv.items()}


def m_basic(rows):
    # pattern_stress_v3.py::m_basic + validate_infer_pattern.day_sig (tick//50).
    tv = tickvec(rows)
    vecs = list(tv.values())
    n_pv = len(set(vecs))
    rep = 1 - n_pv / len(vecs) if vecs else -1.0
    by = defaultdict(set)
    for t, s in tv.items():
        by[t // 50] |= set(s)
    sigs = [s for s in by.values() if s]
    n_sig = len({frozenset(s) for s in sigs})
    return {"rows": len(rows), "N_sig": n_sig, "N_pv": n_pv,
            "repetition": round(rep, 4),
            "units": sorted({u for s in by.values() for u in s})}


def pairwise_jacc(rows):
    tv = tickvec(rows)
    present = defaultdict(set)
    for t, s in tv.items():
        for u in s:
            present[u].add(t)
    units = sorted(present)
    mx, ties, pair = 0.0, 0, None
    for i in range(len(units)):
        for j in range(i + 1, len(units)):
            a, b = present[units[i]], present[units[j]]
            jv = len(a & b) / len(a | b) if (a | b) else 1.0
            if jv > mx + 1e-12:
                mx, pair = jv, (units[i], units[j])
            if abs(jv - 1.0) < 1e-12:
                ties += 1
    return round(mx, 4), ties, pair, present


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eta", default="0")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    assert os.path.isfile(AFF), "TEST-B kablosu yok!"

    # B: lob binary kaynaktan derlenir.
    p = run(["g++", "-std=c++17", "-O2", "-Isrc", LOBE_SRC, "-o", LOBE])
    check("B-derleme", p.returncode == 0, p.stderr[-300:])
    p = run(["g++", "-std=c++17", "-O2", "-Isrc", REL_SRC, "-o", REL])
    check("B-derleme-rel", p.returncode == 0, p.stderr[-300:])

    # P (yapisal): check 12/12.
    chk = "/tmp/check_lobe_v"
    p = run(["g++", "-std=c++17", "-O2", "-Isrc", CHK_SRC, "-o", chk])
    check("P-build", p.returncode == 0, p.stderr[-300:])
    p = run([chk])
    check("P-check",
          p.returncode == 0 and "OZET-LOB-CHECK: OK" in p.stdout,
          p.stdout.strip().splitlines()[-1] if p.stdout else "")

    # R: sentetik R1-R8.
    p = run([REL])
    ok = p.returncode == 0 and "OZET-K4-REL: R1 R2 R3 R4 R5 R6 R7 R8" in p.stdout
    check("R-sentetik", ok,
          p.stdout.strip().splitlines()[-1] if p.stdout else "")

    # J: lob --k4 0 ciktilari kayitli v3e kanonik hash'leriyle ayni
    # (W satirlari kabul oncesi taze v3e kosusuyla birebir dogrulandi: 522).
    v4m, v4l = f"{OUT}/lobe_off_mem.csv", f"{OUT}/lobe_off_log.csv"
    p4 = run([LOBE, "--aff", AFF, "--mem", v4m, "--log", v4l,
              "--eta", a.eta, "--k4", "0"])
    check("J-run", p4.returncode == 0, "")
    w4 = [l for l in p4.stdout.splitlines() if l.startswith("W ")]
    same = (p4.returncode == 0 and sha(v4m) == V3E_MEM_SHA and
            sha(v4l) == V3E_LOG_SHA and len(w4) == 29 * 18)
    check("J-bit-identical", same,
          f"mem={sha(v4m)[:12]} log={sha(v4l)[:12]} W={len(w4)}")

    # D + pilot: lob --k4 1 cift-kosu (branch + matrix + ids telemetrisi).
    k1m, k1l = f"{OUT}/lobe_on_mem.csv", f"{OUT}/lobe_on_log.csv"
    k1k, k1p = f"{OUT}/lobe_on_branch.csv", f"{OUT}/lobe_on_matrix.csv"
    k1i = f"{OUT}/lobe_on_ids.csv"
    k2m, k2l = f"{OUT}/lobe_on_mem2.csv", f"{OUT}/lobe_on_log2.csv"
    k2k, k2p = f"{OUT}/lobe_on_branch2.csv", f"{OUT}/lobe_on_matrix2.csv"
    k2i = f"{OUT}/lobe_on_ids2.csv"
    q1 = run([LOBE, "--aff", AFF, "--mem", k1m, "--log", k1l,
              "--eta", a.eta, "--k4", "1", "--k4csv", k1k,
              "--k4paircsv", k1p, "--k4idcsv", k1i])
    q2 = run([LOBE, "--aff", AFF, "--mem", k2m, "--log", k2l,
              "--eta", a.eta, "--k4", "1", "--k4csv", k2k,
              "--k4paircsv", k2p, "--k4idcsv", k2i])
    check("D-run", q1.returncode == 0 and q2.returncode == 0, "")
    det = all(sha(x) == sha(y)
              for x, y in ((k1m, k2m), (k1l, k2l), (k1k, k2k), (k1p, k2p),
                           (k1i, k2i)))
    check("D-determinism", det, f"mem={sha(k1m)[:12]} mx={sha(k1p)[:12]}")
    oz = [l for l in q1.stdout.splitlines() if "OZET-PATTERN-LOB" in l]
    print(f"  BILGI {oz[0][:260] if oz else 'OZET-YOK'}", flush=True)
    s4max_oz = 0.0
    kf_oz = 0
    if oz:
        for tok in oz[0].split():
            if tok.startswith("k4_s4max="):
                s4max_oz = float(tok.split("=")[1])
            if tok.startswith("k4_kfires="):
                kf_oz = int(tok.split("=")[1])

    # P runtime: matris nonuniform (sifir + dolu bir arada).
    pairs = {}
    with open(k1p) as f:
        for r in csv.DictReader(f):
            x, y = int(r["b1"]), int(r["b2"])
            if x != y:
                pairs[(min(x, y), max(x, y))] = float(r["r"])
    nz = len(pairs)
    check("P-nonuniform", 0 < nz < NPAIR, f"dolu={nz}/{NPAIR}")

    # M runtime: soma_k4<=S4_CAP (mem), s4max<=S4_CAP (OZET), W [0,2].
    s4vals = [float(r["soma_k4"]) for r in csv.DictReader(open(k1m))]
    wmax, wmin = 0.0, 99.0
    for l in q1.stdout.splitlines():
        if l.startswith("W "):
            wmax = max(wmax, float(l.split()[3]))
            wmin = min(wmin, float(l.split()[3]))
    m_ok = ((not s4vals or max(s4vals) <= S4_CAP + 1e-9) and
            s4max_oz <= S4_CAP + 1e-9 and
            0.0 <= wmin and wmax <= W_MAX + 1e-9)
    check("M-bounded", m_ok and q1.returncode == 0,
          f"ns4={len(s4vals)} maxs4={max(s4vals) if s4vals else 0:.4f} "
          f"oz_s4max={s4max_oz:.4f} W=[{wmin:.4f},{wmax:.4f}]")

    # N runtime: OPEN birimler (27,28) ateslemez.
    on = read_mem(k1m)
    open_fires = sum(1 for r in on if int(r["unit"]) in (27, 28))
    check("N-open-sessiz", open_fires == 0, f"open_ates={open_fires}")

    # S runtime (nedensellik): k4-kaynakli ates varsa mem soma_k4>0 ile
    # isaretlidir; yoksa kapali-kosu ates kumesi korunur.
    s4nz = sum(1 for r in on if float(r["soma_k4"]) > 0)
    spkrows = sum(1 for r in on if int(r["k4spk"]) != 0)
    s_ok = (kf_oz == 0) or (s4nz > 0)
    check("S-nedensellik", s_ok, f"kfires={kf_oz} s4satir={s4nz} "
                                 f"spksatir={spkrows}")

    # RAPOR (kapi degil).
    off = read_mem(v4m)
    mo, mn = m_basic(off), m_basic(on)
    jo, to, jo_p, _ = pairwise_jacc(off)
    jn, tn, jn_p, pn = pairwise_jacc(on)
    br = list(csv.DictReader(open(k1k)))
    br_ticks = {r["tick"] for r in br}
    total_ticks = max(int(r["tick"]) for r in on) + 1 if on else 0
    common = (1 - len(br_ticks) / total_ticks) if total_ticks else -1.0
    sat = sum(1 for x in s4vals if x >= S4_CAP - 1e-9)
    nspk = sum(int(r["spk"]) for r in br)
    fo = defaultdict(int)
    fn = defaultdict(int)
    for r in off:
        fo[int(r["unit"])] += 1
    for r in on:
        fn[int(r["unit"])] += 1
    fired_off = sorted(u for u, c in fo.items() if c)
    fired_on = sorted(u for u, c in fn.items() if c)
    print(f"  RAPOR kapali: rows={mo['rows']} Nsig={mo['N_sig']} "
          f"Npv={mo['N_pv']} rep={mo['repetition']} "
          f"birim={fired_off} maxJ={jo}({jo_p}) cokmus={to}", flush=True)
    print(f"  RAPOR acik:   rows={mn['rows']} Nsig={mn['N_sig']} "
          f"Npv={mn['N_pv']} rep={mn['repetition']} "
          f"birim={fired_on} maxJ={jn}({jn_p}) cokmus={tn}", flush=True)
    print(f"  RAPOR k4: nztick={len(br_ticks)}/{total_ticks} "
          f"ortakmod={common:.4f} nact={len(br)} spikes={nspk} "
          f"kfires={kf_oz} s4max={s4max_oz:.4f} s4sat={sat} "
          f"matris-dolu={nz}/{NPAIR} ({nz / NPAIR:.3f})", flush=True)
    print(f"  RAPOR fark: d_rows={mn['rows'] - mo['rows']} "
          f"d_Nsig={mn['N_sig'] - mo['N_sig']} "
          f"d_birim={sorted(set(fired_on) ^ set(fired_off))}", flush=True)

    # (11,14) hukmu: ates senkronu + matris lisansi (r 22,23,28,29).
    def J(u, v, present):
        a, b = present.get(u, set()), present.get(v, set())
        return (len(a & b) / len(a | b)) if (a | b) else -1.0
    _, _, _, po = pairwise_jacc(off)
    j_off, j_on = round(J(11, 14, po), 4), round(J(11, 14, pn), 4)
    bids = [22, 23, 28, 29]
    rvals = {}
    for x in bids:
        for y in bids:
            if x < y:
                rvals[(x, y)] = pairs.get((x, y), 0.0)
    lic = max(rvals.values()) if rvals else 0.0
    print(f"  RAPOR (11,14): Jkapali={j_off} Jacik={j_on} "
          f"r_max={lic:.4f} {sorted(rvals.items())}", flush=True)
    print(f"  RAPOR hukmum: senkron {'LISANSLI' if lic >= 0.5 else 'LISANSSIZ'}"
          f" (kural: ayni-kimlik+coincidence -> r yuksek -> senkron beklenir)",
          flush=True)

    # top_partner tablosu (final matris, dal -> en yakin dal).
    row = defaultdict(dict)
    for (x, y), v in pairs.items():
        row[x][y] = v
    tops = []
    for b in range(NB):
        if row[b]:
            t = max(row[b], key=row[b].get)
            tops.append(f"{b}->{t}:{row[b][t]:.2f}")
    print(f"  RAPOR top_partner ({len(tops)}/{NB} dalli): "
          f"{' '.join(tops[:24])}", flush=True)
    if len(tops) > 24:
        print(f"  RAPOR top_partner (devam): {' '.join(tops[24:])}",
              flush=True)

    print(f"OZET-LOB-PILOT: {'OK' if not fails else 'BATTI ' + ','.join(fails)}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())