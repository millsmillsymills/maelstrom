SHELL := /bin/bash

.PHONY: gh.auth gh.probe gh.push gh.oauth

gh.auth:
	@source ./scripts/github_auth.sh >/dev/null 2>&1 || true; \
	if ./internal/github_auth/token_provider.sh >/dev/null 2>&1; then \
	  echo "Non-interactive GitHub auth OK"; \
	else \
	  echo "Non-interactive auth unavailable. Set GITHUB_OAUTH_* or GITHUB_PAT."; exit 1; \
	fi

gh.probe:
	@echo "Probing network reachability and remote access..."
	@curl -sSf https://github.com/ >/dev/null
	@GIT_ASKPASS=./internal/github_auth/git_askpass.sh GIT_TERMINAL_PROMPT=0 \
	  git -c credential.helper= -c http.https://github.com/.extraheader= \
	  ls-remote https://github.com/$$(git config --get remote.origin.url | sed -E 's#.*github.com[:/](.+/.+)\.git#\1#g').git -h refs/heads/main | head -n1

gh.push:
	@branch="$$(git rev-parse --abbrev-ref HEAD || true)"; \
	if [[ -z "$$branch" || "$$branch" == "HEAD" ]]; then \
	  branch="chore/github-integration-cleanup"; \
	  git checkout -B "$$branch"; \
	fi; \
	repo="$$(git config --get remote.origin.url | sed -E 's#.*github.com[:/](.+/.+)\.git#\1#g').git"; \
	echo "Pushing branch $$branch to https://github.com/$$repo (dry-run configurable)"; \
	GIT_ASKPASS=./internal/github_auth/git_askpass.sh GIT_TERMINAL_PROMPT=0 \
	  git -c credential.helper= -c http.https://github.com/.extraheader= \
	  push https://github.com/$$repo "$$branch"

gh.oauth:
	@./scripts/github_oauth_device.sh
