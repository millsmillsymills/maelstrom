"""
Compatibility shim for legacy imports.
Re-exports helpers from collections.ml_analytics.secrets_helper
so that `from secrets_helper import ...` continues to work.
"""

from collections.ml_analytics.secrets_helper import (
    read_secret,
    get_database_url,
    get_slack_webhook,
    get_api_key,
)
