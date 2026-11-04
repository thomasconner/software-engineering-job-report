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

INDUSTRIES = {
    "ai_ml": {
        "covers": "Sells AI itself: models, AI assistants or agents, ML platforms, "
        "computer vision or speech technology, with no single other sector as its market.",
        "excludes": "An AI product built for one sector below, such as AI for "
        "radiology (health) or AI for fraud (fintech). Pick that sector instead.",
    },
    "devtools_infra": {
        "covers": "Products for developers and IT teams: developer tools, cloud "
        "infrastructure, databases, data pipelines, DevOps, observability, APIs.",
        "excludes": "Business software for non-technical teams (enterprise_saas).",
    },
    "fintech": {
        "covers": "Money: payments, banking, lending, insurance, trading, investing, "
        "accounting, crypto and blockchain.",
    },
    "health": {
        "covers": "Healthcare, medical devices, biotech, pharma, health insurance, "
        "mental health, fitness and wellness.",
    },
    "climate_energy": {
        "covers": "Energy, solar, batteries, grid, EV charging, carbon removal, "
        "climate and sustainability tech.",
    },
    "security": {
        "covers": "Cybersecurity, identity and access, privacy, threat detection, "
        "security compliance.",
    },
    "commerce": {
        "covers": "Buying, selling and moving goods: e-commerce, retail, marketplaces, "
        "logistics, delivery, supply chain, travel booking.",
    },
    "media_consumer": {
        "covers": "Products for consumers: social apps, games, media, news, music, "
        "video, dating, consumer subscriptions.",
    },
    "enterprise_saas": {
        "covers": "Business software for non-technical teams: CRM, HR, sales, "
        "marketing, collaboration, analytics, vertical SaaS (legal, construction).",
    },
    "hardware_robotics": {
        "covers": "Physical products: robotics, drones, semiconductors, IoT, space, "
        "automotive, manufacturing, consumer electronics.",
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
                "excludes": "Remote for only some days of the week (hybrid).",
            },
            "hybrid": {
                "covers": "People must be in an office part of the week, such as two "
                "or three days, and can work from home the rest.",
                "excludes": "Fully remote teams that meet up only for occasional "
                "offsites (remote).",
            },
            "onsite": {
                "covers": "Work happens at an office or site: the post says onsite or "
                "no remote, or names an office location and does not offer remote work.",
            },
            "unclear": {
                "covers": "The post names no office location and no work arrangement, "
                "or contradicts itself.",
            },
        },
    ),
    "seniority": Choice(
        instructions="What seniority level does this job post hire engineers at? If "
        "it hires at several levels, pick the most senior level it names. " + TEXT_ONLY,
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
                "covers": "Senior, lead or tech lead engineers, or asking for five or "
                "more years of experience.",
            },
            "staff_plus": {
                "covers": "Staff, principal, distinguished or architect roles, and "
                "engineering leadership: engineering manager, head of engineering, "
                "director, VP of engineering, CTO.",
            },
            "unspecified": {
                "covers": "No level is given: titles without a level, such as "
                "'Software Engineer' or 'Backend Developer', and no years of experience.",
            },
        },
    ),
    "industry": Choice(
        instructions="Which sector is the hiring company's main product or service "
        "in? " + TEXT_ONLY,
        criteria=INDUSTRIES,
    ),
    # Companion to `industry`: a Choice always picks a sector, even for a consultancy or a
    # university. This says whether any listed sector fits, and run() turns a "no" into
    # the `other` category.
    "industry_fits": Noul(
        instructions="Does the hiring company's main product or service belong to one "
        "of these sectors: AI and machine learning, developer tools and infrastructure, "
        "fintech, health, climate and energy, security, commerce, consumer and media, "
        "business software, hardware and robotics? " + TEXT_ONLY,
        criteria=NoulCriteria(
            true="The post says what the company makes or does, and it clearly belongs "
            "to one of the listed sectors.",
            false="The company does something else, such as consulting, agency or "
            "staffing work, government, education, research, nonprofit or real estate, "
            "or the post does not say what the company does.",
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
                "covers": "Pre-seed, seed or angel funded, or backed by an accelerator "
                "such as Y Combinator or Techstars, with no later round named.",
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
            "unknown": {
                "covers": "The post states no stage, round, investors or size, or says "
                "only that it is venture-backed without naming a round.",
            },
        },
    ),
    "ai_native": Noul(
        instructions="According to the job post, is the company's core product built "
        "on AI or machine learning? " + TEXT_ONLY,
        criteria=NoulCriteria(
            true="The main product depends on AI or ML: it is a model, an AI assistant "
            "or agent, an ML platform, or a product whose core feature is computer "
            "vision, speech, recommendations or prediction.",
            false="AI is absent, a side feature, an internal tool, or a role (such as "
            "one data scientist) rather than the product itself.",
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
    "seeker_mood": Score(
        instructions="How does this job seeker sound about their job search, judging "
        "only from the tone and content of their post?",
        criteria=[
            {
                "level": "Discouraged",
                "signals": "Says the search is going badly or has dragged on for "
                "months, mentions many rejections, money worries or desperation, or "
                "asks for any job at all.",
            },
            {
                "level": "Strained",
                "signals": "Mentions a layoff, a gap or urgency, or offers concessions "
                "such as lower pay or any role, but without despair.",
            },
            {
                "level": "Neutral",
                "signals": "Lists facts only, such as location, remote preference, "
                "skills and a résumé link, with no sign of how the search is going.",
            },
            {
                "level": "Positive",
                "signals": "A confident, warm introduction: describes the work they "
                "enjoy and want next, open and optimistic.",
            },
            {
                "level": "Upbeat",
                "signals": "Enthusiastic and in demand: excited about what comes "
                "next, or employed and choosy, open only to the right role.",
            },
        ],
    ),
}

QUESTIONS: dict[str, dict[str, Question]] = {"hiring": HIRING, "seeking": SEEKING}
