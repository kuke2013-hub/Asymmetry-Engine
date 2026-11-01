"""Japan and Korea source collector health and local SQLite persistence."""
import argparse,json
from pathlib import Path
from .core import connect,utc_now
from .market_products import setup,collect

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("command",choices=["collect","summary"])
    p.add_argument("--config",default="config/watchlist.json")
    p.add_argument("--db",default="data/market_products.sqlite")
    p.add_argument("--out",default="reports/product-sources.json")
    a=p.parse_args(argv)
    db=Path(a.db);db.parent.mkdir(parents=True,exist_ok=True)
    conn=connect(str(db));setup(conn)
    try:
        if a.command=="summary":
            print(json.dumps({"products":conn.execute("SELECT COUNT(*) FROM product_snapshots").fetchone()[0],
              "korean_keyword_clicks":conn.execute("SELECT COUNT(*) FROM korean_keyword_interest").fetchone()[0]}))
            return 0
        cfg=json.loads(Path(a.config).read_text(encoding="utf-8"))
        runs=collect(conn,cfg)
        counts={k:sum(r["status"]==k for r in runs) for k in ("success","skipped","failed")}
        report={"captured_at":utc_now(),"warning":"Ranks and clicks are not actual sales",
                "counts":counts,"runs":runs}
        path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(counts))
        return int(counts["failed"]>0)
    finally:conn.close()

if __name__=="__main__":raise SystemExit(main())
