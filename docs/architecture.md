# Architecture

The contracts here are shared by every module. Change them here first, then in code.

## Layout

```
src/sejr/
  cli.py            `sejr <command>` entry point (fetch, normalize, features, classify, aggregate, export; also validate, unanswered)
  fetch.py          Algolia → data/raw
  normalize.py      data/raw → DuckDB threads/posts/replies
  features/         deterministic answers (regex, vocab, joins) → answers table
  classify/         Jev questions → answers table
  aggregate.py      answers → monthly_metrics, point-in-time
  export.py         monthly_metrics → site/data/*.json
  noise.py          point-in-time noise bars attached to every exported point
data/raw/           gzipped API responses, committed, never edited
data/sejr.duckdb    rebuildable from data/raw, gitignored
data/cache/jev/     cached Jev responses keyed by request hash, gitignored
data/answers/       Jev answers as Parquet, committed (the durable record)
site/               static GitHub Pages site (index.html + assets + data/)
site/articles/      one Markdown article per month, YYYY-MM.md
tests/
```

Run everything with `uv run sejr <command>`. Tests: `uv run pytest`.

## Raw storage

`data/raw/<kind>/<YYYY-MM>/<thread_id>.json.gz`: the Algolia `items/<id>` response, unmodified, plus a sidecar `<thread_id>.meta.json` with `{thread_id, kind, month, title, fetched_at, source_url}`.

`kind` is one of `hiring` ("Ask HN: Who is hiring?") or `seeking` ("Ask HN: Who wants to be hired?"). Freelancer threads are ignored.

`month` is the month named in the title, not the creation date.

One file per thread; a re-fetch overwrites it only when content changed, and git history keeps earlier versions. The sidecar also records `checked_at` (last fetch, changed or not) and the thread's Firebase `kids` list, used to count removed posts.

## DuckDB schema

```sql
CREATE TABLE threads (
  thread_id   BIGINT PRIMARY KEY,
  kind        VARCHAR NOT NULL,          -- 'hiring' | 'seeking'
  month       DATE NOT NULL,             -- first day of the named month
  title       VARCHAR NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL,
  snapshot_at TIMESTAMPTZ NOT NULL,      -- created_at + 168 hours (computed in UTC)
  fetched_at  TIMESTAMPTZ NOT NULL,      -- last fetch whose content was stored or confirmed unchanged
  removed_in_snapshot INTEGER,           -- top-level comments (Firebase kids) in the window that Algolia omits as deleted/dead
  UNIQUE (kind, month)
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

A month is complete only when its thread's `fetched_at >= snapshot_at`. Aggregate skips incomplete months (the export lists them as `pending`).

Raw files freeze once complete: fetch re-fetches a thread only while its stored `fetched_at < snapshot_at`. Later edits and deletions never change a published month.

`aggregate.compute_month(con, t)` must return the same rows whether the database holds all months or only months `<= t`. `tests/test_point_in_time.py` enforces this.

## Metric ids

Scalar metrics (`category = ''`). Shares are 0–1. Jev-based shares are expected values (sums of probabilities divided by n).

| metric | kind | method | meaning |
|---|---|---|---|
| `posts` | hiring, seeking | count | top-level posts submitted in the snapshot window, including ones later deleted or removed (posts + removed_in_snapshot). Live counts depend on how long after the window a thread was fetched; submitted counts don't |
| `removed_share` | hiring, seeking | count | removed_in_snapshot ÷ (posts + removed_in_snapshot); shown in methodology |
| `seekers_per_post` | hiring | count | submitted seeking posts ÷ submitted hiring posts, same month |
| `seekers_per_post_us` | hiring | regex | `seekers_per_post` × (share of live seeking posts with a known region that are `us`) ÷ (share of live hiring posts with an `open_to_us` answer that are open): US seekers per US-open hiring post on the submitted basis. n = live hiring posts open to US workers. Not emitted under 50 located seekers. See the note on removed posts below |
| `seeker_us_share` | seeking | regex | share of seeking posts with `region = us`, among those whose region is known; n = known-region posts |
| `replies_per_post` | hiring | count | mean direct replies per post |
| `salary_disclosed_share` | hiring | regex | share with a parseable salary |
| `salary_min_median_usd` | hiring | regex | median lower bound, USD annual, among disclosed |
| `salary_max_median_usd` | hiring | regex | median upper bound |
| `remote_token_share` | hiring | regex | REMOTE in the header line |
| `onsite_token_share` | hiring | regex | ONSITE in the header line |
| `visa_share` | hiring | regex | mentions visa sponsorship |
| `new_company_share` | hiring | join | company not seen in any earlier month |
| `returning_company_share` | hiring | join | company also posted last month |
| `ai_native_share` | hiring | jev | Noul: the post describes its product as built on AI/ML |
| `new_grad_share` | hiring | jev | Noul: open to new grads / juniors |
| `seeker_mood` | seeking | jev | Score mean, 0 (discouraged) – 4 (upbeat) |
| `seeker_strained_share` | seeking | jev | mean of P(level 0) + P(level 1) of seeker_mood |
| `eng_leadership_share` | hiring | jev | Noul: the post hires engineering managers or leads |
| `interns_token_share` | hiring | regex | INTERN(S) keyword present |

Breakdowns (`category` set, values sum to ~1 per month):

| metric | method | categories |
|---|---|---|
| `work_mode` | jev | remote, hybrid, onsite, unclear |
| `seniority` | jev | junior, mid, senior, staff_plus, unspecified. The modal level of the individual-contributor engineering roles; management roles excluded; "all levels" = unspecified |
| `industry` | jev | ai_ml, devtools_infra, fintech, health, climate_energy, security, commerce, media_consumer, enterprise_saas, hardware_robotics, other, unstated. `other` = described but no listed sector fits; `unstated` = the post doesn't say what the company does. Export also publishes shares renormalized over posts whose sector is known |
| `funding_stage` | jev | bootstrapped, seed, series_a, series_b, series_c_plus, public_or_large, venture_unspecified, unknown. `seed` needs an explicitly named pre-seed/seed/angel round; an accelerator batch tag alone (e.g. "YC W12") is `unknown`; investors or amounts without a named round are `venture_unspecified` |
| `stack` | vocab | one category per term in `features/vocab.py`; share of posts mentioning it (does not sum to 1) |
| `region` | regex | us, canada, uk, europe (non-UK), india, latam, asia_pacific, africa_mideast, unknown. Hiring posts; the header can name several regions, so shares do not sum to 1. Live posts |
| `seeker_region` | regex | same categories, one per seeking post (sums to 1). Live posts |

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
      "series": [{"month": "2026-11", "value": 312, "n": 312, "bar": {"3m": 0.342, "1y": 0.338, "5y": 0.329}}]
    }
  },
  "breakdowns": {
    "work_mode": {
      "label": "How companies want people to work",
      "method": "jev",
      "categories": ["remote", "hybrid", "onsite", "unclear"],
      "series": [{"month": "2026-11", "n": 312, "values": {"remote": 0.41, "hybrid": 0.22, "onsite": 0.31, "unclear": 0.06},
                  "bar": {"1y": {"remote": 0.095, "hybrid": 0.062, "onsite": 0.08, "unclear": 0.038}}}]
    }
  }
}
```

Scalar keys are `<metric>.<kind>`. Each metric and breakdown carries `polarity`: `1` when a rise is good news for job seekers, `-1` when bad, `0` when neutral; the exporter owns it. `pending` lists months whose snapshot is not complete; the site never shows a pending month (series end at the last complete month, and the newest article is for that month). Each metric and breakdown also carries `sources`: the thread kinds it draws on (e.g. `["hiring","seeking"]` for `seekers_per_post`), used for the chart source line. `n` is the number of posts the value is computed from (for salary medians: posts with a parsed salary). `bar` is the noise bar for the change into that point from 3, 12 and 60 months earlier (keys `3m`, `1y`, `5y`; a key is missing when the earlier month isn't in the series or its bar can't be computed). For `share` and `score` it bounds the absolute difference; for `count`, `ratio` and `usd` it bounds |ln(now / then)|, so a rise is noise under e^bar − 1 and a fall under 1 − e^−bar. Breakdown points nest it by window, then category. `noise.py` computes it as 1.96 × √(2s² + v_then + v_now): v is each month's sampling variance and s² the series' extra month-to-month variance, estimated from neighbor residuals using only months up to that point. `removed_share` has none; `usd` bars use the bootstrap alone; `score` bars have a 0.2 floor. The file is written compactly (no indentation). See docs/style-guide.md, "The noise bar". The mock file adds `"mock": true` and `"note"`. `unit` is one of `count`, `share`, `usd`, `ratio`, `score`. Months with no data are omitted from `series`, never null-filled.

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

Chart types: `line`, `bar`, `stacked-area`, `small-multiples`, `slope` (two months compared), `dot` (now vs past per category).

Directive attributes:

| attribute | applies to | meaning |
|---|---|---|
| `metric` | all charts | one metric key, or a comma list for multi-series lines |
| `breakdown` | stacked-area, small-multiples, slope, dot, bar | breakdown id |
| `categories` | breakdown charts | comma list; a subset of the breakdown's categories |
| `highlight` | multi-series charts | comma list of series drawn in the story color; the rest gray |
| `from`, `to` | time-series charts | YYYY-MM bounds of the default view |
| `vs` | slope, dot | the past point: `3m`, `1y`, `5y`, or `YYYY-MM`; default 5y on slope, 1y on dot |
| `months` | slope | two explicit months, `"2021-10,2026-10"`; overrides `vs` |
| `against` | ::compare | comma list of windows, default `3m,1y,5y` |
| `annotate` | time-series charts | `YYYY-MM:Label`, several separated by `;` |
| `title` | all, including ::compare | required; the finding, stated |
| `subtitle` | all | optional; defaults to the metric label + date range |
| `note` | all | text after the source line |

`bar` with a breakdown draws horizontal bars at the issue month; with a scalar metric it draws monthly columns (default: the last 24 months). `stack` must not be drawn as `stacked-area` (its shares don't sum to 1).

A back issue clips every series to its front-matter `month`, so older issues never show later data.

Manifest: `site/articles/index.json` is `{"months": ["YYYY-MM", ...]}`, newest last. Files starting with `_` are samples and never listed.

Column schedule: `site/articles/schedule.json` is `{"publish_in": [1, ..., 12]}`, the calendar months that get a column. All twelve means monthly; `[3, 6, 9, 12]` means quarterly. Data still refreshes every month either way. The monthly workflow opens a "Write the column" issue, and the column-writer routine writes, only when `latest_month` is in the list. A column written after a skipped month covers everything since the previous column.

## Jev answers storage

- `industry` rows store the folded distribution: P(sector) = P(fits) × P(sector | Choice); P(other) and P(unstated) come from the companion Nouls. `confidence` is that of the stored label, or NULL.
- Noul rows have NULL `confidence`.
- `answers` holds one Jev version per post; classify replaces a post's Jev rows.
- Classify answers only in-snapshot posts of complete threads (`fetched_at >= snapshot_at`), so it always sees the frozen text.
- Durable copy: `data/answers/<model>/<YYYY-MM>.parquet` (one file per thread month, both kinds). Each row also carries `qset` (hash of model + questions for the kind) and `digest` (sha256 of the canonical request, including the post text); classify skips a post only when both match, so a question edit or a text change re-runs just the affected posts. Classify loads these before calling the API, so a fresh checkout reclassifies nothing. `sejr unanswered` prints the complete months that still have posts to classify. The response cache under `data/cache/jev/` is a local accelerator, sharded by the first two hex characters of the hash, and gitignored.

## Validation set

`data/labels/reference.jsonl`: about 240 posts stratified by era (2011–14, 2015–19, 2020–22, 2023–26) and kind, labeled independently. Each Jev question reports accuracy and Brier score per era before its metric is published; the export carries those scores per metric as `validation`.

## Sample posts: `site/data/samples/YYYY-MM.json`

Real posts the article may quote, so the column never invents color. Export writes, for each complete month, a deterministic sample (seeded by month) of up to 30 in-snapshot hiring posts and 20 seeking posts:

```json
{"month": "2026-11", "posts": [{"id": 50340012, "kind": "hiring", "url": "https://news.ycombinator.com/item?id=50340012", "header": "first line", "text": "first 600 characters", "answers": {"work_mode": "remote", "new_grad": 0.91}}]}
```

The writer may quote only from these files and must put the item id in the ledger. Quote job posts, not individual job seekers (seeking posts are used for paraphrase-free mood examples only when the person's name and contact details are removed).

## Question ids in `answers`

| question | method | stored as |
|---|---|---|
| `company` | regex | label: normalized company name |
| `salary_min_usd`, `salary_max_usd` | regex | value |
| `salary_currency` | regex | label: ISO code, `unknown` (bare k-range), or `none` (no salary found) |
| `remote_token`, `onsite_token`, `mentions_visa`, `interns_token` | regex | value 0/1 |
| `stack` | vocab | one row per post; `probabilities` holds the terms found |
| `region` | regex | hiring: one row per post, `probabilities` holds every region the header line names (`unknown` when none); seeking: `label` is the region of the first place on the `Location:` line (`unknown` when there is no line or no recognized place) |
| `open_to_us` | regex | hiring only, value 0/1: the header names a US place, or says remote with no region, a worldwide, North American, Americas or US-time-zone restriction. "REMOTE (EU)", "Berlin \| Remote" and "non-US" are 0. No row when the header names no place and doesn't say remote |
| `new_company`, `returned_from_last_month` | join | value 0/1; not emitted when no earlier (or previous-month) hiring thread exists |
| `work_mode`, `seniority`, `industry`, `funding_stage` | jev | Choice: label, probabilities (category → p), confidence |
| `industry_stated`, `industry_fits`, `ai_native`, `new_grad`, `eng_leadership` | jev | Noul: value |
| `seeker_mood` | jev | Score: value, probabilities keyed "0"–"4", confidence |

`salary_disclosed_share` counts any currency, including `unknown`; the salary medians use USD only.

Extra breakdowns: `industry_known` (sector shares among posts whose sector is stated), `seniority_ai_native` and `seniority_not_ai_native` (seniority shares among posts with ai_native ≥ 0.5 and < 0.5). Stack categories use display names ("C++", "Next.js", "AI agents").

Completeness is per thread: a month whose hiring thread is complete publishes hiring metrics even if its seeking thread is still pending; `seekers_per_post` and `seekers_per_post_us` need both.

Samples contain hiring posts only. Seeking posts are never exported.

Authoring mode (`?mock=1`, localhost) shows directive errors in red; readers see "This chart is unavailable". Samples (`_name.md`) load only with `?mock=1&issue=_name`.

`removed_share` depends on fetch age (history was fetched years later; new months at about day 8), so it is shown in the methodology only and never compared across months in an article. Shares (regex and Jev) are computed over live posts.

`seekers_per_post_us` needs each post's location, and removed posts have no text. Rather than count live posts, which would let each thread's removed share (a product of fetch age) move the ratio, it scales the submitted `seekers_per_post` by the US shares measured on live posts. This assumes removed posts have the same region mix as live ones. Both shares also leave out posts that say nothing about place: seekers with an unknown region, and hiring headers with no place and no "remote" (no `open_to_us` row). Treating those headers as not open would make the ratio drift by era, since their share of live hiring posts runs about 9–15% in 2011–15, 3.5–5% in 2017–22 and 6–8% in 2023–26. Both sides make the same assumption: unknowns split like the knowns. The US seeker count behind the noise bar is `seeker_us_share` × its n.
