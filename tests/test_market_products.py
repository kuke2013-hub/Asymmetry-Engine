import json,sqlite3,unittest
from pathlib import Path
from datetime import date
from engine.market_products import (setup,parse_yahoo,parse_naver,save_yahoo,save_naver,
                                     collect)
from engine.multilingual import LABELS,classify_batch

ROOT=Path(__file__).resolve().parents[1]
class MarketProductTests(unittest.TestCase):
 def setUp(self):
    self.db=sqlite3.connect(":memory:");setup(self.db)
    self.jp=(ROOT/"fixtures/yahoo_products.json").read_bytes()
    self.kr=(ROOT/"fixtures/naver_keywords.json").read_bytes()
 def tearDown(self):self.db.close()
 def test_real_product_fields_but_synthetic_data(self):
    a=parse_yahoo(self.jp,captured="2026-11-01T12:00:00Z")
    self.assertEqual(len(a),2)
    self.assertEqual(a[0][3],"折りたたみ収納ボックス")
    self.assertEqual(a[0][5],1990)
    self.assertIn("NOT units sold",a[0][-1])
 def test_yahoo_store_deduplicates(self):
    a=parse_yahoo(self.jp)
    save_yahoo(self.db,a);save_yahoo(self.db,a)
    self.assertEqual(self.db.execute("select count(*) from product_snapshots").fetchone()[0],2)
 def test_naver_click_index_not_sales(self):
    a=parse_naver(self.kr,"50000002","beauty")
    self.assertEqual(len(a),3)
    self.assertEqual(a[1][5],100.0)
    save_naver(self.db,a);save_naver(self.db,a)
    self.assertEqual(self.db.execute("select count(*) from korean_keyword_interest").fetchone()[0],3)
 def test_naver_invalid_ratio(self):
    bad=self.kr.decode().replace('"ratio": 100','"ratio": 101')
    with self.assertRaises(ValueError):parse_naver(bad.encode(),"50000002","beauty")
 def test_no_key_no_network_and_skipped(self):
    cfg=json.loads((ROOT/"config/watchlist.json").read_text())
    def fail(*a,**kw):raise AssertionError("No network without credentials")
    out=collect(self.db,cfg,env={},fetch=fail,today=date(2026,11,1))
    self.assertEqual(len(out),5)
    self.assertTrue(all(r["status"]=="skipped" for r in out))
 def test_fake_auth_requests_use_official_schema(self):
    cfg={"yahoo_queries":["美容 グッズ"],"naver":[{"name":"beauty",
        "category_id":"50000002","keywords":["두피 마사지기"]}]}
    calls=[]
    def fake(url,**kwargs):
       calls.append((url,kwargs))
       return (self.kr if "naverapihub" in url else self.jp),200
    env={"YAHOO_JP_APP_ID":"fake-key","NAVER_API_HUB_CLIENT_ID":"fake-id",
         "NAVER_API_HUB_CLIENT_SECRET":"fake-secret"}
    out=collect(self.db,cfg,env=env,fetch=fake,today=date(2026,11,1))
    self.assertEqual([r["status"] for r in out],["success","success"])
    self.assertEqual(calls[1][1]["body"]["category"],"50000002")
    self.assertEqual(len(calls[1][1]["body"]["keyword"]),1)
 def test_parse_empty_is_explicit_failure(self):
    with self.assertRaises(ValueError):parse_yahoo(b'{}')
    with self.assertRaises(ValueError):parse_naver(b'{"results":[]}',"50000002","beauty")

class FakeEmbedder:
 def __init__(self,selected):
    self.selected=selected
 def embed(self,texts):
    n=len(LABELS)
    for i in range(len(texts)):
       vector=[0.0]*n
       vector[i if i<n else self.selected[i-n]]=1.0
       yield vector

class MultilingualTests(unittest.TestCase):
 def test_product_classification_with_stubbed_embedding(self):
    c=classify_batch(["折りたたみ収納ボックス"],FakeEmbedder([list(LABELS).index("storage")]))
    self.assertEqual(c[0]["category"],"storage")
    self.assertTrue(c[0]["product_related"])
 def test_news_rejected_with_stubbed_embedding(self):
    c=classify_batch(["football result"],FakeEmbedder([list(LABELS).index("sports_news")]))
    self.assertFalse(c[0]["product_related"])
    self.assertTrue(c[0]["needs_review"])
 def test_marketplace_source_comes_from_observation_not_model(self):
    c=classify_batch(["두피 마사지기"],FakeEmbedder([list(LABELS).index("sports_news")]),
                     source_is_product=True)
    self.assertTrue(c[0]["product_related"])
