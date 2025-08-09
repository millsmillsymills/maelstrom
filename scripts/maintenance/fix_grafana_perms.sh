#!/usr/bin/env bash
set -euo pipefail
DATA_DIR="/home/mills/collections/grafana"
if [ ! -d "$DATA_DIR" ]; then
  echo "Directory not found: $DATA_DIR" >&2; exit 1
fi
sudo chown -R 472:472 "$DATA_DIR"
sudo find "$DATA_DIR" -type f -name 'grafana.db' -exec chmod 640 {} \;
sudo find "$DATA_DIR" -type d -exec chmod 755 {} \;
echo "Grafana permissions fixed for $DATA_DIR"

