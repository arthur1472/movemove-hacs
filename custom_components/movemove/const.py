from __future__ import annotations

DOMAIN = "movemove"
PLATFORMS = ["sensor", "button"]

CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_CSRF_TOKEN = "csrf_token"
CONF_MAX_RECORDS = "max_records"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_TITLE = "MoveMove"
DEFAULT_MAX_RECORDS = 100
DEFAULT_SCAN_INTERVAL_MINUTES = 360
MIN_SCAN_INTERVAL_MINUTES = 15
ATTR_TRANSACTIONS = "transactions"
ATTR_SUMMARY = "summary"
ATTR_CURRENT_PERIOD = "current_period"
ATTR_LATEST_TRANSACTION = "latest_transaction"
ATTR_DIAGNOSTICS = "diagnostics"
