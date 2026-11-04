# Software Engineering Job Report: spec

A monthly heartbeat on US startup and engineering hiring, built from Hacker News "Ask HN: Who is hiring?" and "Who wants to be hired?" threads. Published as a single-page report on GitHub Pages, written like FiveThirtyEight data journalism: each section leads with a finding, then shows the chart behind it.

## Goals

- Show trends over time, with direct comparisons: this month vs 3 months ago, 1 year ago and 5 years ago.
- Compute every month **as it looked at the time**, with no knowledge of later months, even though the backfill runs in November 2026.
- Keep yes/no measurements in code and use Jev only for judgment calls, so every number traces back to a method and a version.

## Non-goals

- A job board or search tool.
- A single composite "health score". Each measure is shown on its own.

## Sources

| Source | Use |
|---|---|
| Algolia `search_by_date?tags=story,author_whoishiring` | Discover monthly thread IDs back to April 2011 |
| Algolia `items/<id>` | Full comment tree per thread, with `created_at_i` per comment |
| Greenhouse / Lever / Ashby public job-board JSON | Current month only: open-role counts for linked companies (later phase) |

## Pipeline

1. **Fetch:** save raw thread JSON, gzipped, under `data/raw/<kind>/<YYYY-MM>/<thread_id>.json.gz`. A re-fetch overwrites only when content changed; git history keeps earlier versions.
2. **Normalize:** DuckDB tables `threads`, `posts` (top-level comments), `replies`.
3. **Derive:** table `answers(post_id, question, method, version, value, probabilities, confidence)`.
4. **Aggregate:** monthly series, computed with `as_of = month`.
5. **Publish:** export series to JSON, build the static page, deploy to GitHub Pages.

## Methods by question type

| Type | Examples | Method |
|---|---|---|
| Deterministic | Post count, `$` amount present, REMOTE/ONSITE token, "visa" mentioned, stack terms from a fixed list, new vs returning company | Python (regex, joins) |
| Judgment, fixed answers | Remote policy, seniority, industry, funding stage, AI-native | Jev `Choice` |
| Judgment, ordered scale | Applicant mood in "Who wants to be hired?", frustration in replies, hiring urgency | Jev `Score` |
| Judgment, yes/no but fuzzy | "Hires new grads?", "Mentions layoffs?" | Jev `Noul` |
| Free-text extraction | Salary min/max, company name from the header line | Python (regex). No LLM extraction: HN headers are regular enough, and it keeps Jev as the only model |

Monthly aggregates sum probabilities (expected counts) instead of counting top answers.

### Validation

A reference set of 265 posts labeled by two AI annotators with adjudication, plus an 88-post held-out set, sampled across years. Each method is scored on accuracy and calibration (Brier score) before its output reaches the report. AI labels can share the classifier's blind spots; see docs/research.md for the planned human-labeled sample.

## Point-in-time rules (no look-ahead)

1. **Fixed snapshot age.** Each month uses only posts and replies whose `created_at` is within **7 days** of the thread's creation. Every month, past or current, is measured at the same age.
2. **Cross-month features use only the past.** "New vs returning company", first appearance, rolling baselines, percentiles and z-scores are computed from months `<= as_of`. A test checks that computing month *t* from the full dataset gives the same output as computing it from data cut off at *t*.
3. **Classifiers see only the post text.** No dates, no company outcomes, no other months. Questions ask what the text says, not what the model knows about the company.
4. **Pinned model versions.** Jev versions are pinned (for example `jev-1.14.0`, not `jev-latest`) and stored on every answer. An upgrade reclassifies the full history, so one series never mixes versions.
5. **Fixed vocabularies apply to all months.** Adding a term (for example "agents") reruns every month. A zero in 2015 is a real zero.

### Known biases (stated on the report)

- Edited posts show the text as of the snapshot fetch. Deleted posts are missing. For hiring threads the removed share held at 5–7% through 2022 and reached 14% in 2026; seeking threads run 10–27% throughout. The post-count trend is shown alongside `removed_share`.
- HN skews toward US startups, engineering roles and the Bay Area.
- One post can cover many roles, so post count is not job count.

## Report (GitHub Pages, one page)

- Lede: three or four sentences on what moved this month.
- Comparison strip: now vs 3 months, 1 year and 5 years ago, for each headline measure.
- Sections, each with a headline finding and a chart:
  1. Demand: employer posts, job seekers per employer
  2. Remote, hybrid, onsite
  3. Pay: disclosure rate, ranges by seniority
  4. AI share of hiring
  5. Seniority mix and the entry-level squeeze
  6. Stack trends
  7. Company churn: new, returning, gone quiet
  8. Job-seeker mood
- Methodology and caveats footer.
- Design: `frontend-design` skill, with Mobbin as reference for the dashboard layout.

## Stack

- Python 3.12, uv, DuckDB, `typesafe-sdk`, httpx. Contracts in `docs/architecture.md`.
- Static page reading exported JSON. The charting library is chosen during the design ticket.
- GitHub Actions: a monthly job runs on day 8 after each thread (the day-7 snapshot is then complete), plus a manual trigger for backfills.

## Backfill

All months from April 2011 for "Who is hiring?"; "Who wants to be hired?" starts May 2014, when the thread began. This gives a 5-year comparison with deeper context (2020, the 2022–23 layoffs).

## The article

Each month is one article in `site/articles/YYYY-MM.md`, written like a newspaper data column: a headline that makes a claim, a dek, an argued lede, and sections where every claim sits next to the chart that backs it. Voice: a FiveThirtyEight-style analyst writing an opinion column, plain and confident, with honest uncertainty. The style guide is `docs/style-guide.md`.

Articles are written by an agent from the exported numbers, then fact-checked by a second agent. Every number in the text must match `site/data/metrics.json`.

## Decisions log

- 2026-11-04: Public repo `thomasconner/software-engineering-job-report`. Linear project P-CON-53 in Conner Technology.
- 2026-11-04: No Haiku. Salary and company name come from regex. Jev is the only model.
- 2026-11-04: Backfill from April 2011, both thread kinds. Snapshot age 7 days.
- 2026-11-04: Raw storage keeps one file per thread (architecture.md layout); git history is the version record.
- 2026-11-04: The Jev response cache (~126k files) is not committed. Jev answers are committed as Parquet under `data/answers/`, so CI only classifies new posts.
- 2026-11-04: Thread coverage: 188 hiring months (2011-04 to 2026-11, no gaps) and 151 seeking months (the thread started 2014-05). Four months use threads posted by other users; see `EXTRA_THREADS` in fetch.py.
- 2026-11-04: Months are complete only once fetched after the 7-day window; raw files then freeze. Removed posts are counted from Firebase and published as `removed_share` rather than added back into post counts (many are spam or rule-breaking posts).
- 2026-11-04: Reference set: 220 random posts (two AI annotators, kappa 0.92–1.00, 22 adjudicated) + 45 keyword-selected seeker posts. No outside knowledge of company size (Cisco subsidiaries = unknown). Seeker mood leads with seeker_strained_share; level 4 is unvalidated and never reported on its own.
- 2026-11-04: Post counts are submitted posts (live + removed within the window), because live counts depend on fetch age: history was fetched years after the window, new months at day 8. This reverses the earlier choice to keep removed posts out of counts. removed_share is methodology-only.
- 2026-11-04: The column is drafted by a scheduled Claude Code routine ("SEJR monthly column writer", trig_012tg7HejoUkmenRt2Q4sh3E, Opus) at 18:00 UTC on days 10–14. It exits unless the latest exported month has no article and no open PR. It writes, runs independent fact-check and reader-review subagents, and opens a PR on `column/<YYYY-MM>`; a human merges. The prompt lives in the routine (claude.ai/code/routines), not the repo.
- 2026-11-04: Column cadence is a setting, not code: `site/articles/schedule.json` lists the calendar months that get a column (all twelve for now). Data refreshes monthly regardless; the routine still fires days 10–14 every month and exits in unscheduled months.
- 2026-11-04: Adversarial research findings and the fix list live in docs/research.md. Columns describe HN's threads, not the US market, until outside benchmarks and a US-only ratio exist.
- 2026-11-04: Noise bars (CON-166) are exported per point as `bar` and drive the "≈" marker. Additive model: each month varies by its sampling variance (Poisson, binomial, bootstrapped salary median, mood variance) plus a series-wide extra variance s², estimated as the value that makes the median of r²/Var(r) match a chi-square(1) over the last 36 neighbor residuals at or before the point; fewer than 12 residuals → s² = 9 × sampling variance. Bars sit on ln(now/then) for counts, ratios and dollars. Chosen over the spread of k-month changes, which counts real trend as noise, and over a company-clustered bootstrap, which needs post-level resampling for every share and category; the neighbor check already catches clustering, and most shares come out near binomial. Salary bars are bootstrap-only (tied medians make residuals zero); mood bars have a 0.2 floor because classifier error isn't in them; all-zero share trios count toward the 12-residual minimum but not the estimate, which needs 6 residuals with movement.
- 2026-11-04: metrics.json is written compactly (no indentation): per-point noise bars took the indented file from 1.0 MB to 2.9 MB; compact is 1.3 MB.
