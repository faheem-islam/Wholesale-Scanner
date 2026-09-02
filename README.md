# Wholesale Price Monitor

Checks product prices on wholesaler websites twice daily, compares them
against a target price list, and emails an alert when a tracked product is
found at or below its target price. Built per `WHOLESALER_PRICE_MONITOR_BRIEF.md`.

## How it works

1. `main.py` reads `products.csv` and groups target products by wholesaler.
2. For each wholesaler, it launches a headless Playwright browser, logs in
   once (`adapters/<name>.py`'s `login()`), and reuses that session to check
   every target product for that wholesaler (`fetch_listings()`).
3. `matcher.py` matches scraped listings back to target products — exact
   identifier/SKU first, fuzzy name match as a fallback — and logs any
   target product that couldn't be matched to anything.
4. Any match at or below its target price becomes a hit; if there are any
   hits, `notifier.py` emails a single summary to `ALERT_EMAIL_TO` via SMTP.
5. A wholesaler that fails (site down, layout changed) is logged and
   skipped — it doesn't stop the other wholesalers, but it does make the
   run exit non-zero so it's visible in the GitHub Actions tab.
6. `dashboard.py` renders every checked product (not just hits) to
   `site/index.html`, which the workflow publishes to GitHub Pages —
   see "Dashboard" below.

## Dashboard

Every run publishes a results page to GitHub Pages — no separate hosting,
no login, just a URL: `https://faheem-islam.github.io/Wholesale-Scanner/`.
It shows every target product, the price found vs. target, VAT-inclusive
price where available, a link to the listing, and any unmatched products
or wholesaler failures from that run.

**One-time setup** (do this once, in the GitHub website): go to the
repo's **Settings → Pages**, and under "Build and deployment" set
**Source** to **GitHub Actions**. That's it — the workflow handles
everything else, including the first deploy on its next run.

## Project layout

```
adapters/
  base.py       shared WholesalerAdapter interface + Listing record + price parsing
  eurolots.py   Eurolots.com adapter (single catalog)
  merkandi.py   Merkandi.co.uk adapter (marketplace keyword search)
config.py       non-secret tunables (thresholds, price ceiling, default alert address)
currency.py     EUR -> GBP conversion (Frankfurter API) for non-GBP wholesalers
matcher.py      identifier/fuzzy-name matching against products.csv
notifier.py     SMTP email formatting + sending
dashboard.py    renders site/index.html, published to GitHub Pages
main.py         orchestrates: scrape -> match -> alert -> dashboard
products.csv    target product list (edit this to add/remove tracked products)
.github/workflows/price-check.yml   twice-daily GitHub Actions cron + Pages deploy
```

Adding an 11th wholesaler later means adding `adapters/<name>.py` that
implements `WholesalerAdapter` from `adapters/base.py`, plus one line each in
`main.py`'s `ADAPTERS` and `CREDENTIAL_ENV_VARS` dicts — no other file
should need to change.

## `products.csv` format

```
product_name,identifier,target_price,wholesaler
Example Product One,SKU-0001,9.99,eurolots
```

- `identifier` is the SKU/product code, if the wholesaler exposes one.
  Leave it blank to force fuzzy name matching (see the third example row).
- `wholesaler` must be `eurolots` or `merkandi` (matches the adapter names)
  — though `merkandi` is currently unused, see "Status: Merkandi paused"
  below.
- The three rows currently in the file are placeholders — replace them with
  the real ~20-product list.

## Setup

### Local

```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env   # fill in credentials + SMTP details
python main.py
```

### GitHub Actions

Add these as **repository secrets** (Settings → Secrets and variables →
Actions): `EUROLOTS_USERNAME`, `EUROLOTS_PASSWORD`, `MERKANDI_USERNAME`,
`MERKANDI_PASSWORD`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`,
`SMTP_PASSWORD`, `ALERT_EMAIL_TO`. The workflow at
`.github/workflows/price-check.yml` runs twice daily and can also be
triggered manually from the Actions tab (`workflow_dispatch`).

No paid services are used anywhere in this setup — SMTP works with a free
Gmail/Outlook account or any free-tier transactional provider, and GitHub
Actions' free tier easily covers two runs a day.

## Currency and VAT

- `products.csv`'s `target_price` is in **GBP**. Eurolots bills in **EUR**,
  so `adapters/eurolots.py` converts scraped EUR prices to GBP before
  returning them, using a live rate from `currency.py` (free, keyless
  Frankfurter API). Every adapter is expected to return GBP — see the
  `Listing` docstring in `adapters/base.py`.
- Eurolots only shows the ex-VAT price on its item pages; the inc-VAT
  figure is calculated in `adapters/eurolots.py` at a fixed **20%** (UK
  standard rate). If Eurolots' actual VAT treatment differs, update
  `VAT_RATE` there.

## Status: Merkandi paused

Merkandi's login sits behind a Cloudflare Turnstile CAPTCHA on every
attempt (not just after a failed one), which is specifically built to
detect automated/headless browsers — the kind GitHub Actions runs. That's
a real decision to make (reuse a manually-created session, pay for a
CAPTCHA-solving service, or skip Merkandi automation), not something to
route around silently, so it's on hold for now.

The system currently runs **Eurolots only** — `products.csv` has no
Merkandi rows, so `main.py` never touches `adapters/merkandi.py`. Nothing
else had to change: adapters are self-contained by design, so this is a
data change, not a code change. To bring Merkandi back once the login
question is settled:
1. Add its rows back to `products.csv` (`wholesaler` = `merkandi`).
2. Verify `adapters/merkandi.py`'s `SELECTORS` against the live site (see
   below — they're still unconfirmed guesses).
3. Add the `MERKANDI_USERNAME`/`MERKANDI_PASSWORD` secrets and implement
   whichever login approach gets decided on.

## Known limitations / before this is production-ready

- **Eurolots' adapter is confirmed against the real site** (via Playwright
  codegen) for: login fields, the logged-in marker, the search box/submit
  button, the item page URL pattern (`/en/item/<slug>`), the product
  title, the price text, and the SKU (read from a specs table row). Two
  things are still unconfirmed and should be sanity-checked on the first
  real run — see the comments at the top of `adapters/eurolots.py`:
  - the exact click path to open the login form (a popup can appear first)
  - the search *results* page's structure — the code picks the first link
    matching the confirmed `/en/item/` URL pattern, which should be
    resilient to markup changes, but hasn't been exercised against a real
    results page yet.
- **Merkandi's adapter is still unverified** — its `SELECTORS` dict is a
  best-effort guess, not confirmed against the real DOM (this environment
  had no network access to merkandi.co.uk while building it). Same
  process as Eurolots: `playwright codegen https://merkandi.co.uk` while
  logged in, then correct `SELECTORS` in `adapters/merkandi.py` — the
  logic around it shouldn't need to change.
- **`products.csv`** currently holds 3 placeholder rows; swap in the real list.

## Open questions from the brief (defaults assumed for now)

The brief flagged these as "ask before proceeding." Given no answer yet,
sensible defaults were chosen so the system is usable end-to-end — flag
if any should change:

1. **Exact check times/timezone** → confirmed as 8am and 8pm UK time. Cron
   is UTC and can't shift with UK clocks, so it drifts to 7am/7pm UK time
   during British Summer Time — see the comment in `price-check.yml`.
2. **Re-alert behaviour** → currently alerts on **every** run a product is
   at/under target (simplest, no extra state to manage). If you'd rather
   have "only once when it first drops" or a daily digest, that needs a
   small persisted state file (e.g. committed back to the repo, or a
   GitHub Actions cache) to remember what's already been alerted on.
3. **Failed-scrape alerting** → currently just logged, not emailed; the run
   does exit non-zero on failure so it shows red in the Actions tab. Can
   add a dedicated failure email if you'd rather be notified without
   checking Actions.
4. **Alert email address** → defaulted to `faheem_islam02@hotmail.com`
   (in `config.py`, overridable via the `ALERT_EMAIL_TO` env var/secret).
   Sending service defaults to plain SMTP (works with any provider, no
   signup cost) rather than a service like SendGrid/Mailgun.
