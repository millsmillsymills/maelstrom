## Summary
- What: Concise description of the change.
- Why: Problem it solves (link issues, incidents).

## Changes
- Services/components touched: vault, trivy, docs
- Files: docker-compose.yml (or override), AGENTS.md, scripts/health/maelstrom_health.sh

## Profiles Used
- Profiles enabled during local validation: `security-stack wazuh-stack` (example)

## Validation Steps
Run locally before submitting. Paste key outputs.

```bash
# Compose sanity
${DOCKER:-docker} compose -f base.yml config --quiet

# Quick stack checks
./validate_stack.sh --quick

# Optional: apply health override temporarily
${DOCKER:-docker} compose -f base.yml -f compose_overrides/health-fixes.yml up -d

# Health collector (24h window)
scripts/health/maelstrom_health.sh --hours 24 \
  --json /tmp/maelstrom_health.json \
  --summary /tmp/maelstrom_health.md

echo "JSON:"; head -c 600 /tmp/maelstrom_health.json; echo
echo "Summary:"; sed -n '1,80p' /tmp/maelstrom_health.md
```

## Screenshots / Dashboards
- Grafana panels or Wazuh dashboard screenshots if applicable.

## Risks & Rollback
- Risks: Minimal (healthcheck/command only). No data migrations.
- Rollback: Revert commit or remove `-f compose_overrides/health-fixes.yml` from compose command.

## Checklist
- [ ] `pre-commit run -a` passes
- [ ] `pytest -q` or focused markers pass
- [ ] `./validate_stack.sh --quick` shows no new failures
- [ ] Secrets not committed; `.env` changes documented
