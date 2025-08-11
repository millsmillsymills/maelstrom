#!/usr/bin/env bash
# shellcheck disable=SC1091
[ -f /usr/local/lib/codex_env.sh ] && . /usr/local/lib/codex_env.sh
set -euo pipefail

# Sync the working tree of this repo to the resurgent mirror.
# Default target can be overridden with MGMT_TARGET env var.

SRC_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
# Default target mirrors to the Resurgent code share under resurgent_mgmt/maelstrom_mgmt
# Override with MGMT_TARGET to use a different destination.
TARGET_DIR=${MGMT_TARGET:-/home/mills/resurgent/code/resurgent_mgmt/maelstrom_mgmt}

if [ ! -d "$TARGET_DIR" ]; then
  mkdir -p "$TARGET_DIR"
fi

echo "Syncing from $SRC_ROOT to $TARGET_DIR" >&2

# Prefer rsync with tracked files to avoid copying untracked noise.
if command -v rsync >/dev/null 2>&1; then
  # Use git ls-files to list tracked files, sync them, and clean removed files.
  # Create an empty placeholder to ensure target exists before --delete.
  touch "$TARGET_DIR/.sync_placeholder" || true
  git -C "$SRC_ROOT" ls-files -z |
    rsync -a --delete --from0 --files-from=- "$SRC_ROOT/" "$TARGET_DIR/"
  rm -f "$TARGET_DIR/.sync_placeholder" || true
else
  # Fallback: archive the current working tree state using tar.
  tmp_tar=$(mktemp)
  (cd "$SRC_ROOT" && tar --exclude-vcs -cf "$tmp_tar" .)
  tar -xf "$tmp_tar" -C "$TARGET_DIR"
  rm -f "$tmp_tar"
fi

echo "Sync complete." >&2
