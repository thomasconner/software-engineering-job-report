# Style guide: the monthly report

This guide is for the agent that writes `site/articles/YYYY-MM.md` and for the agent that fact-checks it. The spec (`docs/spec.md`) says what the report measures. The architecture (`docs/architecture.md`) says where the numbers live and how directives are written. This file says how the report sounds, how it is put together, and what it is not allowed to claim.

The report is a monthly Software Engineering Jobs Report on the US software engineering job market. It is written from several public sources: Indeed Hiring Lab job postings, the Bureau of Labor Statistics' JOLTS and CES surveys, Hacker News's monthly hiring and job-seeker threads, and, as they arrive, company job boards, SEC filings and WARN notices. Hacker News is one of those sources, not the subject. Section 4, "Sources", says what each one measures. The October 2026 column predates this framing and stays as an archived edition; don't copy its HN-centered framing.

## 1. Voice

We write like a columnist who has done the math. Every article makes one argument about the month in the software engineering job market and defends it with numbers a reader can check. The argument is a synthesis: it says what the sources show together, where they agree and where they don't. The reader is smart, busy and not a statistician: an engineer deciding whether to job-hunt, a founder deciding whether to hire, a reporter who wants to know if software hiring is picking up. We are plain, confident and specific. We have opinions, and we show the chart that earned them. When the data is noisy we say so once, in the sentence where it matters, and then we move on. We don't cheerlead a recovery or mourn an industry. A month that looks like the month before is a fine result, and we can say so.

### Sentences

- Aim for an average of 15 to 20 words, and vary it: a four-word sentence after a 30-word one is good. Sentences over 35 words are almost always two sentences.
- One idea per sentence. A sentence carries one value and at most two reference points ("37%, down from 41% three months ago and 63% five years ago"). Anything more becomes two sentences or a chart.
- Active voice, concrete subjects: "Hiring posts rose to 362", not "An increase in hiring activity was observed".
- Keep paragraphs short. A paragraph that makes two points is two paragraphs.
- Use "is", "are" and "has". Don't swap in "serves as", "stands as" or "represents".

### Numbers (AP style)

- Spell out one through nine. Use numerals for 10 and up: "three months", "12 months", "five years". Percentages, percentage points and dollar amounts always take numerals, even under 10.
- Don't start a sentence with a numeral. Spell it out ("Eleven percent of posts...") or rewrite so the number comes later. Years are the one exception ("2021 was the peak").
- Percentages take the % sign with a numeral: 38%, 6%, 0.5%. AP adopted the sign in 2019. At the start of a sentence, spell out both: "Thirty-eight percent".
- Use "percentage points" for the difference between two shares. "The remote share fell 4 percentage points, to 37%." After the first mention in a paragraph, "points" alone is fine. Never say a share "fell 4%" when you mean four points.
- Use percent change for counts, dollars and ratios. "Hiring posts rose 22% from a year ago."
- Shares change in points. A relative change on a share ("fell by more than half") is allowed only for a move that clears the noise bar and is large next to the share itself. Print both endpoints in the same or the previous sentence, and compute the relative change from the unrounded values. "Rust mentions jumped 50%" for a move from 2% to 3% is never allowed.
- Dollars: "$185,000", "$1.2 million". No "$185K" and no "185k" in prose. Salaries are nominal. When comparing across more than one year, say "not adjusted for inflation" once in the article.
- Commas in numbers of 1,000 and up: 1,018.
- BLS counts come in thousands. Write them out as whole numbers ("128,000 openings") or, from a million up, in millions to two decimals ("2.36 million people"). Never "128K".
- Indexes get one decimal and their base on first mention: "78.3, where February 2020 equals 100".
- Ratios get one decimal and a plain-English unit: "2.4 people posting in 'Who wants to be hired?' for every hiring post".
- Scores get one decimal and their scale, every time: "a mood score of 1.7 on our 0-to-4 scale".
- Months: spell them out in prose ("October 2021", "last October"). No "Oct. '21", no "10/2021", no "Q4" unless quoting.
- Use "about" for approximations, not "approximately". Don't approximate a number the reader can see exactly in the chart.

### Rounding

| Measure | metrics.json unit | Write it as |
|---|---|---|
| Post counts | `count` | Exact: 362. Never round a count the reader can check against the thread. |
| Shares | `share` (0 to 1) | Whole percent: 0.384 becomes 38%. One decimal only for shares under 1%. |
| Point differences | derived | Whole points, computed from the rounded shares you print, so the reader's subtraction works. |
| Percent change | derived | Whole percent, computed from the unrounded values. |
| Medians in dollars | `usd` | Nearest $1,000. |
| Ratios | `ratio` | One decimal. |
| Scores | `score` | One decimal, with the scale. |
| Outside indexes | `index` (external) | One decimal. Changes in percent, from the unrounded values. |
| Outside counts | `thousands` (external) | Whole numbers, or millions to two decimals. Changes in percent. |
| Outside shares | `share` (external) | Whole percent; changes in points, like HN shares. |

Fractions are fine for big moves when they're accurate: "just over a third of the 2021 peak" for 36%, "fell by about two-thirds" for a 65% drop. The exact number goes in the same paragraph or the chart.

### Comparisons

The pattern is: current value, direction, reference value, reference period.

- "Hiring posts rose to 362, up from 296 a year ago."
- "The remote share was 37%, down from 41% three months ago and 63% five years ago."
- Name the context when the reference month is unusual: "five years ago, in October 2021, during the pandemic-era hiring boom".
- "A year ago" means the same month last year. "Three months ago" means the thread three months back, not an average. Say "the three months through September" if you mean an average.
- Superlatives ("highest since", "lowest on record", "first time") need a check against the full series, and the check goes in the ledger (section 4). The series don't all start at the same time. HN hiring metrics start in April 2011 and have no gaps. Seeking metrics, including `seekers_per_post` and `seeker_mood`, start in May 2014. Indeed's postings index starts in the June 2021 issue, its remote share in October 2024 and its pay share in September 2025, because earlier values were never published in a form we can date. JOLTS and CES start in April 2011. "On record" means since the start of that series, and the first use in an article says which: "the most since the hiring thread began in April 2011", "the highest since Indeed's series starts here, in June 2021".
- An outside value names its reference period, not the issue month: "Indeed's index stood at 78.3 in the week to October 2", "employers reported 128,000 openings in August". See "Reference periods and lags" in section 4.

### Hedge once, where the doubt lives

A claim that clears the noise bar in section 4 is stated flat. No "may", "appears to" or "seems". A claim that is close to the bar, or rests on a classifier with a weak validation score, gets one hedge, in one sentence, with the reason:

> Junior posts went from 9% to 6% in the past year, a gap that sits inside the noise for months this size.

Not: "This could potentially suggest that junior hiring may be somewhat weakening." Stacked qualifiers tell the reader we don't know what we think. One hedge with a reason tells them exactly how much to trust the number.

The "what this data can't tell us" paragraph (section 2) is about the source's limits. It doesn't count as the hedge, and it's no excuse to hedge the findings again.

### Person

- "We" is the report. Use it for what we did and what we think: "we count top-level posts", "we read this as a recovery in ads, not yet in payrolls". The byline is "Software Engineering Jobs Report", so there is no "I".
- "You" is fine when the sentence is about the reader's own situation ("if you're a junior engineer"). Use it sparingly, and never for "you might be wondering".
- Opinion comes through the claim and the verbs more than through "we believe" or "in our view".

## 2. Article anatomy

The lengths below are targets for the editor, not pass/fail rules. A normal month runs 600 to 1,100 words of prose, not counting directives.

| Part | Target | Job |
|---|---|---|
| Headline | 6 to 12 words, about 70 characters at most | A claim someone could disagree with. |
| Dek | One sentence, about 30 words | The evidence for the headline, with one or two numbers. |
| Lede | 1 to 3 sentences, about 60 words | Why this month is worth reading. |
| Nut graf | 60 to 110 words | The argument in plain terms, and the numbers that carry it. |
| Compare strip | One `::compare` | The data turn: here are the numbers. |
| Sections | 3 to 5, each 90 to 200 words | Each leads with a finding and has one chart. |
| What this data can't tell us | 60 to 130 words | The sources' limits, as they apply to this month's argument. |
| Kicker | 1 to 3 sentences, about 50 words | Takes the argument one step further. Never a summary. |

### Headline

A claim about the software engineering job market, not a label. It should be checkable against the data and narrow enough to be wrong. It comes from the sources together, so it never takes one source as its frame.

- Good: "Software job postings rose this year, but employment slipped"
- Good: "Remote work is losing, but not where you'd think"
- Good, for a quiet month: "Nothing moved in October, and that is the story"
- Bad (one source as the frame): "HN has 2.4 job seekers for every hiring post"
- Bad (a label): "October 2026 job market report"
- Bad (a question): "Is the tech hiring freeze over?"
- Bad (hype): "The AI hiring boom is here"

Sentence case, no period, no em dash, no colon-subtitle ("AI hiring: what it means").

### Dek

The line under the headline. It gives the reader the one or two numbers that justify the headline, each with its source. "Indeed's index of US software job postings rose 23% in a year, while the BLS counted 2% fewer people working at computer systems design firms."

### Lede

Open on the tension, not on the method. Don't start with "Every month, we analyze..." or with a number the reader has no context for. The tension comes from the numbers: two sources moving apart, a contrast between two groups in the data, a surprise against last year, or a flat statement of what changed. The lede is about the market. A Hacker News number can carry it only as one source among others ("On Hacker News, job seekers per hiring post doubled"), never as the frame ("HN has..."). A real post from the month's sample file can also open the piece (section 4 says how to quote one). Never open on an invented scene, person or quote. The lede can be argued. It can't be unsupported: whatever it asserts, a section backs up.

### Nut graf

The paragraph that tells the reader what the whole article argues and why they should keep reading. State the one argument in a sentence a friend would repeat. If you can't write that sentence, the article isn't ready. The nut graf carries the two or three numbers that matter most and sets up the compare strip.

### The data turn

Right after the nut graf comes the `::compare` strip. It has a fixed core so readers can compare months at a glance. The core mixes sources, outside series first:

```markdown
::compare{title="Postings rose on Indeed while BLS employment and openings fell" metrics="external:indeed_software_postings.US,external:jolts_openings_information.US,external:ces_computer_systems_design.US,posts.hiring,seekers_per_post.hiring,seekers_per_post_us.hiring,salary_disclosed_share.hiring" against="3m,1y,5y"}
```

| Row | What it adds |
|---|---|
| `external:indeed_software_postings.US` | Software development job ads across the US, the widest view of demand |
| `external:jolts_openings_information.US` | Openings at information-sector employers, an industry check on the ads (unadjusted) |
| `external:ces_computer_systems_design.US` | People employed at computer systems design firms, the closest payroll count |
| `posts.hiring` | Employer posts in Hacker News's hiring thread, the startup-leaning panel |
| `seekers_per_post.hiring` | Job seekers per hiring post on HN, the only supply-side measure |
| `seekers_per_post_us.hiring` | The same ratio for US job seekers and US-open posts, the check on the one above |
| `salary_disclosed_share.hiring` | HN hiring posts that state pay |

Outside rows show the period their number describes ("Aug 2026 data") and a plain change with no noise verdict. Add one or two extra rows at the end when the argument uses them (for example `external:indeed_software_pay_transparency.US` beside the HN pay share, or `new_grad_share.hiring`). When a new source reaches `metrics.json` (SEC filings, job-board snapshots), propose its core row in the PR that first uses it. Don't drop a core row because it's dull this month. The strip is the "here's the data" moment. Don't restate every cell of it in prose. The prose picks the cells that matter.

### Sections

Each section is:

1. An `##` heading that states the finding, in sentence case. "Employment at computer systems design firms slipped", not "Employment".
2. The finding in the first sentence, with its number and its source.
3. Context: the comparison windows, what the reference months were like, the strongest other reading.
4. One `::chart` directive that backs the heading. Place it after the prose, as the evidence for what was just said.

Order sections by importance to the argument, not by the order in the spec. Sections the argument doesn't need are left out. They live on the dashboard. Three strong sections beat five thin ones.

### The "to be sure" paragraph

Every article has one "to be sure" paragraph, inside the section whose finding it tests. It takes the strongest objection to the argument head-on. Name the counter-reading specifically, give it its best numbers, then say why the argument survives or how far it has to retreat. If it doesn't survive, change the argument. FiveThirtyEight's editors called this letting the data change the story.

The strongest objections for this data are usually one of these:

- **Another source disagrees.** Indeed's ads rise while JOLTS openings fall, or HN's hiring thread shrinks while Indeed grows. Name both, say what each counts (section 4, "Sources"), and say which reading survives. A disagreement explained is a finding; a disagreement left out is a hole.
- **Industry isn't occupation.** JOLTS and CES count employers in an industry, every job in it, and miss software engineers in other industries. A move there may not be a move in software work.
- **Title inflation.** Companies relabel the same role as "senior", so the seniority mix shifts while hiring doesn't. Test it with `new_grad_share`, which asks a question titles don't answer.
- **A change in who posts.** The mix of companies on HN shifts (more AI startups, fewer agencies, more remote-first firms), so a share moves without any one company changing its behavior.
- **A change in how posts are written.** Companies describe the same product differently over the years. See the drift rule in section 4.
- **The base month.** The comparison month was unusual (spring 2020, the 2021 boom).

### What this data can't tell us

A fixed `##` heading, every month, just before the kicker. Pick the two to four limits from section 4 (the sources' caveats and the HN rules) that bear on *this* month's argument and say them plainly, in prose, not as a bullet list. Close any gap the argument invites but the data can't fill: "We don't split seniority by AI status, so we can't test whether the change in who posts explains the shift." This paragraph builds trust. Write it like you mean it, not like a disclaimer.

### Kicker

The last line is the one people quote. It turns the argument forward: what to watch next month, what the finding means for someone deciding something, or a short line that restates the argument's contrast in plain words. It doesn't summarize the sections. It doesn't end on "only time will tell" or "the future remains uncertain". It stays inside the data. A kicker can sharpen what the article showed, but it can't add a number, a cause or a motive ("companies would rather someone else trained them" is a motive the data can't show).

### Continuity

When last month's article made a call this month's data can check, open the first section with one line on it: "Last month we said the September rise could be a blip. October's count says it wasn't." Optional, and only when the call was specific. If last month's call was wrong, say so in the same plain voice.

### Quiet months

Some months nothing clears the noise bar. That is a valid article, not a reason to stretch a sub-bar move into a story. The quiet-month shape:

- At least about 350 words, with two sections instead of three to five.
- The argument is the long view: where the month sits against one and five years ago, which the noise doesn't touch.
- The headline can say so outright: "Nothing moved in October, and that is the story".
- The compare strip, the "can't tell us" paragraph and the kicker stay.

### The comparison convention

Every headline measure is placed against three reference points, in this order:

| Window | Directive value | What it tells the reader | Watch out for |
|---|---|---|---|
| 3 months ago | `3m` | Short-term direction. | Seasonality, and single-month blips (section 4). Check the same stretch in earlier years before calling it a trend. |
| 1 year ago | `1y` | The cleanest comparison: same month, so seasonal effects mostly cancel. | Lead with this one when only one comparison fits. |
| 5 years ago | `5y` | Where the market sits in the long cycle. | From 2026, five years back lands in the 2021 boom. Name the base month's context so the drop isn't read as a collapse. |

For an outside series, the windows count back from the issue value's own reference period, and both values come from the same release (`compare` in `metrics.json`): "September 2026 against September 2025, both as published in October 2026". The strip prints both reference periods. When that release has no reading for the same month (a skipped or delayed release), the strip says "No same-month value", and the prose says so too rather than reaching for another month or another release. For a not seasonally adjusted series (JOLTS, Indeed's remote and pay shares), the strip shows "seasonal" for windows that compare different calendar months; the 1y and 5y windows compare like seasons.

Skip a window, and say why in the chart note or a clause, when:

- the metric has no value for that month (`series` omits it, for example seeking metrics before May 2014);
- the reference month's `n` is under 50 posts;
- the reference month was distorted by a known event and the comparison would mislead (for example, March and April 2020 as a "normal" baseline).

The `::compare` strip uses `against="3m,1y,5y"`. Don't drop a window from the strip because it hurts the argument. That's the window the "to be sure" paragraph has to handle.

## 3. Charts

Every claim in a section heading has a chart. Every chart supports a claim in the text. A chart nobody refers to is cut. Each chart asks the reader for effort, so it has to pay that back.

### Title states the finding

The `title` attribute is a sentence that says what the chart shows, like a headline. Aim for 10 to 15 words, sentence case, no period.

- Good: `title="Posts describing AI products went from 8% to 38% in five years"`
- Bad: `title="AI-native share of hiring posts, 2019-2026"` (that's a subtitle)
- Bad: `title="AI is taking over startup hiring"` (that's not what the chart measures)

The title must be true of the chart as drawn. If the line is flat for the last six months, the title can't say "still climbing". The same vocabulary rules apply as in the prose: posts aren't "roles" or "jobs".

### Subtitle states the measure

The subtitle names the measure and the period: "Share of 'Who is hiring?' posts from AI-native companies, January 2019 to October 2026." The renderer builds it from the metric's, breakdown's or outside series' `label` in `metrics.json` plus the chart's date range, so the writer doesn't type it. An outside series drawn on its own adds "as published by each issue's date", because each point is the value known when that issue came out. The writer checks that it reads correctly. If it doesn't, fix the label in the export, not in the article.

### Notes

`note` is for what a reader needs to read this chart correctly, in one or two sentences:

- that a share is a Jev expected value ("Shares are expected values from a model's reading of each post");
- a skipped or unusual month;
- a definition the subtitle can't hold, quoted from the classifier's question text rather than paraphrased from memory;
- for an outside series, that values are as first published, and any visible break that comes from the publisher rather than the market (CES shows its yearly benchmark revision as a step in early-year months).

Don't repeat the methodology footer in every note. Don't put an argument in a note.

### Annotating events

Annotations mark real-world events so readers can line them up against the data. They don't claim the event caused the change (section 4). Rules:

- Two annotations per chart at most. Pick the events relevant to this chart's claim. Separate two entries with `;`: `annotate="2022-03:First rate hike;2023-01:Big Tech layoffs"`.
- Labels are four words or fewer, in sentence case: `2022-11:ChatGPT launches`.
- Annotate the month the event happened. Each "Who is hiring?" thread goes up around the 1st to 3rd of its month, so any event after the thread's posting date first shows in the next month's thread. Don't write as if the thread reacted the same month.
- Use the standard list below. An event not on the list needs a source in the ledger and a line added here in the same change.

| Month | Label | Event |
|---|---|---|
| 2020-03 | COVID shutdowns | WHO declares a pandemic (March 11); US shutdowns begin |
| 2021-01 | Colorado pay law | Colorado's pay-range disclosure law takes effect (salary charts only) |
| 2022-01 | Sec. 174 change | R&D costs must be amortized, not expensed, from tax year 2022 |
| 2022-03 | First rate hike | Federal Reserve starts raising rates (March 16) |
| 2022-11 | Meta layoffs | Meta announces about 11,000 job cuts (November 9) |
| 2022-11 | ChatGPT launches | ChatGPT public release (November 30) |
| 2022-11 | NYC pay law | New York City pay-range law takes effect (November 1; salary charts only) |
| 2023-01 | Big Tech layoffs | Amazon, Microsoft and Google announce cuts of about 40,000 jobs between them |
| 2023-01 | California pay law | California and Washington pay-range laws take effect (salary charts only) |
| 2023-03 | SVB collapses | Silicon Valley Bank fails (March 10) |
| 2024-09 | First rate cut | Federal Reserve starts cutting (September 18) |
| 2025-07 | Sec. 174 restored | Domestic R&D expensing restored (signed July 4) |
| 2025-09 | H-1B fee | Presidential proclamation signed September 19, effective September 21, puts a $100,000 fee on new H-1B petitions (visa charts only) |

The 2022 rate hikes were a series of increases. Annotate the first one, and don't label it "rate hikes" as if it were a single date.

### Choosing the chart type

Pick the type from the shape of the claim. The attributes column lists what each type takes besides `title` and `note`.

| The claim is about | Type | Attributes | Example |
|---|---|---|---|
| One measure moving over time | `line` | `metric`, `from`, `to`, `annotate` | "Hiring posts are just over a third of the 2021 peak" |
| One outside series over time, in its own unit | `line` | `external` (no `metric`, no `base`), `from`, `to`, `annotate` | "Indeed's US software postings rose 23% in a year but are a third of their 2022 peak" |
| An HN measure against an outside series | `line` | `metric`, `external`, `base`, `from`, `to` | "Indeed's US software postings rose 23% this year; HN's hiring thread did not" |
| Parts of a whole shifting over time (categories that sum to 1) | `stacked-area` | `breakdown`, `from`, `to`, `annotate` | "Hybrid has taken share from remote since 2022" (`work_mode`, `seniority`, `funding_stage`) |
| Several categories, each with its own trend | `small-multiples` | `breakdown`, `categories`, `from`, `to`, `annotate` | "Rust and Go rose while Ruby faded" (`stack`, `industry`) |
| The same categories at two dates | `slope` | `breakdown`, `months`, `categories` | "Senior and staff posts gained 18 points as junior posts lost 11" |
| Many categories, now vs one past point, ranked | `dot` | `breakdown`, `vs`, `categories` | "AI/ML gained the most share of any industry this year" |
| Values for categories at one month, or yearly totals | `bar` | `metric` or `breakdown`, `categories` | "Fintech and devtools wrote the most hiring posts this month" |
| Headline measures against 3m/1y/5y | `::compare` | `metrics`, `against` | The data turn after the nut graf |

Formats: `from` and `to` are `YYYY-MM` (`to` defaults to the article month). `months` is two months, `"2021-10,2026-10"`. `vs` is a window (`1y`) or a month (`2021-10`). `categories` is a comma-separated subset of the breakdown's categories.

Rules that follow from the data:

- `stack` shares don't sum to 1 (a post can mention many terms). Never draw them as `stacked-area`. Use `small-multiples` or `dot`.
- `industry` has 11 categories. Don't stack all of them. Use `small-multiples`, `dot`, or `categories` to show the four or five the claim is about.
- Bars start at zero. Lines can start above zero, but the renderer's y-axis rules decide that, not the writer.
- Pick `from` to fit the claim, not to exaggerate it. A "lowest since" claim shows enough history to see the earlier low. A short-term claim can start in 2019, which keeps COVID and the 2021 peak in view. Starting a line in mid-2022 to make a drop look steeper is not allowed.
- One chart per section. If a section needs two charts, it's two findings, so it's two sections.
- JOLTS is flagged `smooth_12m`, so every chart draws it as a 12-month trailing average, and the subtitle says so. A chart title about JOLTS describes the average, not the latest month; the prose can cite the latest month as long as it says which.
- An outside series starts where its point-in-time history starts (Indeed postings June 2021). Don't set `from` earlier and imply the gap is zero.

## 4. Honesty rules for this data

These apply to every sentence. The fact-checker enforces them.

### Sources

Each source sees a different part of the market. Know what it counts before you write a sentence about it.

| Source | `metrics.json` | Counts | Reference period and lag | Adjusted | Noise bar |
|---|---|---|---|---|---|
| Indeed Hiring Lab | `external` `indeed_*` | Software development job ads on Indeed (index, Feb 2020 = 100); shares of those ads offering remote work or stating pay | Postings: a 7-day average ending days before the issue's window ends. Remote: previous month end. Pay: about two months back | Postings yes; remote and pay no | None |
| BLS JOLTS | `external` `jolts_*` | Job openings, hires, layoffs and discharges at employers in the information sector and in professional and business services, all occupations | About two months behind the issue | No | None |
| BLS CES | `external` `ces_computer_systems_design.US` | People employed at computer systems design and related services firms | About one month behind | Yes | None |
| Hacker News | `metrics` | Employer posts in "Who is hiring?" and posts from people looking for work in "Who wants to be hired?", first 7 days | None: the issue month itself | No | Exported `bar` |
| Company job boards, SEC filings, WARN notices | not exported yet | Open roles on company boards; company headcount, restructuring and layoff filings; state layoff notices | Added here when each reaches `metrics.json` | | |

Rules:

- **Every claim names its source.** "Indeed's index of US software job postings rose 23%", "the BLS counted 2% fewer people", "employer posts in Hacker News's monthly hiring thread". A number without a source is not checkable, so it isn't printed.
- **No single source stands in for the market.** Not Indeed ("software hiring rose 23%" when ads rose), not JOLTS, and above all not Hacker News. Market-level claims ("the software job market", "demand", "hiring") are syntheses: they say which sources back them, and they hold only as far as those sources agree.
- **When sources disagree, say so and explain what each measures.** Postings are ads, openings are employers' reported vacancies, hires and layoffs are flows of people, employment is a stock of people on payrolls, filings are what public companies tell the SEC, and HN posts are what startups and job seekers choose to write. Ads can rise while hires fall. That gap is the story, not a problem to smooth over.
- **Industries aren't occupations.** JOLTS and CES count every job at employers in an industry, software or not, and miss software engineers in other industries. Say "openings in the information sector", never "software openings".
- **Postings aren't jobs.** Indeed counts ads, and one HN post can list many roles. Neither is a count of people hired.
- **Values are as first published.** Outside series are read as published by each issue's date and never revised later. BLS revises its numbers, and CES re-benchmarks every year, which shows as a step in early-year months. Don't read a revision step as a move in the market, and say "as first published" when a reader might compare with today's BLS figures.

### Reference periods and lags

- **State the reference period whenever it differs from the issue month.** JOLTS runs about two months behind, CES about one, Indeed's pay share about two. "In August, employers in the information sector reported 128,000 openings", not "in October".
- **No silent mixing.** A sentence that sets an August JOLTS figure against an October HN figure says both months.
- **Changes come from one release.** Every outside change (3 months, a year, five years) compares two readings from the same vintage: the issue's value and its `compare` reading. Never subtract the values stored for two different issues: they come from different releases, so BLS revisions and benchmark steps would read as market moves (CES September 2026 against September 2025 is −2.3% across releases and −1.3% within one). If `compare` has no reading for the window, write that there is no same-month value in this release, and leave the change out.
- **Levels across releases.** A chart line or a "peak" is a series of values as first published, so it does mix releases. Say "as first published" when a level claim spans a benchmark revision.
- **Lagged sources describe the past.** A September CES count can't confirm or refute an October HN move; say they cover different months.

### Outside series have no noise bar

HN series carry an exported noise bar (below). Outside series don't: their publishers' sampling errors aren't in `metrics.json`, and we don't estimate them.

- Describe an outside change in plain language with its number, computed within one release (above): "Indeed's index rose 23%", "employment was 2% lower". Never call it "about the same" or "within the noise" (we haven't measured that), and never call it "clearing the bar".
- Reserve the stronger size verbs (jumped, plunged) for large moves over a year or more, stated with the number. A one-month change in a single outside reading is a reading, not a trend.
- **Unadjusted series swing with the seasons.** JOLTS and Indeed's remote and pay shares are not seasonally adjusted. Compare a month with the same month a year earlier, or use the 12-month average the charts draw, and don't describe a month-to-month move in them as a rise or fall. JOLTS for one industry swings widely even year on year; a single-month JOLTS change leads a section only when the 12-month average moves the same way.
- Counting directions is still allowed, as readings: "the index rose in 10 of the 12 monthly readings since October 2025". Those readings come from different releases, so count them only for series without big revisions (Indeed's postings index), and say "readings".
- A JOLTS 12-month average is the mean of the distinct reference months published by the issue's date, at least 10 of the last 12; the tooltip says how many. Write "averaged over the 12 months to August" (or "over 11 monthly readings" when one is missing), never "12 readings" or "12 issues".

### No fabrication

- No invented people, quotes, anecdotes or scenes. No "Maria, a bootcamp grad in Austin". No "picture a founder scrolling the thread". The column has no reporting behind it beyond the data, so it doesn't pretend to.
- Color comes from the numbers, or from quoting a real post. Real posts come only from the month's sample file, `site/data/samples/YYYY-MM.json`, which the export writes. Quote the post's text, not the username, keep it to a sentence or two, and put its HN item id in the ledger. The sample files hold hiring posts only; never quote or paraphrase an individual job seeker.
- A quoted post illustrates a finding. It never stands in for one: "one company wrote X" can't support a claim about the thread.

### Hacker News: what a post is

- **HN is one source.** Cite HN figures as one source among several: "employer posts in Hacker News's monthly hiring thread", "people posting in Hacker News's 'Who wants to be hired?' thread". The threads are a startup-leaning panel of employers and self-selected job seekers. HN numbers can lead a section about HN, but the headline, dek and lede are about the market, and an HN move is set beside what the other sources show.
- **Posts aren't jobs.** One "Who is hiring?" post can list one role or 20. Write "hiring posts" or "companies posting". Never write "jobs", "openings" or "roles" for a post count. A role level can describe which posts ("posts for senior engineers").
- **Seeking posts aren't all job seekers.** "Who wants to be hired?" posts come from people who chose to post on Hacker News. On first mention write "people posting in 'Who wants to be hired?'". After that, "job seekers posting" or "job seekers" is fine.
- **Hacker News isn't the job market.** The threads skew toward venture-backed startups, engineering roles and the Bay Area. Say "on Hacker News", "in the thread" or "among companies posting on HN". Never "tech hiring rose" or "the job market recovered" on HN numbers alone. When HN and another source agree, say both; when they diverge, say that and say what each counts.
- **The threads aren't the US market either.** In 2026 only about a third to two fifths of the people posting in "Who wants to be hired?" gave a US location, and hiring posts include European, Canadian and remote-anywhere companies. "US" claims rest on `seeker_us_share`, `seekers_per_post_us` or the `region` breakdowns, never on the whole-thread numbers.
- **The snapshot is seven days.** Every month counts posts in the first seven days of its thread. Late posts don't count, past or present. Don't compare our counts to someone else's thread totals.
- **Survivorship.** Deleted posts are missing and edited posts show their latest text. Older months have had more time to lose posts, so counts from earlier years are a floor.
- **Series starts.** The hiring series runs from April 2011 with no gaps (July and December 2011 use replacement threads). The seeking series starts in May 2014. The first seeking thread was posted by the user jader201, and the whoishiring account took it over in July 2014.

### How each metric is made

- **Jev estimates, shares:** `ai_native_share`, `new_grad_share`, `work_mode`, `seniority`, `industry`, `funding_stage`. These are expected values: the sum of the model's probabilities divided by the number of posts. Say "by our classifier's estimate" or similar once per article, the first time one appears.
- **Jev estimate, score:** `seeker_mood` is a mean score from 0 (discouraged) to 4 (upbeat). It isn't a share and doesn't take points-of-share language.
- **Counts:** `posts`, `seekers_per_post`, `replies_per_post`.
- **Outside:** every key under `external`. Published values, read as of each issue's date; see "Sources" above for what each counts.
- **Regex:** `salary_disclosed_share`, `salary_min_median_usd`, `salary_max_median_usd`, `remote_token_share`, `onsite_token_share`, `visa_share`, `seeker_us_share`, `seekers_per_post_us`, `region`, `seeker_region`. These are exact counts of what the text says, but regex can miss unusual formats. Region comes from the seeker's `Location:` line and the hiring post's first line; posts that name no place are `unknown`. `seekers_per_post_us` is `seekers_per_post` scaled by the US shares of live posts, so both ratios count submitted posts and can be compared directly. It assumes deleted posts, seekers with no recognized location and hiring posts that name no place and don't say remote split the same way as the rest.
- **Join:** `new_company_share`, `returning_company_share`. These depend on company names pulled from the header line by regex, so a renamed company or a typo counts as new. They also need history: in 2011 every company is "new". Don't use their 2011 values.
- **Vocab:** `stack`. This is the share of posts mentioning each term from a fixed list. Terms overlap and don't sum to 1.

### Classified shares are estimates, and they drift

- Jev shares carry two kinds of error: the model can be wrong about a post, and a month of about 300 posts is a small sample. Both mean small moves are noise.
- **Era drift.** The classifier reads only the text, and posts from 2011 and 2026 are written differently. "AI" in particular moved into marketing copy after 2022, so some of the rise in `ai_native_share` may come from how companies describe themselves rather than what they build. Over five years or more, name this limit whenever an argument leans on a Jev share.
- Name the measure for what it measures. `ai_native_share` is "posts that describe a product built on AI". It isn't "AI jobs", "AI companies" as a fact, or "posts mentioning AI". `remote_token_share` is "posts with REMOTE in the header line", which differs from `work_mode` remote. Pick one per article and stick to it.
- **Junior claims lead with `new_grad_share`.** It asks whether a post says it will consider new grads, which a title change doesn't affect. The `seniority` breakdown supports it. The column's term for the low end of the seniority mix is "junior". Don't cycle through "entry-level", "beginners" and "first job". `new_grad_share` is called "posts open to new grads" when it's named.

### The noise bar

Every HN point in `metrics.json` (under `metrics` and `breakdowns`) carries `bar`: the noise bar for the change into that month from 3 months, 1 year and 5 years earlier (`{"3m": 0.342, "1y": 0.338, "5y": 0.329}` for hiring posts in October 2026). Breakdown points carry one per category (`bar["1y"]["remote"]`). Read the bar from the later month's point and put it in the ledger. Its scale follows the unit:

| Unit | Bar is on | A move is inside the bar when |
|---|---|---|
| `share` | the difference, as a 0 to 1 share | the gap is smaller: 0.095 means 9.5 points |
| `count`, `ratio`, `usd` | the log ratio, ln(now / then) | a rise is under e^bar − 1, a fall under 1 − e^−bar: 0.338 means a rise under 40% or a fall under 29% |
| `score` | the difference | the gap is smaller |

How it is built: each month's value varies by its sampling error (Poisson for counts, binomial for shares, a bootstrap of the median for salaries, the spread of scores for mood) plus an extra variance s² that sampling can't explain and that is the same for every month of a series. s² comes from how far each month sits from the average of its two neighbors, over the last 36 such comparisons (36 months for a series with no gaps), using a median so one odd month doesn't widen every later bar. The bar is 1.96 × √(2s² + sampling variance of the earlier month + that of the later month). In late 2026 that makes the post-count bars about twice the old Poisson ones (hiring about −29% to +40% for a year-on-year change, not ±14%), while most shares stay near the binomial bar because they wobble about as much as sampling predicts. A month's bar uses only that month and earlier ones, so it never changes after publication. A series with fewer than 12 comparisons gets a deliberately wide bar (extra noise nine times its sampling variance). Comparisons where a share is 0 in all three months count toward those 12 but not toward s², and s² needs at least 6 comparisons with some movement. A stack term that sat at 0% for years therefore leaves the wide bar about six months after it catches on, with s² measured on its own wobble rather than on the zeros.

The bar still covers only the series' own month-to-month noise. Classifier error sits on top, so a Jev share near its bar gets the hedge.

Rules that stay:

- **Salary medians.** Use a median only when at least 30 posts disclosed pay in each month compared. Months under 30 have no bar and the page shows "too few posts". The bar is the bootstrap alone (s² = 0): salaries cluster on round numbers, so neighboring medians often tie exactly and the neighbor comparison can't measure their wobble.
- **Other month pairs.** A comparison that isn't 3 months, 1 year or 5 years (a chart with explicit `months`) has no exported bar. The page then falls back to the sampling-only floors (Poisson, binomial, 5% for salaries, 0.2 for mood); treat those as too narrow and hedge anything close.
- **Mood.** `seeker_mood` bars never go below 0.2 points. Its sampling and dispersion bar is only about 0.02 to 0.04, but it leaves out classifier error, which dominates a Jev score.
- **US-only ratio.** `seekers_per_post_us` gets its bar the same way as `seekers_per_post`, with S = value × n and H = n (hiring posts open to US workers). Fewer posts on each side make it wider, about 30% before dispersion.
- `removed_share` has no bar: it is never compared across months.

**Many comparisons.** Each article looks at dozens of numbers across three windows, so some will clear the bar by chance. Prefer moves that persist: the 1y window, or a three-month average against the same three months a year earlier. Treat a 3m move that the 1y window doesn't confirm as suspect. Counting directions is allowed and often more honest than one comparison: "the share has risen in 10 of the last 12 months".

Below the bar: say the measure was about the same, or leave it out. Don't build a section on it. Near the bar: state it with the one hedge. Above it: state it flat. All of this is for HN series; outside series follow "Outside series have no noise bar" above.

### Words of size

Match the verb to the move.

| Move | Verbs |
|---|---|
| Below the noise bar (HN series) | was about the same, held steady, roughly flat |
| Outside series, any size | rose, fell, was up or down, with the number; see "Outside series have no noise bar" |
| Above the bar | rose, fell, grew, shrank, slipped, climbed |
| Largest move in at least 12 months | jumped, dropped, surged, sank, and say "the largest in X months" |
| Record or multi-year extreme | Only with a ledger check: "lowest since March 2013", "the most since the hiring thread began in April 2011" |

"Plunged", "soared", "collapsed", "skyrocketed" and "exploded" are reserved for moves of a third or more, and still need the check.

### No causal claims, no motives

The data shows when things moved, not why. Annotated events are context.

- Banned with a measure as the subject or object: "caused", "drove", "led to", "fueled", "triggered", "because of", "due to", "thanks to", "as a result of", "killed", "sparked".
- Allowed: "after", "since", "coincided with", "began rising a few months after", "followed".
- No causes across sources either. "Employment fell because postings were down" and "the ads haven't turned into hires" both assert a mechanism; "ads rose while employment fell" is the finding.
- No motives. The data doesn't say what companies want, prefer or fear. "Companies are skipping juniors to save on training" is a motive. "Fewer posts say they'll consider new grads" is a finding.
- When a cause is the natural question, name it as a question the data can't answer, in the "can't tell us" paragraph. You can say which explanation fits the timing better. You can't say it's proven, and you don't cast suspects.

### Every number is checkable

- Every number in the prose, headline, dek, chart titles and notes comes from `site/data/metrics.json` for a named key and month, or is computed from those values with the rounding rules in section 1. Outside values are cited by their `external` key, issue month and `ref_period`.
- Derived numbers (percent changes, point differences, expected counts, "a third of", "fourth straight month") get a ledger line showing the inputs.
- Shape words count as claims: "last year's low", "the 2021 peak", "the height of the boom", "started climbing in early 2023". Each gets a ledger line pointing at the series.
- Outside facts (event dates, laws, company layoffs, what an industry includes) come only from the event table in section 3 or carry a source in the ledger.
- No numbers from memory, other articles or datasets that aren't in `metrics.json`.
- Don't compare a metric before its series starts (see "Series starts" above).

### The numbers ledger

At the end of the article file, after the kicker, add an HTML comment listing every number and shape claim in the text with its source. Browsers don't display HTML comments, so readers never see it. The fact-checker works from it. The first line restates the rounding rule so the checker knows how each number was made.

```markdown
<!-- ledger
rounding: shares to whole %, point gaps from printed shares, % change from unrounded values
289 hiring posts            posts.hiring 2026-10 = 289
about the same as a year ago posts.hiring 2025-10 = 351; ln(289/351) = -0.194; bar 1y = 0.338; inside
685 people looking for work posts.seeking 2026-10 = 685
Indeed rose 23%             external indeed_software_postings.US 2026-10 = 78.33 (ref 2026-10-02); compare.1y = 63.6 (ref 2025-10-02, same release); no bar
128,000 openings in August  external jolts_openings_information.US 2026-10 = 128 (ref 2026-08)
up 70% from a year ago      posts.seeking 2025-10 = 404; 685/404 = 1.696; ln = 0.528; bar 1y = 0.299; outside
most on record              posts.seeking max(2014-05..2026-09) < 685
ChatGPT launches            event table, 2022-11
"We hire for slope..."      samples/2026-10.json, HN item 45123456
-->
```

## 5. Banned phrases and AI tells

The column is written by an agent, which makes this list more important, not less. Readers have learned the tells. One "delve" and they stop trusting the numbers. This list folds in the `humanizer` skill (based on Wikipedia's "Signs of AI writing") and adds the clichés of business and economics journalism.

### Words and phrases

Never use these in article prose, titles or notes:

- **AI vocabulary:** delve, tapestry, testament, landscape (for anything but land), realm, intricate, interplay, pivotal, crucial, vital, key (as an adjective), robust, seamless, multifaceted, nuanced, underscore, highlight (as a verb), showcase, foster, garner, bolster, navigate (except maps), unlock, elevate, leverage (as a verb), embark, journey, ever-evolving, game-changer, paradigm shift.
- **Openers and fillers:** "In today's fast-paced world", "in today's [anything] landscape", "In the ever-changing world of", "It's worth noting that", "It is important to note", "Interestingly", "Notably", "Importantly", "Let's dive in", "Let's take a closer look", "Here's the thing", "So, what does this mean?", "At its core", "At the end of the day", "When it comes to".
- **Significance inflation:** "marks a turning point", "a pivotal moment", "represents a shift", "sets the stage for", "a sign of the times", "speaks volumes", "the writing on the wall", "reflects broader trends", "signals a new era".
- **Market clichés:** "headwinds", "tailwinds", "perfect storm", "new normal", "bloodbath", "the great reset", "tech winter", "thaw", "green shoots", "a tale of two markets", "the elephant in the room", "cautious optimism", "mixed bag", "only time will tell", "remains to be seen", "the jury is still out".
- **Vague attribution:** "experts say", "many believe", "observers note", "some argue", "industry reports suggest". If a source matters, name it and cite it.
- **Chatbot residue:** "I hope this helps", "Certainly", "Great question", "Here is a summary", "Here is the summary", "As of my last update", "based on available information", "Let me know".
- **Generic endings:** "the future looks bright", "exciting times ahead", "one thing is clear", "In conclusion", "In summary", "Ultimately".

### Constructions

- **Negative parallelism.** No "It's not just X, it's Y", "not only X but Y", "This isn't about X. It's about Y." State Y.
- **Rule of three.** Don't group things in threes for rhythm. If there are two reasons, give two. Lists of three are fine when there really are three items, like the three comparison windows.
- **Trailing -ing analysis.** No sentences that end in ", highlighting...", ", underscoring...", ", reflecting...", ", signaling...". If the implication matters, give it its own sentence with a subject.
- **Synonym cycling.** Pick one name for a thing and keep it. "Hiring posts" stays "hiring posts", not "listings", then "ads", then "openings". "Junior" stays "junior".
- **False ranges.** No "from X to Y" unless X and Y are two ends of a real scale ("from 8% to 38%" is fine).
- **Rhetorical questions** as transitions or headlines. Ask a question only when the next sentence answers it with data.
- **Signposting.** No "we come back to that below", "more on that later", "as we'll see". Say it where it belongs.
- **Clever turns.** A twist line ("the bottom hasn't been invited", "this data can't convict them") reads as a writer performing. One plain sentence that says the finding beats it.
- **Copula dodging.** "Is" over "serves as", "stands as", "boasts", "features".
- **Stacked hedges.** "Could potentially suggest", "may possibly indicate". One hedge, with a reason (section 1). A one-word hedge sentence ("Maybe.") is a stacked hedge in disguise.

### Typography

- **Em dashes:** none in headlines, deks, chart titles or section headings. At most two in the body. Commas, colons, parentheses and periods do the same work.
- Straight quotes ("), not curly.
- No bold or italics for emphasis in the prose. Italics are for publication names only.
- No emojis, no exclamation marks.
- Headings in sentence case.
- No bullet lists in the article body. The column is prose. The ledger and front matter are the only lists.

### Soul is required too

Clean but voiceless is its own tell. A month of flat numbers read out in order sounds like a template. Have a view about what the month means. Vary sentence length. Make one comparison a reader will remember ("the thread is just over a third the size it was in 2021"). Let the "to be sure" paragraph actually concede something. Every article should tell the reader something they didn't know before they opened it. If you'd be bored reading it aloud, rewrite it.

## 6. Worked example

This example uses real numbers: the October 2026 export (`generated_at` 2026-11-04T12:07:47Z). It is saved as `site/articles/_sample-jobs-report.md`, which is a sample, not a published issue: files starting with `_` load only in authoring mode (`?issue=_sample-jobs-report` on a local server, or with `?mock=1`). The article below and that file must stay identical, except that the full ledger lives only in the file. It has four sections and runs about 800 words of prose.

The published October 2026 column (`site/articles/2026-10.md`) was written before this framing, with Hacker News as its subject. It stays as an archived edition with its correction. Compare the two to see the difference: the same HN numbers appear here, but as one source in the third section, beside what Indeed and the BLS show.

### The article

```markdown
---
month: 2026-10
headline: "Software job ads rose, but computer systems design employment slipped"
dek: "Indeed's index of US software job postings rose 22% in a year, while the BLS counted 1% fewer people working at computer systems design firms."
byline: "Software Engineering Jobs Report"
ribbon: "external:indeed_software_postings.US"
---

Ads for software work rose this year. Indeed's index of US software development job postings rose 22% over the year to early October. Employment at computer systems design firms went the other way. The Bureau of Labor Statistics counted 1% fewer people working there in September than a year earlier.

So far the rise is in ads. Indeed's index reached 78.3 in the week to October 2, up from 64.3 a year earlier, and it rose in 10 of the 12 monthly readings since October 2025. Over the year to September, the BLS counted about 32,000 fewer people at computer systems design firms, and employers in the information sector reported 9% fewer job openings in August than a year earlier. On Hacker News, employer posts in the monthly hiring thread held about steady, within ordinary swings for a thread this size.

::compare{title="Postings rose on Indeed while BLS employment and openings fell" metrics="external:indeed_software_postings.US,external:jolts_openings_information.US,external:ces_computer_systems_design.US,posts.hiring,seekers_per_post.hiring,seekers_per_post_us.hiring,salary_disclosed_share.hiring" against="3m,1y,5y"}

## Software job postings on Indeed rose for most of the year

Indeed's index of US software development postings stood at 78.3 in the week to October 2, where February 2020 equals 100. In the same release, the index was 64.3 a year earlier, so it rose 22%. It went up in 10 of the 12 monthly readings since then.

The longer view is less bright. In October 2021, during the pandemic-era hiring boom, the index was 179.4, and the latest reading is 56% below it. As first published, the index peaked at 231.6 in March 2022. Today's level is about a third of that.

To be sure, the BLS count of job openings points the other way. Employers in the information sector reported 128,000 open jobs in August, against 141,000 in August 2025 in the same release, 9% fewer. The two sources count different things. Indeed counts ads for software development work at employers in every industry. JOLTS counts every opening, software or not, at publishers, broadcasters, telecom carriers and data processors. JOLTS is also not seasonally adjusted, which is why this comparison sets August against August. Indeed's rise held for most of the year, but it is a rise in ads for software work, and the industry count of openings has not confirmed it.

::chart{type="line" external="indeed_software_postings.US" from="2021-06" title="Indeed's US software postings rose 22% in a year but are a third of their 2022 peak"}

## Employment at computer systems design firms slipped

The BLS counted 2.36 million people working at computer systems design firms in September, 1% fewer than the 2.39 million it now estimates for September 2025. Five years ago, in September 2021, the count was 2.35 million, about the same as today.

Our chart strings together each month's first estimate, so it shows a larger fall since 2024 than that. Part of it is a step in early 2025, when the BLS revised the whole series. Compared within one release, the past year's drop is about 32,000 people.

::chart{type="line" external="ces_computer_systems_design.US" from="2019-01" title="Employment at computer systems design firms is below its 2024 level" note="Values as first published. BLS's yearly benchmark revision shows as a step in early-year months, including February 2025."}

## On Hacker News, job seekers per hiring post doubled

Employer posts in Hacker News's monthly hiring thread held about steady: 289 in October, against 351 a year earlier, a gap within ordinary swings for a thread this size. People posting in "Who wants to be hired?" rose 70%, to 685. That left 2.4 job seekers for every hiring post, up from 1.2.

Most of that rise came from people outside the US. Counting only US job seekers against hiring posts open to US workers, the ratio went from 0.7 to 1.0, a change within ordinary swings. The thread leans toward startups, so it is a narrow view, and on it the job seekers' side did the moving.

::chart{type="line" metric="seekers_per_post.hiring" from="2014-05" title="Job seekers per hiring post on Hacker News doubled in a year, to 2.4" annotate="2020-03:COVID shutdowns;2023-01:Big Tech layoffs"}

## More software job ads state pay, on Indeed and on Hacker News

Forty-nine percent of Indeed's US software postings stated pay in August, up 9 percentage points from 40% in August 2025 in the same release. Hacker News agrees on direction. Thirty-one percent of October's hiring posts gave a yearly salary, against 22% a year earlier, a gap just past ordinary swings.

The two sources measure the same thing in different places. Indeed's share is taken across Indeed's US postings, and the Hacker News share covers startup posts written in free text.

::chart{type="line" external="indeed_software_pay_transparency.US" title="Indeed's share of software postings that state pay rose 9 points in a year"}

## What this data can't tell us

None of these sources counts software engineers directly. Indeed counts ads, not hires. The BLS series count industries, not occupations, so they include jobs that aren't software work and miss software engineers employed in other industries. They also run behind: September is the newest employment month here and August the newest for openings. The BLS revises its figures, which is why every change here compares two numbers from the same release. Hacker News posts aren't jobs, and the people who post there are not a sample of anyone in particular. Nor can any of these numbers say why ads rose while employment fell.

For now the recovery is in the ads. The BLS counts run one to two months behind, so they are the ones to watch next.
```

### The humanizer and honesty pass

The draft went through the `humanizer` checklist and the rules in section 4 before this version. What they caught, and the fix:

| Draft | Problem | Fix |
|---|---|---|
| "So far the recovery is in the ads, not in the payrolls." | Negative parallelism | "So far the rise is in ads. Payroll counts moved the other way." |
| "Payroll counts have not caught up." | Implies they will, and that ads lead payrolls: a mechanism the data can't show | "Payroll counts moved the other way." |
| "The Indeed rise is real" | Outside series have no noise bar, so "real" claims a test we didn't run | "Indeed's rise held for most of the year", which counts directions instead |
| "Indeed counts ads, which can be reposted, left up or never filled." | An outside claim with no source | "Indeed counts ads, not hires." |
| "miss software engineers at banks, retailers and carmakers" | Examples from memory, no source | "miss software engineers employed in other industries" |
| "BLS counts, which trail the ads by one to two months" | The lag is behind the issue month, not behind the ads | "The BLS counts run one to two months behind" |

An independent review of that draft then caught the errors below. The first was serious: the draft's outside changes subtracted values from two different releases.

| Draft | Problem | Fix |
|---|---|---|
| "rose 23%" (Indeed), "2% fewer" (CES), "3% larger" than in 2021 (CES) | Each change set this release's value against a value first published a year or five years earlier, so BLS revisions and a benchmark step read as market moves | Same-release changes from `compare`: 22%, 1% fewer, and about the same as in 2021 |
| "Averaged over its last 12 readings, openings were 105,000" | Averaged 12 issues, which repeat and skip reference months, across several releases | Cut. The August-against-August change from one release carries the point |
| "people posting that they want work grew much faster than the companies posting that they are hiring" | Hiring posts moved within ordinary swings; only the job seekers' side moved | "employer posts in the monthly hiring thread held about steady, within ordinary swings" |
| Headline "Software job postings rose this year, but employment slipped" | "Employment" read as all software employment; CES counts one industry | "Software job ads rose, but computer systems design employment slipped" |
| "rose in 10 of the last 12 months" | Those are first-published readings from different releases | "rose in 10 of the 12 monthly readings" |
| "Indeed's share covers ads across the whole US market" | Indeed is one job site, not the market | "Indeed's share is taken across Indeed's US postings" |

### The ledger, in part

Every line names an `external` key with its `ref_period`, or an HN metric with its exported bar. The full ledger is at the end of the file.

```markdown
<!-- ledger (excerpt)
rounding: shares to whole %, point gaps from printed shares, % change from unrounded values, ratios one decimal, outside thousands as whole numbers or millions to two decimals
metrics.json generated_at 2026-11-04T12:07:47Z; outside values as published by each HN month's as-of date
outside changes: issue value against its same-release `compare` reading (data/external, metrics.json external series[].compare); ref periods named
headline/dek postings rose 22%    external indeed_software_postings.US 2026-10 = 78.33 (ref 2026-10-02, release 2026-10-06); compare.1y = 64.3 (ref 2025-10-02); 78.33/64.3 = 1.218; no bar
headline/dek employment 1% fewer  external ces_computer_systems_design.US 2026-10 = 2355.4 (ref 2026-09, vintage 2026-10-09); compare.1y = 2387.6 (ref 2025-09); 2355.4/2387.6 = 0.9865
10 of the 12 monthly readings     indeed issue values (as first published) 2025-10..2026-10: up 10, down 2 (2026-05 72.15 < 72.44; 2026-07 72.51 < 72.57); no large revisions in this series
information sector 9% fewer       external jolts_openings_information.US 2026-10 = 128 (ref 2026-08); compare.1y = 141 (ref 2025-08); 128/141 = 0.908
hiring posts held about steady    posts.hiring 2026-10 = 289, 2025-10 = 351; ln -0.194 vs bar 1y 0.338; inside
peaked 231.6 March 2022, first published  indeed issue values max over 2021-06..2026-10 = 231.57 at HN month 2022-03 (ref 2022-03-04)
information sector examples       NAICS 51 definition, BLS Industries at a Glance https://www.bls.gov/iag/tgs/iag51.htm
2.35 million September 2021       CES compare.5y = 2348.9 (ref 2021-09); 2355.4/2348.9 = 1.003, about the same
US-only 0.7 to 1.0, in swings     seekers_per_post_us.hiring 2025-10 = 0.7343, 2026-10 = 1.0363; ln 0.344 vs bar 1y 0.358; inside
31% vs 22%, just past swings      salary_disclosed_share.hiring 2026-10 = 0.3133 (n 233), 2025-10 = 0.2166 (n 314); printed gap 9; unrounded 0.0967 vs bar 1y 0.095; just outside (hedged)
-->
```

## 7. Fact-check checklist

The reviewing agent works through this list before an article is published. It reads the article, `metrics.json` and the sample file fresh, and doesn't take the writer's word for anything. A "must pass" failure blocks publication and goes back to the writer with the line, the rule and the fix. "Editor's judgment" items are notes the writer should weigh, not blockers.

### Must pass

Numbers and ledger

- [ ] Every number and shape claim in the headline, dek, prose, chart titles and notes has a ledger line.
- [ ] Each ledger line names a `metrics.json` key and month, and the value matches the file for the current `generated_at`. Outside values also name their `ref_period`.
- [ ] Derived numbers recompute from the ledger inputs: percent changes from unrounded values, point differences from the printed shares.
- [ ] Rounding follows the table in section 1.
- [ ] Every superlative ("highest since", "first time", "on record", "straight months", "peak", "low") is checked against the full series, from the right series start.
- [ ] "A year ago", "three months ago" and "five years ago" point at the right months.
- [ ] Outside facts come from the event table or have a cited source in the ledger.

Sources

- [ ] Every claim names its source, and the headline, dek and lede are about the software engineering job market, synthesized across sources. None is framed as "HN has..." or rests on Hacker News alone.
- [ ] No single source stands in for the market. Market-level words ("demand", "hiring", "the market") name the sources behind them.
- [ ] Where sources disagree, the text says so and says what each measures (postings, openings, hires, layoffs, employment, filings, self-posts).
- [ ] Every outside value whose reference period differs from the issue month states it ("in August"). No sentence sets different reference periods against each other without naming both.
- [ ] Every outside change is computed from the issue value and its same-release `compare` reading, and the ledger shows both with their reference periods. Where `compare` has no reading, the text says there is no same-month value.
- [ ] JOLTS and CES are described as industries ("the information sector", "computer systems design firms"), never as software jobs.

Noise and claims

- [ ] Every HN move described as a change clears the noise bar for its `n` (section 4). Moves below it are called flat or left out.
- [ ] Outside changes are stated in plain language with their number. None is called "about the same", "within the noise" or "real", and no month-to-month move in a not seasonally adjusted series is called a rise or fall.
- [ ] Verbs of size match the table in section 4.
- [ ] Relative changes on shares only for large moves, with both endpoints printed.
- [ ] Before a change in `seekers_per_post` is called "doubled", a surge or any large move, the checker compares `seekers_per_post_us` over the same months. If the US ratio moved much less, the text says so (for example, "most of the rise came from people outside the US"), and the ledger carries both ratios.
- [ ] No causal verbs with a measure, and no motives. Annotated events are described as timing.

Vocabulary of the data

- [ ] No "jobs", "openings" or "roles" for post counts.
- [ ] HN is never called "the job market" or "tech hiring". HN figures are cited as one source, for example "employer posts in Hacker News's monthly hiring thread".
- [ ] First mention of seeking posts says "people posting in 'Who wants to be hired?'".
- [ ] No "jobs" for Indeed postings: they are ads ("postings"), not jobs or hires.
- [ ] Jev-based measures are flagged as estimates at first mention, and each is named for what it measures.

Comparisons

- [ ] The `::compare` strip has the seven core rows (section 2, "The data turn") and `against="3m,1y,5y"`, or a stated reason for a skipped window.
- [ ] Unusual base months (2020 shutdowns, the 2021 boom) are named as such where they are used.
- [ ] Salary comparisons across more than a year say "not adjusted for inflation" once.

Charts

- [ ] Every chart's type fits its claim (section 3), and `stack` is never stacked-area.
- [ ] Every directive uses metric, breakdown and external ids that exist in `metrics.json`, and attributes that its type accepts.
- [ ] A chart of JOLTS is read as the 12-month average it draws, and an outside chart's `from` doesn't start before the series' point-in-time history.
- [ ] Each `title` states a finding that is true of the chart as drawn.
- [ ] `from` doesn't crop history to exaggerate a move.
- [ ] Annotations come from the event table, two per chart at most.

Fabrication

- [ ] No invented people, quotes, anecdotes or scenes.
- [ ] Every quoted post is in `site/data/samples/YYYY-MM.json`, with its HN item id in the ledger.

### Editor's judgment

- [ ] The headline is a claim, and the sections support it.
- [ ] Lengths are near the targets in section 2 (or the quiet-month shape). Three to five sections.
- [ ] One hedge per claim at most, with a reason.
- [ ] The "to be sure" paragraph names a real counter-reading and the article answers it.
- [ ] The "what this data can't tell us" paragraph covers the limits this month's argument leans on.
- [ ] The kicker stays inside the data.
- [ ] Each section has one chart that backs its heading.
- [ ] One term per thing, with no synonym cycling.
- [ ] Nothing from the banned list in section 5. Search the prose, titles and notes for each banned word, not the ledger or front matter.
- [ ] Em dashes: none in headline, dek, titles or headings, and two at most in the body.
- [ ] AP number style: one through nine spelled out, no sentence starts with a numeral, % with numerals, "percentage points" for share differences.
- [ ] American spelling throughout. Front matter matches `docs/architecture.md`.
- [ ] Read it aloud once. Flag any sentence that sounds like a template, and ask whether the article tells the reader something they didn't know.

## Sources

Data journalism and FiveThirtyEight

- Julia Wolfe (FiveThirtyEight senior data editor), interviewed by Danica Jefferies, Storybench, October 27, 2021. On letting findings change the story, killing noisy stories and charts that pay the reader back. https://www.storybench.org/?p=13447
- Micah Cohen (FiveThirtyEight managing editor), "Politics and probability," Conversations with Data #60, European Journalism Centre, October 2020. On ranges, "favored" over certainty, and being specific about what results mean. https://datajournalism.com/read/newsletters/politics-and-probability
- "This is how FiveThirtyEight is trying to build the right amount of uncertainty into its 2020 election data analysis," Nieman Lab, July 2020. https://www.niemanlab.org/2020/07/this-is-how-fivethirtyeight-is-trying-to-build-the-right-amount-of-uncertainty-into-its-2020-election-data-analysis/
- Nate Silver, "The Media Has A Probability Problem," FiveThirtyEight, September 2017, as summarized by MPR News. https://www.mprnews.org/story/2017/09/21/how-did-media-get-election-wrong-a-hurricane-has-the-answer
- "How to pitch FiveThirtyEight" (thesis first, caveats and counterexamples expected). https://fivethirtyeight.com/how-to-pitch-fivethirtyeight
- "How FiveThirtyEight's 2020 Presidential Forecast Works," FiveThirtyEight, 2020 (methodology written for a general reader). https://fivethirtyeight.com/features/how-fivethirtyeights-2020-presidential-forecast-works-and-whats-different-because-of-covid-19

Jobs-report writing and noise

- "The Jobs Report Is Overhyped. Here's Why That's A Problem," FiveThirtyEight, on payroll margins of error and treating one month as a best guess. https://fivethirtyeight.com/features/the-jobs-report-is-overhyped-heres-why-thats-a-problem
- NPR Planet Money, "What Does The Jobs Report Really Say?" January 31, 2013. On the BLS confidence interval and reading multi-month patterns. https://www.npr.org/sections/money/2013/01/31/170755257/what-does-the-jobs-report-really-say
- "Does the Margin of Error Make the Jobs Report Meaningless?" U.S. News, February 7, 2014. https://www.usnews.com/news/blogs/data-mine/2014/02/07/does-the-margin-of-error-make-the-jobs-report-meaningless
- Axios, "Why U.S. jobs numbers get revised," October 4, 2024. https://www.axios.com/2024/10/04/us-job-number-revisions
- Foreign Press USA, "Decoding the Jobs Report," July 7, 2023. https://foreignpress.org/journalism-resources/decoding-the-jobs-report-what-journalists-should-know-about-reporting-on-employment-numbers

Opinion-column structure

- Harvard Kennedy School Communications Program, "How to Write an Op-Ed" (hook, setup, nut graph, argument, conclusion). https://www.hks.harvard.edu/sites/default/files/Academic%20Dean%27s%20Office/communications_program/digital_resources/js_how_to_oped_2_pgs_11_3_22.pdf
- Cornell INFO 4240, "What is an op-ed made of?" (the "to be sure" paragraph). https://courses.infosci.cornell.edu/info4240/2024fa/my_assets/img/What%20is%20an%20oped%20made%20of.docx
- University of Washington Odegaard Writing Center, "Concessions and Counterarguments." https://depts.washington.edu/owrc/wp-content/uploads/2021/05/Concessions-and-Counterarguments.pdf
- Poynter, "The Nut Graf, Part I," May 19, 2003. https://www.poynter.org/archive/2003/the-nut-graf-part-i/

Chart text

- Office for National Statistics, "Say what you see: the way we write chart titles is changing," January 28, 2019. https://digitalblog.ons.gov.uk/2019/01/28/say-what-you-see-the-way-we-write-chart-titles-is-changing
- ONS Service Manual, "Chart text" (titles describe the main trend; subtitles give measure, geography and period). https://service-manual.ons.gov.uk/data-visualisation/guidance/chart-text
- Albert Rapp, R for the Rest of Us, November 2023, on "active titles" that state the insight. https://rfortherestofus.com/2023/11/theme-minimal
- Stephanie Evergreen, "Strong Titles Are The Biggest Bang for Your Buck." https://stephanieevergreen.com/strong-titles/

Numbers style

- Writer's Digest, "10 Important Rules and Conventions of AP Style" (2019 switch to the % sign; one through nine). https://writersdigest.com/write-better-fiction/10-important-rules-and-conventions-of-associated-press-ap-style

HN hiring threads as a signal

- Gergely Orosz, "Is there a drop in software engineer job openings, globally?" The Pragmatic Engineer, March 2023. Treats HN "Who is hiring?" as a startup proxy, alongside Indeed. https://blog.pragmaticengineer.com/is-there-a-drop-in-software-engineer-job-openings-globally/

AI tells

- Wikipedia, "Signs of AI writing," WikiProject AI Cleanup (via the `humanizer` skill). https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing

## Changes within noise on the page

The renderer reads the exported `bar` (section 4, "The noise bar"), so the page and the ledger use the same number. A move inside the bar is shown gray with "≈" and read as "about the same"; salary medians with fewer than 30 posts show "too few posts". The prose must agree with the page: never call a ≈ move a rise or fall. Outside rows in the strip have no bar: they show a plain gray change with an arrow, computed within one release, the reference period of each value, "Not seasonally adjusted" when that applies, "seasonal" in place of a change between different calendar months of an unadjusted series, and "No same-month value" when the release has none.
