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

# Colour meaning is consistent across the whole page:
#   green  = act on this (a price hit)
#   blue   = informational, no action needed
#   amber  = worth a look (products.csv couldn't be matched to anything)
#   red    = something broke (a wholesaler failed to scrape)
HIT = "hit"
INFO = "info"
WARN = "warn"
ERROR = "error"


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
        hits_section=_matches_section(
            HIT,
            "Price hits",
            hits,
            empty_message="No products are at or under target right now.",
        ),
        above_target_section=_matches_section(
            INFO,
            "Above target",
            above_target,
            empty_message="Nothing currently above target.",
        ),
        unmatched_section=_list_section(
            WARN,
            "Unmatched products",
            [f"{p['product_name']} ({p['wholesaler']})" for p in unmatched],
        ),
        failure_section=_list_section(ERROR, "Wholesaler failures this run", failures),
    )
    (SITE_DIR / "index.html").write_text(page, encoding="utf-8")


def _is_hit(m: Match) -> bool:
    return m.listing.price_ex_vat <= m.target_product["target_price"]


def _card(variant: str, title: str, count: int, body_html: str) -> str:
    return f"""<section class="card card-{variant}">
  <h2><span class="dot dot-{variant}"></span>{html.escape(title)} <span class="count">({count})</span></h2>
  {body_html}
</section>"""


def _matches_section(variant: str, title: str, rows: list[Match], *, empty_message: str) -> str:
    if not rows:
        return _card(variant, title, 0, f'<p class="empty">{html.escape(empty_message)}</p>')

    header_cells = "".join(f'<th class="{_col_class(c)}">{c}</th>' for c in TABLE_COLUMNS)
    body_rows = "\n".join(_match_row(m) for m in rows)
    table = f"""<div class="table-wrap">
    <table>
      <thead><tr>{header_cells}</tr></thead>
      <tbody>
{body_rows}
      </tbody>
    </table>
  </div>"""
    return _card(variant, title, len(rows), table)


def _match_row(m: Match) -> str:
    target = m.target_product
    listing = m.listing
    inc_vat = f"£{listing.price_inc_vat:.2f}" if listing.price_inc_vat is not None else "—"
    link = (
        f'<a href="{html.escape(listing.url)}" target="_blank" rel="noopener">view</a>'
        if listing.url
        else "—"
    )
    return f"""        <tr>
          <td>{html.escape(target['product_name'])}</td>
          <td>{html.escape(target['wholesaler'])}</td>
          <td class="num">£{target['target_price']:.2f}</td>
          <td class="num">£{listing.price_ex_vat:.2f}</td>
          <td class="num">{inc_vat}</td>
          <td>{link}</td>
        </tr>"""


def _col_class(column: str) -> str:
    return "num" if column in ("Target", "Ex VAT", "Inc VAT") else ""


def _list_section(variant: str, title: str, items: list[str]) -> str:
    if not items:
        return ""
    list_items = "\n".join(f"    <li>{html.escape(item)}</li>" for item in items)
    return _card(variant, title, len(items), f"<ul>\n{list_items}\n  </ul>")


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Wholesale Price Monitor</title>
<style>
  :root {{
    color-scheme: light dark;
    --bg: #ffffff;
    --text: #1a1a1a;
    --muted: #6b7280;
    --border: rgba(0, 0, 0, 0.12);
    --row-border: rgba(0, 0, 0, 0.08);

    --hit-fg: #15803d;
    --hit-bg: #f0fdf4;
    --hit-border: #86efac;

    --info-fg: #1d4ed8;
    --info-bg: #eff6ff;
    --info-border: #93c5fd;

    --warn-fg: #b45309;
    --warn-bg: #fffbeb;
    --warn-border: #fcd34d;

    --error-fg: #b91c1c;
    --error-bg: #fef2f2;
    --error-border: #fca5a5;
  }}

  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #0f1115;
      --text: #e5e7eb;
      --muted: #9ca3af;
      --border: rgba(255, 255, 255, 0.14);
      --row-border: rgba(255, 255, 255, 0.08);

      --hit-fg: #4ade80;
      --hit-bg: rgba(34, 197, 94, 0.1);
      --hit-border: rgba(74, 222, 128, 0.35);

      --info-fg: #60a5fa;
      --info-bg: rgba(59, 130, 246, 0.1);
      --info-border: rgba(96, 165, 250, 0.35);

      --warn-fg: #fbbf24;
      --warn-bg: rgba(217, 119, 6, 0.12);
      --warn-border: rgba(251, 191, 36, 0.35);

      --error-fg: #f87171;
      --error-bg: rgba(220, 38, 38, 0.12);
      --error-border: rgba(248, 113, 113, 0.35);
    }}
  }}

  * {{ box-sizing: border-box; }}

  body {{
    font-family: -apple-system, system-ui, "Segoe UI", sans-serif;
    max-width: 960px;
    margin: 2rem auto;
    padding: 0 1rem;
    line-height: 1.5;
    background: var(--bg);
    color: var(--text);
  }}

  h1 {{
    margin: 0 0 0.25rem;
    font-size: 1.6rem;
  }}

  .updated {{
    color: var(--muted);
    margin: 0 0 2rem;
    font-size: 0.9rem;
  }}

  .card {{
    border: 1px solid var(--border);
    border-left: 4px solid var(--border);
    border-radius: 8px;
    padding: 1.1rem 1.25rem 1.25rem;
    margin-bottom: 1.25rem;
    background: var(--bg);
  }}

  .card-hit {{ border-left-color: var(--hit-border); background: var(--hit-bg); }}
  .card-info {{ border-left-color: var(--info-border); background: var(--info-bg); }}
  .card-warn {{ border-left-color: var(--warn-border); background: var(--warn-bg); }}
  .card-error {{ border-left-color: var(--error-border); background: var(--error-bg); }}

  h2 {{
    margin: 0 0 0.9rem;
    font-size: 1.05rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }}

  .dot {{
    width: 0.6rem;
    height: 0.6rem;
    border-radius: 50%;
    flex: none;
  }}

  .dot-hit {{ background: var(--hit-fg); }}
  .dot-info {{ background: var(--info-fg); }}
  .dot-warn {{ background: var(--warn-fg); }}
  .dot-error {{ background: var(--error-fg); }}

  .count {{
    color: var(--muted);
    font-weight: 400;
    font-size: 0.9rem;
  }}

  .empty {{
    color: var(--muted);
    margin: 0;
    font-size: 0.95rem;
  }}

  .table-wrap {{
    overflow-x: auto;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--bg);
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
    border-bottom: 1px solid var(--border);
  }}

  td {{
    border-bottom: 1px solid var(--row-border);
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
