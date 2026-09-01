# Wholesale Price Monitor — Project Spec (for Claude Code)

## Objective
Build an automated system that checks product prices on 2 (eventually ~10) wholesaler websites twice daily, compares them against a target price list, and emails Faheem when any tracked product is found at or below its target price.

## Recommended tech stack
- **Language:** Python
- **Scraping:** Playwright — both current target sites render listings via JavaScript, so plain HTTP requests won't see the content
- **Scheduling:** GitHub Actions cron workflow (twice daily, free tier)
- **Notifications:** Email via a free-tier transactional email service (SMTP or a service like SendGrid/Mailgun) — avoid anything paid unless the free tier is genuinely insufficient
- **Config format:** CSV for the target product list, so it's editable without touching code

If a different tool is clearly better for a specific piece, propose it and explain why — priorities are: it actually works, then cost, then simplicity.

## Wholesalers (current)
1. **Eurolots.com** (https://www.eurolots.com)
   - Single wholesaler's own liquidation/returns catalog
   - Listings render via JavaScript — requires Playwright
   - Prices are visible on item pages
   - Faheem has an account; no 2FA enabled

2. **Merkandi.co.uk** (https://merkandi.co.uk)
   - B2B marketplace aggregating listings from many independent sellers — NOT a fixed catalog
   - Listings appear and disappear continuously
   - Tracking approach: keyword/product search across all sellers, not a fixed per-product page. Use reasonably specific search terms plus a price ceiling to cut down false positives
   - Also JS-rendered — requires Playwright
   - Faheem has an account; no 2FA enabled

Design for ~10 wholesalers eventually: each wholesaler should be its own self-contained adapter/module implementing a shared interface (returns a list of records like `{product_name, identifier, price_ex_vat, price_inc_vat (optional), url}`), so adding a new wholesaler later means writing one new adapter file, not modifying shared code.

## Login handling
- Both current wholesalers require an account to see full pricing/inventory (confirm exact requirements per site while building)
- No 2FA on either account — automated login is viable
- Log in once per run and reuse that session for the rest of the run's checks — don't log in repeatedly
- Credentials must NEVER be hardcoded or committed to the repo. Store them as GitHub Actions encrypted secrets and read them from environment variables at runtime. Suggested secret names: `EUROLOTS_USERNAME`, `EUROLOTS_PASSWORD`, `MERKANDI_USERNAME`, `MERKANDI_PASSWORD`
- Add a `.gitignore` that excludes any local `.env` file used for testing credentials locally

## Target product list
- Format: a CSV file (e.g. `products.csv`) with columns: `product_name, identifier, target_price, wholesaler`
- ~20 products expected; the actual list will be provided separately — build the system to read from this file rather than hardcoding products
- If the file doesn't exist yet, create a small example/template CSV with 2–3 placeholder rows so the system is testable immediately

## Price comparison rules
- Compare against the base (ex-VAT) price
- If a wholesaler's page also shows a VAT-inclusive price, include that in the alert too — informational only, not used in the comparison itself

## Matching logic
- Prefer exact SKU/identifier match
- Fall back to fuzzy name matching where a wholesaler doesn't expose a consistent SKU
- Log any target-list product that couldn't be matched to anything, so mismatches are visible rather than silent

## Notifications
- Channel: email only for this phase (WhatsApp is a later phase — see Out of scope)
- Each alert should include: product name, wholesaler, price found, target price, and a link to the listing if available
- Re-alert behaviour is undecided — ask before implementing (see Open questions)

## Scheduling
- GitHub Actions workflow, cron-triggered, twice daily
- Exact times are undecided — ask (see Open questions); if no preference is given, default to a sensible UK-daytime pair (e.g. 8am and 6pm UK time)

## Error handling
- If a wholesaler's site fails to load or its layout has changed so scraping fails, log the failure clearly rather than crashing the whole run — one wholesaler failing shouldn't block checks on the others
- Whether a failed scrape should trigger its own alert is undecided — ask (see Open questions)

## Budget constraint
Cheapest possible at every stage. Stay on free tiers until a paid step is clearly unavoidable (e.g. WhatsApp Business API later) — flag it before introducing anything with a cost.

## Explicitly out of scope for this phase
- WhatsApp notifications (later phase, once the email version works)
- Proxy / anti-bot infrastructure (only add if a specific wholesaler turns out to need it — don't build it preemptively)
- Wholesalers beyond the 2 listed above (architecture should support more later, but don't build placeholder adapters for wholesalers that don't exist yet)

## Open questions — ask Faheem before proceeding on these
1. What are the two exact daily check times (and time zone)?
2. Should a product that stays under target get a fresh alert every check, only once when it first drops, or a daily digest?
3. Should a failed scrape (site down / layout changed) trigger its own alert, or just get logged?
4. What email address should alerts go to, and is there a preferred sending service already, or should one be set up from scratch?

## Suggested first steps
1. Propose a file/folder structure and confirm before writing code
2. Build a working adapter for Eurolots first (single catalog, simpler) before tackling Merkandi's marketplace-search model
3. Get one full local run working end-to-end (scrape → match against the example CSV → print result) before wiring up email and GitHub Actions scheduling
