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

TABLE_COLUMNS = ["Product", "Wholesaler", "Target", "Ex VAT", "Inc VAT", "Link"]


def render(matches: list[Match], unmatched: list[dict], failures: list[str]) -> None:
    SITE_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    hits = sorted(
        (m for m in matches if _is_hit(m)),
        key=lambda m: m.target_product["product_name"],
    )
    above_target = sorted(
        (m for m in matches if not _is_hit(m)),
        key=lambda m: m.target_product["product_name"],
    )

    page = TEMPLATE.format(
        timestamp=timestamp,
        hit_count=len(hits),
        hits_section=_matches_section(
            "Price hits", hits, empty_message="No products are at or under target right now."
        ),
        above_target_section=_matches_section(
            "Above target", above_target, empty_message="Nothing currently above target."
        ),
        unmatched_section=_list_section(
            "Unmatched products",
            [f"{p['product_name']} ({p['wholesaler']})" for p in unmatched],
        ),
        failure_section=_list_section("Wholesaler failures this run", failures),
    )
    (SITE_DIR / "index.html").write_text(page, encoding="utf-8")


def _is_hit(m: Match) -> bool:
    return m.listing.price_ex_vat <= m.target_product["target_price"]


def _matches_section(title: str, rows: list[Match], *, empty_message: str) -> str:
    heading = f"<h2>{html.escape(title)} <span class=\"count\">({len(rows)})</span></h2>"
    if not rows:
        return f'{heading}\n<p class="empty">{html.escape(empty_message)}</p>'

    header_cells = "".join(
        f'<th class="{_col_class(c)}">{c}</th>' for c in TABLE_COLUMNS
    )
    body_rows = "\n".join(_match_row(m) for m in rows)
    return f"""{heading}
<div class="table-wrap">
  <table>
    <thead><tr>{header_cells}</tr></thead>
    <tbody>
{body_rows}
    </tbody>
  </table>
</div>"""


def _match_row(m: Match) -> str:
    target = m.target_product
    listing = m.listing
    inc_vat = f"£{listing.price_inc_vat:.2f}" if listing.price_inc_vat is not None else "—"
    link = (
        f'<a href="{html.escape(listing.url)}" target="_blank" rel="noopener">view</a>'
        if listing.url
        else "—"
    )
    return f"""      <tr>
        <td>{html.escape(target['product_name'])}</td>
        <td>{html.escape(target['wholesaler'])}</td>
        <td class="num">£{target['target_price']:.2f}</td>
        <td class="num">£{listing.price_ex_vat:.2f}</td>
        <td class="num">{inc_vat}</td>
        <td>{link}</td>
      </tr>"""


def _col_class(column: str) -> str:
    return "num" if column in ("Target", "Ex VAT", "Inc VAT") else ""


def _list_section(title: str, items: list[str]) -> str:
    if not items:
        return ""
    list_items = "\n".join(f"      <li>{html.escape(item)}</li>" for item in items)
    return f"""<h2>{html.escape(title)} <span class="count">({len(items)})</span></h2>
<ul>
{list_items}
</ul>"""


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Wholesale Price Monitor</title>
<style>
  :root {{ color-scheme: light dark; }}

  * {{ box-sizing: border-box; }}

  body {{
    font-family: -apple-system, system-ui, "Segoe UI", sans-serif;
    max-width: 960px;
    margin: 2rem auto;
    padding: 0 1rem;
    line-height: 1.5;
  }}

  h1 {{
    margin: 0 0 0.25rem;
    font-size: 1.6rem;
  }}

  .updated {{
    color: #888;
    margin: 0 0 2rem;
    font-size: 0.9rem;
  }}

  h2 {{
    margin: 2.5rem 0 0.75rem;
    font-size: 1.15rem;
    display: flex;
    align-items: baseline;
    gap: 0.4rem;
  }}

  h2:first-of-type {{ margin-top: 0; }}

  .count {{
    color: #888;
    font-weight: 400;
    font-size: 0.9rem;
  }}

  .empty {{
    color: #888;
    margin: 0;
    font-size: 0.95rem;
  }}

  .table-wrap {{
    overflow-x: auto;
    border: 1px solid rgba(128, 128, 128, 0.25);
    border-radius: 8px;
  }}

  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.95rem;
  }}

  th, td {{
    text-align: left;
    padding: 0.6rem 0.85rem;
    white-space: nowrap;
  }}

  th {{
    font-weight: 600;
    border-bottom: 1px solid rgba(128, 128, 128, 0.3);
  }}

  td {{
    border-bottom: 1px solid rgba(128, 128, 128, 0.15);
  }}

  tbody tr:last-child td {{ border-bottom: none; }}

  th.num, td.num {{ text-align: right; }}

  ul {{
    margin: 0;
    padding-left: 1.25rem;
  }}

  li {{ margin: 0.2rem 0; }}
</style>
</head>
<body>
  <h1>Wholesale Price Monitor</h1>
  <p class="updated">Last checked: {timestamp}</p>

  {hits_section}

  {above_target_section}

  {unmatched_section}

  {failure_section}
</body>
</html>
"""
