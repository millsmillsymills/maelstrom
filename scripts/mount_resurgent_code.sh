#!/usr/bin/env bash
# shellcheck disable=SC1091
[ -f /usr/local/lib/codex_env.sh ] && . /usr/local/lib/codex_env.sh
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/mount_resurgent_code.sh [--mountpoint PATH] [--server IP] [--share NAME] [--cred-file PATH]

Mount the Resurgent "code" SMB share to a local mountpoint.

Options:
  --mountpoint PATH   Local mountpoint (default: /home/mills/resurgent/code)
  --server IP         SMB server IP/host (default: 192.168.1.115)
  --share NAME        SMB share name (default: code)
  --cred-file PATH    Credentials file (default: secrets/smb_resurgent_code or .smbcredentials if present)

Credentials sources (in order):
  1) --cred-file path if provided or detected
  2) Environment vars from .env: RESURGENT_SMB_USER/RESURGENT_SMB_PASS or SMB_USERNAME/SMB_PASSWORD

The script uses uid/gid of the invoking user and CIFS vers=3.0.
USAGE
}

MOUNTPOINT=${MOUNTPOINT:-/home/mills/resurgent/code}
SERVER=${SERVER:-192.168.1.115}
SHARE=${SHARE:-code}
CRED_FILE=${CRED_FILE:-}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mountpoint) MOUNTPOINT=$2; shift 2;;
    --server) SERVER=$2; shift 2;;
    --share) SHARE=$2; shift 2;;
    --cred-file) CRED_FILE=$2; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown argument: $1" >&2; usage; exit 2;;
  esac
done

ROOT_DIR=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
DEFAULT_SECRET_1="$ROOT_DIR/secrets/smb_resurgent_code"
DEFAULT_SECRET_2="$ROOT_DIR/.smbcredentials"

# Ensure mount.cifs exists
if ! command -v mount.cifs >/dev/null 2>&1; then
  echo "mount.cifs not found. Please install cifs-utils (apt install cifs-utils)" >&2
  exit 1
fi

mkdir -p "$MOUNTPOINT"

# Resolve credentials file or build from env
TMP_CRED=""
if [[ -z "${CRED_FILE}" ]]; then
  if [[ -f "$DEFAULT_SECRET_1" ]]; then
    CRED_FILE="$DEFAULT_SECRET_1"
  elif [[ -f "$DEFAULT_SECRET_2" ]]; then
    CRED_FILE="$DEFAULT_SECRET_2"
  fi
fi

if [[ -z "${CRED_FILE}" ]]; then
  # Try environment variables from .env
  if [[ -f "$ROOT_DIR/.env" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$ROOT_DIR/.env"
    set +a
  fi
  USER_VAR=${RESURGENT_SMB_USER:-${SMB_USERNAME:-}}
  PASS_VAR=${RESURGENT_SMB_PASS:-${SMB_PASSWORD:-}}
  if [[ -n "${USER_VAR}" && -n "${PASS_VAR}" ]]; then
    TMP_CRED=$(mktemp)
    chmod 600 "$TMP_CRED"
    {
      printf 'username=%s\n' "$USER_VAR"
      printf 'password=%s\n' "$PASS_VAR"
    } > "$TMP_CRED"
    CRED_FILE="$TMP_CRED"
  else
    echo "No credentials file found and required env vars are not set." >&2
    echo "Set RESURGENT_SMB_USER/RESURGENT_SMB_PASS in .env, or provide --cred-file." >&2
    exit 1
  fi
fi

# If path is already a cifs mount, exit successfully
if findmnt -n -T "$MOUNTPOINT" >/dev/null 2>&1; then
  FSTYPE=$(findmnt -n -T "$MOUNTPOINT" -o FSTYPE)
  if [[ "$FSTYPE" == "cifs" ]]; then
    echo "Already mounted: //$SERVER/$SHARE -> $MOUNTPOINT" >&2
    exit 0
  fi
fi

UID_VAL=$(id -u)
GID_VAL=$(id -g)
OPTS="credentials=$CRED_FILE,uid=$UID_VAL,gid=$GID_VAL,file_mode=0644,dir_mode=0755,vers=3.0,noserverino"

MOUNT_CMD=(mount -t cifs "//$SERVER/$SHARE" "$MOUNTPOINT" -o "$OPTS")

if [[ $EUID -ne 0 ]]; then
  if command -v ${SUDO} >/dev/null 2>&1; then
    echo "Mounting with sudo: //$SERVER/$SHARE -> $MOUNTPOINT" >&2
    ${SUDO} "${MOUNT_CMD[@]}"
  else
    echo "Root privileges required to mount. Re-run with sudo." >&2
    exit 1
  fi
else
  echo "Mounting: //$SERVER/$SHARE -> $MOUNTPOINT" >&2
  "${MOUNT_CMD[@]}"
fi

# Verify mount
if [[ "$(findmnt -n -T "$MOUNTPOINT" -o FSTYPE)" != "cifs" ]]; then
  echo "Mount verification failed for $MOUNTPOINT" >&2
  exit 1
fi

echo "Mounted //$SERVER/$SHARE at $MOUNTPOINT" >&2

# Cleanup temp credential file if created (not deleting while mounted since kernel holds FD)
if [[ -n "$TMP_CRED" ]]; then
  # Leave temp cred file in place until unmount; warn user for manual cleanup
  echo "Temporary credentials file created at $TMP_CRED (600). Remove after unmount." >&2
fi