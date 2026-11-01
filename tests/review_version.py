"""Verify two live URLs and the authentic retail-only product feed (not fixtures)."""
import json,time,urllib.request
from pathlib import Path
BASE="https://kuke2013-hub.github.io/Asymmetry-Engine/"
VER=json.loads(Path("config/site-release.json").read_text())["version"]
def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":"AsymmetryEngine-QA/2.0"})
    with urllib.request.urlopen(req,timeout=20) as x:
        assert x.status==200, f"Wrong HTTP status {x.status}"
        return x.read(2_000_000)
def check():
    a=fetch(BASE+"reports/product-only.json")
    data=json.loads(a)
    assert data["schema_version"]==3 and data["data_type"]=="retailer_product_listings_only"
    assert isinstance(data["products"],list) and len(data["products"])==data["product_count"]
    assert all(p.get("source") in {"yahoo_jp_high_rating_products","rakuten_jp_item_search"} for p in data["products"])
    texts={}
    for label,url in (("root",BASE),("version",BASE+"versions/"+VER+"/")):
        html=fetch(url).decode()
        assert f'content="{VER}"' in html,f"{label} is not at {VER}"
        assert "andreas almgren" not in html.lower()
        assert "Recorded search signals" not in html
        assert "product-only.json" in html
        if label=="version":
            assert "../../reports/product-only.json" in html
        texts[label]=len(html)
    print("LIVE RELEASE PASS:",VER,"HTML sizes:",texts,
          "PRODUCTS:",len(data["products"]),
          "AUTHENTICATED QUERIES:",sum(s.get("status")=="success" for s in data["source_status"]))
if __name__=="__main__":
    last=None
    for i in range(45):
        try:
            check()
            break
        except Exception as ex:
            last=ex
            time.sleep(4)
    else:raise AssertionError("Live release never passed: "+str(last))
