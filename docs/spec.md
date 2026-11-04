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
| Greenhouse / Ashby / Lever / SmartRecruiters public job-board JSON | Monthly snapshot of boards linked from recent hiring posts plus a fixed panel (`sejr ats`, `data/external/ats/`); counts and job metadata, no job text |
| Indeed Hiring Lab GitHub repos (CC BY 4.0) | Benchmarks: software postings index and remote share (US, GB), pay transparency (US), each as published by the month's as-of date |
| BLS API v2 and ALFRED vintages (public domain) | Benchmarks: JOLTS openings/hires/layoffs (information; professional and business services) and CES computer systems design employment, US |
| SEC EDGAR submissions, XBRL company facts and filed documents (public) | Benchmarks from a ~50-company US public tech panel fixed each January: quarterly restructuring charges, monthly 8-K Item 2.05 layoff filings (panel and all SIC 7370–7374 filers), headcount change from 10-Ks, quarterly Meta/Alphabet/Amazon headcount from earnings releases (`sejr sec`, `data/external/sec/`) |

## Pipeline

1. **Fetch:** save raw thread JSON, gzipped, under `data/raw/<kind>/<YYYY-MM>/<thread_id>.json.gz`. A re-fetch overwrites only when content changed; git history keeps earlier versions.
2. **Normalize:** DuckDB tables `threads`, `posts` (top-level comments), `replies`.
3. **Derive:** table `answers(post_id, question, method, version, value, probabilities, confidence)`.
4. **Aggregate:** monthly series, computed with `as_of = month`.
5. **External:** one value per outside series per month, as published by the month's as-of date (thread + 8 days), under `data/external/`. SEC series use only filings accepted by that date.
6. **Publish:** export series to JSON, build the static page, deploy to GitHub Pages.

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
- 2026-11-04: Lessons loop: each column PR's first commit is the routine's untouched draft; the merged article is Thomas's edit. Before drafting, the routine diffs the previous routine PR's draft against main, records lessons in docs/editor-notes.md (with PR refs and counts), and proposes style-guide rules for lessons seen 2–3 times. Lesson changes ride in the column PR, so Thomas approves them by merging.
- 2026-11-04: Post region is a regex feature (features-3): a seeker's `Location:` line, a hiring post's header line (several regions allowed) plus `open_to_us`. Region is a general category, not a US flag, so UK/Europe comparisons can follow. `seekers_per_post_us` is `seekers_per_post` × the live US seeker share ÷ the live open-to-US hiring share, so it stays on the submitted basis (removed posts have no text and are assumed to share the live mix); both shares leave out posts that say nothing about place (unknown seekers; headers with no place and no "remote"), so unknowns are assumed to split like the knowns on both sides, and the ratio is withheld under 50 located seekers. It is checked before any seeker-ratio change is called large. Validation: 150 Location lines and 150 headers (seeded, stratified 2011–26) were labeled by hand blind to the regex, then the rules were tuned on them, so that set (tests/fixtures/region_sample.jsonl) is in-sample. A held-out set (tests/fixtures/region_heldout.jsonl: 190 Location lines and 200 headers, 2015–26) was drawn by an independent reviewer, whose labels were not saved; it was relabeled by hand blind to the regex before the second round of rules. That round targeted its misses (as general patterns, not single lines), so the held-out set is now partly in-sample too. A clean accuracy number needs a fresh third draw labeled before any further rule change. Both sets carry accuracy-floor tests (≥ 95% exact, US precision and recall ≥ 95%).
- 2026-11-04: Outside benchmarks (CON-167): Indeed Hiring Lab from its GitHub repos, BLS from the API with ALFRED vintages for history. Month t uses only values published by thread + 8 days. Indeed months before a file's first commit get no value rather than a revised one, so the postings benchmark starts June 2021. Daily Indeed series take the 7-day trailing average dated at (or just before) the thread's window end. JOLTS uses the unadjusted JTU series because ALFRED has no adjusted vintages for these industries. Every series carries a country for the planned US vs UK comparison.
- 2026-11-04: Review fixes to CON-167: Indeed vintages are dated by first-parent commits on the default branch (merge time), not branch commit dates; months missing an expected BLS value stay open; an outside-source failure only warns; unadjusted JOLTS is drawn as a 12-month trailing average on indexed charts (not Indeed's remote and pay shares, whose seasonality is minor and history short); every credit links its license and says what this report changed.
- 2026-11-04: Job-board snapshots start now because they have no history (CON-173). `sejr ats` runs once per calendar month after normalize and snapshots boards linked from the latest 3 complete hiring threads plus a fixed ~40-company US tech panel (`data/external/ats/panel.json`, edited only by hand, with added/removed dates). Stored per job: id, title, department, team, location, remote, dates; never descriptions. Engineering = software engineering, a deterministic title-first rule validated on hand-labeled titles. No metrics.json section until there are snapshots to compare. Workable, Rippling, Personio and EU-hosted boards are not covered.
- 2026-11-04: Job-board follow-ups: no big tech on the ATS panel (own careers sites); the SEC panel (CON-174) covers it. Boards keep a `scope` (`company`, or `portfolio` set in `data/external/ats/overrides.json`; pear-vc is the first). US-located job counts are computed at export from job locations, not stored. Western Digital leaves the panel for Asana (software only) on 2026-12-01. Workable is a follow-up ticket.
- 2026-11-04: Job-board review fixes (eng-2): per-job `workplace` (remote/hybrid/onsite/unknown) replaces the remote flag, because Ashby's isRemote includes hybrid; a run writes nothing when over 20% of boards fail or after 10 unreachable in a row; the first snapshot was re-fetched with these rules.
- 2026-11-04: Classifier eng-3: "Systems Engineer" is decided by department, customer-facing role words beat software words, and a reviewer's 100 independently labeled titles are a held-out test (98%). US location counts return unknown for unrecognized places. The 2026-11-04 snapshot's engineering counts were recomputed in place from stored titles (no re-fetch).
- 2026-11-04: SEC EDGAR panel (CON-174). Panel per calendar year, frozen from filings accepted before January 1: US-based 10-K filers in SIC 7370–7374 plus named big-tech CIKs in other codes (revised below), alive (a 10-K in the past 456 days, no Form 15 since its last report), top 50 by revenue as first filed. Revenue, not headcount, ranks the panel, because headcount is untagged and reading it for every candidate is too slow; the frames API (restated) only shortlists 100. Series start 2012-01, the first January after XBRL reached mid-size 10-Ks. Restructuring is `RestructuringCharges` else `SeveranceCosts1`, as first filed, for the latest calendar quarter at least four months back, summed over reporting companies (`n` published). Item 2.05 counts original 8-Ks only, for the panel and for every SIC 7370–7374 filer (bucketing and SIC source revised below). The all-filer count uses the nightly `submissions.zip` (1.6 GB, about 20 s to scan), downloaded only when a month is computed, rather than EFTS full-text search. Headcount comes from regex over 10-K text (published as the panel total and, because Amazon drives the total, the median company's change) (validated on 40 hand-labeled filings, then a 20-filing second draw) and from Meta, Alphabet and Amazon earnings releases. A month is computed only after its as-of date, so its first file is final. CI skips the step with a warning when the `SEC_USER_AGENT` secret is missing.
- 2026-11-04: SEC review fixes (CON-174). Restructuring reads six us-gaap tags, one per company-year by priority, takes a fourth quarter from a 10-K-only charge when the year's 10-Qs carried no tag, leaves out Meta (own XBRL element), is named "restructuring and other charges", publishes the top contributor and its share, and gains a count of companies with a charge. Panel headcount drops companies whose count moved by more than 0.3 in log terms (spin-offs, large acquisitions) and lists the matched companies per point. SIC is the code in each filing's header, never today's code: the all-filer Item 2.05 count checks every filing's header, and the panel checks each candidate's latest 10-K; candidates are still found from today's codes plus a short list of known reclassifications, which is a documented gap. The panel adds hardware (SIC 3570–3579) and semiconductors (3670–3679) by the same revenue rule; `NAMED` keeps only eight internet platforms no SIC captures (Amazon, Uber, Lyft, Airbnb, DoorDash, PayPal, eBay, Netflix), an editorial choice that uses hindsight. Month buckets use EDGAR's filing date. A sentence must score at least 1 to give a headcount.
- 2026-11-04: SEC re-review fixes (CON-174). Filing headers come from `<accession>.hdr.sgml`, which exists for every filing; the HTML index-headers page that an earlier version read 404s before mid-2014, and caching those 404s as blank codes had emptied the 2012–14 panels. Panel scope is one constant, `sec.PANEL_SCOPE`, defaulting to software and internet (7370–7374) plus chip companies (3674, and Qualcomm under 3663); hardware, networking and contract manufacturing are out (Apple, Cisco, IBM, Dell, HP), pending Thomas's choice. SIC and business state are those in the latest 10-K's header. A restructuring charge known only for the full year counts in the company count but adds no quarterly dollars, because booking it all to Q4 overstated Q4 in most cases. Headcount change drops companies with a completed acquisition, disposition or spin-off between their 10-Ks (8-K Item 2.01, Form 10, or a short hand list) instead of any large move, so organic growth and layoffs stay in. Revenue ignores goods/services component tags when a total exists, and a value over 100 times the next largest.
- 2026-11-04: A corporate action excludes a company from the headcount change only when its count also moved by more than 0.15 in log terms (`sec.DEAL_LOG_CHANGE`). Item 2.01 alone dropped acquisitive companies for years (Microsoft 2017–25, Salesforce for a decade).
- 2026-11-04: Final SEC review (CON-174). A deal is an 8-K with Items 2.01 and 9.01, a Form 10, or the hand list, filed up to 75 days after the later fiscal year end; it drops a company only with a change over 15%, which also drops some mostly organic years (Uber 2020, ServiceNow 2021, Meta 2014). A change over 0.7 in log terms with no deal is a suspect extraction and is dropped too; `dropped` lists CIK and reason. Headcount skips sentences about another named company (judged against the filer's names and tickers) and sales-force counts. Solar makers are excluded from the chips scope by hand; the panel scope itself is still pending Thomas.
