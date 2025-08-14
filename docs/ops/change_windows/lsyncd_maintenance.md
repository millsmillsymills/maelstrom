# Change Window: Lsyncd Maintenance (Maelstrom)

Recommended window: Saturday 03:30–03:45 local
Owner: Maelstrom Ops
Impact: Low (mirroring delay only)

## Pre-check (T-5 min)
- [ ] Run snapshot: `scripts/ops/lsyncd_snapshot.sh` (captures status, logs, mount posture)
- [ ] Confirm `/mnt/code` mount healthy: `findmnt -no SOURCE,TARGET,OPTIONS /mnt/code`

## Actions
- [ ] Restart service: `sudo systemctl restart codex-home-sync.service`
- [ ] Wait 5–10 seconds, then check: `systemctl is-active codex-home-sync.service`
- [ ] Tail logs for errors: `journalctl -u codex-home-sync.service -n 100 --no-pager`

## Validation (T+5 min)
- [ ] Service `active`
- [ ] No repeated backoffs/errors in journal
- [ ] New files under `/home/mills/tools/duo/logs` are mirrored to `/mnt/code` promptly

## Rollback
- [ ] If service remains `activating`, verify mount, network, and permissions; defer to storage/network team
- [ ] Revert any config experimentation; restore previous unit files if modified (not part of this task)
