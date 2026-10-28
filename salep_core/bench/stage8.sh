#!/bin/bash
# bench/stage8.sh — AŞAMA 8: donanım maliyeti (ölçülen + kağıt-üstü).
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BENCH="$ROOT/bench"
OUT="$BENCH/results/stage8"
mkdir -p "$OUT" "$BENCH/build"
echo "=== stage8: cost_probe derle + kostur ==="
g++ -std=c++17 -O2 -I"$ROOT/src" "$BENCH/cost_probe.cpp" -o "$BENCH/build/cost_probe" || exit 1
WIRE="$BENCH/results/stage2/data/demux_s2000_wire.csv"
"$BENCH/build/cost_probe" "$WIRE" 4,12 | tee "$OUT/probe.txt"
echo "=== stage8: islem sayaci (ablate kopya + COUNT_OPS) ==="
python3 "$BENCH/ablate/mk_ablate.py" || exit 1
g++ -std=c++17 -O2 -DCOUNT_OPS -I"$BENCH/ablate" "$BENCH/ablate/exp_demux_abl.cpp" \
  -o "$BENCH/build/exp_demux_count" || exit 1
# Sayaç okuma: minik ayrı TU (count_main.cpp, ablate başlıklarıyla).
cat > "$BENCH/ablate/count_main.cpp" <<'EOF'
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#include "src/fdm.h"
int main(int argc, char** argv) {
    FILE* f = fopen(argv[1], "r");
    std::vector<int32_t> wire;
    char line[256];
    if (!fgets(line, sizeof(line), f)) return 1;
    while (fgets(line, sizeof(line), f)) {
        char* c = strchr(line, ',');
        if (c) wire.push_back((int32_t)strtol(c + 1, nullptr, 10));
    }
    fclose(f);
    FdmNetwork net;
    int32_t ta[3] = {4, 12, 0};
    int po[3] = {8, 8, 0};
    bench_cnt_mul = 0;
    bench_cnt_div = 0;
    fdm_init(net, ta, po, 2, 1, 7001);
    long init_mul = bench_cnt_mul, init_div = bench_cnt_div;
    for (size_t t = 0; t < wire.size(); ++t) fdm_tick(net, (int32_t)t, wire[t]);
    long n = (long)wire.size();
    printf("tick=%ld toplam_mul=%ld toplam_div=%ld mul_per_tick=%.2f div_per_tick=%.4f (init haric: mul=%ld div=%ld)\n",
           n, bench_cnt_mul, bench_cnt_div,
           (double)(bench_cnt_mul - init_mul) / n,
           (double)(bench_cnt_div - init_div) / n,
           bench_cnt_mul - init_mul, bench_cnt_div - init_div);
    return 0;
}
EOF
g++ -std=c++17 -O2 -DCOUNT_OPS -I"$BENCH/ablate" "$BENCH/ablate/count_main.cpp" \
  -o "$BENCH/build/count_main" || exit 1
"$BENCH/build/count_main" "$WIRE" | tee "$OUT/opcount.txt"
# A1: sayaçlı kopya, makrosuzken orijinalle aynı mı? (mk_ablate sonrası tekrar)
g++ -std=c++17 -O2 -I"$BENCH/ablate" "$BENCH/ablate/exp_demux_abl.cpp" \
  -o "$BENCH/build/exp_demux_abl" || exit 1
"$BENCH/build/exp_demux_abl" --wire "$WIRE" --taus 4,12 --out /tmp/a1_re >/dev/null || exit 1
"$BENCH/build/exp_demux" --wire "$WIRE" --taus 4,12 --out /tmp/a1_src2 >/dev/null || exit 1
cmp -s /tmp/a1_re_tick.csv /tmp/a1_src2_tick.csv \
  && echo "A1-tekrar: kopya hala bit-bit ayni" \
  || { echo "STAGE8 BATTI: A1 regresyonu"; exit 1; }
echo "=== stage8: sentez araci kontrolu ==="
for t in vitis_hls vivado yosys nextpnr openlane qflow; do
  which $t 2>/dev/null || echo "yok: $t"
done | tee "$OUT/synth_tools.txt"
echo "=== stage8: toplama ==="
python3 - "$OUT" <<'PY'
import csv, statistics as st, sys
OUT = sys.argv[1]
probe = open(f"{OUT}/probe.txt").read()
opc = open(f"{OUT}/opcount.txt").read()
print(probe.strip())
print(opc.strip())
# Sinaps ağırlık gözlenen aralığı: snapshot causality CSV (mevcut veri, yeniden kullanım).
rows = list(csv.DictReader(open(
    "/home/metehan/Masaüstü/Bitki nöromorfik/salep_core/bench/baseline_snapshot/causality/causality_learning.csv")))
w0 = [float(r["w0"]) for r in rows]
w2 = [float(r["w2"]) for r in rows]
print(f"gozlenen agirlik: w0=[{min(w0):.4f},{max(w0):.4f}] w2=[{min(w2):.4f},{max(w2):.4f}] "
      f"(kod siniri [0,2.0]; trace [0,1] kirpmali)")
with open(f"{OUT}/weight_range.txt", "w") as f:
    f.write(f"w0_min={min(w0):.4f} w0_max={max(w0):.4f} w2_min={min(w2):.4f} w2_max={max(w2):.4f}\n")
print("OK stage8-toplama (bit-genisligi tablosu REPORT'ta)")
PY
echo "=== stage8: regresyon ==="
cp "$BENCH/baseline_snapshot/MANIFEST.sha256" /tmp/snap_before_stage8.txt
"$BENCH/snapshot.sh" >/tmp/snap_rerun_stage8.log 2>&1 || exit 1
cmp -s /tmp/snap_before_stage8.txt "$BENCH/baseline_snapshot/MANIFEST.sha256" \
  && echo "REGRESYON OK" || { echo "STAGE8 BATTI: regresyon"; exit 1; }
echo "STAGE8: OK"
