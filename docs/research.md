# Research: how this report could be wrong

Adversarial research done 2026-11-04 by four independent agents (prior work on HN hiring threads, job-postings methodology, outside data, a red team of the October 2026 column), with the key claims rechecked by the lead. Each finding names what it breaks and the fix. Tickets live in Linear project P-CON-53.

## Findings that change conclusions

1. **The seeker surge is mostly outside the US.** Among live seeker posts with a `Location:` line, the US share was 44–47% through 2025 and 32% in October 2026. US-looking seekers rose about 27% year over year; others more than doubled (India 14 → 70, Europe/UK 65 → 147). A US-only ratio rose about 65%, not the ×2.06 the headline ratio shows. Fix: a `seeker_us_share` metric and a US-only `seekers_per_post` (US seekers over hiring posts open to US workers); the column checks it before saying "doubled".
2. **HN's hiring thread diverges from the wider market.** Indeed's Software Development postings index rose 64.3 → 78.3 (+22%) from October 2025 to October 2026; CompTIA reported a three-year high in tech postings in September 2026. HN hiring posts fell 18% (live posts 26%). HN is likely losing share as a hiring channel, or its startup/remote mix is diverging. Fix: show the Indeed line next to `posts.hiring`; the column says "HN's hiring thread", never "the market", and must name any divergence.
3. **Noise bars are too narrow.** Month-to-month swings in post counts are about 4–5× (median) and 9–13× (mean) the Poisson variance, so the real bar is 2–3.5× wider. Posts cluster by company, and multi-role and repeat posts break independence. Fix: bars from each series' own history (quasi-Poisson dispersion or the spread of 1-year log changes); company-clustered bootstrap for shares; the "≈" marker uses them.
4. **Pay claims are fragile.** Disclosing posts barely moved (about 68 → 73); the 31% share rose mainly because the denominator shrank. The higher pay top sits in staff+, SF/NYC and AI-native posts; median tops for senior, remote and non-AI posts did not move. Before 2024 most months fall below the n ≥ 30 floor, so "highest since 2016" rests on a gappy series. New state pay-transparency laws took effect in 2025–26 (IL, MN, NJ, VT, MA, CT). Fix: print counts next to shares; medians within seniority and location plus a fixed-mix median; bootstrap interval must exclude zero before "rose"; "series high" needs enough qualifying months; law annotations.
5. **Validation is circular and thin.** The reference labels come from AI annotators, the holdout drops fields where they disagreed, each era has about 20 posts, and rare labels (new grad, about 5 positives) can't be checked. The literature (Egami et al. 2023; Ludwig, Mullainathan & Rambachan 2024; prediction-powered inference) shows that even 80–90% accurate labels bias downstream shares. Fix: about 400 human-labeled posts, stratified by era with rare positives oversampled and disagreements kept; then bias-corrected shares with intervals that include classifier error.

## Structural breaks to annotate

| Date | Change | Affects |
|---|---|---|
| 2015-09 | No recruiting firms or job boards | `posts.hiring` level |
| 2017-06 | Explain what your company does unless it's a household name | `industry` unstated share |
| 2018-02 | One post per company (duplicate-company share fell from 4–6% to under 1%) | `posts.hiring`, `new_company_share` |
| 2018-03 | Don't reply to complain | reply metrics |
| 2024-04 | Recruiters off topic in the seeking thread | `posts.seeking` |
| 2024-11 | Only post if actively hiring and committed to responding | `posts.hiring` |
| 2025-11 | Freelancer thread retired; some of its posters moved to "Who wants to be hired?" (about 6–15 new seekers a month) | `posts.seeking`, the 1-year comparison |

Also: moderators detach off-topic subthreads, which then look like top-level posts (10–44 a year in hiring); normalize should drop them. Late posting is rising (posts after day 7: hiring about 5% in 2019, 10% in 2026), so the 7-day window captures a smaller share each year and recent hiring declines look about 4–5% too steep; a 14-day window would fix that at the cost of publishing a week later.

## Weaker but worth doing

- Seasonality: January hiring is about 0.78× trend. Publish seasonal factors and a seasonally adjusted line. "Record" claims use 3-month averages, and comparisons avoid the 2021 peak as their only base.
- HN activity: new items per day grew about 19% in a year. Add a per-10k-items check series.
- Seeker newness: first-time seekers went 146 → 332 year over year, so repeat posting does not explain the surge. Publish `new_seekers`. The October column said "we can't test" this; now we can.
- Machine-written seeker posts: em-dash share 6% → 11%, median length +32%. Track it as a signal and never claim it as fact.
- Prompt sensitivity: rerun one month with paraphrased questions and report how much the shares move.

## Outside data to add

Pull Indeed from its GitHub repos (CC BY 4.0), not FRED: FRED's copies need Indeed's pre-approval, and FRED's terms forbid archiving.

1. Indeed Hiring Lab `hiring-lab/job_postings_tracker` (Software Development), `remote-tracker` (techsoftware) and `pay-transparency` (Software Development). Daily or monthly, from 2019–20, no key. These check `posts.hiring`, `work_mode` and `salary_disclosed_share` directly.
2. BLS JOLTS openings, hires and layoffs for Information (`JTS510000000000000JOL/HIL/LDL`) and Professional and business services (`JTS540099000000000…`) via BLS API v2. From 2000, public domain.
3. BLS CES employment for computer systems design (`CES6054150001`) and software publishers (`CEU5051320001`).
4. Later: Census high-propensity business applications (context for new companies), SEC Form D (free funding proxy), DOL H-1B LCA data (visa share and wage levels).

Point-in-time rule: month *t* uses only the outside values that had been published by its as-of date (thread date + 8 days), stored with `ref_period` and `vintage_date`. Backfill BLS from ALFRED vintages, keeping one value per month. Backfill Indeed from the repo's git history (from 2020-05). Done in CON-167: `sejr external` stores one file per source and HN month under `data/external/<source>/<YYYY-MM>.json`; see architecture.md, "External benchmarks".

## Prior work

- hn-glut (github.com/majiayu000/hn-glut) counts whole threads including deleted posts; October 2026: 319 hiring / 799 seekers. It is the closest external benchmark.
- Also: ej29-r3d/hacker-news-hiring-trends, the Pragmatic Engineer's "drop in software engineer job openings" analysis, mljar's remote-Python series, hacker-hirings.com, hnhiring.com/trends.
- HN's own critiques of these ratios (item 35440348): posts aren't jobs, employed people don't post publicly, and early-month readings flip as late posts arrive.
- No academic paper using these threads was found.

## More sources: filings, layoffs, job boards (researched 2026-11-04)

Build, in this order:

1. **Company job boards (ATS).** Greenhouse, Ashby, Lever and SmartRecruiters publish open jobs as public JSON with no key. The October 2026 hiring thread links to about 46 distinct company boards, mostly Ashby and Greenhouse. A monthly snapshot of those boards plus a fixed big-tech/YC panel gives open engineering roles per company, and "share of HN posters still hiring 3 months later". There is no history before the first run, so start early. Publish counts, never job text.
2. **SEC EDGAR panel.**
   - Headcount is almost never machine-tagged: 0 of 46 large tech companies tag it in XBRL. It comes from text instead: the 10-K "Human Capital" section (annual) and the earnings press release, Exhibit 99.1 (quarterly, for Meta, Alphabet and Amazon only).
   - Restructuring and severance costs are tagged quarterly (`RestructuringCharges` at 31 of 46).
   - 8-K Item 2.05 (exit and restructuring costs) is a dated layoff signal.
   - Every value has an acceptance timestamp, so the panel is exactly point-in-time.
   - SEC requires a User-Agent with a real contact email.
   - Panel: US 10-K filers in SIC 7370–7374 plus named big tech in other codes, top ~50 by headcount, membership frozen each January from filings public by then.
   - Later, Jev can score filed text (Ex 99.1, 10-Q MD&A) for hiring intent and AI-efficiency language. Store scores, not text.
3. **WARN notices** via Big Local News (`biglocalnews/warn-github-flow`, `integrated.csv`; about 90k notices across about 40 states). Its `first_inserted_date` gives point-in-time from 2022-04. There's no industry field, so match company names against the panel and HN companies deterministically. Never ask Jev whether a company is tech from its name, because that uses model knowledge (rule 3).

Later or context only: DOL H-1B LCA filings for software occupations (quarterly), Census business formation, GitHub Innovation Graph (CC0), Remote OK (backlink required), BLS OEWS.

Cite only, never ingest:
- **LinkedIn:** the user agreement bans scraping, the hiQ case ended with that ban enforced, and there's no data download.
- **TrueUp:** its terms ban scraping and benchmarking.
- **Earnings call transcripts:** copyrighted, so use filed Ex 99.1 text instead.
- **layoffs.fyi:** reuse with attribution is allowed, but there's no export or reliable date-added field.
- **Challenger and Dice:** PDF reports only.
- **Levels.fyi:** its terms couldn't be read, so treat it as cite-only until they are.
- **Wellfound, Built In, Welcome to the Jungle, YC Work at a Startup:** no public data. Their companies are reached through ATS links instead.
- **Dead:** Stack Overflow Jobs, Hired, Google Jobs.
