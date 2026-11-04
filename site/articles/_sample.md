---
month: 2026-10
headline: "Software hiring has drifted down for three years while job seekers keep coming"
dek: "Sample issue on mock data. On Hacker News, employer posts have drifted down for three years while the line of people looking keeps getting longer."
byline: "Software Engineering Jobs Report"
---

This is a sample issue. The numbers come from synthetic data and the prose is placeholder copy, written to show how an article reads with every chart type in place. Fewer companies posted in October's "Who is hiring?" thread than a year earlier, and people looking for work outnumbered them about two to one.

::compare{title="October's thread against three earlier points" metrics="posts.hiring,seekers_per_post.hiring,new_grad_share.hiring,ai_native_share.hiring,salary_disclosed_share.hiring" against="3m,1y,5y"}

## Demand has not come back

The hiring thread peaked in early 2022, when more than a thousand companies posted in the first week. Within a year it had lost almost half of them, and it has drifted lower since.

::chart{type="line" metric="posts.hiring" from="2019-01" annotate="2022-03:First rate hike;2023-01:Big Tech layoffs" title="Hiring posts are less than a third of the early 2022 peak"}

## The last two years have been flat, not falling

Month to month the count is noisy. December and summer threads run light, so two years of columns show the range better than a line.

::chart{type="bar" metric="posts.hiring" title="Hiring posts have stayed between about 290 and 400 a month for two years"}

## More people per opening

Divide one thread by the other and you get a rough measure of competition: about two job seekers for every company post, up from under one during the 2021 boom.

::chart{type="line" metric="seekers_per_post.hiring" from="2019-01" annotate="2023-01:Big Tech layoffs" title="Job seekers now outnumber hiring posts two to one"}

## Remote is shrinking slowly

Remote peaked in 2021. Hybrid has taken some of that share, and onsite has made a steady comeback.

::chart{type="stacked-area" breakdown="work_mode" from="2018-01" annotate="2020-03:COVID shutdowns" title="Onsite is creeping back as remote gives up ground" note="Shares are expected values from a model's reading of each post."}

## The seniority mix has moved up a rung

Senior and staff posts took the share that junior posts lost.

::chart{type="slope" breakdown="seniority" months="2021-10,2026-10" highlight="senior,junior" title="Senior posts gained 13 points as junior posts lost 11" note="Shares are expected values from a model's reading of each post."}

## Seed-stage companies grew the most

::chart{type="dot" breakdown="funding_stage" vs="5y" title="Seed-stage companies grew their share more than any other stage" note="Shares are expected values from a model's reading of each post."}

## AI companies are the biggest group

::chart{type="bar" breakdown="industry" title="AI and ML companies write about a third of hiring posts" note="Shares are expected values from a model's reading of each post."}

## Stack terms move slowly, then all at once

Ruby faded over a decade. LLM went from zero to about a third of posts in three years.

::chart{type="small-multiples" breakdown="stack" categories="llm,agents,python,typescript,rust,go,ruby,javascript" highlight="llm,agents" from="2016-01" annotate="2022-11:ChatGPT launches" title="LLM went from nowhere to a third of posts in three years"}
