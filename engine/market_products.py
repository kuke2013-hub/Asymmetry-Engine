"""Official Yahoo Japan ranked products and Naver Korea shopping-keyword interest.
Rank and relative-click ratio are NOT verified sales.
"""
import json, sqlite3, os, urllib.request, urllib.parse
from datetime import date,timedelta
from .core import utc_now

YAHOO="https://shopping.yahooapis.jp/ShoppingWebService/V1/highRatingTrendRanking"
NAVER="https://naverapihub.apigw.ntruss.com/shopping/v1/category/keywords"
SCHEMA="""
CREATE TABLE IF NOT EXISTS product_snapshots (
 day TEXT NOT NULL, source TEXT NOT NULL, product_id TEXT NOT NULL, name TEXT NOT NULL,
 rank INTEGER, price_jpy INTEGER, url TEXT, reviews INTEGER, rating REAL,
 captured_at TEXT NOT NULL, extras TEXT NOT NULL,
 UNIQUE(day,source,product_id));
CREATE TABLE IF NOT EXISTS korean_keyword_interest (
 day TEXT NOT NULL, comparison_set TEXT NOT NULL, category_id TEXT NOT NULL,
 keyword TEXT NOT NULL, period TEXT NOT NULL, ratio REAL NOT NULL,
 window_start TEXT NOT NULL, window_end TEXT NOT NULL, captured_at TEXT NOT NULL,
 UNIQUE(day,comparison_set,category_id,keyword,period,window_start,window_end));
"""
def setup(conn): conn.executescript(SCHEMA)

def parse_yahoo(raw, captured=None):
    captured=captured or utc_now()
    root=json.loads(raw).get("high_rating_trend_ranking",{})
    rows=root.get("ranking_data")
    if isinstance(rows,dict):rows=[rows]
    if not isinstance(rows,list) or not rows:raise ValueError("Yahoo: missing ranking data")
    out=[]
    for r in rows:
        item=r.get("item_information") or {}
        pid=str(item.get("code") or "").strip()
        name=str(item.get("name") or "").strip()
        if not pid or not name:continue
        rev=r.get("review") or {}
        out.append((captured[:10],"yahoo_jp_high_rating_products",pid,name,
            int(r["rank"]) if r.get("rank") is not None else None,
            int(item.get("bargain_price") or item.get("regular_price") or 0) or None,
            str(item.get("url") or ""),rev.get("count"),rev.get("rate"),captured,
            json.dumps({"updated":(root.get("meta") or {}).get("last_modified"),
                        "note":"Blended rank, NOT units sold"},ensure_ascii=False)))
    if not out:raise ValueError("Yahoo: zero valid ranked products")
    return out

def parse_naver(raw,category,comparison_set,captured=None):
    captured=captured or utc_now()
    data=json.loads(raw)
    if not data.get("startDate") or not data.get("endDate"):raise ValueError("Naver: missing window")
    if not isinstance(data.get("results"),list) or not data["results"]:
        raise ValueError("Naver: missing results")
    out=[]
    for group in data["results"]:
        for p in group.get("data") or []:
            if p.get("ratio") is None:continue
            ratio=float(p["ratio"])
            if ratio<0 or ratio>100:raise ValueError("Naver: ratio out of range")
            out.append((captured[:10],comparison_set,str(category),str(group["title"]),
                str(p["period"]),ratio,data["startDate"],data["endDate"],captured))
    if not out:raise ValueError("Naver: zero usable points")
    return out

def save_yahoo(conn, rows):
    with conn:
        for row in rows:
            conn.execute("INSERT OR IGNORE INTO product_snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?)",row)
    return len(rows)

def save_naver(conn, rows):
    with conn:
        for row in rows:
            conn.execute("INSERT OR IGNORE INTO korean_keyword_interest VALUES (?,?,?,?,?,?,?,?,?)",row)
    return len(rows)

def request(url,headers=None,body=None):
    data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None
    req=urllib.request.Request(url,data=data,headers=headers or {},
                               method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req,timeout=25) as res:
            raw=res.read(2_000_001)
            if not raw or len(raw)>2_000_000:raise ValueError("Empty or oversized response")
            return raw,int(res.status)
    except urllib.error.HTTPError as e:
        raise ValueError("HTTP "+str(e.code)) from None
    except (urllib.error.URLError,TimeoutError) as e:
        raise ValueError("Network error "+type(e).__name__) from None

def collect(conn,watchlist,env=None,fetch=request,today=None):
    env=env if env is not None else os.environ
    today=today or date.today()
    results=[]
    key=env.get("YAHOO_JP_APP_ID")
    for term in watchlist["yahoo_queries"]:
        result={"source":"yahoo_jp_high_rating_products","market":"JP",
                "term":term,"status":"skipped"}
        if not key:result["reason"]="credentials_missing"
        else:
            try:
                url=YAHOO+"?"+urllib.parse.urlencode({
                    "appid":key,"query":term,"limit":20,"price_from":500,"price_to":4000})
                raw,status=fetch(url)
                rows=parse_yahoo(raw)
                save_yahoo(conn,rows)
                result.update(status="success",http_status=status,observations=len(rows))
            except Exception as e:
                result.update(status="failed",reason=str(e)[:90] if isinstance(e,ValueError) else type(e).__name__)
        results.append(result)
    a=env.get("NAVER_API_HUB_CLIENT_ID")
    b=env.get("NAVER_API_HUB_CLIENT_SECRET")
    for group in watchlist["naver"]:
        result={"source":"naver_kr_shopping_keyword_clicks","market":"KR",
                "group":group["name"],"status":"skipped"}
        if not a or not b:result["reason"]="credentials_missing"
        else:
            try:
                keywords=group["keywords"]
                if not 1<=len(keywords)<=5:raise ValueError("1-5 Korean keyword groups required")
                body={"startDate":str(today-timedelta(days=28)),
                      "endDate":str(today),"timeUnit":"date",
                      "category":str(group["category_id"]),
                      "keyword":[{"name":w,"param":[w]} for w in keywords]}
                headers={"X-NCP-APIGW-API-KEY-ID":a,"X-NCP-APIGW-API-KEY":b,
                         "Content-Type":"application/json"}
                raw,status=fetch(NAVER,headers=headers,body=body)
                rows=parse_naver(raw,group["category_id"],group["name"])
                save_naver(conn,rows)
                result.update(status="success",http_status=status,observations=len(rows))
            except Exception as e:
                result.update(status="failed",reason=str(e)[:90] if isinstance(e,ValueError) else type(e).__name__)
        results.append(result)
    return results
