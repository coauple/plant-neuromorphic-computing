#!/bin/bash
# bench/stage3.sh — AŞAMA 3: gürültü ızgarası (pextra x jit).
# Kullanım: stage3.sh [PEX_LIST] [JIT_LIST]  (varsayılan: tam ızgara)
# Parça parça koşulabilir; toplama + regresyon için: stage3.sh finalize
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BENCH="$ROOT/bench"
G="$BENCH/results/stage3"
mkdir -p "$G" "$BENCH/build"

if [ "${1:-}" = "finalize" ]; then
  echo "=== stage3: toplama + yari-AUC ==="
  python3 "$BENCH/stage3_aggregate.py" "$G" || exit 1
  echo "=== stage3: regresyon ==="
  cp "$BENCH/baseline_snapshot/MANIFEST.sha256" /tmp/snap_before_stage3.txt
  "$BENCH/snapshot.sh" >/tmp/snap_rerun_stage3.log 2>&1 || exit 1
  cmp -s /tmp/snap_before_stage3.txt "$BENCH/baseline_snapshot/MANIFEST.sha256" \
    && echo "REGRESYON OK" || { echo "STAGE3 BATTI: regresyon"; exit 1; }
  echo "STAGE3: OK"
  exit 0
fi

if [ $# -eq 0 ]; then
  "$0" "0 2 5 10 20 30" "0 10 20 30" && exec "$0" finalize
fi
PEXS="${1:-0 2 5 10 20 30}"
JITS="${2:-0 10 20 30}"
[ -x "$BENCH/build/exp_demux" ] || \
  g++ -std=c++17 -O2 -I"$ROOT/src" "$BENCH/exp_demux.cpp" -o "$BENCH/build/exp_demux" || exit 1
for p in $PEXS; do
  for j in $JITS; do
    C="$G/p${p}_j${j}"
    [ -f "$C/done" ] && { echo "atla p$p j$j (hazir)"; continue; }
    mkdir -p "$C/data"
    for s in $(seq 1000 1009) $(seq 2000 2029); do
      python3 "$BENCH/gen.py" demux --seed $s --pextra $p --jit $j \
        --out "$C/data/demux_s$s" || exit 1
      "$BENCH/build/exp_demux" --wire "$C/data/demux_s${s}_wire.csv" \
        --taus 4,12 --out "$C/data/demux_s$s" > /dev/null || exit 1
    done
    python3 "$BENCH/stage2_analysis.py" "$C/data" "$C" "4,12" 1000 1009 2000 2029 \
      > "$C/console.txt" 2>&1 || exit 1
    touch "$C/done"
    echo "hucre p$p j$j OK"
  done
done
