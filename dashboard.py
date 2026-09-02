"""Renders a static HTML dashboard (site/index.html) summarizing the most
recent run, published to GitHub Pages by
.github/workflows/price-check.yml. Deliberately dependency-free (plain
string templating, no Jinja) since this is the only place in the project
that needs HTML output.
"""
from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path

from matcher import Match

SITE_DIR = Path(__file__).resolve().parent / "site"


def render(matches: list[Match], unmatched: list[dict], failures: list[str]) -> None:
    SITE_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    ordered = sorted(matches, key=_sort_key)
    rows = "\n".join(_match_row(m) for m in ordered)
    if not rows:
        rows = '<tr><td colspan="7">No products matched this run.</td></tr>'

    unmatched_items = "\n".join(
        f"<li>{html.escape(p['product_name'])} ({html.escape(p['wholesaler'])})</li>"
        for p in unmatched
    )
    failure_items = "\n".join(f"<li>{html.escape(f)}</li>" for f in failures)

    page = TEMPLATE.format(
        timestamp=timestamp,
        rows=rows,
        unmatched_section=_optional_section("Unmatched products", unmatched_items),
        failure_section=_optional_section("Wholesaler failures this run", failure_items),
    )
    (SITE_DIR / "index.html").write_text(page, encoding="utf-8")


def _sort_key(m: Match) -> tuple[bool, str]:
    hit = m.listing.price_ex_vat <= m.target_product["target_price"]
    return (not hit, m.target_product["product_name"])


def _match_row(m: Match) -> str:
    target = m.target_product
    listing = m.listing
    hit = listing.price_ex_vat <= target["target_price"]
    status = (
        '<span class="badge hit">AT/UNDER TARGET</span>'
        if hit
        else '<span class="badge">above target</span>'
    )
    inc_vat = f"£{listing.price_inc_vat:.2f}" if listing.price_inc_vat is not None else "—"
    link = (
        f'<a href="{html.escape(listing.url)}" target="_blank" rel="noopener">view</a>'
        if listing.url
        else "—"
    )
    return f"""    <tr class="{'hit' if hit else ''}">
      <td>{html.escape(target['product_name'])}</td>
      <td>{html.escape(target['wholesaler'])}</td>
      <td>£{target['target_price']:.2f}</td>
      <td>£{listing.price_ex_vat:.2f}</td>
      <td>{inc_vat}</td>
      <td>{status}</td>
      <td>{link}</td>
    </tr>"""


def _optional_section(title: str, items_html: str) -> str:
    if not items_html:
        return ""
    return f"<h2>{html.escape(title)}</h2>\n<ul>\n{items_html}\n</ul>"


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Wholesale Price Monitor</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{
    font-family: -apple-system, system-ui, "Segoe UI", sans-serif;
    max-width: 960px; margin: 2rem auto; padding: 0 1rem;
  }}
  h1 {{ margin-bottom: 0.25rem; }}
  .updated {{ color: #888; margin-bottom: 1.5rem; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid rgba(128,128,128,0.3); }}
  tr.hit {{ background: rgba(34, 197, 94, 0.15); }}
  .badge {{
    display: inline-block; padding: 0.15rem 0.6rem; border-radius: 999px;
    font-size: 0.75rem; background: rgba(128,128,128,0.2);
  }}
  .badge.hit {{ background: #22c55e; color: #063; font-weight: 600; }}
  ul {{ padding-left: 1.25rem; }}
  h2 {{ margin-top: 2rem; font-size: 1.1rem; }}
</style>
</head>
<body>
  <h1>Wholesale Price Monitor</h1>
  <p class="updated">Last checked: {timestamp}</p>
  <table>
    <thead>
      <tr>
        <th>Product</th><th>Wholesaler</th><th>Target</th>
        <th>Ex VAT</th><th>Inc VAT</th><th>Status</th><th>Link</th>
      </tr>
    </thead>
    <tbody>
{rows}
    </tbody>
  </table>
  {unmatched_section}
  {failure_section}
</body>
</html>
"""
