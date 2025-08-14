#!/usr/bin/env bash
set -euo pipefail

if ! command -v trivy >/dev/null 2>&1; then
  echo "trivy not found; please install it (or run scripts/scan_images.sh)" >&2
  exit 2
fi

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <image:tag> [more images...]" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}/../.."
REPORT_DIR="${REPO_ROOT}/reports"
mkdir -p "${REPORT_DIR}"

for img in "$@"; do
  ts=$(date +%Y%m%d_%H%M%S)
  safe=$(echo "$img" | tr '/:@' '___')
  out="${REPORT_DIR}/single_${safe}_${ts}.json"
  echo "Scanning $img -> $out" >&2
  if ! trivy image --format json --severity HIGH,CRITICAL "$img" > "$out" 2>/dev/null; then
    echo "[WARN] Failed to scan $img" >&2
    continue
  fi
  # Summarize HIGH/CRITICAL count
  if command -v jq >/dev/null 2>&1; then
    count=$(jq -r '.Results[]?.Vulnerabilities | length // 0' "$out" | awk '{s+=$1} END{print s+0}')
    echo "$img => $count HIGH/CRITICAL" >&2
  fi
done

echo "Done." >&2
