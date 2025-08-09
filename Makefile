SHELL := /bin/bash

.PHONY: gh.auth gh.probe gh.push

gh.auth:
	@./scripts/github_auth.sh --require-token

gh.probe:
	@echo "Probing network reachability and remote access..."
	@curl -sSf https://github.com/ >/dev/null
	@GIT_CURL_VERBOSE=1 git ls-remote origin -h refs/heads/main | head -n1

gh.push:
	@branch="$$(git rev-parse --abbrev-ref HEAD || true)"; \
	if [[ -z "$$branch" || "$$branch" == "HEAD" ]]; then \
	  branch="chore/github-integration-cleanup"; \
	  git checkout -B "$$branch"; \
	fi; \
	upstream_set=$$(git rev-parse --abbrev-ref --symbolic-full-name "$$branch@{u}" >/dev/null 2>&1 && echo yes || echo no); \
	echo "Pushing branch $$branch (upstream set: $$upstream_set)"; \
	if [[ "$$upstream_set" == "no" ]]; then \
	  GIT_TRACE=1 GIT_CURL_VERBOSE=1 git push -u origin "$$branch"; \
	else \
	  GIT_TRACE=1 GIT_CURL_VERBOSE=1 git push origin "$$branch"; \
	fi

