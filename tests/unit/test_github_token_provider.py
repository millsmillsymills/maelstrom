import os
import types
import builtins

import internal.github_auth.token_provider as tp


def test_pat_fallback(monkeypatch):
    monkeypatch.delenv("GITHUB_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("GITHUB_OAUTH_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("GITHUB_OAUTH_REFRESH_TOKEN", raising=False)

    monkeypatch.setenv("GITHUB_PAT", "test_pat_123")

    # Force probe to succeed
    monkeypatch.setattr(tp, "_probe_token", lambda token: (200, {}))

    tok = tp.get_access_token()
    assert tok.access_token == "test_pat_123"
    assert tok.source == "pat"


def test_oauth_then_probe_fail_then_pat(monkeypatch):
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_SECRET", "sec")
    monkeypatch.setenv("GITHUB_OAUTH_REFRESH_TOKEN", "rtok")
    monkeypatch.setenv("GITHUB_PAT", "fallback_pat")

    class DummyToken(tp.Token):
        pass

    # Mock refresh to return token, but probe returns 401
    monkeypatch.setattr(
        tp,
        "_oauth_refresh",
        lambda cid, csec, rtok: tp.Token("oauth_tok", "bearer", source="oauth"),
    )

    probes = {"oauth_tok": [401, 401, 401], "fallback_pat": [200]}

    def _probe(tok):
        lst = probes.get(tok, [0])
        return (lst.pop(0), {})

    monkeypatch.setattr(tp, "_probe_token", _probe)

    tok = tp.get_access_token()
    assert tok.access_token == "fallback_pat"
    assert tok.source == "pat"


def test_error_when_no_creds(monkeypatch):
    for k in [
        "GITHUB_OAUTH_CLIENT_ID",
        "GITHUB_OAUTH_CLIENT_SECRET",
        "GITHUB_OAUTH_REFRESH_TOKEN",
        "GITHUB_PAT",
        "GITHUB_TOKEN",
    ]:
        monkeypatch.delenv(k, raising=False)
    try:
        tp.get_access_token()
        assert False, "expected exception"
    except tp.TokenError:
        pass
