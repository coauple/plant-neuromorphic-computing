#!/bin/bash
# bench/stage7.sh — AŞAMA 7: gerçek veri (figshare bitki e-phys kütüphanesi).
# Adımlar: fetch -> kodlayıcı birim testi -> theta(on-geçiş) -> kodla -> S -> analiz.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BENCH="$ROOT/bench"
RD="$BENCH/real_data"
WORK="$RD/work"
OUT="$BENCH/results/stage7"
MD5REF="4e720f041014c8db4186b25f0de271dc"
mkdir -p "$RD" "$WORK" "$OUT"

echo "=== stage7: fetch (yoksa) ==="
if [ ! -f "$RD/plant_lib.rar" ]; then
  python3 - "$RD/plant_lib.rar" <<'PY'
import json, subprocess, sys, urllib.request
d = json.load(urllib.request.urlopen("https://api.figshare.com/v2/articles/25425920", timeout=60))
url = [f for f in d["files"] if f["name"].endswith(".rar")][0]["download_url"]
r = subprocess.run(["curl", "-sL", url, "-o", sys.argv[1], "--max-time", "600"])
sys.exit(r.returncode)
PY
  [ $? -ne 0 ] && { echo "STAGE7: indirme basarisiz (ag yok?) — gerekceyle atlandi"; exit 2; }
fi
echo "$MD5REF  $RD/plant_lib.rar" | md5sum -c - || { echo "STAGE7 BATTI: md5 uyumsuz"; exit 1; }
if [ ! -d "$WORK/Ocimum" ]; then
  UNRAR=""
  [ -x "$RD/tools/usr/bin/unrar-nonfree" ] && UNRAR="$RD/tools/usr/bin/unrar-nonfree"
  if [ -z "$UNRAR" ]; then
    ( cd /tmp && apt-get download unrar >/dev/null 2>&1 ) || { echo "STAGE7: unrar alinamadi — atlandi"; exit 2; }
    mkdir -p "$RD/tools" && dpkg-deb -x /tmp/unrar_*.deb "$RD/tools" || exit 1
    UNRAR="$RD/tools/usr/bin/unrar-nonfree"
  fi
  "$UNRAR" x -o+ "$RD/plant_lib.rar" "$WORK/" >/dev/null 2>&1 || exit 1
fi
mkdir -p "$WORK/flat"
find "$WORK" -path "*Ocimum*" -name "*.wav" -exec cp {} "$WORK/flat/" \; 2>/dev/null
find "$WORK" -path "*Ocimum*" -name "*-events.txt" -exec cp {} "$WORK/flat/" \; 2>/dev/null
ls "$WORK/flat/"*.wav | wc -l
echo "=== stage7: kodlayici birim testi (sentetik) ==="
python3 - "$BENCH" <<'PY'
import struct, wave, subprocess, sys
BENCH = sys.argv[1]
p = "/tmp/enc_test.wav"
w = wave.open(p, "w")
w.setframerate(10000); w.setnchannels(1); w.setsampwidth(2)
# 300 ornek: 0-düz, +5000 adım (100-199), 0-düz (200-299) -> 100Hz'de [0,5000,0]
x = [0]*100 + [5000]*100 + [0]*100
w.writeframes(struct.pack(f"<{len(x)}h", *x)); w.close()
r = subprocess.run(["python3", BENCH + "/spike_encode.py",
                    "--wav", p, "--theta", "1000", "--out", "/tmp/enc_test"],
                   capture_output=True, text=True)
print(r.stdout, r.stderr)
ticks = [l.strip() for l in open("/tmp/enc_test_wire.csv") if not l.startswith("tick")]
assert ticks == ["0,0", "1,52428", "2,52428"], f"beklenmeyen tel: {ticks}"
print("OK encoder-unit: adim kenarlari 2 darbe")
PY
echo "=== stage7: on-kodlama (theta=1, ds icin) ==="
for w in "$WORK/flat/"*.wav; do
  b="${w%.wav}"
  python3 "$BENCH/spike_encode.py" --wav "$w" --theta 1 --out "$b" >/dev/null || exit 1
done
echo "=== stage7: THETA (kalibrasyon) ==="
python3 "$BENCH/stage7_analysis.py" "$WORK/flat" "$OUT" theta || exit 1
THETA=$(cut -d= -f2 "$OUT/theta.txt" | cut -d' ' -f1)
echo "THETA=$THETA ile yeniden kodla + S kostur"
[ -x "$BENCH/build/exp_demux" ] || \
  g++ -std=c++17 -O2 -I"$ROOT/src" "$BENCH/exp_demux.cpp" -o "$BENCH/build/exp_demux" || exit 1
for w in "$WORK/flat/"*.wav; do
  b="${w%.wav}"
  python3 "$BENCH/spike_encode.py" --wav "$w" --theta "$THETA" --out "$b" >/dev/null || exit 1
  "$BENCH/build/exp_demux" --wire "${b}_wire.csv" --taus 12 --pops 8 --plir 1 \
    --win 100 --out "$b" >/dev/null || exit 1
done
echo "=== stage7: analiz ==="
python3 "$BENCH/stage7_analysis.py" "$WORK/flat" "$OUT" full || exit 1
echo "=== stage7: regresyon ==="
cp "$BENCH/baseline_snapshot/MANIFEST.sha256" /tmp/snap_before_stage7.txt
"$BENCH/snapshot.sh" >/tmp/snap_rerun_stage7.log 2>&1 || exit 1
cmp -s /tmp/snap_before_stage7.txt "$BENCH/baseline_snapshot/MANIFEST.sha256" \
  && echo "REGRESYON OK" || { echo "STAGE7 BATTI: regresyon"; exit 1; }
echo "STAGE7: OK"
