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

