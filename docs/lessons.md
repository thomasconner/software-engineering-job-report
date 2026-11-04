# Lessons

These are mistakes already made, approaches already tried, and traps found in each source. Read this before proposing or building something. Every review that uncovers a class of mistake adds a line here, in the same PR. Each entry says what happened, why it matters and what to do instead.

## Measurement and statistics

- **Live post counts depend on when a thread was fetched.** Old threads were fetched years after their 7-day window and new ones at day 8, so live counts drifted with fetch age. Count submitted posts (live plus removed within the window) instead. `removed_share` is methodology-only.
- **Poisson and binomial noise bars were too narrow.** Monthly counts swing 4–13× more than Poisson allows, because posts cluster by company and repost. Bars are estimated from each series' own history (CON-166).
- **Log-scale bars were read as percent changes.** The renderer compared |b/a − 1| against a bar defined on ln(now/then), which gave 151 wrong verdicts. Compare |ln(b/a)|. A rise is inside the bar below e^bar − 1, a fall below 1 − e^−bar.
- **A median over mostly-zero residuals hides volatility.** New terms such as RAG got near-zero bars for two years. Zero trios count toward the minimum history, but not toward the estimate.
- **Salary medians tie on round numbers.** Residual-based dispersion collapses to 0, so salary bars use the bootstrap only.
- **Comparisons need the same population on both sides.** The seekers-per-post ratio mixed a global seeker pool with a US-leaning hiring pool, and most of the 2026 seeker surge was non-US. Check `seekers_per_post_us` before calling a ratio change large.
- **Unknowns must be treated the same on both sides of a ratio.** Hiring headers with no place had counted as "not open to US" while unknown seekers were dropped, and the bias changed by era.
- **A share can rise because its denominator fell.** Pay disclosure went from 22% to 31% while the count of disclosing posts barely moved (68 to 73). Report the count next to the share.
- **"Series high" on a gappy series.** Months under the n ≥ 30 floor are missing, and most salary months before 2024 are missing. Say how many months qualify before calling something a high.
- **Classifier labels from AI annotators can share the classifier's blind spots.** The held-out set also dropped annotator disagreements. Treat validation as provisional until human labels exist (CON-170).
- **A validation set stops being held-out once rules are tuned to its misses.** The region regex hit this twice. A clean number needs a fresh draw labeled before any rule change.
- **Mentioning a tool is not using it.** Stack and benefit trends are shares of posts that mention a term.

## Point-in-time and outside data

- **A commit date is not a publication date.** Indeed data reaches the default branch through PRs, so branch commits are dated before the data was public, which leaked 6 values. Use `git log --first-parent` (merge time). This needs git 2.31 or later.
- **FRED copies of Indeed series need Indeed's pre-approval, and FRED's terms forbid archiving.** Take Indeed from its GitHub repos (CC BY 4.0). Use ALFRED only for one value per BLS month.
- **ALFRED has no seasonally adjusted vintages for JOLTS Information.** Use the unadjusted (JTU) series. Draw them as a 12-month average on charts, and never over-read month-to-month moves.
- **A missing value must not freeze a month.** Months missing an expected series stay open and are retried. An outside-source failure warns and never blocks the HN refresh.
- **Values revise.** CES annual benchmarks show up as steps, and Indeed revised its history in November 2024. Values are as first published, and charts say so.
- **Outside series have no noise bar.** Describe their moves plainly and never with "≈".

## Sources: legal and practical

- **Rejected sources:**
  - LinkedIn: scraping is banned by its user agreement, upheld in hiQ v. LinkedIn, and it has no data download.
  - TrueUp: its terms ban scraping and benchmarking.
  - Earnings call transcripts: copyrighted. Use the filed Exhibit 99.1 text instead.
  - layoffs.fyi: no export.
  - Challenger, Dice and Levels.fyi: cite only.
- **The SEC rejects requests without a real contact in the User-Agent.** It's set as `SEC_USER_AGENT`.
- **Headcount is almost never in XBRL.** 0 of 46 big tech companies tag it. It has to come from filing text.
- **ATS fields differ by vendor.**
  - Ashby's `isRemote` is true for hybrid jobs.
  - Greenhouse has no workplace field.
  - Board-level "mostly non-US" flags mislabel US companies that hire abroad, so count US jobs per board instead.
  - A failed run must not lock the month.
- **Moderators detach off-topic subthreads into top-level comments.** These look like posts and should be dropped (CON-169).
- **HN thread rules changed over time:** 2015-09, 2017-06, 2018-02 (one post per company), 2024-04, 2024-11, and the Freelancer thread was retired in 2025-11. Annotate charts and don't compare across these breaks silently.

## Regex features

- **Two-letter codes are words too.** ON, OR, IN, OK, NO, CA and DE caused false places ("Full-time, On-site" was read as Ontario, "No Visa" as Norway). Code-only matches need context and a regression test per case.
- **Company names collide with tools and places:** Bank of America, Elixir's Phoenix framework, Snowflake, Datadog. Header company fields need care.
- **Labeled fixtures hold only the line needed** (a Location line or a header), never seeker post text, and never post ids for seekers.

## Process and tooling

- **Git worktrees under `.claude/worktrees` were once committed as gitlinks.** `.claude/` is gitignored now; keep it that way.
- **Agent sessions are blocked from setting secrets.** Give Thomas the exact `! gh secret set …` command.
- **`pkill -f <pattern>` can kill the shell running it** when the pattern matches the command line. Kill by PID from `pgrep` instead.
- **Branches that touch the shared fetch client, the monthly workflow and the docs conflict when merged.** Have the branch author merge main and resolve, since they know the code best, and keep defaults for other callers unchanged.
- **Don't publish a column claim before checking it against outside data.** The October 2026 column called HN's trend a market trend and needed a correction. A red-team pass against outside sources is part of review.
