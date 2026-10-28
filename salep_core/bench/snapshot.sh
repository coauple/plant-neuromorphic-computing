#!/bin/bash
# AŞAMA 0 anlık görüntüsü: tüm main_*.cpp'yi derle + koştur + SHA256 kaydet.
# Repo'ya YAZMAZ: derleme bench/build'e, çıktılar bench/baseline_snapshot'a.
# Girdi olarak repo CSV'leri salt-okunur kullanılır.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SNAP="$ROOT/bench/baseline_snapshot"
BUILD="$ROOT/bench/build"
LOG="$SNAP/snapshot.log"
mkdir -p "$BUILD" "$SNAP"
: > "$LOG"
echo "compiler: $(g++ --version | head -1)" | tee -a "$LOG"
echo "flags: -std=c++17 -O2" | tee -a "$LOG"
echo "date: $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG"

build() { # name src
  g++ -std=c++17 -O2 -I"$ROOT/src" "$ROOT/src/$2" -o "$BUILD/$1" 2>>"$LOG" \
    && echo "BUILD OK $1" | tee -a "$LOG" \
    || echo "BUILD FAIL $1 (dokunulmadı, listede)" | tee -a "$LOG"
}
run() { # name... (runs in own dir, 300s timeout)
  local name="$1"; local d="$SNAP/$1"; shift
  mkdir -p "$d"
  ( cd "$d" && timeout 300 "$@" >stdout.txt 2>stderr.txt; echo "exit=$?" >exit.txt )
  ( cd "$d" && sha256sum stdout.txt stderr.txt exit.txt *.csv 2>/dev/null >SHA256SUMS )
  echo "RUN $name exit=$(cat "$d/exit.txt")" | tee -a "$LOG"
}

build sim main.cpp
build branch main_branch.cpp
build multi main_multi.cpp
build sim_event main_event.cpp
build synapse main_synapse.cpp
build network main_network.cpp
build phase_group main_phase_group.cpp
build causality main_causality.cpp
build fdm main_fdm.cpp
build plant_npu main_plant_npu.cpp
build sensory_lobe main_sensory_lobe.cpp
build sensory_plant main_sensory_plant.cpp
build causal_afferent main_causal_afferent.cpp
build pattern_lobe main_pattern_lobe.cpp
build k4_rel main_pattern_lobe_k4_rel.cpp

[ -x "$BUILD/sim" ] && run sim "$BUILD/sim"
[ -x "$BUILD/branch" ] && run branch "$BUILD/branch" -all
[ -x "$BUILD/multi" ] && run multi "$BUILD/multi"
[ -x "$BUILD/sim_event" ] && run sim_event "$BUILD/sim_event"
[ -x "$BUILD/synapse" ] && run synapse "$BUILD/synapse"
[ -x "$BUILD/network" ] && run network "$BUILD/network"
[ -x "$BUILD/phase_group" ] && run phase_group "$BUILD/phase_group"
[ -x "$BUILD/causality" ] && run causality "$BUILD/causality"
[ -x "$BUILD/fdm" ] && run fdm "$BUILD/fdm"
[ -x "$BUILD/plant_npu" ] && run plant_npu "$BUILD/plant_npu"
[ -x "$BUILD/sensory_lobe" ] && run sensory_lobe_batch "$BUILD/sensory_lobe"
[ -x "$BUILD/sensory_lobe" ] && run sensory_lobe_selforg "$BUILD/sensory_lobe" --selforg
[ -x "$BUILD/sensory_lobe" ] && run sensory_lobe_stress "$BUILD/sensory_lobe" --stress
[ -x "$BUILD/sensory_plant" ] && run sensory_plant "$BUILD/sensory_plant" \
  --spikes "$ROOT/testb_spikes.csv" --sensors "$ROOT/testb_sensors.csv" \
  --out cond.csv --cond 22 --test 3 --diag diag.csv --aff aff.csv
[ -x "$BUILD/causal_afferent" ] && run causal_afferent "$BUILD/causal_afferent"
[ -x "$BUILD/pattern_lobe" ] && run pattern_k4off "$BUILD/pattern_lobe" \
  --aff "$ROOT/testb_afferent.csv" --mem mem.csv --log log.csv --eta 0 --k4 0
[ -x "$BUILD/pattern_lobe" ] && run pattern_k4on "$BUILD/pattern_lobe" \
  --aff "$ROOT/testb_afferent.csv" --mem mem.csv --log log.csv --eta 0 --k4 1 \
  --k4csv k4.csv --k4paircsv k4pair.csv --k4idcsv k4id.csv
[ -x "$BUILD/k4_rel" ] && run k4_rel "$BUILD/k4_rel"

( cd "$SNAP" && sha256sum */SHA256SUMS >MANIFEST.sha256 2>/dev/null )
echo "SNAPSHOT DONE" | tee -a "$LOG"
