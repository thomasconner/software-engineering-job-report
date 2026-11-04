"""Regex and vocabulary rules, checked against real "Who is hiring?" text from 2014–2026."""

import json

import pytest

from sejr.features import post_answers
from sejr.features.company import company_name, normalize_company
from sejr.features.salary import salary_summary
from sejr.features.tokens import mentions_visa, onsite_token, remote_token
from sejr.features.vocab import TERMS, stack_terms


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("DataSift | Reading UK, San Francisco and New York", "datasift"),
        ("Kodable (http://www.kodable.com) - Full time, Mountain View, CA", "kodable"),
        ("OrgSync — Dallas, TX. Full-time.", "orgsync"),
        ("Citymapper (London, UK) - Help build the world's most loved urban navigation app!",
         "citymapper"),
        ("CloudFlare is hiring Go, Lua, PHP JavaScript developers", "cloudflare"),
        ("Stripe. We're hiring engineers in San Francisco and remotely within US timezones.",
         "stripe"),
        ("Software Engineer at VaxTrac (http://vaxtrac.com) | Washington, D.C. | Full-time",
         "vaxtrac"),
        ("At Tether (https://tether.io/) we're hiring! We envision a world where", "tether"),
        ("Bevy Labs, Inc. | Remote (North/South America) | Full-time", "bevy labs"),
        ("Apple, Inc.", "apple"),
        ("Cardano Foundation  (https://cardanofoundation.org/) | REMOTE | Technical Writer",
         "cardano foundation"),
        ("Planlab.ai | | Product Engineer (Design) & Platform Engineer | ONSITE in London, UK",
         "planlab"),
        ("Modash.io | Senior Product Engineer | Remote (Europe) | Full-time | €75k–110k",
         "modash"),
        ("The Motley Fool | https://careers.fool.com/ | Full-Stack PHP Developer", "motley fool"),
        ("Veezoo AG | Software Developer Backend | Zurich, Switzerland | Onsite", "veezoo"),
        ("Bakken & Bæck | Bonn, Germany", "bakken and bæck"),
        # Headers that open with a role, a location, a URL or a sentence give no name.
        ("Full-stack Python/Django developer", None),
        ("Grand Rapids, MI - Hiring Experienced .Net Web Developers.", None),
        ("Location: Western Suburbs of Chicago (Naperville area)", None),
        ("https://www.hireart.com/jobs/9b26ada4/apply", None),
        ("Looking for a commercial co-founder | Europe / US Remote", None),
        ("I'm applying for the Growth Lead / Expansion & Lifecycle role", None),
        ("SAN FRANCISCO, CA", None),
        ("Amsterdam, Netherlands - Acme", "acme"),
        ("Berlin, Germany | Acme GmbH | Backend Engineer", "acme"),
        ("Amsterdam, the Netherlands. No remote work", None),
        ("London | Acme | Engineer", None),
        ("Boston Dynamics | Robotics Engineer | Waltham, MA", "boston dynamics"),
        ("Senior Backend Engineer | Acme | Remote", None),
        ("Head of Data | Acme", None),
        ("2024 | Acme | Remote", None),
        ("Palo Alto, CA - Box.net", "box"),
        ("San Francisco, CA - Kontagent", "kontagent"),
        ("Santa Barbara, CA: AppFolio inc.", "appfolio"),
        ("Groupon is hiring in Palo Alto, CA & Chicago, IL", "groupon"),
        ("New York, NY - Software Engineer , fulltime", None),
        ("San Mateo, CA", None),
        ("Hey founder of Notion here. You can think of it as the next generation", None),
    ],
)  # fmt: skip
def test_company_name(text, expected):
    assert company_name(text) == expected


def test_company_spellings_normalize_together():
    names = ["Acme Inc.", "ACME, LLC", "The Acme Co.", "acme.io", "Acme Ltd"]
    assert {normalize_company(n) for n in names} == {"acme"}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (("Discord | Senior Software Engineer | REMOTE (US West Coast) or San Francisco, CA | "
         "$196K-$245K base + equity"), (196_000, 245_000, "USD")),
        ("Paramark | Software Engineer (L4) | REMOTE (US) | Full-time | $199K–$249K + equity",
         (199_000, 249_000, "USD")),
        ("Morgan & Morgan | Salesforce Developer | Brooklyn, NY | Onsite | Salary: $90k-$120k",
         (90_000, 120_000, "USD")),
        (("Spade | Multiple Roles | ONSITE NYC or REMOTE (US/Can) | $130-240K+ (depending on "
         "role/level) + equity"), (130_000, 240_000, "USD")),
        ("We'd like to meet you. Compensation is $95K to $130K + equity. Read more",
         (95_000, 130_000, "USD")),
        ("- DevSecOps Engineer | $120,000 - $165,000 | apply at https://app.trinethire.com/",
         (120_000, 165_000, "USD")),
        ("Positions: $150,000 - 200,000 base", (150_000, 200_000, "USD")),
        ("Salary range is 150-200k USD plus options", (150_000, 200_000, "USD")),
        ("We pay $170k to $230k for this role.", (170_000, 230_000, "USD")),
        ("ESTIMATED COMPENSATION: $180,000--$250,000 depending on experience",
         (180_000, 250_000, "USD")),
        ("Senior Backend Engineer - $178,500 USD + equity https://jobs.ashbyhq.com/duck",
         (178_500, 178_500, "USD")),
        ("Sourcegraph | Software Engineer | San Francisco, CA | REMOTE, Salary: $100-200K + equity",
         (100_000, 200_000, "USD")),
        ("Pex | Engineers | Los Angeles | ONSITE, FULL-TIME |Salary $100k+ & Equity | https://pex.com",
         (100_000, None, "USD")),
        ("principal and distinguished engineers | up to ~ $750k", (None, 750_000, "USD")),
        # Several roles: median of the lows, median of the highs.
        (("- Lead Engineer ($140-180k plus stock options)\n- Frontend Engineer ($80-120k plus "
         "stock options)\n- Backend Engineer ($100-150k plus stock options)"),
         (100_000, 150_000, "USD")),
        ("Acme | Senior Engineer | NYC | 100k-140kUSD", (100_000, 140_000, "USD")),
        ("Acme | Engineer | Remote (US) | $150k+bonus", (150_000, 150_000, "USD")),
        ("Acme | Engineer | Austin, TX | $120k (USD) + equity", (120_000, 120_000, "USD")),
        ("Acme | Engineer | Remote (US/Canada) | $150k-$190k", (150_000, 190_000, "USD")),
        # A range right after "Salary:" survives a stock mention; a lone RSU amount doesn't.
        ("Salary: $150k-$200k RSUs on top", (150_000, 200_000, "USD")),
        # Hourly and annual quoted together: only the annual figure counts.
        ("Remote or NY | Full-time or Part-time | $60/hr (Part-time) or $120k/yr (Full-time)",
         (120_000, 120_000, "USD")),
    ],
)  # fmt: skip
def test_usd_salary(text, expected):
    assert salary_summary(text) == expected


@pytest.mark.parametrize(
    ("text", "currency"),
    [
        ("Shopify | Toronto, Canada | ONSITE | $120k-$150k", "CAD"),
        ("Acme | Sydney, Australia | $140k-$170k", "AUD"),
        ("Acme | Berlin, Germany | $90k-$120k", "unknown"),
        ("Acme | Engineer | $120k-$160k CAD + equity", "CAD"),
        ("Acme | Engineer | $120k-$160k base (paid in CAD)", "CAD"),
        ("Planlab.ai | ONSITE in London, UK | 100k-160k GBP + 0.25-0.75% Equity | Visa sponsorship",
         "GBP"),
        ("Trackerbot | Full-Stack Developer (Node.js) | REMOTE |  €35-45k/year", "EUR"),
        ("Montreal, QC | ONSITE, VISA, SALARY: 80-110k CAD + stock options", "CAD"),
        ("digitalasset.zone | NYC or Zurich | SALARY: 160k-200k CHF/USD | ONSITE", "CHF"),
        ("JavaScript Engineer | London | Onsite, Full-time, £40K-£60K + 0.5-1.25% Equity", "GBP"),
        ("- €39.6k-€55.2k gross salary per year.", "EUR"),
        # A bare k-range in the header line is disclosed pay of unknown currency.
        ("Doctible | ONSITE | Fulltime | San Diego, CA | 100k-120k", "unknown"),
        ("The Farmer's Dog | Software Engineer | New York, NY | ONSITE, SALARY:100-140k", "unknown"),
    ],
)  # fmt: skip
def test_non_usd_salary_is_counted_but_not_in_usd(text, currency):
    assert salary_summary(text) == (None, None, currency)


@pytest.mark.parametrize(
    "text",
    [
        "Founded in May 2013. We've raised $8M and don't have to think about raising money.",
        "Our recent funding of $1.9 million lets us add some new members to the team.",
        "Series B was $15M. Total funds raised $20M from First Round Capital.",
        "In 2018, S&P Global acquired Kensho for $550M, the largest AI acquisition in history.",
        "Coatue Management is a $10bn hedge fund that was founded in 1999.",
        "We bring AI to the $17T, 7,000 year old construction industry.",
        "Perks: competitive salary, 401k, & healthcare benefits.",
        "Employee eligible to participate in 401k plan immediately.",
        "somewhere around $55-65/hr is likely.",
        "Remote | Full-time contractor | $23-$34 USD/hour | https://careers.searchat",
        "Salary: $4,000 to $6,000 per month for full time interns",
        "Compensation: 1%-4% equity, plus medical and dental.",
        "Referral bonus: $10k cash for referral to candidate who ends up joining",
        "~ $2000 annual education budget to learn anything you like",
        "Over 100k people pay to subscribe to publications on our platform.",
        "a Javascript codebase of about 250k lines of JS",
        "| up to $380,895/yr Performance Share Units (PSUs; payout",
        "Fixed-fee project ($12K, milestone-based) + equity tied to ARR",
        "we've helped over 100 million Americans save over $15 billion to date",
        "Thinknum | Senior Engineer | New York | 55K",
        "no traffic or commute, surfing, and houses that commonly go for $150,000 to $450,000.",
        "Perks: $50k RSUs vesting over 4 years",
        "Join us: a $10k signing bonus for senior hires",
    ],
)
def test_not_a_salary(text):
    assert salary_summary(text) == (None, None, "none")


@pytest.mark.parametrize(
    ("text", "remote", "onsite"),
    [
        ("Cardano Foundation | REMOTE | Technical Project Manager | Full time", True, False),
        ("Lambda | Senior Software Engineer | San Francisco, CA (Dogpatch) | Onsite | Full Time",
         False, True),
        ("Amazon Alexa | Engineers | Los Angeles, Seattle | Full-time | VISA | ONSITE (remote for now)",
         True, True),
        ("Sentry | Growth Engineer | San Francisco | Full time, on-site", False, True),
        ("ZEN.ag - Distributed team - REMOTE", True, False),
        ("Stripe. We're hiring engineers in San Francisco and remotely within US timezones.",
         True, False),
        ("Amsterdam, the Netherlands. No remote work – must be willing to work at our office.",
         False, False),
        ("FULL-TIME, INTERN, VISA, LOCAL, RELOCATION, NO REMOTE", False, False),
        ("Ruby developer at theScore in Toronto, Ontario, Canada (no remote -- local)", False, False),
        ("Acme | Engineer | NYC | Remote: no", False, False),
        ("Canva | Sydney | Permanent, Onsite\n\nWe are a remote-friendly team at heart.", False, True),
    ],
)  # fmt: skip
def test_remote_and_onsite_tokens(text, remote, onsite):
    assert (remote_token(text), onsite_token(text)) == (remote, onsite)


@pytest.mark.parametrize(
    "text",
    [
        "Shutterstock - New York, San Francisco, Remote, Visa",
        (
            "CircleCI (https://circleci.com/jobs) - fulltime, SF or REMOTE, international OK, "
            "VISA-transfers OK"
        ),
        "Stripe. REMOTE and H1B welcome.",
        "Thumbtack - San Francisco (H1-B and interns welcome)",
        "Booking.com - Amsterdam - relocation and visa sponsored",
        "Gusto | VISA, ONSITE | Sr. Rails/React Engineer | San Francisco",
        "We sponsor all visas (including H1B and Green Card), and we pay market rate.",
        "Formlabs | Software Lead | Full-time | Visa\n\nFormlabs' software is a mix of C++",
        "ZenPayroll - San Francisco, CA\n\nVisa provided\n\nWe're revolutionizing payroll",
        "FULL-TIME, INTERN, VISA, LOCAL, RELOCATION, NO REMOTE",
        "Visa: H-1B transfers supported; no new visa sponsorship",
        "Sorry at this time we cannot sponsor NEW H-1B’s, but we can transfer existing visa’s",
    ],
)
def test_mentions_visa(text):
    assert mentions_visa(text)


@pytest.mark.parametrize(
    "text",
    [
        "Acme | REMOTE (US) | Full-time | No visa sponsorship offered",
        "Unfortunately we can't sponsor visas right now unless you're from Canada",
        "At this time we aren't prepared to offer H1B/Visa sponsorship or remote work.",
        "Please note: HPR currently does not provide H-1B visa sponsorship",
        "We are not in a position to sponsor visas, and therefore can only consider people",
        "competitive benefits + equity; VISA sponsorship is NOT possible.",
        "Please note, we currently don't sponsor H1Bs or other visas.",
        "we can only hire people with a legal right to work in the US (e.g. no H-1Bs), sorry.",
        "Applicants must be US Citizens or green card holders.",
        "Allowed to work in Germany (EU citizen or work visa holder) or in the USA",
        "foreigners welcome as long as you can secure a visa on your own (usually J-1 or F-1).",
        "Acme | Engineer | NYC\n\nOur clients include Google, Microsoft, Visa, Twitter and the FDA.",
        "Acme | Engineer | NYC\n\nWe're backed by Homebrew and are Visa's first seed investment.",
        "REMOTE (US only, US time zones; no visa sponsorship) | Full-time | $170k–$210k",
        "We're not able to offer relocation or visa sponsorship.",
        "We help trial sponsors recruit quickly.",
        "VISA | Senior Software Engineer | Austin, TX | ONSITE",
        "Acme | London | You must have the right to work in the UK, visa holders welcome",
        "Acme | NYC | Work visa required.",
        "Visa Inc | Platform Engineer | Kubernetes / OpenShift",
        "I'm moving to the Bay Area in November (I have work visa)",
    ],
)
def test_no_visa_offer(text):
    assert not mentions_visa(text)


@pytest.mark.parametrize(
    ("text", "present", "absent"),
    [
        ("We write code in Python and Go, deploy 15-20 times a day", {"Python", "Go"}, set()),
        ("Redis and Postgres, and some Go/Lua sprinkled in.", {"Go", "Redis", "Postgres"}, set()),
        ("strongDM | All Roles! Go / Golang | FULL REMOTE", {"Go"}, set()),
        ("Go, Kubernetes, reliable systems", {"Go", "Kubernetes"}, set()),
        ("Head of AI Sales / AI Go To Market | SF", set(), {"Go"}),
        ("a hands-on Go-To-Market (GTM) Specialist", set(), {"Go"}),
        ("Free lunch in the Dropbox building. Go Giants!", set(), {"Go"}),
        ("Go ahead and apply at https://example.com", set(), {"Go"}),
        ("Python, Java, C/C++, Go.", {"Python", "Java", "C", "C++", "Go"}, {"C#"}),
        ("Experience programming in Python, R, C, and C++.", {"Python", "R", "C", "C++"}, set()),
        ("A video codec written in C (with some CUDA)", {"C"}, set()),
        ("We just raised a $65MM Series C to continue growing our team.", set(), {"C"}),
        ("iOS with Objective-C, or even Windows Phone with C#.", {"iOS", "C#"}, {"C"}),
        ("Washington, D.C. | Full-time", set(), {"C"}),
        ("data science tools in python or R and know JS", {"Python", "R", "JavaScript"}, set()),
        ("R&D team in Boston", set(), {"R"}),
        ("We build Terran R, a reusable medium-to-heavy-lift rocket", set(), {"R"}),
        ("Backend (Rust/Go/Typescript/PHP)", {"Rust", "Go", "TypeScript", "PHP"}, set()),
        ("Our office is in the Rust Belt", set(), {"Rust"}),
        ("Swift and Kotlin for our mobile apps", {"Swift", "Kotlin"}, set()),
        ("We value swift decisions and SWIFT payments", set(), {"Swift"}),
        ("Front-end: React, Next.js; backend: Node.js and Django", {"React", "Next.js",
         "Node.js", "Django"}, set()),
        ("Users react quickly to changes", set(), {"React"}),
        ("Backed by Spark Capital", set(), {"Spark"}),
        ("data team (Go, Kafka, Spark, Flink)", {"Go", "Kafka", "Spark"}, set()),
        ("Ruby on Rails, Sidekiq", {"Ruby", "Rails"}, set()),
        ("guard rails for production", set(), {"Rails"}),
        ("JavaScript and TypeScript", {"JavaScript", "TypeScript"}, {"Java"}),
        ("Have shipped AI agents or agentic workflows", {"AI agents"}, set()),
        ("Our real estate agents and insurance agents love it", set(), {"AI agents"}),
        ("We use LLMs with RAG over PyTorch models", {"LLM", "RAG", "PyTorch"}, set()),
        ("Each node in the graph", set(), {"Node.js"}),
        ("AWS, GCP and Azure, provisioned with Terraform", {"AWS", "GCP", "Azure", "Terraform"},
         set()),
        ("Machine learning on k8s", {"Machine learning", "Kubernetes"}, set()),
        ("Apply: https://jobs.example.com/go/python-rust | Remote", set(), {"Go", "Python", "Rust"}),
    ],
)  # fmt: skip
def test_stack_terms(text, present, absent):
    found = set(stack_terms(text))
    assert present <= found
    assert not (absent & found)


def test_vocabulary_size():
    assert 40 <= len(TERMS) <= 50


def test_post_answers_shape():
    text = (
        "Discord | Senior Software Engineer | REMOTE (US West Coast) | $196K-$245K base + equity"
        "\n\nWe use Python and Rust. Visa sponsorship available."
    )
    answers = {(q, m): (value, label, probs) for _, q, m, _, value, label, probs, _ in
               post_answers(1, text)}  # fmt: skip
    assert answers[("company", "regex")][1] == "discord"
    assert answers[("salary_min_usd", "regex")][0] == 196_000
    assert answers[("salary_max_usd", "regex")][0] == 245_000
    assert answers[("salary_currency", "regex")][1] == "USD"
    assert answers[("remote_token", "regex")][0] == 1.0
    assert answers[("onsite_token", "regex")][0] == 0.0
    assert answers[("mentions_visa", "regex")][0] == 1.0
    assert json.loads(answers[("stack", "vocab")][2]) == {"Python": 1.0, "Rust": 1.0}
    assert json.loads(answers[("region", "regex")][2]) == {"us": 1.0}
    assert answers[("open_to_us", "regex")][0] == 1.0


def test_seeking_posts_get_only_a_region():
    answers = post_answers(2, "Location: Toronto, ON\nRemote: Yes", "seeking")
    assert [(q, label) for _, q, _, _, _, label, _, _ in answers] == [
        ("region", "canada")
    ]
