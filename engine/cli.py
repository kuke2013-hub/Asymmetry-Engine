"""Command-line interface. No fabricated sales data or paid API calls."""
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
from .core import connect, parse_rss, parse_yahoo_keyword_json, store_signals, evidence_export, report
from .collection import collect_daily, collect_one, health_report

ROOT=Path(__file__).resolve().parent.parent
DEFAULT_DB=ROOT/'data'/'signals.sqlite'

def main(argv=None):
    p=argparse.ArgumentParser(description='Asymmetry Engine — verified source observations')
    p.add_argument('--db',default=str(DEFAULT_DB))
    subs=p.add_subparsers(dest='command',required=True)
    subs.add_parser('init')
    c=subs.add_parser('collect')
    c.add_argument('--markets',default='GB,JP,KR')
    c.add_argument('--with-yahoo',action='store_true')
    c.add_argument('--json',action='store_true')
    h=subs.add_parser('health')
    ex=subs.add_parser('export')
    ex.add_argument('--date',default=None)
    ex.add_argument('--out',required=True)
    sub=subs.add_parser('import-rss')
    sub.add_argument('--market',required=True,choices=['GB','JP','KR'])
    sub.add_argument('--file',required=True)
    sub=subs.add_parser('import-yahoo')
    sub.add_argument('--file',required=True)
    yf=subs.add_parser('fetch-yahoo')
    yf.add_argument('--type',choices=['up','ranking'],default='up')
    sub=subs.add_parser('report')
    a=p.parse_args(argv)
    db=Path(a.db)
    db.parent.mkdir(parents=True,exist_ok=True)
    conn=connect(str(db))
    try:
        if a.command=='init':
            print('Database initialised:',db)
        elif a.command=='collect':
            markets=tuple(x.strip().upper() for x in a.markets.split(',') if x.strip())
            if (not markets or len(set(markets))!=len(markets)
                or any(x not in ('GB','JP','KR') for x in markets)):
                p.error('Markets must be unique codes GB,JP,KR')
            if a.with_yahoo and not os.getenv('YAHOO_JP_APP_ID'):
                p.error('YAHOO_JP_APP_ID is required for Yahoo')
            results=collect_daily(conn,markets,with_yahoo=a.with_yahoo)
            if a.json:
                print(json.dumps([asdict(r) for r in results],ensure_ascii=False,indent=2))
            else:
                for r in results:
                    print(f'{r.market}/{r.source}: {r.status} parsed={r.parsed} new={r.inserted}'+
                          (f' error={r.error}' if r.error else ''))
            return 1 if any(r.status!='success' for r in results) else 0
        elif a.command=='health':
            print(health_report(conn))
        elif a.command=='export':
            obj=evidence_export(conn,a.date)
            dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(f'Exported {len(obj["observations"])} observed signals and {len(obj["collection_runs"])} run records to {dest}')
        elif a.command=='report':
            print(report(conn))
        elif a.command in ('import-rss','import-yahoo'):
            raw=Path(a.file).read_bytes()
            obs=parse_rss(raw,a.market) if a.command=='import-rss' else parse_yahoo_keyword_json(raw)
            print('OFFLINE IMPORT (check provenance): parsed=',len(obs),
                  'inserted=',store_signals(conn,obs))
        elif a.command=='fetch-yahoo':
            key=os.getenv('YAHOO_JP_APP_ID')
            if not key:p.error('YAHOO_JP_APP_ID is missing')
            r=collect_one(conn,source='yahoo_jp_keyword_ranking',market='JP',
                          app_id=key,ranking_type=a.type)
            print(f'{r.market}/{r.source}: {r.status} parsed={r.parsed} inserted={r.inserted}'+
                  (f' issue={r.error}' if r.error else ''))
            return 1 if r.status!='success' else 0
        return 0
    finally:
        conn.close()

if __name__=='__main__':
    raise SystemExit(main())
