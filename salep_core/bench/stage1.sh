#!/bin/bash
# bench/stage1.sh — AŞAMA 1: harness + üreteçler + H1-H4 kapıları + regresyon.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BENCH="$ROOT/bench"
RES="$BENCH/results/stage1"
STAMP=$(date +%s)
mkdir -p "$RES" "$BENCH/build"
echo "=== stage1: harness testi derle + kostur ==="
g++ -std=c++17 -O2 -I"$BENCH" "$BENCH/harness_test.cpp" -o "$BENCH/build/harness_test" \
  || { echo "STAGE1 BATTI: harness derlenmedi"; exit 1; }
echo "=== stage1: duman setleri (seed 2000-2002) ==="
for s in 2000 2001 2002; do
  python3 "$BENCH/gen.py" demux --seed $s --out "$RES/demux_s$s" || exit 1
  python3 "$BENCH/gen.py" sparse --seed $s --out "$RES/sparse_s$s" || exit 1
done
"$BENCH/build/harness_test" "$RES/demux_s2000" || exit 1
echo "=== stage1: H3 icin 30 seed sparse ==="
for s in $(seq 2003 2029); do
  python3 "$BENCH/gen.py" sparse --seed $s --out "$RES/sparse_s$s" || exit 1
done
echo "=== stage1: H1-H4 ==="
python3 "$BENCH/check_stage1.py" "$STAMP" || exit 1
echo "=== stage1: regresyon (snapshot karsilastir) ==="
cp "$BENCH/baseline_snapshot/MANIFEST.sha256" /tmp/snap_before_stage1.txt
"$BENCH/snapshot.sh" >/tmp/snap_rerun_stage1.log 2>&1 || exit 1
if cmp -s /tmp/snap_before_stage1.txt "$BENCH/baseline_snapshot/MANIFEST.sha256"; then
  echo "REGRESYON OK: snapshot bit-bit ayni"
else
  echo "STAGE1 BATTI: regresyon farki"; exit 1
fi
echo "STAGE1: OK"
