"""Evidence store: a search trend is NOT a product sale."""
from __future__ import annotations
from datetime import datetime, timezone
import json
import sqlite3
import xml.etree.ElementTree as ET

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 captured_day TEXT NOT NULL, captured_at TEXT NOT NULL,
 market TEXT NOT NULL, source TEXT NOT NULL,
 source_record_id TEXT NOT NULL, source_url TEXT NOT NULL,
 metric_type TEXT NOT NULL, metric_value REAL,
 original_text TEXT NOT NULL, metadata_json TEXT NOT NULL,
 UNIQUE(captured_day,market,source,source_record_id)
);
CREATE TABLE IF NOT EXISTS collection_runs (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 source TEXT NOT NULL, market TEXT NOT NULL,
 started_at TEXT NOT NULL, finished_at TEXT,
 status TEXT NOT NULL CHECK(status IN ('running','success','failed')),
 parsed_count INTEGER NOT NULL DEFAULT 0,
 inserted_count INTEGER NOT NULL DEFAULT 0,
 http_status INTEGER, payload_sha256 TEXT, error_message TEXT
);
CREATE INDEX IF NOT EXISTS idx_runs ON collection_runs(source,market,started_at);
CREATE TABLE IF NOT EXISTS classifications (
 signal_id INTEGER PRIMARY KEY REFERENCES signals(id),
 translated_term TEXT NOT NULL, product_related INTEGER NOT NULL,
 category TEXT NOT NULL, demo_potential INTEGER NOT NULL,
 impulse_fit INTEGER NOT NULL, confidence REAL NOT NULL,
 rationale TEXT NOT NULL, risk_flags_json TEXT NOT NULL,
 reviewed INTEGER NOT NULL DEFAULT 0
);
"""

def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def connect(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA foreign_keys=ON')
    conn.executescript(SCHEMA)
    return conn

def parse_rss(xml_bytes: bytes, market: str, capture: str | None = None):
    capture = capture or utc_now()
    market = market.upper()
    if market not in ('GB','JP','KR'):
        raise ValueError('Unsupported RSS market')
    root = ET.fromstring(xml_bytes)
    items = root.findall('./channel/item')
    if not items:
        raise ValueError('Feed contained zero RSS items')
    ns = '{https://trends.google.com/trending/rss}'
    result = []
    for item in items:
        title = (item.findtext('title') or '').strip()
        if not title:
            continue
        traffic = (item.findtext(ns+'approx_traffic') or '').strip()
        result.append(dict(
            captured_day=capture[:10], captured_at=capture, market=market,
            source='google_trending_rss', source_record_id=title.casefold(),
            source_url=(item.findtext('link') or '').strip() or
                       'https://trends.google.com/trending?geo='+market,
            metric_type='approx_search_traffic_bucket' if traffic else 'trending_search_topic',
            metric_value=None, original_text=title,
            metadata={'approx_traffic_display':traffic,
                      'published_at':item.findtext('pubDate') or '',
                      'note':'Search trends, NOT verified product sales'}))
    if not result:
        raise ValueError('RSS feed has no usable titles')
    return result

def parse_yahoo_keyword_json(raw: bytes, capture: str | None = None):
    capture = capture or utc_now()
    data = json.loads(raw)
    block = data.get('keyword_ranking')
    if not isinstance(block,dict):
        raise ValueError('Yahoo response missing keyword_ranking')
    rows = block.get('ranking_data')
    if isinstance(rows,dict):
        rows=[rows]
    if not isinstance(rows,list):
        raise ValueError('Yahoo response missing ranking_data')
    kind = (block.get('conditions') or {}).get('type','ranking')
    meta = block.get('meta') or {}
    result=[]
    for row in rows:
        if not isinstance(row,dict):
            continue
        query=str(row.get('query') or '').strip()
        if not query:
            continue
        result.append(dict(
            captured_day=capture[:10], captured_at=capture,
            market='JP', source='yahoo_jp_keyword_ranking',
            source_record_id=str(kind)+':'+query.casefold(),
            source_url=str(row.get('url') or 'https://shopping.yahoo.co.jp/'),
            metric_type='shopping_search_rank',
            metric_value=float(row['rank']) if row.get('rank') is not None else None,
            original_text=query,
            metadata={'previous_rank':row.get('pre_rank'),
                      'change':row.get('vector'),
                      'period_start':meta.get('start_date'),
                      'period_end':meta.get('end_date'),
                      'ranking_type':kind,
                      'note':'Search rank, NOT item sales'}))
    if not result:
        raise ValueError('No usable Yahoo shopping keywords')
    return result

def store_signals(conn, records):
    inserted=0
    with conn:
        for r in records:
            cur=conn.execute("""INSERT OR IGNORE INTO signals
              (captured_day,captured_at,market,source,source_record_id,
               source_url,metric_type,metric_value,original_text,metadata_json)
              VALUES (?,?,?,?,?,?,?,?,?,?)""",
              (r['captured_day'],r['captured_at'],r['market'],r['source'],
               r['source_record_id'],r['source_url'],r['metric_type'],
               r['metric_value'],r['original_text'],
               json.dumps(r['metadata'],ensure_ascii=False)))
            inserted+=cur.rowcount
    return inserted

def evidence_export(conn, day=None):
    """Only real rows actually collected are exported, never fixtures."""
    day = day or utc_now()[:10]
    rows = conn.execute("""SELECT market,source,original_text,metric_type,
                metric_value,source_url,metadata_json,captured_at
                FROM signals WHERE captured_day=? ORDER BY market,source,original_text""",
                (day,)).fetchall()
    runs = conn.execute("""SELECT market,source,status,parsed_count,inserted_count,
                    http_status,error_message,started_at,finished_at
                    FROM collection_runs WHERE substr(started_at,1,10)=?
                    ORDER BY id""",(day,)).fetchall()
    return {
      'captured_day':day,
      'generated_at':utc_now(),
      'warning':'Market research signals; NOT product sales or affiliate earnings',
      'observations':[dict(market=r[0],source=r[1],term=r[2],metric_type=r[3],
                          metric_value=r[4],source_url=r[5],
                          metadata=json.loads(r[6]),captured_at=r[7]) for r in rows],
      'collection_runs':[dict(market=r[0],source=r[1],status=r[2],
                              parsed=r[3],inserted=r[4],http_status=r[5],
                              error=r[6],started_at=r[7],finished_at=r[8]) for r in runs]
    }

def report(conn, limit=20):
    counts=conn.execute('SELECT market,source,COUNT(*) FROM signals GROUP BY market,source').fetchall()
    lines=['# Evidence report','','Search trends are not product sales.','']
    lines.extend(f'- {m} {s}: {n} observations' for m,s,n in counts)
    if not counts: lines.append('- No observations')
    return '\n'.join(lines)
