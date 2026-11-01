"""Live deployed-site HTTP contract — actual public GitHub Pages, not repo files."""
import json,sys,time,urllib.request,urllib.error
URL="https://kuke2013-hub.github.io/Asymmetry-Engine/"
def load(path):
    req=urllib.request.Request(URL+path,headers={"User-Agent":"AsymmetryEngine-QA/1.0"})
    with urllib.request.urlopen(req,timeout=20) as res:
        if res.status!=200:raise AssertionError(f"Unexpected HTTP {res.status}: {path}")
        return res.read(3_000_000)
def main():
    last=""
    for attempt in range(18):
        try:
            text=load("").decode("utf-8")
            if 'name="app-version" content="3.1"' in text and "reports/product-only.json" in text:break
            last="Expected version not yet deployed"
        except Exception as ex:last=type(ex).__name__
        time.sleep(5)
    else:raise AssertionError("Deployed site not at required release: "+last)
    assert "andreas almgren" not in text.lower(), "Old celebrity visible in HTML"
    assert "Recorded search signals" not in text, "Old search table visible in HTML"
    assert "reports/latest-observations.json" not in text, "Old RSS feed still loaded"
    assert "Not assessed" in text, "UK assessment falsely shown as numerical zero"
    assert "No live retail feeds connected" in text, "Missing honest source-readiness state"
    data=json.loads(load("reports/product-only.json"))
    assert data["schema_version"]==3
    assert data["data_type"]=="retailer_product_listings_only"
    assert data["product_count"]==len(data["products"])
    assert all(item["source"] in ("yahoo_jp_high_rating_products","rakuten_jp_item_search") for item in data["products"])
    assert all(x["status"]!="success" for x in data["source_status"]) or data["products"], "No fake successful product fetches"
    print("LIVE HTTP PASS: correct product-only version, zero RSS routes, consistent JSON.")
    print("LIVE PRODUCT COUNT:",data["product_count"])
    print("SOURCE STATES:",[(x["source"],x["status"]) for x in data["source_status"]])
if __name__=="__main__":main()
