"""Currency conversion for wholesalers that bill in a currency other than
GBP (see adapters/base.py — all Listing objects are expected in GBP).

Uses Frankfurter (https://www.frankfurter.dev), a free, keyless API backed
by European Central Bank reference rates — no signup, no cost, updated on
each ECB business day.
"""
from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

FRANKFURTER_URL = "https://api.frankfurter.app/latest"


def get_rate(from_currency: str, to_currency: str) -> float:
    """Fetch today's conversion rate. Raises if the API is unreachable or
    the response is unexpected — callers should let that fail the calling
    wholesaler's run rather than silently using a stale/guessed rate.

    NOTE: this couldn't be live-tested from the environment this was built
    in (outbound network is restricted there to an allowlist that doesn't
    include api.frankfurter.app) — verify with a real `python -c
    "from currency import get_rate; print(get_rate('EUR', 'GBP'))"` run
    once you have this checked out locally or in CI.
    """
    response = requests.get(
        FRANKFURTER_URL,
        params={"from": from_currency, "to": to_currency},
        timeout=10,
    )
    response.raise_for_status()
    rate = response.json()["rates"][to_currency]
    logger.info("%s -> %s rate: %s", from_currency, to_currency, rate)
    return float(rate)
