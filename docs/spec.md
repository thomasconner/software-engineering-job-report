# Software Engineering Jobs Report: spec

A monthly Software Engineering Jobs Report on the US software engineering job market, drawn from several public sources: Indeed Hiring Lab job postings, BLS job openings, hires, layoffs and employment (JOLTS and CES), Hacker News's monthly hiring and job-seeker threads, and, as they are built, company job boards, SEC filings and WARN layoff notices. Hacker News is one source among these, a startup-leaning panel of employer posts and job-seeker posts, not the subject of the report. Published as a single-page report on GitHub Pages, written like FiveThirtyEight data journalism: each section leads with a finding, then shows the chart behind it.

## Goals

- Say each month what the US software engineering job market did, synthesized across sources: where postings, openings, hires, layoffs, employment, filings and HN posts agree, and where they don't and why (each measures something different).
- Show trends over time, with direct comparisons: this month vs 3 months ago, 1 year ago and 5 years ago.
- Compute every month **as it looked at the time**, with no knowledge of later months, even though the backfill runs in November 2026. For outside sources that means each value as published by the issue's as-of date, never a later revision.
- Keep yes/no measurements in code and use Jev only for judgment calls, so every number traces back to a method and a version.
- Make adding a source cheap: a new publisher's series lands in the `external` export and appears in the compare strip, the charts and the Sources block without renderer changes.

## Non-goals

- A job board or search tool.
- A single composite "health score". Each measure is shown on its own, with its source.
- A report about Hacker News. HN figures appear as one source; the threads' own trivia (stack trends, industries) lives on the dashboard and enters a column only when it bears on the market argument.
- Non-US markets, for now. Series carry a country so a US vs UK comparison can follow (Indeed GB, later UK ONS).

## Sources

Every source is read as published by each issue's as-of date (thread + 8 days). The site lists them, with coverage, lag, credit and caveat, in a Sources block generated from the export (`sources` in metrics.json).

| Source | Use |
|---|---|
| Algolia `search_by_date?tags=story,author_whoishiring` | Hacker News: discover monthly thread IDs back to April 2011 |
| Algolia `items/<id>` | Full comment tree per thread, with `created_at_i` per comment |
| Greenhouse / Ashby / Lever / SmartRecruiters public job-board JSON | Monthly snapshot of boards linked from recent hiring posts plus a fixed panel (`sejr ats`, `data/external/ats/`); counts and job metadata, no job text |
| Indeed Hiring Lab GitHub repos (CC BY 4.0) | Software postings index and remote share (US, GB), pay transparency (US), each as published by the month's as-of date |
| BLS API v2 and ALFRED vintages (public domain) | JOLTS openings/hires/layoffs (information; professional and business services) and CES computer systems design employment, US |

## Pipeline

1. **Fetch:** save raw thread JSON, gzipped, under `data/raw/<kind>/<YYYY-MM>/<thread_id>.json.gz`. A re-fetch overwrites only when content changed; git history keeps earlier versions.
2. **Normalize:** DuckDB tables `threads`, `posts` (top-level comments), `replies`.
3. **Derive:** table `answers(post_id, question, method, version, value, probabilities, confidence)`.
4. **Aggregate:** monthly series, computed with `as_of = month`.
5. **External:** one value per outside series per month, as published by the month's as-of date (thread + 8 days), under `data/external/`.
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

- Lede: three or four sentences on what the software engineering job market did this month, across sources.
- Comparison strip: now vs 3 months, 1 year and 5 years ago for a fixed core that mixes sources (Indeed postings, JOLTS information openings, CES computer systems design employment, HN hiring posts, HN job seekers per post and its US-only version, HN pay disclosure). Outside rows show their reference period and a plain change, with no noise verdict.
- Sections, each with a headline finding and a chart, chosen by the month's argument from these themes:
  1. Demand: postings (Indeed), openings (JOLTS), employer posts (HN), and later open roles on company job boards
  2. Employment and flows: CES employment, JOLTS hires and layoffs, later SEC headcount and restructuring filings and WARN notices
  3. Supply and competition: job seekers per hiring post (HN, with the US-only ratio)
  4. Pay: pay transparency (Indeed, HN) and posted ranges (HN)
  5. Remote, hybrid, onsite (Indeed, HN)
  6. Seniority mix and the entry-level squeeze; AI share of hiring; stack trends (HN)
- Methodology footer with a Sources block (one row per source: what it measures, coverage start, typical lag, license and credit, caveat), then how the HN threads are measured.
- Design: `frontend-design` skill, with Mobbin as reference for the dashboard layout.

## Stack

- Python 3.12, uv, DuckDB, `typesafe-sdk`, httpx. Contracts in `docs/architecture.md`.
- Static page reading exported JSON. The charting library is chosen during the design ticket.
- GitHub Actions: a monthly job runs on day 8 after each thread (the day-7 snapshot is then complete), plus a manual trigger for backfills.

## Backfill

All months from April 2011 for "Who is hiring?"; "Who wants to be hired?" starts May 2014, when the thread began. This gives a 5-year comparison with deeper context (2020, the 2022–23 layoffs).

## The article

Each month is one article in `site/articles/YYYY-MM.md`, written like a newspaper data column about the software engineering job market: a headline that makes a claim about the market, a dek, an argued lede, and sections where every claim names its source and sits next to the chart that backs it. When sources disagree, the article says so and explains what each measures. Voice: a FiveThirtyEight-style analyst writing an opinion column, plain and confident, with honest uncertainty. The style guide is `docs/style-guide.md`.

Articles are written by an agent from the exported numbers, then fact-checked by a second agent. Every number in the text must match `site/data/metrics.json`. The October 2026 column predates the multi-source framing and stays as an archived edition, with its correction, unchanged.

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
- 2026-11-04: Reframe (CON-201). The product is a monthly Software Engineering Jobs Report on the US software engineering job market, synthesized from several sources; Hacker News is one source (a startup-leaning panel of employer and job-seeker posts), not the theme. Headlines and ledes are about the market; every claim names its source; no single source stands in for the market. Outside series have no noise bar and are described in plain language with their reference period. The core compare strip mixes sources and takes `external:<key>` rows. The page has a Sources block generated from a `sources` export section. The October 2026 column stays as an archived edition, unchanged. This replaces the earlier rule that columns describe HN's threads, not the US market.
- 2026-11-04: The brand is "Software Engineering Jobs Report" on every user-facing surface (wordmark, page title, meta, default byline, footer, README). The repo name and URL stay `software-engineering-job-report`. The archived October 2026 column keeps its original byline in its front matter; the page chrome around it uses the new name.
- 2026-11-04: Context for later sessions lives in the repo: CLAUDE.md (read order, how Thomas wants the report, how work runs), docs/lessons.md (mistakes, rejected approaches, source traps; every review that finds a class of mistake adds a line in the same PR) and docs/sessions/<date>.md (what Thomas asked and answered). Every agent diff gets an independent adversarial review and re-review before merge.
- 2026-11-04: Outside changes are computed within one release (CON-201 review). Each stored outside value carries the same vintage's readings for its reference period minus 3, 12 and 60 months (`compare`); the strip and the prose use those, never two issues' stored values, so revisions don't read as market moves. A missing reading is shown as "No same-month value". JOLTS 12-month averages use distinct reference months (at least 10 of 12), not 12 issues. The masthead ribbon is set per issue (`ribbon` front matter), defaulting to Indeed's postings index from November 2026 and to HN hiring posts before.
- 2026-11-04: Article text runs the same width as charts (--measure = --wide = 56rem), at Thomas's request; it trades a longer line for one aligned column.
- 2026-11-04: Responsive article layout, replacing the 56rem column above at Thomas's request (wide desktop, iPad, iPhone). One container of up to 96rem holds the masthead, ribbon, compare strip and wide charts. Text sits in a centered column of up to 52rem (about 105 characters a line). From 80rem (1280px) up, regular charts float at 46% of the container, alternating right and left, and are moved up to the start of their section's paragraphs so text wraps beside them (about 55 characters a line) and returns to the full column below; headings clear floats. A chart with under about 500 characters of paragraphs beside it stays in the column, so a short section leaves no hole. `::compare`, small multiples and `layout="wide"` charts span the container. Below 1280px everything is one column with charts at column width, in the written order. Root type scales from 16px at 1600px to 18px at 2240px and up, so the page grows with big screens. Gutters are 16px on phones, 32px from 600px, 48px from 1280px.
- 2026-11-04: What employers ask for (CON-202, features-4): the stack vocabulary grows from 45 to 107 terms in seven groups (`stack_<group>` breakdowns; the 45 features-3 rules are unchanged so their history doesn't move), plus `benefits`, `years_required`, degree shares, interview style, office days and post length, all regex on the post text and applied to every month. A tool that is also a company (Datadog, Snowflake, OpenAI) doesn't count in that company's own post, in the header's company field, or after investor, customer or former-employer cues. Roles per post is not measured (no reliable rule). Validated on three hand-labeled sets drawn and labeled before the rules ran on them (scores in architecture.md); medians in whole years get bootstrap-only noise bars like salaries.
- 2026-11-04: CON-202 review: an independent review confirmed the trends and point-in-time, and found that years medians had no noise bars (zero-year posts broke the log bootstrap; fixed). Company cues for stack terms must sit within six words of the term and don't apply in tool lists; the reviewer's 250 labeled posts joined the fixtures. Equity's rise since 2021 is mostly disclosure (more posts state pay; among those, equity mentions held at 40–59%), and columns must say so.
- 2026-11-04: CON-202 second review: on the reviewer's untouched seed-31337 draw (60 posts), benefits scored 0.99 precision / 0.90 recall and years 9 of 9 stated, all exact, before the last round of fixes. That round restored about 110 parenthesized years requirements ("Python (5+ years)") that the company-age rule had dropped, kept strong company cues ("used by", "customers") in tool lists, and tightened relocation; the draw is now a fixture and partly in-sample. A month with no exported bar reads "no comparison" on the site for years medians.
