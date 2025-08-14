"""Shared pytest configuration and fixtures.

Ensures the project root is importable so tests can import modules like
`internal.github_auth.token_provider` reliably regardless of pytest's
working directory. Also provides integration-oriented fixtures which
gracefully skip when dependent services are unavailable.
"""

import os
import sys
import pathlib
from typing import Any, Dict

import pytest
import requests

# Ensure project root is on sys.path for imports like `internal.*`
# This makes collection robust even when pytest changes CWD to the tests dir.
ROOT = pathlib.Path(__file__).resolve().parents[1].resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def influxdb_client():
    """Return a live InfluxDB client or skip if not accessible."""
    try:
        from influxdb import InfluxDBClient
    except Exception as e:
        pytest.skip(f"InfluxDB client library not available: {e}")

    host = os.environ.get("INFLUXDB_HOST", "localhost")
    port = int(os.environ.get("INFLUXDB_PORT", "8086"))
    db = os.environ.get("INFLUXDB_DB", "_internal")

    try:
        client = InfluxDBClient(host=host, port=port, database=db)
        # Quick ping to verify connectivity
        health = requests.get(f"http://{host}:{port}/ping", timeout=3)
        if health.status_code not in (200, 204):
            raise RuntimeError(f"InfluxDB ping status {health.status_code}")
        return client
    except Exception as e:
        pytest.skip(f"InfluxDB not accessible: {e}")


@pytest.fixture
def prometheus_client():
    """Return a minimal Prometheus HTTP API client or skip if unavailable."""

    class PromClient:
        base_url: str

        def __init__(self, base_url: str = "http://localhost:9090") -> None:
            self.base_url = base_url.rstrip("/")

        def query(self, expr: str) -> Dict[str, Any]:
            resp = requests.get(
                f"{self.base_url}/api/v1/query", params={"query": expr}, timeout=5
            )
            resp.raise_for_status()
            return resp.json()

    # Verify Prometheus is reachable; if not, skip
    try:
        pc = PromClient()
        health = requests.get("http://localhost:9090/-/ready", timeout=3)
        health.raise_for_status()
        return pc
    except Exception as e:
        pytest.skip(f"Prometheus not accessible: {e}")


@pytest.fixture
def secrets_helper():
    """Expose the secrets helper if configured; skip when not available.

    Ensures Slack webhook is available to satisfy tests that assert presence.
    """
    try:
        # Import our helper module directly from service collections path
        import importlib.util
        import pathlib

        root = pathlib.Path(__file__).resolve().parents[1]
        service_path = root / ".." / "collections" / "ml_analytics"
        spec = importlib.util.spec_from_file_location(
            "ml_analytics.secrets_helper",
            str(service_path / "secrets_helper.py"),
        )
        if not spec or not spec.loader:
            raise ImportError("Cannot load secrets_helper spec")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as e:
        pytest.skip(f"Secrets helper not importable: {e}")

    # If Slack webhook not configured, skip dependent tests
    webhook = module.read_secret("slack_webhook_url", required=False)
    if not webhook:
        pytest.skip("Slack webhook not configured for integration tests")

    return module
