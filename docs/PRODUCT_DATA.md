# Asian commerce data pipeline (November 2026)

## Japan
Official Yahoo Shopping High Rating Trend Ranking API:
https://developer.yahoo.co.jp/webapi/shopping/shopping/v1/highRatingTrendRanking.html
Requires a registered Yahoo Shopping client ID. Results include distinct
product identifiers, Japanese names, price in JPY, links, rating and
a blended rank. A rank is not a sales quantity.

## South Korea
Official NAVER API HUB Shopping Insight keyword endpoint:
https://api.ncloud-docs.com/docs/en/naver-api-hub-shopping-insight-keywords
Requires a NAVER API HUB client ID and secret. Returns relative
shopping-keyword clicks in a specified category and time window.
It does not return individual product listings, unit sales or conversion.

## Access and storage
No credentials are present in the codebase. A connection with missing
credentials reports skipped rather than success. The GitHub repository is
public, so the pipeline must not publish proprietary merchant data or
secret keys. Raw authenticated data remains local in SQLite until
retention and redistribution rights are confirmed.

## Multilingual classification
The initial zero-shot model is an open-weight multilingual embedding
model, not a custom fine-tuned LLM. Classifications of genuine market
observations require manual review. There is no verified market-lead
time or affiliate-revenue forecast yet.
