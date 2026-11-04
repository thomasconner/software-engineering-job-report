# Adjudication log

Reference set: `reference.jsonl` = core sample (220 posts, `source` agreed/adjudicated) + mood oversample (45 posts, `source: oversample_mood`).

Core: 220 posts, two independent annotators (A, B) on `rubric.md`. 21 posts disagreed on at least one field (24 fields). Two more fields on posts where A and B agreed were overridden by the Cisco ruling below, so 22 posts are `adjudicated` and 198 are `agreed`. Fields where A and B agreed were kept as-is except for that ruling.

## Rulings

1. **Parent company / big-name employers (Cisco subsidiaries, Oracle).** The rubric bans outside knowledge of company size. "Part of Cisco" states ownership, not size. Knowing that Cisco or Oracle is large comes from outside the text. Ruling: `funding_stage = unknown` unless the text itself claims size or public listing. This applies to ThousandEyes 30518193 and Cisco Meraki 33821202, where both annotators said `public_or_large` and the ruling overrides them, and to Oracle 30881314, where they split. It matches the agreed labels on Juniper 6691668 and Yelp 3301129 (both `unknown`). By contrast, Chemspeed 29407703 calls itself a "market leader with a global footprint", and Fold 48008420 says it is "publicly listed": those are text claims and stay `public_or_large`.
2. **Non-job posts.** `exclude: true` on 6310592 (plugs a recruiting utility) and 35777100 (rejection complaint), both in the hiring thread, and on 12629759 (a The Trade Desk hiring post in the seeking thread). They stay in the file with their labels but are not scored.
3. **Seniority ties.** When one role states a level and another of equal count states none (e.g. "Software Engineer" + "Senior Software Engineer"), the stated level wins. `unspecified` is for posts that state no level. Applies to 16529790, 17668186, 42577286.
4. **"Lead … Engineer" titles** count as `eng_leadership = 1` and senior. This follows the labels A and B agreed on for StackShare 11815947, CIONIC 41436557 and Smarkets 42019783. Applies to 15826175, 43552825.
5. **Industry for vertical software:** use the vertical when a category fits (drug-discovery data, so health; this matches the agreed Layer = fintech). Use `other` when no category fits (automotive software, so other; this matches Hire an Esquire). AI-powered horizontal B2B products go under their domain (`enterprise_saas` / `devtools_infra`), and the AI part is recorded only in `ai_native`. That matches the agreed DataFox and Cleric labels. Betting exchanges are gambling, so `other`, not fintech.

## Disputed fields

| post_id | field | A | B | final | reason |
|---|---|---|---|---|---|
| 6310592 | industry | other | unstated | unstated | No employer; plugs a free recruiting utility. Post is excluded anyway. |
| 6476915 | industry | fintech | other | other | Betting exchange is gambling, not financial services. Same call as Smarkets 42019783. |
| 6827968 | industry | commerce | unstated | unstated | Text only says "a decision algorithm" platform used by big UK companies. Retail/gifting comes from the company name. |
| 14689623 | seniority | senior | mid | mid | Only one eng role: plain "Software Engineer", stated as "mid-to-senior+". Mid is the stated floor. |
| 15826175 | seniority | senior | unspecified | senior | Only role is the Lead Software Engineer link. Lead titles read as senior, same as CIONIC 41436557. |
| 15826175 | eng_leadership | 1 | 0 | 1 | "Lead Software Engineer" counts as a team lead, same as the agreed StackShare/CIONIC/Smarkets labels. |
| 16529790 | seniority | unspecified | senior | senior | 1 senior vs 1 unleveled role. Tie rule: a stated level beats unleveled roles. |
| 16529790 | industry | enterprise_saas | media_consumer | enterprise_saas | Productivity and team-collaboration apps sold as software; Twist is explicitly for teams. |
| 16736919 | industry | enterprise_saas | other | other | Vertical software (automotive) with no matching category. Vertical-domain convention, as with Hire an Esquire. |
| 17668186 | seniority | unspecified | senior | senior | SE vs Senior SE tie. Tie rule: a stated level beats unleveled roles. |
| 23042978 | funding_stage | unknown | venture_unspecified | venture_unspecified | "Two recent rounds" states outside funding rounds with no letter. Same as agreed Kentik "VC backed". |
| 29407703 | funding_stage | unknown | public_or_large | public_or_large | Self-described "market leader with a global footprint", 20+ years old: the text itself claims size. |
| 30167592 | industry | devtools_infra | enterprise_saas | enterprise_saas | Session replay/analytics that finds where end users get stuck: product analytics, not developer tooling. |
| 30518193 | funding_stage | public_or_large | public_or_large | unknown | Cisco ruling: "part of cisco" states ownership, not size. Cisco being large is outside knowledge. |
| 30881314 | funding_stage | unknown | public_or_large | unknown | Cisco/name ruling: Oracle size known only from outside knowledge; text gives no size or ownership claim. |
| 31238048 | industry | climate_energy | hardware_robotics | hardware_robotics | Builds ocean sensor hardware (Spotter, Smart Mooring) and sells data. Same as agreed Saildrone 44759839. |
| 33441288 | industry | ai_ml | enterprise_saas | enterprise_saas | Sells GTM insights to businesses; AI is captured by ai_native=1. Same as agreed DataFox. |
| 33821202 | work_mode | hybrid | remote | remote | "Hybrid/Remote" makes remote an option ("onsite or remote, your choice" = remote). |
| 33821202 | funding_stage | public_or_large | public_or_large | unknown | Cisco ruling: knowing Cisco is large is outside knowledge. Text makes no size claim. |
| 37742498 | work_mode | hybrid | remote | hybrid | "Expect travel for regular on-site, in-person work in SLC" is a stated recurring in-office cadence. |
| 40230432 | industry | enterprise_saas | health | health | Data platform for pharma/biotech drug discovery. Vertical domain wins, as with agreed Layer=fintech. |
| 42019783 | industry | fintech | other | other | Betting exchange is gambling, not fintech. Same call as Smarkets 6476915. |
| 42577286 | seniority | unspecified | senior | senior | SE vs Senior SE tie. Tie rule: a stated level beats unleveled roles. |
| 43552825 | ai_native | 1 | 0 | 1 | "Building products ... from the ground up using AI" with LLMs in the stack: the post describes the product as built on AI. |
| 43552825 | eng_leadership | 1 | 0 | 1 | "Lead Product Engineer": Lead titles count, as in the agreed StackShare/CIONIC/Smarkets labels. |
| 48804251 | industry | enterprise_saas | ai_ml | enterprise_saas | Automates packaging-compliance review for brands; AI is captured by ai_native=1. Same as Windfall/DataFox. |

## Mood oversample (`reference_mood.jsonl`)

In the core sample, 58 of 60 random seeking posts were neutral (2), so the core set can't validate `seeker_mood`. To cover the other levels, in-snapshot seeking posts were pulled from `src.duckdb` with a keyword regex for text that talks about the search itself:

```
(?i)(laid off|layoff|let go\b|months? (of )?(searching|looking|job ?hunting)|(searching|looking) for (\w+ )?months|struggl|any job|anything at all|desperate|multiple offers|several offers|happily employed|currently employed and|casually looking|not actively looking|passively looking|open to anything|hard to find|tough market|rough market|no luck|unemployed for|been searching|been looking for)
```

Core-sample posts were excluded, and each author was kept once (their lowest `hash(post_id)` post) because a few people repost the same text every month. The first 15 per era by `hash(post_id)` were then taken from the de-duplicated pools (2015–19: 43, 2020–22: 57, 2023–26: 138). Each post was read and labeled by hand; no script or model set any label.

**These posts were selected by keyword, so they validate the scale's levels, not the base rate.** Don't use them to estimate how often seekers are discouraged or upbeat. Many hits are false positives ("Remote: open to anything", "laid off" stated as a plain fact), and those are labeled 2 as the rubric says.

Distribution (n=45): 0 = 3, 1 = 4, 2 = 31, 3 = 7, 4 = 0.
By era: 2015–19 {0:2, 2:8, 3:5}; 2020–22 {1:3, 2:11, 3:1}; 2023–26 {0:1, 1:1, 2:12, 3:1}.

Level 4 (upbeat) has no examples. About 29 in-snapshot seeking posts match "multiple/several/competing offers | in demand | very selective | only considering", and none came up in the random draw. A targeted pull is needed if level 4 must be validated.
