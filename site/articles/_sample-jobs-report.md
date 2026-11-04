---
month: 2026-10
headline: "Software job postings rose this year, but employment slipped"
dek: "Indeed's index of US software job postings rose 23% in a year, while the BLS counted 2% fewer people working at computer systems design firms."
byline: "Software Engineering Job Report"
---

Ads for software work are coming back. Indeed's index of US software development job postings rose 23% over the year to early October. The government's counts of people employed and hired have not followed. Employment at computer systems design firms was 2% lower in September than a year earlier, by the Bureau of Labor Statistics' count.

So far the rise is in ads. Payroll counts moved the other way. Indeed's index reached 78.3 in the week to October 2, up from 63.6 a year earlier, and it rose in 10 of the last 12 months. Over roughly the same year, BLS counted about 55,000 fewer people working at computer systems design firms, and the information sector reported fewer job openings. On Hacker News, people posting that they want work grew much faster than the companies posting that they are hiring.

::compare{title="Postings rose on Indeed while BLS employment and openings fell" metrics="external:indeed_software_postings.US,external:jolts_openings_information.US,external:ces_computer_systems_design.US,posts.hiring,seekers_per_post.hiring,seekers_per_post_us.hiring,salary_disclosed_share.hiring" against="3m,1y,5y"}

## Software job postings on Indeed rose for most of the year

Indeed's index of US software development postings stood at 78.3 in the week to October 2, where February 2020 equals 100. A year earlier it was 63.6, so the index rose 23%. It went up in 10 of the 12 months since then.

The longer view is less bright. In October 2021, during the pandemic-era hiring boom, the index was 178.0, and the latest reading is 56% below it. The index peaked at 231.6 in March 2022. Today's level is about a third of that.

To be sure, the BLS count of job openings points the other way. Employers in the information sector reported 128,000 open jobs in August, against 169,000 in August 2025. The two sources count different things. Indeed counts ads for software development work at employers in every industry. JOLTS counts every opening, software or not, at publishers, broadcasters, telecom carriers and data processors. JOLTS is also not seasonally adjusted and swings a lot from month to month. Averaged over its last 12 readings, information-sector openings were 105,000, against 164,000 a year earlier. Indeed's rise held for most of the year, but it is a rise in ads for software work, and the industry count of openings has not confirmed it.

::chart{type="line" external="indeed_software_postings.US" from="2021-06" title="Indeed's US software postings rose 23% in a year but are a third of their 2022 peak"}

## Employment at computer systems design firms slipped

The BLS counted 2.36 million people working at computer systems design firms in September, 2% fewer than the 2.41 million of September 2025. Five years ago, in September 2021, the count was 2.28 million, so the industry is still 3% larger than it was during the boom.

Hiring in the information sector was also lower. Averaged over 12 readings, JOLTS counted 78,000 hires a month in the information sector, 7% fewer than the 83,000 of a year earlier.

::chart{type="line" external="ces_computer_systems_design.US" from="2019-01" title="Employment at computer systems design firms is below its 2024 level" note="Values as first published. BLS's yearly benchmark revision shows as a step in early-year months, including February 2025."}

## On Hacker News, job seekers per hiring post doubled

Employer posts in Hacker News's monthly hiring thread held about steady: 289 in October, against 351 a year earlier, a gap within ordinary swings for a thread this size. People posting in "Who wants to be hired?" rose 70%, to 685. That left 2.4 job seekers for every hiring post, up from 1.2.

Most of that rise came from people outside the US. Counting only US job seekers against hiring posts open to US workers, the ratio went from 0.7 to 1.0, a change within ordinary swings. The thread leans toward startups, so it is a narrow view, but on it the job seekers' side did the moving while Indeed's postings rose.

::chart{type="line" metric="seekers_per_post.hiring" from="2014-05" title="Job seekers per hiring post on Hacker News doubled in a year, to 2.4" annotate="2020-03:COVID shutdowns;2023-01:Big Tech layoffs"}

## More software job ads state pay, on Indeed and on Hacker News

Forty-nine percent of Indeed's US software postings stated pay in August, up 10 percentage points from 39% in August 2025. Hacker News agrees on direction. Thirty-one percent of October's hiring posts gave a yearly salary, against 22% a year earlier, a gap just past ordinary swings.

The two sources measure the same thing in different places. Indeed's share covers ads across the whole US market, and the Hacker News share covers startup posts written in free text.

::chart{type="line" external="indeed_software_pay_transparency.US" title="Indeed's share of software postings that state pay rose 10 points in a year"}

## What this data can't tell us

None of these sources counts software engineers directly. Indeed counts ads, not hires. The BLS series count industries, not occupations, so they include jobs that aren't software work and miss software engineers employed in other industries. They also run behind: September is the newest employment month here and August the newest for openings and hires. The employment figures are as first published, and BLS revises them. Hacker News posts aren't jobs, and the people who post there are not a sample of anyone in particular. Nor can any of these numbers say why ads rose while employment fell.

For now the recovery is in the ads. The BLS counts run one to two months behind, so they are the ones to watch next.

<!-- ledger
rounding: shares to whole %, point gaps from printed shares, % change from unrounded values, ratios one decimal, outside thousands as whole numbers or millions to two decimals
metrics.json generated_at 2026-11-04T12:07:47Z; outside values are as published by each HN month's as-of date; ref periods named below
SAMPLE: layout test for the multi-source framing; not published
headline/dek postings rose 23%    external indeed_software_postings.US 2026-10 = 78.33 (ref 2026-10-02), 2025-10 = 63.57 (ref 2025-10-03); 78.33/63.57 = 1.232; no bar for outside series
headline/dek employment slipped 2% external ces_computer_systems_design.US HN 2026-10 = 2355.4 (ref 2026-09); HN 2025-12 = 2410.6 (ref 2025-09, same reference month a year earlier); 2355.4/2410.6 = 0.977
lede over the year to early October  ref 2025-10-03 to 2026-10-02
2% lower in September             same CES line
78.3 week to October 2            indeed 2026-10 = 78.33, ref 2026-10-02 (7-day trailing average)
63.6 a year earlier               indeed 2025-10 = 63.57
rose in 10 of last 12 months      indeed HN months 2025-10..2026-10: up 10, down 2 (2026-05 72.15 < 72.44; 2026-07 72.51 < 72.57)
about 55,000 fewer                2410.6 - 2355.4 = 55.2 thousand (ref 2025-09 vs 2026-09)
information sector fewer openings external jolts_openings_information.US 2026-10 = 128 (ref 2026-08), 2025-10 = 169 (ref 2025-08)
job seekers grew faster than hiring posts  posts.seeking 404 -> 685 (+70%, ln 0.528 vs bar 1y 0.299, outside); posts.hiring 351 -> 289 (ln -0.194 vs bar 1y 0.338, inside)
compare strip                     external rows: no bar, plain change; ref periods printed by the renderer
February 2020 = 100               indeed_software_postings.US description
178.0 in October 2021             indeed 2021-10 = 177.99 (ref 2021-10-01)
56% below                         78.33/177.99 = 0.440
pandemic-era hiring boom          base-month context, style guide section 2
peaked at 231.6 in March 2022     indeed max over 2021-06..2026-10 = 231.57 at HN month 2022-03 (ref 2022-03-04)
about a third                     78.33/231.57 = 0.338
128,000 in August                 jolts_openings_information.US 2026-10 = 128 (ref 2026-08)
169,000 in August 2025            jolts_openings_information.US 2025-10 = 169 (ref 2025-08)
not seasonally adjusted           external seasonally_adjusted = false (JTU series)
12-reading average 105,000        trailing 12 HN months 2025-11..2026-10 mean = 105.08 (refs 2025-08..2026-08; some repeat)
164,000 a year earlier            trailing 12 HN months 2024-11..2025-10 mean = 163.92
chart title rose 23%              see headline line
chart title a third of 2022 peak  78.33/231.57 = 0.338
information sector examples     NAICS 51 definition, BLS Industries at a Glance https://www.bls.gov/iag/tgs/iag51.htm
chart from 2021-06                first Indeed value (point-in-time start), architecture.md
2.36 million in September         CES 2026-10 = 2355.4 (ref 2026-09)
2.41 million September 2025       CES HN 2025-12 = 2410.6 (ref 2025-09); the strip's 1y cell compares HN 2025-10 = 2415.4 (ref 2025-08), also -2% (0.975); prose uses the same-month pair
2.28 million September 2021       CES HN 2021-10 = 2278.2 (ref 2021-09)
3% larger                         2355.4/2278.2 = 1.034
78,000 hires a month, 12 readings jolts_hires_information.US trailing 12 HN months to 2026-10 = 77.58
7% fewer than 83,000              trailing 12 to 2025-10 = 83.08; 77.58/83.08 = 0.934
chart title below 2024 level      CES HN months 2024-01..2024-12 min 2531.5, max 2554.5; 2026-10 = 2355.4
chart note February 2025 step     CES HN 2025-01 = 2545.4 (ref 2024-12) -> 2025-02 = 2457.9 (ref 2025-01), BLS annual benchmark
289 vs 351, within swings         posts.hiring 2026-10 = 289, 2025-10 = 351; ln -0.194 vs bar 1y 0.338; inside
rose 70% to 685                   posts.seeking 2025-10 = 404, 2026-10 = 685; 1.696; ln 0.528 vs bar 1y 0.299; outside
2.4 vs 1.2                        seekers_per_post.hiring 2026-10 = 2.3702, 2025-10 = 1.1510; ln 0.722 vs bar 1y 0.308; outside
most of rise outside the US       US seekers = posts.seeking * seeker_us_share.seeking: 685*0.3213 = 220.1 vs 404*0.4708 = 190.2; +30 of +281
US-only 0.7 to 1.0, in swings     seekers_per_post_us.hiring 2025-10 = 0.7343, 2026-10 = 1.0363; ln 0.344 vs bar 1y 0.358; inside
chart title doubled, 2.4          2.3702/1.1510 = 2.06
annotations                       event table 2020-03, 2023-01
49% stated pay in August          indeed_software_pay_transparency.US 2026-10 = 0.4912 (ref 2026-08)
39% in August 2025                indeed_software_pay_transparency.US 2025-10 = 0.3914 (ref 2025-08)
10 percentage points              49 - 39
31% vs 22%, just past swings      salary_disclosed_share.hiring 2026-10 = 0.3133 (n 233), 2025-10 = 0.2166 (n 314); printed gap 9; unrounded 0.0967 vs bar 1y 0.095; just outside (hedged)
chart title 10 points in a year   0.4912 - 0.3914 = 0.0998; printed 49 - 39
September newest employment month CES 2026-10 ref 2026-09
August newest openings and hires  JOLTS 2026-10 ref 2026-08
one to two months behind          CES lag ~1 month, JOLTS ~2 months (sources section, architecture.md)
-->
