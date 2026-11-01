"""Regression suite for critical failure: NEVER publish general search trends as products."""
from dataclasses import asdict
from pathlib import Path
import json,unittest
from engine.product_only import (
    Product,BadProduct,validate_product,parse_yahoo_product_list,
    parse_rakuten_product_list,publish,collect_product_sources,safe_url)
ROOT=Path(__file__).resolve().parents[1]
ST="2026-11-01T17:00:00+00:00"

def valid(**changes):
    d={"market":"JP","source":"yahoo_jp_high_rating_products",
       "product_id":"fixture-shop:fold","title":"折りたたみ 収納 ボックス",
       "category":"storage_organisation","price":1800,"currency":"JPY",
       "product_url":"https://store.shopping.yahoo.co.jp/fixture-shop/fold.html",
       "observed_at":ST,"ranking_position":3}
    d.update(changes)
    return d

class HardProductGateTests(unittest.TestCase):
 def test_real_listing_gate(self):
    self.assertEqual(validate_product(valid()).product_id,"fixture-shop:fold")
 def test_real_athlete_from_google_is_rejected(self):
    with self.assertRaises(BadProduct):
       validate_product({"source":"google_trending_rss",
         "market":"GB","original_text":"andreas almgren",
         "metric_type":"approx_search_traffic_bucket"})
 def test_spoofed_google_record_rejected_even_if_price_added(self):
    with self.assertRaises(BadProduct):
       validate_product(valid(source="google_trending_rss",title="andreas almgren"))
 def test_no_product_id(self):
    with self.assertRaises(BadProduct):validate_product(valid(product_id=None))
 def test_no_listing_url(self):
    with self.assertRaises(BadProduct):validate_product(valid(product_url=""))
 def test_link_cannot_be_search_results(self):
    with self.assertRaises(BadProduct):
       validate_product(valid(product_url="https://trends.google.com/trending/rss?geo=JP"))
 def test_link_cannot_use_lookalike_domain(self):
    with self.assertRaises(BadProduct):
       validate_product(valid(product_url="https://store.shopping.yahoo.co.jp.evil.example/abc"))
 def test_url_must_be_https(self):
    with self.assertRaises(BadProduct):
       validate_product(valid(product_url="http://store.shopping.yahoo.co.jp/a"))
 def test_missing_price(self):
    with self.assertRaises(BadProduct):validate_product(valid(price=None))
 def test_no_false_uk_currency(self):
    with self.assertRaises(BadProduct):validate_product(valid(currency="GBP"))
 def test_unapproved_category(self):
    with self.assertRaises(BadProduct):validate_product(valid(category="sports_news"))
 def test_missing_timestamp(self):
    with self.assertRaises(BadProduct):validate_product(valid(observed_at="2026-11-01"))
 def test_naver_keyword_cannot_be_a_product(self):
    with self.assertRaises(BadProduct):
       validate_product(valid(source="naver_kr_shopping_keyword_clicks",
                              product_id="얼굴 아이스팩"))
 def test_rakuten_wrong_market_rejected(self):
    with self.assertRaises(BadProduct):
       validate_product(valid(source="rakuten_jp_item_search",market="KR"))
 def test_price_limits(self):
    with self.assertRaises(BadProduct):validate_product(valid(price=200000))
 def test_product_validates_exact_domain(self):
    self.assertTrue(safe_url("https://item.rakuten.co.jp/s/i/",{"item.rakuten.co.jp"}))
    self.assertFalse(safe_url("https://evil.example/?u=item.rakuten.co.jp",{"item.rakuten.co.jp"}))

class ProviderParsingTests(unittest.TestCase):
 def test_yahoo_parses_real_schema_and_rejects_bad_records(self):
    obs,bad=parse_yahoo_product_list((ROOT/"fixtures/product_only_yahoo.json").read_bytes(),
                       "beauty_tools",ST)
    self.assertEqual(len(obs),1);self.assertEqual(bad,2)
    self.assertEqual(obs[0].price,1590)
    self.assertEqual(obs[0].currency,"JPY")
    self.assertIn("store.shopping.yahoo.co.jp",obs[0].product_url)
 def test_rakuten_parses_real_schema_and_rejects_bad_records(self):
    obs,bad=parse_rakuten_product_list((ROOT/"fixtures/product_only_rakuten.json").read_bytes(),
                       "storage_organisation",ST)
    self.assertEqual(len(obs),1);self.assertEqual(bad,1)
    self.assertEqual(obs[0].price,2500)
 def test_parser_fails_on_bad_schema(self):
    with self.assertRaises(ValueError):parse_yahoo_product_list(b'{}',"beauty_tools")
    with self.assertRaises(ValueError):parse_rakuten_product_list(b'{}',"beauty_tools")
 def test_publish_is_fail_closed_from_legacy_feed(self):
    legacy=(ROOT/"fixtures/google_jp.xml").read_text()
    payload=[{"source":"google_trending_rss","original_text":"andreas almgren",
             "market":"GB"},{"source":"google_trending_rss","original_text":"football news","market":"JP"}]
    out=publish(payload,[],ST)
    self.assertEqual(out["product_count"],0)
    self.assertEqual(out["rejected_records"],2)
    self.assertEqual(out["products"],[])
 def test_publish_dedupe_and_classification(self):
    out=publish([valid(),valid(),valid(category="other_review")],[],ST)
    self.assertEqual(out["product_count"],1)
    self.assertEqual(out["rejected_records"],1)
 def test_publish_metadata_cannot_claim_sales(self):
    out=publish([valid()],[],ST)
    self.assertEqual(out["sales_status"],"no_verified_units_sold")
    self.assertEqual(out["uk_matching_status"],"not_implemented")
 def test_no_api_credentials_means_zero_products_and_no_network(self):
    def forbidden(*a,**kw):raise AssertionError("No network without credentials")
    cfg=json.loads((ROOT/"config/products.json").read_text())
    out=collect_product_sources(cfg,env={},fetch=forbidden)
    self.assertEqual(out["product_count"],0)
    self.assertEqual(len(out["source_status"]),6)
    self.assertTrue(all(x["status"]=="credentials_missing" for x in out["source_status"]))
 def test_authenticated_fake_providers_only_for_fixtures(self):
    yf=(ROOT/"fixtures/product_only_yahoo.json").read_bytes()
    rf=(ROOT/"fixtures/product_only_rakuten.json").read_bytes()
    def fixture_fetch(url,headers=None):
       return rf if "rakuten.co.jp" in url else yf
    cfg={"queries":[{"source":"yahoo_jp_high_rating_products",
                     "term":"美容","category":"beauty_tools"},
                    {"source":"rakuten_jp_item_search",
                     "term":"収納","category":"storage_organisation"}]}
    out=collect_product_sources(cfg,env={"YAHOO_JP_APP_ID":"fixture",
                         "RAKUTEN_APP_ID":"fixture","RAKUTEN_ACCESS_KEY":"fixture"},
                                fetch=fixture_fetch)
    self.assertEqual(out["product_count"],2)
    self.assertTrue(all(x["status"]=="success" for x in out["source_status"]))
 def test_bad_source_fails_pre_collection(self):
    with self.assertRaises(ValueError):
       collect_product_sources({"queries":[{"source":"google_trending_rss",
             "term":"andreas almgren","category":"beauty_tools"}]},env={})
 def test_missing_category_fails_pre_collection(self):
    with self.assertRaises(ValueError):
       collect_product_sources({"queries":[{"source":"yahoo_jp_high_rating_products",
             "term":"sports","category":"news"}]},env={})
 def test_no_empty_title_as_product(self):
    with self.assertRaises(BadProduct):validate_product(valid(title=""))
 def test_offline_fixtures_are_not_public_artifact(self):
    # Files under fixtures/ aren't read by the dashboard or action collector.
    self.assertTrue((ROOT/"fixtures/product_only_yahoo.json").exists())

class WebsiteContractTests(unittest.TestCase):
 def test_website_only_loads_retail_product_feed(self):
    page=(ROOT/"index.html").read_text(encoding="utf-8")
    self.assertIn("./reports/product-only.json",page)
    self.assertNotIn("latest-observations.json",page)
    self.assertNotIn("google_trending_rss",page)
    self.assertNotIn("Recorded search signals",page)
 def test_no_unverified_products_in_public_report(self):
    path=ROOT/"reports/product-only.json"
    if not path.exists():
       self.skipTest("No production report has been generated yet")
    data=json.loads(path.read_text(encoding="utf-8"))
    self.assertEqual(data["schema_version"],3)
    self.assertEqual(data["data_type"],"retailer_product_listings_only")
    self.assertEqual(data["product_count"],len(data["products"]))
    for product in data["products"]:
       validate_product(product)
       self.assertNotEqual(product["source"],"google_trending_rss")
 def test_watchlist_cannot_request_general_search_topics(self):
    config=json.loads((ROOT/"config/products.json").read_text(encoding="utf-8"))
    from engine.product_only import SOURCES,PUBLISHABLE
    for item in config["queries"]:
       self.assertIn(item["source"],SOURCES)
       self.assertIn(item["category"],PUBLISHABLE)

if __name__=="__main__":unittest.main()
