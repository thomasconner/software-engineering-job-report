---
month: 2026-11
headline: "There are two job seekers for every company hiring, and the gap is still growing"
dek: "Sample issue on mock data. Hiring posts have fallen for three years while the line of people looking keeps getting longer, and the first rung of the ladder is the one that broke."
byline: "Software Engineering Job Report"
---

This is a sample issue. The numbers come from synthetic data, and the prose is placeholder copy that shows how an article reads with every chart type in place. Fewer companies posted in November's "Who is hiring?" thread than in any November we have measured, and the people looking for work outnumbered them roughly two to one.

::compare{metrics="posts.hiring,seekers_per_post.hiring,new_grad_share.hiring,salary_disclosed_share.hiring,ai_native_share.hiring,seeker_mood.seeking" against="3m,1y,5y"}

## Demand has not come back

The hiring thread peaked in early 2022, when more than a thousand companies posted in the first week. Within a year it had lost almost half of them, and it has drifted lower since. The decline is slow now, not a cliff, but it hasn't turned.

::chart{type="line" metric="posts.hiring" from="2019-01" annotate="2020-03:Pandemic lockdowns;2022-11:ChatGPT launches;2023-01:Layoff wave" title="Hiring posts are at their lowest in the series" note="Each month counts posts written in the first 7 days of the thread."}

Monthly counts are noisy. December and summer threads run light, so the columns below cover two years to make the seasonal dip easy to see.

::chart{type="bar" metric="posts.hiring" title="Hiring posts have stayed between about 280 and 400 a month for two years"}

## More people per opening

The other thread tells the other half. "Who wants to be hired?" has more than doubled since 2021. Divide one by the other and you get a rough measure of competition: about two job seekers for every company post, up from under one during the 2021 boom.

::chart{type="line" metric="seekers_per_post.hiring" from="2015-01" annotate="2021-09:Peak of the boom" title="Job seekers now outnumber hiring posts two to one"}

## Remote work is shrinking, slowly

Remote peaked in 2021. Hybrid has taken some of that share, and onsite has made a steady comeback. Note the scale: remote is still the most common arrangement, just a smaller majority than it was.

::chart{type="stacked-area" breakdown="work_mode" from="2018-01" annotate="2020-03:Pandemic lockdowns" title="Onsite is creeping back as remote gives up ground"}

The REMOTE and ONSITE tags in the header line tell the same story with a cruder ruler.

::chart{type="line" metric="remote_token_share.hiring,onsite_token_share.hiring" annotate="2020-03:Pandemic lockdowns" title="REMOTE overtook ONSITE in 2020 and still leads"}

## The entry level is where it hurts

The share of posts open to new graduates has fallen by more than half in five years. Senior and staff roles took the space.

::chart{type="slope" breakdown="seniority" against="5y" highlight="junior,senior" title="Senior roles gained what junior roles lost"}

## Who is hiring

AI companies are now the largest single group in the thread, according to Jev's reading of each post.

::chart{type="bar" breakdown="industry" title="AI and ML companies make up the largest group of posts"}

::chart{type="dot" breakdown="funding_stage" against="5y" title="Seed-stage companies grew their share the most" note="Unknown means the post does not say."}

::chart{type="stacked-area" breakdown="industry" from="2016-01" title="The AI wedge has grown since 2023"}

## What they want you to know

Stack terms move slowly, then all at once. Ruby faded over a decade; LLM went from zero to a third of posts in three years.

::chart{type="small-multiples" breakdown="stack" categories="python,typescript,javascript,react,go,rust,ruby,kubernetes,llm,agents,aws,java" from="2014-01" annotate="2022-11:ChatGPT" title="LLM went from nowhere to a third of posts in three years"}

## Pay is out in the open

Pay transparency laws in Colorado, California and Washington pushed salary ranges into the open. More than half of posts now state one.

::chart{type="line" metric="salary_min_median_usd.hiring,salary_max_median_usd.hiring" from="2016-01" title="Stated salary ranges have been flat for three years"}

## How job seekers feel

Mood in the "Who wants to be hired?" thread fell hard in 2023 and has only just stopped falling.

::chart{type="line" metric="seeker_mood.seeking" annotate="2020-03:Pandemic;2023-01:Layoff wave" title="Job seekers sound less hopeful than at any time before 2023"}
