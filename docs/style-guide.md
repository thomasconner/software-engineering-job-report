# Style guide: the monthly column

This guide is for the agent that writes `site/articles/YYYY-MM.md` and for the agent that fact-checks it. The spec (`docs/spec.md`) says what the column measures. The architecture (`docs/architecture.md`) says where the numbers live and how directives are written. This file says how the column sounds, how it is put together, and what it is not allowed to claim.

## 1. Voice

We write like a columnist who has done the math. Every article makes one argument about the month and defends it with numbers a reader can check. The reader is smart, busy and not a statistician: an engineer deciding whether to job-hunt, a founder deciding whether to hire, a reporter who wants to know if startup hiring is picking up. We are plain, confident and specific. We have opinions, and we show the chart that earned them. When the data is noisy we say so once, in the sentence where it matters, and then we move on. We don't cheerlead a recovery or mourn an industry. A month that looks like the month before is a fine result, and we can say so.

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

Fractions are fine for big moves when they're accurate: "just over a third of the 2021 peak" for 36%, "fell by about two-thirds" for a 65% drop. The exact number goes in the same paragraph or the chart.

### Comparisons

The pattern is: current value, direction, reference value, reference period.

- "Hiring posts rose to 362, up from 296 a year ago."
- "The remote share was 37%, down from 41% three months ago and 63% five years ago."
- Name the context when the reference month is unusual: "five years ago, in October 2021, during the pandemic-era hiring boom".
- "A year ago" means the same month last year. "Three months ago" means the thread three months back, not an average. Say "the three months through September" if you mean an average.
- Superlatives ("highest since", "lowest on record", "first time") need a check against the full series, and the check goes in the ledger (section 4). The series don't all start at the same time. Hiring metrics start in April 2011 and have no gaps. Seeking metrics, including `seekers_per_post` and `seeker_mood`, start in May 2014. "On record" means since the start of that metric's series, and the first use in an article says which: "the most since the hiring thread began in April 2011".

### Hedge once, where the doubt lives

A claim that clears the noise bar in section 4 is stated flat. No "may", "appears to" or "seems". A claim that is close to the bar, or rests on a classifier with a weak validation score, gets one hedge, in one sentence, with the reason:

> Junior posts went from 9% to 6% in the past year, a gap that sits inside the noise for months this size.

Not: "This could potentially suggest that junior hiring may be somewhat weakening." Stacked qualifiers tell the reader we don't know what we think. One hedge with a reason tells them exactly how much to trust the number.

The "what this data can't tell us" paragraph (section 2) is about the source's limits. It doesn't count as the hedge, and it's no excuse to hedge the findings again.

### Person

- "We" is the column. Use it for what we did and what we think: "we count top-level posts", "we read this as a top-down recovery". The byline is "Software Engineering Job Report", so there is no "I".
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
| What this data can't tell us | 60 to 130 words | The source's limits, as they apply to this month's argument. |
| Kicker | 1 to 3 sentences, about 50 words | Takes the argument one step further. Never a summary. |

### Headline

A claim, not a label. It should be checkable against the data and narrow enough to be wrong.

- Good: "HN's hiring thread is growing again, but not for junior engineers"
- Good: "Remote work is losing, but not where you'd think"
- Good, for a quiet month: "Nothing moved in October, and that is the story"
- Bad (a label): "October 2026 job market report"
- Bad (a question): "Is the tech hiring freeze over?"
- Bad (hype): "The AI hiring boom is here"

Sentence case, no period, no em dash, no colon-subtitle ("AI hiring: what it means").

### Dek

The line under the headline. It gives the reader the one or two numbers that justify the headline. "October's thread had the most hiring posts since July 2024, but only 6% were for junior engineers, down from 17% five years ago."

### Lede

Open on the tension, not on the method. Don't start with "Every month, we analyze..." or with a number the reader has no context for. The tension comes from the numbers: a contrast between two groups in the data, a surprise against last year, or a flat statement of what changed. A real post from the month's sample file can also open the piece (section 4 says how to quote one). Never open on an invented scene, person or quote. The lede can be argued. It can't be unsupported: whatever it asserts, a section backs up.

### Nut graf

The paragraph that tells the reader what the whole article argues and why they should keep reading. State the one argument in a sentence a friend would repeat. If you can't write that sentence, the article isn't ready. The nut graf carries the two or three numbers that matter most and sets up the compare strip.

### The data turn

Right after the nut graf comes the `::compare` strip. It has a fixed core so readers can compare months at a glance:

```markdown
::compare{title="The thread grew this year, but not for juniors" metrics="posts.hiring,seekers_per_post.hiring,new_grad_share.hiring,ai_native_share.hiring,salary_disclosed_share.hiring" against="3m,1y,5y"}
```

Add one or two extra metrics at the end when the argument uses them. Don't drop a core metric because it's dull this month. The strip is the "here's the data" moment. Don't restate every cell of it in prose. The prose picks the cells that matter.

### Sections

Each section is:

1. An `##` heading that states the finding, in sentence case. "AI companies now write more than a third of the posts", not "AI share".
2. The finding in the first sentence, with its number.
3. Context: the comparison windows, what the reference months were like, the strongest other reading.
4. One `::chart` directive that backs the heading. Place it after the prose, as the evidence for what was just said.

Order sections by importance to the argument, not by the order in the spec. Sections the argument doesn't need are left out. They live on the dashboard. Three strong sections beat five thin ones.

### The "to be sure" paragraph

Every article has one "to be sure" paragraph, inside the section whose finding it tests. It takes the strongest objection to the argument head-on. Name the counter-reading specifically, give it its best numbers, then say why the argument survives or how far it has to retreat. If it doesn't survive, change the argument. FiveThirtyEight's editors called this letting the data change the story.

The strongest objections for this data are usually one of these:

- **Title inflation.** Companies relabel the same role as "senior", so the seniority mix shifts while hiring doesn't. Test it with `new_grad_share`, which asks a question titles don't answer.
- **A change in who posts.** The mix of companies on HN shifts (more AI startups, fewer agencies, more remote-first firms), so a share moves without any one company changing its behavior.
- **A change in how posts are written.** Companies describe the same product differently over the years. See the drift rule in section 4.
- **The base month.** The comparison month was unusual (spring 2020, the 2021 boom).

### What this data can't tell us

A fixed `##` heading, every month, just before the kicker. Pick the two to four limits from section 4 that bear on *this* month's argument and say them plainly, in prose, not as a bullet list. Close any gap the argument invites but the data can't fill: "We don't split seniority by AI status, so we can't test whether the change in who posts explains the shift." This paragraph builds trust. Write it like you mean it, not like a disclaimer.

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

The subtitle names the measure and the period: "Share of 'Who is hiring?' posts from AI-native companies, January 2019 to October 2026." The renderer builds it from the metric's or breakdown's `label` in `metrics.json` plus the chart's date range, so the writer doesn't type it. The writer checks that it reads correctly. If it doesn't, fix the label in the export, not in the article.

### Notes

`note` is for what a reader needs to read this chart correctly, in one or two sentences:

- that a share is a Jev expected value ("Shares are expected values from a model's reading of each post");
- a skipped or unusual month;
- a definition the subtitle can't hold, quoted from the classifier's question text rather than paraphrased from memory.

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

## 4. Honesty rules for this data

These apply to every sentence. The fact-checker enforces them.

### No fabrication

- No invented people, quotes, anecdotes or scenes. No "Maria, a bootcamp grad in Austin". No "picture a founder scrolling the thread". The column has no reporting behind it beyond the data, so it doesn't pretend to.
- Color comes from the numbers, or from quoting a real post. Real posts come only from the month's sample file, `site/data/samples/YYYY-MM.json`, which the export writes. Quote the post's text, not the username, keep it to a sentence or two, and put its HN item id in the ledger. The sample files hold hiring posts only; never quote or paraphrase an individual job seeker.
- A quoted post illustrates a finding. It never stands in for one: "one company wrote X" can't support a claim about the thread.

### What a post is

- **Posts aren't jobs.** One "Who is hiring?" post can list one role or 20. Write "hiring posts" or "companies posting". Never write "jobs", "openings" or "roles" for a post count. A role level can describe which posts ("posts for senior engineers").
- **Seeking posts aren't all job seekers.** "Who wants to be hired?" posts come from people who chose to post on Hacker News. On first mention write "people posting in 'Who wants to be hired?'". After that, "job seekers posting" or "job seekers" is fine.
- **Hacker News isn't the job market.** The threads skew toward venture-backed startups, engineering roles and the Bay Area. Say "on Hacker News", "in the thread" or "among companies posting on HN". Never "tech hiring rose" or "the job market recovered". When you want to say something wider, say that HN agrees or disagrees with a named outside measure, and cite it in the ledger.
- **The snapshot is seven days.** Every month counts posts in the first seven days of its thread. Late posts don't count, past or present. Don't compare our counts to someone else's thread totals.
- **Survivorship.** Deleted posts are missing and edited posts show their latest text. Older months have had more time to lose posts, so counts from earlier years are a floor.
- **Series starts.** The hiring series runs from April 2011 with no gaps (July and December 2011 use replacement threads). The seeking series starts in May 2014. The first seeking thread was posted by the user jader201, and the whoishiring account took it over in July 2014.

### How each metric is made

- **Jev estimates, shares:** `ai_native_share`, `new_grad_share`, `work_mode`, `seniority`, `industry`, `funding_stage`. These are expected values: the sum of the model's probabilities divided by the number of posts. Say "by our classifier's estimate" or similar once per article, the first time one appears.
- **Jev estimate, score:** `seeker_mood` is a mean score from 0 (discouraged) to 4 (upbeat). It isn't a share and doesn't take points-of-share language.
- **Counts:** `posts`, `seekers_per_post`, `replies_per_post`.
- **Regex:** `salary_disclosed_share`, `salary_min_median_usd`, `salary_max_median_usd`, `remote_token_share`, `onsite_token_share`, `visa_share`. These are exact counts of what the text says, but regex can miss unusual formats.
- **Join:** `new_company_share`, `returning_company_share`. These depend on company names pulled from the header line by regex, so a renamed company or a typo counts as new. They also need history: in 2011 every company is "new". Don't use their 2011 values.
- **Vocab:** `stack`. This is the share of posts mentioning each term from a fixed list. Terms overlap and don't sum to 1.

### Classified shares are estimates, and they drift

- Jev shares carry two kinds of error: the model can be wrong about a post, and a month of about 300 posts is a small sample. Both mean small moves are noise.
- **Era drift.** The classifier reads only the text, and posts from 2011 and 2026 are written differently. "AI" in particular moved into marketing copy after 2022, so some of the rise in `ai_native_share` may come from how companies describe themselves rather than what they build. Over five years or more, name this limit whenever an argument leans on a Jev share.
- Name the measure for what it measures. `ai_native_share` is "posts that describe a product built on AI". It isn't "AI jobs", "AI companies" as a fact, or "posts mentioning AI". `remote_token_share` is "posts with REMOTE in the header line", which differs from `work_mode` remote. Pick one per article and stick to it.
- **Junior claims lead with `new_grad_share`.** It asks whether a post says it will consider new grads, which a title change doesn't affect. The `seniority` breakdown supports it. The column's term for the low end of the seniority mix is "junior". Don't cycle through "entry-level", "beginners" and "first job". `new_grad_share` is called "posts open to new grads" when it's named.

### The noise bar

Until `metrics.json` carries intervals, use these rules. They cover sampling error only, so they're a floor, and classifier error sits on top.

**Shares.** For a change between month 1 and month 2, the bar in points is

> 1.96 × √(p(1 − p)(1/n₁ + 1/n₂)) × 100

where p is the average of the two shares. Quick reference for two months of about 300 posts each:

| Share near | Noise bar (points) |
|---|---|
| 5% | 3.5 |
| 10% | 5 |
| 20% | 6.5 |
| 30% to 50% | 7.5 to 8 |

**Counts.** Treat post counts as Poisson. The bar for a change from n₁ (the reference month) to n₂, as a fraction of n₁, is 1.96 × √(n₁ + n₂) / n₁. Near 300 posts that's about 17%. Near 1,000 it's about 9%. Real counts swing more than Poisson (holidays, the day the thread goes up), so this is a floor too.

**Ratios.** For `seekers_per_post`, the bar is relative: 1.96 × √(1/S₁ + 1/H₁ + 1/S₂ + 1/H₂), where S is seeking posts and H is hiring posts in each month (S = ratio × H). With about 300 hiring posts and 800 seeking posts, that's about 18%.

**Salary medians.** Use a median only when at least 30 posts disclosed pay in each month compared. Treat changes under 5% as noise. That 5% is a convention until the export carries intervals.

**Mood.** Treat changes in `seeker_mood` under 0.2 points as noise until the export carries its standard deviation.

**Many comparisons.** Each article looks at dozens of numbers across three windows, so some will clear the bar by chance. Prefer moves that persist: the 1y window, or a three-month average against the same three months a year earlier. Treat a 3m move that the 1y window doesn't confirm as suspect. Counting directions is allowed and often more honest than one comparison: "the share has risen in 10 of the last 12 months".

Below the bar: say the measure was about the same, or leave it out. Don't build a section on it. Near the bar: state it with the one hedge. Above it: state it flat.

### Words of size

Match the verb to the move.

| Move | Verbs |
|---|---|
| Below the noise bar | was about the same, held steady, roughly flat |
| Above the bar | rose, fell, grew, shrank, slipped, climbed |
| Largest move in at least 12 months | jumped, dropped, surged, sank, and say "the largest in X months" |
| Record or multi-year extreme | Only with a ledger check: "lowest since March 2013", "the most since the hiring thread began in April 2011" |

"Plunged", "soared", "collapsed", "skyrocketed" and "exploded" are reserved for moves of a third or more, and still need the check.

### No causal claims, no motives

The data shows when things moved, not why. Annotated events are context.

- Banned with a measure as the subject or object: "caused", "drove", "led to", "fueled", "triggered", "because of", "due to", "thanks to", "as a result of", "killed", "sparked".
- Allowed: "after", "since", "coincided with", "began rising a few months after", "followed".
- No motives. The data doesn't say what companies want, prefer or fear. "Companies are skipping juniors to save on training" is a motive. "Fewer posts say they'll consider new grads" is a finding.
- When a cause is the natural question, name it as a question the data can't answer, in the "can't tell us" paragraph. You can say which explanation fits the timing better. You can't say it's proven, and you don't cast suspects.

### Every number is checkable

- Every number in the prose, headline, dek, chart titles and notes comes from `site/data/metrics.json` for a named key and month, or is computed from those values with the rounding rules in section 1.
- Derived numbers (percent changes, point differences, expected counts, "a third of", "fourth straight month") get a ledger line showing the inputs.
- Shape words count as claims: "last year's low", "the 2021 peak", "the height of the boom", "started climbing in early 2023". Each gets a ledger line pointing at the series.
- Outside facts (event dates, laws, company layoffs) come only from the event table in section 3 or carry a source in the ledger.
- No numbers from memory, other articles or other datasets in the prose.
- Don't compare a metric before its series starts (see "Series starts" above).

### The numbers ledger

At the end of the article file, after the kicker, add an HTML comment listing every number and shape claim in the text with its source. Browsers don't display HTML comments, so readers never see it. The fact-checker works from it. The first line restates the rounding rule so the checker knows how each number was made.

```markdown
<!-- ledger
rounding: shares to whole %, point gaps from printed shares, % change from unrounded values
362 hiring posts            posts.hiring 2026-10 = 362
up 22% from a year ago      posts.hiring 2025-10 = 296; 362/296 = 1.223; bar 17%
most since July 2024        posts.hiring max(2024-08..2026-09) = 331; 2024-07 = 371
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

**This is an example. The month is hypothetical and every number is invented.** The same article is saved as `site/articles/_style-example.md` for renderer testing, and the two must stay identical. It has four sections and runs about 760 words of prose.

### The article

```markdown
---
month: 2026-10
headline: "HN's hiring thread is growing again, but not for junior engineers"
dek: "October's thread had the most hiring posts since July 2024, but only 6% were for junior engineers, down from 17% five years ago."
byline: "Software Engineering Job Report"
---

Hacker News' October hiring thread drew more posts than any month since July 2024. All of the growth over the past year came from posts for senior and staff engineers. For junior engineers, the thread looks about the same as it did a year ago, and far thinner than in 2021.

The thread drew 362 hiring posts, up 22% from a year ago. By our classifier's estimate, posts for senior and staff engineers rose by about 67 over the same year, a bit more than the thread's whole gain of 66. Posts for junior engineers made up 6% of the thread, against 17% in October 2021. Hiring on HN is recovering from the top down. So far, the recovery hasn't reached junior engineers.

::compare{title="The thread grew this year, but not for juniors" metrics="posts.hiring,seekers_per_post.hiring,new_grad_share.hiring,ai_native_share.hiring,salary_disclosed_share.hiring" against="3m,1y,5y"}

## Demand is climbing out of last year's low

October's 362 posts were up 20% from 301 in July. It was the fourth straight month above 300, and the rise shows up in both the three-month and one-year windows. Last year's low came in December 2025, when 262 companies posted.

The competition for those posts eased too. There were 2.4 people posting in "Who wants to be hired?" for every hiring post, down from 3.1 a year ago. In October 2021 the ratio was 0.6, and companies outnumbered the job seekers posting.

That month, 1,018 companies posted, the most since the hiring thread began in April 2011. It was the height of the pandemic-era hiring boom, so the 64% drop since then says as much about 2021 as about today.

::chart{type="line" metric="posts.hiring" from="2019-01" title="Hiring posts are up from last year's low but just over a third of the 2021 peak" annotate="2022-03:First rate hike;2023-01:Big Tech layoffs"}

## AI companies now write more than a third of the posts

Thirty-eight percent of October's posts described a product built on AI. A year ago the figure was 29%, and in October 2021 it was 8%. The share held between 9% and 11% through 2022 and started climbing in February 2023, three months after ChatGPT's public release. It has risen in 10 of the last 12 months.

Part of that rise could be vocabulary. Our classifier reads only what a post says, so a company that started calling itself an AI company looks the same to it as one that started building AI products. Read the 38% as the share of posts that pitch an AI product. That is still a large change in what the thread is selling.

::chart{type="line" metric="ai_native_share.hiring" from="2019-01" title="Posts describing AI products went from 8% to 38% in five years" annotate="2022-11:ChatGPT launches" note="Shares are expected values from a model's reading of each post."}

## Fewer than half as many posts are open to new grads as in 2021

Eleven percent of October's posts said they would consider new grads, down from 27% in October 2021. In counts, that is about 40 posts this October against about 275 five years ago. Over five years, a drop that size is far outside the noise.

The past year is less clear. Posts open to new grads went from 14% to 11%, a gap that sits inside the noise for months this size. The five-year decline is solid. Whether it continued this year, the data can't yet say.

::chart{type="line" metric="new_grad_share.hiring" from="2019-01" title="Posts open to new grads fell from 27% to 11% in five years" note="Shares are expected values from a model's reading of each post."}

## The seniority mix has moved up a rung

Posts for junior engineers fell from 17% of the thread in October 2021 to 6% this October. Posts for senior and staff engineers rose from 39% to 57% over the same years.

To be sure, a shift like this can come from titles rather than hiring. If companies started calling mid-level roles "senior", the senior share would climb without any change in who gets hired. The new-grad measure is the check on that reading, because it asks whether a post will consider someone straight out of school, and a title change doesn't alter the answer. It fell over the same five years. Title inflation may account for some of the senior gain. It can't account for the drop at the bottom.

::chart{type="slope" breakdown="seniority" months="2021-10,2026-10" title="Senior and staff posts gained 18 points as junior posts lost 11" note="Shares are expected values from a model's reading of each post."}

## What this data can't tell us

Hacker News is not the job market. Its hiring thread leans toward venture-backed startups and the Bay Area, and one post can advertise one role or 20, so more posts means more companies willing to post, not more jobs. The mix of companies that post also changes. If the companies posting today are different kinds of companies than in 2021, the seniority shift could come from that change in mix rather than from any one company changing how it hires. We don't split seniority by AI status, so we can't test that. The shares here are a model's estimates, and posts from 2021 and 2026 are written in different styles. Deleted posts are missing, which matters more for 2021 than for this month.

The thread is growing again. Its door for junior engineers isn't.

<!-- ledger
...
-->
```

### The humanizer pass

Two drafts went through the `humanizer` checklist and a fact-check before this version. What they caught, and the fix:

| Draft | Problem | Fix |
|---|---|---|
| "For a senior engineer, that is the best news this column has had to report in two years." | Unverifiable; the column didn't exist two years ago | Cut. The lede contrasts the two groups with numbers. |
| "That is a real rise, not a wobble." | Negative parallelism | Cut. "The rise shows up in both the three-month and one-year windows" makes the point with a check. |
| "No other category we track has moved this far this fast." | Unchecked superlative | "It has risen in 10 of the last 12 months", which goes in the ledger. |
| "...a few months after ChatGPT's launch, underscoring how quickly the market adapted." | Trailing -ing analysis, causal hint | Cut the clause. The annotation carries the timing. |
| "It's a squeeze that is real, significant and accelerating." | Rule of three; "accelerating" isn't shown | "Over five years, a drop that size is far outside the noise." |
| "...so far the bottom hasn't been invited." | Clever turn, implies intent | "So far, the recovery hasn't reached junior engineers." |
| "Maybe. Our numbers can't say, and we come back to that below." | One-word hedge plus signposting | Cut. The limit lives in the "can't tell us" paragraph. |
| "The size of this year's step is the part to hold loosely." | Vague hedge stacked on a hedge | "Whether it continued this year, the data can't yet say." |
| "They're the obvious suspect. This data can't convict them." | Casts a cause; clever turn | "We don't split seniority by AI status, so we can't test that." |
| "Companies are hiring again. They'd just prefer that someone else did the training." | Motive the data can't show | "The thread is growing again. Its door for junior engineers isn't." |
| "entry-level", "beginners", "first job", "junior" | Synonym cycling | "Junior" throughout; `new_grad_share` named as "posts open to new grads". |
| "Senior and staff-level roles made up 57% of posts" | Posts called roles | "Posts for senior and staff engineers" |
| "Job seekers got a little breathing room too" | Skipped the required first-mention phrasing | "people posting in 'Who wants to be hired?'" on first mention |
| Headline "Startups are hiring again, but the entry-level door keeps narrowing" | Speaks for all startups, not the thread | Names the thread. |

The draft also failed the noise bar. Its 16% one-year rise in posts and 17% drop in the seeker ratio both sat under the Poisson bar (about 17% and 18%), so the example's numbers were changed to ones that clear it rather than describing noise as a rise. In a real month the fix would go the other way: the prose would call those moves flat.

### The ledger for the example

```markdown
<!-- ledger (example, invented values)
rounding: shares to whole %, point gaps from printed shares, % change from unrounded values
most since July 2024            posts.hiring max(2024-08..2026-09) = 331; 2024-07 = 371
362 hiring posts                posts.hiring 2026-10 = 362
up 22% from a year ago          posts.hiring 2025-10 = 296; 362/296 = 1.223; bar 1.96*sqrt(296+362)/296 = 17%
senior+staff up about 67        seniority 2026-10 (0.45+0.12)*362 = 206.3; 2025-10 (0.38+0.09)*296 = 139.1; diff 67.2
whole gain of 66                362 - 296
6% junior                       seniority 2026-10 junior 0.06
17% in October 2021             seniority 2021-10 junior 0.17
up 20% from 301 in July         posts.hiring 2026-07 = 301; 362/301 = 1.203; bar 1.96*sqrt(301+362)/301 = 17%
fourth straight month above 300 posts.hiring 2026-07 = 301, 2026-08 = 318, 2026-09 = 327, 2026-10 = 362; 2026-06 = 288
last year's low                 posts.hiring min(2025-01..2025-12) = 262 at 2025-12
2.4 vs 3.1                      seekers_per_post.hiring 2026-10 = 2.4, 2025-10 = 3.1; change -23%; relative bar 18%
ratio 0.6 in October 2021       seekers_per_post.hiring 2021-10 = 0.6
1,018 in October 2021           posts.hiring 2021-10 = 1018
most since April 2011           posts.hiring max(2011-04..2026-10) = 1018 at 2021-10
2021 peak / height of the boom  same check as above
64% drop                        362/1018 = 0.356
just over a third               0.356
38%, 29%, 8%                    ai_native_share.hiring 2026-10 = 0.38, 2025-10 = 0.29, 2021-10 = 0.08; 1y gap 9 vs bar 7.2
held 9% to 11% through 2022     ai_native_share.hiring min/max(2022-01..2022-12) = 0.09/0.11
started climbing February 2023  ai_native_share.hiring 2023-01 = 0.11, rises every month 2023-02..2023-07
three months after ChatGPT      event table 2022-11; 2023-02 is three threads later
risen in 10 of last 12 months   ai_native_share.hiring month-over-month, 2025-11..2026-10: 10 up, 2 down
ChatGPT public release          event table, 2022-11
11% vs 27% new grads            new_grad_share.hiring 2026-10 = 0.11, 2021-10 = 0.27; gap 16 vs bar 4.7 (n 362, 1018)
fewer than half as many         0.11/0.27 = 0.41
about 40 vs about 275           0.11*362 = 39.8; 0.27*1018 = 274.9
14% to 11% is noise             new_grad_share.hiring 2025-10 = 0.14 (n 296); gap 3 vs bar 5.1
39% to 57% senior and staff     seniority 2021-10 senior 0.33 + staff_plus 0.06; 2026-10 0.45 + 0.12; gap 18 vs bar 6.0
junior 17% to 6%                gap 11 vs bar 3.8
18 points, 11 points            57 - 39; 17 - 6
-->
```

The ledger caught one real error along the way. A draft said "third straight month above 300", counting August through October and forgetting that July was also above 300. Writing the ledger line against the series caught it. A writer working from memory wouldn't have.

## 7. Fact-check checklist

The reviewing agent works through this list before an article is published. It reads the article, `metrics.json` and the sample file fresh, and doesn't take the writer's word for anything. A "must pass" failure blocks publication and goes back to the writer with the line, the rule and the fix. "Editor's judgment" items are notes the writer should weigh, not blockers.

### Must pass

Numbers and ledger

- [ ] Every number and shape claim in the headline, dek, prose, chart titles and notes has a ledger line.
- [ ] Each ledger line names a `metrics.json` key and month, and the value matches the file for the current `generated_at`.
- [ ] Derived numbers recompute from the ledger inputs: percent changes from unrounded values, point differences from the printed shares.
- [ ] Rounding follows the table in section 1.
- [ ] Every superlative ("highest since", "first time", "on record", "straight months", "peak", "low") is checked against the full series, from the right series start.
- [ ] "A year ago", "three months ago" and "five years ago" point at the right months.
- [ ] Outside facts come from the event table or have a cited source in the ledger.

Noise and claims

- [ ] Every move described as a change clears the noise bar for its `n` (section 4). Moves below it are called flat or left out.
- [ ] Verbs of size match the table in section 4.
- [ ] Relative changes on shares only for large moves, with both endpoints printed.
- [ ] No causal verbs with a measure, and no motives. Annotated events are described as timing.

Vocabulary of the data

- [ ] No "jobs", "openings" or "roles" for post counts.
- [ ] HN is never called "the job market" or "tech hiring".
- [ ] First mention of seeking posts says "people posting in 'Who wants to be hired?'".
- [ ] Jev-based measures are flagged as estimates at first mention, and each is named for what it measures.

Comparisons

- [ ] The `::compare` strip has the five core metrics and `against="3m,1y,5y"`, or a stated reason for a skipped window.
- [ ] Unusual base months (2020 shutdowns, the 2021 boom) are named as such where they are used.
- [ ] Salary comparisons across more than a year say "not adjusted for inflation" once.

Charts

- [ ] Every chart's type fits its claim (section 3), and `stack` is never stacked-area.
- [ ] Every directive uses metric and breakdown ids that exist in `metrics.json`, and attributes that its type accepts.
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
