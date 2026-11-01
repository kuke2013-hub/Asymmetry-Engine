"""All tests are offline and use synthetic fixtures; they prove NO live data access."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError
from engine.core import (connect,parse_rss,parse_yahoo_keyword_json,store_signals,
                         evidence_export,report)
from engine.collection import (get_bytes,collect_one,collect_daily,health_report,FetchError)
from engine.cli import main

ROOT=Path(__file__).resolve().parents[1]
CAPTURE='2026-11-01T12:00:00+00:00'

class FakeResponse:
    status=200
    def __init__(self,data):self.data=data
    def __enter__(self):return self
    def __exit__(self,*args):return None
    def read(self,n):return self.data

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.conn=connect(str(Path(self.tmp.name)/'test.sqlite'))
        self.rss=(ROOT/'fixtures/google_jp.xml').read_bytes()
        self.yahoo=(ROOT/'fixtures/yahoo_jp.json').read_bytes()
    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()
    def test_rss_does_not_treat_traffic_as_sales(self):
        obs=parse_rss(self.rss,'JP',CAPTURE)
        self.assertEqual(len(obs),2)
        self.assertEqual(obs[0]['metric_value'],None)
        self.assertEqual(obs[0]['metadata']['approx_traffic_display'],'1K+')
    def test_rss_news_not_product(self):
        obs=parse_rss(self.rss,'JP',CAPTURE)
        self.assertIn('ニュース',obs[1]['original_text'])
    def test_yahoo_keyword_not_units(self):
        obs=parse_yahoo_keyword_json(self.yahoo,CAPTURE)
        self.assertEqual(len(obs),2)
        self.assertEqual(obs[0]['metric_type'],'shopping_search_rank')
        self.assertEqual(obs[0]['metric_value'],1.0)
    def test_deduplication(self):
        obs=parse_rss(self.rss,'JP',CAPTURE)
        self.assertEqual(store_signals(self.conn,obs),2)
        self.assertEqual(store_signals(self.conn,obs),0)
        self.assertIn('JP google_trending_rss: 2',report(self.conn))
    def test_empty_feed_error(self):
        with self.assertRaises(ValueError):
            parse_rss(b'<rss><channel/></rss>','GB',CAPTURE)
    def test_bad_yahoo_response_error(self):
        with self.assertRaises(ValueError):
            parse_yahoo_keyword_json(b'{}',CAPTURE)
    def test_logged_success_repeat(self):
        a=collect_one(self.conn,source='google_trending_rss',market='GB',
                      fetcher=lambda url:(self.rss,200))
        b=collect_one(self.conn,source='google_trending_rss',market='GB',
                      fetcher=lambda url:(self.rss,200))
        self.assertEqual((a.status,a.parsed,a.inserted),('success',2,2))
        self.assertEqual((b.status,b.parsed,b.inserted),('success',2,0))
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM collection_runs').fetchone()[0],2)
        self.assertEqual(len(a.payload_sha256),64)
    def test_failed_fetch_explicit(self):
        def fail(url):raise FetchError('Network failure')
        r=collect_one(self.conn,source='google_trending_rss',market='KR',fetcher=fail)
        self.assertEqual(r.status,'failed')
        self.assertIn('FAILED',health_report(self.conn))
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM signals').fetchone()[0],0)
    def test_empty_feed_logged_failed(self):
        r=collect_one(self.conn,source='google_trending_rss',market='JP',
                      fetcher=lambda url:(b'<rss><channel/></rss>',200))
        self.assertEqual(r.status,'failed')
        self.assertIn('zero RSS items',r.error)
    def test_yahoo_does_not_store_secret(self):
        r=collect_one(self.conn,source='yahoo_jp_keyword_ranking',
                      market='JP',app_id='secret987',fetcher=lambda url:(self.yahoo,200))
        self.assertEqual(r.status,'success')
        self.assertNotIn('secret987',repr(self.conn.execute('SELECT * FROM collection_runs').fetchall()))
    def test_partial_failure_continues(self):
        def fetch(url):
            if 'geo=KR' in url:raise FetchError('Network failure')
            return self.rss,200
        result=collect_daily(self.conn,('GB','KR','JP'),fetcher=fetch)
        self.assertEqual([r.status for r in result],['success','failed','success'])
    def test_http_404_not_retried_or_leaked(self):
        attempts=[]
        def fake(req,timeout):
            attempts.append(1)
            raise HTTPError('https://example.invalid/token123',404,'Missing',{},None)
        with self.assertRaises(FetchError) as e:
            get_bytes('https://example.invalid?secret=token123',opener=fake)
        self.assertEqual(len(attempts),1)
        self.assertNotIn('token123',str(e.exception))
    def test_export_reports_real_rows_only(self):
        d=evidence_export(self.conn,CAPTURE[:10])
        self.assertEqual(d['observations'],[])
        self.assertEqual(d['collection_runs'],[])
        self.assertIn('NOT product sales',d['warning'])
    def test_cli_health_empty(self):
        out=io.StringIO()
        with redirect_stdout(out):
            rc=main(['--db',str(Path(self.tmp.name)/'clean.sqlite'),'health'])
        self.assertEqual(rc,0)
        self.assertIn('No source collection attempts recorded',out.getvalue())
    def test_cli_collect_invalid_market(self):
        with self.assertRaises(SystemExit):
            main(['--db',str(Path(self.tmp.name)/'invalid.sqlite'),'collect','--markets','CN'])
    def test_export_one_record(self):
        obs=parse_rss(self.rss,'JP',CAPTURE)
        store_signals(self.conn,obs)
        data=evidence_export(self.conn,CAPTURE[:10])
        self.assertEqual(len(data['observations']),2)
        self.assertIsNone(data['observations'][0]['metric_value'])

if __name__=='__main__':
    unittest.main()
