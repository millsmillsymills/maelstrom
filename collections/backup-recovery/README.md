# backup-recovery

- Purpose: Service configuration for backup-recovery within the Maelstrom stack.
- Location:   - Compose mounts from     - - Validate:
  - ${DOCKER} compose -f base.yml config --quiet
  - ./validate_stack.sh --quick
- Notes:
  - Keep secrets in secrets/ (chmod 0600); do not commit.
  - Follow kebab-case for service dirs; use *-data for runtime volumes.
