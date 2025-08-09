#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILES=( -f base.yml -f docker-compose.secrets.yml )

echo "== Bringing up stack (detached) =="
docker compose "${COMPOSE_FILES[@]}" up -d

"$(dirname "$0")"/check_stack.sh

