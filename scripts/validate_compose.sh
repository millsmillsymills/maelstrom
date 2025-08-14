#!/usr/bin/env bash
set -euo pipefail

# Validate Docker Compose configurations for base and prod overlays.

bin="${DOCKER-}"
if [[ -z "$bin" ]]; then
  if command -v docker >/dev/null 2>&1; then
    bin="docker"
  elif command -v podman >/dev/null 2>&1; then
    bin="podman"
  else
    echo "No docker/podman found; skipping compose validation" >&2
    exit 0
  fi
fi

"$bin" compose -f base.yml config --quiet
"$bin" compose -f base.yml -f prod.yml config --quiet
echo "Compose validation passed using $bin"
