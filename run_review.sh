#!/usr/bin/env bash
# Salep Sibernetiği — hızlı yeniden-üretim kontrolü (~1-2 dk).
# Depoyu GEÇİCİ bir kopyada çalıştırır; kayıtlı dosyalara dokunmaz.
# Gereksinim: g++ (C++17) ve python3 (numpy). Kullanım: bash run_review.sh
set -u
SRC="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cp -a "$SRC/salep_core" "$TMP/salep_core"
cd "$TMP/salep_core" || exit 1
pass=0; fail=0
check() { # ad, koşul-sonucu(0=geçti), ayrıntı
  if [ "$2" -eq 0 ]; then echo "  [GEÇTİ] $1"; pass=$((pass+1)); else echo "  [KALDI] $1 — $3"; fail=$((fail+1)); fi
}

echo "== 1) Tek nöron deneyi (src/main.cpp) =="
g++ -std=c++17 -O2 -Isrc src/main.cpp -o "$TMP/npu_sim" 2>"$TMP/e1" ; check "derleme" $? "$(head -2 "$TMP/e1")"
mkdir "$TMP/r1" && ( cd "$TMP/r1" && "$TMP/npu_sim" >out.txt 2>&1 )
grep -q "500 tick, 6 ate" "$TMP/r1/out.txt"; check "çıktı: 500 tick, 6 ateşleme" $? "beklenen satır yok"
H=$(sha256sum "$TMP/r1/neuron_trace.csv" | cut -d' ' -f1)
[ "$H" = "8e91337c32f7a60e848651fe9def6b35ee86db137ceb1f61fe56da3256ba62d5" ]; check "SHA-256 kayıtlı değerle aynı" $? "$H"

echo "== 2) Örüntü lobu (src/main_pattern_lobe.cpp) =="
g++ -std=c++17 -O2 -Isrc src/main_pattern_lobe.cpp -o "$TMP/npu_pl" 2>"$TMP/e2"; check "derleme" $? "$(head -2 "$TMP/e2")"
mkdir "$TMP/r2" && ( cd "$TMP/r2" && "$TMP/npu_pl" --aff "$TMP/salep_core/testb_afferent.csv" --mem mem.csv --log log.csv --eta 0 --k4 0 >out.txt 2>&1 )
grep -q "OZET-PATTERN-LOB: k4=0 olay=300 mem=116" "$TMP/r2/out.txt"; check "OZET: olay=300 mem=116" $? "beklenen satır yok"

echo "== 3) Python doğrulamaları =="
if command -v python3 >/dev/null && python3 -c "import numpy" 2>/dev/null; then
  python3 validate_assoc.py >"$TMP/a.txt" 2>&1; grep -q "OZET-ASSOC" "$TMP/a.txt"; check "validate_assoc.py (association, 163/165)" $? "OZET yok"
  python3 validate_inference.py >"$TMP/i.txt" 2>&1
  grep -q "OK I1 deterministik" "$TMP/i.txt" && grep -q "OK I2 sizintisiz" "$TMP/i.txt"; check "validate_inference.py (determinizm + sızıntısızlık)" $? "OK satırları yok"
  grep "kurak->normal" "$TMP/i.txt" | head -1 | sed 's/^/     bulgu: /'
else
  echo "  [ATLANDI] python3/numpy yok (pip install numpy)"
fi

echo
echo "Sonuç: $pass geçti, $fail kaldı."
echo "Ayrıntılı sonuçların yorumu için README.md §8 ve §9'a bakın."
[ "$fail" -eq 0 ]
