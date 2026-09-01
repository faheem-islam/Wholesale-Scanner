"""Adapter for Merkandi.co.uk — a B2B marketplace aggregating listings from
many independent sellers, not a fixed catalog. There's no single per-product
page to check, so for each target product we run a keyword search and keep
only results at or below a price ceiling (config.MERKANDI_PRICE_CEILING_MULTIPLIER)
before handing candidates to matcher.py for name/SKU matching. This also
means Merkandi results rarely carry a stable SKU, so identifier is left
unset here and matching falls back to fuzzy name matching.

NOTE ON SELECTORS: this environment had no network access to
merkandi.co.uk while writing this, so the CSS selectors below are a
best-effort guess, not a verified match against the live DOM. Before
relying on this in production: log in manually, run
`playwright codegen https://merkandi.co.uk` and correct the SELECTORS
dict below — the scraping logic itself shouldn't need to change.
"""
from __future__ import annotations

import logging
from urllib.parse import quote

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from adapters.base import Listing, WholesalerAdapter, parse_price
from config import MERKANDI_PRICE_CEILING_MULTIPLIER

logger = logging.getLogger(__name__)

BASE_URL = "https://merkandi.co.uk"
LOGIN_URL = f"{BASE_URL}/en/login"

SELECTORS = {
    "login_email": "input[name='email'], input[type='email'], #email",
    "login_password": "input[name='password'], input[type='password'], #password",
    "login_submit": "button[type='submit'], input[type='submit']",
    "login_success_marker": "a[href*='logout'], a[href*='account'], a[href*='my-account']",
    "result_card": ".offer-item, .listing-item, article.offer",
    "result_name": ".offer-title, .listing-title, h2, h3",
    "result_price": ".offer-price, .price",
    "result_link": "a",
}


class MerkandiAdapter(WholesalerAdapter):
    name = "merkandi"

    def login(self, username: str, password: str) -> None:
        page = self.page
        logger.info("[merkandi] logging in as %s", username)
        page.goto(LOGIN_URL, wait_until="domcontentloaded")
        page.locator(SELECTORS["login_email"]).first.fill(username)
        page.locator(SELECTORS["login_password"]).first.fill(password)
        page.locator(SELECTORS["login_submit"]).first.click()
        try:
            page.wait_for_selector(SELECTORS["login_success_marker"], timeout=15000)
        except PlaywrightTimeoutError as exc:
            raise RuntimeError(
                "merkandi login did not reach a logged-in state — check "
                "credentials and SELECTORS['login_success_marker']"
            ) from exc
        logger.info("[merkandi] login OK")

    def fetch_listings(self, products: list[dict]) -> list[Listing]:
        page = self.page
        listings: list[Listing] = []

        for product in products:
            search_term = product.get("identifier") or product["product_name"]
            price_ceiling = product["target_price"] * MERKANDI_PRICE_CEILING_MULTIPLIER
            search_url = f"{BASE_URL}/en/search?q={quote(search_term)}"

            try:
                page.goto(search_url, wait_until="domcontentloaded")
                page.wait_for_selector(SELECTORS["result_card"], timeout=10000)
            except PlaywrightTimeoutError:
                logger.warning("[merkandi] no search results for %r", search_term)
                continue

            cards = page.locator(SELECTORS["result_card"])
            for i in range(cards.count()):
                card = cards.nth(i)
                try:
                    name = card.locator(SELECTORS["result_name"]).first.inner_text().strip()
                    price = parse_price(card.locator(SELECTORS["result_price"]).first.inner_text())
                    href = card.locator(SELECTORS["result_link"]).first.get_attribute("href")
                except Exception:
                    logger.debug("[merkandi] skipping unparsable result card")
                    continue

                if price > price_ceiling:
                    continue

                url = href if (href and href.startswith("http")) else f"{BASE_URL}{href or ''}"
                listings.append(
                    Listing(
                        product_name=name,
                        price_ex_vat=price,
                        url=url,
                    )
                )

        return listings
