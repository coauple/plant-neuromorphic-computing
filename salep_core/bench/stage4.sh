#!/bin/bash
# bench/stage4.sh — AŞAMA 4: ablasyon (demux kolu; nedensellik kolu Aşama 6'da
# aynı altyapıyla eklenir). Orijinal çekirdeğe DOKUNULMAZ.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BENCH="$ROOT/bench"
A="$BENCH/results/stage4"
AB="$BENCH/ablate"
mkdir -p "$A" "$BENCH/build"
echo "=== stage4: ablate kopyasi olustur ==="
python3 "$AB/mk_ablate.py" || exit 1
sed 's|../src/fdm.h|src/fdm.h|' "$BENCH/exp_demux.cpp" > "$AB/exp_demux_abl.cpp"
grep -q 'include "src/fdm.h"' "$AB/exp_demux_abl.cpp" || exit 1
echo "=== stage4: derlemeler ==="
g++ -std=c++17 -O2 -I"$AB" "$AB/exp_demux_abl.cpp" -o "$BENCH/build/exp_demux_abl" || exit 1
g++ -std=c++17 -O2 -DABL_NO_BONUS -I"$AB" "$AB/exp_demux_abl.cpp" -o "$BENCH/build/exp_demux_nobonus" || exit 1
g++ -std=c++17 -O2 -I"$ROOT/src" "$AB/syn_probe.cpp" -o "$BENCH/build/syn_probe_src" || exit 1
g++ -std=c++17 -O2 -I"$AB/src" "$AB/syn_probe.cpp" -o "$BENCH/build/syn_probe_abl" || exit 1
g++ -std=c++17 -O2 -DABL_NO_TRACE -I"$AB/src" "$AB/syn_probe.cpp" -o "$BENCH/build/syn_probe_notrace" || exit 1
echo "=== stage4: A1 esdegerlik kanitlari ==="
WIRE="$BENCH/results/stage2/data/demux_s2000_wire.csv"
"$BENCH/build/exp_demux" --wire "$WIRE" --taus 4,12 --out /tmp/a1_src >/dev/null || exit 1
"$BENCH/build/exp_demux_abl" --wire "$WIRE" --taus 4,12 --out /tmp/a1_abl >/dev/null || exit 1
cmp -s /tmp/a1_src_tick.csv /tmp/a1_abl_tick.csv \
  && echo "A1-neuron-kopya: bit-bit ayni" \
  || { echo "STAGE4 BATTI: A1 neuron"; exit 1; }
"$BENCH/build/syn_probe_src" > /tmp/a1_syn_src.txt
"$BENCH/build/syn_probe_abl" > /tmp/a1_syn_abl.txt
cmp -s /tmp/a1_syn_src.txt /tmp/a1_syn_abl.txt \
  && echo "A1-synapse-kopya: bit-bit ayni" \
  || { echo "STAGE4 BATTI: A1 synapse"; exit 1; }
"$BENCH/build/exp_demux_nobonus" --wire "$WIRE" --taus 4,12 --out /tmp/a1_nb >/dev/null || exit 1
cmp -s /tmp/a1_src_tick.csv /tmp/a1_nb_tick.csv \
  && echo "A3-onbellek: nobonus demux'ta bit-bit ayni (beklendigi gibi, Dal B bos)" \
  || echo "A3-not: nobonus demux'ta FARKLI cikti (incelenecek)"
"$BENCH/build/syn_probe_notrace" > /tmp/a1_syn_nt.txt
cmp -s /tmp/a1_syn_src.txt /tmp/a1_syn_nt.txt \
  && echo "NOT: notrace probu da ayni (iz yola girmedi?)" \
  || echo "OK: notrace probu farkli (iz mekanizmasi devrede)"
echo "=== stage4: demux ablasyon kosulari (test seti) ==="
S2D="$BENCH/results/stage2/data"
run_abl() { # name ; exp-args... (S2 verisini symlink ile yeniden kullanir)
  local n="$1"; shift
  local d="$A/$n/data"
  mkdir -p "$d"
  for s in $(seq 1000 1009) $(seq 2000 2029); do
    ln -sf "$S2D/demux_s${s}_wire.csv" "$d/" 2>/dev/null
    ln -sf "$S2D/demux_s${s}_windows.csv" "$d/" 2>/dev/null
    "$@" --wire "$d/demux_s${s}_wire.csv" --taus 4,12 --out "$d/demux_s$s" > /dev/null || exit 1
  done
  python3 "$BENCH/stage2_analysis.py" "$d" "$A/$n" "4,12" 1000 1009 2000 2029 \
    > "$A/$n/console.txt" 2>&1 || exit 1
  echo "ablasyon $n OK"
}
run_abl noplir "$BENCH/build/exp_demux" --plir 0
run_abl npop1 "$BENCH/build/exp_demux" --pops 1,1
run_abl nobonus "$BENCH/build/exp_demux_nobonus"
echo "=== stage4: demux ablasyon tablosu ==="
python3 - "$A" <<'PY'
import csv, statistics as st, sys
A = sys.argv[1]
base = list(csv.DictReader(open(f"{A}/../stage2/auc.csv")))
out = [("mekanizma", "tau4_ort", "tau4_std", "tau12_ort", "tau12_std",
        "dusuk_tau4", "dusuk_tau12")]
def ms(rows, t):
    v = [float(r["auc"]) for r in rows if r["method"] == "S" and r["tau"] == t]
    return st.mean(v), st.stdev(v)
b4, s4 = ms(base, "4")
b12, s12 = ms(base, "12")
out.append(("baz", f"{b4:.4f}", f"{s4:.4f}", f"{b12:.4f}", f"{s12:.4f}", "0", "0"))
for n in ("noplir", "npop1", "nobonus"):
    rows = list(csv.DictReader(open(f"{A}/{n}/auc.csv")))
    m4, d4 = ms(rows, "4")
    m12, d12 = ms(rows, "12")
    out.append((n, f"{m4:.4f}", f"{d4:.4f}", f"{m12:.4f}", f"{d12:.4f}",
                f"{b4-m4:+.4f}", f"{b12-m12:+.4f}"))
    print(f"  {n}: tau4={m4:.4f}±{d4:.4f} tau12={m12:.4f}±{d12:.4f}")
out.append(("notrace", "N/A", "N/A", "N/A", "N/A"))
with open(f"{A}/ablation_demux.csv", "w") as f:
    for r in out:
        f.write(",".join(r) + "\n")
print("not: notrace demux'ta yapisal N/A (fdm yolunda synapse cagrisi yok)")
PY
echo "=== stage4: regresyon ==="
cp "$BENCH/baseline_snapshot/MANIFEST.sha256" /tmp/snap_before_stage4.txt
"$BENCH/snapshot.sh" >/tmp/snap_rerun_stage4.log 2>&1 || exit 1
cmp -s /tmp/snap_before_stage4.txt "$BENCH/baseline_snapshot/MANIFEST.sha256" \
  && echo "REGRESYON OK" || { echo "STAGE4 BATTI: regresyon"; exit 1; }
echo "STAGE4-demux: OK (nedensellik sutunu Asama 6'da eklenecek)"
