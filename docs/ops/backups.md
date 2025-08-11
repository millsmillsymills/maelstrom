# Backups (Operations)

This project includes backup utilities under `scripts/backups/`. This document outlines read-only verification and a safe approach to scheduling.

## Verify backups (read-only)

Use the verification script to summarize presence and recency without writing:

```bash
scripts/backups/verify_backups.sh --base-dir /home/mills/backup/maelstrom --max-age-days 7
```

Outputs recent directories/files, newest artifacts, and totals. It never writes.

## Dry-run utilities

- `scripts/backups/backup_influxdb.sh` — supports dry-run flags in comments; consult script usage.
- `scripts/backups/backup_volume.sh` — supports `--dry-run`.

## Suggested schedule (example; commented)

Add to crontab (edit with `crontab -e`) only after validation. The following shows a daily verification and weekly dry-run example; both are safe.

```cron
# Daily verify (07:30): read-only check of backups directory
30 7 * * * /bin/bash -lc 'cd $HOME && scripts/backups/verify_backups.sh --base-dir /home/mills/backup/maelstrom --max-age-days 7 >> $HOME/tools/duo/logs/backup_verify.log 2>&1'

# Weekly dry-run volume backup sample (Saturday 03:15): adjust volume name
#15 3 * * 6 /bin/bash -lc 'cd $HOME && scripts/backups/backup_volume.sh prometheus_data --dry-run >> $HOME/tools/duo/logs/backup_dryrun.log 2>&1'
```

## Retention

Use `scripts/backups/rotate_backups.sh` in `--dry-run` first to preview deletions before enabling in production.

