"""Entry point: log into each wholesaler, scrape its target products, match
against products.csv, email Faheem when something is at or below target
price, and render the site/ dashboard published to GitHub Pages.

Usage:
    python main.py

Reads credentials and SMTP settings from environment variables — see
.env.example for the full list and README.md for setup. Locally these can
come from a `.env` file (loaded via python-dotenv, gitignored); in GitHub
Actions they're injected directly from repo secrets by
.github/workflows/price-check.yml.
"""
from __future__ import annotations

import csv
import logging
import os
import sys
from collections import defaultdict

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

import dashboard
from adapters.base import WholesalerAdapter
from adapters.eurolots import EurolotsAdapter
from adapters.merkandi import MerkandiAdapter
from config import PRODUCTS_CSV
from matcher import match_listings
from notifier import format_alert_email, send_alert_email

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# One entry per wholesaler adapter that currently exists. Adding a new
# wholesaler = write adapters/<new>.py implementing WholesalerAdapter, then
# add one line here and to CREDENTIAL_ENV_VARS below.
ADAPTERS: dict[str, type[WholesalerAdapter]] = {
    "eurolots": EurolotsAdapter,
    "merkandi": MerkandiAdapter,
}

CREDENTIAL_ENV_VARS: dict[str, tuple[str, str]] = {
    "eurolots": ("EUROLOTS_USERNAME", "EUROLOTS_PASSWORD"),
    "merkandi": ("MERKANDI_USERNAME", "MERKANDI_PASSWORD"),
}


def load_products(path=PRODUCTS_CSV) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        products = list(csv.DictReader(f))
    for row in products:
        row["target_price"] = float(row["target_price"])
        row["wholesaler"] = row["wholesaler"].strip().lower()
    return products


def main() -> int:
    products = load_products()
    products_by_wholesaler: dict[str, list[dict]] = defaultdict(list)
    for row in products:
        products_by_wholesaler[row["wholesaler"]].append(row)

    all_matches = []
    all_unmatched = []
    hits = []
    failures: list[str] = []

    # Headless by default (required in GitHub Actions); set HEADLESS=false
    # locally to watch the browser live while debugging an adapter.
    headless = os.environ.get("HEADLESS", "true").strip().lower() != "false"

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)

        for wholesaler_name, target_products in products_by_wholesaler.items():
            adapter_cls = ADAPTERS.get(wholesaler_name)
            if adapter_cls is None:
                msg = (
                    f"{wholesaler_name}: no adapter registered "
                    f"(skipping {len(target_products)} product(s) from products.csv)"
                )
                logger.warning(msg)
                failures.append(msg)
                continue

            user_env, pass_env = CREDENTIAL_ENV_VARS[wholesaler_name]
            username, password = os.environ.get(user_env), os.environ.get(pass_env)
            if not username or not password:
                msg = f"{wholesaler_name}: missing {user_env}/{pass_env} environment variable(s)"
                logger.error(msg)
                failures.append(msg)
                continue

            context = browser.new_context()
            page = context.new_page()
            adapter = adapter_cls(page)
            try:
                adapter.login(username, password)
                listings = adapter.fetch_listings(target_products)
                matches, unmatched = match_listings(target_products, listings)
                all_matches.extend(matches)
                all_unmatched.extend(unmatched)
                under_target = [
                    m for m in matches if m.listing.price_ex_vat <= m.target_product["target_price"]
                ]
                hits.extend(under_target)
                logger.info(
                    "%s: %d listing(s) scraped, %d matched, %d at/under target",
                    wholesaler_name, len(listings), len(matches), len(under_target),
                )
            except Exception as exc:
                logger.exception("%s: run failed", wholesaler_name)
                failures.append(f"{wholesaler_name}: {exc}")
            finally:
                context.close()

        browser.close()

    dashboard.render(all_matches, all_unmatched, failures)

    if hits:
        subject, body = format_alert_email(hits, failures)
        send_alert_email(subject, body)
        logger.info("Sent alert email for %d hit(s)", len(hits))
    else:
        logger.info("No price hits this run.")

    if failures:
        logger.warning("%d wholesaler(s) failed this run: %s", len(failures), "; ".join(failures))

    # Non-zero exit on any failure so a failed scrape is visible as a red
    # run in the GitHub Actions tab, even though it doesn't (yet) send its
    # own alert email — see README's "Open questions" section.
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
