#!/usr/bin/env bash
# shellcheck disable=SC1091
[ -f /usr/local/lib/codex_env.sh ] && . /usr/local/lib/codex_env.sh
set -euo pipefail

COMPOSE_FILES=( -f base.yml -f docker-compose.secrets.yml )

echo "== Bringing up stack (detached) =="
${DOCKER} compose "${COMPOSE_FILES[@]}" up -d

"$(dirname "$0")"/check_stack.sh