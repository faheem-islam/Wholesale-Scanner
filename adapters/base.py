"""Shared interface every wholesaler adapter implements.

A wholesaler adapter owns login + scraping for exactly one site. `main.py`
gives it a fresh, logged-in Playwright page once per run and reuses that
same session for every product check against that wholesaler.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import Page


@dataclass
class Listing:
    """One scraped price record, matching the shape required by the spec.

    Prices are always in GBP, since that's the currency target_price uses
    in products.csv. A wholesaler that bills in a different currency is
    responsible for converting before returning Listing objects — see
    adapters/eurolots.py (EUR) for an example, via currency.py.
    """

    product_name: str
    price_ex_vat: float
    url: str
    identifier: Optional[str] = None
    price_inc_vat: Optional[float] = None
    stock: Optional[int] = None


class WholesalerAdapter(ABC):
    name: str

    def __init__(self, page: Page):
        self.page = page

    @abstractmethod
    def login(self, username: str, password: str) -> None:
        """Log in once; the session is then reused for the rest of the run."""

    @abstractmethod
    def fetch_listings(self, products: list[dict]) -> list[Listing]:
        """Return listings relevant to the given target products (all of
        which belong to this wholesaler)."""


def parse_price(text: str) -> float:
    """Pull a number like 12.34 out of a price string, e.g. '£12.34 ex VAT'."""
    match = re.search(r"[\d,]+\.\d{2}|\d+", text.replace(",", ""))
    if not match:
        raise ValueError(f"could not parse price from {text!r}")
    return float(match.group())
