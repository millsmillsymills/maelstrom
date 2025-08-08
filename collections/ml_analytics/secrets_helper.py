#!/usr/bin/env python3
"""
Secrets Helper Module for ML/Analytics services
Provides secure secret retrieval and connection URL helpers.
"""

import os
from pathlib import Path
from typing import Optional


def read_secret(secret_name: str, fallback_env: Optional[str] = None, required: bool = True) -> Optional[str]:
    """
    Read a secret from the secrets directory or fall back to env vars.

    Args:
        secret_name: Name of the secret file (e.g., "influxdb_admin_password").
        fallback_env: Environment variable name to use as a fallback.
        required: If True, raise when not found; otherwise return None.

    Returns:
        The secret value as a string, or None when not required and missing.
    """
    # Try reading from Docker secrets mount (or local test path via patched Path)
    secret_path = Path(f"/secrets/{secret_name}")
    if secret_path.exists():
        value = secret_path.read_text().strip()
        if value:
            return value

    # Fallback to provided environment variable
    if fallback_env:
        env_value = os.environ.get(fallback_env)
        if env_value:
            return env_value

    # Final fallback: direct env lookup by uppercased secret name
    direct_env = os.environ.get(secret_name.upper())
    if direct_env:
        return direct_env

    if required:
        # Match test expectation for error message wording
        raise ValueError(f"Required secret '{secret_name}' not found")
    return None


def get_database_url(db_type: str = "influxdb") -> str:
    """
    Build a database connection URL using secrets and environment.

    Supported types:
      - influxdb: http://<user>:<pass>@<host>:<port>/<db>
      - mysql:    mysql://<user>:<pass>@<host>/<db>
    """
    if db_type == "influxdb":
        user = os.environ.get("INFLUXDB_ADMIN_USER", "admin")
        host = os.environ.get("INFLUXDB_HOST", "influxdb")
        port = os.environ.get("INFLUXDB_PORT", "8086")
        db = os.environ.get("INFLUXDB_DB", "")
        password = read_secret("influxdb_admin_password", "INFLUXDB_ADMIN_PASSWORD", required=False) or ""

        auth = f"{user}:{password}@" if password else ""
        suffix = f"/{db}" if db else ""
        return f"http://{auth}{host}:{port}{suffix}"

    if db_type == "mysql":
        user = os.environ.get("ZABBIX_DB_USER", "root")
        host = os.environ.get("ZABBIX_DB_HOST", "mysql")
        db = os.environ.get("ZABBIX_DB_NAME", "")
        password = read_secret("zabbix_db_password", "ZABBIX_DB_PASSWORD", required=False) or ""

        auth = f"{user}:{password}@" if password else ""
        suffix = f"/{db}" if db else ""
        return f"mysql://{auth}{host}{suffix}"

    raise ValueError(f"Unsupported database type: {db_type}")


def get_slack_webhook() -> Optional[str]:
    """Return the Slack webhook URL if configured, else None."""
    return read_secret("slack_webhook_url", "SLACK_WEBHOOK_URL", required=False)


def get_api_key(service: str) -> str:
    """
    Retrieve API key for a given service.

    Currently supported services:
      - "unraid": secret file "unraid_api_key" or env "UNRAID_API_KEY".
    """
    service = service.lower()
    if service == "unraid":
        value = read_secret("unraid_api_key", "UNRAID_API_KEY", required=True)
        return value

    # Match unit test expectation for invalid services
    raise ValueError(f"Unknown service: {service}")

