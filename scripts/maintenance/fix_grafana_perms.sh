#!/usr/bin/env bash
# shellcheck disable=SC1091
[ -f /usr/local/lib/codex_env.sh ] && . /usr/local/lib/codex_env.sh
set -euo pipefail
DATA_DIR="/home/mills/collections/grafana"
if [ ! -d "$DATA_DIR" ]; then
  echo "Directory not found: $DATA_DIR" >&2; exit 1
fi
${SUDO} chown -R 472:472 "$DATA_DIR"
${SUDO} find "$DATA_DIR" -type f -name 'grafana.db' -exec chmod 640 {} \;
${SUDO} find "$DATA_DIR" -type d -exec chmod 755 {} \;
echo "Grafana permissions fixed for $DATA_DIR"
