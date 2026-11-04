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
- **A disclosure trend can pose as a benefits trend.** Equity mentions rose from 8% to 22% of HN posts, but among posts that state pay they held at 40–59%. About two-thirds of the rise was more posts stating compensation ("$X + equity"). Check a mention share against how often posts state compensation at all.
- **A log-scale bootstrap must survive zeros.** "0–2 years" posts made the years median's variance undefined, so no month got a bar and every move rendered as real. Guard on the statistic, not the minimum, and test with zeros.
- **Mentioning a tool is not using it.** Stack and benefit trends are shares of posts that mention a term.

## Point-in-time and outside data

- **A commit date is not a publication date.** Indeed data reaches the default branch through PRs, so branch commits are dated before the data was public, which leaked 6 values. Use `git log --first-parent` (merge time). This needs git 2.31 or later.
- **FRED copies of Indeed series need Indeed's pre-approval, and FRED's terms forbid archiving.** Take Indeed from its GitHub repos (CC BY 4.0). Use ALFRED only for one value per BLS month.
- **ALFRED has no seasonally adjusted vintages for JOLTS Information.** Use the unadjusted (JTU) series. Draw them as a 12-month average on charts, and never over-read month-to-month moves.
- **A missing value must not freeze a month.** Months missing an expected series stay open and are retried. An outside-source failure warns and never blocks the HN refresh.
- **Values revise.** CES annual benchmarks show up as steps, and Indeed revised its history in November 2024. Values are as first published, and charts say so.
- **Outside series have no noise bar.** Describe their moves plainly and never with "≈".
- **Comparing values stored for two issues mixes vintages.** CES September 2026 against September 2025 read −2% across vintages but −1.3% within one, and a benchmark step read as a five-year gain; revisions looked like market moves. Store each value's same-vintage readings for t−3, t−12 and t−60 (`compare`) and compute changes from those.
- **Twelve issues are not twelve months.** Releases slip, so issues repeat or skip reference months, and a 12-issue average counted some months twice. Average the distinct reference months in the 12 calendar months ending at the point's own reference period.

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
- **A standard XBRL tag is not a standard concept.** Meta's $4.6B 2022 restructuring sits in a custom tag that company facts omit, and Intel's `RestructuringCharges` includes a $2.2B patent verdict. Before summing a tag across companies, check each peak's top contributor against the filing text, and publish who drives each point.
- **Year-to-date differencing loses one-quarter charges.** When the 10-Qs never tagged a zero, a Q4-only charge disappears (Salesforce, $828M). Treat untagged year-to-date as zero only when the 10-Qs were filed.
- **Corporate actions read as moves.** The HP/HPE split read as an 83% headcount fall, and eBay/PayPal as 66%. Flag company changes over about 30% and check for a spin-off or divestiture before counting them.
- **EDGAR's present-day metadata rewrites the past.** Yahoo/Altaba has a blank SIC, and Compass moved from 7371 to 6531. Take SIC from the filing, never from today's submissions file.
- **EDGAR timestamps differ by copy.** The data.sec.gov API gives true UTC, but `submissions.zip` often gives Eastern time labeled "Z". Bucket months by `filingDate`.
- **Revenue tags change over time, and named lists carry hindsight.** AMD's first-filed revenue was `SalesRevenueGoodsNet`, and Broadcom had an older CIK. Check that each expected company lands in each year's panel, and prefer mechanical membership rules to lists of today's winners.
- **EDGAR's `-index-headers.html` doesn't exist for filings before about 2014; `{accn}.hdr.sgml` does.** Never cache a 404 as a value. After any change to how a panel is built, check that every year still has its full size. In CON-174 the 2012–14 panels shrank to 3–4 companies while all tests passed.
- **Untagged 10-Qs don't mean zero.** Putting a 10-K-only charge into Q4 was right 5 times and wrong about 11 times when checked against later comparatives. Dell had $160M of nine-month severance that landed in Q4.
- **A size threshold isn't a corporate-action detector.** Dropping year-over-year changes over 30% removed Amazon's 2020 hiring and Compass's layoffs along with HP's split. Detect corporate actions explicitly (8-K Item 2.01, Form 10, a documented list).
- **A guard against unit slips needs a sound reference.** Comparing against the smallest revenue tag let a goods-only component ($4.3M) replace $3.3B of revenue.
- **Widening SIC ranges changes what a panel measures.** Adding 3570–79 and 3670–79 brought in contract manufacturers and solar makers and pushed out Qualcomm and design-software companies. Check the membership diff before accepting a rule change.
- **A deal filter needs an extraction-error guard next to it.** Without one, a misread sentence about another company (Koch Industries' 120,000 read as Infor's) went straight into the panel total and halved a year's change. With no deal on file, treat a change of more than about 2× as a suspect extraction, not as hiring.
- **"Any Item 2.01" is a blunt test for corporate actions.** Acquisitive companies file one most years, so some organic years get dropped too. Pair it with a size threshold and say so wherever the rule is described.
- **A SIC code isn't an industry definition.** SIC 3674 includes solar makers, and First Solar led the "tech" restructuring sum in some quarters. After any scope change, check the panel's top contributors.
- **Moderators detach off-topic subthreads into top-level comments.** These look like posts and should be dropped (CON-169).
- **HN thread rules changed over time:** 2015-09, 2017-06, 2018-02 (one post per company), 2024-04, 2024-11, and the Freelancer thread was retired in 2025-11. Annotate charts and don't compare across these breaks silently.

## Regex features

- **Two-letter codes are words too.** ON, OR, IN, OK, NO, CA and DE caused false places ("Full-time, On-site" was read as Ontario, "No Visa" as Norway). Code-only matches need context and a regression test per case.
- **Company names collide with tools and places:** Bank of America, Elixir's Phoenix framework, Snowflake, Datadog. Header company fields need care.
- **Words near a tool are not always about the company.** An investor and customer cue ("backed", "client") dropped about 17% real mentions ("a Rails stack backed by MySQL"). Keep the cue close to the term, and skip it in tech-list sentences.
- **A header URL can hide the company name**, so a company's own posts count as mentions of its product (Cloudflare). Strip URLs before parsing names.
- **Labeled fixtures hold only the line needed** (a Location line or a header), never seeker post text, never post ids for seekers, and never personal emails. Seeker posts sometimes appear in hiring threads; check for them.

## Process and tooling

- **Git worktrees under `.claude/worktrees` were once committed as gitlinks.** `.claude/` is gitignored now; keep it that way.
- **Agent sessions are blocked from setting secrets.** Give Thomas the exact `! gh secret set …` command.
- **`pkill -f` and `pgrep -f` can match the shell running them**, because the pattern is in that shell's own command line, and the shell gets killed. Find a server's PID by its port (`ss -ltnp "sport = :<port>"`) and kill that PID.
- **Branches that touch the shared fetch client, the monthly workflow and the docs conflict when merged.** Have the branch author merge main and resolve, since they know the code best, and keep defaults for other callers unchanged.
- **Don't publish a column claim before checking it against outside data.** The October 2026 column called HN's trend a market trend and needed a correction. A red-team pass against outside sources is part of review.

## Page layout

- **Floating charts beside text were tried and rejected (CON-205).** Text wrapping a float changed measure mid-paragraph, gave the page three left edges, and needed a script to move charts above their paragraphs. Graphics sit on the text's axis at `column`, `wide` or `full` width instead. Check a layout change with screenshots at phone, iPad and 2560px widths before calling it done.
- **Measure line length in the browser with the real fonts loaded.** An estimate of 70 characters at 40rem was 75 by median and up to 87 once Newsreader loaded. Count characters per rendered line after `document.fonts.ready`, not from an average glyph width.
- **Sweep widths around every breakpoint, not just device sizes.** Device screenshots at 390, 834 and 1194 missed a strip that scrolled sideways from 641 to 684px. Sweep 320–3840px in 10px steps and assert `scrollWidth` equals `clientWidth`.
- **Set the layout width before async data arrives.** A chart mounted at the text width and widened only after its breakdown file loaded, so it drew twice and the page jumped. Set `data-width` before the first `await` and give empty mounts a placeholder height.
- **A rule about errored directives must cover render-time failures, not only parse errors.** The topline skip checked only the parser's flag, so a strip with an unknown metric took the top slot. Draw strips first and treat a mount that ends in an error box as failed.
- **Prose selectors must not reach into charts.** `.article-body p` and `.article-body h3` restyled chart subtitles, notes and titles (a chart title came out serif). Scope prose rules to the article's direct children (`.article-body > p`).

## Working with Thomas (retro, 2026-11-04)

What cost rework on the first day, and what to do instead.

- **Settle the framing before building.** "A Software Engineering Jobs Report with HN as one source" arrived mid-afternoon, after an HN-centered October column had been published. That forced a correction and a rewrite of the style guide. Before new product work, ask what the finished thing is and who it's about.
- **Ask for reference examples first.** FiveThirtyEight plus NYT was the real design brief, but it came after two layout attempts (a 56 rem column, then charts with text wrapped around them). Before any UI work, ask for one or two reference links and show a quick mockup before building.
- **Ask who reads it and what decision it informs.** That decides which measures lead and which are trivia.
- **Ask which measures matter most.** Stack, benefits and experience came late. Asking at kickoff shapes the first output.
- **Red-team before publishing, not after.** The outside-data check that forced the October correction should have run before it went live.
- **Sequence parallel branches that touch the same files.** Three branches editing the same docs, fetch client and export cost a round of conflict fixes and a strict merge order. Plan shared-file edits up front, or have each branch merge main before its PR.
- **Ask about permissions up front.** Agent merges, agent pushes and secret writes were each blocked once. Ask at kickoff whether Thomas wants a permission rule (for example, merging reviewed PRs). Until he says so, he merges.
- **What works well with Thomas:** short, direct answers to one question with a default ("yes", "public is fine"), and screenshots with "what's off?". Give him something concrete to react to rather than open questions.

