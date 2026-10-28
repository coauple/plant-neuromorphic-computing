#!/bin/bash
# bench/stage5.sh — AŞAMA 5: genelleme (kalibre-dışı tau). Parametre DEĞİŞMEZ.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BENCH="$ROOT/bench"
G="$BENCH/results/stage5"
mkdir -p "$G"
[ -x "$BENCH/build/exp_demux" ] || \
  g++ -std=c++17 -O2 -I"$ROOT/src" "$BENCH/exp_demux.cpp" -o "$BENCH/build/exp_demux" || exit 1
run_cfg() { # tag taus foreign
  local tag="$1" taus="$2" foreign="$3"
  local C="$G/$tag"
  [ -f "$C/done" ] && { echo "atla $tag (hazir)"; return; }
  mkdir -p "$C/data"
  for s in $(seq 1000 1009) $(seq 2000 2029); do
    python3 "$BENCH/gen.py" demux --seed $s --taus "$taus" --foreign "$foreign" \
      --out "$C/data/demux_s$s" || exit 1
    "$BENCH/build/exp_demux" --wire "$C/data/demux_s${s}_wire.csv" --taus "$taus" \
      --out "$C/data/demux_s$s" > /dev/null || exit 1
  done
  python3 "$BENCH/stage2_analysis.py" "$C/data" "$C" "$taus" 1000 1009 2000 2029 \
    > "$C/console.txt" 2>&1 || exit 1
  touch "$C/done"
  echo "cfg $tag OK"
}
run_cfg tau5 5 4,8,12
run_cfg tau6 6 4,8,12
run_cfg tau7 7 4,8,12
run_cfg tau9 9 4,8,12
run_cfg tau10 10 4,8,12
run_cfg tau11 11 4,8,12
run_cfg tau13 13 4,8,12
run_cfg tau14 14 4,8,12
run_cfg tau15 15 4,8,12
run_cfg pair6_14 6,14 4,8,12
run_cfg pair5_10 5,10 4,8,12
run_cfg pair7_15 7,15 4,8,12
echo "=== stage5: toplama ==="
python3 - "$G" <<'PY'
import csv, glob, statistics as st, sys
G = sys.argv[1]
print("cfg : S-AUC test ort±std (hedef-basina)")
for cfg in sorted(glob.glob(f"{G}/*/auc.csv")):
    tag = cfg.split("/")[-2]
    rows = list(csv.DictReader(open(cfg)))
    taus = sorted({r["tau"] for r in rows if r["method"] == "S"})
    line = []
    for t in taus:
        v = [float(r["auc"]) for r in rows if r["method"] == "S" and r["tau"] == t]
        flag = " BOZUK(<0.7)" if st.mean(v) < 0.7 else ""
        line.append(f"tau{t}={st.mean(v):.3f}±{st.stdev(v):.3f}{flag}")
    print(f"  {tag}: " + " ".join(line))
PY
echo "=== stage5: regresyon ==="
cp "$BENCH/baseline_snapshot/MANIFEST.sha256" /tmp/snap_before_stage5.txt
"$BENCH/snapshot.sh" >/tmp/snap_rerun_stage5.log 2>&1 || exit 1
cmp -s /tmp/snap_before_stage5.txt "$BENCH/baseline_snapshot/MANIFEST.sha256" \
  && echo "REGRESYON OK" || { echo "STAGE5 BATTI: regresyon"; exit 1; }
echo "STAGE5: OK (ayarli sutun: bu asamada ayarlama yapilmadi)"
