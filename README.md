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

## Project layout

```
adapters/
  base.py       shared WholesalerAdapter interface + Listing record + price parsing
  eurolots.py   Eurolots.com adapter (single catalog)
  merkandi.py   Merkandi.co.uk adapter (marketplace keyword search)
config.py       non-secret tunables (thresholds, price ceiling, default alert address)
matcher.py      identifier/fuzzy-name matching against products.csv
notifier.py     SMTP email formatting + sending
main.py         orchestrates: scrape -> match -> alert
products.csv    target product list (edit this to add/remove tracked products)
.github/workflows/price-check.yml   twice-daily GitHub Actions cron
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
- `wholesaler` must be `eurolots` or `merkandi` (matches the adapter names).
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

## Known limitations / before this is production-ready

- **Selectors are unverified.** This project was built without network
  access to eurolots.com or merkandi.co.uk, so the CSS selectors in
  `adapters/eurolots.py` and `adapters/merkandi.py` (the `SELECTORS` dicts
  at the top of each file) are best-effort guesses based on common
  e-commerce markup, not confirmed against the real DOM. Before the first
  real run: log into each site, run
  `playwright codegen https://www.eurolots.com` (and the same for
  Merkandi), and correct the selectors. The scraping logic around them
  shouldn't need to change.
- **Eurolots is assumed to have a `/search?q=` endpoint.** If it browses by
  category instead, `fetch_listings()` in `adapters/eurolots.py` will need
  a different lookup strategy per product.
- **`products.csv`** currently holds 3 placeholder rows; swap in the real list.

## Open questions from the brief (defaults assumed for now)

The brief flagged these as "ask before proceeding." Given no answer yet,
sensible defaults were chosen so the system is usable end-to-end — flag
if any should change:

1. **Exact check times/timezone** → defaulted to a UTC cron approximating
   8am/6pm UK time (drifts to 9am/7pm during British Summer Time — see the
   comment in `price-check.yml`).
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
