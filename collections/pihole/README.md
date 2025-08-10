# pihole

- Purpose: Service configuration for pihole within the Maelstrom stack.
- Validate:
  - ${DOCKER} compose -f base.yml config --quiet
  - ./validate_stack.sh --quick
- Notes:
  - Keep secrets in secrets/ (chmod 0600); do not commit.
  - Follow kebab-case for service dirs; use *-data for runtime volumes.