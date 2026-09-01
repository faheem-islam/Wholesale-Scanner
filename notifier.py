"""Email notifications via plain SMTP — works with Gmail, Office 365, or any
other provider's SMTP, so no paid signup is required (see .env.example for
provider examples).
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.mime.text import MIMEText

from config import ALERT_EMAIL_TO
from matcher import Match

logger = logging.getLogger(__name__)


def format_alert_email(hits: list[Match], failures: list[str]) -> tuple[str, str]:
    subject = f"Wholesale Price Alert: {len(hits)} product(s) at/under target"

    lines = [f"{len(hits)} product(s) are at or below their target price:", ""]
    for m in hits:
        target = m.target_product
        listing = m.listing
        lines.append(f"- {target['product_name']} ({target['wholesaler']})")
        lines.append(f"    Target price:  £{target['target_price']:.2f}")
        price_line = f"    Found price:   £{listing.price_ex_vat:.2f} ex VAT"
        if listing.price_inc_vat is not None:
            price_line += f" / £{listing.price_inc_vat:.2f} inc VAT"
        lines.append(price_line)
        lines.append(f"    Matched via:   {m.match_type} ({m.score:.0f}% confidence)")
        lines.append(f"    Link:          {listing.url}")
        lines.append("")

    if failures:
        lines.append(f"{len(failures)} wholesaler(s) failed to scrape this run:")
        for failure in failures:
            lines.append(f"- {failure}")
        lines.append("")

    return subject, "\n".join(lines)


def send_alert_email(subject: str, body: str) -> None:
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    username = os.environ["SMTP_USERNAME"]
    password = os.environ["SMTP_PASSWORD"]

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = username
    msg["To"] = ALERT_EMAIL_TO

    with smtplib.SMTP(host, port) as server:
        server.starttls()
        server.login(username, password)
        server.sendmail(username, [ALERT_EMAIL_TO], msg.as_string())

    logger.info("Alert email sent to %s", ALERT_EMAIL_TO)
