#!/usr/bin/env bash
# shellcheck disable=SC1091
[ -f /usr/local/lib/codex_env.sh ] && . /usr/local/lib/codex_env.sh
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/umount_resurgent_code.sh [--mountpoint PATH]

Unmount the Resurgent "code" SMB share from a local mountpoint.

Options:
  --mountpoint PATH   Local mountpoint (default: /home/mills/resurgent/code)
USAGE
}

MOUNTPOINT=${MOUNTPOINT:-/home/mills/resurgent/code}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mountpoint) MOUNTPOINT=$2; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown argument: $1" >&2; usage; exit 2;;
  esac
done

if ! findmnt -n -T "$MOUNTPOINT" >/dev/null 2>&1; then
  echo "Not mounted: $MOUNTPOINT" >&2
  exit 0
fi

FSTYPE=$(findmnt -n -T "$MOUNTPOINT" -o FSTYPE)
if [[ "$FSTYPE" != "cifs" ]]; then
  echo "$MOUNTPOINT is mounted but not as CIFS (type=$FSTYPE). Aborting." >&2
  exit 1
fi

UMOUNT_CMD=(umount "$MOUNTPOINT")

if [[ $EUID -ne 0 ]]; then
  if command -v ${SUDO} >/dev/null 2>&1; then
    echo "Unmounting with sudo: $MOUNTPOINT" >&2
    ${SUDO} "${UMOUNT_CMD[@]}"
  else
    echo "Root privileges required to unmount. Re-run with sudo." >&2
    exit 1
  fi
else
  echo "Unmounting: $MOUNTPOINT" >&2
  "${UMOUNT_CMD[@]}"
fi

echo "Unmounted $MOUNTPOINT" >&2
