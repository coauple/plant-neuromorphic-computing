#!/bin/bash
# bench/stage9.sh — AŞAMA 9: şekiller + son regresyon (REPORT.md el-yazımı).
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BENCH="$ROOT/bench"
export MPLCONFIGDIR=/tmp/mpl_bench
mkdir -p "$MPLCONFIGDIR"
echo "=== stage9: sekiller ==="
python3 "$BENCH/stage9_figs.py" "$BENCH" || exit 1
ls "$BENCH/figures/"*.png | wc -l
[ -f "$BENCH/REPORT.md" ] && echo "REPORT.md mevcut" || { echo "STAGE9 BATTI: REPORT yok"; exit 1; }
echo "=== stage9: repo temizlik + son regresyon ==="
find "$ROOT" -newermt "-600 minutes" -type f -not -path "*/bench/*" 2>/dev/null | grep . \
  && echo "UYARI: bench-disi degisen dosya var (yukarida)" || echo "TEMIZ: bench-disi degisiklik yok"
cp "$BENCH/baseline_snapshot/MANIFEST.sha256" /tmp/snap_before_stage9.txt
"$BENCH/snapshot.sh" >/tmp/snap_rerun_stage9.log 2>&1 || exit 1
cmp -s /tmp/snap_before_stage9.txt "$BENCH/baseline_snapshot/MANIFEST.sha256" \
  && echo "REGRESYON OK" || { echo "STAGE9 BATTI: regresyon"; exit 1; }
echo "STAGE9: OK"
