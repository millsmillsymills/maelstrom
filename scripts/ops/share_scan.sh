#!/usr/bin/env bash
set -euo pipefail

# Read-only scan of the Resurgent code share for TODO/FIXME/WIP markers
# and basic project hygiene. Produces a Markdown report.
#
# Behavior:
# - If /mnt/code exists, scans it with exclusions and time bounds.
# - If not present, produces a short report noting the skip.
# - Writes report to ./output/share_scan_YYYYmmdd_HHMMSS.md

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
OUTDIR="$ROOT_DIR/output"
mkdir -p "$OUTDIR"
TS=$(date +%Y%m%d_%H%M%S)
OUT="$OUTDIR/share_scan_${TS}.md"

if [ ! -d /mnt/code ]; then
  {
    echo "# Resurgent Share Scan (skipped)"
    echo
    echo "Generated: $(date -Is)"
    echo
    echo "/mnt/code is not mounted on this runner; skipping read-only scan."
  } > "$OUT"
  echo "WROTE $OUT"
  exit 0
fi

PATTERN='TODO|FIXME|WIP|HACK|BUG|XXX'
{
  echo "# Resurgent Share Scan"
  echo
  echo "Generated: $(date -Is)"
  echo
  echo "Top-level directories under /mnt/code:"
  echo
  find /mnt/code -maxdepth 1 -mindepth 1 -type d -printf '- %f\n' 2>/dev/null | sort || true
  echo
  echo "## Marker files (TODO*, FIXME*, *TODO*.md)"
  echo
  find /mnt/code -maxdepth 3 \
    \( -iname 'TODO*' -o -iname 'FIXME*' -o -iname '*TODO*.md' \) \
    -type f -printf '%P\n' 2>/dev/null | sed 's#^#- /mnt/code/#' | head -n 200 || true
  echo
  echo "## Code markers (TODO/FIXME/WIP/HACK/BUG/XXX) — sampled"
  echo
  if command -v rg >/dev/null 2>&1; then
    timeout 45 rg -n --no-heading --hidden -S -e "$PATTERN" /mnt/code \
      -g '!**/.git/**' -g '!**/node_modules/**' -g '!**/dist/**' -g '!**/build/**' \
      -g '!**/.venv/**' -g '!**/venv/**' -g '!**/__pycache__/**' \
      -g '!**/logs/**' -g '!**/backups/**' -g '!**/output/**' -g '!**/trash/**' \
      --max-filesize 512k | sed -E 's#^/mnt/code/##' | head -n 1000 || true
  else
    timeout 45 grep -RInE "$PATTERN" /mnt/code \
      --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=build \
      --exclude-dir=.venv --exclude-dir=venv --exclude-dir=__pycache__ --exclude-dir=logs \
      --exclude-dir=backups --exclude-dir=output --exclude-dir=trash --binary-files=without-match 2>/dev/null \
      | sed -E 's#^/mnt/code/##' | head -n 1000 || true
  fi
  echo
  echo "## Notes"
  echo "- This is a time-bounded sample (<=45s scan, 1000 matches)."
  echo "- Excludes heavy dirs: .git, node_modules, dist, build, venvs, caches, logs, backups, output, trash."
} > "$OUT"

echo "WROTE $OUT"
