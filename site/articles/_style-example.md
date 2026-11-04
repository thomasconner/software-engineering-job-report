---
month: 2026-10
headline: "HN's hiring thread is growing again, but not for beginners"
dek: "October's thread had the most hiring posts since July 2024, but only 6% were aimed at junior engineers, down from 17% five years ago."
byline: "Software Engineering Job Report"
---

<!-- STYLE EXAMPLE: hypothetical month, every number is invented. See docs/style-guide.md section 6. -->

*Example article from the style guide. Every number in it is invented.*

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
