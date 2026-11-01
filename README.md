# Asymmetry Engine — Market intelligence prototype

A Python + SQLite collector for investigating whether product interests in Japan,
South Korea and China lead commercial opportunities in the UK. Current Step 1
collects **public Google Trending Now RSS search topics** from GB, JP and KR,
not actual product sales. A Yahoo Japan Shopping keyword-ranking adapter is
available with separate credentials. Product research and local LLM evaluation
come in later phases.

## What is live

- GitHub Actions runs offline tests on commits and pull requests.
- A separate workflow attempts **live RSS collection** on qualifying pushes,
  daily at 05:43 UTC and when manually dispatched.
- Each attempted collection records success/failure and the exact number parsed.
- A dated JSON evidence file and a health report are committed automatically
  when the workflow has write permission.
- No external LLM tokens, paid data services or affiliate accounts are required.

Inspect [the latest health report](reports/latest-health.md) after an Action run.
Dated observations are stored in [data/history](data/history).
The source may block hosted runners: a recorded failed status is not a successful
collection, and the workflow then fails visibly after saving the diagnostic.

## Local commands

Requires Python 3.10+ and uses the standard library.

    python3 -m unittest discover -s tests -v
    python3 -m engine.cli init
    python3 -m engine.cli collect --markets GB,JP,KR
    python3 -m engine.cli health
    python3 -m engine.cli report
    python3 -m engine.cli export --out data/local-snapshot.json

The local SQLite file is ignored by Git. The optional Yahoo Japan collector
requires YAHOO_JP_APP_ID, and this project never stores that key in Git:

    python3 -m engine.cli fetch-yahoo --type up

An optional **Ollama** JSON-schema classifier is in engine/ai.py, but is not
trained, benchmarked or invoked in cloud scheduled jobs.

## Important limits

Google Trending Now reflects sudden general search activity. It is NOT a
consumer-product listing feed, NOT measured unit sales and NOT proof that
a country leads another. The next milestones are permitted product-specific
feeds, multilingual product matching, sustained history and benchmarked scoring.
No affiliate revenue is claimed.

The input XML/JSON test fixtures under fixtures/ are SYNTHETIC.
See [source-access audit](docs/SOURCES.md).
