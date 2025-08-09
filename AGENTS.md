# Repository Guidelines

## Project Structure & Module Organization
- Core compose: `base.yml` (core services) and `prod.yml` (profiles/overlays).
- Orchestration: `deploy_stack.sh`, `validate_stack.sh`, and `scripts/` (health, security, backups, utilities).
- Service code: `maelstrom-api/` (Python API); configurations in `collections/`.
- Tests: `tests/unit/` and `tests/integration/` (pytest markers).
- Docs & assets: `docs/`, `documentation/`, `README.md`.
- Backups & secrets: artifacts under `backups/`, tools in `scripts/backups/`, sensitive files in `secrets/` (chmod 0600).

## Build, Test, and Development Commands
- Start core locally: `./deploy_stack.sh --base-only`.
- Enable overlays via profiles: `./deploy_stack.sh security-stack wazuh-stack`.
- Dry run everything: `./deploy_stack.sh --dry-run --all-profiles`.
- Validate quickly or by area: `./validate_stack.sh --quick` (or `--health-checks-only`, `--security-only`, `--backups-only`).
- Compose sanity: `docker-compose -f base.yml config --quiet`.
- Tests: `pytest -q`, or focused with `pytest -m unit` / `pytest -m integration`.
- Pre-commit lint/format: `pre-commit run -a` before committing.

## Coding Style & Naming Conventions
- Shell: bash with `set -euo pipefail`; filenames `lower_snake_case`; lint using ShellCheck; scripts executable and self-documented (`usage()`).
- Python: Black; Flake8 (max line length 120). Functions/modules `lower_snake_case`; classes `PascalCase`.
- YAML/Docker: lint with `yamllint`/`hadolint`; service/network names `kebab-case`.

## Testing Guidelines
- Framework: pytest with `@pytest.mark.unit` and `@pytest.mark.integration`.
- Naming: files `test_*.py`; tests independent and idempotent.
- Run focused suites with markers; CI favors quick checks via `./validate_stack.sh --quick`.

## Commit & Pull Request Guidelines
- Commits: short, imperative subject + why/what; link issues. Example: `🚀 Deploy profiles: security-stack, wazuh-stack`.
- PRs: clear summary; repro/validation steps (commands run); include `docker-compose -f base.yml config --quiet` output when relevant.
- Add dashboards/screenshots where applicable; note active profiles used (e.g., `security-stack wazuh-stack`).

## Security & Configuration Tips
- Never commit secrets. Use `secrets/` (0600) and `.env.template`; keep real `.env` local.
- Scan images: `scripts/scan_images.sh`; run `./validate_stack.sh --security-only` before merge.
- Backups: `scripts/backups/backup_influxdb.sh` and `scripts/backups/backup_volume.sh` (support `--dry-run`); rotate with `scripts/backups/rotate_backups.sh`.
- MySQL Exporter: create `secrets/mysql_exporter_my_cnf` and mount `/etc/mysql/.my.cnf:ro`; run exporter with `--config.my-cnf`.
