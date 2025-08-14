# Contributing Guide

Thank you for improving the Maelstrom stack. This guide summarizes expectations and the workflow for changes.

## Workflow
- Create a feature branch from `main`.
- Keep changes focused and incremental; prefer small PRs.
- Validate locally before opening a PR:
  - `./deploy_stack.sh --dry-run --all-profiles`
  - `./validate_stack.sh --quick`
  - `make compose.check` and `make health.report` (generates summary + JSON)
  - `pytest -q` (or focused: `pytest -m unit` / `pytest -m integration`)
  - `pre-commit run -a`

## Coding Standards
- Shell: bash + `set -euo pipefail`; lint with ShellCheck; scripts executable; include `usage()`.
- Python: Black + Flake8 (max line length 120); functions/modules `lower_snake_case`; classes `PascalCase`.
- YAML/Docker: lint with `yamllint` and `hadolint`; service/network names use `kebab-case`.

## Structure & Naming
- Compose: `base.yml` (core), `prod.yml` (overlays via profiles).
- Configs under `collections/` (kebab-case for services). Data dirs use `*-data` suffix.
- Docs live in `docs/`; prefer `README.md` in important subdirs.
- Env templates: use `.env.template` (do not commit real secrets).

## PR Checklist
- Clear summary of what/why, linked issue if applicable.
- Repro/validation steps, including `${DOCKER} compose -f base.yml config --quiet` output when relevant.
- Screenshots for dashboards/UX; list active profiles (e.g., `security-stack wazuh-stack`).
- Reference `AGENTS.md` for detailed repository guidelines and troubleshooting.

## Security
- Never commit secrets or tokens. Use `secrets/` (chmod 0600) and `.env.template`.
- Run `./validate_stack.sh --security-only` before merge; scan images via `scripts/scan_images.sh`.

## Tests
- Add or update tests under `tests/unit` and `tests/integration` with pytest markers.
- Tests must be idempotent and independent.
