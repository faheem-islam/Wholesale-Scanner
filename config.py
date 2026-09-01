"""Central, non-secret configuration.

Credentials and mail server details come from environment variables
(see .env.example) — never put them here.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
PRODUCTS_CSV = ROOT_DIR / "products.csv"

# Merkandi is a marketplace search, not a fixed catalog, so results can't be
# filtered by exact SKU up front. This caps how far above a product's target
# price a search result is still worth pulling in for name/SKU matching —
# tune it if searches return too many or too few candidates.
MERKANDI_PRICE_CEILING_MULTIPLIER = 1.5

# Fuzzy name-matching threshold (0-100, higher = stricter), used as a
# fallback when a wholesaler doesn't expose a consistent SKU. See matcher.py.
FUZZY_MATCH_THRESHOLD = 85

# Where price alerts are sent. Faheem's address is used as the default since
# the exact preference wasn't specified — override via env var if needed.
ALERT_EMAIL_TO = os.environ.get("ALERT_EMAIL_TO", "faheem_islam02@hotmail.com")
