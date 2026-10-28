#!/bin/bash
# Salep Dijital İkizi başlatıcı — simülasyon yayıncısı.
#
# W0: görsel katman (godot/_legacy/dashboard) kaldırıldı; koşu yolu
# simülasyon yayıncısıdır (ayrı süreç, TCP NDJSON, latest-wins).
# NPU: ayrı çekirdek, lob ile bağlanır (henüz entegre değil).
#
# Kullanım: ./sim/run.sh [--speed 4] [--port 41790] [--scenario drought]
set -e
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORE="$(dirname "$HERE")"
exec "$CORE/.venv/bin/python" "$HERE/serve.py" "$@"
