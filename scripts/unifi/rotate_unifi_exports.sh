#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Usage: $(basename "$0") [--path output/unifi] [--keep-days 14] [--dry-run]

Deletes UniFi export directories older than N days under the given path.
Preserves special directories like 'latest' and 'last7d'.

Examples:
  scripts/unifi/rotate_unifi_exports.sh --keep-days 21 --dry-run
  scripts/unifi/rotate_unifi_exports.sh --keep-days 30
USAGE
}

BASE="output/unifi"
KEEP_DAYS=14
DRY=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --path) BASE="$2"; shift 2 ;;
    --keep-days) KEEP_DAYS="$2"; shift 2 ;;
    --dry-run) DRY=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1 ;;
  esac
done

now_epoch=$(date +%s)
cutoff=$(( now_epoch - KEEP_DAYS*24*3600 ))

shopt -s nullglob
count=0
for d in "$BASE"/*; do
  name=$(basename "$d")
  [[ ! -d "$d" ]] && continue
  case "$name" in
    latest|last7d) continue ;;
  esac
  # Use mtime to determine age
  mtime=$(stat -c %Y "$d" 2>/dev/null || echo 0)
  if (( mtime < cutoff )); then
    if [[ "$DRY" == true ]]; then
      echo "DRY-RUN would remove: $d"
    else
      echo "Removing: $d"
      rm -rf -- "$d"
    fi
    ((count++)) || true
  fi
done
echo "Processed: $count candidates (keep-days=$KEEP_DAYS)"
