#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Usage: $(basename "$0") [--dest-dir /var/lib/node_exporter/textfile_collector]

Creates/updates a symlink for UniFi metrics into node_exporter textfile collector directory.
Falls back to copying if symlink is not permitted.
USAGE
}

DEST_DIR="${NODE_EXPORTER_TEXTFILE_DIR:-}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dest-dir) DEST_DIR="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$DEST_DIR" ]]; then
  echo "NODE_EXPORTER_TEXTFILE_DIR not set and --dest-dir not provided; nothing to do" >&2
  exit 0
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/../.. && pwd)"
SRC="${REPO_ROOT}/output/unifi/unifi_metrics.prom"
DEST_PATH="${DEST_DIR%/}/unifi_metrics.prom"

mkdir -p "$DEST_DIR"
if ln -sf "$SRC" "$DEST_PATH" 2>/dev/null; then
  echo "Linked metrics to $DEST_PATH"
else
  cp -f "$SRC" "$DEST_PATH"
  echo "Copied metrics to $DEST_PATH"
fi
