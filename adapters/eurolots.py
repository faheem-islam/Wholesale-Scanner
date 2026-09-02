"""Adapter for Eurolots.com — a single wholesaler's own liquidation/returns
catalog. Prices live on individual item pages, so for each target product
we search the catalog and read the price off the first matching result.

Confirmed against the live site via Playwright codegen (see the item page
at /en/item/<slug>, which shows a specs table with SKU/stock/condition
rows and a price shown only ex-VAT):
  - login fields: get_by_role("textbox", name="E-mail address"/"Password")
  - login button: get_by_role("button", name="Login")
  - logged-in marker: a "Logout" link becomes visible
  - search box: get_by_role("textbox", name="Search")
  - search submit: button[name="submit_search"]
  - item URL pattern: https://www.eurolots.com/en/item/<slug>
  - product title: an <h1>-level heading
  - price: text like "€12,00 VAT Excl." (comma as decimal separator — see
    _parse_eur_amount, NOT the shared parse_price helper)
  - SKU: a table row labelled "SKU" whose second cell holds the value
    (same pattern confirmed for "In Stock" and "Condition" rows)
  - no VAT-inclusive price is shown anywhere on the item page, so it's
    calculated here instead (see VAT_RATE)

STILL UNCONFIRMED, flagged rather than guessed silently:
  - The exact click path to open the login form (whether "Login" is
    directly clickable from the homepage, or sits behind another menu —
    the recording that captured the working login also included a
    ".popup-close" click, suggesting a cookie/promo popup can appear first)
  - The search RESULTS page's own URL/structure — `fetch_listings` below
    picks the first link whose href matches the confirmed /en/item/
    pattern, which should be robust to markup/class changes, but hasn't
    been run against a real results page yet.
Both should get exercised (and adjusted if wrong) by the first real run.

Eurolots bills in EUR; target_price in products.csv is GBP, so prices are
converted here (see currency.py) before being returned — Listing objects
from every adapter are expected to be in GBP (adapters/base.py).
"""
from __future__ import annotations

import logging
import re

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from adapters.base import Listing, WholesalerAdapter
from currency import get_rate

logger = logging.getLogger(__name__)

BASE_URL = "https://www.eurolots.com"

# Eurolots only shows the ex-VAT price; this is applied to derive the
# inc-VAT figure shown in alerts. UK standard rate, per confirmation.
VAT_RATE = 0.20

PRICE_TEXT_RE = re.compile(r"€\s*[\d.,]+\s*VAT Excl\.", re.IGNORECASE)


def _parse_eur_amount(text: str) -> float:
    """'€1.234,56 VAT Excl.' -> 1234.56. Eurolots uses EU number
    formatting (comma as the decimal separator, '.' for thousands) —
    NOT the UK/US style the shared adapters.base.parse_price expects."""
    digits = re.sub(r"[^\d.,]", "", text)
    normalised = digits.replace(".", "").replace(",", ".")
    return float(normalised)


class EurolotsAdapter(WholesalerAdapter):
    name = "eurolots"

    def __init__(self, page):
        super().__init__(page)
        self._eur_to_gbp: float | None = None

    def _to_gbp(self, eur_amount: float) -> float:
        if self._eur_to_gbp is None:
            self._eur_to_gbp = get_rate("EUR", "GBP")
        return round(eur_amount * self._eur_to_gbp, 2)

    def login(self, username: str, password: str) -> None:
        page = self.page
        logger.info("[eurolots] logging in as %s", username)
        page.goto(BASE_URL, wait_until="domcontentloaded")

        # Best-effort: a cookie/promo popup can appear on first load.
        try:
            page.locator(".popup-close").click(timeout=3000)
        except PlaywrightTimeoutError:
            pass

        page.get_by_role("link", name=re.compile("login", re.IGNORECASE)).first.click()
        page.get_by_role("textbox", name="E-mail address").fill(username)
        page.get_by_role("textbox", name="Password").fill(password)
        page.get_by_role("button", name="Login").click()

        try:
            page.get_by_role("link", name=re.compile("logout", re.IGNORECASE)).wait_for(timeout=15000)
        except PlaywrightTimeoutError as exc:
            raise RuntimeError(
                "eurolots login did not reach a logged-in state (no 'Logout' "
                "link appeared) — check credentials, and whether 'Login' is "
                "still directly clickable from the homepage"
            ) from exc
        logger.info("[eurolots] login OK")

    def fetch_listings(self, products: list[dict]) -> list[Listing]:
        page = self.page
        listings: list[Listing] = []

        for product in products:
            query = product.get("identifier") or product["product_name"]

            try:
                page.get_by_role("textbox", name="Search").fill(query)
                page.locator("button[name='submit_search']").click()
                page.wait_for_load_state("domcontentloaded")
            except PlaywrightTimeoutError:
                logger.warning("[eurolots] search failed for %r", query)
                continue

            result_link = page.locator("a[href*='/en/item/']").first
            if result_link.count() == 0:
                logger.warning("[eurolots] no search results for %r", query)
                continue
            href = result_link.get_attribute("href")
            product_url = href if href.startswith("http") else f"{BASE_URL}{href}"

            try:
                page.goto(product_url, wait_until="domcontentloaded")

                name = page.get_by_role("heading").first.inner_text().strip()

                price_locator = page.get_by_text(PRICE_TEXT_RE).first
                price_ex_vat_eur = _parse_eur_amount(price_locator.inner_text())
                price_inc_vat_eur = round(price_ex_vat_eur * (1 + VAT_RATE), 2)

                identifier = self._spec_value(page, "SKU")

                listings.append(
                    Listing(
                        product_name=name,
                        price_ex_vat=self._to_gbp(price_ex_vat_eur),
                        price_inc_vat=self._to_gbp(price_inc_vat_eur),
                        url=product_url,
                        identifier=identifier,
                    )
                )
            except Exception:
                logger.exception("[eurolots] failed to scrape %s", product_url)
                continue

        return listings

    @staticmethod
    def _spec_value(page, label: str) -> str | None:
        """Read the value cell from the item page's specs table, e.g.
        _spec_value(page, "SKU") -> "EU B0C1KQLLC5"."""
        row = page.get_by_role("row").filter(has_text=label)
        if row.count() == 0:
            return None
        cells = row.first.get_by_role("cell")
        if cells.count() < 2:
            return None
        return cells.nth(1).inner_text().strip()
