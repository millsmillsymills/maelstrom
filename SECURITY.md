Secret Handling and Rotation

- Never commit secrets. Use `secrets/` (0600) and environment variables in CI.
- Central GitHub auth uses OAuth2 refresh or PAT non-interactively via `internal/github_auth/`.
- Banned patterns: interactive `gh auth login`, device-code flows, `.netrc` for GitHub, tokens in URLs, `Authorization: Basic` to api.github.com.
- Rotation procedure:
  - Revoke leaked tokens in the provider (GitHub settings).
  - Purge from history using `git filter-repo` targeting exact blobs/paths, then force-push.
  - Tag previous head as `pre-auth-scrub-<timestamp>`.
  - Update CI secrets and re-run `auth-smoke` job.

If you detect a leak:
- Open an incident issue and rotate credentials immediately.
- Provide redacted details and affected paths/commits. Do not include secret values.

Container Image Security and Scanning

- Pin image tags in `.env` to avoid `latest` drift (see `.env.pinned.example`).
- Validate configs with `${DOCKER:-docker} compose -f base.yml config --quiet`.
- Scan images for HIGH/CRITICAL CVEs:
  - Running services only: `SCAN_ONLY_RUNNING=true ./validate_stack.sh --security-only`
  - All compose images: `./validate_stack.sh --security-only`
- Review reports under `reports/vulnerability_scan_*.json`; list of vulnerable images in `logs/vulnerable_images.txt`.
- Prefer non-Alpine or stable patch tags where upstream CVEs are lower; test in non-prod first.
- Document acceptable risk: add vetted CVEs to `.trivyignore` with rationale and links; keep entries minimal and time-bound. Review ignores by: 2025-09-14.

Ignored custom-image CVEs (vetted)

- CVE-2023-31484: https://nvd.nist.gov/vuln/detail/CVE-2023-31484
- CVE-2023-45853: https://nvd.nist.gov/vuln/detail/CVE-2023-45853
- CVE-2024-47874: https://nvd.nist.gov/vuln/detail/CVE-2024-47874
- CVE-2024-53981: https://nvd.nist.gov/vuln/detail/CVE-2024-53981
- CVE-2025-4802:  https://nvd.nist.gov/vuln/detail/CVE-2025-4802
- CVE-2025-6020:  https://nvd.nist.gov/vuln/detail/CVE-2025-6020
- CVE-2025-6965:  https://nvd.nist.gov/vuln/detail/CVE-2025-6965

Notes
- These entries apply only to custom images (API and Plex collector) to keep signal high while vendors patch bases.
- Re-validate monthly; remove ignores when upstream or base updates remediate.

## Pinned Image Matrix (CVE-aware + stable)

- prom/prometheus: `v2.53.5` — lowest HIGH/CRIT among nearby versions.
- prom/node-exporter: `v1.8.2` — lower than v1.8.1/1.8.0.
- prom/alertmanager: `v0.27.0` — better than v0.25.x.
- grafana/loki: `2.9.9` — lower than 2.9.10/2.9.11 in scans.
- grafana/promtail: `2.9.11` — lower than 2.9.10.
- gcr.io/cadvisor/cadvisor: `v0.49.2` — lower than v0.49.1.
- grafana/grafana: `11.1.13-ubuntu` — competitive with 11.2.x; stable.
- influxdb: `1.8.10` — alpine variant is much worse in scans.
- hashicorp/vault: `1.16.3` — older tags inconsistent to scan.

Rationale
- Pins selected based on recent Trivy scans for HIGH/CRITICAL exposure while maintaining service health.
- Weekly drift job (`track-cve-drift.yml`) scans these images to surface changes over time.
