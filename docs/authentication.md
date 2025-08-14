Authentication: GitHub OAuth2 + PAT (Non-Interactive)

Overview
- Central module at `internal/github_auth/` provides non-interactive GitHub authentication for all languages (Python, Node, Bash).
- Priority order: OAuth2 refresh (pre-provisioned refresh token) → PAT → backoff/retry. One automatic failover between sources.
- All API calls inject headers: `Authorization: Bearer <token>`, `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`.
- Git operations use ephemeral `GIT_ASKPASS` and never persist credentials.

Environment Variables
- OAuth2: `GITHUB_OAUTH_CLIENT_ID`, `GITHUB_OAUTH_CLIENT_SECRET`, `GITHUB_OAUTH_REFRESH_TOKEN`
- PAT: `GITHUB_PAT` (CI can map `${{ github.token }}`)
- Common: `GITHUB_API_BASE` (default https://api.github.com), `GITHUB_GRAPHQL_URL` (default https://api.github.com/graphql)

Usage
- Bash REST/GraphQL: `AUTH_HEADER=$(internal/github_auth/token_provider.sh --print-header)` then `curl -H "$AUTH_HEADER" ...`
- Git CLI: `GIT_ASKPASS=internal/github_auth/git_askpass.sh git -c credential.helper= -c http.https://github.com/.extraheader= <cmd>`
- Python: `from internal.github_auth.token_provider import get_auth_header`
- Node: `import { getAccessToken } from '../internal/github_auth/tokenProvider'`

Scopes
- Ensure required scopes for your use: `repo`, `workflow`, `read:org` as needed by scripts and CI.

Caching
- In-memory cache in all adapters.
- Optional on-disk cache at `~/.cache/github_token.json` with 0600 perms; skipped in CI.

Deprecated Patterns (removed)
- Interactive flows: `gh auth login`, device/browser codes, prompts.
- Insecure/static auth: basic auth, tokens in URLs, `.netrc` for GitHub, persisted git headers.

CI Behavior
- GitHub Actions job `auth-smoke` validates REST, GraphQL, and git (dry-run push) without prompts.
- Prefer default `${{ github.token }}`; mapped to `GITHUB_PAT` for provider compatibility.
