---
name: Bug report
about: Report a problem with the stack or scripts
title: "[bug] <short description>"
labels: bug
assignees: ''
---

## Summary
- What broke, expected vs actual behavior.

## Repro Steps
1. Command(s) run
2. Environment/profile(s)
3. Logs or output (snippets)

## Affected Area
- Services: grafana | prometheus | alertmanager | influxdb | exporters | other
- Scripts: deploy_stack.sh | validate_stack.sh | scripts/ops/*

## Validation
- compose: `${DOCKER} compose -f base.yml config --quiet`
- quick: `./validate_stack.sh --quick`
- logs: attach relevant snippets

## Additional Context
- Profiles used, env overrides, screenshots, etc.
