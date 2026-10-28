#!/bin/bash
# bench/stage2.sh — AŞAMA 2: demux baseline karşılaştırması (temiz koşu).
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BENCH="$ROOT/bench"
DATA="$BENCH/results/stage2/data"
OUT="$BENCH/results/stage2"
STAMP=$(date +%s)
mkdir -p "$DATA" "$OUT" "$BENCH/build"
echo "=== stage2: exp_demux derle ==="
g++ -std=c++17 -O2 -I"$ROOT/src" "$BENCH/exp_demux.cpp" -o "$BENCH/build/exp_demux" || exit 1
echo "=== stage2: veri uret (kal 1000-1009, test 2000-2029) ==="
for s in $(seq 1000 1009) $(seq 2000 2029); do
  python3 "$BENCH/gen.py" demux --seed $s --out "$DATA/demux_s$s" || exit 1
done
echo "=== stage2: S-kolu kostur ==="
for s in $(seq 1000 1009) $(seq 2000 2029); do
  "$BENCH/build/exp_demux" --wire "$DATA/demux_s${s}_wire.csv" --taus 4,12 \
    --out "$DATA/demux_s$s" > /dev/null || exit 1
done
echo "=== stage2: metrikler ==="
python3 "$BENCH/stage2_analysis.py" "$DATA" "$OUT" "4,12" 1000 1009 2000 2029 || exit 1
echo "=== stage2: maliyet tablosu (on-hesap, formuller cost_prelim.csv'de) ==="
python3 - "$OUT/cost_prelim.csv" <<'PY'
import sys
# TICK-BAŞINA kağıt-üstü tahminler (Aşama 8'de ölçülecek; formül belgeli).
# S: üye-başına neuron_tick: difüzyon 4 mul, leak 3 mul, gating 3 mul+sönüm,
#    soma 1 mul + ~12 karsilastirma/toplama; 2 bant x 8 uye = 16 noron.
# B1: 1 AND + 1 toplama (kayan toplam) + tau-bit kayar yazmac.
# B2: 1 carpma + 2 toplama + W-ornek tamponu.
# B3: Goertzel: 2 carpma + 2 toplama + 2 durum-sozcugu (blok başına).
# B4: 1 karsilastirma (kenar) + sayaç + ~3 hücre histogramı.
rows = [
 ("S(fdm,2x8)", "16*11=176 mul", "~16*14=224 add/cmp", "16 noron x ~480b = ~7.7Kb"),
 ("B1", "0 mul", "2 add + 1 AND", "tau+8 bit (<24b)"),
 ("B2", "1 mul", "2 add", "100 ornek x 16b = 1.6Kb"),
 ("B3", "2 mul", "2 add", "2 x 32b + katsayi"),
 ("B4", "0 mul", "~2 add/cmp", "~4 sayac x 8b"),
]
with open(sys.argv[1], "w") as f:
    f.write("yontem,mul_per_tick,addcmp_per_tick,durum_bit\n")
    for r in rows:
        f.write(",".join(r) + "\n")
print("OK cost_prelim")
PY
echo "=== stage2: regresyon ==="
cp "$BENCH/baseline_snapshot/MANIFEST.sha256" /tmp/snap_before_stage2.txt
"$BENCH/snapshot.sh" >/tmp/snap_rerun_stage2.log 2>&1 || exit 1
cmp -s /tmp/snap_before_stage2.txt "$BENCH/baseline_snapshot/MANIFEST.sha256" \
  && echo "REGRESYON OK" || { echo "STAGE2 BATTI: regresyon"; exit 1; }
echo "STAGE2: OK"
