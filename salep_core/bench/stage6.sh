#!/bin/bash
# bench/stage6.sh — AŞAMA 6: seyrek-dünya nedensellik + baseline'lar + kontrol.
# Kullanım: stage6.sh [hücre-filtresi...] | stage6.sh nox | stage6.sh abl | stage6.sh finalize
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BENCH="$ROOT/bench"
G="$BENCH/results/stage6"
mkdir -p "$G" "$BENCH/build"
EXE="$BENCH/build/exp_causal"

build_all() {
  [ -x "$EXE" ] || g++ -std=c++17 -O2 -I"$ROOT/src" "$BENCH/exp_causal.cpp" -o "$EXE" || exit 1
}

run_cell() { # tag gen-args...
  local tag="$1"; shift
  local C="$G/$tag"
  [ -f "$C/done" ] && { echo "atla $tag (hazir)"; return; }
  mkdir -p "$C/data"
  for s in $(seq 1000 1009) $(seq 2000 2029); do
    python3 "$BENCH/gen.py" sparse --seed $s "$@" --out "$C/data/sparse_s$s" || exit 1
    "$EXE" --events "$C/data/sparse_s${s}_events.csv" --ticks 30000 \
      --out "$C/data/sparse_s$s" > /dev/null || exit 1
  done
  python3 "$BENCH/stage6_analysis.py" "$C/data" "$C" 1000 1009 2000 2029 30000 \
    > "$C/console.txt" 2>&1 || exit 1
  touch "$C/done"
  echo "hucre $tag OK"
}

if [ $# -eq 0 ]; then
  "$0" grid && "$0" nox && "$0" abl && exec "$0" finalize
fi
case "${1:-grid}" in
  grid)
    build_all
    filt="${2:-}"
    for p in 0.5 0.8 1.0; do for j in 0 2; do for q in 0.001 0.005; do
      tag="p${p}_j${j}_q${q}"
      [ -n "$filt" ] && [[ "$tag" != *"$filt"* ]] && continue
      run_cell "$tag" --p $p --j $j --q $q
    done; done; done
    ;;
  nox)
    build_all
    for q in 0.001 0.005; do
      tag="nox_q${q}"; C="$G/$tag"; mkdir -p "$C/data"
      [ -f "$C/done" ] && { echo "atla $tag"; continue; }
      for s in $(seq 2000 2029); do
        python3 "$BENCH/gen.py" sparse --seed $s --q $q --nox --out "$C/data/sparse_s$s" || exit 1
        "$EXE" --events "$C/data/sparse_s${s}_events.csv" --ticks 30000 \
          --out "$C/data/sparse_s$s" > "$C/data/s$s.log" 2>&1 || exit 1
      done
      python3 - "$C" <<'PY'
import csv, glob, sys
import numpy as np
C = sys.argv[1]
rates = []
for p in sorted(glob.glob(f"{C}/data/sparse_s*_tick.csv")):
    d = np.loadtxt(p, delimiter=",", skiprows=1)
    rates.append(float((d[:, 4] > 0).sum()) / d.shape[0])
import statistics as st
print(f"{C}: X-yok alarm hizi = {st.mean(rates):.6f}±{st.stdev(rates):.6f} /tick (n={len(rates)})")
with open(f"{C}/far.csv", "w") as f:
    f.write("mean,std,n\n%s,%s,%d\n" % (st.mean(rates), st.stdev(rates), len(rates)))
PY
      touch "$C/done"
    done
    ;;
  abl)
    build_all
    echo "=== stage6-abl: A1 (causal yolu) ==="
    sed -e 's|../src/sensory_lobe.h|src/sensory_lobe.h|' \
        -e 's|../src/causality.h|src/causality.h|' \
        -e 's|../src/causal_afferent.h|src/causal_afferent.h|' \
        -e 's|../src/predict.h|src/predict.h|' \
        "$BENCH/exp_causal.cpp" > "$BENCH/ablate/exp_causal_abl.cpp"
    g++ -std=c++17 -O2 -I"$BENCH/ablate" "$BENCH/ablate/exp_causal_abl.cpp" \
      -o "$BENCH/build/exp_causal_abl" || exit 1
    g++ -std=c++17 -O2 -DABL_NO_TRACE -I"$BENCH/ablate" "$BENCH/ablate/exp_causal_abl.cpp" \
      -o "$BENCH/build/exp_causal_notrace" || exit 1
    g++ -std=c++17 -O2 -DABL_NO_BONUS -I"$BENCH/ablate" "$BENCH/ablate/exp_causal_abl.cpp" \
      -o "$BENCH/build/exp_causal_nobonus" || exit 1
    EV="$G/p0.8_j2_q0.001/data/sparse_s2000_events.csv"
    "$EXE" --events "$EV" --ticks 30000 --out /tmp/a1c_src >/dev/null || exit 1
    "$BENCH/build/exp_causal_abl" --events "$EV" --ticks 30000 --out /tmp/a1c_abl >/dev/null || exit 1
    cmp -s /tmp/a1c_src_tick.csv /tmp/a1c_abl_tick.csv \
      && echo "A1-causal-kopya: bit-bit ayni" \
      || { echo "STAGE6 BATTI: A1 causal"; exit 1; }
    for cond in notrace nobonus; do
      C="$G/abl_$cond"; mkdir -p "$C/data"
      [ -f "$C/done" ] && { echo "atla abl_$cond"; continue; }
      for s in $(seq 1000 1009) $(seq 2000 2029); do
        ln -sf "$G/p0.8_j2_q0.001/data/sparse_s${s}_events.csv" "$C/data/" 2>/dev/null
        "$BENCH/build/exp_causal_$cond" --events "$C/data/sparse_s${s}_events.csv" \
          --ticks 30000 --out "$C/data/sparse_s$s" > /dev/null || exit 1
      done
      python3 "$BENCH/stage6_analysis.py" "$C/data" "$C" 1000 1009 2000 2029 30000 \
        > "$C/console.txt" 2>&1 || exit 1
      touch "$C/done"
      echo "ablasyon $cond OK"
    done
    echo "=== ablation tablosu (tam: demux + nedensellik) ==="
    python3 - "$BENCH" <<'PY'
import csv, statistics as st, sys
B = sys.argv[1]
def m6(path):
    rows = list(csv.DictReader(open(path)))
    p = [float(r["prec_L"]) for r in rows if r["method"] == "S"]
    r = [float(r["rec_L"]) for r in rows if r["method"] == "S"]
    return st.mean(p), st.stdev(p), st.mean(r), st.stdev(r)
bp, bps, br, brs = m6(f"{B}/results/stage6/p0.8_j2_q0.001/metrics.csv")
print(f"  baz: P={bp:.4f}±{bps:.4f} R={br:.4f}±{brs:.4f}")
rows = [("mekanizma", "ned_P_ort", "ned_P_std", "ned_R_ort", "ned_R_std", "dusus_P", "dusus_R"),
        ("baz", f"{bp:.4f}", f"{bps:.4f}", f"{br:.4f}", f"{brs:.4f}", "0", "0")]
for n in ("notrace", "nobonus"):
    p, ps, r, rs = m6(f"{B}/results/stage6/abl_{n}/metrics.csv")
    rows.append((n, f"{p:.4f}", f"{ps:.4f}", f"{r:.4f}", f"{rs:.4f}", f"{bp-p:+.4f}", f"{br-r:+.4f}"))
    print(f"  {n}: P={p:.4f}±{ps:.4f} (d{bp-p:+.4f}) R={r:.4f}±{rs:.4f} (d{br-r:+.4f})")
rows.append(("noplir", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A"))
rows.append(("npop1", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A"))
with open(f"{B}/results/stage4/ablation_causal.csv", "w") as f:
    for r in rows:
        f.write(",".join(r) + "\n")
print("not: noplir/npop1 nedensellikte yapisal N/A (eski-ISI pre'ler, FDM yok)")
PY
    ;;
  finalize)
    echo "=== stage6: toplama ==="
    python3 - "$G" <<'PY'
import csv, glob, statistics as st, sys
G = sys.argv[1]
print("hucre : S(P/R/lead) N1 N2 N3 (test ort)")
for m in sorted(glob.glob(f"{G}/p*/metrics.csv")):
    tag = m.split("/")[-2]
    rows = list(csv.DictReader(open(m)))
    line = []
    for md in ("S", "N1", "N2", "N3"):
        p = [float(r["prec_L"]) for r in rows if r["method"] == md]
        r = [float(r["rec_L"]) for r in rows if r["method"] == md]
        line.append(f"{md}:P={st.mean(p):.3f}/R={st.mean(r):.3f}")
    print(f"  {tag}: " + " ".join(line))
PY
    echo "=== stage6: regresyon ==="
    cp "$BENCH/baseline_snapshot/MANIFEST.sha256" /tmp/snap_before_stage6.txt
    "$BENCH/snapshot.sh" >/tmp/snap_rerun_stage6.log 2>&1 || exit 1
    cmp -s /tmp/snap_before_stage6.txt "$BENCH/baseline_snapshot/MANIFEST.sha256" \
      && echo "REGRESYON OK" || { echo "STAGE6 BATTI: regresyon"; exit 1; }
    echo "STAGE6: OK"
    ;;
esac
