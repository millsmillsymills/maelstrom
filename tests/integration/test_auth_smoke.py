import os
import json
import subprocess
import pytest


pytestmark = pytest.mark.integration


def _provider_header():
    proc = subprocess.run([
        'bash','-lc','internal/github_auth/token_provider.sh --print-header'
    ], capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def test_rest_rate_limit_non_interactive():
    hdr = _provider_header()
    if not hdr:
        pytest.skip('No token available in environment for auth smoke')
    import urllib.request
    req = urllib.request.Request('https://api.github.com/rate_limit')
    k, v = hdr.split(': ', 1)
    req.add_header(k, v)
    req.add_header('Accept', 'application/vnd.github+json')
    req.add_header('X-GitHub-Api-Version', '2022-11-28')
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.getcode() in (200, 304)


def test_graphql_viewer(monkeypatch):
    hdr = _provider_header()
    if not hdr:
        pytest.skip('No token available in environment for auth smoke')
    import urllib.request
    data = json.dumps({'query': 'query { viewer { login } }'}).encode('utf-8')
    req = urllib.request.Request('https://api.github.com/graphql', data=data, method='POST')
    k, v = hdr.split(': ', 1)
    req.add_header(k, v)
    req.add_header('Accept', 'application/vnd.github+json')
    req.add_header('X-GitHub-Api-Version', '2022-11-28')
    req.add_header('Content-Type', 'application/json')
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.getcode() in (200, 304)

