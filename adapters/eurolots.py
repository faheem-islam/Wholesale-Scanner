"""Adapter for Eurolots.com — a single wholesaler's own liquidation/returns
catalog. Prices live on individual item pages, so for each target product
we search the catalog and read the price off the first matching result.

NOTE ON SELECTORS: this environment had no network access to
www.eurolots.com while writing this, so the CSS selectors below are a
best-effort guess based on common e-commerce markup, not a verified match
against the live DOM. Before relying on this in production: log in
manually, run `playwright codegen https://www.eurolots.com` (or just
inspect the page) and correct the SELECTORS dict below — the scraping
logic itself shouldn't need to change.
"""
from __future__ import annotations

import logging

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from adapters.base import Listing, WholesalerAdapter, parse_price

logger = logging.getLogger(__name__)

BASE_URL = "https://www.eurolots.com"
LOGIN_URL = f"{BASE_URL}/login"

SELECTORS = {
    "login_email": "input[name='email'], input[type='email'], #email",
    "login_password": "input[name='password'], input[type='password'], #password",
    "login_submit": "button[type='submit'], input[type='submit']",
    "login_success_marker": "a[href*='logout'], a[href*='account'], a[href*='my-account']",
    "search_result_link": "a.product-item, .product-list a.product, a[href*='/product/']",
    "product_name": ".product-name, h1.product-title, .product-title",
    "product_price_ex_vat": ".price-excl-vat, .price-ex-vat, .product-price",
    "product_price_inc_vat": ".price-incl-vat, .price-inc-vat",
    "product_sku": ".product-sku, .sku, [data-sku]",
}


class EurolotsAdapter(WholesalerAdapter):
    name = "eurolots"

    def login(self, username: str, password: str) -> None:
        page = self.page
        logger.info("[eurolots] logging in as %s", username)
        page.goto(LOGIN_URL, wait_until="domcontentloaded")
        page.locator(SELECTORS["login_email"]).first.fill(username)
        page.locator(SELECTORS["login_password"]).first.fill(password)
        page.locator(SELECTORS["login_submit"]).first.click()
        try:
            page.wait_for_selector(SELECTORS["login_success_marker"], timeout=15000)
        except PlaywrightTimeoutError as exc:
            raise RuntimeError(
                "eurolots login did not reach a logged-in state — check "
                "credentials and SELECTORS['login_success_marker']"
            ) from exc
        logger.info("[eurolots] login OK")

    def fetch_listings(self, products: list[dict]) -> list[Listing]:
        page = self.page
        listings: list[Listing] = []

        for product in products:
            query = product.get("identifier") or product["product_name"]
            search_url = f"{BASE_URL}/search?q={query}"

            try:
                page.goto(search_url, wait_until="domcontentloaded")
                page.wait_for_selector(SELECTORS["search_result_link"], timeout=10000)
            except PlaywrightTimeoutError:
                logger.warning("[eurolots] no search results for %r", query)
                continue

            href = page.locator(SELECTORS["search_result_link"]).first.get_attribute("href")
            if not href:
                logger.warning("[eurolots] result link had no href for %r", query)
                continue
            product_url = href if href.startswith("http") else f"{BASE_URL}{href}"

            try:
                page.goto(product_url, wait_until="domcontentloaded")

                name = page.locator(SELECTORS["product_name"]).first.inner_text().strip()
                price_ex_vat = parse_price(
                    page.locator(SELECTORS["product_price_ex_vat"]).first.inner_text()
                )

                identifier = None
                sku_locator = page.locator(SELECTORS["product_sku"]).first
                if sku_locator.count():
                    identifier = sku_locator.inner_text().strip()

                price_inc_vat = None
                inc_locator = page.locator(SELECTORS["product_price_inc_vat"]).first
                if inc_locator.count():
                    price_inc_vat = parse_price(inc_locator.inner_text())

                listings.append(
                    Listing(
                        product_name=name,
                        price_ex_vat=price_ex_vat,
                        url=product_url,
                        identifier=identifier,
                        price_inc_vat=price_inc_vat,
                    )
                )
            except Exception:
                logger.exception("[eurolots] failed to scrape %s", product_url)
                continue

        return listings
