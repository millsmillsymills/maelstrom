# Lsyncd Troubleshooting (Maelstrom)

Lsyncd mirrors `/home/mills` content (e.g., ops artifacts) to `/mnt/code`. If the service appears `activating` or lagging, use this read-only flow:

## Read-only checks

```bash
# Service state and recent logs
systemctl status codex-home-sync.service --no-pager
journalctl -u codex-home-sync.service -n 200 --no-pager

# Lsyncd logs (host)
sudo tail -n 200 /var/log/lsyncd/lsyncd.log

# Target mount posture
findmnt -no SOURCE,TARGET,OPTIONS /mnt/code
```

## Common causes
- Target share latency or reconnects causing startup delays.
- Exclusion rules causing noisy retries.
- Permission issues on specific files.

## Low-risk remediation (change window)
- Restart service after confirming target mount is healthy:

```bash
sudo systemctl restart codex-home-sync.service
sleep 5
systemctl is-active codex-home-sync.service
```

- If restart keeps reverting to `activating`, increase verbosity and inspect rsync options in the unit configuration (file location may vary) and confirm remote path accessibility.

## Validation
- Service becomes `active`.
- Lsyncd log shows steady syncing without repeated backoffs.
- No errors in `journalctl -u codex-home-sync.service` for 5–10 minutes after restart.

