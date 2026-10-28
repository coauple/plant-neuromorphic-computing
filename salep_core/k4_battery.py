"""REV4 K4 davranis bataryasi — KARAKTERIZASYON (validated DEGIL).

Kural disiplini (on-kayitli, calisma sirasinda degismez):
- Frozen v3e K1/K2/K3/F1'e dokunulmaz; REV4 K4 mekanizmasi (onayli, §9.95)
  calisma sirasinda degistirilmez.
- REV4 metrik-anlam notu (karsilastirilabilirlik icin kayitli, metrikler
  AYNI kalir): branch act = K4 kapili voltaji (sinirsiz salim; REV3'teki
  cap'li toplam DEGIL); drive = dal S4 salimi; top = MEKANIK argmax;
  rel_sat (r>=0.999) REV4 tavani 0.875 oldugundan ~0 beklenir; common_mode
  operasyonel tanimi ayni (act>0) ama REV4'te yogun cikar; mem acik-kosuda
  +2 kolon (soma_k4,k4spk), DictReader uyumlu.
- Yeni mekanizma/feature/phase/tau/sin/cos/global-similarity yok.
- Parametre optimizasyonu YOK (eta 0 / 0.30 ve K4 0/1 disinda ayar yok).
- Condition label K4 relation formation / pattern generation / plasticity
  icine GIRMEZ (lobe'a giden CSV'de label="" bos; manifest.json yalniz
  sonradan analizde kullanilir).
- Basarisiz sonuc = kod degisikligi sebebi DEGIL, raporlanir.
- Deterministik: bitki seed sabit (I grubu haric 42); sentetik RNG
  random.Random(acik seed).
- Full battery bitmeden "validated" hukmu YOK.

HAT (mevcut sistem, sifirdan simulasyon YOK):
  bitki: drive_line_front.py -> sensors/pspikes -> npu_sensory_plant --aff
  sentetik: dogrudan afferent.csv (encoder run_chain asamasindan gecer)
  tuketim: run_chain_v3 asamaları (intake/encoder/adapter) + buradaki lob
  asamasi (cift-kosu sha determinizm kapili, --k4csv/--k4paircsv ile).

KOSULLAR (4):
  base      = K4 OFF, eta 0        | k4static = K4 ON, eta 0
  plastic   = K4 OFF, eta 0.30     | k4plastic = K4 ON, eta 0.30

OPERASYONEL TANIMLAR (olcu durustlugu):
- Afferentte genlik alani YOKTUR (binary olay). "siddet" = ayni tick'teki
  eszamanli slot sayisi x tekrar (strong 4x3, medium 2x2, weak 1x1,
  veryweak 1x1 tek). Bu biyofiziksel genlik iddiasi DEGIL, operasyonel
  siddet merdivenidir.
- "eslesen partner" = AYNi slot kumesi (ayni dallari surer);
  "nonmatching" = AYRİK slot kumesi. Dal kimligi olculur (k4_branch.csv),
  varsayilmaz (donuk tablo koda gomulmedi).
- common-mode (on-kayitli): act>0 dal sayisi >=29 olan tick'lerin,
  act>0 iceren tick'lere orani (29 = 58 dalin yarisi).
- relation lifetime VEKILDIR (binary matris ara-dokumu vermez): dal basina
  act>0 kosularinin ortalama uzunlugu (tick). Yorum degil olcudur; basligi
  "lifetime_proxy"dir.
- insect/fungus: drive_line_front bayragi YOK + kural yeni-feature yasagi
  -> TEST EDILEMEDI (durust kayit; fungus+drought dahil).
- rain+humidity: nem dugmesi yok -> W-wet VEKILDIR (raporlanir).
- ZCAL kalibrasyon: tek-slot burst'larindan olcumsel slot->dal haritasi
  (C/F yorumunda kullanilir; olusuma girmez). matrix.csv yonlu cift
  yazar -> metrikler TEKIL cift uzerinden (duzeltme kayitli).

Kullanim: .venv/bin/python k4_battery.py [--only A,B1,C] [--outdir D]
"""

import argparse
import csv
import hashlib
import json
import math
import os
import random
import statistics as st
import subprocess
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "encoder"))
import run_chain_v3 as C  # noqa: E402 (asamalar: intake/encoder/adapter)
import pattern_stress_v3 as P  # noqa: E402 (m_basic/tickvec/day_jacc)
from validate_infer_pattern import day_sig, infer  # noqa: E402

BIN = os.path.join(ROOT, "npu_pattern_lobe")
PLANT = os.path.join(ROOT, "npu_sensory_plant")
WV = os.path.join(ROOT, "weather_v3")
WB = f"{WV}/W-base.csv"
OUTBASE = os.environ.get("K4BAT_BASE", "/tmp/k4bat")
DAYS = 130  # emsal rejim (pattern_stress_v3): cond = 130//10-3 = 10
SEED = 42
ETAS = {"eta0": "0", "eta03": "0.30"}
CONDS = ["base", "k4static", "plastic", "k4plastic"]  # k4: 0,1,0,1
K4FLAG = {"base": "0", "k4static": "1", "plastic": "0", "k4plastic": "1"}
K4ETA = {"base": "eta0", "k4static": "eta0",
         "plastic": "eta03", "k4plastic": "eta03"}
NBR = 58
NPAIR = NBR * (NBR - 1) // 2  # 1653

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
                          timeout=1200)


# ---------------- bitki senaryolari (A/B): drive_line_front bayraklari ----
# Hepsine weather=WB eklenir (yazilmamissa). days=DAYS, seed=SEED sabit.
PLANT_SCEN = {
    # A) NORMAL / TEKIL
    "A_base": {},
    "A_drought_mild": {"drought": True, "drought_from": 40,
                       "drought_len": 10},
    "A_drought_severe": {"drought": True, "drought_from": 20,
                         "drought_len": 30},
    "A_heat": {"weather": f"{WV}/W-hot.csv"},
    "A_cold": {"weather": f"{WV}/W-cold.csv"},
    "A_ec": {"fert": 80.0},
    "A_irrigation": {"irrig": 20.0},
    "A_rain": {"weather": f"{WV}/W-wet.csv"},  # VEKIL (yagmur-dosyasi)
    "A_recovery": {"drought": True, "drought_from": 10,
                   "drought_len": 15},  # erken kuraklik + temiz devam
    # B) KOMBINASYON
    "B_drought_heat": {"drought": True, "drought_from": 40,
                       "drought_len": 10, "weather": f"{WV}/W-hot.csv"},
    "B_drought_ec": {"drought": True, "drought_from": 40,
                     "drought_len": 10, "fert": 40.0},
    "B_heat_ec": {"weather": f"{WV}/W-hot.csv", "fert": 40.0},
    "B_rain_humid": {"weather": f"{WV}/W-wet.csv"},  # VEKIL (nem dugmesi yok)
    "B_drought_irrig": {"drought": True, "drought_from": 10,
                        "drought_len": 15, "irrig": 20.0,
                        "irrig_from": 30, "irrig_len": 10},
    "B_heat_recovery": {"weather": f"{WV}/W-hot.csv"},  # VEKIL: zaman-dilimli
    "B_ec_wash": {"fert": 60.0, "fert_from": 10, "fert_len": 10,
                  "irrig": 25.0, "irrig_from": 25, "irrig_len": 10},
}
SKIP_SCEN = {"A_insect": "bocek modeli yok (drive bayragi yok)",
             "A_fungus": "patojen bayragi yok (events.py'de var, front'ta yok;"
                         " yeni feature yasak)",
             "B_fungus_drought": "fungus test edilemedigi icin"}


# ---------------- sentetik kablo ureteci (C-J) -----------------------------
# Afferent satiri: tick,post_id,tau_b + tasiyici kolonlar (label BOS).
# Slotlar: post 0..7, tau sabit 35 (on-kayitli keyfi deger; davranis
# farki slot deseninden gelir, tau'dan degil).
AFF_HEAD = ["tick", "post_id", "tau_b", "a0lag", "a1lag", "bmask", "bwin",
            "label", "w"]
SLOT_TAU = 35
SA = [0, 1]
SB = [2, 3]
SC = [4, 5]
SD = [6, 7]
A1, B2, C1, C2, C3 = [0], [3], [4], [5], [6]


def aff_rows(events):
    """events: [(tick, post)] -> header'li satirlar (label bos)."""
    rows = [AFF_HEAD]
    for t, p in sorted(events):
        rows.append([t, p, SLOT_TAU, -1, -1, "0000000000", "0000000000",
                     "", 0.2])
    return rows


def burst(tick, slots, reps=1, gap=20, t0=0):
    """Her rep'te tum slotlar ayni tick (eszamanli burst)."""
    ev = []
    for r in range(reps):
        t = t0 + tick + r * gap
        for s in slots:
            ev.append((t, s))
    return ev


def stream(slots, t0, t1, period):
    ev = []
    for t in range(t0, t1, period):
        for s in slots:
            ev.append((t, s))
    return ev


def build_synthetic():
    """-> {scen_id: {'rows': [...], 'label': str}}; label lob'a GITMEZ."""
    S = {}

    def put(sid, ev, label):
        S[sid] = {"rows": aff_rows(ev), "label": label}

    # C) TEMPORAL COINCIDENCE: A(={0,1}) + B(={2,3}), periyot 40, 600 tick.
    for off in (0, 1, 5, 9, 10, 11):
        ev = stream(SA, 0, 600, 40) + stream(SB, off, 600, 40)
        put(f"C_AB_off{off}", ev, f"C:A+B off={off}")
        ev2 = stream(SB, 0, 600, 40) + stream(SA, off, 600, 40)
        put(f"C_BA_off{off}", ev2, f"C:B+A off={off} (reversed)")
    # C2) AYRIK AKIMLAR (ZCAL olcumu: slot0/slot5 surusleri ayrik).
    # C'de SA/sB dallari olcusel olarak icice cikti (SA⊂SB) -> capraz
    # kumesi bos kaldi; C2 ayni soruyu ayrik akimla sorar (sapma kayitli).
    S0, S1 = [0], [5]
    for off in (0, 1, 5, 9, 10, 11):
        put(f"C2_AB_off{off}", stream(S0, 0, 600, 40) +
            stream(S1, off, 600, 40), f"C2:A+B off={off} (ayrik)")
        put(f"C2_BA_off{off}", stream(S1, 0, 600, 40) +
            stream(S0, off, 600, 40), f"C2:B+A off={off} (ayrik,rev)")
    # D) WEAK-SIGNAL: guc merdiveni x partner.
    strength = {"strong": (SA + SB, 3), "medium": (SA, 2),
                "weak": ([0], 1), "veryweak": ([1], 1)}
    for sname, (slots, reps) in strength.items():
        base = burst(100, slots, reps)
        put(f"D_{sname}_none", base, f"D:{sname} partnersiz")
        put(f"D_{sname}_matching", base + burst(100, slots, reps),
            f"D:{sname} eslesen")
        other = SC + SD if set(slots) <= set(SA + SB) else SA + SB
        put(f"D_{sname}_nonmatching", base + burst(100, other, reps),
            f"D:{sname} nonmatching")
        put(f"D_{sname}_delayed", base + burst(115, slots, reps),
            f"D:{sname} gecikmeli(+15)")
    # E) COMBINATORIAL (hepsi t=100'de burst x2, gap 30).
    combos = {"ApB": SA + SB, "ApC": SA + SC, "BpD": SB + SD,
              "ApCpD": SA + SC + SD, "ApBpC": SA + SB + SC,
              "ApBpD": SA + SB + SD, "ApBpCpD": SA + SB + SC + SD}
    for cname, slots in combos.items():
        put(f"E_{cname}", burst(100, slots, 2, 30), f"E:{cname}")
    # F) PERMUTATION (parcalar farkli dallara).
    put("F_A1B2", burst(100, A1 + B2, 2, 30), "F:A1+B2")
    put("F_A1C2", burst(100, A1 + C2, 2, 30), "F:A1+C2")
    put("F_C1B2", burst(100, C1 + B2, 2, 30), "F:C1+B2")
    put("F_A1B2C3", burst(100, A1 + B2 + C3, 2, 30), "F:A1+B2+C3")
    # G) HISTORY: gecmis blok (t 0..300) + prob X (t 320, SA+SC burst x1).
    hist = {"none": [], "AB": stream(SA + SB, 0, 300, 30),
            "AC": stream(SA + SC, 0, 300, 30),
            "mixed": stream(SA + SB, 0, 150, 30) +
            stream(SA + SC, 150, 300, 30)}
    for hname, hev in hist.items():
        for gap, gname in ((5, "short"), (200, "long")):
            put(f"G_{hname}_{gname}", hev + burst(320 + gap - 5, SA + SC, 1),
                f"G:gecmis={hname} prob-gap={gname}")
    # H) UNSUPERVISED: plant kablo kullanir (asamada uretilir); yer tutucu yok.
    # I) ROBUSTNESS: referans + bozunumlar (R=Random(1000+i)).
    ref = stream(SA + SB, 0, 600, 40) + stream(SC, 200, 600, 40)
    put("I_ref", ref, "I:referans")
    rng = random.Random(1001)
    ev = [(t + rng.choice((-1, 0, 0, 1)), p) for t, p in ref if t > 0]
    put("I_jitter", ev, "I:+-1 tick jitter")
    ev = [(t, p) for t, p in ref if rng.random() > 0.20]
    put("I_dropout", ev, "I:%20 dropout")
    ev = list(ref) + [(rng.randrange(0, 600), rng.randrange(0, 8))
                      for _ in range(len(ref) // 20)]
    put("I_noise", ev, "I:%5 gurultu")
    ev = [(t, p) for t, p in ref if p not in SC]  # bir dal sustu
    put("I_silenced", ev, "I:SC susturuldu")
    ev = [(t + (15 if p in SC else 0), p) for t, p in ref]
    put("I_delayed", ev, "I:partner +15")
    amps = [(t, p) for t, p in ref if not (p == 1 and rng.random() < 0.5)]
    put("I_amp", amps, "I:genlik bozunumu")
    # ZCAL) KALIBRASYON (olcumsel slot->dal haritasi; yorumda kullanilir,
    # olusuma girmez): tek slot burst'u, act>0 dallar = o slotun surdukleri.
    for s in range(8):
        put(f"ZCAL_slot{s}", burst(100, [s], 3, 30), f"ZCAL:slot{s}")
    # J) ADVERSARIAL.
    all8 = [0, 1, 2, 3, 4, 5, 6, 7]
    put("J_masscoin", burst(0, all8, 20, 30), "J:8-slot x20 coincidence")
    put("J_cont", stream([0, 1], 0, 200, 1), "J:surekli event 200tick")
    put("J_allsync", burst(0, all8, 5, 40), "J:tum-dal eszamanli x5")
    put("J_overdrive", stream([0], 0, 600, 3), "J:tek dal asiri x200")
    put("J_constid", stream(SA, 0, 600, 20), "J:surekli ayni kimlik")
    ev = []
    for k in range(20):
        part = [SA, SB, SC, SD][k % 4]
        ev += burst(k * 30, SA, 1) + burst(k * 30, part, 1)
    put("J_churn", ev, "J:surekli degisen partner")
    # kimlik siniri: referans dal deseni SA+SB'ye karsi agree degiskenleri.
    # (agree lob-icinde olculur; burada slot-ortusme merdiveni verilir.)
    put("J_agree1", burst(100, [0, 4, 6], 3, 30), "J:ortusme-1/3")
    put("J_agree2", burst(100, [0, 1, 4], 3, 30), "J:ortusme-2/3")
    put("J_agree3", burst(100, [0, 1, 2], 3, 30), "J:ortusme-3/3")
    return S


# ---------------- kosucu ---------------------------------------------------
def front(outdir, seed=SEED, days=DAYS, **kw):
    """Bitki onu: drive_line_front (sistem pythonu ile)."""
    os.makedirs(outdir, exist_ok=True)
    cmd = [sys.executable, os.path.join(ROOT, "drive_line_front.py"),
           "--seed", str(seed), "--days", str(days), "--outdir", outdir]
    for k, v in kw.items():
        fl = f"--{k}".replace("_", "-")
        cmd += [fl, str(v)] if v is not True else [fl]
    p = run(cmd)
    assert p.returncode == 0, p.stderr[-500:]
    return outdir


def plant_aff(d, cond=None, test=3):
    """Duyusal lob: npu_sensory_plant --aff (mevcut binary, degismez)."""
    p = run([PLANT, "--spikes", f"{d}/pspikes.csv", "--sensors",
             f"{d}/sensors.csv", "--out", f"{d}/plant_out.csv",
             "--aff", f"{d}/afferent.csv",
             "--cond", str(cond), "--test", str(test)])
    assert p.returncode == 0, p.stderr[-500:]
    return f"{d}/afferent.csv"


def write_aff(path, rows):
    with open(path, "w", newline="") as f:
        csv.writer(f).writerows(rows)


def stage_lobe(aff_in, outdir, k4, eta):
    """Tuketim: run_chain asamaları + lob (cift-kosu determinizm kapili).

    k4 "0"/"1" acikca verilir; --k4csv/--k4paircsv her kosuda istenir
    (k4 kapaliysa binary yazmaz -> metrikler bos okunur)."""
    os.makedirs(outdir, exist_ok=True)
    aff_p, evs, full, _ = C.stage_intake(aff_in, outdir)
    _, spk = C.stage_encoder(evs, outdir)
    aff2 = C.stage_adapter(spk, evs, full, outdir)
    outs = {"mem": os.path.join(outdir, "mem.csv"),
            "log": os.path.join(outdir, "log.csv"),
            "branch": os.path.join(outdir, "branch.csv"),
            "matrix": os.path.join(outdir, "matrix.csv")}
    base = dict(outs)
    for tag in ("", ".chk"):
        paths = {k: v + tag for k, v in base.items()}
        p = run([BIN, "--aff", aff2, "--mem", paths["mem"],
                 "--log", paths["log"], "--eta", eta, "--k4", k4,
                 "--k4csv", paths["branch"], "--k4paircsv", paths["matrix"]])
        assert p.returncode == 0, p.stderr[-500:]
        if not tag:
            outs["ozet"] = [l for l in p.stdout.splitlines()
                            if "OZET-PATTERN-LOB" in l]
    assert sha(outs["mem"]) == sha(outs["mem"] + ".chk"), "DETERMINISTIK DEGIL"
    assert sha(outs["log"]) == sha(outs["log"] + ".chk"), "DETERMINISTIK DEGIL"
    return outs


# ---------------- metrik motoru --------------------------------------------
def read_csv_rows(p):
    if not os.path.isfile(p):
        return []
    with open(p) as f:
        return list(csv.DictReader(f))


def jaccard_sets(a, b):
    a, b = set(a), set(b)
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b) if (a | b) else -1.0


def unit_jaccards(mem):
    tv = P.tickvec(mem)
    present = defaultdict(set)
    for t, s in tv.items():
        for u in s:
            present[u].add(t)
    units = sorted(present)
    vals = []
    for i in range(len(units)):
        for j in range(i + 1, len(units)):
            a, b = present[units[i]], present[units[j]]
            vals.append(len(a & b) / len(a | b) if (a | b) else 1.0)
    if not vals:
        return {"max": -1.0, "mean": -1.0, "n": 0}
    return {"max": round(max(vals), 4), "mean": round(st.mean(vals), 4),
            "n": len(vals)}


def k4_metrics(outs):
    """branch.csv + matrix.csv -> relational metrikler (k4 kapaliysa bos)."""
    br = read_csv_rows(outs.get("branch", ""))
    mx = read_csv_rows(outs.get("matrix", ""))
    m = {"k4_cells": len(br), "k4_ticks": 0, "k4_energy": 0.0,
         "active_k4": [], "common_mode": -1.0, "mean_r": 0.0, "max_r": 0.0,
         "rel_nz": 0, "rel_sat": 0, "density": 0.0, "lifetime_proxy": -1.0,
         "top": {}, "turnover": -1}
    if not br and not mx:
        return m
    per_tick = defaultdict(set)
    per_branch = defaultdict(list)
    energy = 0.0
    for r in br:
        b = (int(r["birim"]), int(r["dal"]))
        per_tick[int(r["tick"])].add(b)
        per_branch[b].append(int(r["tick"]))
        energy += float(r["act"])
    m["k4_cells"] = len(br)
    m["k4_ticks"] = len(per_tick)
    m["k4_energy"] = round(energy, 4)
    m["active_k4"] = sorted(f"{u}.{d}" for u, d in per_branch)
    if per_tick:
        big = sum(1 for s in per_tick.values() if len(s) >= 29)
        m["common_mode"] = round(big / len(per_tick), 4)
    runs = []
    for ts in per_branch.values():
        ts = sorted(ts)
        run, best = 1, 1
        for a, b in zip(ts, ts[1:]):
            run = run + 1 if b == a + 1 else 1
            best = max(best, run)
        runs.append(best)
    m["lifetime_proxy"] = round(st.mean(runs), 2) if runs else -1.0
    # matrix.csv yonlu ciftleri icerir (a,b)+(b,a); metrikler TEKIL cift
    # uzerinden (duzeltme: yonlu sayim density'yi 2x sisiriyordu).
    uniq = {}
    for r in mx:
        a, b = int(r["b1"]), int(r["b2"])
        if a == b:
            continue
        uniq[(min(a, b), max(a, b))] = float(r["r"])
    rels = list(uniq.values())
    if rels:
        m["mean_r"] = round(st.mean(rels), 6)
        m["max_r"] = round(max(rels), 6)
        m["rel_nz"] = len(rels)
        m["rel_sat"] = sum(1 for v in rels if v >= 0.999)
        m["density"] = round(len(rels) / NPAIR, 4)
    row = defaultdict(dict)
    for (a, b), v in uniq.items():
        row[a][b] = v
        row[b][a] = v
    for b, d in row.items():
        if d:
            t = max(d, key=d.get)
            m["top"][str(b)] = [t, round(d[t], 4)]
    # turnover: dort ceyrekte modal top-partner degistiren dal sayisi
    # (branch.csv topartner kolonu; partner degisimi olcusudur).
    if br:
        ticks = sorted(per_tick)
        q = max(1, len(ticks) // 4)
        modal = {}
        for i in range(4):
            seg = set(ticks[i * q:(i + 1) * q])
            votes = defaultdict(lambda: defaultdict(int))
            for r in br:
                if int(r["tick"]) in seg:
                    votes[(int(r["birim"]), int(r["dal"]))][
                        int(r["toppartner"])] += 1
            for b, c in votes.items():
                modal.setdefault(b, []).append(max(c, key=c.get))
        m["turnover"] = sum(1 for v in modal.values() if len(set(v)) > 1)
    return m


def cond_metrics(outs):
    mem = outs["mem"]
    with open(mem) as f:
        nrows = sum(1 for _ in f) - 1
    if nrows <= 0:
        basic = {"rows": 0, "N_sig": 0, "N_pv": 0, "repetition": -1.0,
                 "ISI": (-1, -1, 0), "stabilite": -1.0, "days": 0,
                 "units": []}
    else:
        basic = P.m_basic(mem)
    j = unit_jaccards(mem)
    k = k4_metrics(outs)
    return {"basic": basic, "jacc": j, "k4": k,
            "sha": sha(mem)[:12]}


# ---------------- orkestrasyon ---------------------------------------------
RESULTS = {}
MANIFEST = {}


def run_case(scen, aff, label):
    """Ayni kablo x 4 kosul. Donus: {cond: metrics}."""
    MANIFEST[scen] = {"label": label, "aff": aff}
    out = {}
    for cond in CONDS:
        d = os.path.join(OUTBASE, scen, cond)
        outs = stage_lobe(aff, d, K4FLAG[cond], ETAS[K4ETA[cond]])
        out[cond] = cond_metrics(outs)
        b = out[cond]["basic"]
        print(f"  [{scen}/{cond}] rows={b['rows']} Nsig={b['N_sig']} "
              f"units={len(b['units'])} sha={out[cond]['sha']}", flush=True)
    RESULTS[scen] = out
    return out


def plant_group():
    print("GRUP A/B (bitki, sistem hatti):", flush=True)
    for scen, kw in PLANT_SCEN.items():
        kw = dict(kw)
        kw.setdefault("weather", WB)
        d = front(os.path.join(OUTBASE, scen, "front"), **kw)
        cond_n = DAYS // 10 - 3
        aff = plant_aff(d, cond=cond_n)
        run_case(scen, aff, f"plant:{scen}")
    for scen, why in SKIP_SCEN.items():
        MANIFEST[scen] = {"label": f"SKIP: {why}", "aff": None}
        print(f"  [{scen}] SKIP ({why})", flush=True)


def synth_group():
    print("GRUP C-J (sentetik kablo, ayni tuketim hatti):", flush=True)
    for scen, s in build_synthetic().items():
        p = os.path.join(OUTBASE, scen, "cable.csv")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        write_aff(p, s["rows"])
        run_case(scen, p, s["label"])


def retrieval_on(mems_labels):
    """LOO nearest-sequence (pattern_stressv3.awins_of benzeri, sade).

    Label yalniz burada, sonradan-analizde kullanilir."""
    wins = []
    for i, (mem, lab) in enumerate(mems_labels):
        by = day_sig(list(csv.DictReader(open(mem))))
        days = sorted(by)
        for j in range(len(days) - 3 + 1):
            ds = days[j:j + 3]
            if ds != list(range(ds[0], ds[0] + 3)):
                continue
            seq = tuple({"posts": by.get(x, set()), "blines": set(),
                         "a": set()} for x in ds)
            if not any(sg["posts"] for sg in seq):
                continue
            wins.append({"s": ds[0] + i * 100000, "seq": seq, "label": lab})
    if len(wins) < 4:
        return -1.0, len(wins)
    cm, _ = infer(wins)
    tot = sum(cm.values())
    ok = sum(v for (t, p), v in cm.items() if t == p)
    return round(ok / tot, 4) if tot else -1.0, tot


def cond_sep(group_prefix, cond):
    """Ayni-kosul ici vs kosullar-arasi mean r (H; label sonradan)."""
    mats = {}
    for scen, out in RESULTS.items():
        if not scen.startswith(group_prefix):
            continue
        p = os.path.join(OUTBASE, scen, cond, "matrix.csv")
        vals = [float(r["r"]) for r in read_csv_rows(p)]
        if vals:
            mats[scen] = vals
    within, across = [], []
    keys = sorted(mats)
    for i in range(len(keys)):
        within += mats[keys[i]]
        for j in range(i + 1, len(keys)):
            a, b = mats[keys[i]], mats[keys[j]]
            across.append(abs(st.mean(a) - st.mean(b)))
    return (round(st.mean(within), 6) if within else 0.0,
            round(st.mean(across), 6) if across else 0.0)


def slotmap():
    """Olcumsel slot->dal haritasi (ZCAL kosulari, k4static).

    act>0 <=> dalin kendisi olay aldi (coin kendi evt'sini ister; sessiz
    dal yapisal olarak act=0 alir). Donus: {slot: {(birim,dal)}}."""
    m = {}
    for s in range(8):
        br = read_csv_rows(os.path.join(OUTBASE, f"ZCAL_slot{s}",
                                        "k4static", "branch.csv"))
        m[s] = {(int(r["birim"]), int(r["dal"])) for r in br}
    return m


def crosstalk(scen, off, cond, smap):
    """C grubu cift-turu ayrıştırması (sonradan-analiz, mekanizmaya dokunmaz).

    Dalin akim bagliligi ZCAL haritasindan: stream0/1 slotlarinin surdugu
    dallar. cross = yalnizca-karsi-akim ciftleri; within = ayni-akim.
    Donus: (cross, within, n_cross, n_within)."""
    if scen.startswith("C_AB"):
        s0, s1 = set(SA), set(SB)
    elif scen.startswith("C_BA"):
        s0, s1 = set(SB), set(SA)
    elif scen.startswith("C2_AB"):
        s0, s1 = {0}, {5}
    else:
        s0, s1 = {5}, {0}
    B0 = set().union(*(smap[s] for s in s0)) if s0 else set()
    B1 = set().union(*(smap[s] for s in s1)) if s1 else set()
    only0, only1 = B0 - B1, B1 - B0
    mx = read_csv_rows(os.path.join(OUTBASE, scen, cond, "matrix.csv"))
    uniq = {}
    for r in mx:
        a, b = int(r["b1"]), int(r["b2"])
        if a != b:
            uniq[(min(a, b), max(a, b))] = float(r["r"])
    bid = lambda u, d: u * 2 + d
    O0 = {bid(u, d) for u, d in only0}
    O1 = {bid(u, d) for u, d in only1}
    cross, within = [], []
    for (a, b), v in uniq.items():
        ina0, inb0 = a in O0, b in O0
        ina1, inb1 = a in O1, b in O1
        if (ina0 and inb1) or (ina1 and inb0):
            cross.append(v)
        elif (ina0 and inb0) or (ina1 and inb1):
            within.append(v)

    def avg(x):
        return round(st.mean(x), 4) if x else -1.0
    return (avg(cross), avg(within), len(cross), len(within))


def seed_robustness(scen_a, scen_b):
    """Iki kosu arasi gun-imza Jaccard (I grubu; eksikse n/a)."""
    out = {}
    for cond in CONDS:
        ma = os.path.join(OUTBASE, scen_a, cond, "mem.csv")
        mb = os.path.join(OUTBASE, scen_b, cond, "mem.csv")
        if not (os.path.isfile(ma) and os.path.isfile(mb)):
            out[cond] = "n/a"
            continue
        out[cond] = round(P.day_jacc(P.daysig(ma), P.daysig(mb)), 4)
    return out


def plast_delta(scen, c_static, c_plast):
    a = RESULTS[scen][c_static]["basic"]
    b = RESULTS[scen][c_plast]["basic"]
    return {"d_rows": b["rows"] - a["rows"],
            "d_units": len(b["units"]) - len(a["units"]),
            "d_Nsig": b["N_sig"] - a["N_sig"]}


# ---------------- rapor ------------------------------------------------------
MEASURED_VS_OPINION = """\
OLCU/YORUM AYRIMI (on-kayitli kural):
- OLCU: CSV'den dogrudan okunan sayilar (Nsig, rows, r degerleri, Jaccard,
  sha esitlikleri, act seyrI). Yorum rubriksi "YORUM:" ile baslar.
- YORUM: sayilarin davranissal anlami (rescue, collapse, cesitlilik...).
  Yorumlar kanit DEGILDIR, gozlem ozetidir; "validated" hukmu YOKTUR.
"""


def fmt_basic(m):
    b = m["basic"]
    return (f"rows={b['rows']} Nsig={b['N_sig']} Npv={b['N_pv']} "
            f"rep={b['repetition']} P3={len(b['units'])}")


def fmt_k4(m):
    k = m["k4"]
    return (f"K4cell={k['k4_cells']} E={k['k4_energy']} dens={k['density']} "
            f"sat={k['rel_sat']} cm={k['common_mode']} maxr={k['max_r']} "
            f"turn={k['turnover']}")


def write_report(path):
    L = []
    A = L.append
    A("# K4 BATARYA RAPORU — KARAKTERIZASYON (validated DEGIL)\n")
    A(MEASURED_VS_OPINION)
    A("\n## Kosullar\nbase=K4 OFF/eta0, k4static=K4 ON/eta0, "
      "plastic=K4 OFF/eta0.30, k4plastic=K4 ON/eta0.30.\n")

    A("\n## A) MECHANICAL\n")
    A("Cift-kosu sha determinizm kapisi tum kosul x senaryoda GECTI "
      "(aksi halde kosu assert ile dururdu; fails listesi asagida). "
      "Encoder 1:1 + adapter roundtrip run_chain asamasinda kapili.\n")
    A(f"fails={fails if fails else 'yok'}\n")

    A("\n## B) SELECTIVITY\n")
    for scen in sorted(RESULTS):
        if scen.startswith("D_") or scen.startswith("J_agree"):
            o = RESULTS[scen]
            A(f"- {scen}: " + " | ".join(
                f"{c}:[{fmt_k4(o[c])}]" for c in CONDS) + "\n")

    A("\n## C) PATTERN DIVERSITY\n")
    for scen in sorted(RESULTS):
        if scen.startswith(("A_", "B_", "E_", "F_")):
            o = RESULTS[scen]
            A(f"- {scen}: " + " | ".join(
                f"{c}:[{fmt_basic(o[c])}]" for c in CONDS) + "\n")

    A("\n## D) TEMPORAL BEHAVIOR\n")
    smap = slotmap()
    A(f"- ZCAL slot->dal (k4static, olcumsel): " +
      "; ".join(f"s{s}={sorted(f'{u}.{d}' for u, d in smap[s])}"
                for s in range(8)) + " [KALIBRASYON]\n")
    for scen in sorted(RESULTS):
        if scen.startswith("C_") or scen.startswith("C2_"):
            o = RESULTS[scen]
            A(f"- {scen}: " + " | ".join(
                f"{c}:[rows={o[c]['basic']['rows']} "
                f"E={o[c]['k4']['k4_energy']} "
                f"maxr={o[c]['k4']['max_r']}]" for c in CONDS) + "\n")
            try:
                off = int(scen.rsplit("off", 1)[1])
            except ValueError:
                off = -1
            if off >= 0:
                for c in ("k4static", "k4plastic"):
                    cr, wn, nc, nw = crosstalk(scen, off, c, smap)
                    A(f"  - {scen}/{c}: cross_r={cr} within_r={wn} "
                      f"(n_cross={nc} n_within={nw}) "
                      f"[cift-turu ayristirmasi, sonradan-analiz]\n")

    A("\n## E) RELATIONAL BEHAVIOR\n")
    for scen in sorted(RESULTS):
        if scen.startswith(("E_", "F_")):
            o = RESULTS[scen]
            A(f"- {scen}: " + " | ".join(
                f"{c}:[dens={o[c]['k4']['density']} "
                f"meanr={o[c]['k4']['mean_r']} "
                f"turn={o[c]['k4']['turnover']}]" for c in CONDS) + "\n")
    for prefix in ("A_", "B_"):
        for cond in ("k4static", "k4plastic"):
            w, ac = cond_sep(prefix, cond)
            A(f"- {prefix} {cond}: ayni-kosul-ici mean_r={w}, "
              f"kosullar-arasi fark={ac} (H metodu, label sonradan)\n")

    A("\n## F) PLASTICITY\n")
    for scen in sorted(RESULTS):
        if scen.startswith(("A_", "B_", "G_")):
            d1 = plast_delta(scen, "base", "plastic")
            d2 = plast_delta(scen, "k4static", "k4plastic")
            A(f"- {scen}: K4suz plastisite {d1} | K4lu plastisite {d2}\n")

    A("\n## G) ROBUSTNESS\n")
    r = seed_robustness("I_ref", "I_jitter")
    A(f"- jitter robustlugu (gun-imza Jaccard): {r}\n")
    for s in ("I_dropout", "I_noise", "I_silenced", "I_delayed", "I_amp"):
        o = RESULTS.get(s)
        if o:
            A(f"- {s}: " + " | ".join(
                f"{c}:[{fmt_basic(o[c])}]" for c in CONDS) + "\n")

    A("\n## H) FAILURE MODES\n")
    for scen in sorted(RESULTS):
        if scen.startswith("J_"):
            o = RESULTS[scen]
            A(f"- {scen}: " + " | ".join(
                f"{c}:[rows={o[c]['basic']['rows']} "
                f"cm={o[c]['k4']['common_mode']} "
                f"sat={o[c]['k4']['rel_sat']} "
                f"maxJ={o[c]['jacc']['max']}]" for c in CONDS) + "\n")

    A("\n## I) EMERGENT BEHAVIOR (otomatik tarama + YORUM)\n")
    # I1: BASE'de olmayan yeni imzalar (k4static/k4plastic gun-imzalari).
    for scen in sorted(RESULTS):
        if scen.startswith(("A_", "B_", "E_", "F_")):
            for c in ("k4static", "k4plastic"):
                ma = os.path.join(OUTBASE, scen, "base", "mem.csv")
                mb = os.path.join(OUTBASE, scen, c, "mem.csv")
                sa = {frozenset(s) for s in
                      P.daysig(ma).values() if s} if os.path.isfile(ma) \
                    else set()
                sb = {frozenset(s) for s in
                      P.daysig(mb).values() if s} if os.path.isfile(mb) \
                    else set()
                A(f"- I1 {scen}/{c}: yeni imza={len(sb - sa)} "
                  f"(base={len(sa)}, {c}={len(sb)}) [OLCU]\n")
    # I2: ayni parcalar farkli duzen (F grubu matris farki).
    fsc = sorted(s for s in RESULTS if s.startswith("F_"))
    for i in range(len(fsc)):
        for j in range(i + 1, len(fsc)):
            ds = {}
            for cond in ("k4static", "k4plastic"):
                pa = os.path.join(OUTBASE, fsc[i], cond, "matrix.csv")
                pb = os.path.join(OUTBASE, fsc[j], cond, "matrix.csv")
                ra = {f"{r['b1']},{r['b2']}" for r in read_csv_rows(pa)}
                rb = {f"{r['b1']},{r['b2']}" for r in read_csv_rows(pb)}
                ds[cond] = round(
                    len(ra ^ rb) / len(ra | rb), 4) if (ra | rb) else -1.0
            A(f"- I2 {fsc[i]} vs {fsc[j]}: matris simetrik-fark={ds} [OLCU]\n")
    # I3: ayni prob X, farkli gecmis (G grubu prob penceresi karsilastirma).
    A("- I3 G grubu prob-yaniti: asagida G satirlari [OLCU]\n")
    for scen in sorted(RESULTS):
        if scen.startswith("G_"):
            o = RESULTS[scen]
            A(f"  - {scen}: " + " | ".join(
                f"{c}:[{fmt_basic(o[c])}]" for c in CONDS) + "\n")
    # I4: zayif dal destegi (D weak/veryweak x partner).
    for scen in sorted(RESULTS):
        if "weak" in scen:
            o = RESULTS[scen]
            A(f"- I4 {scen}: " + " | ".join(
                f"{c}:[rows={o[c]['basic']['rows']} "
                f"E={o[c]['k4']['k4_energy']}]" for c in CONDS) + "\n")
    A("\nYORUM: yukaridaki OLCU satirlari davranissal yoruma aciktir; "
      "yorumlar ayrica yazilacaktir. Bu asamada iyilestirme/ayar YOK.\n")

    A("\n## Karsilastirmalar\n")
    A("### 1) BASE vs K4 STATIC\n")
    for scen in sorted(RESULTS):
        a, b = RESULTS[scen]["base"], RESULTS[scen]["k4static"]
        A(f"- {scen}: d_rows={b['basic']['rows'] - a['basic']['rows']} "
          f"d_Nsig={b['basic']['N_sig'] - a['basic']['N_sig']} "
          f"d_P3={len(b['basic']['units']) - len(a['basic']['units'])} "
          f"d_E={round(b['k4']['k4_energy'] - a['k4']['k4_energy'], 3)}\n")
    A("\n### 2) BASE vs PLASTIC BASE\n")
    for scen in sorted(RESULTS):
        d = plast_delta(scen, "base", "plastic")
        A(f"- {scen}: {d}\n")
    A("\n### 3) K4 STATIC vs K4 PLASTIC\n")
    for scen in sorted(RESULTS):
        d = plast_delta(scen, "k4static", "k4plastic")
        A(f"- {scen}: {d}\n")

    A("\n## Retrieval (H metodu, label sonradan; rapor)\n")
    for prefix in ("A_", "B_"):
        pools = []
        for scen in sorted(RESULTS):
            if scen.startswith(prefix):
                for cond in CONDS:
                    pools.append((os.path.join(OUTBASE, scen, cond,
                                               "mem.csv"),
                                  f"{scen}/{cond}"))
        acc, n = retrieval_on([(m, l) for m, l in pools
                               if os.path.isfile(m)])
        A(f"- {prefix}: acc={acc}(n={n})\n")

    with open(path, "w") as f:
        f.writelines(L)
    print(f"RAPOR: {path}", flush=True)


def main():
    global OUTBASE, RESULTS, MANIFEST
    ap = argparse.ArgumentParser(description="REV4 K4 davranis bataryasi")
    ap.add_argument("--only", default="",
                    help="ornek: A,B_drought_heat,C_AB_off0 (bos=hepsi)")
    ap.add_argument("--outdir", default=OUTBASE)
    ap.add_argument("--smoke", action="store_true",
                    help="hizli duman: 2 senaryo x 4 kosul")
    ap.add_argument("--report-only", action="store_true",
                    help="binary calistirmadan mevcut OUTBASE'den metrik+rapor")
    a = ap.parse_args()
    OUTBASE = a.outdir
    os.makedirs(OUTBASE, exist_ok=True)
    only = [s.strip() for s in a.only.split(",") if s.strip()]
    if not a.report_only:
        # Kismi kosular mevcut manifesti EZMEMELI (birlestir).
        try:
            with open(os.path.join(OUTBASE, "manifest.json")) as f:
                MANIFEST = json.load(f)
        except FileNotFoundError:
            pass

    def wanted(scen):
        return not only or scen in only or any(
            scen.startswith(o) for o in only)

    if a.report_only:
        # Mevcut kosu agacindan yeniden hesaplama (binary calismaz).
        try:
            with open(os.path.join(OUTBASE, "manifest.json")) as f:
                MANIFEST = json.load(f)
        except FileNotFoundError:
            MANIFEST = {}
        RESULTS = {}
        for scen in sorted(os.listdir(OUTBASE)):
            sdir = os.path.join(OUTBASE, scen)
            if not os.path.isdir(sdir):
                continue
            if not all(os.path.isfile(
                    os.path.join(sdir, c, "mem.csv")) for c in CONDS):
                continue
            RESULTS[scen] = {
                c: cond_metrics({"mem": os.path.join(sdir, c, "mem.csv"),
                                 "log": os.path.join(sdir, c, "log.csv"),
                                 "branch": os.path.join(sdir, c,
                                                        "branch.csv"),
                                 "matrix": os.path.join(sdir, c,
                                                        "matrix.csv")})
                for c in CONDS}
            MANIFEST.setdefault(scen, {"label": "?", "aff": None})
    elif a.smoke:
        synth = build_synthetic()
        for scen in ("C_AB_off0", "D_weak_matching"):
            p = os.path.join(OUTBASE, scen, "cable.csv")
            os.makedirs(os.path.dirname(p), exist_ok=True)
            write_aff(p, synth[scen]["rows"])
            run_case(scen, p, synth[scen]["label"])
    else:
        if not only or any(o.startswith(("A_", "B_")) or o in ("A", "B")
                           for o in only):
            # plant grubunu sinirla (only önek destegi)
            global PLANT_SCEN
            if only:
                PLANT_SCEN = {k: v for k, v in PLANT_SCEN.items()
                              if wanted(k)}
            plant_group()
        synth = build_synthetic()
        for scen, s in synth.items():
            if not wanted(scen):
                continue
            p = os.path.join(OUTBASE, scen, "cable.csv")
            os.makedirs(os.path.dirname(p), exist_ok=True)
            write_aff(p, s["rows"])
            run_case(scen, p, s["label"])

    with open(os.path.join(OUTBASE, "results.json"), "w") as f:
        json.dump({"results": RESULTS, "manifest": MANIFEST,
                   "fails": fails}, f, default=str)
    with open(os.path.join(OUTBASE, "manifest.json"), "w") as f:
        json.dump(MANIFEST, f, default=str)
    write_report(os.path.join(OUTBASE, "REPORT.md"))
    print(f"OZET-K4BAT: {'BITTI' if not fails else 'BATTI: ' + str(fails)}",
          flush=True)
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
