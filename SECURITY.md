# Security Policy

## Supported Versions
- Active development on `main`. Security fixes are prioritized for currently deployed stacks.

## Reporting a Vulnerability
- Email the maintainer or open a private issue if available. Do not post secrets publicly.
- Include: affected component, reproduction steps, logs, and impact.

## Secret Management
- Never commit real secrets. Use `secrets/` (chmod 0600) and `.env.template` as reference.
- Docker services read secrets from files or environment; prefer file-based mounts for long-lived credentials.

## Hardening & Scanning
- Run `./validate_stack.sh --security-only` before merges.
- Scan images with `scripts/scan_images.sh` and review findings.
- Compose config uses restricted privileges, resource limits, and network segmentation where possible.

## Incident Response
- Quarantine affected services via `docker-compose stop <service>`.
- Rotate credentials: update secret files and restart dependent services.
- Review Wazuh/Suricata/Zeek dashboards and Alertmanager routes for ongoing threats.

