# Image Tag Pinning Strategy

This repository supports pinning container images via environment variables to reduce CVE churn and ensure reproducible deployments. Defaults remain compatible (often `latest`) but can be overridden in `.env`.

## Why pin?
- Reduce unexpected changes and minimize vulnerability noise from moving `latest`.
- Stage upgrades deliberately with validation and roll-back.

## How it works
- Compose files reference env-driven tags, e.g. `grafana/grafana:${GRAFANA_TAG:-latest}`.
- Define tag values in `.env` (see `.env.pinned.example` for recommendations).

## Recommended tags (Aug 2025)
See `.env.pinned.example` for a curated set covering core, exporters, and security stack. Validate in a non-production environment before applying.

## Validation steps
- Compose syntax: `docker compose -f base.yml config --quiet`.
- Dry-run deploy: `./deploy_stack.sh --dry-run --all-profiles`.
- Health checks: `./validate_stack.sh --quick`.
- Security scan: `./scripts/scan_images.sh` (honors `.trivyignore`).

## Notes and caveats
- InfluxDB 1.8 is legacy. Consider planning a migration to InfluxDB 2.x; the data path and APIs differ.
- MySQL 8.4 is the LTS line; confirm Zabbix compatibility before upgrading from 8.0.
- Wazuh stack currently references Elasticsearch 7.x and Wazuh 4.9.x. Upgrades may require coordinated changes; avoid bumping here without a dedicated plan.
- Pi-hole and ntopng releases vary; test pins in a lab setup.

## Triage of CVEs
- `.trivyignore` is included with an expiration date (2025-09-30). Review and reduce exceptions as images are upgraded.

## Rollout plan (suggested)
1. Apply `.env.pinned.example` selections to your `.env` in a test environment.
2. Run validation, monitor for regressions, and adjust pins as needed.
3. Promote to production during a maintenance window.
