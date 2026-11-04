# Jev questions

Every question Jev answers for the report. The source of truth is `src/sejr/classify/questions.py`. This page explains the wording.

## How a request is built

- **One request per post.** It carries every question for the post's thread kind ([speculative fan-out](https://docs.typesafe.ai/patterns/fan-out.md)). Jev reads the state once and answers all questions in parallel.
- **State is the post text and nothing else.** `posts.text` with trailing spaces and runs of blank lines collapsed. No post id, author, thread title, date or month goes in, so Jev can't place a post in time. Dates the author typed into the post stay, because they are part of what the post says.
- **Long posts are cut at 6,000 characters** (about 1,500 tokens), at a paragraph break when there is one, and end with `[post truncated]`. In a sample of about 940 posts from October 2026 the longest was 3.5k characters, so the cap only catches outliers. Jev gets less accurate as state grows with irrelevant text ([model jaggedness](https://docs.typesafe.ai/model-jaggedness.md)), and the facts asked about are near the top of a post. Cost isn't the reason: a whole hiring request costs about $0.0001.
- **No look-ahead.** The backfill runs in 2026 on posts going back to 2011, and Jev may know that a company later raised money, went public or pivoted to AI. Every hiring question ends with: *"Answer only from what the post itself says. Ignore anything you may know about the company from elsewhere, such as what it later became."*
- **Structured option descriptions.** Choice options are objects with `covers` and, where two options blur, `excludes`. This follows TypeSafe's [boundary-clarification rubric](https://docs.typesafe.ai/primitives/advanced.md). Jev also reads the option names, so they stay descriptive.
- **Model pinned** to `config.JEV_MODEL` (`jev-1.14.0`). The model id in each response is stored as `answers.version`, and the run fails if it differs from the pin.

## Hiring posts ("Who is hiring?")

### `work_mode` (Choice)

> Where can the engineering roles in this job post be done? If roles differ, answer for most of the engineering roles.

| Option | Covers |
|---|---|
| `remote` | Fully remote allowed, including remote within a country, region or time zone, and "office or remote, your choice". Excludes remote for only some days (hybrid). |
| `hybrid` | In an office part of the week, home the rest. Excludes fully remote teams with occasional offsites (remote). |
| `onsite` | Says onsite or no remote, or names an office location and does not offer remote. |
| `unclear` | No location and no arrangement, or the post contradicts itself. |

Why: in 2011–2015 most posts just gave a city and said nothing about remote. Back then that meant onsite, so a bare location counts as `onsite`. Otherwise early years would be mostly `unclear` and the trend would be meaningless. Literal REMOTE/ONSITE tokens are measured separately by regex (`remote_token_share`, `onsite_token_share`), so the two can be compared.

### `seniority` (Choice)

> What seniority level does this job post hire engineers at? If it hires at several levels, pick the most senior level it names.

| Option | Covers |
|---|---|
| `junior` | Interns, new grads, entry-level, junior, associate, up to about 2 years. |
| `mid` | Called mid-level or Engineer II, or about 2–5 years. |
| `senior` | Senior, lead, tech lead, or 5+ years. |
| `staff_plus` | Staff, principal, distinguished, architect, and engineering leadership (EM, head of engineering, director, VP, CTO). |
| `unspecified` | Titles with no level ("Software Engineer") and no years of experience. |

Why: multi-role posts need a single rule, and "most senior level named" is one Jev can apply literally. A post with no level signal goes to `unspecified` rather than being guessed as `mid`, so the share of posts that name a level is itself a measurement. Early-career openness is asked separately (`new_grad`), so a post hiring seniors *and* interns is still counted for the entry-level section.

### `industry` (Choice) + `industry_fits` (companion Noul)

> Which sector is the hiring company's main product or service in?

Options: `ai_ml`, `devtools_infra`, `fintech`, `health`, `climate_energy`, `security`, `commerce`, `media_consumer`, `enterprise_saas`, `hardware_robotics`. Each has a `covers` list of example businesses. `ai_ml` also says what it excludes: *an AI product built for one of the other sectors goes to that sector*. Without that, every AI-for-X startup would land in `ai_ml`. AI is measured separately by `ai_native`.

The Choice has no `other` option. TypeSafe's [companion Noul](https://docs.typesafe.ai/patterns/companion-noul.md) page explains why: an `other` option competes with the real sectors for probability. Instead a second question asks:

> Does the hiring company's main product or service belong to one of these sectors: …?

`true`: the post says what the company does and it clearly fits one. `false`: consulting, agency or staffing work, government, education, research, nonprofit, real estate, or the post does not say what the company does.

Code then folds the two into the `industry` row that the contract expects: `P(sector) = fits × P_choice(sector)` and `P(other) = 1 − fits`, with `label` set to the most likely of the 11. The raw Noul is also stored as `industry_fits`. The row's `confidence` is the Choice's own confidence in its sector pick, before folding. In the live check, a Rust consultancy, an education nonprofit and an online-assessment platform came back with `fits` ≤ 0.26 and so landed in `other`. The bare Choice had them at `devtools_infra` 0.99 and `enterprise_saas` 0.79–0.89.

### `funding_stage` (Choice)

> What funding stage or company size does the job post state? … A company's name alone is not evidence of its stage.

| Option | Covers |
|---|---|
| `bootstrapped` | Self-funded, no outside investors, profitable and independent. |
| `seed` | Pre-seed, seed, angel, or accelerator-backed (YC, Techstars) with no later round named. |
| `series_a` / `series_b` | That round named as the latest. |
| `series_c_plus` | Series C or later, late-stage private, pre-IPO. |
| `public_or_large` | Says it is publicly traded or describes itself as large (thousands of employees, Fortune 500, a division of a large company). |
| `unknown` | No stage, round, investors or size stated, or "VC-backed" with no round. |

Why: this is the question most exposed to look-ahead, because Jev knows which 2013 startups later went public. "Name alone is not evidence" makes a Google post with no size claim `unknown`, not `public_or_large`. That costs some recall but keeps every year measured the same way. `unknown` stays as an option rather than a companion Noul because "not stated" is a real answer here, not a failure of the list.

### `ai_native` (Noul)

> According to the job post, is the company's core product built on AI or machine learning?

`true`: the main product depends on AI/ML (a model, an AI assistant or agent, an ML platform, or a product whose core feature is vision, speech, recommendations or prediction). `false`: AI is absent, a side feature, an internal tool, or a role (one data scientist) rather than the product.

Why: "uses AI" would be true of nearly every 2025 post. The question is whether the product *is* AI, which is what `ai_native_share` charts.

### `new_grad` (Noul)

> Does the job post say it welcomes new grads, junior engineers, interns or other entry-level candidates?

`true`: invites new grads, juniors, interns, apprentices, bootcamp grads or entry-level engineers, or says no experience is needed. `false`: only experienced engineers, or no mention of early-career candidates.

Why: silence counts as no. The metric is "posts that say they are open to new grads", which is what the entry-level squeeze section needs.

## Seeking posts ("Who wants to be hired?")

### `seeker_mood` (Score, 0–4)

> How does this job seeker say their job search is going? Judge what they say about their situation, not how confidently they describe their skills.

| Level | Signals |
|---|---|
| 0 Discouraged | Search going badly or dragging on for months, many rejections, money worries or desperation, "any job at all". |
| 1 Strained | Mentions a layoff, gap or urgency, or offers concessions (lower pay, any role), without despair. |
| 2 Neutral | Location, skills, experience and the role they want, however confidently, with nothing about how the search is going. |
| 3 Positive | Something hopeful about their situation: chose to leave, looking forward to the next role, taking time to find the right fit. |
| 4 Upbeat | A strong position: employed and open only to exceptional offers, or openly excited and in demand. |

Why: most seeking posts follow the thread's template (Location / Remote / Willing to relocate / Technologies / Résumé / Email) plus a short pitch. A pitch is written to sound confident, so confidence alone is the baseline (level 2). The levels key on what the seeker says about their situation: layoffs, months of searching, being choosy. Those are the signals that move with the market.

The first wording ("a confident, warm introduction" as level 3) was tried live on 8 October 2026 posts. It scored ordinary pitches at 3.2–3.6 and almost never used level 2, so mood would have tracked salesmanship. The current wording fixes the anchor but has **not yet been run against the API**. Check it on the hand-labeled set before it reaches the report.
