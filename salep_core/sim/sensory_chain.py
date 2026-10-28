"""Canli duyusal -> kosul -> oruntu zinciri (sim tarafi, §9.96).

    Baglanti (yalniz veri, import YOK):
      sim karesi (7 sensor) --SET--> npu_sensory_lobe --stream
      sensory T telemetrisi --(tick,post,tau)--> pencere birikir
      pencere esigi asilinca npu_pattern_lobe batch kosar, OZET yakalanir.

    Kurallar:
      - Karelere DOKUNULMAZ (sema v2 donuk, G21); panel YOK (sonraki is).
      - Fizik determinizmi korunur: zincir okur, geri yazmaz (§0/K6).
      - stdlib-only (re/subprocess/threading/queue/tempfile) → G11 temiz.
      - Binary yoksa zincir sessizce kapanir, yayinci kosar (G22 ruhu).

    Esleme (uretim hatti aff300 ile ayni alfabe):
      post = P2 indeksi k (0..9; SPEC 0..11), tau = bank tau_b[k]
      TAU_B = (35,45,35,36,46,26,37,37,37,37)  (default_bank, harness omru)
"""

import collections
import os
import queue
import re
import subprocess
import tempfile
import threading
import time

SENSORS_7 = ("hs", "ts", "hn", "tn", "ph", "npk", "ec")

# P2 bank tau_b (main_sensory_lobe.cpp default_bank; SPEC tau 4..60).
TAU_B = (35, 45, 35, 36, 46, 26, 37, 37, 37, 37)
NUM_P2 = len(TAU_B)

K_RE = re.compile(r"^K t=(\d+) (.+) kosul$")
T_RE = re.compile(r"^T (\d+) p1=([01]{2}) p2=([01]{10}) w=")

# Panel kirpmasi: live_k4.csv'den spk==1 + act>=bu esik tasinir.
# Gozlenen maxact ~0.11 (sessiz kosu) oldugundan esik dusuk tutulur;
# panel act'i ham gosterir, esik yalniz tasiyici kirpmasidir.
K4_ACT_MIN = 0.05


def sensor_sets(sensors):
    """7 sensor (0-100 float) -> SET satirlari; eksikse [] (uydurma yok)."""
    lines = []
    for k in SENSORS_7:
        try:
            v = int(round(float(sensors[k])))
        except (KeyError, TypeError, ValueError):
            return []
        lines.append(f"SET {k} {max(0, min(100, v))}")
    return lines


def aff_events_from_t(tick, bits):
    """T-line p2 bitleri -> (tick, post, tau) listesi."""
    return [(int(tick), k, TAU_B[k]) for k in range(NUM_P2)
            if k < len(bits) and bits[k] == "1"]


def p1_events_from_t(tick, bits):
    """T-line p1 bitleri -> (tick, hat) listesi (hat 0=p1a, 1=p1b).

    Bitki faz hatti atimidir (motorun r.p1_fired cikisi); dusurulmez,
    panele tasinir. Beslemeye (pattern _forward) girmez.
    """
    return [(int(tick), line) for line in (0, 1)
            if line < len(bits) and bits[line] == "1"]


def _default_bin(name):
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), name)


class SensoryChain:
    """Yayinci tarafi zincir sahibi (tek zincir, thread-guvenli).

    Yasam dongusu (§9.111 E-1): sensory + pattern prosesleri start()'ta
    BIR KEZ acilir, stop()'ta kapanir. Pencere siniri yalniz episodic
    tamponu sifirlar; w/T/r pattern prosesinde yasar (stream besleme).
    Pattern beklenmedik olurse sessiz restart YOK (state kaybi gizlenmez).
    """

    def __init__(self, bin_sensory=None, bin_pattern=None,
                 events_per_window=300, outdir=None, k4=True):
        self.bin_sensory = bin_sensory or _default_bin("npu_sensory_lobe")
        self.bin_pattern = bin_pattern or _default_bin("npu_pattern_lobe")
        self.events_per_window = max(1, int(events_per_window))
        self.outdir = outdir or tempfile.mkdtemp(prefix="salep_chain_")
        self.k4 = bool(k4)
        self.proc = None           # sensory prosesi
        self.pat = None            # pattern prosesi (TEK instance)
        self.state_path = os.path.join(self.outdir, "live_state.plst")
        self.loaded = False        # baslangic state dosyadan geldi mi
        self.saved = False         # kapanista SAVE yazildi mi
        self.disabled = False
        self.pattern_broken = False  # beklenmedik olum (restart yok)
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._pat_send_lock = threading.Lock()  # pattern stdin tek yazici
        self._buffer = []          # pencere kaydi (raporlama icin) — episodic
        self._fed_events = 0       # pattern'a beslenen toplam olay
        self._fed_tick = -1        # pattern'a isletilen son tick
        self._reported = 0         # raporlanan olay sayisi
        self._win_lock = threading.Lock()  # pencere kapatma serisi
        self._pat_resp = queue.Queue()     # pattern yanit kuyrugu
        self.k_lines = 0           # K kosul satiri sayaci
        self.t_lines = 0           # T telemetri sayaci
        # Canli panel tamponlari (§9.115: harness-omru, cekirdege dokunmaz).
        # recent_aff: son afferent olaylari (tick,post,tau); post=P2 indeksi.
        # recent_p1: son bitki faz-hatti atimlari (tick,hat); hat 0=p1a,
        #   1=p1b (§9.116: panel bitki yolu; beslemeye girmez).
        # recent_k4: live_k4.csv tail — (tick,birim,dal,act,spk); yalniz
        #   spk==1 veya act>=K4_ACT_MIN satirlari (panel kirpmasi, raporda
        #   tam dosya durur; esik snapshot'ta acik yazilir).
        self._recent_aff = collections.deque(maxlen=40)
        self._recent_p1 = collections.deque(maxlen=40)
        self._recent_k4 = collections.deque(maxlen=96)
        self._k4_path = None
        self._k4_off = 0
        self.windows_run = 0
        self.windows_ok = 0
        self.last_ozet = ""
        self.last_state = ""
        self.last_files = ()

    def _spawn(self, argv):
        env = dict(os.environ)
        env["ASAN_OPTIONS"] = "detect_leaks=0"  # §9.9 LSan kisiti
        return subprocess.Popen(
            argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1, env=env)

    def _wait_ready(self, proc, token="READY", timeout=15.0):
        """READY satirini bekler; gorulen satirlari dondurur (bos=None)."""
        seen = []
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                return None
            line = proc.stdout.readline()
            seen.append(line)
            if token in line:
                return seen
        return None

    def start(self):
        """Sensory + pattern proseslerini BIR KEZ baslat.

        Ikisinden biri acilmazsa zincir kapali doner (kismi canli yok).
        """
        if not (os.path.isfile(self.bin_sensory)
                and os.access(self.bin_sensory, os.X_OK)):
            self.disabled = True
            return False
        if not (os.path.isfile(self.bin_pattern)
                and os.access(self.bin_pattern, os.X_OK)):
            self.disabled = True
            return False
        os.makedirs(self.outdir, exist_ok=True)
        try:
            self.proc = self._spawn([self.bin_sensory, "--stream"])
            if self._wait_ready(self.proc, "DUYUSAL LOB") is None:
                raise OSError("sensory READY yok")
            mem = os.path.join(self.outdir, "live_mem.csv")
            log = os.path.join(self.outdir, "live_log.csv")
            cmd = [self.bin_pattern, "--stream",
                   "--mem", mem, "--log", log]
            if self.k4:
                cmd += ["--k4", "1",
                        "--k4csv", os.path.join(self.outdir, "live_k4.csv"),
                        "--k4paircsv", os.path.join(self.outdir,
                                                    "live_k4pair.csv"),
                        "--k4idcsv", os.path.join(self.outdir,
                                                  "live_k4id.csv")]
            if os.path.isfile(self.state_path):
                cmd += ["--load", self.state_path]
            self.pat = self._spawn(cmd)
            seen = self._wait_ready(self.pat, "READY stream")
            if seen is None:
                raise OSError("pattern READY yok")
            self.loaded = any(ln.startswith("OK LOAD") for ln in seen)
            self.last_files = (mem, log)
        except OSError:
            self._kill(self.proc)
            self._kill(self.pat)
            self.proc = None
            self.pat = None
            self.disabled = True
            return False
        self._stop.clear()
        threading.Thread(target=self._reader, daemon=True,
                         name="sensory-chain-reader").start()
        threading.Thread(target=self._pat_reader, daemon=True,
                         name="pattern-chain-reader").start()
        if self.k4:
            self._k4_path = os.path.join(self.outdir, "live_k4.csv")
            self._k4_off = 0
            threading.Thread(target=self._k4_tail, daemon=True,
                             name="pattern-k4-tail").start()
        return True

    def _k4_tail(self):
        """live_k4.csv kuyrugu: yeni satirlar -> _recent_k4 (panel canlisi).

        Dosya kuculurse (truncate/yeniden yazim) bastan baslar; baslik
        satiri atlanir; spk==1 veya act>=K4_ACT_MIN olanlar alinir.
        Salt-okur: pattern prosesinin yazimina dokunulmaz.
        """
        while not self._stop.is_set():
            try:
                if self._k4_path and os.path.isfile(self._k4_path):
                    size = os.path.getsize(self._k4_path)
                    if size < self._k4_off:
                        self._k4_off = 0
                    if size > self._k4_off:
                        with open(self._k4_path, "r",
                                 encoding="utf-8") as f:
                            f.seek(self._k4_off)
                            chunk = f.read()
                            self._k4_off = f.tell()
                        for line in chunk.splitlines():
                            parts = line.split(",")
                            if len(parts) != 8 or parts[0] == "tick":
                                continue
                            try:
                                tick = int(parts[0])
                                birim = int(parts[1])
                                dal = int(parts[2])
                                act = float(parts[3])
                                spk = int(parts[7])
                            except ValueError:
                                continue
                            if spk == 1 or act >= K4_ACT_MIN:
                                with self._lock:
                                    self._recent_k4.append(
                                        (tick, birim, dal, act, spk))
            except OSError:
                pass
            time.sleep(1.0)

    def lobes_snapshot(self):
        """Panel canlisi: kilit altinda hafif lob ozeti (frame.lobes'e)."""
        with self._lock:
            aff = list(self._recent_aff)[-24:]
            p1 = list(self._recent_p1)[-24:]
            k4 = list(self._recent_k4)[-64:]
            return {
                "sensory_alive": self.proc is not None
                and self.proc.poll() is None,
                "pattern_alive": self.pat is not None
                and self.pat.poll() is None,
                "pattern_broken": self.pattern_broken,
                "fed_tick": self._fed_tick,
                "fed_events": self._fed_events,
                "aff": [list(e) for e in aff],
                "p1": [list(e) for e in p1],
                "k4": [list(e) for e in k4],
                "k4_act_min": K4_ACT_MIN,
                "ozet": self.last_ozet,
            }

    @staticmethod
    def _kill(proc):
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass

    def _reader(self):
        try:
            for line in self.proc.stdout:
                if self._stop.is_set():
                    break
                line = line.strip()
                m = T_RE.match(line)
                if m:
                    evs = aff_events_from_t(m.group(1), m.group(3))
                    tick = int(m.group(1))
                    p1evs = p1_events_from_t(m.group(1), m.group(2))
                    # BESLEME (esiksiz): olaylar aninda yasayan
                    # instance'a akar; pencere yalniz raporlama kadansidir.
                    # p1 bitki atimidir: panele tasinir, beslemeye girmez.
                    fed_ok = self._forward(tick, evs)
                    with self._lock:
                        self.t_lines += 1
                        self._buffer.extend(evs)
                        self._recent_aff.extend(evs)
                        self._recent_p1.extend(p1evs)
                        pending = (len(self._buffer) - self._reported
                                   >= self.events_per_window)
                    if pending and fed_ok:
                        self._maybe_report_window()
                    continue
                m = K_RE.match(line)
                if m:
                    with self._lock:
                        self.k_lines += 1
        except (OSError, ValueError):
            pass

    def feed(self, sensors):
        """7 sensor degerini SET'le (gun degisiminde cagir; no-op guvenli)."""
        if self.disabled or self.proc is None or self.proc.poll() is not None:
            return False
        try:
            for line in sensor_sets(sensors):
                self.proc.stdin.write(line + "\n")
            self.proc.stdin.flush()
            return True
        except OSError:
            return False

    def _pat_reader(self):
        """Pattern yanitlari (OZET/STATE/ERR) kuyruga; olum isareti."""
        try:
            for line in self.pat.stdout:
                if self._stop.is_set():
                    break
                line = line.strip()
                if not line:
                    continue
                if line.startswith(("OZET-", "STATE", "ERR", "OK ")):
                    try:
                        self._pat_resp.put_nowait(line)
                    except queue.Full:
                        pass
        except (OSError, ValueError):
            pass
        finally:
            with self._lock:
                if not self._stop.is_set():
                    # Beklenmedik olum: state kaybi gizlenmez, restart YOK.
                    self.pattern_broken = True

    def _forward(self, tick, evs):
        """T-satirini aninda pattern'a islet (AFF + TICK, esiksiz).

        Olaysiz T-satirinda bile TICK gider (leak/decay süzülür).
        Donus: besleme basariliysa True.
        """
        pat = self.pat
        if pat is None or pat.poll() is not None:
            with self._lock:
                self.pattern_broken = True
            return False
        try:
            with self._pat_send_lock:
                for (t, p, tau) in evs:
                    pat.stdin.write(f"AFF {t},{p},{tau}\n")
                pat.stdin.write(f"TICK {tick}\n")
                pat.stdin.flush()
        except OSError:
            with self._lock:
                self.pattern_broken = True
            return False
        with self._lock:
            self._fed_events += len(evs)
            if tick > self._fed_tick:
                self._fed_tick = tick
        return True

    def _pat_cmd(self, cmd, expect, timeout=30.0):
        """Pattern komutu + beklenen prefix'li yanit (yoksa None)."""
        pat = self.pat
        if pat is None or pat.poll() is not None:
            return None
        try:
            with self._pat_send_lock:
                pat.stdin.write(cmd + "\n")
                pat.stdin.flush()
        except OSError:
            return None
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                line = self._pat_resp.get(
                    timeout=max(0.1, deadline - time.monotonic()))
            except queue.Empty:
                return None
            if line.startswith(expect):
                return line
        return None

    def _maybe_report_window(self):
        threading.Thread(target=self._report_window, daemon=True,
                         name="pattern-window").start()

    def _report_window(self):
        """Rapor kadansi: OZET/STATE + pencere dosyasi + chain.log.

        Olaylar ZATEN yasayan instance'a beslendi (_forward); burada
        yalniz episodic kayit kapatilir. w/T/r'ye dokunulmaz.
        """
        with self._win_lock:
            with self._lock:
                pending = self._fed_events - self._reported
                if pending < self.events_per_window:
                    return
                window = list(self._buffer)
                self._buffer = []
                self._reported = self._fed_events
                tag = f"w{self.windows_run}"
            if self.pat is None or self.pat.poll() is not None:
                with self._lock:
                    self.pattern_broken = True
                return
            aff = os.path.join(self.outdir, f"{tag}_afferent.csv")
            try:
                with open(aff, "w", encoding="utf-8") as f:
                    f.write("tick,post,tau\n")
                    for (t, p, tau) in window:
                        f.write(f"{t},{p},{tau}\n")
            except OSError:
                pass
            ozet = self._pat_cmd("OZET", "OZET-")
            state = self._pat_cmd("STATE", "STATE")
            with self._lock:
                self.windows_run += 1
                if ozet:
                    self.windows_ok += 1
                    self.last_ozet = ozet
                    self.last_state = state or ""
                    try:
                        with open(os.path.join(self.outdir, "chain.log"),
                                  "a", encoding="utf-8") as f:
                            f.write(f"{tag} {ozet}\n")
                            if state:
                                f.write(f"{tag} {state}\n")
                    except OSError:
                        pass

    def status(self):
        """Salt-okunur ozet (panel sonraya; simdi log/teshis icin)."""
        with self._lock:
            return {
                "disabled": self.disabled,
                "sensory_alive": self.proc is not None
                and self.proc.poll() is None,
                "pattern_alive": self.pat is not None
                and self.pat.poll() is None,
                "pattern_broken": self.pattern_broken,
                "sensory_pid": self.proc.pid if self.proc else None,
                "pattern_pid": self.pat.pid if self.pat else None,
                "k_lines": self.k_lines,
                "t_lines": self.t_lines,
                "buffered": len(self._buffer),
                "fed_events": self._fed_events,
                "fed_tick": self._fed_tick,
                "windows_run": self.windows_run,
                "windows_ok": self.windows_ok,
                "loaded": self.loaded,
                "saved": self.saved,
                "state_path": self.state_path,
                "last_ozet": self.last_ozet,
                "last_state": self.last_state,
                "outdir": self.outdir,
            }

    def stop(self):
        """Temiz kapanis: QUIT yalniz gercek sonda (kural 5)."""
        pat = self.pat
        self.pat = None
        if pat is not None and pat.poll() is None:
            try:
                # Kapanis SAVE'i reader yasanirken (STOP bayragindan ONCE;
                # yoksa yanit okunamaz). Basarisizsa QUIT yine gider.
                pat.stdin.write(f"SAVE {self.state_path}\n")
                pat.stdin.flush()
                deadline = time.monotonic() + 15.0
                while time.monotonic() < deadline:
                    try:
                        ln = self._pat_resp.get(timeout=1.0)
                    except queue.Empty:
                        break
                    if ln.startswith("OK SAVE"):
                        with self._lock:
                            self.saved = True
                        break
            except OSError:
                pass
        self._stop.set()
        if pat is not None and pat.poll() is None:
            try:
                pat.stdin.write("QUIT\n")
                pat.stdin.flush()
            except OSError:
                pass
            try:
                pat.wait(timeout=15)
            except subprocess.TimeoutExpired:
                try:
                    pat.terminate()
                except OSError:
                    pass
        proc, self.proc = self.proc, None
        if proc is not None and proc.poll() is None:
            try:
                proc.stdin.write("QUIT\n")
                proc.stdin.flush()
            except OSError:
                pass
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._kill(proc)
