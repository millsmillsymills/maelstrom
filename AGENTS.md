# Repository Guidelines

## Project Structure & Module Organization
- Core compose: `base.yml` (core services), `prod.yml` (profiles/overlays).
- Orchestration: `deploy_stack.sh`, `validate_stack.sh`, `scripts/` (health, security, backups, utilities).
- Service code: `maelstrom-api/` (Python API); configurations under `collections/`.
- Tests: `tests/unit/` and `tests/integration/` (pytest).
- Docs & assets: `docs/`, `documentation/`, `README.md`.

## Build, Test, and Development Commands
- Deploy base stack: `./deploy_stack.sh --base-only` — bring up core services.
- Deploy with profiles: `./deploy_stack.sh security-stack wazuh-stack` — enable overlays.
- Dry-run plan: `./deploy_stack.sh --dry-run --all-profiles` — show actions only.
- Validate stack: `./validate_stack.sh` (use `--quick`, `--health-checks-only`, `--security-only`).
- Compose sanity check: `docker-compose -f base.yml config --quiet` — validate YAML.
- Tests: `pytest -q`, or focused via `pytest -m unit` / `pytest -m integration`.
- Pre-commit: `pre-commit run -a` — format/lint before commit.

## Coding Style & Naming Conventions
- Shell: `bash`, `set -euo pipefail`; filenames lower_snake_case (e.g., `validate_stack.sh`); lint with ShellCheck.
- Python: Black formatting; Flake8 (max line length 120). Functions/modules lower_snake_case; classes PascalCase.
- YAML/Docker: lint with `yamllint`/`hadolint`; service/network names kebab-case.
- Scripts executable (`chmod +x`) and self-documented (provide `usage()`).

## Testing Guidelines
- Framework: `pytest` with `@pytest.mark.unit` and `@pytest.mark.integration` markers.
- Naming: files `test_*.py`; tests independent and idempotent.
- Run focused suites with markers; CI favors quick checks (`./validate_stack.sh --quick`).
- Add tests for new logic (secrets helpers, health checks, profile gating); update fixtures as needed.

## Commit & Pull Request Guidelines
- Commits: short, imperative subject; optional emoji; include why + what; link issues. Example: `🚀 Deploy profiles: security-stack, wazuh-stack`.
- PRs: clear summary, repro/validation steps (commands run), screenshots for dashboards, and `docker-compose -f base.yml config --quiet` output when relevant.

## Security & Configuration Tips
- Never commit secrets. Use `secrets/` files (0600) and `.env.template`; keep real `.env` local.
- Run `scripts/scan_images.sh` for CVE scans; use `validate_stack.sh --security-only` before merge.
- Backups live under `backups/`; prefer dry-runs first.

## Service-Specific: MySQL Exporter
- Credentials: `prom/mysqld-exporter` reads MySQL creds from `/etc/mysql/.my.cnf`.
- Secret file: create `secrets/mysql_exporter_my_cnf` (0600) with:
  `[client]\nuser=zabbix\npassword=<zabbix_db_password>\nhost=zabbix-mysql\nport=3306`.
- Compose: `mysql-exporter` mounts it as `- /home/mills/secrets/mysql_exporter_my_cnf:/etc/mysql/.my.cnf:ro` and runs with `--config.my-cnf`.
- Rotate password: update the secret file, then `docker restart mysql-exporter` or `docker-compose -f base.yml up --no-deps -d --force-recreate mysql-exporter`.
