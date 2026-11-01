"""Bounded public-feed collection with durable success/failure records."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen
from urllib.parse import urlencode
import hashlib
import os
import time
from .core import parse_rss, parse_yahoo_keyword_json, store_signals, utc_now

MAX_RESPONSE_BYTES=3_000_000
RSS_URL='https://trends.google.com/trending/rss'
YAHOO_URL='https://shopping.yahooapis.jp/ShoppingWebService/V2/queryRanking'
MARKETS=('GB','JP','KR')

class FetchError(RuntimeError):
    def __init__(self,message,http_status=None):
        super().__init__(message)
        self.http_status=http_status

@dataclass
class CollectionResult:
    source: str
    market: str
    status: str
    parsed: int=0
    inserted: int=0
    error: str | None=None
    http_status: int | None=None
    payload_sha256: str | None=None

def get_bytes(url, *, timeout=20, retries=2, opener=None):
    opener=opener or urlopen
    request=Request(url,headers={'User-Agent':'AsymmetryEngine/1.0 (public RSS research)'})
    error=None
    for i in range(retries+1):
        try:
            with opener(request,timeout=timeout) as r:
                status=int(getattr(r,'status',200))
                content=r.read(MAX_RESPONSE_BYTES+1)
                if len(content)>MAX_RESPONSE_BYTES:
                    raise FetchError('Response too large',status)
                if not content.strip():
                    raise FetchError('Empty feed response',status)
                return content,status
        except HTTPError as e:
            error=FetchError('HTTP '+str(e.code)+' from source',e.code)
            if e.code not in (429,500,502,503,504):
                break
        except (URLError,OSError,TimeoutError) as e:
            # Never log URL or exception text: query may contain credentials.
            error=FetchError('Network failure ('+type(e).__name__+')')
        if i<retries:
            time.sleep(min(2**i,4))
    raise error or FetchError('Unknown fetch error')

def collect_one(conn, *, source, market, app_id=None, ranking_type='up', fetcher=get_bytes):
    if source not in ('google_trending_rss','yahoo_jp_keyword_ranking'):
        raise ValueError('Invalid source')
    if source=='google_trending_rss' and market not in MARKETS:
        raise ValueError('Unsupported market')
    if source=='yahoo_jp_keyword_ranking':
        if market!='JP' or ranking_type not in ('up','ranking'):
            raise ValueError('Unsupported Yahoo request')
        if not app_id:
            raise ValueError('YAHOO_JP_APP_ID missing')
    now=utc_now()
    with conn:
        run_id=conn.execute("""INSERT INTO collection_runs
             (source,market,started_at,status)
             VALUES (?,?,?,'running')""",(source,market,now)).lastrowid
    result=CollectionResult(source,market,'failed')
    try:
        if source=='google_trending_rss':
            url=RSS_URL+'?'+urlencode({'geo':market})
        else:
            url=YAHOO_URL+'?'+urlencode({'appid':app_id,'type':ranking_type})
        raw,status=fetcher(url)
        result.http_status=status
        result.payload_sha256=hashlib.sha256(raw).hexdigest()
        obs=parse_rss(raw,market) if source=='google_trending_rss' else parse_yahoo_keyword_json(raw)
        result.parsed=len(obs)
        result.inserted=store_signals(conn,obs)
        result.status='success'
    except Exception as e:
        if isinstance(e,FetchError):
            result.http_status=e.http_status
            result.error=str(e)
        elif isinstance(e,ValueError):
            result.error='ValueError: '+str(e)[:160]
        else:
            result.error=type(e).__name__+': collection failed'
    finally:
        with conn:
            conn.execute("""UPDATE collection_runs SET finished_at=?,status=?,
                    parsed_count=?,inserted_count=?,http_status=?,
                    payload_sha256=?,error_message=? WHERE id=?""",
                    (utc_now(),result.status,result.parsed,result.inserted,
                     result.http_status,result.payload_sha256,result.error,run_id))
    return result

def collect_daily(conn,markets=('GB','JP','KR'),with_yahoo=False,fetcher=get_bytes):
    results=[collect_one(conn,source='google_trending_rss',market=m,
                         fetcher=fetcher) for m in markets]
    if with_yahoo:
        results.append(collect_one(conn,source='yahoo_jp_keyword_ranking',
                       market='JP',app_id=os.getenv('YAHOO_JP_APP_ID'),
                       fetcher=fetcher))
    return results

def health_report(conn):
    runs=conn.execute("""SELECT market,source,status,started_at,
                 parsed_count,inserted_count,error_message
                 FROM collection_runs ORDER BY id DESC LIMIT 20""").fetchall()
    lines=['# Collector health','','A successful fetch does NOT imply verified product sales.','']
    if not runs:
        lines.append('No source collection attempts recorded')
    for market,source,status,start,parsed,inserted,error in runs:
        lines.append(f'- {market}/{source}: {status.upper()} at {start}; parsed={parsed}, new={inserted}'
                     +(f'; issue={error}' if error else ''))
    counts=conn.execute("""SELECT market,source,COUNT(DISTINCT captured_day)
                     FROM signals GROUP BY market,source""").fetchall()
    lines+=['','## Days with observations']
    for market,source,count in counts:
        lines.append(f'- {market}/{source}: {count}')
    if not counts:lines.append('- None')
    return '\n'.join(lines)
