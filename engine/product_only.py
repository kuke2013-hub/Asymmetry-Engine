"""Asymmetry Engine v3 — fail-closed product discovery.

Only official RETAIL PRODUCT LISTINGS may enter the catalogue.
Search trends, celebrities, shopping-keyword ratios and AI guesses cannot.
No paid LLM usage. Product listings are observations, not proof of sales.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html import unescape
import json, os, re
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

SOURCES = {
    "yahoo_jp_high_rating_products": ("JP","JPY",{"store.shopping.yahoo.co.jp"}),
    "rakuten_jp_item_search": ("JP","JPY",{"item.rakuten.co.jp"}),
}
CATEGORIES = {"beauty_tools", "kitchen_gadgets", "storage_organisation",
              "cleaning_tools", "travel_accessories", "pet_accessories",
              "desk_gadgets", "other_review"}
PUBLISHABLE = CATEGORIES - {"other_review"}
YAHOO_URL = "https://shopping.yahooapis.jp/ShoppingWebService/V1/highRatingTrendRanking"
RAKUTEN_URL = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"
SOURCE_DOCS = {
    "yahoo_jp_high_rating_products": "https://developer.yahoo.co.jp/webapi/shopping/shopping/v1/highRatingTrendRanking.html",
    "rakuten_jp_item_search": "https://webservice.rakuten.co.jp/index.php/documentation/ichiba-item-search"
}

@dataclass(frozen=True)
class Product:
    market: str
    source: str
    product_id: str
    title: str
    category: str
    price: int
    currency: str
    product_url: str
    observed_at: str
    ranking_position: int | None = None
    image_url: str | None = None
    review_count: int | None = None

class BadProduct(ValueError):
    pass

def now_utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def safe_url(url, hosts):
    if not isinstance(url,str):return False
    p=urlparse(url)
    if p.scheme != "https" or not p.hostname or p.port not in (None,443):
        return False
    if p.username or p.password:return False
    return p.hostname.lower() in hosts

def validate_product(record):
    if not isinstance(record,dict):raise BadProduct("not a product object")
    src=record.get("source")
    if src not in SOURCES:raise BadProduct("unapproved product source")
    market, currency, hosts = SOURCES[src]
    if record.get("market")!=market or record.get("currency")!=currency:
        raise BadProduct("source/market/currency mismatch")
    if record.get("category") not in CATEGORIES:
        raise BadProduct("unapproved category")
    pid=record.get("product_id")
    if not isinstance(pid,str) or not (2<=len(pid)<=160) or not pid.strip():
        raise BadProduct("missing product ID")
    title=record.get("title")
    if not isinstance(title,str) or not (3<=len(title.strip())<=240):
        raise BadProduct("missing product name")
    price=record.get("price")
    if type(price) is not int or not 100<=price<=120000:
        raise BadProduct("missing/unreasonable local currency price")
    if not safe_url(record.get("product_url"),hosts):
        raise BadProduct("not an official product listing URL")
    stamp=record.get("observed_at")
    if not isinstance(stamp,str):raise BadProduct("missing collection timestamp")
    try:
        dt=datetime.fromisoformat(stamp.replace("Z","+00:00"))
        if not dt.tzinfo:raise ValueError()
    except ValueError:
        raise BadProduct("timestamp must include timezone")
    rank=record.get("ranking_position")
    if rank is not None and (type(rank) is not int or rank<=0):
        raise BadProduct("invalid rank")
    return Product(market=market,source=src,product_id=pid.strip(),
         title=title.strip(),category=record["category"],price=price,
         currency=currency,product_url=record["product_url"],
         observed_at=stamp,ranking_position=rank,
         image_url=record.get("image_url"),review_count=record.get("review_count"))

def parse_yahoo_product_list(raw,category,observed_at=None):
    data=json.loads(raw)
    root=data.get("high_rating_trend_ranking")
    if not isinstance(root,dict):raise ValueError("Yahoo missing ranking response")
    rows=root.get("ranking_data")
    if isinstance(rows,dict):rows=[rows]
    if not isinstance(rows,list):raise ValueError("Yahoo missing product rows")
    observed_at=observed_at or now_utc()
    good=[]; rejected=0
    for row in rows:
        try:
            item=row.get("item_information") or {}
            price=item.get("bargain_price") or item.get("regular_price")
            image=row.get("image") or {}
            product=validate_product({
                "market":"JP","source":"yahoo_jp_high_rating_products",
                "product_id":item.get("code"),
                "title":item.get("name"),"category":category,
                "price":price,"currency":"JPY","product_url":item.get("url"),
                "observed_at":observed_at,
                "ranking_position":row.get("rank"),
                "image_url":image.get("medium"),
                "review_count":(row.get("review") or {}).get("count")})
            good.append(product)
        except (TypeError,ValueError,AttributeError,BadProduct):
            rejected+=1
    return good,rejected

def parse_rakuten_product_list(raw,category,observed_at=None):
    data=json.loads(raw)
    rows=data.get("Items")
    if rows is None:rows=data.get("items")
    if not isinstance(rows,list):raise ValueError("Rakuten missing product items")
    observed_at=observed_at or now_utc()
    good=[]; rejected=0
    for row in rows:
        try:
            item=row.get("Item",row.get("item",row))
            thumbs=item.get("mediumImageUrls") or []
            if thumbs and isinstance(thumbs[0],dict):
                image=thumbs[0].get("imageUrl")
            elif thumbs:image=thumbs[0]
            else:image=None
            product=validate_product({
              "market":"JP","source":"rakuten_jp_item_search",
              "product_id":item.get("itemCode"),
              "title":item.get("itemName"),"category":category,
              "price":item.get("itemPrice"),"currency":"JPY",
              "product_url":item.get("itemUrl"),"observed_at":observed_at,
              "image_url":image,
              "review_count":item.get("reviewCount")})
            good.append(product)
        except (TypeError,ValueError,AttributeError,BadProduct,IndexError):
            rejected+=1
    return good,rejected

def https_json(url,headers=None):
    req=Request(url,headers=headers or {"User-Agent":"AsymmetryEngine/3.0"})
    try:
        with urlopen(req,timeout=25) as res:
            data=res.read(2_000_001)
            if not data or len(data)>2_000_000:
                raise ValueError("empty/oversized provider response")
            return data
    except HTTPError as e:raise ValueError("provider HTTP "+str(e.code)) from None
    except (URLError,OSError,TimeoutError) as e:
        raise ValueError("provider network "+type(e).__name__) from None

def publish(products,source_status,observed_at=None):
    """In-memory transform is the ONLY gate to public product-candidate JSON."""
    observed_at=observed_at or now_utc()
    approved={}
    rejected=0
    for record in products:
        try:
            p=validate_product(asdict(record) if isinstance(record,Product) else record)
            if p.category not in PUBLISHABLE:
                rejected+=1;continue
            key=(p.source,p.product_id)
            if key not in approved:approved[key]=p
        except (BadProduct,TypeError,ValueError):
            rejected+=1
    candidates=[asdict(x) for x in sorted(approved.values(),
              key=lambda p:(p.market,p.category,p.source,p.product_id))]
    return {
       "schema_version":3,"generated_at":observed_at,
       "data_type":"retailer_product_listings_only",
       "headline":"Catalogue candidates; none are verified UK commercial opportunities",
       "products":candidates,"product_count":len(candidates),
       "rejected_records":rejected,
       "source_status":source_status,
       "uk_matching_status":"not_implemented",
       "china_status":"not_connected",
       "korea_product_status":"no_authorised_SKU_feed",
       "sales_status":"no_verified_units_sold",
       "disclaimer":"Ranking is not units sold. No UK availability, commissions or predictive advantage validated."
    }

def collect_product_sources(watchlist,env=None,fetch=https_json):
    env=env if env is not None else os.environ
    products=[];status=[]
    for spec in watchlist["queries"]:
        src=spec["source"]; category=spec["category"];term=spec["term"]
        if src not in SOURCES or category not in PUBLISHABLE:
            raise ValueError("Invalid watchlist source/category")
        if not isinstance(term,str) or not term.strip():raise ValueError("Empty watchlist query")
        auth=(("YAHOO_JP_APP_ID",) if src=="yahoo_jp_high_rating_products"
              else ("RAKUTEN_APP_ID","RAKUTEN_ACCESS_KEY"))
        result={"source":src,"market":"JP","category":category,
                "query":term,"status":"credentials_missing",
                "accepted":0,"rejected":0}
        if not all(env.get(name) for name in auth):
            status.append(result);continue
        try:
            if src=="yahoo_jp_high_rating_products":
                url=YAHOO_URL+"?"+urlencode({"appid":env["YAHOO_JP_APP_ID"],
                    "query":term,"limit":20,"price_from":500,"price_to":3500})
                raw=fetch(url)
                rows,bad=parse_yahoo_product_list(raw,category)
            else:
                url=RAKUTEN_URL+"?"+urlencode({"applicationId":env["RAKUTEN_APP_ID"],
                   "keyword":term,"hits":20,"minPrice":500,"maxPrice":3500,
                   "availability":1,"hasImageFlag":1,"format":"json",
                   "formatVersion":2})
                raw=fetch(url,headers={"accessKey":env["RAKUTEN_ACCESS_KEY"]})
                rows,bad=parse_rakuten_product_list(raw,category)
            products.extend(rows)
            result.update(status="success" if rows else "empty_or_rejected",
                          accepted=len(rows),rejected=bad)
        except Exception as ex:
            # URLs and credentials are deliberately never exposed
            result.update(status="failed",
                          reason=type(ex).__name__+(" (provider response)" if isinstance(ex,ValueError) else ""))
        status.append(result)
    return publish(products,status)

def main(argv=None):
    import argparse
    p=argparse.ArgumentParser(description="Official retail product listings only")
    p.add_argument("--watchlist",default="config/products.json")
    p.add_argument("--output",default="reports/product-only.json")
    args=p.parse_args(argv)
    cfg=json.loads(Path(args.watchlist).read_text(encoding="utf-8"))
    out=collect_product_sources(cfg)
    dest=Path(args.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"product_count":out["product_count"],"rejected":out["rejected_records"],
          "sources":out["source_status"]},ensure_ascii=False))
    if any(x["status"]=="failed" for x in out["source_status"]):
        return 1
    return 0

if __name__=="__main__":
    raise SystemExit(main())
