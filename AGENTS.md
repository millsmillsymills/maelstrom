# Repository Guidelines

## Project Structure & Module Organization
- Core compose: `base.yml` (core services) and `prod.yml` (profiles/overlays).
- Orchestration: `deploy_stack.sh`, `validate_stack.sh`, and `scripts/` (health, security, backups, utilities).
- Service code: `maelstrom-api/` (Python API); configurations under `collections/`.
- Tests: `tests/unit/` and `tests/integration/` (pytest).
- Docs & assets: `docs/`, `documentation/`, `README.md`.
- Backups & secrets: `backups/` (artifacts), `scripts/backups/` (tools), `secrets/` (0600).

## Build, Test, and Development Commands
- `./deploy_stack.sh --base-only`: bring up core services locally.
- `./deploy_stack.sh security-stack wazuh-stack`: enable overlays via profiles.
- `./deploy_stack.sh --dry-run --all-profiles`: show planned actions only.
- `./validate_stack.sh` (use `--quick`, `--health-checks-only`, `--security-only`, `--backups-only`).
- Compose sanity: `docker-compose -f base.yml config --quiet`.
- Tests: `pytest -q`, focused via `pytest -m unit` / `pytest -m integration`.
- Pre-commit: `pre-commit run -a` (format/lint before committing).

## Coding Style & Naming Conventions
- Shell: bash, `set -euo pipefail`; filenames `lower_snake_case`; lint with ShellCheck; scripts executable and self-documented (`usage()`).
- Python: Black; Flake8 (max line length 120). Functions/modules `lower_snake_case`; classes `PascalCase`.
- YAML/Docker: lint with `yamllint`/`hadolint`; service/network names `kebab-case`.

## Testing Guidelines
- Framework: pytest with `@pytest.mark.unit` and `@pytest.mark.integration`.
- Naming: files `test_*.py`; tests independent and idempotent.
- Run focused suites with markers; CI favors quick checks: `./validate_stack.sh --quick`.

## Commit & Pull Request Guidelines
- Commits: short, imperative subject; include why + what; link issues. Example: `🚀 Deploy profiles: security-stack, wazuh-stack`.
- PRs: clear summary; repro/validation steps (commands run); screenshots for dashboards; include `docker-compose -f base.yml config --quiet` output when relevant.

## Security & Configuration Tips
- Never commit secrets. Use `secrets/` (0600) and `.env.template`; keep real `.env` local.
- Scan images: `scripts/scan_images.sh`; run `./validate_stack.sh --security-only` before merge.
- Backups: use `scripts/backups/backup_influxdb.sh` and `scripts/backups/backup_volume.sh` (support `--dry-run`); rotate with `scripts/backups/rotate_backups.sh`.
- MySQL Exporter: create `secrets/mysql_exporter_my_cnf` and mount at `/etc/mysql/.my.cnf:ro`; run exporter with `--config.my-cnf`.

## Contributing
- Workflow: open/assign an issue, discuss scope, then branch from `main`.
- Branch names: `feature/<short-scope>`, `fix/<ticket-id>`, `docs/<topic>`.
- Before PR: `pre-commit run -a`, `pytest -q`, `./validate_stack.sh --quick`, and `docker-compose -f base.yml config --quiet`.
- Commits: imperative subject + why/what; example: `chore: tighten hadolint rules`.
- PRs: link issues, list commands run and outputs, add screenshots for dashboards, and note active profiles used (e.g., `security-stack wazuh-stack`).
