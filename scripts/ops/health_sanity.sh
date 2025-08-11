#!/usr/bin/env bash
set -euo pipefail
# Lightweight, non-destructive health sanity for CI and local use.
# - Validates Compose configs
# - Emits recommended readiness endpoints
# - Verifies presence of key scripts (no execution of backups)

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "::group::Compose config validation"
if command -v docker >/dev/null 2>&1; then
  if docker compose version >/dev/null 2>&1; then
    [ -f "$root_dir/base.yml" ] && docker compose -f "$root_dir/base.yml" config --quiet || true
    if [ -f "$root_dir/prod.yml" ] && [ -f "$root_dir/base.yml" ]; then
      docker compose -f "$root_dir/base.yml" -f "$root_dir/prod.yml" config --quiet || true
    fi
  else
    echo "docker compose plugin not available; skipping compose validation"
  fi
else
  echo "docker not available; skipping compose validation"
fi
echo "::endgroup::"

echo "::group::Readiness endpoints (reference)"
cat << 'EOF'
Prometheus:     GET http://localhost:9090/-/ready
Grafana:        GET http://localhost:3000/api/health
Alertmanager:   GET http://localhost:9093/-/ready
InfluxDB 1.8:   GET http://localhost:8086/ping
Loki:           GET http://localhost:3100/ready
EOF
echo "::endgroup::"

echo "::group::Script presence"
for f in \
  "$root_dir/validate_stack.sh" \
  "$root_dir/deploy_stack.sh" \
  "$root_dir/scripts/backups/backup_influxdb.sh" \
  "$root_dir/scripts/backups/backup_volume.sh"
do
  if [ -f "$f" ]; then echo "✅ present: $f"; else echo "⚠️ missing: $f"; fi
done
echo "::endgroup::"

echo "::group::Prometheus rules layout"
if [ -d "$root_dir/collections/prometheus" ]; then
  echo "rules likely provisioned from collections/prometheus (see docs/ops/prometheus_rules_layout.md)"
else
  echo "collections/prometheus not present; skip"
fi
echo "::endgroup::"

echo "Health sanity complete"

