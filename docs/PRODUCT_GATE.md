# Product-only evidence policy — v3

## The bug this redesign fixes
On 1 November 2026, the previous landing page rendered Google Trending Now
topics including Andreas Almgren, football matches and public affairs.
Those were collected correctly as **search queries** but had no logical
connection to the physical-goods / affiliate discovery project.

The prior design was invalid for the business goal. Its successful tests
verified the parser, not product relevance.

## Non-negotiable product gate
A public product candidate must have ALL these fields:

- Origin from an explicitly approved **retailer product API**, not general
  trends, Naver shopping click ratios, social-media views or inferred text.
- Actual retailer product ID and physical product listing URL on the
  source provider's canonical domain.
- Physical-goods watchlist category, name and positive local-currency price.
- Timezone-aware observation timestamp.
- A non-synthetic origin. Test fixtures are always kept outside the
  published data path.

These conditions are enforced in engine/product_only.py and a second
time by the browser before product records are displayed.
The source allowlist is not user-editable via watchlist JSON.

## Source roles
- **Yahoo Japan highRatingTrendRanking:** retailer SKU + blended rank,
  price and optional reviews. Rank is NOT purchase count.
  https://developer.yahoo.co.jp/webapi/shopping/shopping/v1/highRatingTrendRanking.html
- **Rakuten Ichiba Item Search 2026-07-01:** retailer SKU + listed price
  and optional reviews. Search order is NOT evidence of rapid demand
  growth. API requires application ID and access key.
  https://webservice.rakuten.co.jp/index.php/documentation/ichiba-item-search
- **Naver Shopping Insight:** Korean relative shopping click interest;
  it does NOT produce a verified retail SKU, so it is not an entry point
  into the public product catalogue.
  https://api.ncloud-docs.com/docs/en/naver-api-hub-overview
- **Google Trends:** the old RSS feed is retired from scheduled
  commercial collection. Historical records are not product data.
- **China / UK:** no approved live SKU provider is connected.
  Do not invent coverage.

## Restrictions and uncertainty
- Rakuten Web Services impose restrictions on use of product information,
  affiliate programmes and attribution. Display and reuse must comply
  with provider terms; gathering data for a separate competing affiliate
  programme may be prohibited without permission.
  https://webservice.rakuten.co.jp/guide/rule
  https://webservice.rakuten.co.jp/guide/credit
- Provider API credentials are not present. If missing, the collector
  records credentials_missing, and **returns zero products**.
- No source currently verifies UK checkout, UK price, commissions,
  actual unit sales or China/Japan/Korea-to-UK lead times.
- Listing presence is NOT a "commercial opportunity".
  Product categorisation, authenticity, novelty, UK saturation, legality,
  shipping and affiliate eligibility are separate review gates.

## Release checklist
All of the following must pass before a deploy can be called good:
1. Existing non-product RSS observations are rejected (regression).
2. A fabricated non-retailer link fails strict source-domain validation.
3. Missing source credentials cause a visible empty state.
4. Real-shaped official API fixtures produce only valid product cards.
5. Synthetic fixtures are not published as live results.
6. Public site never counts search queries as products.
7. Production browser fetch uses reports/product-only.json only.

Any unsatisfied gate means **no product claim**, not a plausible guess.
