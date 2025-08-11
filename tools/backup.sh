#!/usr/bin/env bash
set -euo pipefail
usage() {
  cat <<USAGE
Usage: $0 [--dry-run] [--target <dir>]
Read-only placeholder backup script.
- Default target: /home/mills/backup/maelstrom
This stub only echoes intended actions.
USAGE
}
DRY=0; TARGET="/home/mills/backup/maelstrom"
while [ $# -gt 0 ]; do case "$1" in --dry-run) DRY=1;; --target) TARGET="$2"; shift;; -h|--help) usage; exit 0;; *) echo "Unknown: $1"; usage; exit 1;; esac; shift; done
mkdir -p "$TARGET"
echo "[DRY=$DRY] Would snapshot configs and volumes to: $TARGET"
exit 0
