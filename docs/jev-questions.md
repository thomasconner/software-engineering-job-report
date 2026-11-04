# Jev questions

Every question Jev answers for the report. The source of truth is `src/sejr/classify/questions.py`. This page explains the wording.

## How a request is built

- **One request per post.** It carries every question for the post's thread kind ([speculative fan-out](https://docs.typesafe.ai/patterns/fan-out.md)). Jev reads the state once and answers all questions in parallel.
- **State is the post text and nothing else.** `posts.text` with trailing spaces and runs of blank lines collapsed. No post id, author, thread title, date or month goes in, so Jev can't place a post in time. Dates the author typed into the post stay, because they are part of what the post says.
- **Long posts are cut at 6,000 characters** (about 1,500 tokens), at a paragraph break when there is one, and end with `[post truncated]`. In a sample of about 940 posts from October 2026 the longest was 3.5k characters, so the cap only catches outliers. Jev gets less accurate as state grows with irrelevant text ([model jaggedness](https://docs.typesafe.ai/model-jaggedness.md)), and the facts asked about are near the top of a post. Cost isn't the reason: a whole hiring request costs about $0.0001.
- **No look-ahead.** The backfill runs in 2026 on posts going back to 2011, and Jev may know that a company later raised money, went public or pivoted to AI. Every hiring question ends with: *"Answer only from what the post itself says. Ignore anything you may know about the company from elsewhere, such as what it later became."*
- **Structured option descriptions.** Choice options are objects with `covers` and, where two options blur, `excludes`. This follows TypeSafe's [boundary-clarification rubric](https://docs.typesafe.ai/primitives/advanced.md). Jev also reads the option names, so they stay descriptive.
- **Model pinned** to `config.JEV_MODEL` (`jev-1.14.0`). The model id in each response is stored as `answers.version`, and the run fails if it differs from the pin.
- **Question-set hash.** Each kind's questions plus the model pin hash to one value. It is stored with every answer in `data/answers/<model>/<YYYY-MM>.parquet`, so an edit to any question re-runs that kind's posts, and nothing else does.

## Validation and its limits

The definitions here were aligned with the reference rubric (`data/labels/rubric.md`) after a validation run on the reference set itself (`data/labels/reference.jsonl`). Six rules changed to match it: founding engineers, adtech, gambling, consumer fitness, mood levels 3 and 4, and the mid-level range. `ai_native` was also tightened for recommendation teams at consumer companies. Because the wording was tuned against the same posts that score it, the reference-set numbers in `site/data/validation.json` are optimistic. A held-out set is being labeled for an unbiased score.

## What gets stored

- **Answer rows.** One `answers` row per question per post, `method = 'jev'`, `version` = the model id from the response. Choice: `label`, `probabilities`, `confidence`. Score: `value` (expected score), `probabilities` keyed `"0"`–`"4"`, `confidence`. Noul: `value` only; Jev returns no confidence for a Noul.
- **Extra answers beyond the metric ids.** `industry_stated` and `industry_fits` (the companion Nouls behind the `industry` fold) and `eng_leadership` (feeds `eng_leadership_share`).
- **The industry fold assumes independence.** P(other) and P(unstated) multiply the two Nouls as if they were independent. `industry_fits` is asked unconditionally ("says what it does *and* fits a sector"), so the products are an approximation, not an exact decomposition.
- **One Jev version per post.** A run deletes every earlier Jev row of the posts it classifies, including questions that no longer exist.
- **Durable copy.** `data/answers/<model>/<YYYY-MM>.parquet` holds the `answers` columns plus `qset`, the question-set hash of the post's kind at the time it was answered. A post is skipped only when its stored `qset` equals the current one.
- **Fatal errors.** These stop the run and write nothing: `JevVersionMismatch` (the response model differs from the pin), `TypeSafeAuthenticationError` (401) and `TypeSafePermissionDeniedError` (403). Any other error is logged with the post id, the remaining posts are still written, and the run exits non-zero.

## Hiring posts ("Who is hiring?")

### `work_mode` (Choice)

> Where can the engineering roles in this job post be done? If roles differ, answer for most of the engineering roles.

| Option | Covers |
|---|---|
| `remote` | Fully remote allowed, including remote within a country, region or time zone, and "office or remote, your choice". Excludes remote only as an exception or on occasional days (onsite), and a set number of days a week (hybrid). |
| `hybrid` | The post says "hybrid", or states a recurring in-office schedule (for example two or three days a week). Excludes ad-hoc work from home with no schedule (onsite) and fully remote teams with offsites (remote). |
| `onsite` | Says onsite or no remote, names an office location without offering remote, or allows home working only occasionally or as an exception. |
| `unclear` | No location and no arrangement, or the post contradicts itself. |

Why: in 2011–2015 most posts just gave a city and said nothing about remote. Back then that meant onsite, so a bare location counts as `onsite`. Otherwise early years would be mostly `unclear` and the trend would be meaningless. "Flexible hours, work from home sometimes" was common in early posts. It isn't hybrid in today's sense, so `hybrid` needs the word itself or a stated weekly cadence. Literal REMOTE/ONSITE tokens are measured separately by regex (`remote_token_share`, `onsite_token_share`).

### `seniority` (Choice)

> What seniority level are most of the individual-contributor engineering roles in this job post? Ignore management roles. If levels are tied, pick the more senior one.

| Option | Covers |
|---|---|
| `junior` | Interns, new grads, entry-level, junior, associate, up to about 2 years. |
| `mid` | Called mid-level or Engineer II, or about 2–4 years. |
| `senior` | Senior, lead, tech lead, or 5+ years. A founding or first engineer with no stated level is `unspecified`. |
| `staff_plus` | Staff, principal, distinguished or architect engineers. Excludes managers, directors, VPs and CTOs. |
| `unspecified` | Titles with no level ("Software Engineer") and no years of experience, or "all levels". |

Why: the modal level, with the same "most of the roles" rule as `work_mode`, describes what a post is mostly hiring for. Management is measured separately (`eng_leadership`), so it doesn't push a post toward `staff_plus`. A founding engineer with no stated level is `unspecified`, as in the reference rubric; "founding" describes the team's stage, not the hire's level. Posts with no level signal go to `unspecified` rather than being guessed as `mid`, so the share of posts that name a level is itself a measurement. Early-career openness is asked separately (`new_grad`).

### `eng_leadership` (Noul)

> Does the job post hire engineering managers or engineering leads?

`true`: a role that leads engineers (engineering manager, team lead, tech lead, head of engineering, director or VP of engineering, CTO). `false`: only engineers with no lead or management role, or only non-engineering managers. Feeds `eng_leadership_share`.

### `industry` (Choice) + `industry_stated`, `industry_fits` (companion Nouls)

> Which sector is the hiring company's main product or service in?

The options are listed in this order: `enterprise_saas`, `commerce`, `fintech`, `health`, `media_consumer`, `devtools_infra`, `hardware_robotics`, `security`, `climate_energy`, `ai_ml`. Each has a `covers` list, and the sectors that blur have `excludes`:

- AI for one sector (radiology, fraud) goes to that sector, not `ai_ml`. AI is measured separately by `ai_native`.
- HR and recruiting *software*, and sales and marketing software, are `enterprise_saas`. Advertising technology, and staffing agencies that *place* candidates, are not listed sectors (they fold into `other`).
- Gambling, betting and betting exchanges are excluded from `fintech` and fold into `other`.
- `health` is healthcare, medical care and devices, biotech, pharma and health insurance. Consumer fitness and wellness products (Peloton) are `media_consumer`.
- Education products, consumer or not, real estate and proptech, and government are not listed sectors.

The order is deliberate. TypeSafe notes that Jev can lean toward the first Choice option ([model jaggedness](https://docs.typesafe.ai/model-jaggedness.md#choice-option-order)). `ai_ml` is the sector whose trend the report watches most, so it goes last, and a broad, stable sector goes first.

The Choice has no `other` option. TypeSafe's [companion Noul](https://docs.typesafe.ai/patterns/companion-noul.md) page recommends pairing a Choice with a Noul that asks whether any option fits, instead of adding `other`, which competes with the real options for probability. We use two Nouls:

- `industry_stated`: *Does the job post say what the hiring company makes or does?*
- `industry_fits`: *Does the post say what the hiring company does, and does its main product or service belong to one of `sectors`?* Its `sectors` field is the same `INDUSTRIES` mapping the Choice uses, so the two can't drift apart.

**The fold is our choice, not TypeSafe guidance.** TypeSafe describes reading the Noul first and ignoring the Choice when it's a clear no. We need a distribution over 12 categories for expected-count aggregation, so code combines the three answers:

- P(sector) = P(fits) × P(sector | Choice)
- P(other) = (1 − P(fits)) × P(stated)
- P(unstated) = (1 − P(fits)) × (1 − P(stated))

This treats the two Nouls as independent. `label` is the most likely of the 12. `confidence` is the Choice's own when a sector is the label, and NULL when the label is `other` or `unstated`. The raw Nouls are stored too, as `industry_stated` and `industry_fits`.

### `funding_stage` (Choice)

> What funding stage or company size does the job post state? … A company's name alone is not evidence of its stage.

| Option | Covers |
|---|---|
| `bootstrapped` | Self-funded, no outside investors, profitable and independent. |
| `seed` | The post names a pre-seed, seed or angel round. An accelerator tag alone ("YC W12") is not enough. |
| `series_a` / `series_b` | That round named as the latest. |
| `series_c_plus` | Series C or later, late-stage private, pre-IPO. |
| `public_or_large` | Says it is publicly traded or describes itself as large (thousands of employees, Fortune 500, a division of a large company). |
| `venture_unspecified` | Names investors or an amount raised, or says venture-backed, but names no round. |
| `unknown` | No stage, round, investors, amount or size. An accelerator batch tag alone counts here. |

Why: this is the question most exposed to look-ahead, because Jev knows which 2013 startups later went public. "Name alone is not evidence" makes a Twitter post with no size claim `unknown`. A YC batch tag says when a company went through the program, not what it has raised since. A 2012 "YC S11" company may be at Series B by then, so the tag alone is `unknown`, not `seed`. "Backed by Sequoia" is real information but names no stage, so it gets its own bucket instead of being forced into one.

### `ai_native` (Noul)

> Does the job post describe the company's product as built on AI or machine learning?

`true`: the post presents AI or ML as the core of the product (a model, an AI assistant or agent, an ML platform, or a product whose main feature is vision, speech or prediction). Recommendations or personalization count only when the post presents the product itself as AI-driven. `false`: no AI or ML, or AI for a side feature, an internal tool, or one data scientist, or hiring for an ML, research or data-science team at a company whose product the post doesn't present as AI, such as a large consumer company hiring for its recommendations team. "Data-driven", "analytics", "big data" and "automation" are not AI or ML on their own.

Why: "uses AI" would be true of nearly every 2025 post, and "data-driven" of every 2012 one. The question is whether the post presents the product *as* AI, which is what `ai_native_share` charts.

### `new_grad` (Noul)

> Does the job post say it welcomes new grads, junior engineers, interns or other entry-level candidates?

`true`: invites new grads, juniors, interns, apprentices, bootcamp grads or entry-level engineers, or says no experience is needed. `false`: only experienced engineers, or no mention of early-career candidates.

Why: silence counts as no. The metric is "posts that say they are open to new grads", which is what the entry-level squeeze section needs.

## Seeking posts ("Who wants to be hired?")

### `seeker_mood` (Score, 0–4)

> How does this job seeker say their job search is going? Judge what they say about the search, not how confidently they describe their skills. Facts about their circumstances, such as a career gap, a layoff, visa status or a move, are not mood on their own.

| Level | Signals |
|---|---|
| 0 Discouraged | Search going badly or dragging on for months, many rejections, money worries or desperation, "any job at all". |
| 1 Strained | Says the search is hard or urgent: needs work soon, struggling to land interviews, or offers concessions (lower pay, any role), without despair. |
| 2 Neutral | Location, skills, experience and the role they want, however confidently, with nothing about how the search is going. |
| 3 Positive | The search is going fine: employed and selective, casually looking, chose to leave, taking time to find the right fit. |
| 4 Upbeat | Clearly in demand: multiple offers, or very choosy because companies are competing for them. |

Why: most seeking posts follow the thread's template (Location / Remote / Willing to relocate / Technologies / Résumé / Email) plus a short pitch. A pitch is written to sound confident, so confidence alone is the baseline (level 2). A layoff or a gap is a fact about the person, not a mood about the market, and a 2016 career-gap line shouldn't read as distress. The levels key on what the seeker says about the search itself. The full probability vector is stored, so `seeker_strained_share` is the mean of P(0) + P(1).

History: the first wording ("a confident, warm introduction" as level 3) scored ordinary October 2026 pitches at 3.2–3.6. On the second live check (10 posts from 2016 and 2025, all plain template posts), the current wording put all ten at 2.0. That is the right answer for those posts, but none of them expressed any mood, so the sample can't show whether levels 0, 1, 3 and 4 trigger correctly. The hand-labeled set needs seeking posts that do express mood.
