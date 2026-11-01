# Market data sources and hard access limits

| Source | Market | Data type | Current implementation |
|---|---|---|---|
| Google Trending Now RSS | GB, JP, KR | Rising general search topics; broad traffic buckets | Live collector; daily GitHub Actions schedule |
| Yahoo Japan Shopping keyword ranking | JP | Shopping keyword ranks, not unit sales | Credential-optional connector and parser, no app ID supplied |
| Naver DataLab / API Hub | KR | Shopping interest by keyword | Research target, not yet implemented |
| Rakuten / Yahoo Shopping products | JP | Products, availability, rankings | Research target, not yet implemented |
| Douyin / Chanmama | CN | Social-commerce trends and possible sales estimates | No authorised free bulk sales feed established |
| TikTok Shop / Amazon | UK | Affiliate commissions, eligibility, product offers | No linked accounts or API credentials |

All fields must retain source provenance and type. Do not compare a keyword rank
with a sales quantity. No product popularity, commission or market lead-lag is
verified by a general search RSS trend alone.

This initial prototype intentionally has NO paid AI API dependency.
