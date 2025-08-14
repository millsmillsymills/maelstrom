#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Code Share Migration Runbook

Description:
  Safely migrates local resurgent code directories to the canonical share at /mnt/code.
  - Syncs resurgent/code/maelstrom_mgmt -> /mnt/code/maelstrom_mgmt
  - Syncs resurgent/code/resurgent_mgmt -> /mnt/code/resurgent_mgmt
  - Moves system_* docs to /mnt/code root
  - Leaves backups for any overwritten files under /mnt/code/.migrate_backup_<ts>

Usage:
  scripts/ops/migrate_code_share.sh [--dry-run]

Notes:
  - Does NOT delete any source content. Clean-up is separate and manual.
  - Excludes logs/backups/output/.git and common build artifacts.
USAGE
}

dry_run=false
if [[ "${1:-}" == "--dry-run" ]]; then dry_run=true; fi

src_root="resurgent/code"
dest_root="/mnt/code"

if [[ ! -d "$dest_root" ]]; then
  echo "Destination $dest_root not found or not a directory." >&2
  exit 1
fi

backup_dir="$dest_root/.migrate_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$backup_dir"

rsync_bin=$(command -v rsync || true)
if [[ -z "$rsync_bin" ]]; then echo "rsync not found" >&2; exit 1; fi

excludes=(".git/" "logs/" "backups/" "output/" "__pycache__/" "*.pyc")
rs_opts=(-avh --backup --backup-dir "$backup_dir")
"$dry_run" && rs_opts+=(--dry-run)

echo ":: Migrating code share ::"
echo "Source: $src_root"
echo "Dest:   $dest_root"
echo "Backup: $backup_dir"

sync_one() {
  local src="$1" dest="$2"
  if [[ -d "$src" ]]; then
    echo "> Syncing $src -> $dest"
    mkdir -p "$dest"
    local cmd=("$rsync_bin" "${rs_opts[@]}")
    for ex in "${excludes[@]}"; do cmd+=(--exclude "$ex"); done
    cmd+=("$src/" "$dest/")
    echo "+ ${cmd[*]}"
    "${cmd[@]}"
  else
    echo "(skip) $src not present"
  fi
}

sync_one "$src_root/maelstrom_mgmt" "$dest_root/maelstrom_mgmt"
sync_one "$src_root/resurgent_mgmt" "$dest_root/resurgent_mgmt"

# Move system_* docs to /mnt/code root (prefer copy then remove to be safe)
shopt -s nullglob
for doc in "$src_root"/system_*.md; do
  echo "> Placing doc $(basename "$doc") into $dest_root"
  cp -f "$doc" "$dest_root/"
done
shopt -u nullglob

echo ":: Migration complete (dry-run=$dry_run). Backups at: $backup_dir ::"
