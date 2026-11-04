# Architecture

The contracts here are shared by every module. Change them here first, then in code.

## Layout

```
src/sejr/
  cli.py            `sejr <command>` entry point (fetch, normalize, features, classify, aggregate, export)
  fetch.py          Algolia → data/raw
  normalize.py      data/raw → DuckDB threads/posts/replies
  features/         deterministic answers (regex, vocab, joins) → answers table
  classify/         Jev questions → answers table
  aggregate.py      answers → monthly_metrics, point-in-time
  export.py         monthly_metrics → site/data/*.json
data/raw/           gzipped API responses, committed, never edited
data/sejr.duckdb    rebuildable from data/raw, gitignored
data/cache/jev/     cached Jev responses keyed by request hash, committed
site/               static GitHub Pages site (index.html + assets + data/)
site/articles/      one Markdown article per month, YYYY-MM.md
tests/
```

Run everything with `uv run sejr <command>`. Tests: `uv run pytest`.

## Raw storage

`data/raw/<kind>/<YYYY-MM>/<thread_id>.json.gz`: the Algolia `items/<id>` response, unmodified, plus a sidecar `<thread_id>.meta.json` with `{thread_id, kind, month, title, fetched_at, source_url}`.

`kind` is one of `hiring` ("Ask HN: Who is hiring?") or `seeking` ("Ask HN: Who wants to be hired?"). Freelancer threads are ignored.

`month` is the month named in the title, not the creation date.

A re-fetch writes a new file only when the content changed. The newest file wins in normalize.

## DuckDB schema

```sql
CREATE TABLE threads (
  thread_id   BIGINT PRIMARY KEY,
  kind        VARCHAR NOT NULL,          -- 'hiring' | 'seeking'
  month       DATE NOT NULL,             -- first day of the named month
  title       VARCHAR NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL,
  snapshot_at TIMESTAMPTZ NOT NULL       -- created_at + INTERVAL 7 DAY
);

CREATE TABLE posts (                      -- top-level comments only
  post_id     BIGINT PRIMARY KEY,
  thread_id   BIGINT NOT NULL,
  author      VARCHAR,
  created_at  TIMESTAMPTZ NOT NULL,
  text_html   VARCHAR NOT NULL,
  text        VARCHAR NOT NULL,          -- HTML stripped, entities decoded, paragraphs as \n\n
  in_snapshot BOOLEAN NOT NULL           -- created_at <= threads.snapshot_at
);

CREATE TABLE replies (                    -- every non-top-level comment
  reply_id    BIGINT PRIMARY KEY,
  post_id     BIGINT NOT NULL,           -- top-level ancestor
  parent_id   BIGINT NOT NULL,
  thread_id   BIGINT NOT NULL,
  author      VARCHAR,
  created_at  TIMESTAMPTZ NOT NULL,
  text        VARCHAR NOT NULL,
  depth       INTEGER NOT NULL,          -- 1 = direct reply to a post
  in_snapshot BOOLEAN NOT NULL
);

CREATE TABLE answers (
  post_id       BIGINT NOT NULL,
  question      VARCHAR NOT NULL,        -- e.g. 'work_mode', 'salary_min_usd', 'mentions_visa'
  method        VARCHAR NOT NULL,        -- 'regex' | 'vocab' | 'join' | 'jev'
  version       VARCHAR NOT NULL,        -- code version for deterministic, model id for jev (e.g. 'jev-1.14.0')
  value         DOUBLE,                  -- numeric answer, Noul probability, or Score position
  label         VARCHAR,                 -- categorical answer (top choice)
  probabilities JSON,                    -- full distribution for Choice/Score
  confidence    DOUBLE,
  PRIMARY KEY (post_id, question, method, version)
);

CREATE TABLE monthly_metrics (
  month    DATE NOT NULL,
  kind     VARCHAR NOT NULL,             -- thread kind the metric is about
  metric   VARCHAR NOT NULL,             -- metric id, see below
  category VARCHAR NOT NULL DEFAULT '',  -- '' for scalar metrics, the category for breakdowns
  value    DOUBLE,
  n        INTEGER,                      -- posts the value is based on
  PRIMARY KEY (month, kind, metric, category)
);
```

Empty-text, `[dead]` and `[flagged]` comments are dropped in normalize, and the count is logged.

## Point-in-time rule

Every metric for month *t* may read only:

- posts and replies with `in_snapshot = true` from threads with `month <= t`;
- answers for those posts.

`aggregate.compute_month(con, t)` must return the same rows whether the database holds all months or only months `<= t`. `tests/test_point_in_time.py` enforces this.

## Metric ids

Scalar metrics (`category = ''`). Shares are 0–1. Jev-based shares are expected values (sums of probabilities divided by n).

| metric | kind | method | meaning |
|---|---|---|---|
| `posts` | hiring, seeking | count | top-level posts in snapshot |
| `seekers_per_post` | hiring | count | seeking posts ÷ hiring posts, same month |
| `replies_per_post` | hiring | count | mean direct replies per post |
| `salary_disclosed_share` | hiring | regex | share with a parseable salary |
| `salary_min_median_usd` | hiring | regex | median lower bound, USD annual, among disclosed |
| `salary_max_median_usd` | hiring | regex | median upper bound |
| `remote_token_share` | hiring | regex | REMOTE in the header line |
| `onsite_token_share` | hiring | regex | ONSITE in the header line |
| `visa_share` | hiring | regex | mentions visa sponsorship |
| `new_company_share` | hiring | join | company not seen in any earlier month |
| `returning_company_share` | hiring | join | company also posted last month |
| `ai_native_share` | hiring | jev | Noul: the product is built on AI/ML |
| `new_grad_share` | hiring | jev | Noul: open to new grads / juniors |
| `seeker_mood` | seeking | jev | Score mean, 0 (discouraged) – 4 (upbeat) |

Breakdowns (`category` set, values sum to ~1 per month):

| metric | method | categories |
|---|---|---|
| `work_mode` | jev | remote, hybrid, onsite, unclear |
| `seniority` | jev | junior, mid, senior, staff_plus, unspecified |
| `industry` | jev | ai_ml, devtools_infra, fintech, health, climate_energy, security, commerce, media_consumer, enterprise_saas, hardware_robotics, other |
| `funding_stage` | jev | bootstrapped, seed, series_a, series_b, series_c_plus, public_or_large, unknown |
| `stack` | vocab | one category per term in `features/vocab.py`; share of posts mentioning it (does not sum to 1) |

## Export contract: `site/data/metrics.json`

```json
{
  "generated_at": "2026-11-09T12:00:00Z",
  "latest_month": "2026-11",
  "months": ["2011-04", "...", "2026-11"],
  "metrics": {
    "posts.hiring": {
      "label": "Companies hiring",
      "unit": "count",
      "method": "count",
      "description": "Top-level posts in the first 7 days of the thread",
      "series": [{"month": "2026-11", "value": 312, "n": 312}]
    }
  },
  "breakdowns": {
    "work_mode": {
      "label": "How companies want people to work",
      "method": "jev",
      "categories": ["remote", "hybrid", "onsite", "unclear"],
      "series": [{"month": "2026-11", "n": 312, "values": {"remote": 0.41, "hybrid": 0.22, "onsite": 0.31, "unclear": 0.06}}]
    }
  }
}
```

Scalar keys are `<metric>.<kind>`. `unit` is one of `count`, `share`, `usd`, `ratio`, `score`. Months with no data are omitted from `series`, never null-filled.

## Articles: `site/articles/YYYY-MM.md`

Markdown with front matter and chart directives. The site renders the newest article by default, with a month picker for older ones.

```markdown
---
month: 2026-11
headline: "Remote work is losing, but not where you'd think"
dek: "One-sentence standfirst under the headline."
byline: "Software Engineering Job Report"
---

Body paragraphs…

::chart{type="line" metric="posts.hiring" from="2019-01" annotate="2022-11:ChatGPT launches"}

::chart{type="stacked-area" breakdown="work_mode" from="2020-01"}

::compare{metrics="posts.hiring,seekers_per_post.hiring,salary_disclosed_share.hiring" against="3m,1y,5y"}
```

Chart types: `line`, `bar`, `stacked-area`, `small-multiples`, `slope` (two months compared), `dot` (now vs past per category). Every directive accepts `title` and `note`.
