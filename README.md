# Asymmetry Engine — Product Discovery v3

**Research hypothesis (not verified):** Discover inexpensive, demo-friendly physical consumer
goods in Asian marketplaces, and later test whether their UK marketing
potential is underexploited.

**Important correction:** The old Google general-trends dashboard was wrong.
The engine now publishes only retailer SKU observations that pass
[the product gate](docs/PRODUCT_GATE.md).
No search trends, football, news or inferred product demand may enter it.

## Website
https://kuke2013-hub.github.io/Asymmetry-Engine/

The dashboard loads only `reports/product-only.json`.
When no authenticated product APIs are available it shows zero
validated listings and explicit source-access failures. This is the
correct result; it is not a successful product research outcome.

## Current research connectors
- Yahoo Japan High Rating Trend Ranking (actual retailer SKU).
- Rakuten Ichiba Item Search, 2026-07-01 (actual retailer SKU).
- South Korea Naver Shopping Insight is **contextual keyword interest**,
  not a product listing source; no Korean SKU feed is connected.
- China, UK product matching and affiliate commissions are not connected.

## How the code is verified
- `python -m unittest discover -s tests -v`
- `python -m engine.product_only --output reports/product-only.json`

The published JSON is generated from real source responses only;
offline fixtures are explicitly marked as synthetic and cannot be
promoted to the dashboard.

## Credentials and licensing
Yahoo requires `YAHOO_JP_APP_ID`.
Rakuten requires `RAKUTEN_APP_ID` and `RAKUTEN_ACCESS_KEY`.
These are source-issued credentials; none can be manufactured by code.
Product APIs have commercial usage and display restrictions. In
particular, Rakuten content may not be repurposed for another affiliate
network without permission. See the full [data policy](docs/PRODUCT_GATE.md).

## This isn't yet a profitable product finder
No real retailer product collection is established without credentials.
No UK product matches, sales counts or proven market lead-time exist.
We intentionally do not show a product "opportunity score" yet.

## Third-party audit findings (1 November 2026)

- Both official API adapters currently have **no authenticated live responses**. Only their parsing logic has been tested using synthetic test data.
- The Yahoo adapter now scopes item codes to stores to avoid accidental ID collisions.
- The Rakuten adapter now uses the documented `imageFlag` argument (rather than an unrecognised image filter) and formatVersion=2.
- A successful GitHub Action means the software check ran. The Actions job summary separately states how many retailer requests really returned product data.
- Product category labels are **search/watchlist themes**, not verified item classifications.
- GitHub publishes only the most recent product-only status file. **A durable historical product database is not operational**, so no growth rate or cross-market lead time can presently be measured.
- The website is additionally audited by a live Chrome desktop/mobile rendering workflow; an already-open browser tab can still display a stale earlier version until reloaded.
