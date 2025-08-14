# Repository Guidelines

## Project Structure & Module Organization
- Compose: `base.yml` (core) with overlay profiles in `prod.yml`.
- Orchestration: `deploy_stack.sh`, `validate_stack.sh`, and `scripts/` (health, security, backups, utilities).
- Services: Python API in `maelstrom-api/`; configuration collections in `collections/`.
- Tests: `tests/unit/` and `tests/integration/` (pytest markers).
- Docs & assets: `docs/`, `README.md`; backups in `backups/`; secrets in `secrets/` (chmod `0600`).

## Build, Test, and Development Commands
- Setup hooks: `pre-commit install`; run all checks: `pre-commit run -a`.
- Container engine: `export DOCKER=docker` (or `podman`).
- Compose validate: ``${DOCKER} compose -f base.yml config --quiet`` (optionally add `-f compose_overrides/health-fixes.yml`).
- Run stack: `./deploy_stack.sh --base-only` or enable profiles, e.g., `./deploy_stack.sh security-stack wazuh-stack` (`--dry-run --all-profiles` to preview).
- Validate runtime: `./validate_stack.sh --quick` (or `--health-checks-only`, `--security-only`, `--backups-only`).
- Health report: `scripts/health/maelstrom_health.sh --hours 24 --json /tmp/maelstrom_health.json --summary /tmp/maelstrom_health.md`.

## Coding Style & Naming Conventions
- Shell: bash with `set -euo pipefail`; files `lower_snake_case`; include `usage()`; lint with ShellCheck.
- Python: format with Black; lint with Flake8 (line length 120); modules/functions `lower_snake_case`, classes `PascalCase`.
- YAML/Docker: lint with `yamllint` and `hadolint`; service/network names `kebab-case`.

## Testing Guidelines
- Framework: pytest; mark tests with `@pytest.mark.unit` or `@pytest.mark.integration`.
- Naming: `tests/test_*.py`; tests must be independent and idempotent.
- Run all: `pytest -q`; focus: `pytest -m unit` or `pytest -m integration`.

## Commit & Pull Request Guidelines
- Commits: imperative subject + why/what; link issues.
- Example: `🚀 Deploy profiles: security-stack, wazuh-stack`.
- PRs: provide summary, commands run (tests/validate), relevant compose output, active profiles used, and screenshots for UI/metrics changes.

## Security & Configuration
- Never commit secrets; use `.env.template` and keep real `.env` local.
- Protect `secrets/*` with `chmod 0600`.
- Image scanning: `scripts/scan_images.sh`; run `./validate_stack.sh --security-only` before merging.
- Backups: `scripts/backups/backup_influxdb.sh`, `scripts/backups/backup_volume.sh` (supports `--dry-run`); rotate with `scripts/backups/rotate_backups.sh`.

## Architecture Overview
- Compose orchestrates core (`base.yml`) plus profiles (`prod.yml`).
- Internal services: Maelstrom API `http://localhost:8000` (`/health`), Grafana `http://localhost:3000`, Prometheus `http://localhost:9090`, Alertmanager `http://localhost:9093`, InfluxDB `http://localhost:8086`, Loki `http://localhost:3100`, Wazuh `https://localhost:5601` (self-signed).
