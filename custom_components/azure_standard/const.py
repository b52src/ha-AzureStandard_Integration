"""Constants for the Azure Standard integration."""
from __future__ import annotations

from datetime import timedelta

DOMAIN = "azure_standard"
API_BASE = "https://api.azurestandard.com"

# Config entry keys
CONF_MODE = "mode"
CONF_DROP_ID = "drop_id"
CONF_EMAIL = "email"
CONF_PASSWORD = "password"              # stored in entry.data (HA encrypts .storage)
CONF_PERSON_ID = "person_id"
CONF_SESSION_COOKIE = "session_cookie"  # stored in entry.data, not options
CONF_TRACKED_PRODUCTS = "tracked_products"
CONF_DISCOVERY_ENABLED = "discovery_enabled"
CONF_MIN_PURCHASE_COUNT = "min_purchase_count"
CONF_SALE_THRESHOLD = "sale_threshold"

# Modes
MODE_MANUAL = "manual"
MODE_ACCOUNT = "account"

# Defaults
DEFAULT_MIN_PURCHASE_COUNT = 3
DEFAULT_SALE_THRESHOLD = 0.95
DEFAULT_PRICE_HISTORY_DAYS = 90

# Poll intervals
SCAN_INTERVAL_PUBLIC = timedelta(hours=6)
SCAN_INTERVAL_ORDERS = timedelta(hours=1)
SCAN_INTERVAL_LISTS = timedelta(minutes=30)
SCAN_INTERVAL_HISTORY = timedelta(hours=24)
SCAN_INTERVAL_SESSION = timedelta(hours=12)

# Storage keys
STORAGE_KEY_PRICE_HISTORY = f"{DOMAIN}.price_history"
STORAGE_VERSION = 1
