#!/usr/bin/env bash
# shellcheck disable=SC1091
[ -f /usr/local/lib/codex_env.sh ] && . /usr/local/lib/codex_env.sh
set -euo pipefail

echo "== Pre-sync safety checks =="

have() { command -v "$1" >/dev/null 2>&1; }

if have git; then
  echo "-- Git tracked sensitive file scan --"
  SUSPICIOUS=$(git ls-files -z | tr '\0' '\n' | grep -Ei '(\\bsecret|\\bpassword|\\btoken|\\bcred|\\bkey)') || true
  if [ -n "${SUSPICIOUS:-}" ]; then
    echo "Found potentially sensitive tracked paths:" && echo "$SUSPICIOUS" | sed 's/^/  - /'
  else
    echo "No suspicious tracked paths found"
  fi

  echo "-- Ensure secrets/ and .env are untracked/ignored --"
  for p in secrets .env .smbcredentials env_vars.txt; do
    if git ls-files --error-unmatch "$p" >/dev/null 2>&1; then
      echo "WARNING: $p is tracked by git (should be ignored)"
    else
      echo "OK: $p not tracked"
    fi
    git check-ignore -v "$p" >/dev/null 2>&1 && git check-ignore -v "$p" || echo "NOTE: $p not ignored"
  done
fi

echo
echo "-- Compose config validation --"
if have docker; then
  ${DOCKER} compose -f base.yml -f docker-compose.secrets.yml config --quiet && echo "Compose config OK" || { echo "Compose config FAILED"; exit 1; }
else
  echo "${DOCKER} not found; skip compose validation"
fi

echo
echo "-- Pre-commit hooks (optional) --"
echo "Run: pre-commit install && pre-commit run --all-files"

echo
echo "Pre-sync checks complete."