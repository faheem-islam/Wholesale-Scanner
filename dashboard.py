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

TABLE_COLUMNS = ["Product", "Wholesaler", "Target", "Ex VAT", "Inc VAT", "Stock", "Link"]
NUMERIC_COLUMNS = {"Target", "Ex VAT", "Inc VAT", "Stock"}

# Colour meaning is consistent across the whole page:
#   green = act on this (a price hit)
#   blue  = informational, no action needed
#   amber = worth a look (products.csv couldn't be matched to anything)
#   red   = something broke (a wholesaler failed to scrape)
HIT = "hit"
INFO = "info"
WARN = "warn"
ERROR = "error"


def render(matches: list[Match], unmatched: list[dict], failures: list[str]) -> None:
    SITE_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")

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
        stats=_stats_strip(
            tracked=len(matches) + len(unmatched),
            hits=len(hits),
            above=len(above_target),
            unmatched=len(unmatched),
            failures=len(failures),
        ),
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


def _stats_strip(*, tracked: int, hits: int, above: int, unmatched: int, failures: int) -> str:
    tiles = [
        ("Tracked products", tracked, ""),
        ("Price hits", hits, "stat-hit"),
        ("Above target", above, "stat-info"),
        ("Unmatched", unmatched, "stat-warn"),
        ("Failures", failures, "stat-error"),
    ]
    cells = "\n".join(
        f"""    <div class="stat">
      <span class="stat-value {cls}">{value}</span>
      <span class="stat-label">{html.escape(label)}</span>
    </div>"""
        for label, value, cls in tiles
    )
    return f'<div class="stats">\n{cells}\n  </div>'


def _card(variant: str, title: str, count: int, body_html: str) -> str:
    return f"""<section class="card">
  <header class="card-header card-header-{variant}">
    <h2>{html.escape(title)}</h2>
    <span class="count">{count}</span>
  </header>
  <div class="card-body">
    {body_html}
  </div>
</section>"""


def _matches_section(variant: str, title: str, rows: list[Match], *, empty_message: str) -> str:
    if not rows:
        return _card(variant, title, 0, f'<p class="empty">{html.escape(empty_message)}</p>')

    header_cells = "".join(
        f'<th class="{"num" if c in NUMERIC_COLUMNS else ""}">{c}</th>' for c in TABLE_COLUMNS
    )
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
    inc_vat = f"£{listing.price_inc_vat:,.2f}" if listing.price_inc_vat is not None else "—"
    stock = f"{listing.stock:,}" if listing.stock is not None else "—"
    link = (
        f'<a href="{html.escape(listing.url)}" target="_blank" rel="noopener">View &rarr;</a>'
        if listing.url
        else "—"
    )
    return f"""        <tr>
          <td>{html.escape(target['product_name'])}</td>
          <td class="muted">{html.escape(target['wholesaler'])}</td>
          <td class="num">£{target['target_price']:,.2f}</td>
          <td class="num">£{listing.price_ex_vat:,.2f}</td>
          <td class="num">{inc_vat}</td>
          <td class="num">{stock}</td>
          <td>{link}</td>
        </tr>"""


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
    --bg: #f6f7f9;
    --surface: #ffffff;
    --text: #14171f;
    --muted: #66707e;
    --border: #e2e5ea;
    --border-strong: #cbd0d8;

    --hit: #0f9d58;
    --info: #2563eb;
    --warn: #b7791f;
    --error: #d32f2f;
  }}

  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #0b0d11;
      --surface: #14171d;
      --text: #e6e8eb;
      --muted: #8b95a3;
      --border: #262b33;
      --border-strong: #333a44;

      --hit: #34d399;
      --info: #60a5fa;
      --warn: #fbbf24;
      --error: #f87171;
    }}
  }}

  * {{ box-sizing: border-box; }}

  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    -webkit-font-smoothing: antialiased;
    max-width: 1080px;
    margin: 0 auto;
    padding: 2.5rem 1.5rem 4rem;
    background: var(--bg);
    color: var(--text);
    line-height: 1.5;
    font-size: 14px;
  }}

  .masthead {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 0.5rem;
    border-bottom: 1px solid var(--border-strong);
    padding-bottom: 1.25rem;
    margin-bottom: 1.75rem;
  }}

  h1 {{
    margin: 0;
    font-size: 1.35rem;
    font-weight: 600;
    letter-spacing: -0.01em;
  }}

  .updated {{
    color: var(--muted);
    font-size: 0.8rem;
    font-variant-numeric: tabular-nums;
  }}

  .stats {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 1px;
    background: var(--border);
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
    margin-bottom: 2rem;
  }}

  .stat {{
    background: var(--surface);
    padding: 1rem 1.1rem;
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }}

  .stat-value {{
    font-size: 1.6rem;
    font-weight: 650;
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.02em;
  }}

  .stat-hit {{ color: var(--hit); }}
  .stat-info {{ color: var(--info); }}
  .stat-warn {{ color: var(--warn); }}
  .stat-error {{ color: var(--error); }}

  .stat-label {{
    font-size: 0.72rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }}

  .card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    margin-bottom: 1.25rem;
    overflow: hidden;
  }}

  .card-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.85rem 1.1rem;
    border-bottom: 1px solid var(--border);
    border-left: 3px solid var(--border-strong);
  }}

  .card-header-hit {{ border-left-color: var(--hit); }}
  .card-header-info {{ border-left-color: var(--info); }}
  .card-header-warn {{ border-left-color: var(--warn); }}
  .card-header-error {{ border-left-color: var(--error); }}

  .card-header h2 {{
    margin: 0;
    font-size: 0.85rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: var(--text);
  }}

  .count {{
    font-size: 0.78rem;
    color: var(--muted);
    font-variant-numeric: tabular-nums;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 0.05rem 0.55rem;
  }}

  .card-body {{ padding: 0; }}

  .empty {{
    color: var(--muted);
    margin: 0;
    padding: 1rem 1.1rem;
    font-size: 0.85rem;
  }}

  .table-wrap {{ overflow-x: auto; }}

  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
  }}

  th, td {{
    text-align: left;
    padding: 0.6rem 1.1rem;
    white-space: nowrap;
  }}

  th {{
    font-weight: 600;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: var(--muted);
    border-bottom: 1px solid var(--border);
  }}

  td {{
    border-bottom: 1px solid var(--border);
    font-variant-numeric: tabular-nums;
  }}

  tbody tr:last-child td {{ border-bottom: none; }}
  tbody tr:nth-child(even) {{ background: color-mix(in srgb, var(--border) 25%, transparent); }}

  td.muted {{ color: var(--muted); }}

  th.num, td.num {{ text-align: right; }}

  a {{ color: var(--info); text-decoration: none; font-weight: 500; }}
  a:hover {{ text-decoration: underline; }}

  ul {{
    margin: 0;
    padding: 0.75rem 1.1rem 0.9rem 2rem;
    font-size: 0.85rem;
  }}

  li {{ margin: 0.2rem 0; }}
</style>
</head>
<body>
  <div class="masthead">
    <h1>Wholesale Price Monitor</h1>
    <span class="updated">Last checked {timestamp}</span>
  </div>

  {stats}

  {hits_section}

  {above_target_section}

  {unmatched_section}

  {failure_section}
</body>
</html>
"""
