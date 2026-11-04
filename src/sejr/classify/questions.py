"""Jev question definitions, keyed by thread kind and answer id.

Question ids match the metric ids in docs/architecture.md. docs/jev-questions.md explains
the wording. Any change here changes the request hash, so the affected posts re-run.
"""

from typesafe_sdk import Choice, Noul, NoulCriteria, Question, Score

# The backfill runs years after most posts were written. Jev may know how a company turned
# out (acquired, IPO, pivoted to AI), so every question pins it to the text in front of it.
TEXT_ONLY = (
    "Answer only from what the post itself says. Ignore anything you may know about "
    "the company from elsewhere, such as what it later became."
)

# Jev can lean toward the first option (docs: model-jaggedness). ai_ml is the sector whose
# trend the report watches most, so it sits last, and a broad, stable sector sits first.
INDUSTRIES = {
    "enterprise_saas": {
        "covers": "Business software for non-technical teams: CRM, HR and recruiting "
        "software, sales, marketing and adtech, collaboration, analytics, vertical SaaS "
        "(legal, construction).",
        "excludes": "Tools for developers (devtools_infra). Education products and "
        "staffing agencies that place candidates (neither is a listed sector).",
    },
    "commerce": {
        "covers": "Buying, selling and moving goods: e-commerce, retail, marketplaces "
        "for goods, logistics, delivery, supply chain, travel booking.",
        "excludes": "Real estate, property and rental platforms (not a listed sector).",
    },
    "fintech": {
        "covers": "Money: payments, banking, lending, insurance, trading, investing, "
        "accounting, crypto and blockchain.",
    },
    "health": {
        "covers": "Healthcare, medical devices, biotech, pharma, health insurance, "
        "mental health, fitness and wellness.",
    },
    "media_consumer": {
        "covers": "Products for consumers: social apps, games, media, news, music, "
        "video, dating, consumer subscriptions.",
        "excludes": "Education and learning products, even consumer ones (not a "
        "listed sector).",
    },
    "devtools_infra": {
        "covers": "Products for developers and IT teams: developer tools, cloud "
        "infrastructure, databases, data pipelines, DevOps, observability, APIs.",
        "excludes": "Business software for non-technical teams (enterprise_saas).",
    },
    "hardware_robotics": {
        "covers": "Physical products: robotics, drones, semiconductors, IoT, space, "
        "automotive, manufacturing, consumer electronics.",
    },
    "security": {
        "covers": "Cybersecurity, identity and access, privacy, threat detection, "
        "security compliance.",
    },
    "climate_energy": {
        "covers": "Energy, solar, batteries, grid, EV charging, carbon removal, "
        "climate and sustainability tech.",
    },
    "ai_ml": {
        "covers": "Sells AI itself: models, AI assistants or agents, ML platforms, "
        "computer vision or speech technology, with no other sector as its market.",
        "excludes": "An AI product built for one of the other sectors, such as AI for "
        "radiology (health) or AI for fraud (fintech). Pick that sector instead.",
    },
}

HIRING: dict[str, Question] = {
    "work_mode": Choice(
        instructions="Where can the engineering roles in this job post be done? If "
        "roles differ, answer for most of the engineering roles. " + TEXT_ONLY,
        criteria={
            "remote": {
                "covers": "Fully remote work is allowed, including remote within a "
                "country, region or time zone, and posts that offer office or remote "
                "at the candidate's choice.",
                "excludes": "Remote only as an exception or for occasional days "
                "(onsite), or for a set number of days a week (hybrid).",
            },
            "hybrid": {
                "covers": "The post says hybrid, or states a recurring in-office "
                "schedule such as two or three days a week in the office.",
                "excludes": "Occasional or ad-hoc work from home with no stated "
                "schedule (onsite). Fully remote teams that meet only for offsites "
                "(remote).",
            },
            "onsite": {
                "covers": "Work happens at an office or site: the post says onsite or "
                "no remote, names an office location without offering remote work, or "
                "allows working from home only occasionally or as an exception.",
            },
            "unclear": {
                "covers": "The post names no office location and no work arrangement, "
                "or contradicts itself.",
            },
        },
    ),
    "seniority": Choice(
        instructions="What seniority level are most of the individual-contributor "
        "engineering roles in this job post? Ignore management roles. If levels are "
        "tied, pick the more senior one. " + TEXT_ONLY,
        criteria={
            "junior": {
                "covers": "Interns, new grads, entry-level, junior or associate "
                "engineers, or up to about two years of experience.",
            },
            "mid": {
                "covers": "Roles called mid-level or Engineer II, or asking for about "
                "two to five years of experience.",
            },
            "senior": {
                "covers": "Senior, lead or tech lead engineers, founding or first "
                "engineers, or asking for five or more years of experience.",
            },
            "staff_plus": {
                "covers": "Staff, principal, distinguished or architect engineers.",
                "excludes": "Engineering managers, directors, VPs and CTOs; those are "
                "management roles and are ignored here.",
            },
            "unspecified": {
                "covers": "No level is given: titles without a level, such as "
                "'Software Engineer' or 'Backend Developer', and no years of "
                "experience; or the post says it hires at all levels.",
            },
        },
    ),
    "eng_leadership": Noul(
        instructions="Does the job post hire engineering managers or engineering "
        "leads? " + TEXT_ONLY,
        criteria=NoulCriteria(
            true="It hires for a role that leads engineers: engineering manager, team "
            "lead, tech lead, head of engineering, director or VP of engineering, CTO.",
            false="It hires only engineers without a lead or management role, or only "
            "non-engineering managers.",
        ),
    ),
    "industry": Choice(
        instructions="Which sector is the hiring company's main product or service "
        "in? " + TEXT_ONLY,
        criteria=INDUSTRIES,
    ),
    # Companions to `industry`: a Choice always picks a sector, even for a consultancy or a
    # post that never says what the company does. jev.fold_industry() turns these two
    # into the `other` and `unstated` categories.
    "industry_stated": Noul(
        instructions="Does the job post say what the hiring company makes or does?",
        criteria=NoulCriteria(
            true="It describes the company's product, service or business, even in "
            "one phrase.",
            false="It gives only a company name, roles, location or perks, with no "
            "description of what the company does.",
        ),
    ),
    "industry_fits": Noul(
        instructions={
            "question": "Does the post say what the hiring company does, and does its "
            "main product or service belong to one of `sectors`? " + TEXT_ONLY,
            "sectors": INDUSTRIES,
        },
        criteria=NoulCriteria(
            true="The post describes the company, and it clearly fits one of `sectors`.",
            false="The company does something outside `sectors`, such as consulting, "
            "agency or staffing work, education, government, research, nonprofit or "
            "real estate; or the post does not say what the company does.",
        ),
    ),
    "funding_stage": Choice(
        instructions="What funding stage or company size does the job post state? "
        + TEXT_ONLY
        + " A company's name alone is not evidence of its stage.",
        criteria={
            "bootstrapped": {
                "covers": "Self-funded, no outside investors, or profitable and "
                "independent without venture funding.",
            },
            "seed": {
                "covers": "The post names a pre-seed, seed or angel round.",
                "excludes": "An accelerator batch tag alone, such as 'YC W12' "
                "(unknown).",
            },
            "series_a": {"covers": "The post names a Series A round as its latest."},
            "series_b": {"covers": "The post names a Series B round as its latest."},
            "series_c_plus": {
                "covers": "Series C or later, late-stage private, or pre-IPO.",
            },
            "public_or_large": {
                "covers": "The post says the company is publicly traded, or describes "
                "itself as a large established company (thousands of employees, Fortune "
                "500, a division of a large company).",
            },
            "venture_unspecified": {
                "covers": "The post names investors or an amount raised, or says it is "
                "venture-backed, but names no round.",
            },
            "unknown": {
                "covers": "The post states no stage, round, investors, amount or size. "
                "An accelerator batch tag alone counts as unknown.",
            },
        },
    ),
    "ai_native": Noul(
        instructions="Does the job post describe the company's product as built on AI "
        "or machine learning? " + TEXT_ONLY,
        criteria=NoulCriteria(
            true="The post presents AI or ML as the core of the product: a model, an AI "
            "assistant or agent, an ML platform, or a product whose main feature is "
            "computer vision, speech, recommendations or prediction.",
            false="The post does not mention AI or ML, or uses it for a side feature or "
            "an internal tool, or hires one data scientist, or is hiring for an ML, "
            "research or data-science team at a company whose product the post does "
            "not present as AI. Words like 'data-driven', 'analytics', 'big data' or "
            "'automation' are not AI or ML on their own.",
        ),
    ),
    "new_grad": Noul(
        instructions="Does the job post say it welcomes new grads, junior engineers, "
        "interns or other entry-level candidates? " + TEXT_ONLY,
        criteria=NoulCriteria(
            true="The post invites new graduates, juniors, interns, apprentices, "
            "bootcamp graduates or entry-level engineers, or says no experience is needed.",
            false="The post asks only for experienced engineers, or does not mention "
            "early-career candidates at all.",
        ),
    ),
}

SEEKING: dict[str, Question] = {
    # Every post here is a sales pitch, so a confident self-description is the baseline
    # (Neutral), not a sign of mood. The levels key on what the seeker says about how the
    # search is going. The first live check scored plain pitches near "Positive".
    "seeker_mood": Score(
        instructions="How does this job seeker say their job search is going? Judge "
        "what they say about the search, not how confidently they describe their "
        "skills. Facts about their circumstances, such as a career gap, a layoff, visa "
        "status or a move, are not mood on their own.",
        criteria=[
            {
                "level": "Discouraged",
                "signals": "Says the search is going badly or has dragged on for "
                "months, mentions many rejections, money worries or desperation, or "
                "asks for any job at all.",
            },
            {
                "level": "Strained",
                "signals": "Says the search is hard or urgent: needs work soon, is "
                "struggling to land interviews, or offers concessions such as lower "
                "pay or any role, but without despair.",
            },
            {
                "level": "Neutral",
                "signals": "Describes location, skills, experience and the role they "
                "want, however confidently, but says nothing about how the search is "
                "going or how they feel about it.",
            },
            {
                "level": "Positive",
                "signals": "Says something hopeful about the search: chose to leave "
                "their last job, is looking forward to the next one, or is taking time "
                "to find the right fit.",
            },
            {
                "level": "Upbeat",
                "signals": "Says they are in a strong position: currently employed and "
                "open only to exceptional offers, or openly excited and in demand.",
            },
        ],
    ),
}

QUESTIONS: dict[str, dict[str, Question]] = {"hiring": HIRING, "seeking": SEEKING}
