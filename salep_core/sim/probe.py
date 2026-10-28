"""Terminal tüketici — renderer'sız kanıt (A2).

serve.py'ye bağlanır, N frame okur, SON frame'in özetini basar ve
günlerin monoton arttığını (latest-wins disiplini) doğrular.
G14 + G17'nin referans tarafı.

Kullanım:
    .venv/bin/python -m sim.probe [--port 41790] [--count 10]
"""
import argparse
import json
import socket
import sys


def read_frames(port, count, timeout=15.0):
    s = socket.create_connection(("127.0.0.1", port), timeout=timeout)
    s.settimeout(timeout)
    buf = ""
    frames = []
    try:
        while len(frames) < count:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk.decode("utf-8", "replace")
            while "\n" in buf and len(frames) < count:
                line, buf = buf.split("\n", 1)
                line = line.strip()
                if line.startswith("{"):
                    frames.append(json.loads(line))
    finally:
        s.close()
    return frames


def main():
    ap = argparse.ArgumentParser(description="Salep terminal tüketici")
    ap.add_argument("--port", type=int, default=41790)
    ap.add_argument("--count", type=int, default=10)
    args = ap.parse_args()

    frames = read_frames(args.port, args.count)
    assert frames, "PROBE BAŞARISIZ: frame alınamadı"
    days = [f["sim"]["day"] + f["sim"]["day_frac"] for f in frames]
    assert all(b >= a for a, b in zip(days, days[1:])), \
        f"PROBE BAŞARISIZ: monoton değil {days}"
    last = frames[-1]
    p = last["plant"]
    print(f"PROBE: n={len(frames)} gun={last['sim']['day']} "
          f"evre={p['stage']} hava={last['world']['temp_air']:.1f}C "
          f"nem={p['soil_moisture']:.0f} ec={p['soil_ec']:.2f} "
          f"hs={last['sensors']['hs']} gok={last['world']['sky']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
