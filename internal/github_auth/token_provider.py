import os
import json
import time
import random
import stat
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any

import urllib.request
import urllib.error


CACHE_PATH = os.path.expanduser("~/.cache/github_token.json")


@dataclass
class Token:
    access_token: str
    token_type: str
    expires_at: Optional[float] = None  # epoch seconds
    source: str = "unknown"  # "oauth" or "pat" or "env"
    scopes: Optional[str] = None


class TokenError(RuntimeError):
    pass


def _now() -> float:
    return time.time()


def _read_cache() -> Optional[Token]:
    try:
        if os.environ.get("CI"):  # skip disk cache in CI
            return None
        if not os.path.exists(CACHE_PATH):
            return None
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "access_token" not in data:
            return None
        t = Token(
            access_token=data["access_token"],
            token_type=data.get("token_type", "bearer"),
            expires_at=data.get("expires_at"),
            source=data.get("source", "cache"),
            scopes=data.get("scopes"),
        )
        # If expires_at is close (<5m), ignore
        if t.expires_at and t.expires_at - _now() <= 300:
            return None
        return t
    except Exception:
        return None


def _write_cache(token: Token) -> None:
    if os.environ.get("CI"):
        return
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "access_token": token.access_token,
                    "token_type": token.token_type,
                    "expires_at": token.expires_at,
                    "source": token.source,
                    "scopes": token.scopes,
                },
                f,
            )
        os.chmod(CACHE_PATH, stat.S_IRUSR | stat.S_IWUSR)  # 0600
    except Exception:
        # best-effort cache only
        pass


def _oauth_refresh(
    client_id: str, client_secret: str, refresh_token: str
) -> Token:
    """
    Perform OAuth2 refresh for GitHub OAuth App.

    Scopes guidance: ensure refresh token/session grants include repo, workflow, read:org as needed.
    """
    url = "https://github.com/login/oauth/access_token"
    payload = json.dumps(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        }
    ).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Accept", "application/json")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise TokenError(f"OAuth refresh failed: HTTP {e.code}") from e
    except Exception as e:
        raise TokenError("OAuth refresh failed: network error") from e

    access_token = data.get("access_token")
    token_type = data.get("token_type", "bearer")
    expires_in = data.get("expires_in")
    new_refresh_token = data.get("refresh_token")
    scope = data.get("scope") or data.get("scopes")

    if not access_token:
        raise TokenError("OAuth refresh failed: missing access_token in response")

    expires_at = None
    if isinstance(expires_in, (int, float)):
        expires_at = _now() + float(expires_in)

    # Optionally persist the new refresh token if desired; we avoid writing secrets here.
    t = Token(
        access_token=access_token,
        token_type=token_type,
        expires_at=expires_at,
        source="oauth",
        scopes=scope,
    )
    _write_cache(t)
    return t


def _get_oauth_from_env() -> Optional[Tuple[str, str, str]]:
    cid = os.environ.get("GITHUB_OAUTH_CLIENT_ID")
    csec = os.environ.get("GITHUB_OAUTH_CLIENT_SECRET")
    rtok = os.environ.get("GITHUB_OAUTH_REFRESH_TOKEN")
    if cid and csec and rtok:
        return cid, csec, rtok
    return None


def _get_pat_from_env() -> Optional[str]:
    # Accept both GITHUB_PAT and GITHUB_TOKEN for CI convenience
    return os.environ.get("GITHUB_PAT") or os.environ.get("GITHUB_TOKEN")


def _backoff_sleep(attempt: int) -> None:
    # Exponential backoff with jitter up to ~2^attempt seconds
    base = min(2 ** attempt, 16)
    time.sleep(random.uniform(0.25, base))


def _probe_token(token: str) -> Tuple[int, Dict[str, Any]]:
    url = os.environ.get("GITHUB_API_BASE", "https://api.github.com") + "/rate_limit"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            code = resp.getcode()
            body = json.loads(resp.read().decode("utf-8"))
            return code, body
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
        except Exception:
            body = {}
        return e.code, body
    except Exception:
        return 0, {}


def get_access_token() -> Token:
    """
    Return a valid GitHub access token with metadata.

    Priority:
      1) OAuth2 access token from cached refresh flow (refresh if <=5m to expiry)
      2) PAT from env (GITHUB_PAT or GITHUB_TOKEN)

    Automatic failover on 401/403 with exponential backoff and one flip between sources.

    Scopes guidance: ensure repo, workflow, read:org as required by use.
    """
    # 1) Try cached token
    cached = _read_cache()
    if cached:
        code, _ = _probe_token(cached.access_token)
        if code in (200, 304):
            return cached

    # 2) Try OAuth refresh
    tried_oauth_err = None
    oauth_env = _get_oauth_from_env()
    if oauth_env:
        cid, csec, rtok = oauth_env
        try:
            oauth_token = _oauth_refresh(cid, csec, rtok)
            # Probe
            for attempt in range(3):
                code, _ = _probe_token(oauth_token.access_token)
                if code in (200, 304):
                    return oauth_token
                if code in (401, 403, 429) or code == 0:
                    _backoff_sleep(attempt)
                else:
                    break
        except TokenError as e:
            tried_oauth_err = e

    # 3) Fallback to PAT
    pat = _get_pat_from_env()
    if pat:
        token = Token(access_token=pat, token_type="bearer", source="pat")
        for attempt in range(3):
            code, _ = _probe_token(token.access_token)
            if code in (200, 304):
                return token
            if code in (401, 403, 429) or code == 0:
                _backoff_sleep(attempt)
            else:
                break

    # 4) Try the other source once if not tried or failed differently
    if pat and oauth_env:
        # flip once more: if PAT failed, try OAuth; if OAuth failed, try PAT
        if tried_oauth_err is not None:
            # OAuth failed; PAT already tried
            pass
        else:
            cid, csec, rtok = oauth_env
            try:
                oauth_token = _oauth_refresh(cid, csec, rtok)
                return oauth_token
            except Exception:
                pass

    # Structured error
    hints = []
    if not oauth_env:
        hints.append("Set OAuth env: GITHUB_OAUTH_CLIENT_ID/SECRET/REFRESH_TOKEN or")
    if not pat:
        hints.append("provide GITHUB_PAT (or GITHUB_TOKEN in CI)")
    raise TokenError(
        "Unable to obtain GitHub token non-interactively. "
        + " ".join(hints)
    )


def get_auth_header() -> Tuple[str, str]:
    t = get_access_token()
    return ("Authorization", f"Bearer {t.access_token}")


__all__ = ["Token", "TokenError", "get_access_token", "get_auth_header"]

