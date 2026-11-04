# Architecture

The contracts here are shared by every module. Change them here first, then in code.

## Layout

```
src/sejr/
  cli.py            `sejr <command>` entry point (fetch, ats, normalize, features, classify, aggregate, external, export; also validate, unanswered)
  fetch.py          Algolia → data/raw
  ats.py            company job boards (Greenhouse, Ashby, Lever, SmartRecruiters) → data/external/ats
  normalize.py      data/raw → DuckDB threads/posts/replies
  features/         deterministic answers (regex, vocab, joins) → answers table
  classify/         Jev questions → answers table
  aggregate.py      answers → monthly_metrics, point-in-time
  external.py       Indeed Hiring Lab and BLS benchmarks → data/external, one value per HN month
  export.py         monthly_metrics + data/external → site/data/*.json
  noise.py          point-in-time noise bars attached to every exported point
data/raw/           gzipped API responses, committed, never edited
data/sejr.duckdb    rebuildable from data/raw, gitignored
data/cache/jev/     cached Jev responses keyed by request hash, gitignored
data/answers/       Jev answers as Parquet, committed (the durable record)
data/external/      outside benchmark values per HN month, committed
data/cache/external/ blobless mirrors of the hiring-lab repos, gitignored
data/external/ats/  monthly job-board snapshots and the fixed board panel, committed
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

## Job-board snapshots: `data/external/ats/`

`sejr ats` runs after normalize, once per calendar month (it skips when a snapshot for the current month exists). It reads the public job-board JSON of two sets of boards:

- **HN boards:** every Greenhouse (`boards.greenhouse.io`, `job-boards.greenhouse.io`, including iframe and script embeds that name the board in `?for=<slug>`), Ashby (`jobs.ashbyhq.com`), Lever (`jobs.lever.co`) and SmartRecruiters (`jobs.`/`careers.smartrecruiters.com`) link in the in-snapshot posts of the latest 3 complete hiring threads. The snapshot's `hn_months` lists those thread months, whether or not each linked a board. Three months lets a later snapshot ask whether a company that posted in month *t* is still hiring at *t*+3. EU-hosted Greenhouse and Lever boards use other API hosts and are not matched.
- **Panel:** `panel.json`, about 40 US software companies whose boards were checked live on these ATSs. Membership changes only by explicit edit. A run uses the entries with `added <= snapshot date < removed`; retire an entry by setting `removed` rather than deleting it, so the panel's history stays readable. Google, Meta, Apple, Microsoft, Amazon and Netflix run their own careers sites, so the panel has no big tech; the planned SEC filings panel (CON-174) covers them.

Each board carries `scope`: `company` by default, `portfolio` for a VC or aggregator board that lists jobs at many companies. Scopes other than `company` are set by hand in `overrides.json` (`{"scope": {"<ats>/<slug>": "portfolio"}}`). Boards whose jobs are mostly outside the US stay in the snapshot. Export will count each board's US-located jobs from job locations (`ats.us_jobs`: us, non_us, unknown) every time it runs; the count is never stored, so a location-parser fix applies to every past snapshot. Locations that name no country ("Remote", "North America", "N/A") and places on neither list count as unknown, not non-US. Any US name, state name or city wins, so a multi-city string with a US office counts as US ("Remote - US or Canada", "San Francisco, CA; Toronto, Canada"); then Canada by name, city or province code ("Toronto, ON, CA" and "Toronto, CA" are Canada, not California); then case-sensitive state codes after a separator ("Remote - TX", "Austin (TX)"; a leading code such as "CA-Ontario-Toronto" or "IN-Bangalore" is a country prefix, not a state); then a list of non-US countries and cities.

Requests are 1 s apart with the User-Agent `software-engineering-job-report (github.com/thomasconner/software-engineering-job-report)`, a 20 s timeout and 2 attempts per request; only this client follows redirects (moved boards). Board statuses: `not_found` (404/410), `http_<code>` (any other 4xx), `unreachable` (no response), `error` (5xx or 429 after retries, or a bad payload), `empty` (SmartRecruiters answers 200 with no jobs for unknown companies), `ok`. One bad board never stops the run, but the run stops without writing after 10 unreachable boards in a row (our network, not theirs), and writes nothing when more than 20% of boards failed (`unreachable`, `error`, any `http_<code>`; a 404 or 410 is a real answer), because a half-fetched snapshot would read as a hiring drop. `--limit` fetches and prints but never writes. The workflow step has a 20-minute timeout and `continue-on-error`, so a failure never blocks the HN refresh; the next day's run retries.

Each run writes `<YYYY-MM-DD>.json.gz` (compact JSON, gzip mtime 0):

```json
{"snapshot_date": "2026-11-04", "generated_at": "...", "classifier": "eng-3", "hn_months": ["2026-08", "2026-09", "2026-10"],
 "boards": [{"ats": "ashby", "slug": "livekit", "sources": ["hn:2026-08", "panel"], "scope": "company", "fetched_at": "...", "status": "ok",
             "total_jobs": 31, "engineering_jobs": 18, "workplace_jobs": {"remote": 22, "hybrid": 3, "onsite": 4, "unknown": 2},
             "jobs": [{"id": "...", "title": "...", "department": "R&D", "team": "Engineering", "location": "...", "workplace": "remote", "published": "..."}]}]}
```

Per job only id, title, department, team, location, workplace and the published/updated timestamps the ATS provides (missing fields are omitted). No descriptions or other job text: they are large, copyrighted by the employer, and the report publishes counts, not postings. Slugs are lowercased except SmartRecruiters company ids, which are case-sensitive. Greenhouse jobs come from the `/departments` endpoint (the job list has no department); the department is stored with its parents, `Engineering > Software Engineering`, and a job listed under two departments is kept once, under the deeper one.

`workplace` is `remote`, `hybrid`, `onsite` or absent (the board doesn't say). The ATS's own field wins: Ashby `workplaceType` (its `isRemote` only when `workplaceType` is missing, because Ashby sets `isRemote` on hybrid jobs too), Lever `workplaceType`, SmartRecruiters `location.remote`/`hybrid`. Otherwise the location text decides: remote, distributed or anywhere beats hybrid, which beats onsite/in-office; a plain city says nothing. Greenhouse has no field, so most of its jobs are unknown; compare workplace shares across ATSs only over jobs whose workplace is known.

The snapshot is point-in-time by construction: a file holds what the boards showed on its date. There is no history before the first run (2026-11-04).

**Engineering classifier** (`ats.is_engineering`, version `eng-3` in the snapshot): engineering means software engineering, including infra, SRE, security, data and ML engineering, firmware, QA automation, research engineers and engineering managers. It reads the title first: a customer-facing role word right before the role (Sales, Solutions, Field, Support, Customer Engineer or Architect) or "Specialist" is out, whatever software words follow ("Solutions Engineer, ML Platform"); other engineering disciplines and customer-facing engineer titles (sales, GTM, solutions, support, implementation) are out unless the title also names software work (software, backend, platform, ML, SRE, research engineer, ...); non-engineering roles (recruiting, product and program management, design, scientists, analysts, curriculum or business developers) are out unless the title is a software engineering title, so "Backend Engineer | Accounting" is in; a "Systems" title with no software word is in only when its department is a software, engineering or infrastructure one and not systems engineering, hardware, vehicles or IT (Cloudflare's "Systems Engineer" in Engineering is in; Fuel, IT, Financial and Business Systems Engineers are out); software words include languages and areas such as C++, Rust, Go(lang), operating systems, networking, DNS and SDKs; titles naming software work are in; a bare "Engineer" or "Architect" is in unless its department names a non-software function. Labeling calls: forward-deployed engineers are in; GTM engineers, IT support engineers, go-to-market deployment engineers and manual testers are out; "Member of Technical Staff" is in unless the title names hardware or a non-engineering area. `tests/fixtures/ats/engineering_labels.jsonl` holds 150 titles from the first snapshot, labeled by hand before the rule was tuned: 96.7% untuned, 98% with `eng-1` through `eng-3` (precision 0.96, recall 0.98). `engineering_labels_heldout.jsonl` holds 100 titles labeled independently by a reviewer and never used for tuning: `eng-2` 97%, `eng-3` 98% (precision 0.95, recall 1.0). Tests keep both at or above 95%. Jobs keep title and department, so a rule change can reclassify old snapshots.

Not exported yet: `metrics.json` has no ATS section until there are enough snapshots to compare.

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

## External benchmarks

Outside series sit next to HN series so a column can say whether HN's thread moves with the wider market. Every series carries a `country` (ISO 3166 alpha-2: `US`, `GB`, …), so a US vs UK comparison needs no new contract. Keys are `<name>.<country>`.

| key | publisher | source | unit |
|---|---|---|---|
| `indeed_software_postings.US`, `.GB` | Indeed Hiring Lab (CC BY 4.0) | `hiring-lab/job_postings_tracker` `<CC>/job_postings_by_sector_<CC>.csv`, Software Development, `total postings` | index, Feb 1 2020 = 100 |
| `indeed_software_remote_share.US`, `.GB` | Indeed Hiring Lab | `hiring-lab/remote-tracker` `remote_postings_sector.csv`, software sector | share |
| `indeed_software_pay_transparency.US` | Indeed Hiring Lab | `hiring-lab/pay-transparency` `pay-transparency-sector.csv`, Software Development. US only: the file has no GB rows | share |
| `jolts_{openings,hires,layoffs}_information.US` | BLS (public domain) | `JTU510000000000000JOL/HIL/LDL`; ALFRED `JTU5100JOL/HIL/LDL` | thousands |
| `jolts_{openings,hires,layoffs}_professional.US` | BLS | `JTU540099000000000JOL/HIL/LDL`; ALFRED `JTU540099JOL/HIL/LDL` | thousands |
| `ces_computer_systems_design.US` | BLS | `CES6054150001` (same id on ALFRED) | thousands |

Indeed comes from its GitHub repos, never FRED: FRED's copies of Indeed need Indeed's pre-approval, and FRED's terms forbid archiving. Hiring Lab files name the software sector either `Software Development` or `techsoftware`, and versions alternate between the two (the remote tracker went `Software Development` → `techsoftware` → `Software Development` → `techsoftware` between 2024 and 2025), so every reader accepts both; a version with no matching rows prints a warning. Pay transparency, the remote share and JOLTS are not seasonally adjusted (`seasonally_adjusted: false`); the postings index and CES are. Only JOLTS is flagged `smooth_12m`: its counts swing with the seasons, while the remote and pay shares move little by season and have too short a history to give up a year to smoothing. JOLTS uses the unadjusted (`JTU`) series because ALFRED has no seasonally adjusted vintages for information or for professional-services layoffs; current pulls and vintages must be the same series.

**As-of date.** Month *t* may use only values published by its as-of date: the hiring thread's `created_at` + 8 days, as a UTC date. Every stored value has `vintage_date <= as_of`; export drops any that doesn't, and `tests/test_external.py` checks it.

**Vintages.**

- Indeed: the file at the newest commit on the default branch's first-parent line (`git log --first-parent`, UTC committer date) on or before the as-of date that has a reading for the country. Hiring Lab lands many updates through pull requests, and a branch commit is dated when it was written, not when it reached the default branch; the merge commit's date is when it was published, so the file is read at that first-parent commit. This needs git 2.31 or later, where `--first-parent` also diffs merges against their first parent; with an older git, merges drop out of the path-limited log. (Using branch commit dates leaked six values, in 2022-09, 2024-09 and 2026-06, by one to three days.) Git history is the vintage record. Months whose as-of date precedes a file's first commit on the default branch get no value, never a revised one: the postings series starts June 2021 (sector files reached main 2021-05-27), remote October 2024 (the first file reached main 2024-09-12), pay transparency September 2025. January 2025 has no remote value: the November 2024 file had no country column and the older one is too stale.
- BLS: while today is on or before the as-of date, the BLS API v2 (one POST for all seven series; `BLS_API_KEY` raises the keyless 25 queries/day limit), with `vintage_date` = the pull date. After it, the ALFRED vintage in effect on the as-of date (`alfredgraph.csv?id=<FRED id>&vintage_date=<as_of>`), with `vintage_date` = the as-of date. Only the one value per month is stored.

**One value per month.** Indeed's postings and remote series are daily 7-day trailing averages. Month *t* takes the reading dated on or before the thread's window end (`created_at` + 7 days); when the file reaches that day, the reading is exactly the mean over the thread's 7 days, so the benchmark covers the same week as the posts. Usually the file lags a few days (postings) or to the previous month end (remote), and `ref_period` says which day was used. Readings more than 31 days (postings) or 75 days (remote) older than the window end mean the file stopped updating, and the month gets no value. Pay transparency is monthly: the newest month on or before *t*. BLS: the newest month in the vintage, usually *t*−1 (CES) or *t*−2 (JOLTS). The value is plotted at HN month *t*, as known then.

**Storage.** `data/external/<source>/<YYYY-MM>.json`, `source` = `indeed` | `bls`:

```json
{"month": "2026-10", "as_of": "2026-10-09", "fetched_at": "2026-11-04T15:19:31Z",
 "values": {"indeed_software_postings.US": {"value": 78.33, "ref_period": "2026-10-02",
   "vintage_date": "2026-10-06", "source_url": "https://raw.githubusercontent.com/hiring-lab/job_postings_tracker/<sha>/US/job_postings_by_sector_US.csv"}}}
```

A file pulled after its as-of date is frozen and never pulled again, unless it records `missing`: BLS series with no value although the as-of date is past the first ALFRED vintage (2011-04-09). Those months stay open and the next run retries; asking ALFRED for the same vintage date is idempotent. A 404 from ALFRED counts as "no value" only before that first vintage; after it, it is an error. Indeed gaps come from git history and can't change on a retry, so they don't keep a month open, but a series that had a value the month before and has none now prints a warning. If a source fails outright (network, API error), `sejr external` prints a `::warning::`, skips that source for the rest of the run and leaves its months unfrozen; the step never blocks the HN refresh. Before the as-of date, each run rewrites a file only when a value changed. `sejr external` refuses to pull more than three months unless `--backfill` (or `--month`) is given; the backfill is resumable (it skips frozen months) and sends at most one request a second with the project's User-Agent.

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
| `years_required_median` | hiring | regex | median of each post's fewest stated years of experience, among posts that state any; n = those posts; unit `years` |
| `years_required_share` | hiring | regex | share stating a number of years of experience |
| `degree_required_share` | hiring | regex | share that require or prefer a degree, with no "or equivalent experience" |
| `degree_optional_share` | hiring | regex | share that say a degree is optional ("or equivalent experience", "no degree required") |
| `post_length_median` | hiring | count | median characters per live post (HTML stripped); unit `count` |
| `interview_style_share` | hiring | regex | share naming at least one `interview_style` |
| `office_days_share` | hiring | regex | share stating a number of in-office days a week |

Breakdowns (`category` set, values sum to ~1 per month):

| metric | method | categories |
|---|---|---|
| `work_mode` | jev | remote, hybrid, onsite, unclear |
| `seniority` | jev | junior, mid, senior, staff_plus, unspecified. The modal level of the individual-contributor engineering roles; management roles excluded; "all levels" = unspecified |
| `industry` | jev | ai_ml, devtools_infra, fintech, health, climate_energy, security, commerce, media_consumer, enterprise_saas, hardware_robotics, other, unstated. `other` = described but no listed sector fits; `unstated` = the post doesn't say what the company does. Export also publishes shares renormalized over posts whose sector is known |
| `funding_stage` | jev | bootstrapped, seed, series_a, series_b, series_c_plus, public_or_large, venture_unspecified, unknown. `seed` needs an explicitly named pre-seed/seed/angel round; an accelerator batch tag alone (e.g. "YC W12") is `unknown`; investors or amounts without a named round are `venture_unspecified` |
| `stack` | vocab | one category per term in `features/vocab.py`; share of posts mentioning it (does not sum to 1) |
| `stack_<group>` | vocab | the `stack` terms of one group: `language`, `framework`, `database`, `cloud_devops`, `data`, `ai_ml`, `mobile`. Same shares and category ids as `stack` |
| `benefits` | regex | equity, retirement, health_insurance, dental_vision, unlimited_pto, pto_days, parental_leave, four_day_week, learning_budget, remote_stipend, relocation, sign_on_bonus, bonus, visa; share of posts offering each (does not sum to 1) |
| `years_required` | regex | 0_2, 3_4, 5_7, 8_plus: the post's fewest stated years, among posts stating any (sums to 1) |
| `interview_style` | regex | take_home, no_leetcode, pair_programming, paid_trial; share of posts naming each (does not sum to 1) |
| `region` | regex | us, canada, uk, europe (non-UK), india, latam, asia_pacific, africa_mideast, unknown. Hiring posts; the header can name several regions, so shares do not sum to 1. Live posts |
| `seeker_region` | regex | same categories, one per seeking post (sums to 1). Live posts |

## What employers ask for (features-4)

Regex and vocabulary rules on the hiring post's own text, applied to every month (spec rule 5), so each answer is point-in-time by construction.

**Stack groups.** Every term in `features/vocab.py` belongs to one group (`GROUP_TERMS`). The 45 features-3 terms keep their rules exactly, so their answers don't move. The 62 added terms take the same care with ambiguous words: a first name, a season or an English word (Julia, Cassandra, Spring, Express, Chef, Puppet, Helm, Nomad, Jenkins, Prometheus, Solidity, JAX, dbt) needs a tech list or technical words within 80 characters. A term that is also a company (Snowflake, Datadog, Databricks, OpenAI, Grafana, Vercel, Cloudflare and others carry a `company` key) never counts in that company's own post (its header company name contains the key). It also doesn't count after a business cue earlier in the sentence (ex-, former, backed by, raised from, investors, customers, acquired, founded, comes from), before "CEO", "founders" or "alumni", or as an analogy ("building Vercel for AI"). No added term counts inside the header's company field (the header up to its first separator, when it opens with a company name), so "Green Chef | Engineer" is not Chef. "Cloudflare" covers Workers, Pages and the CDN; "Vector databases" covers pgvector, vector DB or search and the named vector stores; "Elasticsearch" includes OpenSearch and ELK.

**Benefits.** Each benefit is a set of patterns. A match counts unless its clause negates it ("no equity", "we can't offer relocation") or a product phrase covers it (diversity, private or health equity; pension funds; software for 401(k)s; "help people get health insurance"; leave-request software). Vague phrases ("great benefits", "generous PTO") count as nothing, and `pto_days` needs a stated number of days or weeks. `visa` is `mentions_visa`, so `benefits.visa` equals `visa_share`. `bonus` excludes "bonus points" and "X is a bonus".

**Years and degrees.** `years_required` is the post's smallest stated number across its roles ("3-5 years" is 3, "5+ YOE" is 5). A bare "N years" counts only next to experience words; "N+ years", ranges and "N years of/in/with X" count on their own. Company age, runway, "in N years", the team's or the writer's own years ("our team has", "most of us have", "I've been"), maximums ("<= 2 years", "up to") and "4 year degree" never count. `degree` is `optional` when a degree mention is followed by "or equivalent experience" (or similar) or the post says one isn't needed, and `required` when the post asks for or prefers one (BS, MS, PhD, "CS degree", "degree in"). Team bios, students working toward a degree and idioms ("to an advanced degree") are not asks. The short forms BS, MS and BA are case-sensitive and need a field or "degree" after them.

**Post traits.** `office_days` is the fewest in-office days a week stated ("3 days a week in office", "hybrid (2 days/wk)", "in-office 3-4 days", "onsite Mon-Fri"); work-from-home days and four-day weeks are not office days. `interview_style` has `take_home` (an explicit take-home or homework assignment), `no_leetcode` (the post says it skips LeetCode, whiteboards, brainteasers or algorithm puzzles), `pair_programming` (only next to interview words, since "we pair program daily" describes the job) and `paid_trial` (a paid trial, a paid take-home, "we pay for your time"). Roles per post is not measured: role lists are free text (bullets, "Engineers (backend, frontend)", bare links), and no rule tried on the dev sample counted them reliably.

**Validation** (`tests/test_post_trends.py`; the fixtures in `tests/fixtures/post_trends/` keep only the lines the rules read). Rules were tuned on a seeded 240-post dev draw. Three other sets were labeled by hand before the rules ran on them: 120 random hiring posts (30 per era), 80 posts with a benefit, experience or interview keyword (20 per era), and the keyword sentences of 120 more posts (years, degree, office days, interview). First scores: benefits precision/recall 0.98/0.98 (random) and 1.00/0.90 (keyword); years stated precision 1.00, 0.93 and 0.95 with recall 1.00 on all three sets, and the smallest number exact in every post both found; degree accuracy 98–99%. Seven general misses found there were then fixed, so these sets are partly in-sample. Current scores: benefits 1.00/0.98 (random) and 1.00/0.92 (keyword, where visa is 9 of 12 under the shared `visa_share` rule and health insurance 8 of 10); years 0.97/1.00; degree and office days 100%; interview style precision 1.00 and recall 0.67 (a "small programming assignment" is not called a take-home). Stack precision was judged on 30 matches per group drawn across all terms (30/30 except database and data at 29/30, both features-3 terms: "the founder of MongoDB" and a company named Spark) and on 20 per group from the added terms (20/20 except ai_ml 19/20 and cloud_devops 18/20 before the analogy, "raised from" and Chef Robotics rules). Tests hold floors: benefits precision 0.95 and recall 0.85, years 0.9, degree 97%, stack 0.9 per group.

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

Scalar keys are `<metric>.<kind>`. Each metric and breakdown carries `polarity`: `1` when a rise is good news for job seekers, `-1` when bad, `0` when neutral; the exporter owns it. `pending` lists months whose snapshot is not complete; the site never shows a pending month (series end at the last complete month, and the newest article is for that month). Each metric and breakdown also carries `sources`: the thread kinds it draws on (e.g. `["hiring","seeking"]` for `seekers_per_post`), used for the chart source line. `n` is the number of posts the value is computed from (for salary medians: posts with a parsed salary). `bar` is the noise bar for the change into that point from 3, 12 and 60 months earlier (keys `3m`, `1y`, `5y`; a key is missing when the earlier month isn't in the series or its bar can't be computed). For `share` and `score` it bounds the absolute difference; for `count`, `ratio` and `usd` it bounds |ln(now / then)|, so a rise is noise under e^bar − 1 and a fall under 1 − e^−bar. Breakdown points nest it by window, then category. `noise.py` computes it as 1.96 × √(2s² + v_then + v_now): v is each month's sampling variance and s² the series' extra month-to-month variance, estimated from neighbor residuals using only months up to that point. `removed_share` has none; `usd` bars use the bootstrap alone; `score` bars have a 0.2 floor. The file is written compactly (no indentation). See docs/style-guide.md, "The noise bar". The mock file adds `"mock": true` and `"note"`. `unit` is one of `count`, `share`, `usd`, `ratio`, `score`, `years`. `years` bars, like `usd`, bound |ln(now / then)| and use the bootstrap of the median alone (whole years tie across months the way round salaries do); `post_length_median` (unit `count`) takes a bootstrap of the median instead of the Poisson variance, plus the neighbor-residual s². Breakdowns may carry `description` (how to read the shares, e.g. that they don't sum to 1) and `category_labels` (display names for category ids, which the site prefers over its own list). Months with no data are omitted from `series`, never null-filled.

`external` (additive) holds the outside benchmarks, keyed by `<name>.<country>`, one entry for every series in the External benchmarks table, even when its series is empty:

```json
"external": {
  "indeed_software_postings.US": {
    "id": "indeed_software_postings.US", "label": "Indeed US software development job postings",
    "country": "US", "publisher": "Indeed Hiring Lab", "credit": "Indeed Hiring Lab, job postings tracker",
    "license": "CC BY 4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/", "seasonally_adjusted": true,
    "unit": "index", "description": "…", "source_url": "https://github.com/hiring-lab/job_postings_tracker",
    "series": [{"month": "2026-10", "value": 78.33, "ref_period": "2026-10-02", "vintage_date": "2026-10-06"}]
  }
}
```

`month` is the HN month (complete months only); `ref_period` is the day (`YYYY-MM-DD`) or month (`YYYY-MM`) the publisher's number describes. External units are `index`, `share` (0–1) or `thousands`. Every description ends by saying values are as first published and later revisions are not applied, so a chart note can repeat it.

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

::chart{type="line" metric="posts.hiring" external="indeed_software_postings.US" base="2022-01" from="2022-01"}
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
| `external` | line | one key from metrics.json `external`, paired with the chart's single `metric`. Needs `base` |
| `base` | line with `external` | `YYYY-MM`; both lines are indexed to 100 at this month. A benchmark with `smooth_12m: true` (JOLTS) is drawn as a 12-month trailing average (months without 12 consecutive values drop out), and the subtitle says so. The average runs over 12 HN months, not 12 reference months: each HN month carries the newest value published by its as-of date, so a reference month can appear twice or not at all (over JOLTS' 188 months, 33 repeat and 34 are skipped). The tooltip shows "12 months to <ref_period>" for a smoothed point. The source line adds the publisher's credit, a link to its license, and what this report changed ("indexed to Jan 2022 = 100 by this report") |
| `title` | all, including ::compare | required; the finding, stated |
| `subtitle` | all | optional; defaults to the metric label + date range |
| `note` | all | text after the source line |

`bar` with a breakdown draws horizontal bars at the issue month; with a scalar metric it draws monthly columns (default: the last 24 months). `stack`, `stack_<group>`, `benefits`, `interview_style` and `region` must not be drawn as `stacked-area` (their shares don't sum to 1, even when a month's happen to stay under 1).

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
| `benefits`, `interview_style` | regex | hiring only, one row per post; `probabilities` holds the categories found, `value` their count |
| `years_required` | regex | hiring only, one row per post: `value` = fewest stated years, `label` = its bucket; both NULL when none is stated, so the share counts every post |
| `degree` | regex | hiring only, `label`: `required`, `optional` or `none` |
| `office_days` | regex | hiring only, `value` = fewest in-office days a week stated, NULL when none |
| `post_length` | count | hiring only, `value` = characters of `posts.text` |
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
