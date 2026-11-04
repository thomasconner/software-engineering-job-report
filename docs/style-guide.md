# Style guide: the monthly column

This guide is for the agent that writes `site/articles/YYYY-MM.md` and for the agent that fact-checks it. The spec (`docs/spec.md`) says what the column measures. The architecture (`docs/architecture.md`) says where the numbers live and how directives are written. This file says how the column sounds, how it is put together, and what it is not allowed to claim.

## 1. Voice

We write like a columnist who has done the math. Every article makes one argument about the month and defends it with numbers a reader can check. The reader is smart, busy and not a statistician: an engineer deciding whether to job-hunt, a founder deciding whether to hire, a reporter who wants to know if startup hiring is picking up. We are plain, confident and specific. We have opinions, and we show the chart that earned them. When the data is noisy we say so once, in the sentence where it matters, and then we move on. We don't cheerlead a recovery or mourn an industry. A month that looks like the month before is a fine result, and we can say so in one line.

### Sentences

- Average 15 to 20 words. Vary it: a four-word sentence after a 30-word one is good. No sentence over 35 words.
- One idea per sentence. A sentence carries one value and at most two reference points ("37%, down from 41% three months ago and 63% five years ago"). Anything more becomes two sentences or a chart.
- Active voice, concrete subjects: "Hiring posts rose to 342", not "An increase in hiring activity was observed".
- Paragraphs run two to five sentences. A one-sentence paragraph is allowed once per article, for emphasis.
- Use "is", "are" and "has". Don't swap in "serves as", "stands as" or "represents".

### Numbers (AP style)

- Spell out one through nine. Use numerals for 10 and up: "three months", "12 months", "five years". Ages, percentages and dollar amounts always take numerals, even under 10.
- Don't start a sentence with a numeral. Spell it out ("Thirty-eight percent of posts...") or rewrite so the number comes later. Years are the one exception ("2021 was the peak").
- Percentages take the % sign with a numeral: 38%, 6%, 0.5%. AP adopted the sign in 2019. At the start of a sentence, spell out both: "Thirty-eight percent".
- Use "percentage points" for the difference between two shares. "The remote share fell 4 percentage points, to 37%." After the first mention in a paragraph, "points" alone is fine. Never say a share "fell 4%" when you mean four points.
- Use percent change for counts, dollars and ratios. "Hiring posts rose 16% from a year ago."
- Shares under 10% get points, not percent change. "Rust mentions rose from 2% to 3% of posts" is honest. "Rust mentions jumped 50%" is technically true and misleading.
- Dollars: "$185,000", "$1.2 million". No "$185K" and no "185k" in prose. Salaries are nominal; when comparing across more than one year, say "not adjusted for inflation" once in the article.
- Commas in numbers of 1,000 and up: 1,018.
- Ratios get one decimal and a plain-English unit: "2.4 job seekers for every hiring post".
- Scores get one decimal and their scale, every time: "a mood score of 1.7 on our 0-to-4 scale".
- Months: spell them out in prose ("October 2021", "last October"). No "Oct. '21", no "10/2021", no "Q4" unless quoting.
- "About" for approximations, not "approximately". Don't approximate a number the reader can see exactly in the chart.

### Rounding

| Measure | metrics.json unit | Write it as |
|---|---|---|
| Post counts | `count` | Exact: 342. Never round a count the reader can check against the thread. |
| Shares | `share` (0 to 1) | Whole percent: 0.384 becomes 38%. One decimal only for shares under 1%. |
| Point differences | derived | Whole points, computed from the rounded shares you print, so the reader's subtraction works. |
| Percent change | derived | Whole percent, computed from the unrounded values. |
| Medians in dollars | `usd` | Nearest $1,000. |
| Ratios | `ratio` | One decimal. |
| Scores | `score` | One decimal, with the scale. |

Fractions are fine for big moves when they're accurate: "about a third of the 2021 peak" for 34%, "fell by about two-thirds" for a 65% drop. The exact number goes in the same paragraph or the chart.

### Comparisons

The pattern is: current value, direction, reference value, reference period.

- "Hiring posts rose to 342, up from 296 a year ago."
- "The remote share was 37%, down from 41% three months ago and 63% five years ago."
- Name the month when the reference month is unusual: "five years ago, in October 2021, at the peak of the post-COVID boom".
- "A year ago" means the same month last year. "Three months ago" means the thread three months back, not an average. Say "the three months through September" if you mean an average.
- Superlatives ("highest since", "lowest on record", "first time") need a check against the full series from April 2011, and the check goes in the ledger (section 4). "On record" means since April 2011 in this data. Say "since we started counting in 2011" the first time.

### Hedge once, where the doubt lives

A claim that clears the noise bar in section 4 is stated flat. No "may", "appears to" or "seems". A claim that is close to the bar, or rests on a classifier with a weak validation score, gets one hedge, in one sentence, with the reason:

> Junior posts slipped from 9% to 6% in the past year, a gap small enough that ordinary month-to-month noise could produce it.

Not: "This could potentially suggest that junior hiring may be somewhat weakening." Stacked qualifiers tell the reader we don't know what we think. One hedge with a reason tells them exactly how much to trust the number.

The "what this data can't tell us" paragraph (section 2) is about the source's limits. It doesn't count as the hedge, and it's no excuse to hedge the findings again.

### Person

- "We" is the column. Use it for what we did and what we think: "we count top-level posts", "we read this as a top-down recovery". The byline is "Software Engineering Job Report", so there is no "I".
- "You" is allowed when the sentence is about the reader's own situation ("if you're looking for a first job"). At most twice per article. No "you might be wondering".
- Opinion comes through the claim and the verbs, not through "we believe" or "in our view". Use "we think" once at most, for the column's main judgment.

## 2. Article anatomy

Total length: 600 to 1,100 words of prose, not counting directives. A quiet month can run short. Don't pad.

| Part | Length | Job |
|---|---|---|
| Headline | 6 to 12 words, at most 70 characters | A claim someone could disagree with. |
| Dek | One sentence, at most 30 words | The evidence for the headline, with one or two numbers. |
| Lede | 1 to 3 sentences, at most 60 words | Why this month is worth reading. Scene or tension, not a statistics dump. |
| Nut graf | 60 to 110 words | The argument in plain terms, and the numbers that carry it. |
| Compare strip | One `::compare` | The data turn: here are the numbers. |
| Sections | 3 to 5, each 90 to 200 words | Each leads with a finding and has one chart. |
| What this data can't tell us | 60 to 130 words | The source's limits, as they apply to this month's argument. |
| Kicker | 1 to 3 sentences, at most 50 words | Takes the argument one step further. Never a summary. |

### Headline

A claim, not a label. It should be checkable against the data and narrow enough to be wrong.

- Good: "HN's hiring thread is growing again, but not for beginners"
- Good: "Remote work is losing, but not where you'd think"
- Bad (a label): "October 2026 job market report"
- Bad (a question): "Is the tech hiring freeze over?"
- Bad (hype): "The AI hiring boom is here"

Sentence case, no period, no em dash, no colon-subtitle ("AI hiring: what it means").

### Dek

The standfirst under the headline. It gives the reader the one or two numbers that justify the headline. "October's thread had the most hiring posts since July 2024, but only 6% were aimed at junior engineers, down from 17% five years ago."

### Lede

Open on the tension, not on the method. Don't start with "Every month, we analyze..." or with a number the reader has no context for. A contrast between two readers, a surprise, or a flat statement of what changed all work. The lede can be argued. It can't be unsupported: whatever it asserts, a section backs up.

### Nut graf

The paragraph that tells the reader what the whole article argues and why they should keep reading. Here you state the one argument in a sentence a friend would repeat. If you can't write that sentence, the article isn't ready. The nut graf carries the two or three numbers that matter most and sets up the compare strip.

### The data turn

Right after the nut graf comes the `::compare` strip: current month against 3 months, 1 year and 5 years ago for the measures the argument uses (three to five metrics). It is the "here's the data" moment. Don't restate every cell of it in prose. The prose picks the cells that matter.

### Sections

Each section is:

1. An `##` heading that states the finding, in sentence case. "AI companies now write more than a third of the posts", not "AI share".
2. The finding in the first sentence, with its number.
3. Context: the comparison windows, what the reference months were like, the strongest other reading.
4. One `::chart` directive that backs the heading. Place it after the prose, as the evidence for what was just said.

Order sections by importance to the argument, not by the order in the spec. Sections the argument doesn't need are left out. They live on the dashboard. Three strong sections beat five thin ones.

One section, usually the second or third, takes the strongest objection to the argument head-on. In op-ed terms it's the "to be sure" paragraph. Name the counter-reading specifically, give it its best numbers, then say why the argument survives or how far it has to retreat. If it doesn't survive, change the argument. FiveThirtyEight's editors called this letting the data change the story.

### What this data can't tell us

A fixed `##` heading, every month, just before the kicker. Pick the two to four limits from section 4 that bear on *this* month's argument and say them plainly, in prose, not as a bullet list. Close any gap the argument invites but the data can't fill: "We don't split seniority by AI status, so we can't say whether the AI companies are the ones skipping juniors." This paragraph builds trust. Write it like you mean it, not like a disclaimer.

### Kicker

The last line is the one people quote. It turns the argument forward: what to watch next month, what the finding means for someone deciding something, or an image that sticks. It doesn't summarize. It doesn't end on "only time will tell" or "the future remains uncertain". It must still be true to the data: a kicker can interpret, but it can't introduce a number or a causal claim the article didn't earn.

### The comparison convention

Every headline measure is placed against three reference points, in this order:

| Window | Directive value | What it tells the reader | Watch out for |
|---|---|---|---|
| 3 months ago | `3m` | Short-term direction. | Seasonality. Check the same three-month stretch in earlier years before calling it a trend. |
| 1 year ago | `1y` | The cleanest comparison: same month, so seasonal effects mostly cancel. | Lead with this one when only one comparison fits. |
| 5 years ago | `5y` | Where the market sits in the long cycle. | From 2026, five years back lands in the 2021 boom. Name the base month's context so the drop isn't read as a collapse. |

Skip a window, and say why in the chart note or a clause, when:

- the metric has no value for that month (`series` omits it);
- the reference month's `n` is under 50 posts;
- the reference month was distorted by a known event and the comparison would mislead (for example, March and April 2020 as a "normal" baseline).

The `::compare` strip uses `against="3m,1y,5y"` by default. Don't drop a window from the strip because it hurts the argument. That's the window the "to be sure" paragraph has to handle.

## 3. Charts

Every claim in a section heading has a chart. Every chart supports a claim in the text. A chart nobody refers to is cut. Each chart asks the reader for effort, so it has to pay that back.

### Directive attributes

`docs/architecture.md` defines `type`, `metric`, `breakdown`, `from`, `annotate`, `title` and `note`, plus `metrics` and `against` on `::compare`. This guide also uses the attributes below. They are not yet in the architecture contract, and the renderer ticket should adopt them there or replace them.

| Attribute | Used by | Format |
|---|---|---|
| `annotate` | `line`, `stacked-area`, `small-multiples` | One or more `YYYY-MM:label` entries separated by `\|` |
| `to` | time-series types | `YYYY-MM`; defaults to the article month |
| `months` | `slope` | Two months, `"2021-10,2026-10"` |
| `against` | `dot` | One window (`1y`) or a month (`2021-10`) |
| `categories` | `small-multiples`, `slope`, `dot`, `bar` | Comma-separated subset of a breakdown's categories |

### Title states the finding

The `title` attribute is a sentence that says what the chart shows, like a headline. Ten to 15 words, sentence case, no period.

- Good: `title="AI-native companies went from 8% of posts to 38% in five years"`
- Bad: `title="AI-native share of hiring posts, 2019-2026"` (that's a subtitle)
- Bad: `title="AI is taking over startup hiring"` (that's not what the chart measures)

The title must be true of the chart as drawn. If the line is flat for the last six months, the title can't say "still climbing".

### Subtitle states the measure

The subtitle names the measure, the population and the period: "Share of 'Who is hiring?' posts from AI-native companies, expected value, January 2019 to October 2026." The renderer builds it from the metric's `label`, `description` and `unit` in `metrics.json` plus the chart's date range, so the writer doesn't type it. The writer checks that it reads correctly. If it doesn't, fix the label in the export, not in the article.

### Notes

`note` is for what a reader needs to read this chart correctly, in one or two sentences:

- that a share is a Jev expected value ("Shares are expected values from a model's reading of each post");
- a skipped or unusual month;
- a definition the subtitle can't hold, quoted from the classifier's question text rather than paraphrased from memory.

Don't repeat the methodology footer in every note. Don't put an argument in a note.

### Annotating events

Annotations mark real-world events so readers can line them up against the data. They don't claim the event caused the change (section 4). Rules:

- Two annotations per chart at most. Pick the events relevant to this chart's claim.
- Labels are four words or fewer, in sentence case: `2022-11:ChatGPT launches`.
- Annotate the month the event happened. The "Who is hiring?" thread goes up on the first weekday of the month, so an event late in month M first shows in the thread for month M+1. Don't write as if the thread reacted the same month.
- Use the standard list below. An event not on the list needs a source in the ledger and a line added here in the same change.

| Month | Label | Event |
|---|---|---|
| 2020-03 | COVID shutdowns | WHO declares a pandemic (March 11); US shutdowns begin |
| 2021-01 | Colorado pay law | Colorado's pay-range disclosure law takes effect (salary charts only) |
| 2022-01 | Sec. 174 change | R&D costs must be amortized, not expensed, from tax year 2022 |
| 2022-03 | First rate hike | Federal Reserve starts raising rates (March 16) |
| 2022-11 | ChatGPT launches | ChatGPT public release (November 30) |
| 2022-11 | NYC pay law | New York City pay-range law takes effect (November 1; salary charts only) |
| 2023-01 | Big Tech layoffs | Amazon, Microsoft and Google cut about 40,000 jobs between them |
| 2023-01 | California pay law | California and Washington pay-range laws take effect (salary charts only) |
| 2023-03 | SVB collapses | Silicon Valley Bank fails (March 10) |
| 2024-09 | First rate cut | Federal Reserve starts cutting (September 18) |
| 2025-07 | Sec. 174 restored | Domestic R&D expensing restored (signed July 4) |
| 2025-09 | H-1B fee | $100,000 fee on new H-1B petitions announced (September 19; visa charts only) |

The 2022 rate hikes were a series of increases. Annotate the first one, and don't label it "rate hikes" as if it were a single date.

### Choosing the chart type

Pick the type from the shape of the claim.

| The claim is about | Type | Example |
|---|---|---|
| One measure moving over time | `line` | "Hiring posts are a third of the 2021 peak" |
| Parts of a whole shifting over time (categories that sum to 1) | `stacked-area` | "Hybrid has taken share from remote since 2022" (`work_mode`, `seniority`, `funding_stage`) |
| Several categories, each with its own trend | `small-multiples` | "Rust and Go rose while Ruby faded" (`stack`, `industry`) |
| The same categories at two dates | `slope` | "Senior roles grew as junior roles shrank, 2021 to 2026" |
| Many categories, now vs one past point, ranked | `dot` | "AI/ML gained the most share of any industry this year" |
| Values for categories at one month, or yearly totals | `bar` | "Fintech and devtools wrote the most hiring posts this month" |
| Headline measures against 3m/1y/5y | `::compare` | The data turn after the nut graf |

Rules that follow from the data:

- `stack` shares don't sum to 1 (a post can mention many terms). Never draw them as `stacked-area`. Use `small-multiples` or `dot`.
- `industry` has 11 categories. Don't stack all of them. Use `small-multiples`, `dot`, or `categories=` to show the four or five the claim is about.
- Bars start at zero. Lines can start above zero, but the renderer's y-axis rules decide that, not the writer.
- Pick `from` to fit the claim, not to exaggerate it. A "lowest since" claim shows enough history to see the earlier low. A short-term claim can start in 2019, which keeps COVID and the 2021 peak in view. Starting a line in mid-2022 to make a drop look steeper is not allowed.
- One chart per section. If a section needs two charts, it's two findings, so it's two sections.

## 4. Honesty rules for this data

These apply to every sentence. The fact-checker enforces them.

### What a post is

- **Posts aren't jobs.** One "Who is hiring?" post can list one role or 20. Write "hiring posts" or "companies posting". Never write "jobs", "openings" or "roles" for a post count. Roles can be named inside a share ("posts aimed at senior engineers").
- **Seeking posts aren't job seekers.** "Who wants to be hired?" posts are people who chose to post on Hacker News, not the unemployed. Write "people posting in 'Who wants to be hired?'" on first mention, then "job seekers posting".
- **Hacker News isn't the job market.** The threads skew toward venture-backed startups, engineering roles and the Bay Area. Say "on Hacker News", "in the thread" or "among startups posting on HN". Never "tech hiring rose" or "the job market recovered". When you want to say something wider, say that HN agrees or disagrees with a named outside measure, and keep it out of the numbers ledger.
- **The snapshot is seven days.** Every month counts posts in the first seven days of its thread. Late posts don't count, past or present. Don't compare our counts to someone else's thread totals.
- **Survivorship.** Deleted posts are missing and edited posts show their latest text. Older months lose more posts to deletion, so early-year counts are a floor.

### Classified shares are estimates

- Jev-based shares (`ai_native_share`, `new_grad_share`, `work_mode`, `seniority`, `industry`, `funding_stage`, `seeker_mood`) are expected values: the sum of the model's probabilities divided by the number of posts. Say "by our classifier's estimate" or similar once per article, the first time one appears.
- They carry two kinds of error: the model can be wrong about a post, and a month of about 300 posts is a small sample. Both mean small moves are noise.
- Regex and count metrics (`posts`, `salary_*`, `remote_token_share`, `visa_share`) are exact counts of what the text says. They still face the sampling point, and regex can miss unusual formats.

### The noise bar

Until `metrics.json` carries intervals, use these rules of thumb. They cover sampling error only, so they're a floor, and classifier error sits on top.

For the change in a share between two months, each with about 300 posts, treat moves smaller than this as noise:

| Share near | Noise bar (points) |
|---|---|
| 5% | 3.5 |
| 10% | 5 |
| 20% | 6.5 |
| 30% to 50% | 7.5 to 8 |

Scale by the square root of 300 divided by the month's `n`: multiply by 1.4 for months of about 150 posts, by 0.55 for about 1,000. The bar comes from 1.96 × √(2p(1 − p)/n).

For counts and medians:

- A change in `posts` under 10% is "about flat" for 3m and 1y comparisons.
- A change in a salary median under 5% is noise. The medians rest only on the posts that disclose pay, so `n` is smaller than the post count. Check `n`.
- Ratios like `seekers_per_post` inherit the noise of both counts. Moves under 0.2 are flat.

Below the bar: say the measure was about the same, or leave it out. Don't build a section on it. Near the bar: state it with the one hedge. Above it: state it flat.

### Words of size

Match the verb to the move.

| Move | Verbs |
|---|---|
| Below the noise bar | was about the same, held steady, roughly flat |
| Above the bar | rose, fell, grew, shrank, slipped, climbed |
| Largest move in at least 12 months | jumped, dropped, surged, sank, and say "the largest in X months" |
| Record or multi-year extreme | Only with a ledger check: "lowest since March 2013", "highest since we started counting in 2011" |

"Plunged", "soared", "collapsed", "skyrocketed" and "exploded" are reserved for moves of a third or more, and still need the check.

### No causal claims

The data shows when things moved, not why. Annotated events are context.

- Banned with a measure as the subject or object: "caused", "drove", "led to", "fueled", "triggered", "because of", "due to", "thanks to", "as a result of", "killed", "sparked".
- Allowed: "after", "since", "coincided with", "began rising a few months after", "followed".
- When a cause is the natural question, name it as a question the data can't answer, in the "can't tell us" paragraph. You can say which explanation fits the timing better. You can't say it's proven.

### Every number is checkable

- Every number in the prose, headline, dek, chart titles and notes comes from `site/data/metrics.json` for a named key and month, or is computed from those values with the rounding rules in section 1.
- Derived numbers (percent changes, point differences, "a third of", "third straight month") get a ledger line showing the inputs.
- Outside facts (event dates, laws, company layoffs) come only from the event table in section 3 or carry a source in the ledger.
- No numbers from memory, other articles or other datasets in the prose. If you want to compare HN with an outside source, say so in words and cite it in the ledger.
- Name the measure precisely. `ai_native_share` is "posts from companies whose product is built on AI". It isn't "AI jobs" and it isn't "posts mentioning AI". `remote_token_share` is "posts with REMOTE in the header line", which differs from `work_mode` remote. Pick one per article and stick to it.
- Don't compare a metric before its series starts. Churn measures (`new_company_share`) need history to mean anything, so the first months of 2011 call every company new. Don't use 2011 values of churn metrics.

### The numbers ledger

At the end of the article file, after the kicker, add an HTML comment listing every number in the text with its source. Browsers don't display HTML comments, so readers never see it. The fact-checker works from it.

```markdown
<!-- ledger
342 hiring posts            posts.hiring 2026-10 = 342
up 16% from a year ago      posts.hiring 2025-10 = 296; 342/296 = 1.155
highest since July 2024     posts.hiring max(2024-08..2026-09) = 331; 2024-07 = 351
ChatGPT launches            event table, 2022-11
-->
```

## 5. Banned phrases and AI tells

The column is written by an agent, which makes this list more important, not less. Readers have learned the tells. One "delve" and they stop trusting the numbers. This list folds in the `humanizer` skill (based on Wikipedia's "Signs of AI writing") and adds the clichés of business and economics journalism.

### Words and phrases

Never use:

- **AI vocabulary:** delve, tapestry, testament, landscape (for anything but land), realm, intricate, interplay, pivotal, crucial, vital, key (as an adjective), robust, seamless, multifaceted, nuanced, underscore, highlight (as a verb), showcase, foster, garner, bolster, navigate (except maps), unlock, elevate, leverage (as a verb), embark, journey, ever-evolving, game-changer, paradigm shift.
- **Openers and fillers:** "In today's fast-paced world", "in today's [anything] landscape", "In the ever-changing world of", "It's worth noting that", "It is important to note", "Interestingly", "Notably", "Importantly", "Let's dive in", "Let's take a closer look", "Here's the thing", "So, what does this mean?", "At its core", "At the end of the day", "When it comes to".
- **Significance inflation:** "marks a turning point", "a pivotal moment", "represents a shift", "sets the stage for", "a sign of the times", "speaks volumes", "the writing on the wall", "reflects broader trends", "signals a new era".
- **Market clichés:** "headwinds", "tailwinds", "perfect storm", "new normal", "bloodbath", "the great reset", "tech winter", "thaw", "green shoots", "a tale of two markets", "the elephant in the room", "cautious optimism", "mixed bag", "only time will tell", "remains to be seen", "the jury is still out".
- **Vague attribution:** "experts say", "many believe", "observers note", "some argue", "industry reports suggest". If a source matters, name it and cite it.
- **Chatbot residue:** "I hope this helps", "Certainly", "Great question", "Here is", "As of my last update", "based on available information", "Let me know".
- **Generic endings:** "the future looks bright", "exciting times ahead", "one thing is clear", "In conclusion", "In summary", "Ultimately".

### Constructions

- **Negative parallelism.** No "It's not just X, it's Y", "not only X but Y", "This isn't about X. It's about Y." State Y.
- **Rule of three.** Don't group things in threes for rhythm. If there are two reasons, give two. Lists of three are fine when there really are three items, like the three comparison windows.
- **Trailing -ing analysis.** No sentences that end in ", highlighting...", ", underscoring...", ", reflecting...", ", signaling...". If the implication matters, give it its own sentence with a subject.
- **Synonym cycling.** Pick one name for a thing and keep it. "Hiring posts" stays "hiring posts", not "listings", then "ads", then "openings".
- **False ranges.** No "from X to Y" unless X and Y are two ends of a real scale ("from 8% to 38%" is fine).
- **Rhetorical questions** as transitions or headlines. Ask a question only when the next sentence answers it with data.
- **Copula dodging.** "Is" over "serves as", "stands as", "boasts", "features".
- **Stacked hedges.** "Could potentially suggest", "may possibly indicate". One hedge, with a reason (section 1).

### Typography

- **Em dashes:** none in headlines, deks, chart titles or section headings. At most two in the body. Commas, colons, parentheses and periods do the same work.
- Straight quotes ("), not curly.
- No bold or italics for emphasis in the prose. Italics are for publication names only.
- No emojis, no exclamation marks.
- Headings in sentence case.
- No bullet lists in the article body. The column is prose. The ledger and front matter are the only lists.

### Soul is required too

Clean but voiceless is its own tell. A month of flat numbers read out in order sounds like a template. Have a view about what the month means. Vary sentence length. Make one comparison a reader will remember ("the thread is a third the size it was in 2021"). Let the "to be sure" paragraph actually concede something. If you'd be bored reading it aloud, rewrite it.

## 6. Worked example

**This is an example. The month is hypothetical and every number is invented.** The same article is saved as `site/articles/_style-example.md` for renderer testing. It sits at the short end of the length target, with three sections, so it shows the anatomy without padding.

### The article

```markdown
---
month: 2026-10
headline: "HN's hiring thread is growing again, but not for beginners"
dek: "October's thread had the most hiring posts since July 2024, but only 6% were aimed at junior engineers, down from 17% five years ago."
byline: "Software Engineering Job Report"
---

More companies posted in Hacker News' October hiring thread than in any month since July 2024. If you're a senior engineer, that's good news. If you're looking for your first job, you'd barely notice.

The thread drew 342 hiring posts, up 16% from a year ago. The growth came at the top. Posts for senior and staff-level engineers made up 57% of the thread, up from 47% a year ago. Posts aimed at junior engineers were 6% of the thread, against 17% in October 2021. Hiring on HN is recovering from the top down, and so far the bottom hasn't been invited.

::compare{metrics="posts.hiring,seekers_per_post.hiring,ai_native_share.hiring,new_grad_share.hiring" against="3m,1y,5y"}

## Demand is climbing out of last year's hole

October's 342 posts were up 11% from 309 in July. It was the fourth straight month above 300. Job seekers got a little breathing room too: there were 2.4 people posting in "Who wants to be hired?" for every hiring post, down from 2.9 a year ago. In October 2021 the ratio was 0.6, and companies outnumbered the people looking.

Five years ago, in October 2021, 1,018 companies posted. That was the height of the post-COVID boom, so the 66% drop since then says as much about 2021 as about today. The thread is still a third the size it was.

::chart{type="line" metric="posts.hiring" from="2019-01" title="Hiring posts are up from last year's low but a third of the 2021 peak" annotate="2022-03:First rate hike|2023-01:Big Tech layoffs"}

## AI companies now write more than a third of the posts

By our classifier's estimate, 38% of October's posts came from companies whose product is built on AI. A year ago the figure was 29%. In October 2021 it was 8%.

The line starts bending upward in early 2023, a few months after ChatGPT's public release, and it has risen in 10 of the last 12 months. The obvious next thought is that these companies are the ones skipping juniors. Maybe. Our numbers can't say, and we come back to that below.

::chart{type="line" metric="ai_native_share.hiring" from="2019-01" title="AI-native companies went from 8% of posts to 38% in five years" annotate="2022-11:ChatGPT launches" note="Shares are expected values from a model's reading of each post."}

## The entry-level share has fallen by about two-thirds since 2021

In October 2021, 17% of hiring posts were aimed at junior engineers. This October it was 6%. Posts open to new grads fell from 27% to 11% over the same five years. A drop that size is far outside anything sampling noise can produce.

The best objection is that companies stopped labeling roles rather than stopped hiring juniors. If posts had dropped the word "junior" and left the level out, the share with no stated level would have grown. It was 13% in both Octobers.

The past year is less clear. Junior posts slipped from 9% to 6%, a gap small enough that ordinary month-to-month noise could produce it. The direction matches the five-year trend. The size of this year's step is the part to hold loosely.

::chart{type="slope" breakdown="seniority" months="2021-10,2026-10" title="Senior roles grew as junior roles shrank" note="Shares are expected values from a model's reading of each post."}

## What this data can't tell us

Hacker News is not the job market. Its hiring thread leans toward venture-backed startups and the Bay Area, and one post can advertise one role or 20, so a rise in posts means more companies willing to post, not more jobs. The seniority and AI shares come from a model reading each post. They're estimates, which is why we treat small moves as noise. Deleted posts are missing and edited posts show their latest text, which matters more for 2021 than for this month. And we don't split seniority by AI status, so we can't tell whether the AI companies are the ones passing on juniors. They're the obvious suspect. This data can't convict them.

Companies are hiring again. They'd just prefer that someone else did the training.

<!-- ledger
...
-->
```

### The humanizer pass

The first draft was run through the `humanizer` checklist. What it caught, and the fix:

| First draft | Pattern | Fix |
|---|---|---|
| "For a senior engineer, that is the best news this column has had to report in two years." | Unverifiable claim; the column didn't exist two years ago | "If you're a senior engineer, that's good news." |
| "That is a real rise, not a wobble." | Negative parallelism | Cut. "Third straight month above 300" makes the point with a number. |
| "Keep the long view in mind." | Filler imperative | Cut. The paragraph opens on the 2021 number instead. |
| "No other category we track has moved this far this fast." | Unchecked superlative | Replaced with "it has risen in 10 of the last 12 months", which goes in the ledger. |
| "...a few months after ChatGPT's launch, underscoring how quickly the market adapted." | Trailing -ing analysis, causal hint | Cut the clause. The chart annotation carries the timing. |
| "It's a squeeze that is real, significant and accelerating." | Rule of three, and "accelerating" isn't shown | "A drop that size is far outside anything sampling noise can produce." |
| "The one-year move may possibly be noise and could suggest a slowdown." | Stacked hedges | One hedge with the reason: "a gap small enough that ordinary month-to-month noise could produce it." |
| "The question for next year is whether anyone is still investing in tomorrow's engineers." | Generic forward-looking ending | "Companies are hiring again. They'd just prefer that someone else did the training." |

The draft headline, "Startups are hiring again, but the entry-level door keeps narrowing", also broke a section 4 rule: it speaks for startups in general, when the data covers startups posting on HN. The published headline names the thread.

Checked and kept: the lede's two "If you're..." sentences are a deliberate contrast and use the second person twice, the article's limit. The article has no em dashes, one hedge, and no causal verbs. "The bottom hasn't been invited" and the kicker are interpretation, and the article supports them with the seniority numbers.

### The ledger for the example

```markdown
<!-- ledger (example, invented values)
most since July 2024            posts.hiring max(2024-08..2026-09) = 331; 2024-07 = 351
342 hiring posts                posts.hiring 2026-10 = 342
up 16% from a year ago          posts.hiring 2025-10 = 296; 342/296 = 1.155
57% senior and staff            seniority 2026-10 senior 0.45 + staff_plus 0.12
47% a year ago                  seniority 2025-10 senior 0.38 + staff_plus 0.09
6% junior                       seniority 2026-10 junior 0.06
17% in October 2021             seniority 2021-10 junior 0.17
309 in July                     posts.hiring 2026-07 = 309
fourth straight month above 300 posts.hiring 2026-07 = 309, 2026-08 = 318, 2026-09 = 327, 2026-10 = 342; 2026-06 = 288
up 11% from July                342/309 = 1.107
2.4 vs 2.9                      seekers_per_post.hiring 2026-10 = 2.4, 2025-10 = 2.9
ratio 0.6 in October 2021       seekers_per_post.hiring 2021-10 = 0.6
1,018 in October 2021           posts.hiring 2021-10 = 1018
66% drop                        342/1018 = 0.336
a third the size                0.336
38%, 29%, 8%                    ai_native_share.hiring 2026-10 = 0.38, 2025-10 = 0.29, 2021-10 = 0.08
risen in 10 of last 12 months   ai_native_share.hiring month-over-month, 2025-11..2026-10
ChatGPT public release          event table, 2022-11
27% to 11% new grads            new_grad_share.hiring 2021-10 = 0.27, 2026-10 = 0.11
about two-thirds                (17 - 6)/17 = 0.65
13% in both Octobers            seniority unspecified 2021-10 = 0.13, 2026-10 = 0.13
9% to 6% is noise               seniority junior 2025-10 = 0.09 (n = 296), 2026-10 = 0.06 (n = 342); bar near 7.5% is about 4 points; gap is 3
AI 9-point rise clears bar      bar near 33% is about 7.5 points
senior 10-point rise clears bar bar near 50% is about 8 points
-->
```

The "fourth straight month" line shows why the ledger exists. The first draft said "third straight month", counting August through October and forgetting that July (309) was also above 300. Writing the ledger line against the series caught it. A writer working from memory wouldn't have.

## 7. Fact-check checklist

The reviewing agent works through this list before an article is published. Any failure goes back to the writer with the line, the rule and the fix. The reviewer reads the article and `metrics.json` fresh. It doesn't take the writer's word for anything.

**Numbers**

- [ ] Every number in the headline, dek, prose, chart titles and notes has a ledger line.
- [ ] Each ledger line names a `metrics.json` key and month, and the value matches the file for the current `generated_at`.
- [ ] Derived numbers recompute from the ledger inputs: percent changes from unrounded values, point differences from the printed shares.
- [ ] Rounding follows the table in section 1. Shares are whole percent, dollars to the nearest $1,000, ratios and scores to one decimal.
- [ ] Every superlative ("highest since", "first time", "on record", "straight months") is checked against the full series, not just the compare windows.
- [ ] "A year ago", "three months ago" and "five years ago" point at the right months.
- [ ] Outside facts come from the event table or have a cited source in the ledger.

**Claims**

- [ ] The headline is a claim, and the sections support it.
- [ ] Every move described as a change clears the noise bar for its `n`. Moves below it are called flat or left out.
- [ ] Verbs of size match the table in section 4.
- [ ] At most one hedge per claim, with a reason. No stacked qualifiers.
- [ ] No causal verbs with a measure. Annotated events are described as timing.
- [ ] No "jobs" or "openings" for post counts. HN is never called "the job market" or "tech hiring".
- [ ] Jev-based shares are flagged as estimates at first mention.
- [ ] Each measure is named consistently and matches what the metric actually counts.
- [ ] The "to be sure" section names a real counter-reading and the article answers it.
- [ ] The "what this data can't tell us" paragraph covers the limits this month's argument leans on.
- [ ] The kicker adds no new number and no causal claim.

**Comparisons**

- [ ] The `::compare` strip includes 3m, 1y and 5y unless a window is skipped for a stated reason.
- [ ] Unusual base months (2020 shutdowns, the 2021 peak) are named as such where they are used.
- [ ] Salary comparisons across more than a year say "not adjusted for inflation" once.

**Charts**

- [ ] Every finding section has exactly one chart, and every chart backs its section's heading.
- [ ] Each `title` states a finding that is true of the chart as drawn.
- [ ] The chart type fits the claim (section 3). `stack` is never stacked-area.
- [ ] `from` doesn't crop history to exaggerate a move.
- [ ] At most two annotations per chart, each from the event table, four words or fewer.
- [ ] Every directive uses metric and breakdown ids that exist in `metrics.json`.

**Style**

- [ ] Headline 6 to 12 words, at most 70 characters. Dek one sentence, at most 30 words.
- [ ] Total prose 600 to 1,100 words. 3 to 5 sections.
- [ ] Nothing from the banned list in section 5. Search the file for each banned word.
- [ ] Em dashes: none in headline, dek, titles or headings; two at most in the body.
- [ ] AP number style: one through nine spelled out, no sentence starts with a numeral, % with numerals, "percentage points" for share differences.
- [ ] American spelling throughout.
- [ ] Front matter matches `docs/architecture.md`: `month`, `headline`, `dek`, `byline`.
- [ ] Read it aloud once. If a sentence sounds like a template, flag it.

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
