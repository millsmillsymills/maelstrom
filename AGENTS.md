# Repository Guidelines

## Project Structure & Module Organization
- Core compose files: `base.yml` (core services), `prod.yml` (profiles/overlays).
- Orchestration scripts: `deploy_stack.sh`, `validate_stack.sh`, `scripts/` (health, security, backups, utilities).
- Tests: `tests/unit/` and `tests/integration/` (pytest).
- Docs and assets: `docs/`, `documentation/`, `README.md`.
- Service code: `maelstrom-api/` (Python API), configurations under `collections/`.

## Build, Test, and Development Commands
- Deploy base stack: `./deploy_stack.sh --base-only`
- Deploy with profiles: `./deploy_stack.sh security-stack wazuh-stack`
- Dry-run plan: `./deploy_stack.sh --dry-run --all-profiles`
- Validate stack: `./validate_stack.sh` (use `--quick`, `--health-checks-only`, or `--security-only`).
- Compose sanity check: `docker-compose -f base.yml config --quiet`
- Run tests: `pytest -q` or markers `pytest -m unit`, `pytest -m integration`.
- Pre-commit locally: `pre-commit run -a` (see `.pre-commit-config.yaml`).

## Coding Style & Naming Conventions
- Shell: `bash`, `set -euo pipefail`; prefer lower_snake_case for filenames (e.g., `validate_stack.sh`). Lint with ShellCheck.
- Python: format with Black; lint with Flake8 (max line length 120). Use lower_snake_case for modules and functions, PascalCase for classes.
- YAML/Docker: lint with `yamllint`/`hadolint`. Keep service and network names kebab-case.
- Keep scripts executable (`chmod +x`) and self-documented (`usage()` where applicable).

## Testing Guidelines
- Framework: `pytest` with markers `@pytest.mark.unit` and `@pytest.mark.integration`.
- Naming: files start with `test_*.py`; tests are independent and idempotent.
- Run focused suites with markers; prefer quick checks in CI (`./validate_stack.sh --quick`).
- Add tests for new logic (secrets helpers, health checks, profile gating) and update fixtures as needed.

## Commit & Pull Request Guidelines
- Commits: short, imperative subject; optional emoji; scoped description (e.g., “🚀 Deploy profiles: security-stack, wazuh-stack”).
- Include why + what changed; link related issues.
- PRs: clear summary, reproduction/validation steps (commands run), screenshots for dashboards, and `docker-compose ... config --quiet` output when relevant.

## Security & Configuration Tips
- Never commit secrets. Use `secrets/` files (0600) and `.env.template` patterns; keep real `.env` local.
- Run `scripts/scan_images.sh` for CVE scans; use `validate_stack.sh --security-only` before merge.
- Backups live under `backups/`; prefer dry-runs first (e.g., backup scripts `--dry-run`).
