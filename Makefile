SHELL := /bin/bash
DOCKER ?= docker
WARN_PCT ?= 90

.PHONY: gh.auth gh.probe gh.push gh.oauth
.PHONY: compose.check validate.quick validate.security validate.backups lint precommit deploy.base deploy.profiles audit.services status.quick mirror.sync pr.status resurgent.probe targets.cleanup dashboards.sync
.PHONY: docs.open
.PHONY: health.report

gh.auth:
	@source ./scripts/github_auth.sh >/dev/null 2>&1 || true; \
	if ./internal/github_auth/token_provider.sh >/dev/null 2>&1; then \
	  echo "Non-interactive GitHub auth OK"; \
	else \
	  echo "Non-interactive auth unavailable. Set GITHUB_OAUTH_* or GITHUB_PAT."; exit 1; \
	fi

gh.probe:
	@echo "Probing network reachability and remote access..."
	@curl -sSf https://github.com/ >/dev/null
	@GIT_ASKPASS=./internal/github_auth/git_askpass.sh GIT_TERMINAL_PROMPT=0 \
	  git -c credential.helper= -c http.https://github.com/.extraheader= \
	  ls-remote https://github.com/$$(git config --get remote.origin.url | sed -E 's#.*github.com[:/](.+/.+)\.git#\1#g').git -h refs/heads/main | head -n1

gh.push:
	@branch="$$(git rev-parse --abbrev-ref HEAD || true)"; \
	if [[ -z "$$branch" || "$$branch" == "HEAD" ]]; then \
	  branch="chore/github-integration-cleanup"; \
	  git checkout -B "$$branch"; \
	fi; \
	repo="$$(git config --get remote.origin.url | sed -E 's#.*github.com[:/](.+/.+)\.git#\1#g').git"; \
	echo "Pushing branch $$branch to https://github.com/$$repo (dry-run configurable)"; \
	GIT_ASKPASS=./internal/github_auth/git_askpass.sh GIT_TERMINAL_PROMPT=0 \
	  git -c credential.helper= -c http.https://github.com/.extraheader= \
	  push https://github.com/$$repo "$$branch"

gh.oauth:
	@./scripts/github_oauth_device.sh

# Convenience targets
compose.check:
	@$(DOCKER) compose -f base.yml config --quiet && echo "compose config OK"

validate.quick:
	@./validate_stack.sh --quick --warn-on-resurgent-down $(WARN_PCT)

validate.security:
	@./validate_stack.sh --security-only

validate.backups:
	@./validate_stack.sh --backups-only

lint precommit:
	@command -v pre-commit >/dev/null 2>&1 && pre-commit run -a || echo "pre-commit not installed"

deploy.base:
	@./deploy_stack.sh --base-only

deploy.profiles:
	@./deploy_stack.sh $(PROFILES)

audit.services:
	@./scripts/ops/services_audit.sh && ls -t output/services_audit_*.md | head -n1

status.quick:
	@./validate_stack.sh --quick --warn-on-resurgent-down $(WARN_PCT) && ./scripts/ops/services_audit.sh && ls -t output/services_audit_*.md | head -n1

mirror.sync:
	@./scripts/ops/mirror_sync.sh $(ARGS)

pr.status:
	@./scripts/ops/check_prs.sh --state $${STATE:-open}

resurgent.probe:
	@./scripts/ops/resurgent_probe.sh $(ARGS)

targets.cleanup:
	@python3 scripts/ops/targets_cleanup.py $${ARGS:-}

dashboards.sync:
	@mkdir -p collections/grafana/dashboards/ops; \
	if cp -f docs/dashboards/*.json collections/grafana/dashboards/ops/ 2>/dev/null; then \
	  echo "Copied dashboards to collections/grafana/dashboards/ops"; \
	else \
	  echo "No dashboards to copy (docs/dashboards/*.json)"; \
	fi; \
	if command -v chown >/dev/null 2>&1; then \
	  chown -R 472:472 collections/grafana/dashboards/ops || echo "chown skipped (insufficient perms)"; \
	fi

health.report:
	@mkdir -p output; \
	HOURS=$${HOURS:-24}; \
	./scripts/health/maelstrom_health.sh --hours $$HOURS --json output/maelstrom_health.json --summary output/maelstrom_health.md; \
	echo "Summary:  $$(realpath output/maelstrom_health.md 2>/dev/null || echo output/maelstrom_health.md)"; \
	echo "JSON:     $$(realpath output/maelstrom_health.json 2>/dev/null || echo output/maelstrom_health.json)"

# Open docs/landing (best-effort) and print locations
docs.open:
	@echo "Docs index: docs/index.md"; \
	echo "Contributor guide: AGENTS.md"; \
	if command -v xdg-open >/dev/null 2>&1; then \
	  (xdg-open docs/index.md >/dev/null 2>&1 || true); \
	elif command -v open >/dev/null 2>&1; then \
	  (open docs/index.md || true); \
	fi
# UniFi toolkit convenience targets
.PHONY: unifi-export unifi-export-7d unifi-load unifi-report unifi-rotate unifi-install-timer

unifi-export:
	./scripts/unifi/unifi_export.sh --resources all --format both --since 24h --out-dir output/unifi/$$(date +%Y%m%d_%H%M%S)

unifi-export-7d:
	./scripts/unifi/unifi_export.sh --resources all --format both --since 7d --out-dir output/unifi/last7d

unifi-load:
	python3 scripts/unifi/unifi_load_sqlite.py --export-dir output/unifi/last7d --db output/unifi/last7d/unifi_export.db --normalize

unifi-report:
	python3 scripts/unifi/unifi_report.py --db output/unifi/last7d/unifi_export.db --out-md output/unifi/last7d/unifi_report.md --out-json output/unifi/last7d/unifi_report.json

unifi-rotate:
	./scripts/unifi/rotate_unifi_exports.sh --keep-days 30

unifi-install-timer:
	./scripts/unifi/install_unifi_export_timer.sh --user --enable --with-rotate

unifi-pipeline:
	./scripts/unifi/unifi_pipeline.sh --since 7d --out-dir output/unifi/last7d

unifi-sql:
	python3 scripts/unifi/unifi_sql_helper.py --db output/unifi/last7d/unifi_export.db --top 10

.PHONY: unifi-status slack-verify
unifi-status:
	python3 scripts/unifi/unifi_status_check.py --export-dir output/unifi/last7d --max-age-hours 12 --min-events 1

slack-verify:
	python3 scripts/unifi/slack_verify.py

.PHONY: unifi-grafana-import
unifi-grafana-import:
	./scripts/unifi/grafana_import_dashboard.sh
