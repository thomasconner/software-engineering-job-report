# Software Engineering Jobs Report

A monthly Software Engineering Jobs Report on the US software engineering job market, built from public sources: Indeed Hiring Lab job postings, BLS job openings and employment (JOLTS, CES), and Hacker News "Ask HN: Who is hiring?" and "Who wants to be hired?" threads back to 2011. Each month gets a short data column with the charts behind it.

Read it at https://thomasconner.github.io/software-engineering-job-report/.

The design is in [docs/spec.md](docs/spec.md) and the data contracts are in [docs/architecture.md](docs/architecture.md).

## Data credits

Benchmark lines use data from [Indeed Hiring Lab](https://github.com/hiring-lab) (job postings, remote and pay transparency trackers), licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); this report indexes it to a base month. BLS JOLTS and CES data are public domain (charts show JOLTS as a 12-month average), with past vintages read from ALFRED (Federal Reserve Bank of St. Louis). SEC EDGAR filings are public information; the panel, sums, counts and headcounts read from filing text are this report's.

## Run it locally

You need [uv](https://docs.astral.sh/uv/). Classification calls the Typesafe API, and SEC EDGAR requires a User-Agent with a contact email, so put both in `.env` (gitignored):

```sh
echo "TYPESAFE_API_KEY=..." > .env
echo "SEC_USER_AGENT=Your Name you@example.com" >> .env
uv sync
```

Then run the pipeline, one step at a time:

```sh
uv run sejr fetch        # Algolia -> data/raw (gzipped thread JSON)
uv run sejr normalize    # data/raw -> data/sejr.duckdb
uv run sejr ats          # company job boards -> data/external/ats (once a month)
uv run sejr features     # regex and vocabulary answers
uv run --env-file .env sejr classify   # Jev answers for posts not yet answered
uv run sejr aggregate    # monthly metrics, each month as it looked at the time
uv run sejr external     # Indeed and BLS benchmarks -> data/external, as published at the time
uv run --env-file .env sejr sec   # SEC EDGAR panel -> data/external/sec, from filings accepted by then
uv run sejr export       # site/data/*.json
uv run pytest
```

Flags:

- `fetch`, `normalize`: `--month YYYY-MM`, `--limit N`, `--dry-run`.
- `classify`: the same, plus `--backfill`. It only answers posts from complete threads (past their 7-day snapshot) and skips posts whose stored answers match the current questions and text. Without `--month` or `--backfill` it refuses a run of more than 500 API calls. `--dry-run` prints the call count and estimated cost.
- `external`: `--month`, `--limit`, `--dry-run`, `--backfill`. Without `--backfill` or `--month` it refuses to pull more than three months. It clones the Indeed Hiring Lab repos (blobless) into `data/cache/external/`, and reads `BLS_API_KEY` from the environment if set (the keyless BLS API allows 25 queries a day).
- `sec`: `--month`, `--limit`, `--dry-run`, `--backfill`. It computes a month only after its as-of date and never again once written (unless a series was missing), so a backfill is resumable. Without `--backfill` or `--month` it refuses more than three months. It needs `SEC_USER_AGENT`, sends at most about 6.7 requests a second, and caches raw EDGAR responses (including the 1.6 GB `submissions.zip` and filing headers) in `data/cache/sec/`. The full backfill (2012 on) takes about 35 minutes from an empty cache, most of it reading about 4,300 filing headers for their SIC code.
- `uv run sejr unanswered` prints the complete months that still have posts to classify.
- `uv run --env-file .env sejr validate` scores Jev against the hand-labeled reference set (`data/labels/`) and writes `site/data/validation.json`. `--dry-run` shows what it would classify first.

Jev answers are committed under `data/answers/`, so a fresh checkout classifies only new posts.

To view the site, serve `site/` (for example `python -m http.server -d site`).

## Monthly updates

`.github/workflows/monthly.yml` runs at 17:00 UTC on days 1–12 of each month. A thread's 7-day snapshot completes around the 8th, and fetch only touches threads still inside that window, so new data appears only in that stretch. Each run:

1. runs the tests;
2. fetches and normalizes, snapshots company job boards (`sejr ats`; it fetches until the month has a snapshot, and a failure there doesn't stop the run), and computes features;
3. classifies each complete month that has unanswered posts (`--month`), then runs a guarded unscoped classify. If more than three months need classifying, it stops: that is a question or model change, and the backfill is run by hand;
4. commits `data/answers` straight away, even if a later step fails, so paid answers aren't lost;
5. aggregates, pulls the outside benchmarks, computes the SEC panel series (`sejr sec`, skipped with a warning when the `SEC_USER_AGENT` secret is missing), exports, and commits `data/raw`, `data/answers`, `data/external` (benchmarks and the job-board snapshots in `data/external/ats`) and `site/data` as `data: refresh YYYY-MM`;
6. redeploys the site when `site/` changed.

Expect a commit on most of days 1–12 while the current thread fills in, and none for the rest of the month.

When a new month becomes complete and `site/articles/YYYY-MM.md` doesn't exist yet, the workflow opens an issue titled "Write the <Month YYYY> column". The column is written and fact-checked by agents outside CI, then merged, which deploys it.

## First deploy

1. Run the full backfill locally (`uv run --env-file .env sejr classify --backfill`) and commit `data/answers/`. CI never backfills.
2. Add `TYPESAFE_API_KEY` and `SEC_USER_AGENT` (a name and contact email, as SEC asks) as repository Actions secrets.
3. Set Settings → Pages → Source to "GitHub Actions".
