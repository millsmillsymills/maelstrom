#!/usr/bin/env bash
# shellcheck disable=SC1091
[ -f /usr/local/lib/codex_env.sh ] && . /usr/local/lib/codex_env.sh
set -euo pipefail

usage() {
  cat <<EOF
Usage: $0 [--aggressive] [--quiet]

Safely prune unused Docker artifacts.
 - default: prune stopped containers, dangling images, unused networks, build cache.
 - volumes: only prunes dangling volumes (not in use). Use --aggressive to prune all unused volumes.

Examples:
  $0                 # safe prune
  $0 --aggressive    # also prune unused volumes
EOF
}

QUIET=${QUIET:-0}
AGGRESSIVE=0
while [[ ${1:-} ]]; do
  case "$1" in
    --aggressive) AGGRESSIVE=1; shift;;
    --quiet) QUIET=1; shift;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1"; usage; exit 1;;
  esac
done

log(){ [[ $QUIET -eq 1 ]] || echo "[$(date -Is)] $*"; }

log "Pruning stopped containers, dangling images, unused networks, and build cache..."
${DOCKER} container prune -f >/dev/null 2>&1 || true
${DOCKER} image prune -f >/dev/null 2>&1 || true
${DOCKER} network prune -f >/dev/null 2>&1 || true
${DOCKER} builder prune -f >/dev/null 2>&1 || true

if [[ $AGGRESSIVE -eq 1 ]]; then
  log "Aggressive: pruning unused volumes..."
  ${DOCKER} volume prune -f >/dev/null 2>&1 || true
else
  log "Safe: removing dangling volumes only..."
  mapfile -t DANGLED < <(${DOCKER} volume ls -qf dangling=true || true)
  if [[ ${#DANGLED[@]} -gt 0 ]]; then
    printf '%s\n' "${DANGLED[@]}" | xargs -r ${DOCKER} volume rm >/dev/null 2>&1 || true
    log "Removed ${#DANGLED[@]} dangling volumes"
  else
    log "No dangling volumes to remove"
  fi
fi

log "Docker prune completed."
