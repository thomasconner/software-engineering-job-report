---
month: 2026-10
headline: "HN's hiring thread is growing again, but not for junior engineers"
dek: "October's thread had the most hiring posts since July 2024, but only 6% were for junior engineers, down from 17% five years ago."
byline: "Software Engineering Job Report"
---

<!-- STYLE EXAMPLE: hypothetical month, every number is invented. See docs/style-guide.md section 6. -->

*Example article from the style guide. Every number in it is invented.*

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
