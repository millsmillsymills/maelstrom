#!/usr/bin/env bash
set -euo pipefail

# Capture Lsyncd service state and recent logs to ops log directory.
# Output: /home/mills/tools/duo/logs/lsyncd_snapshot_YYYYmmdd_HHMMSS.txt

OUT_DIR="/home/mills/tools/duo/logs"
TS=$(date +%Y%m%d_%H%M%S)
OUT="$OUT_DIR/lsyncd_snapshot_${TS}.txt"
mkdir -p "$OUT_DIR"

{
  echo "== Lsyncd Snapshot at $(date -Is) =="
  echo
  echo "-- systemctl status --"
  systemctl status codex-home-sync.service --no-pager || true
  echo
  echo "-- journalctl (last 200 lines) --"
  journalctl -u codex-home-sync.service -n 200 --no-pager || true
  echo
  echo "-- lsyncd log tail --"
  sudo tail -n 200 /var/log/lsyncd/lsyncd.log || true
  echo
  echo "-- mount posture --"
  findmnt -no SOURCE,TARGET,OPTIONS /mnt/code || true
} > "$OUT"

echo "Wrote $OUT"

