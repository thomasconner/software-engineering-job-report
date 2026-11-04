---
month: 2026-10
headline: "Software job ads rose, but computer systems design employment slipped"
dek: "Indeed's index of US software job postings rose 22% in a year, while the BLS counted 1% fewer people working at computer systems design firms."
byline: "Software Engineering Jobs Report"
ribbon: "external:indeed_software_postings.US"
---

Ads for software work rose this year. Indeed's index of US software development job postings rose 22% over the year to early October. Employment at computer systems design firms went the other way. The Bureau of Labor Statistics counted 1% fewer people working there in September than a year earlier.

So far the rise is in ads. Indeed's index reached 78.3 in the week to October 2, up from 64.3 a year earlier, and it rose in 10 of the 12 monthly readings since October 2025. Over the year to September, the BLS counted about 32,000 fewer people at computer systems design firms, and employers in the information sector reported 9% fewer job openings in August than a year earlier. On Hacker News, employer posts in the monthly hiring thread held about steady, within ordinary swings for a thread this size.

::compare{title="Postings rose on Indeed while BLS employment and openings fell" metrics="external:indeed_software_postings.US,external:jolts_openings_information.US,external:ces_computer_systems_design.US,posts.hiring,seekers_per_post.hiring,seekers_per_post_us.hiring,salary_disclosed_share.hiring" against="3m,1y,5y"}

## Software job postings on Indeed rose for most of the year

Indeed's index of US software development postings stood at 78.3 in the week to October 2, where February 2020 equals 100. In the same release, the index was 64.3 a year earlier, so it rose 22%. It went up in 10 of the 12 monthly readings since then.

The longer view is less bright. In October 2021, during the pandemic-era hiring boom, the index was 179.4, and the latest reading is 56% below it. As first published, the index peaked at 231.6 in March 2022. Today's level is about a third of that.

To be sure, the BLS count of job openings points the other way. Employers in the information sector reported 128,000 open jobs in August, against 141,000 in August 2025 in the same release, 9% fewer. The two sources count different things. Indeed counts ads for software development work at employers in every industry. JOLTS counts every opening, software or not, at publishers, broadcasters, telecom carriers and data processors. JOLTS is also not seasonally adjusted, which is why this comparison sets August against August. Indeed's rise held for most of the year, but it is a rise in ads for software work, and the industry count of openings has not confirmed it.

::chart{type="line" external="indeed_software_postings.US" from="2021-06" title="Indeed's US software postings rose 22% in a year but are a third of their 2022 peak"}

## Employment at computer systems design firms slipped

The BLS counted 2.36 million people working at computer systems design firms in September, 1% fewer than the 2.39 million it now estimates for September 2025. Five years ago, in September 2021, the count was 2.35 million, about the same as today.

Our chart strings together each month's first estimate, so it shows a larger fall since 2024 than that. Part of it is a step in early 2025, when the BLS revised the whole series. Compared within one release, the past year's drop is about 32,000 people.

::chart{type="line" external="ces_computer_systems_design.US" from="2019-01" title="Employment at computer systems design firms is below its 2024 level" note="Values as first published. BLS's yearly benchmark revision shows as a step in early-year months, including February 2025."}

## On Hacker News, job seekers per hiring post doubled

Employer posts in Hacker News's monthly hiring thread held about steady: 289 in October, against 351 a year earlier, a gap within ordinary swings for a thread this size. People posting in "Who wants to be hired?" rose 70%, to 685. That left 2.4 job seekers for every hiring post, up from 1.2.

Most of that rise came from people outside the US. Counting only US job seekers against hiring posts open to US workers, the ratio went from 0.7 to 1.0, a change within ordinary swings. The thread leans toward startups, so it is a narrow view, and on it the job seekers' side did the moving.

::chart{type="line" metric="seekers_per_post.hiring" from="2014-05" title="Job seekers per hiring post on Hacker News doubled in a year, to 2.4" annotate="2020-03:COVID shutdowns;2023-01:Big Tech layoffs"}

## More software job ads state pay, on Indeed and on Hacker News

Forty-nine percent of Indeed's US software postings stated pay in August, up 9 percentage points from 40% in August 2025 in the same release. Hacker News agrees on direction. Thirty-one percent of October's hiring posts gave a yearly salary, against 22% a year earlier, a gap just past ordinary swings.

The two sources measure the same thing in different places. Indeed's share is taken across Indeed's US postings, and the Hacker News share covers startup posts written in free text.

::chart{type="line" external="indeed_software_pay_transparency.US" title="Indeed's share of software postings that state pay rose 9 points in a year"}

## What this data can't tell us

None of these sources counts software engineers directly. Indeed counts ads, not hires. The BLS series count industries, not occupations, so they include jobs that aren't software work and miss software engineers employed in other industries. They also run behind: September is the newest employment month here and August the newest for openings. The BLS revises its figures, which is why every change here compares two numbers from the same release. Hacker News posts aren't jobs, and the people who post there are not a sample of anyone in particular. Nor can any of these numbers say why ads rose while employment fell.

For now the recovery is in the ads. The BLS counts run one to two months behind, so they are the ones to watch next.

<!-- ledger
rounding: shares to whole %, point gaps from printed shares, % change from unrounded values, ratios one decimal, outside thousands as whole numbers or millions to two decimals
metrics.json generated_at 2026-11-04T12:07:47Z; outside values as published by each HN month's as-of date
outside changes: issue value against its same-release `compare` reading (data/external, metrics.json external series[].compare); ref periods named
SAMPLE: layout test for the multi-source framing; not published
headline/dek postings rose 22%    external indeed_software_postings.US 2026-10 = 78.33 (ref 2026-10-02, release 2026-10-06); compare.1y = 64.3 (ref 2025-10-02); 78.33/64.3 = 1.218; no bar
headline/dek employment 1% fewer  external ces_computer_systems_design.US 2026-10 = 2355.4 (ref 2026-09, vintage 2026-10-09); compare.1y = 2387.6 (ref 2025-09); 2355.4/2387.6 = 0.9865
lede over the year to early October  ref 2025-10-02 to 2026-10-02, same release
78.3 week to October 2            indeed 2026-10 = 78.33, ref 2026-10-02 (7-day trailing average)
64.3 a year earlier               indeed compare.1y = 64.3 (ref 2025-10-02)
10 of the 12 monthly readings     indeed issue values (as first published) 2025-10..2026-10: up 10, down 2 (2026-05 72.15 < 72.44; 2026-07 72.51 < 72.57); no large revisions in this series
about 32,000 fewer                2387.6 - 2355.4 = 32.2 thousand, same release
information sector 9% fewer       external jolts_openings_information.US 2026-10 = 128 (ref 2026-08); compare.1y = 141 (ref 2025-08); 128/141 = 0.908
hiring posts held about steady    posts.hiring 2026-10 = 289, 2025-10 = 351; ln -0.194 vs bar 1y 0.338; inside
compare strip                     external rows: same-release compare, no bar; JOLTS 3m cell "seasonal" (May vs August, unadjusted)
February 2020 = 100               indeed_software_postings.US description
179.4 in October 2021             indeed compare.5y = 179.4 (ref 2021-10-02), same release
56% below                         78.33/179.4 = 0.437
pandemic-era hiring boom          base-month context, style guide section 2
peaked 231.6 March 2022, first published  indeed issue values max over 2021-06..2026-10 = 231.57 at HN month 2022-03 (ref 2022-03-04)
about a third                     78.33/231.57 = 0.338 (level against a first-published peak; stated as such)
128,000 in August                 jolts_openings_information.US 2026-10 = 128 (ref 2026-08)
141,000 in August 2025            compare.1y = 141 (ref 2025-08), same release
not seasonally adjusted           external seasonally_adjusted = false (JTU series)
information sector examples       NAICS 51 definition, BLS Industries at a Glance https://www.bls.gov/iag/tgs/iag51.htm
chart title rose 22%              same as headline line; chart end label uses compare.1y
chart title a third of 2022 peak  78.33/231.57 = 0.338
chart from 2021-06                first Indeed value (point-in-time start), architecture.md
2.36 million in September         CES 2026-10 = 2355.4 (ref 2026-09)
2.39 million for September 2025   CES compare.1y = 2387.6 (ref 2025-09), same release
2.35 million September 2021       CES compare.5y = 2348.9 (ref 2021-09); 2355.4/2348.9 = 1.003, about the same
larger fall as first published    CES issue values: 2024-10 = 2554.5 (max), 2026-10 = 2355.4
step in early 2025                CES HN 2025-01 = 2545.4 (ref 2024-12) -> 2025-02 = 2457.9 (ref 2025-01), BLS annual benchmark
chart title below 2024 level      CES HN months 2024-01..2024-12 min 2531.5, max 2554.5; 2026-10 = 2355.4 (as drawn, first published)
289 vs 351, within swings         posts.hiring 2026-10 = 289, 2025-10 = 351; ln -0.194 vs bar 1y 0.338; inside
rose 70% to 685                   posts.seeking 2025-10 = 404, 2026-10 = 685; 1.696; ln 0.528 vs bar 1y 0.299; outside
2.4 vs 1.2                        seekers_per_post.hiring 2026-10 = 2.3702, 2025-10 = 1.1510; ln 0.722 vs bar 1y 0.308; outside
most of rise outside the US       US seekers = posts.seeking * seeker_us_share.seeking: 685*0.3213 = 220.1 vs 404*0.4708 = 190.2; +30 of +281
US-only 0.7 to 1.0, in swings     seekers_per_post_us.hiring 2025-10 = 0.7343, 2026-10 = 1.0363; ln 0.344 vs bar 1y 0.358; inside
chart title doubled, 2.4          2.3702/1.1510 = 2.06
annotations                       event table 2020-03, 2023-01
49% stated pay in August          indeed_software_pay_transparency.US 2026-10 = 0.4912 (ref 2026-08)
40% in August 2025                compare.1y = 0.4047 (ref 2025-08), same release
9 percentage points               49 - 40
31% vs 22%, just past swings      salary_disclosed_share.hiring 2026-10 = 0.3133 (n 233), 2025-10 = 0.2166 (n 314); printed gap 9; unrounded 0.0967 vs bar 1y 0.095; just outside (hedged)
chart title 9 points in a year    0.4912 - 0.4047 = 0.0865; printed 49 - 40
September newest employment month CES 2026-10 ref 2026-09
August newest for openings        JOLTS 2026-10 ref 2026-08
one to two months behind          CES lag ~1 month, JOLTS ~2 months (sources section, architecture.md)
-->
