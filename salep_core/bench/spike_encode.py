#!/usr/bin/env python3
"""bench/spike_encode.py — kayit -> tick teli kodlayici (AŞAMA 7, çekirdek dışı).

Boru hattı (tümü tamsayı matematiği, deterministik):
  10 kHz mono int16 wav -> 100 Hz'e mean-pool (x100, tamsayı bölme)
  -> tick = 10 ms (dt AÇIKÇA: 0.01 s/tick)
  -> delta-modülasyon: |x[t]-x[t-1]| >= THETA ise PULSE darbesi
Çıktı: {out}_wire.csv (tick,wire_q16) + {out}_ds.csv (tick,x100hz).
THETA kalibrasyon kayıtlarından seçilir (stage7_analysis), burada parametre.

Kullanım:
  spike_encode.py --wav F.wav --theta T --out P
"""
import argparse
import struct
import sys
import wave

Q16 = 1 << 16
PULSE_Q16 = int(0.8 * Q16)


def load_mono_int16(path):
    w = wave.open(path)
    if w.getframerate() != 10000 or w.getnchannels() != 1 or w.getsampwidth() != 2:
        raise ValueError(f"beklenen 10kHz/mono/16bit: {path}")
    n = w.getnframes()
    raw = w.readframes(n)
    return list(struct.unpack(f"<{n}h", raw))


def downsample100(x):
    n = len(x) // 100
    return [sum(x[i * 100:(i + 1) * 100]) // 100 for i in range(n)]


def encode(wav_path, theta, out_pre):
    x = load_mono_int16(wav_path)
    ds = downsample100(x)
    spikes = set()
    for t in range(1, len(ds)):
        if abs(ds[t] - ds[t - 1]) >= theta:
            spikes.add(t)
    with open(out_pre + "_wire.csv", "w") as f:
        f.write("tick,wire_q16\n")
        for t in range(len(ds)):
            f.write(f"{t},{PULSE_Q16 if t in spikes else 0}\n")
    with open(out_pre + "_ds.csv", "w") as f:
        f.write("tick,x\n")
        for t, v in enumerate(ds):
            f.write(f"{t},{v}\n")
    return len(ds), len(spikes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", required=True)
    ap.add_argument("--theta", type=int, required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    n, s = encode(a.wav, a.theta, a.out)
    print(f"OK encode: {n} tick, {s} darbe")


if __name__ == "__main__":
    sys.exit(main())
