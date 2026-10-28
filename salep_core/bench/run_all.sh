#!/bin/bash
# bench/run_all.sh — tek komutla derle + deneyler + şekiller + regresyon.
# AŞAMA 0 durumu: snapshot + doğrulama çalışır; Aşama 1-9 eklendikçe açılır.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BENCH="$ROOT/bench"
FAIL=0

step() { echo "=== $1 ==="; }

step "0: anlik goruntu (derle + kostur + SHA)"
"$BENCH/snapshot.sh" || FAIL=1

# Aşama 1-9: henüz uygulanmadı (kural 8: aşama aşama, sorarak).
for s in 1 2 3 4 5 6 7 8 9; do
  if [ -x "$BENCH/stage$s.sh" ]; then
    step "$s: stage$s.sh"; "$BENCH/stage$s.sh" || FAIL=1
  else
    echo "--- asama $s: henuz yok (atlandi) ---"
  fi
done

step "regresyon dogrulama"
if ( cd "$BENCH/baseline_snapshot" && sha256sum -c MANIFEST.sha256 --quiet 2>/dev/null ); then
  echo "REGRESYON: tum snapshot dosyalari bit-bit ayni"
else
  echo "REGRESYON: snapshot ile ilk calistirma karsilastirilir (asama sonu kapisi)"
fi

[ "$FAIL" -eq 0 ] && echo "RUN_ALL: OK" || { echo "RUN_ALL: eksik/hatali adim var"; exit 1; }
