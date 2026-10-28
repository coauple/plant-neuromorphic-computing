"""NPU OPS terminali: btop/htop tarzı canlı panel + Komut Yorumlayıcı chati.

Calistirma (proje kokunden):
    .venv/bin/python live_term.py [--bin ./npu_plant_npu]
    .venv/bin/python live_term.py --self-test   # kapı testi + temiz kapanış

Motor (`npu_plant_npu --stream`) degismez (T/OK/ERR/OZET protokolu ayni):
her 25 tick telemetri reader thread ile kuyruga alinir, ana dongu
T farkindan olay sentezler (ates / dw-plato / faz / tasiyici).
Tum grafikler gercek telemetriden beslenen deque'lerdir; uydurma veri yok.
Kullanici girdisi scenario_engine.interpret'ten gecer: motor satirlari
stdin'e, konusma KOMUT GÜNLÜĞÜ'ne [CPU Tercüman] rozetiyle duser; ham
ERR asla basilmaz. tty'de termios tus modu (+alt-ekran), piped'da
satir-modu fallback (eski piped testler bozulmaz).
"""

import collections
import io
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import threading
import time

CORE_DIR = os.path.dirname(os.path.abspath(__file__))
if CORE_DIR not in sys.path:
    sys.path.insert(0, CORE_DIR)
import scenario_engine
import interpreter
import state_analyzer

try:
    from rich.console import Console
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.text import Text
except ImportError:
    print("HATA: 'rich' gerekli: .venv/bin/pip install rich",
          file=sys.stderr)
    raise SystemExit(1)

ARGS = sys.argv[1:]
BIN = ARGS[ARGS.index("--bin") + 1] \
    if "--bin" in ARGS else os.path.join(CORE_DIR, "npu_plant_npu")
SELF_TEST = "--self-test" in ARGS

# --- protokol (C++ ile birebir, degismedi) ---
TELE_RE = re.compile(
    r"^T\s+(\d+)\s+wire=([0-9.]+)\s+f=([01]{9})\s+w=([0-9.,]+)\s+"
    r"cc=([0-9,]+)")
POST_NAMES = ["NEM", "EC", "SIC", "TS", "TN", "PH", "NPK", "X1", "X2"]
# NOT (§9.14 Duyusal Lob v2): P2 kosul bankasi etiket eslemesi
# NEM..X2 <-> p2a.. (varsayilan banka: p2a=NEM, p2b=SIC, p2c=replika,
# p2d/p2e=decoy, p2f=EC-negatif, p2g..p2j=TS/TN/PH/NPK). Tam v5 UI
# eslemesi bir sonraki adimda; bu not arayuz sozlesmesidir.
SENSOR_ORDER = ("hs", "ts", "hn", "tn", "ph", "npk", "ec")
CC_ORDER = ("hn", "ec", "hs", "ts", "tn", "ph", "npk")  # rail_csv sirasi
DEFAULT_PROFILE = {"hs": 75, "ts": 40, "hn": 60, "tn": 40,
                   "ph": 40, "npk": 40, "ec": 40}
SENSOR_TR_SHORT = {"hs": "HavaSic", "ts": "ToprSic", "hn": "HavaNem",
                   "tn": "ToprNem", "ph": "pH", "npk": "NPK", "ec": "EC"}
XPOST = {"X1", "X2"}

EVENT_MAX = 40
BAR_W = 10
WIRE_HIST = 80
SPARK = "▁▂▃▄▅▆▇█"
BRAILLE_BASE = 0x2800

STOP_WORDS = ("/stop", "duraklat", "dur")
CONT_WORDS = ("/continue", "devam", "sürdür", "surdur")


def parse_telemetry(line):
    """Motor telemetri satirini dict'e cevirir; degilse None."""
    m = TELE_RE.match(line.strip())
    if not m:
        return None
    return {"t": int(m.group(1)), "wire": float(m.group(2)),
            "f": m.group(3),
            "w": [float(x) for x in m.group(4).split(",")],
            "cc": [int(x) for x in m.group(5).split(",")]}


def synthesize_events(prev, cur):
    """T farkindan akis olaylari: [(kind, text)]. C++'a dokunmaz."""
    evs = []
    if prev is None:
        return [("sys", "telemetri akışı başladı — NPU donanımı dinleniyor")]
    for i, nm in enumerate(POST_NAMES):
        if cur["f"][i] == "1":
            tag = "  ▸ çapraz kombinasyon" if nm in XPOST else ""
            evs.append(("fire", f"● {nm} ateş t={cur['t']}{tag}"))
    for i, nm in enumerate(POST_NAMES):
        dw = cur["w"][i] - prev["w"][i]
        if dw > 0.002:
            evs.append(("dw", f"▲ Δw {nm} +{dw:.3f} → {cur['w'][i]:.3f} "
                              f"(plato)"))
    if abs(cur["wire"] - prev["wire"]) > 0.5:
        evs.append(("phase", f"▚ faz şifresi wire={cur['wire']:.3f}"))
    for j, ch in enumerate(CC_ORDER):
        d = cur["cc"][j] - prev["cc"][j]
        if d > 0:
            evs.append(("carrier", f"◆ {ch}(τ{interpreter.SENSOR_TAU[ch]}) "
                                   f"taşıyıcı +{d}"))
    return evs


KIND_STYLE = {"fire": "bold red", "dw": "green", "phase": "cyan",
              "carrier": "dim cyan", "cpu": "magenta", "ok": "dim green",
              "warn": "yellow", "sys": "dim"}
AGE_STYLE = ["bold", "", "dim"]  # yas 0-2 / 3-8 / 9+


class FallingEvents:
    """Yas-bazli solan gunluk: yeni olay ustte, yaslilar solar."""

    def __init__(self, maxlen=EVENT_MAX):
        self.dq = collections.deque(maxlen=maxlen)

    def push(self, kind, text):
        self.dq.appendleft({"kind": kind, "text": text, "age": 0})

    def age(self):
        for e in self.dq:
            e["age"] += 1

    def render(self, n=30):
        t = Text()
        for e in list(self.dq)[:n]:
            tier = 0 if e["age"] <= 2 else (1 if e["age"] <= 8 else 2)
            base = KIND_STYLE.get(e["kind"], "")
            style = f"{base} {AGE_STYLE[tier]}".strip()
            t.append(e["text"] + "\n", style=style or None)
        return t


def pause_motor(proc):
    """Motoru dondur (SIGSTOP): tick islemez, durum korunur. Bool doner."""
    if proc.poll() is not None:
        return False
    if not hasattr(signal, "SIGSTOP"):
        return False
    try:
        proc.send_signal(signal.SIGSTOP)
        return True
    except (OSError, ValueError):
        return False


def resume_motor(proc):
    """Donmus motoru surdur (SIGCONT). Bool doner."""
    if proc.poll() is not None:
        return False
    if not hasattr(signal, "SIGCONT"):
        return False
    try:
        proc.send_signal(signal.SIGCONT)
        return True
    except (OSError, ValueError):
        return False


class TermState:
    def __init__(self):
        self.profile = dict(DEFAULT_PROFILE)
        self.gates = {s: True for s in SENSOR_ORDER}  # afferent kapılar
        self.prev = None
        self.last = None
        self.events = FallingEvents()
        self.paused = False
        self.wire_hist = collections.deque(maxlen=WIRE_HIST)
        self.w_min = [None] * 9  # oturum min/max (öğrenme % ölçeği)
        self.w_max = [None] * 9
        self.cc_max = [0] * 7
        self.history = []
        self.brief = ""
        self.brief_until = 0.0
        self.ozet = ""
        self.fires = {nm: 0 for nm in POST_NAMES}
        self.running = True
        self.tick = 0


def bar(frac, width=BAR_W):
    frac = max(0.0, min(1.0, frac))
    n = int(round(frac * width))
    return "█" * n + "░" * (width - n)


def sparkline(values):
    """Gercek wire gecmisi -> olcekli mini grafik (bosken '')."""
    if not values:
        return ""
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return SPARK[3] * len(values)
    return "".join(SPARK[min(7, int((v - lo) / (hi - lo) * 8))]
                    for v in values)


def braille_plot(values, width):
    """Son ~80 gercek ornekten braille alan grafigi (2 ornek/hucre)."""
    vs = list(values)[-80:]
    if not vs:
        return ""
    per = max(1, len(vs) // (width * 2))
    cols = []
    for i in range(width * 2):
        chunk = vs[i * per:(i + 1) * per] or vs[-1:]
        cols.append(sum(chunk) / len(chunk))
    lo, hi = min(cols), max(cols)
    span = (hi - lo) or 1.0
    out = []
    for i in range(0, len(cols), 2):
        c0 = cols[i]
        c1 = cols[i + 1] if i + 1 < len(cols) else cols[i]
        bits = 0
        for v, shifts in ((c0, (0, 1, 2, 6)), (c1, (3, 4, 5, 7))):
            lvl = int(round((v - lo) / span * 4))  # 0..4, alttan dolu
            for r in range(4):
                if r >= 4 - lvl:
                    bits |= 1 << shifts[r]
        out.append(chr(BRAILLE_BASE + bits))
    return "".join(out)


def left_panel_text(state):
    """Sutun 1: AFFERENT (sensor + kapi) ve GROUNDING (post) bloklari."""
    t = Text()
    t.append("AFFERENT\n", style="bold")
    for s in SENSOR_ORDER:
        v = state.profile.get(s, 0)
        shut = not state.gates.get(s, True)
        on = v >= 50 and not shut
        if shut:
            t.append(f"{s} τ{interpreter.SENSOR_TAU[s]:<2} {v:>3} "
                     f"{bar(0.0)} KAPALI\n", style="magenta")
        else:
            led = ("●ON ", "green") if on else ("○OFF", "blue")
            t.append(f"{s} τ{interpreter.SENSOR_TAU[s]:<2} {v:>3} "
                     f"{bar(v / 100.0)} ")
            t.append(*led)
            t.append("\n")
    t.append("\nGROUNDING\n", style="bold")
    w = state.last["w"] if state.last else [0.0] * 9
    for i, nm in enumerate(POST_NAMES):
        mark = "⊕" if nm in XPOST else " "
        fired = state.last and state.last["f"][i] == "1"
        dot = ("●", "bold red") if fired else ("○", "dim")
        t.append(f"{mark} {nm:<3} ")
        t.append(*dot)
        t.append(f" {w[i]:.2f} {bar(w[i] / 2.0)} n={state.fires[nm]}\n")
    return t


def graphs_text(state, plot_width=40):
    """Sutun 2: GRAFIKLER (wire braille + w/cc barlari + analiz)."""
    t = Text()
    t.append("WIRE (son 80, braille)\n", style="bold")
    if state.wire_hist:
        lo, hi = min(state.wire_hist), max(state.wire_hist)
        t.append(braille_plot(state.wire_hist, plot_width) + "\n",
                 style="cyan")
        t.append(f"ölçek [{lo:.2f}..{hi:.2f}] cur={state.last['wire']:.3f}\n"
                 if state.last else "", style="dim")
    else:
        t.append("telemetri bekleniyor...\n", style="dim")
    t.append("POST W (oturum-min/max %)\n", style="bold")
    if state.last:
        for i, nm in enumerate(POST_NAMES):
            pct = state_analyzer.learning_pct(
                state.last["w"][i], state.w_min[i], state.w_max[i])
            mark = "⊕" if nm in XPOST else " "
            t.append(f"{mark}{nm:<3} {bar(pct)} {pct * 100:>3.0f}% "
                     f"{state.last['w'][i]:.2f} n={state.fires[nm]}\n")
    t.append("TAŞIYICI (oturum-maks göreli)\n", style="bold")
    if state.last:
        for j, ch in enumerate(CC_ORDER):
            mx = state.cc_max[j] or 1
            t.append(f"{ch:<3} {bar(state.last['cc'][j] / mx)} "
                     f"{state.last['cc'][j]}\n")
    env, agree = state_analyzer.classify_env(state.profile)
    t.append(f"ORTAM {state_analyzer.ENV_TR[env]} "
             f"(uyum {agree * 7:.0f}/7)\n", style="bold yellow")
    t.append("VİTAL ateş/tick (bar dolusu=0.05)\n", style="bold")
    ticks = max(1, state.tick)
    for nm in POST_NAMES:
        r = state.fires[nm] / ticks
        t.append(f"{nm:<3} {bar(min(1.0, r * 20))} {r:.3f}\n")
    t.append("legend: W%=oturum-min/max; cc=oturum-maks göreli; "
             "VİTAL bar dolusu=0.05 ateş/tick\n", style="dim")
    return t


def vitals_legend():
    t = Text("legend: AKTİF=w≥1.0; ●=bu tick ateş; "
             "wire=motor birimi\n", style="dim")
    return t


def term_width():
    try:
        return shutil.get_terminal_size((110, 30)).columns
    except OSError:
        return 110


def draw_layout(state, prompt_buf, width=None):
    wide = (term_width() if width is None else width) >= 110
    root = Layout()
    root.split_column(Layout(name="head", size=1),
                      Layout(name="body", ratio=1),
                      Layout(name="foot", size=2))
    wire = state.last["wire"] if state.last else 0.0
    if not state.running:
        led = ("○ DURDU", "red")
    elif state.paused:
        led = ("❚❚ DURAKLATILDI", "yellow")
    else:
        led = ("● ÇALIŞIYOR", "green")
    shut = sum(1 for s in SENSOR_ORDER if not state.gates.get(s, True))
    head = Text()
    head.append("NPU OPS  ", style="bold")
    head.append(f"t={state.tick}  wire {sparkline(state.wire_hist)} "
                f"{wire:.3f}  ")
    head.append(*led)
    if shut:
        head.append(f"  kapı:{shut} kapalı", style="magenta")
    head.append("  [q]uit [p]ause [r]eset [s]enaryo", style="dim")
    root["head"].update(head)

    if wide:
        root["body"].split_row(Layout(name="left", size=34),
                               Layout(name="mid", ratio=1),
                               Layout(name="right", size=44))
        root["left"].update(Panel(left_panel_text(state), title="AFFERENT"))
        root["mid"].update(Panel(graphs_text(state), title="GRAFİK"))
        root["right"].update(Panel(state.events.render(),
                                   title="KOMUT GÜNLÜĞÜ"))
    else:  # dar terminal: 3->2 sutun (sol + gunluk)
        root["body"].split_row(Layout(name="left", size=34),
                               Layout(name="right", ratio=1))
        root["left"].update(Panel(left_panel_text(state), title="AFFERENT"))
        root["right"].update(Panel(state.events.render(),
                                   title="KOMUT GÜNLÜĞÜ"))

    foot = Text()
    foot.append(f"❯ {prompt_buf}▌  ", style="bold")
    if state.brief and time.monotonic() < state.brief_until:
        foot.append(f"[CPU Tercüman] {state.brief}", style="magenta")
    elif state.history:
        foot.append(f"son: {state.history[-1]}  ", style="dim")
    foot.append("yardım: /help", style="dim")
    root["foot"].update(foot)
    return root


def handle_user_line(state, line, send, proc):
    """interpret -> motor + konusma. 'quit' dondururse cikis demektir."""
    norm = line.strip().lower()
    if norm == "/help":
        state.events.push("cpu", "[CPU Tercüman] Komutlar: "
                                 "/set <s> <0-100> · "
                                 "/scenario drought|sulama|soguk|reset · "
                                 "/sensor-off|on <s> · /stop · /continue · "
                                 "doğal dil ('nem 70', 'hn kapa') · "
                                 "reset · quit · boşken q/p/r/s kısayol")
        state.history.append("/help")
        return False
    if norm in STOP_WORDS:
        if state.paused:
            state.brief = "zaten duraklatıldı"
        elif pause_motor(proc):
            state.paused = True
            for sp in interpreter.describe_pause():
                state.events.push("cpu", f"[CPU Tercüman] {sp}")
            state.brief = "duraklatıldı"
        else:
            state.events.push("warn", "[CPU Tercüman] Duraklatma "
                                      "desteklenmiyor (SIGSTOP yok).")
            state.brief = "duraklatılamadı"
        state.brief_until = time.monotonic() + 4.0
        state.history.append(line.strip())
        return False
    if norm in CONT_WORDS:
        if not state.paused:
            state.brief = "zaten çalışıyor"
        elif resume_motor(proc):
            state.paused = False
            for sp in interpreter.describe_resume():
                state.events.push("cpu", f"[CPU Tercüman] {sp}")
            state.brief = "devam ediyor"
        else:
            state.events.push("warn", "[CPU Tercüman] Sürdürme başarısız; "
                                      "motor yaşamıyor olabilir.")
            state.brief = "sürdürülemedi"
        state.brief_until = time.monotonic() + 4.0
        state.history.append(line.strip())
        return False
    r = scenario_engine.interpret(line)
    if r["kind"] == "comment":
        return False
    if r["kind"] == "quit":
        state.events.push("cpu", f"[CPU Tercüman] {r['speech'][0]}")
        try:
            send("QUIT")
        except (BrokenPipeError, ValueError):
            pass
        return True
    for ml in r["motor_lines"]:
        try:
            send(ml)
        except (BrokenPipeError, ValueError):
            break
        m = re.match(r"^SET\s+(\w+)\s+(\d+)$", ml)
        if m:
            state.profile[m.group(1)] = int(m.group(2))
        if ml == "RESET":
            state.profile = dict(DEFAULT_PROFILE)
    for sp in r["speech"]:
        state.events.push("cpu", f"[CPU Tercüman] {sp}")
    state.brief = r["brief"]
    state.brief_until = time.monotonic() + 4.0
    state.history.append(line.strip())
    return False


def process_motor_line(state, line):
    tele = parse_telemetry(line)
    if tele is not None:
        state.tick = tele["t"]
        state.wire_hist.append(tele["wire"])
        for i in range(9):
            wv = tele["w"][i]
            if state.w_min[i] is None or wv < state.w_min[i]:
                state.w_min[i] = wv
            if state.w_max[i] is None or wv > state.w_max[i]:
                state.w_max[i] = wv
        for j in range(7):
            if tele["cc"][j] > state.cc_max[j]:
                state.cc_max[j] = tele["cc"][j]
        for i, nm in enumerate(POST_NAMES):
            if tele["f"][i] == "1":
                state.fires[nm] += 1
        for kind, text in synthesize_events(state.prev, tele):
            state.events.push(kind, text)
        state.prev = state.last = tele
        return
    s = line.strip()
    m = re.match(r"^OK SENSOR_(OFF|ON) (\w+)$", s)
    if m:
        state.gates[m.group(2)] = (m.group(1) == "ON")
        state.events.push("ok", f"[NPU] {s}")
        return
    if s.startswith("=== OZET:"):
        state.ozet = s
        state.events.push("sys", s)
    elif s.startswith("OK"):
        state.events.push("ok", f"[NPU] {s}")
    elif s.startswith("ERR"):
        state.events.push("warn", "[CPU Tercüman] Motor bu komutu "
                                  "reddetti; profil değişmedi.")


def spawn_motor():
    env = dict(os.environ)
    env["ASAN_OPTIONS"] = "detect_leaks=0"
    return subprocess.Popen(
        [BIN, "--stream"], cwd=CORE_DIR, stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, env=env)


def main():
    from rich.live import Live
    console = Console()
    try:
        proc = spawn_motor()
    except OSError as e:
        console.print(f"[red]motor başlatılamadı: {e}[/red]")
        raise SystemExit(1)

    out_q = queue.Queue()
    in_q = queue.Queue()
    stop = threading.Event()
    use_tty = sys.stdin.isatty() and not SELF_TEST
    saved_attrs = None

    def reader():
        try:
            for line in proc.stdout:
                out_q.put(line.rstrip("\n"))
        finally:
            stop.set()

    def input_loop():
        # tek okuyucu: tty'de ham tuslar (+bos-satir kisayollari),
        # piped'da satirlar. Boru motora tum oturum boyunca acik tutulur.
        if use_tty:
            fd = sys.stdin.fileno()
            data = bytearray()

            def snap():
                try:
                    in_q.put(("__buf__", bytes(data).decode("utf-8")))
                except UnicodeDecodeError:
                    pass

            while proc.poll() is None:
                try:
                    chunk = os.read(fd, 32)
                except (OSError, KeyboardInterrupt):
                    break
                if not chunk:
                    break
                for b in chunk:
                    if b in (0x7f, 0x08):  # backspace
                        try:
                            s = bytes(data).decode("utf-8")
                        except UnicodeDecodeError:
                            s = ""
                        data = bytearray(s[:-1].encode("utf-8"))
                        snap()
                    elif b == 0x03:  # Ctrl-C: 1x temizle, 2x çıkış
                        if len(data) > 0:
                            data = bytearray()
                            snap()
                        else:
                            in_q.put("quit")
                    elif b in (0x0d, 0x0a):  # enter
                        try:
                            in_q.put(bytes(data).decode("utf-8"))
                        except UnicodeDecodeError:
                            pass
                        data = bytearray()
                        snap()
                    elif not data and b in b"qprs":
                        # bos satir kisayollari (yazarken harfler yaziya
                        # gider, carpismaz): q/p/r aninda, s one önekler
                        if b == ord("s"):
                            data = bytearray(b"/scenario ")
                            snap()
                        else:
                            in_q.put({ord("q"): "quit", ord("p"): "p_toggle",
                                      ord("r"): "reset"}[b])
                    else:
                        data.append(b)
                        snap()
        else:
            while proc.poll() is None:
                try:
                    line = sys.stdin.readline()
                except (EOFError, KeyboardInterrupt):
                    break
                if not line:
                    if sys.stdin.isatty():
                        break
                    time.sleep(0.5)
                    continue
                if line.strip():
                    in_q.put(line.strip())
        stop.set()

    threading.Thread(target=reader, daemon=True).start()
    threading.Thread(target=input_loop, daemon=True).start()

    state = TermState()
    prompt_buf = ""
    if use_tty:
        import termios
        import tty as ttymod
        try:
            saved_attrs = termios.tcgetattr(sys.stdin.fileno())
            ttymod.setcbreak(sys.stdin.fileno())
            mode = termios.tcgetattr(sys.stdin.fileno())
            mode[3] &= ~termios.ISIG
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, mode)
        except (termios.error, OSError):
            saved_attrs = None

    alt_screen = sys.stdout.isatty() and not SELF_TEST
    if alt_screen:
        sys.stdout.write("\x1b[?1049h\x1b[?25l")
        sys.stdout.flush()

    def send(ml):
        proc.stdin.write(ml + "\n")
        proc.stdin.flush()

    console.print("[bold]NPU OPS[/bold] — doğal dil / /scenario / /set / "
                  "/sensor-off / quit. Çıkış: quit / q / Ctrl-C.")
    t0 = time.monotonic()
    should_quit = False
    try:
        with Live(draw_layout(state, prompt_buf), console=console,
                  refresh_per_second=4) as live:
            while not stop.is_set():
                try:
                    line = out_q.get_nowait()
                except queue.Empty:
                    line = None
                if line is not None:
                    process_motor_line(state, line)
                try:
                    while True:
                        item = in_q.get_nowait()
                        if isinstance(item, tuple):
                            prompt_buf = item[1]
                        elif item == "p_toggle":
                            item = ("/continue" if state.paused
                                    else "/stop")
                            if handle_user_line(state, item, send, proc):
                                should_quit = True
                                stop.set()
                            else:
                                prompt_buf = ""
                        elif handle_user_line(state, item, send, proc):
                            should_quit = True
                            stop.set()
                        else:
                            prompt_buf = ""
                except queue.Empty:
                    pass
                if SELF_TEST and time.monotonic() - t0 > 3.0:
                    stop.set()
                    break
                if not state.paused:
                    state.events.age()
                live.update(draw_layout(state, prompt_buf))
                time.sleep(0.1)
                if should_quit:
                    break
            live.update(draw_layout(state, prompt_buf))  # son kare: piped
            time.sleep(0.2)                              # burst'te de görünsün
    except KeyboardInterrupt:
        pass
    finally:
        if alt_screen:
            sys.stdout.write("\x1b[?25h\x1b[?1049l")
            sys.stdout.flush()
        if saved_attrs is not None:
            import termios
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN,
                              saved_attrs)
        resume_motor(proc)  # donmuşsa önce çöz (yoksa QUIT/TERM işlemez)
        try:
            if proc.poll() is None:
                proc.stdin.write("QUIT\n")
                proc.stdin.flush()
                proc.wait(timeout=5)
        except Exception:
            pass
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        console.print("[green]motor kapatıldı.[/green]")


def self_test():
    """Kapı: bölgeler + grafik değişim kanıtı + kapı turu + temiz kapanış."""
    console = Console(file=io.StringIO(), width=120, height=50,
                      force_terminal=True)
    state = TermState()
    state.events.push("fire", "● NEM ateş t=25")
    state.events.push("dw", "▲ Δw NEM +0.021 → 1.312 (plato)")
    state.events.push("cpu", "[CPU Tercüman] Senaryo algılandı: KURAKLIK.")
    state.last = {"t": 100, "wire": 0.812, "f": "100000010",
                  "w": [1.312, 0.2, 0.5, 0.2, 0.2, 0.2, 0.2, 2.0, 0.2],
                  "cc": [3, 0, 7, 0, 0, 0, 0]}
    state.fires["NEM"] = 5
    state.wire_hist.extend([0.0, 0.4, 0.812, 0.2])
    state.paused = True
    console.print(draw_layout(state, "nem 70"))
    txt = console.file.getvalue()
    for needle in ("NPU OPS", "❯", "KOMUT GÜNLÜĞÜ", "AFFERENT", "GRAFİK",
                   "KURAKLIK", "Δw", "CPU Tercüman", "DURAKLATILDI",
                   "legend"):
        assert needle in txt, f"bölge eksik: {needle}"
    # grafik degisim kaniti: farkli gecmis -> farkli braille
    g1 = braille_plot([0.0, 0.5, 1.0, 0.5], 20)
    g2 = braille_plot([1.0, 0.2, 0.1, 0.9], 20)
    assert g1 and g2 and g1 != g2, "braille grafik sabit kaldı"
    proc = spawn_motor()
    try:
        os.set_blocking(proc.stdout.fileno(), False)

        def _drain():
            n = 0
            try:
                while True:
                    chunk = os.read(proc.stdout.fileno(), 65536)
                    if not chunk:
                        break
                    n += chunk.count(b"\n")
            except (BlockingIOError, OSError):
                pass
            return n

        def _drain_text():
            try:
                return os.read(proc.stdout.fileno(), 65536).decode(
                    "utf-8", "replace")
            except (BlockingIOError, OSError):
                return ""

        time.sleep(3.0)
        assert proc.poll() is None, "motor 3 sn yaşamadı"
        # kapi turu: kapat -> OK -> ac -> OK
        proc.stdin.write("SENSOR_OFF hn\n")
        proc.stdin.flush()
        time.sleep(0.5)
        assert "OK SENSOR_OFF hn" in _drain_text(), "kapı kapanmadı"
        proc.stdin.write("SENSOR_ON hn\n")
        proc.stdin.flush()
        time.sleep(0.5)
        assert "OK SENSOR_ON hn" in _drain_text(), "kapı açılmadı"
        assert pause_motor(proc), "SIGSTOP gönderilemedi"
        time.sleep(0.4)
        _drain()  # STOP öncesi artıkları at
        time.sleep(0.8)
        assert _drain() == 0, "duraklatılmış motor telemetri üretti"
        assert proc.poll() is None, "motor duraklatılamadı"
        assert resume_motor(proc), "SIGCONT gönderilemedi"
        time.sleep(1.2)
        assert _drain() > 0, "sürdürülen motor telemetri üretmedi"
        assert proc.poll() is None, "motor sürdürülemedi"
        os.set_blocking(proc.stdout.fileno(), True)
        proc.stdin.write("QUIT\n")
        proc.stdin.flush()
        proc.wait(timeout=10)
        assert proc.returncode == 0
    finally:
        resume_motor(proc)
        if proc.poll() is None:
            proc.kill()
    print("live_term --self-test: OK")


if __name__ == "__main__":
    if SELF_TEST:
        self_test()
    else:
        main()
