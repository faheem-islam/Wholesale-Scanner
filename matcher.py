"""Match scraped wholesaler listings against the target product list.

Match order per target product:
  1. exact identifier/SKU match (case-insensitive)
  2. fuzzy name match (stdlib difflib), only above FUZZY_MATCH_THRESHOLD

Anything in the target list that matches nothing is logged so mismatches
are visible instead of silent, per the spec.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from difflib import SequenceMatcher

from adapters.base import Listing
from config import FUZZY_MATCH_THRESHOLD

logger = logging.getLogger(__name__)


@dataclass
class Match:
    target_product: dict
    listing: Listing
    match_type: str  # "identifier" or "fuzzy_name"
    score: float


def _name_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.strip().lower(), b.strip().lower()).ratio() * 100


def match_listings(target_products: list[dict], listings: list[Listing]) -> list[Match]:
    """Match each target product (already filtered to one wholesaler) against
    that wholesaler's scraped listings."""
    matches: list[Match] = []

    for target in target_products:
        target_id = (target.get("identifier") or "").strip().lower()
        match: Match | None = None

        if target_id:
            for listing in listings:
                if listing.identifier and listing.identifier.strip().lower() == target_id:
                    match = Match(target, listing, "identifier", 100.0)
                    break

        if match is None:
            best_score = 0.0
            best_listing: Listing | None = None
            for listing in listings:
                score = _name_similarity(target["product_name"], listing.product_name)
                if score > best_score:
                    best_score = score
                    best_listing = listing
            if best_listing is not None and best_score >= FUZZY_MATCH_THRESHOLD:
                match = Match(target, best_listing, "fuzzy_name", best_score)

        if match is not None:
            matches.append(match)
        else:
            logger.warning(
                "No match found for target product %r (identifier=%s, wholesaler=%s)",
                target["product_name"],
                target.get("identifier") or "none",
                target.get("wholesaler"),
            )

    return matches
