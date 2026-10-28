"""Canli zincir dogrulamasi (§9.96): parse + esleme + sensory smoke +
pattern mini-batch + ucttan-uca mini pencere.

Calistirma: cd salep_core && .venv/bin/python validate_sensory_chain.py
Cikis 0 = OK. Binary yoksa canli adimlar atlanir (G28a disiplini).
"""
import os
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from sim.sensory_chain import (  # noqa: E402
    SensoryChain, sensor_sets, aff_events_from_t, p1_events_from_t,
    T_RE, TAU_B)

SENSORY_BIN = os.path.join(ROOT, "npu_sensory_lobe")
PATTERN_BIN = os.path.join(ROOT, "npu_pattern_lobe")


def check(cond, msg):
    if not cond:
        print(f"BASARISIZ: {msg}")
        sys.exit(1)
    print(f"ok: {msg}")


# 1) Saf: SET eslemesi (eksikte uydurma yok).
check(sensor_sets({"hs": 75, "ts": 40, "hn": 60, "tn": 40,
                   "ph": 40, "npk": 40, "ec": 68}) ==
      ["SET hs 75", "SET ts 40", "SET hn 60", "SET tn 40",
       "SET ph 40", "SET npk 40", "SET ec 68"], "7 SET satiri birebir")
check(sensor_sets({"hs": 75}) == [], "eksik karede gonderim yok")
check(sensor_sets(None) == [], "bos karede gonderim yok")

# 2) Saf: T-bit -> (tick, post, tau); alfabe aff300 ile ayni.
evs = aff_events_from_t(274, "1010000000")
check(evs == [(274, 0, 35), (274, 2, 35)], "bit->olay eslemesi")
# 2b) Saf: T-satiri p1 yakalama + bitki olay eslemesi (§9.116).
# Canli olcu (2026-09-28): motor T 25 p1=01 / T 200 p1=10 / T 300 p1=11
# atesliyordu, zincir bitleri dusurup paneli sessiz birakiyordu.
m = T_RE.match("T 300 p1=11 p2=0000000000 w=0.213,0.210,")
check(m is not None and m.group(1) == "300"
      and m.group(2) == "11" and m.group(3) == "0000000000",
      "T_RE p1 bitlerini yakalar (tick,p1,p2)")
check(T_RE.match("T 25 p1=01 p2=0000001001 w=") is not None,
      "T_RE karisik p1/p2 satirini eslesir")
check(p1_events_from_t(25, "01") == [(25, 1)], "p1 01->hat1 (p1b)")
check(p1_events_from_t(200, "10") == [(200, 0)], "p1 10->hat0 (p1a)")
check(p1_events_from_t(300, "11") == [(300, 0), (300, 1)],
      "p1 11->iki hat")
check(p1_events_from_t(0, "00") == [], "p1 00->sessiz")
c0 = SensoryChain(bin_sensory="/yok/npu", bin_pattern="/yok/npu")
snap0 = c0.lobes_snapshot()
check("p1" in snap0 and snap0["p1"] == [], "snapshot p1 anahtari (bos)")
c0.stop()
check(TAU_B == (35, 45, 35, 36, 46, 26, 37, 37, 37, 37),
      "tau tablosu bank ile ayni")
check(all(0 <= p <= 11 and 4 <= t < 61 for (_, p, t) in evs),
      "SPEC araligi (post 0..11, tau 4..60)")

# 3) Binary yoksa zincir kapanir, yayin yolu etkilenmez.
c = SensoryChain(bin_sensory="/yok/npu", bin_pattern="/yok/npu")
check(c.start() is False and c.disabled, "kayip binaryde zincir kapali")
check(c.feed({"hs": 60}) is False, "kapali zincirde feed no-op")
c.stop()

has_sens = os.path.isfile(SENSORY_BIN) and os.access(SENSORY_BIN, os.X_OK)
has_pat = os.path.isfile(PATTERN_BIN) and os.access(PATTERN_BIN, os.X_OK)
if not (has_sens and has_pat):
    print("OZET-SENSORY-CHAIN: saf OK (binary yok, canli atlandi)")
    sys.exit(0)

# 4) Sensory smoke: SET -> T telemetrisi akıyor.
c = SensoryChain()
check(c.start(), "sensory --stream kalkti")
c.feed({"hs": 74, "ts": 60, "hn": 56, "tn": 60,
        "ph": 60, "npk": 60, "ec": 40})
deadline = time.monotonic() + 20.0
while time.monotonic() < deadline and c.t_lines == 0:
    time.sleep(0.2)
check(c.t_lines > 0, f"T telemetrisi akiyor (t={c.t_lines})")
deadline = time.monotonic() + 20.0
p1seen = []
while time.monotonic() < deadline and not p1seen:
    time.sleep(0.5)
    p1seen = c.lobes_snapshot().get("p1") or []
check(len(p1seen) > 0, f"bitki P1 atimi panele akiyor ({p1seen[-1]})")
c.stop()

# 5) Pattern mini-batch: kucuk aff -> OZET.
with tempfile.TemporaryDirectory(prefix="salep_chain_test_") as d:
    aff = os.path.join(d, "mini_aff.csv")
    with open(aff, "w", encoding="utf-8") as f:
        f.write("tick,post,tau\n")
        for i in range(30):
            f.write(f"{i * 10},{i % 3},35\n")
    env = dict(os.environ)
    env["ASAN_OPTIONS"] = "detect_leaks=0"
    p = subprocess.run([PATTERN_BIN, "--aff", aff,
                        "--mem", os.path.join(d, "mem.csv"),
                        "--log", os.path.join(d, "log.csv"),
                        "--k4", "0"],
                       capture_output=True, text=True, timeout=300, env=env)
    ozet = [ln for ln in (p.stdout or "").splitlines()
            if "OZET-PATTERN-LOB" in ln]
    check(p.returncode == 0 and ozet, "pattern mini-batch OZET verdi")

# 6) Uctan uca mini: feed -> pencere -> OZET (esik kucuk, sure sinirli).
#    Yasayan instance: pattern PID pencereler boyunca SABIT.
c = SensoryChain(events_per_window=15)
check(c.start(), "zincir kalkti (mini)")
c.feed({"hs": 74, "ts": 60, "hn": 56, "tn": 60,
        "ph": 60, "npk": 60, "ec": 40})
deadline = time.monotonic() + 120.0
while time.monotonic() < deadline and c.windows_ok == 0:
    time.sleep(0.5)
pid1 = c.status()["pattern_pid"]
deadline = time.monotonic() + 120.0
while time.monotonic() < deadline and c.status()["windows_ok"] < 2:
    time.sleep(0.5)
st = c.status()
pid2 = st["pattern_pid"]
c.stop()
check(st["windows_ok"] >= 2, f"2 pencere kapandi ({st['windows_ok']})")
check(pid1 is not None and pid1 == pid2,
      f"TEK instance tum pencerelerde (pid={pid1})")
check(not st["pattern_broken"], "beklenmedik olum yok (restart yok)")
import re as _re
states = []
logp = os.path.join(c.outdir, "chain.log")
with open(logp, encoding="utf-8") as f:
    for ln in f:
        m = _re.search(r"wsum=(\d+) tsum=(\d+) rsum=(\d+)", ln)
        if m:
            states.append(tuple(int(x) for x in m.groups()))
check(len(states) >= 2, "chain.log'da pencere STATE'leri var")
check(all(b[1] >= a[1] for a, b in zip(states, states[1:])),
      f"T monoton (iz korunumu): {[s[1] for s in states]}")

# 8) Gecikme kapisi: besleme pencereyi beklemez (esiksiz akis).
c2 = SensoryChain(events_per_window=100000)
check(c2.start(), "zincir kalkti (akis)")
c2.feed({"hs": 74, "ts": 60, "hn": 56, "tn": 60,
         "ph": 60, "npk": 60, "ec": 40})
deadline = time.monotonic() + 30.0
while time.monotonic() < deadline and c2.status()["t_lines"] == 0:
    time.sleep(0.2)
f1 = c2.status()["fed_tick"]
time.sleep(3.0)
f2 = c2.status()["fed_tick"]
st2 = c2.status()
c2.stop()
check(f1 >= 0 and f2 > f1,
      f"pattern tick surekli ilerliyor ({f1}->{f2}, pencere esigi 100000'e ragmen)")
check(st2["windows_run"] == 0, "rapor kadansi ayri (pencere dolmadan OZET yok)")
check(st2["pattern_pid"] is not None and st2["pattern_alive"],
      "tek instance yasiyor")

# 7) Stream persistence TEST1/TEST2/TEST4: direkt pattern prosesi.
import re


def run_stream_script(cmds, eta="0.30", tag="t"):
    env = dict(os.environ)
    env["ASAN_OPTIONS"] = "detect_leaks=0"
    d = tempfile.mkdtemp(prefix=f"salep_stream_{tag}_")
    p = subprocess.Popen(
        [PATTERN_BIN, "--stream",
         "--mem", os.path.join(d, "mem.csv"),
         "--log", os.path.join(d, "log.csv"),
         "--eta", eta, "--k4", "1"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, bufsize=1, env=env)
    p.stdin.write(cmds + "QUIT\n")
    p.stdin.flush()
    out, _ = p.communicate(timeout=180)
    states = []
    ozets = []
    for ln in out.splitlines():
        if ln.startswith("STATE"):
            m = re.search(r"tick=(\d+) wsum=(\d+) tsum=(\d+) "
                          r"rsum=(\d+) events=(\d+)", ln)
            states.append(tuple(int(x) for x in m.groups()))
        elif ln.startswith("OZET-"):
            m = re.search(r"ates=\[([0-9,]+)\]", ln)
            ozets.append([int(x) for x in m.group(1).split(",")])
    ready = sum(1 for ln in out.splitlines() if "READY stream" in ln)
    return {"rc": p.returncode, "pid": p.pid, "ready": ready,
            "states": states, "ozets": ozets, "out": out, "dir": d}


def aff_block(t0, t1, post, tau):
    return "".join(f"AFF {t},{post},{tau}\n" for t in range(t0, t1, 10))


A = aff_block(0, 200, 0, 35)
A2 = aff_block(200, 400, 0, 35)
B = aff_block(200, 400, 5, 37)
A3 = aff_block(400, 600, 0, 35)

# TEST1: A,A — ikinci pencere ogrenilmis state'i gosterir.
r1 = run_stream_script(A + "TICK 199\nSTATE\n" + A2 + "TICK 399\nSTATE\n",
                       tag="test1")
check(r1["rc"] == 0 and r1["ready"] == 1, "TEST1: tek instance (READY=1)")
s1, s2 = r1["states"]
check(s1[4] == 20 and s2[4] == 40, "TEST1: olaylar kumulatif (20/40)")
check(s2[2] >= s1[2], f"TEST1: T monoton ({s1[2]}->{s2[2]})")
check(s2[1] != s1[1], f"TEST1: w degisti ({s1[1]}->{s2[1]})")

# TEST2: A,B,A — A izi B'de kaybolmaz, A2 atesler.
r2 = run_stream_script(
    A + "TICK 199\nOZET\n" + B + "TICK 399\nOZET\n" + A3 + "TICK 599\nOZET\n",
    tag="test2")
o = r2["ozets"]
check(len(o) == 4, "TEST2: 4 OZET (3 faz + kapanis)")
zero = [0] * len(o[0])
dA = [b - a for a, b in zip(zero, o[0])]
dB = [b - a for a, b in zip(o[0], o[1])]
dA2 = [b - a for a, b in zip(o[1], o[2])]
check(sum(dA) > 0 and sum(dB) > 0 and sum(dA2) > 0,
      f"TEST2: her faz atesler (A={sum(dA)},B={sum(dB)},A2={sum(dA2)})")

# TEST2b: iz monotonlugu (ayni A,B,A dizisi + STATE).
r2b = run_stream_script(
    A + "TICK 199\nSTATE\n" + B + "TICK 399\nSTATE\n" + A3 + "TICK 599\nSTATE\n",
    tag="test2b")
t3 = [s[2] for s in r2b["states"]]
check(all(b >= a for a, b in zip(t3, t3[1:])),
      f"TEST2: T A->B->A2 monoton ({t3})")

# TEST4: determinism — ayni script iki kez, bit-esit STATE.
r4a = run_stream_script(A + "TICK 199\nSTATE\n" + A2 + "TICK 399\nSTATE\n",
                        tag="test4a")
r4b = run_stream_script(A + "TICK 199\nSTATE\n" + A2 + "TICK 399\nSTATE\n",
                        tag="test4b")
check(r4a["states"] == r4b["states"],
      f"TEST4: STATE bit-esit ({r4a['states'][0][:3]}...)")
check(r4a["pid"] != r4b["pid"], "TEST4: ayri prosesler (sahte esitlik yok)")

print("OZET-SENSORY-CHAIN: tum adimlar OK (batch + stream persistence)")

# 9) Persistence TEST A/B/C/D/E (§9.113 — yalniz w/T/r).
import shutil as _shutil


def run_pl(cmds, load=None, save=None, extra=(), tag="p"):
    env = dict(os.environ)
    env["ASAN_OPTIONS"] = "detect_leaks=0"
    d = tempfile.mkdtemp(prefix=f"salep_pl_{tag}_")
    argv = [PATTERN_BIN, "--stream",
            "--mem", os.path.join(d, "mem.csv"),
            "--log", os.path.join(d, "log.csv"),
            "--eta", "0.30", "--k4", "1", *extra]
    if load:
        argv += ["--load", load]
    p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, bufsize=1, env=env)
    tail = ("SAVE %s\nQUIT\n" % save) if save else "QUIT\n"
    p.stdin.write(cmds + tail)
    p.stdin.flush()
    out, err = p.communicate(timeout=180)
    states, ozets, okload, oksave, warnload = [], [], 0, 0, 0
    for ln in out.splitlines():
        if ln.startswith("STATE"):
            m = re.search(r"tick=(\d+) wsum=(\d+) tsum=(\d+) "
                          r"rsum=(\d+) events=(\d+)", ln)
            states.append(tuple(int(x) for x in m.groups()))
        elif ln.startswith("OZET-"):
            m = re.search(r"ates=\[([0-9,]+)\]", ln)
            ozets.append([int(x) for x in m.group(1).split(",")])
        elif ln.startswith("OK LOAD"):
            okload += 1
        elif ln.startswith("OK SAVE"):
            oksave += 1
    warnload = sum(1 for ln in err.splitlines() if "WARN LOAD" in ln)
    return {"rc": p.returncode, "states": states, "ozets": ozets,
            "okload": okload, "oksave": oksave, "warnload": warnload,
            "dir": d}


def fires(oz):
    return sum(oz[-1])


PA = aff_block(0, 200, 0, 35)
PB = aff_block(200, 400, 5, 37)
PA2 = aff_block(400, 600, 0, 35)
TMPST = tempfile.mkdtemp(prefix="salep_plst_")
F1 = os.path.join(TMPST, "s1.plst")

# TEST A: SAVE -> kapat -> LOAD -> devam; state geri gelir.
ra = run_pl(PA + "TICK 199\nSTATE\n", save=F1, tag="a1")
check(ra["oksave"] == 1 and os.path.getsize(F1) == 17668,
      f"TEST A: SAVE yazildi (17668 B)")
sA = ra["states"][0]
rb = run_pl("STATE\n" + PA + "TICK 199\nSTATE\n", load=F1, tag="a2")
check(rb["okload"] == 1, "TEST A: LOAD kabul")
sB0, sB1 = rb["states"]
check(sB0[1:4] == sA[1:4],
      f"TEST A: yuklenen w/T/r aynen ({sB0[1:4]})")
check(sB1[4] == 20 and rb["rc"] == 0, "TEST A: devam eden oruntu (20 olay)")

# TEST B: A -> SAVE -> restart/LOAD -> B -> A; A izi korunur.
run_pl(PA + "TICK 199\n", save=F1, tag="b0")
rb2 = run_pl("STATE\n" + PB + "TICK 399\nSTATE\n" + PA2 + "TICK 599\nOZET\n",
             load=F1, tag="b1")
tB = [s[2] for s in rb2["states"]]
check(all(b >= a for a, b in zip(tB, tB[1:])),
      f"TEST B: restart sonrasi T monoton ({tB})")
oB = rb2["ozets"]
check(sum(oB[-1]) > 0, f"TEST B: A2 sonrasi ates var ({sum(oB[-1])})")

# TEST C: ayni nokta SAVE + ayni akis -> bit-esit.
FC = os.path.join(TMPST, "c.plst")
FD = os.path.join(TMPST, "d.plst")
rc1 = run_pl(PA + "TICK 199\nSTATE\n", save=FC, tag="c1")
rc2 = run_pl(PA + "TICK 199\nSTATE\n", save=FD, tag="c2")
with open(FC, "rb") as f1, open(FD, "rb") as f2:
    b1, b2 = f1.read(), f2.read()
check(b1 == b2 and len(b1) == 17668, "TEST C: SAVE dosyalari bit-esit")
check(rc1["states"] == rc2["states"], "TEST C: STATE bit-esit")

# TEST D: fresh vs loaded davranis farki.
rd_f = run_pl(PA + "TICK 199\nOZET\n", tag="d0")
rd_l = run_pl(PA + "TICK 199\nOZET\n", load=F1, tag="d1")
check(rd_l["okload"] == 1, "TEST D: loaded kosu yukledi")
check(fires(rd_l["ozets"]) > fires(rd_f["ozets"]),
      f"TEST D: ogrenmis yanit guclu "
      f"({fires(rd_f['ozets'])}->{fires(rd_l['ozets'])})")

# TEST E: bozuk state reddedilir, temiz baslangic.
FE = os.path.join(TMPST, "e.plst")
_shutil.copyfile(F1, FE)
with open(FE, "r+b") as f:
    f.seek(100)
    b = bytearray(f.read(16))
    b[0] ^= 0xFF
    f.seek(100)
    f.write(b)
re_ = run_pl(PA + "TICK 199\nSTATE\n", load=FE, tag="e1")
check(re_["okload"] == 0 and re_["warnload"] >= 1,
      "TEST E: bozuk CRC reddedildi (WARN, sessiz yukleme yok)")
rf = run_pl(PA + "TICK 199\nSTATE\n", tag="e2")
check(re_["states"] == rf["states"], "TEST E: reddedilmis = temiz baslangic")
with open(FE, "wb") as f:
    f.write(b"PLST")  # kesik dosya
rg = run_pl("STATE\n", load=FE, tag="e3")
check(rg["okload"] == 0 and rg["warnload"] >= 1,
      "TEST E: kesik dosya reddedildi")

print("OZET-PLST: TEST A/B/C/D/E OK")
