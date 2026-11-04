# Software Engineering Job Report

A monthly report on US startup and engineering hiring, built from Hacker News "Ask HN: Who is hiring?" and "Who wants to be hired?" threads back to 2011. Each month gets a short data column with the charts behind it.

Read it at https://thomasconner.github.io/software-engineering-job-report/.

The design is in [docs/spec.md](docs/spec.md) and the data contracts are in [docs/architecture.md](docs/architecture.md).

## Run it locally

You need [uv](https://docs.astral.sh/uv/). Classification calls the Typesafe API, so put your key in `.env` (gitignored):

```sh
echo "TYPESAFE_API_KEY=..." > .env
uv sync
```

Then run the pipeline, one step at a time:

```sh
uv run sejr fetch        # Algolia -> data/raw (gzipped thread JSON)
uv run sejr normalize    # data/raw -> data/sejr.duckdb
uv run sejr features     # regex and vocabulary answers
uv run --env-file .env sejr classify   # Jev answers for posts not yet answered
uv run sejr aggregate    # monthly metrics, each month as it looked at the time
uv run sejr export       # site/data/*.json
uv run pytest
```

Every step takes `--month YYYY-MM`, `--limit N` and `--dry-run`. Jev answers are committed under `data/answers/`, so a fresh checkout classifies only new posts. Classify refuses a run of more than 500 API calls unless you pass `--month` or `--backfill`.

To view the site, serve `site/` (for example `python -m http.server -d site`).

## Monthly updates

`.github/workflows/monthly.yml` runs every day at 17:00 UTC. Fetch only touches threads still inside their 7-day snapshot window, so on most days nothing changes. Each run goes through the full pipeline and the tests; if data changed, it commits `data/raw`, `data/answers` and `site/data` as `data: refresh YYYY-MM`, and redeploys the site.

When a new month becomes complete and `site/articles/YYYY-MM.md` doesn't exist yet, the workflow opens an issue titled "Write the <Month YYYY> column". The column is written and fact-checked by agents outside CI, then merged, which deploys it.

If the workflow misses a week and classify refuses to run, run it by hand with `--month YYYY-MM` for the missed month and push the answers.
