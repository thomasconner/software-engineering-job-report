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

1. **Fetch:** save raw thread JSON, gzipped, under `data/raw/<thread_id>/<fetched_at>.json.gz`. Never edited.
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

A hand-labeled reference set of about 200 posts, sampled across years. Each method is scored on accuracy and calibration (Brier score) before its output reaches the report.

## Point-in-time rules (no look-ahead)

1. **Fixed snapshot age.** Each month uses only posts and replies whose `created_at` is within **7 days** of the thread's creation. Every month, past or current, is measured at the same age.
2. **Cross-month features use only the past.** "New vs returning company", first appearance, rolling baselines, percentiles and z-scores are computed from months `<= as_of`. A test checks that computing month *t* from the full dataset gives the same output as computing it from data cut off at *t*.
3. **Classifiers see only the post text.** No dates, no company outcomes, no other months. Questions ask what the text says, not what the model knows about the company.
4. **Pinned model versions.** Jev versions are pinned (for example `jev-1.14.0`, not `jev-latest`) and stored on every answer. An upgrade reclassifies the full history, so one series never mixes versions.
5. **Fixed vocabularies apply to all months.** Adding a term (for example "agents") reruns every month. A zero in 2015 is a real zero.

### Known biases (stated on the report)

- Edited posts show their latest text, and deleted posts are missing (survivorship).
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

All months from April 2011, for both threads. This gives a 5-year comparison with deeper context (2020, the 2022–23 layoffs).

## The article

Each month is one article in `site/articles/YYYY-MM.md`, written like a newspaper data column: a headline that makes a claim, a dek, an argued lede, and sections where every claim sits next to the chart that backs it. Voice: a FiveThirtyEight-style analyst writing an opinion column, plain and confident, with honest uncertainty. The style guide is `docs/style-guide.md`.

Articles are written by an agent from the exported numbers, then fact-checked by a second agent. Every number in the text must match `site/data/metrics.json`.

## Decisions log

- 2026-11-04: Public repo `thomasconner/software-engineering-job-report`. Linear project P-CON-53 in Conner Technology.
- 2026-11-04: No Haiku. Salary and company name come from regex. Jev is the only model.
- 2026-11-04: Backfill from April 2011, both thread kinds. Snapshot age 7 days.
