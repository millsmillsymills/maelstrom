#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Mirror Sync Runbook (dry-run by default)

Description:
  Sync this repository into the Resurgent code share mirror at
  resurgent/code/resurgent_mgmt/maelstrom_mgmt while excluding build artifacts,
  backups, logs, and other non-source directories.

Usage:
  scripts/ops/mirror_sync.sh [--apply] [--dest PATH]

Options:
  --apply          Execute sync (disables dry-run). Default is dry-run.
  --dest PATH      Destination path (default: resurgent/code/resurgent_mgmt/maelstrom_mgmt)

Notes:
  - Review the printed rsync plan first. Use --apply to perform changes.
  - This script will create the destination directory if it does not exist.
USAGE
}

apply=false
dest="/mnt/code/maelstrom_mgmt"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) apply=true; shift ;;
    --dest) dest="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

mkdir -p "$dest"

dry_flag="--dry-run"
if $apply; then dry_flag=""; fi

rsync_bin=$(command -v rsync || true)
if [[ -z "$rsync_bin" ]]; then
  echo "rsync not found. Please install rsync." >&2
  exit 1
fi

echo ":: Mirror sync plan ::"
echo "Source: $(pwd)"
echo "Dest:   $dest"
echo "Apply:  $apply"

excludes=(
  ".git/"
  ".venv/"
  "backups/"
  "logs/"
  "output/"
  "trash/"
  "tools/duo/logs/"
  "security-scans/"
  "reports/"
  "*.pyc"
  "__pycache__/"
)

rsync_opts=(
  -avh --delete
  "$dry_flag"
)

for ex in "${excludes[@]}"; do
  rsync_opts+=(--exclude "$ex")
done

cmd=("$rsync_bin" "${rsync_opts[@]}" ./ "$dest/")
echo "+ ${cmd[*]}"
"${cmd[@]}"

echo ":: Mirror sync completed ($([[ $apply == true ]] && echo applied || echo dry-run)) ::"
