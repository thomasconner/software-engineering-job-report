"""Monthly snapshots of public company job boards (Greenhouse, Ashby, Lever, SmartRecruiters).

Boards come from two places: links in the in-snapshot posts of the latest complete hiring
threads, and a fixed panel in data/external/ats/panel.json. One gzipped JSON per run goes to
data/external/ats/<YYYY-MM-DD>.json.gz with job counts and per-job metadata, never job text.
"""

import gzip
import json
import re
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import quote, unquote

import httpx

from sejr.config import ATS_DIR
from sejr.fetch import Client, GaveUp, now

USER_AGENT = "software-engineering-job-report (github.com/thomasconner/software-engineering-job-report)"
MIN_INTERVAL = 1.0
# A board that fails twice is recorded as failed; next month tries again. Short timeouts
# keep a hung host from eating the workflow's time budget.
MAX_ATTEMPTS = 2
TIMEOUT = 20
# This many unreachable boards in a row means our network is down, not theirs.
MAX_CONSECUTIVE_UNREACHABLE = 10
# A snapshot with more failed boards than this would look like a hiring drop, so it isn't written.
MAX_FAILED_SHARE = 0.2
# Boards linked from this many of the latest complete hiring threads. Three months lets a
# later run ask whether a company that posted in month t is still hiring at t+3.
HN_MONTHS = 3
SMARTRECRUITERS_PAGE = 100
# Bumped whenever is_engineering changes; jobs keep title and department, so old
# snapshots can be reclassified.
CLASSIFIER_VERSION = "eng-3"

API = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/departments",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{slug}",
    "lever": "https://api.lever.co/v0/postings/{slug}?mode=json",
    "smartrecruiters": "https://api.smartrecruiters.com/v1/companies/{slug}/postings",
}

# Slugs are the first path segment. Greenhouse embeds (iframe and script) name the board
# in ?for=<slug>. EU-hosted Greenhouse and Lever boards use other API hosts and are not matched.
SLUG = r"([A-Za-z0-9][A-Za-z0-9._%-]*)"
LINK_PATTERNS = [
    ("greenhouse", re.compile(r"(?:job-)?boards\.greenhouse\.io/embed/job_(?:app|board)(?:/js)?\?(?:[^\s\"'<>]*&)?for=" + SLUG, re.IGNORECASE)),
    ("greenhouse", re.compile(r"(?:job-)?boards\.greenhouse\.io/" + SLUG, re.IGNORECASE)),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/" + SLUG, re.IGNORECASE)),
    ("lever", re.compile(r"jobs\.lever\.co/" + SLUG, re.IGNORECASE)),
    ("smartrecruiters", re.compile(r"(?:jobs|careers)\.smartrecruiters\.com/" + SLUG, re.IGNORECASE)),
]  # fmt: skip
NOT_SLUGS = {"embed", "oneclick-ui", "api", "v1"}
FAILED = {"error", "unreachable"}


def board_key(ats: str, slug: str) -> tuple[str, str]:
    return ats, slug.lower()


def extract_slugs(text: str) -> set[tuple[str, str]]:
    """(ats, slug) for every job-board link in a post. Slugs are lowercased, except
    SmartRecruiters company ids, which are case-sensitive in its API."""
    found = set()
    for ats, pattern in LINK_PATTERNS:
        for match in pattern.finditer(text):
            # A link at the end of a sentence picks up its period; HN cuts long labels with "...".
            slug = unquote(match[1]).rstrip(".")
            if not slug or slug.lower() in NOT_SLUGS:
                continue
            found.add((ats, slug if ats == "smartrecruiters" else slug.lower()))
    return found


def discover_hn(
    con, months: int = HN_MONTHS
) -> tuple[list[str], dict[tuple[str, str], dict]]:
    """The latest complete hiring-thread months, and the boards their in-snapshot posts link."""
    selected = con.execute(
        """
        SELECT thread_id, strftime(month, '%Y-%m') AS month FROM threads
        WHERE kind = 'hiring' AND fetched_at >= snapshot_at
        ORDER BY month DESC LIMIT ?
        """,
        [months],
    ).fetchall()
    rows = con.execute(
        """
        SELECT strftime(t.month, '%Y-%m'), p.text FROM posts p JOIN threads t USING (thread_id)
        WHERE p.in_snapshot AND p.thread_id IN (SELECT unnest(?::BIGINT[]))
        ORDER BY t.month, p.post_id
        """,
        [[thread_id for thread_id, _ in selected]],
    ).fetchall()
    boards: dict[tuple[str, str], dict] = {}
    for month, text in rows:
        for ats, slug in extract_slugs(text):
            board = boards.setdefault(
                board_key(ats, slug), {"ats": ats, "slug": slug, "sources": []}
            )
            if f"hn:{month}" not in board["sources"]:
                board["sources"].append(f"hn:{month}")
    return sorted(month for _, month in selected), boards


def load_panel(path: Path, day: date) -> list[dict]:
    """Panel members on day: added <= day < removed. Entries are never deleted, so the
    panel's history stays in the file."""
    iso = day.isoformat()
    return [
        b
        for b in json.loads(path.read_text())["boards"]
        if b["added"] <= iso and (not b.get("removed") or iso < b["removed"])
    ]


def load_scopes(path: Path) -> dict[str, str]:
    """Hand-set board scopes from overrides.json, keyed "<ats>/<slug>" (lowercase)."""
    if not path.exists():
        return {}
    return {k.lower(): v for k, v in json.loads(path.read_text())["scope"].items()}


def plan_boards(
    hn: dict[tuple[str, str], dict],
    panel: list[dict],
    scopes: dict[str, str] | None = None,
) -> list[dict]:
    """HN and panel boards merged. scope is "company" unless overrides.json says otherwise
    ("portfolio" for a VC or aggregator board that lists jobs at many companies)."""
    scopes = scopes or {}
    boards = {key: dict(board) for key, board in hn.items()}
    for entry in panel:
        key = board_key(entry["ats"], entry["slug"])
        board = boards.setdefault(
            key, {"ats": entry["ats"], "slug": entry["slug"], "sources": []}
        )
        board["sources"] = [*board["sources"], "panel"]
    for (ats, slug), board in boards.items():
        board["scope"] = scopes.get(f"{ats}/{slug}", "company")
    return sorted(boards.values(), key=lambda b: board_key(b["ats"], b["slug"]))


# --- Engineering classifier -------------------------------------------------------------
#
# "Engineering" here means software engineering: people who write and run software
# (backend, frontend, mobile, infra, SRE, security, data and ML engineering, firmware,
# QA automation, research engineers) and the managers of those teams. Not engineering:
# other engineering disciplines (mechanical, electrical, chip design), customer-facing
# technical roles (sales, solutions, support, implementation engineers), IT support,
# scientists and analysts, and product, program, design, recruiting or sales roles that
# merely sit in an engineering department or mention one.
#
# Labeling calls for borderline titles (applied to the hand-labeled fixture too):
# forward-deployed engineers are in (they write software at customer sites); GTM
# engineers, IT support engineers, partner/deployment engineers in go-to-market teams
# and manual testers are out; "Member of Technical Staff" is in unless the title names
# hardware or a non-engineering area (policy, strategy). A "Systems Engineer" with no
# software word is in only when its department is a software, engineering or
# infrastructure one and not systems engineering, hardware or vehicles; Fuel, IT,
# Financial and Business Systems Engineers are out. A customer-facing role word before
# the role (Sales, Solutions, Field, Support Engineer) is out even with software words
# after it ("Solutions Engineer, ML Platform"). A non-engineering
# word next to a software engineering title ("Backend Engineer | Accounting") names the
# team, not the role, so the job is in.
#
# The rule reads the title first, the department only when the title is a bare
# "Engineer" or "Systems Engineer": 0) customer-facing roles are out; 1) other-discipline or customer-facing engineering titles are out;
# 2) non-engineering roles are out; 3) titles that name software work are in; 4) a bare
# engineer/architect title is in unless its department names a non-software function.

NON_SOFTWARE_ENGINEERING = re.compile(
    r"\b(sales|gtm|go[- ]to[- ]market|solutions?|pre-?sales|customer|support|implementation|onboarding|field|"
    r"services?|deployment strategist|data cent(?:er|re)|mechanical|electrical|electronics?|civil|structural|"
    r"chemical|fuel|manufacturing|process|industrial|mechatronics?|hardware|rf|analog|asic|fpga|"
    r"silicon|chip|pcb|optical|photonics?|nuclear|reactor|propulsion|thermal|materials?|"
    r"facilities|construction|environmental|aerospace|avionics|test technician|"
    r"technician|it support|helpdesk|help desk|desktop|validation)\b",
    re.IGNORECASE,
)
NON_ENGINEERING_ROLE = re.compile(
    r"\b(recruit\w*|sourc(?:er|ing)|talent|sales|account (?:executive|manager)|marketing|"
    r"counsel|attorney|legal|paralegal|accountant|accounting|controller|payroll|tax|"
    r"designer|product manager|program manager|project manager|product owner|"
    r"product marketing|analyst|scientist|researcher|advocate|evangelist|developer relations|"
    r"devrel|community|writer|editor|communications|people partner|hrbp|human resources|"
    r"executive assistant|assistant|coordinator|specialist|representative|customer success|"
    r"business development|partnerships?|recruiting|operations manager|chief of staff|"
    r"intern(?:ship)? program|"
    r"(?:curriculum|course|content|instructional|business|land|real estate) developer)\b",
    re.IGNORECASE,
)
SOFTWARE_WORDS = (
    r"software|swe|sde|developer|programmer|devops|devsecops|sre|site reliability|"
    r"full[- ]?stack|front[- ]?end|back[- ]?end|mobile|ios|android|web|platform|"
    r"infrastructure|infra|cloud|data|machine learning|ml|ai|llm|security|reliability|"
    r"distributed|firmware|embedded|api|application|applied|product engineer|"
    r"forward[- ]deployed|founding|research engineer|qa|quality assurance|test automation|"
    r"automation|sdet|database|kernel|compiler|graphics|game|gameplay|rendering|"
    r"analytics engineer|frontier|inference|training|gpu|performance|observability|"
    r"build|release|tooling|developer experience|member of technical staff|"
    r"c\+\+|rust|golang|operating systems?|network(?:ing)?|dns|sdk|"
    r"technical staff|mts|cto|chief technology officer|tech lead|engineering manager|"
    r"(?:head|director|vp|vice president|manager)(?:,| of)? (?:software )?engineering|"
    r"engineering (?:lead|director|head)"
)
# Lookarounds instead of \b so "C++" matches.
SOFTWARE_TITLE = re.compile(rf"(?<!\w)({SOFTWARE_WORDS})(?!\w)", re.IGNORECASE)
SYSTEMS = re.compile(r"\bsystems?\b", re.IGNORECASE)
# Enterprise IT, not software engineering.
IT_SYSTEMS = re.compile(
    r"\b(it|i\.t\.|financial|finance|business|enterprise|people|gtm|corporate)\s+systems?\b",
    re.IGNORECASE,
)
SYSTEMS_DEPARTMENT_IN = re.compile(
    r"\b(software|engineering|infrastructure)\b", re.IGNORECASE
)
SYSTEMS_DEPARTMENT_OUT = re.compile(
    r"\b(systems? engineering|hardware|vehicle|avionics|mechanical|electrical|propulsion|"
    r"manufacturing|production|spacecraft|satellite|aircraft|safety|it|i\.t\.)\b",
    re.IGNORECASE,
)
# A customer-facing role word right before the role ("Sales Engineer, Infrastructure",
# "Field Engineer, Platform"), or "specialist", rules a title out whatever software words
# follow. "Software Engineer, Sales Platform" stays in: there "sales" names the product.
CUSTOMER_FACING_ROLE = re.compile(
    r"\b(sales|solutions?|pre-?sales|field|support|customer)\s+(engineer\w*|architect\w*)\b"
    r"|\bspecialist\b",
    re.IGNORECASE,
)
GENERIC_ENGINEERING = re.compile(
    r"\b(engineer\w*|architect|developer|programmer)\b", re.IGNORECASE
)
NON_SOFTWARE_DEPARTMENT = re.compile(
    r"\b(hardware|mechanical|electrical|manufacturing|operations|sales|customer|support|"
    r"field|facilities|construction|supply chain|production|quality|reactor|fuel|"
    r"vehicle|avionics|propulsion|marketing|finance|legal|people|g&a)\b",
    re.IGNORECASE,
)
# Words that keep a title in even when it also names a customer-facing or other function,
# as in "Backend Engineer, Sales Platform" or "Hardware/Firmware Engineer".
SOFTWARE_OVERRIDE = re.compile(
    r"\b(software|firmware|embedded|platform|back[- ]?end|front[- ]?end|full[- ]?stack|"
    r"mobile|ios|android|ml|machine learning|infrastructure|devops|sre|site reliability|"
    r"research engineer)\b",
    re.IGNORECASE,
)
ROLE_OVERRIDE = re.compile(
    r"\b(software engineer\w*|software developer|engineering manager)\b", re.IGNORECASE
)


def is_engineering(title: str, department: str | None = None) -> bool:
    title = title or ""
    if CUSTOMER_FACING_ROLE.search(title):
        return False
    software_override = bool(SOFTWARE_OVERRIDE.search(title))
    is_engineer = bool(GENERIC_ENGINEERING.search(title))
    if NON_SOFTWARE_ENGINEERING.search(title) and not software_override:
        return False
    if NON_ENGINEERING_ROLE.search(title) and not (
        ROLE_OVERRIDE.search(title)
        or (software_override and re.search(r"\bengineer\b", title, re.IGNORECASE))
    ):
        return False
    software_title = bool(SOFTWARE_TITLE.search(title))
    if SYSTEMS.search(title) and not software_title:
        # "Systems Engineer" means software at Cloudflare and spacecraft at ICEYE; the
        # department tells them apart.
        return (
            not IT_SYSTEMS.search(title)
            and bool(SYSTEMS_DEPARTMENT_IN.search(department or ""))
            and not SYSTEMS_DEPARTMENT_OUT.search(department or "")
        )
    if software_title and is_engineer:
        return True
    if re.search(
        r"\b(developer|programmer|sre|devops|sdet|member of technical staff|"
        r"technical staff|cto|chief technology officer|tech lead)\b",
        title,
        re.IGNORECASE,
    ):
        return True
    if is_engineer:
        return not NON_SOFTWARE_DEPARTMENT.search(department or "")
    return False


def is_engineering_job(job: dict) -> bool:
    """Department and team both describe where a job sits (Ashby: "R&D" / "Engineering")."""
    unit = " > ".join(filter(None, [job.get("department"), job.get("team")]))
    return is_engineering(job["title"], unit)


# --- US-located jobs -------------------------------------------------------------------
#
# Export counts a board's US-located jobs from job locations each time it runs; the count
# is never stored, so a parser fix applies to every past snapshot. Locations that name no
# country ("Remote", "North America", "N/A") count neither way.

US_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA",
    "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT",
    "VA", "WA", "WV", "WI", "WY", "DC",
]  # fmt: skip
CA_PROVINCES = [
    "ON",
    "QC",
    "BC",
    "AB",
    "MB",
    "NS",
    "NB",
    "NL",
    "PE",
    "SK",
    "YT",
    "NT",
    "NU",
]
# Two-letter codes are matched case-sensitively after a separator, so "or" and "in" in
# "(ON, AB, or NS Only)" are words, not Oregon and Indiana.
# No "^": a leading code is a country or region prefix ("CA-Ontario-Toronto",
# "IN-Bangalore", "DE-Berlin"), not a state.
SEPARATOR = r"(?:[,;(\-–/|]\s*)"
US_STATE_CODE = re.compile(
    SEPARATOR + r"(?:" + "|".join(US_STATES) + r")(?=$|[\s,;)/|.-])"
)
CA_PROVINCE_CODE = re.compile(
    SEPARATOR + r"(?:" + "|".join(CA_PROVINCES) + r")(?=$|[\s,;)/|.-])"
)
US_NAMED = re.compile(r"\bU\.S\.|\bUS\b")
US_NAMED_CI = re.compile(r"\b(united states|usa)\b", re.IGNORECASE)
US_PLACE = re.compile(
    r"\b(alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|"
    r"georgia|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|"
    r"massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|nevada|"
    r"new hampshire|new jersey|new mexico|new york|north carolina|north dakota|ohio|"
    r"oklahoma|oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|"
    r"texas|utah|vermont|virginia|washington|west virginia|wisconsin|wyoming|"
    r"san francisco|sf|bay area|nyc|seattle|boston|austin|los angeles|chicago|denver|"
    r"atlanta|palo alto|mountain view|menlo park|sunnyvale|santa clara|san jose|"
    r"brooklyn|miami|silicon valley|phoenix|philadelphia|houston|dallas|san diego|"
    r"portland|minneapolis|detroit|pittsburgh|raleigh|durham|nashville|salt lake city|"
    r"baltimore|st\.? louis|kansas city|columbus|cincinnati|cleveland|charlotte|orlando|"
    r"tampa|las vegas|sacramento|oakland|berkeley|irvine|redwood city|san mateo|"
    r"south san francisco|arlington|reston|mclean|boulder|ann arbor|new orleans|honolulu|"
    r"jersey city|hoboken|stamford|providence|scottsdale|tempe|plano|fort worth|"
    r"san antonio|indianapolis|milwaukee|omaha|el segundo|santa monica|culver city|"
    r"pasadena|long beach|hawthorne|cupertino|san bruno|foster city|emeryville)\b",
    re.IGNORECASE,
)
CANADA = re.compile(
    r"\b(canada|canadian|toronto|vancouver|montr[eé]al|ottawa|calgary|edmonton|waterloo|"
    r"kitchener|winnipeg|halifax|qu[eé]bec|ontario|british columbia|alberta)\b",
    re.IGNORECASE,
)
# Places outside the US that job boards name. A location matching nothing here or in the
# US lists is unknown, not non-US.
NON_US_PLACE = re.compile(
    r"\b(uk|u\.k\.|united kingdom|england|scotland|wales|ireland|london|dublin|manchester|"
    r"edinburgh|cambridge, uk|oxford|belfast|europe|eu|emea|apac|latam|asia|"
    r"germany|berlin|munich|m[uü]nchen|hamburg|frankfurt|cologne|stuttgart|france|paris|"
    r"spain|madrid|barcelona|valencia|portugal|lisbon|porto|italy|milan|rome|netherlands|"
    r"amsterdam|rotterdam|belgium|brussels|switzerland|zurich|z[uü]rich|geneva|austria|"
    r"vienna|poland|warsaw|krak[oó]w|wroc[lł]aw|czech|prague|hungary|budapest|romania|"
    r"bucharest|bulgaria|sofia|serbia|belgrade|croatia|greece|athens|sweden|stockholm|"
    r"norway|oslo|denmark|copenhagen|finland|helsinki|espoo|estonia|tallinn|latvia|riga|"
    r"lithuania|vilnius|ukraine|kyiv|turkey|istanbul|israel|tel aviv|uae|dubai|abu dhabi|"
    r"saudi arabia|riyadh|qatar|egypt|cairo|nigeria|lagos|kenya|nairobi|south africa|"
    r"cape town|johannesburg|india|bengaluru|bangalore|hyderabad|pune|chennai|mumbai|"
    r"delhi|new delhi|gurugram|gurgaon|noida|kolkata|ahmedabad|pakistan|bangladesh|"
    r"sri lanka|singapore|malaysia|kuala lumpur|penang|petaling jaya|thailand|bangkok|"
    r"vietnam|ho chi minh|hanoi|philippines|manila|indonesia|jakarta|japan|tokyo|osaka|"
    r"korea|seoul|china|beijing|shanghai|shenzhen|hangzhou|guangzhou|hong kong|taiwan|"
    r"taipei|australia|sydney|melbourne|brisbane|perth|new zealand|auckland|"
    r"mexico|mexico city|guadalajara|monterrey|brazil|s[aã]o paulo|rio de janeiro|"
    r"argentina|buenos aires|chile|santiago|colombia|bogot[aá]|medell[ií]n|peru|lima|"
    r"costa rica|uruguay|montevideo|luxembourg|cyprus|malta|iceland|slovakia|slovenia|"
    r"toulouse|lyon|lviv|united arab emirates|apj|wellington|rwanda|mozambique|drc|congo|"
    r"ghana|accra|morocco|ethiopia|uganda|tanzania|freiburg)\b",
    re.IGNORECASE,
)
NO_COUNTRY_WORDS = {
    "remote", "anywhere", "any", "global", "worldwide", "north", "america", "americas",
    "multiple", "location", "locations", "various", "hybrid", "in", "office", "onsite", "on",
    "site", "flexible", "tbd", "distributed", "n/a", "na", "none", "or",
}  # fmt: skip


def is_us_location(location: str | None) -> bool | None:
    """True for a US location, False for a recognized non-US one, None otherwise.

    Order matters: any US name, state or city wins, so multi-city strings that include a
    US office count as US ("San Francisco, CA; Toronto, Canada"); then Canada, by name, city
    or province code ("Toronto, ON, CA" and "Toronto, CA" are Canada, not California);
    then two-letter state codes; then known non-US places. Anything else is unknown."""
    location = (location or "").strip()
    words = re.findall(r"[a-z./]+", location.lower())
    if all(w.strip(".") in NO_COUNTRY_WORDS for w in words):
        return None
    if (
        US_NAMED.search(location)
        or US_NAMED_CI.search(location)
        or US_PLACE.search(location)
    ):
        return True
    if CANADA.search(location) or CA_PROVINCE_CODE.search(location):
        return False
    if US_STATE_CODE.search(location):
        return True
    if NON_US_PLACE.search(location):
        return False
    return None


def us_jobs(jobs: list[dict]) -> dict[str, int]:
    """Jobs by location: us, non_us, unknown. Export computes this; snapshots don't store it."""
    counts = {"us": 0, "non_us": 0, "unknown": 0}
    for job in jobs:
        us = is_us_location(job.get("location"))
        counts["unknown" if us is None else "us" if us else "non_us"] += 1
    return counts


# --- Workplace --------------------------------------------------------------------------
#
# remote / hybrid / onsite, or None when the board doesn't say. Each ATS's own field wins
# (Ashby workplaceType, Lever workplaceType, SmartRecruiters location.remote/hybrid);
# Ashby's isRemote is used only without workplaceType, because Ashby sets it for hybrid
# jobs too. Otherwise the location text decides: remote or distributed beats hybrid,
# which beats onsite; a plain city says nothing and stays None.

WORKPLACE_TYPES = {
    "remote": "remote",
    "hybrid": "hybrid",
    "onsite": "onsite",
    "on-site": "onsite",
    "on site": "onsite",
}


def workplace_from_text(*values: str | None) -> str | None:
    text = " ".join(v for v in values if v)
    if re.search(r"\b(remote|distributed|anywhere)\b", text, re.IGNORECASE):
        return "remote"
    if re.search(r"\bhybrid\b", text, re.IGNORECASE):
        return "hybrid"
    if re.search(r"\b(on-?site|in[- ]office|in[- ]person)\b", text, re.IGNORECASE):
        return "onsite"
    return None


def _workplace_type(value) -> str | None:
    return WORKPLACE_TYPES.get(str(value).lower()) if value else None


# --- Parsers: one API response → compact jobs ------------------------------------------


def _job(
    id_,
    title,
    department=None,
    team=None,
    location=None,
    workplace=None,
    published=None,
    updated=None,
) -> dict:
    job = {
        "id": str(id_),
        "title": (title or "").strip(),
        "department": department or None,
        "team": team or None,
        "location": location or None,
        "workplace": workplace,
        "published": published,
        "updated": updated,
    }
    return {k: v for k, v in job.items() if v is not None}


def parse_greenhouse(payload: dict) -> list[dict]:
    """The /departments response lists jobs under departments (or "No Department"), stored
    with their parents, "Engineering > Platform". A job listed under several departments is
    kept once, under the most specific (deepest) one; ties keep the first."""
    departments = {d["id"]: d for d in payload["departments"]}

    def path(dep: dict) -> list[str]:
        names, seen = [], set()
        while dep and dep["id"] not in seen:
            seen.add(dep["id"])
            names.append(dep["name"])
            dep = departments.get(dep.get("parent_id"))
        return list(reversed(names))

    jobs: dict = {}
    depth: dict = {}
    for dep in payload["departments"]:
        names = [] if dep["id"] == 0 else path(dep)
        for j in dep["jobs"]:
            if j["id"] in jobs and depth[j["id"]] >= len(names):
                continue
            location = (j.get("location") or {}).get("name")
            depth[j["id"]] = len(names)
            jobs[j["id"]] = _job(
                j["id"],
                j["title"],
                department=" > ".join(names),
                location=location,
                workplace=workplace_from_text(location),
                published=j.get("first_published"),
                updated=j.get("updated_at"),
            )
    return list(jobs.values())


def parse_ashby(payload: dict) -> list[dict]:
    jobs = []
    for j in payload["jobs"]:
        if j.get("isListed") is False:
            continue
        workplace = _workplace_type(j.get("workplaceType"))
        if workplace is None and j.get("isRemote") is True:
            workplace = "remote"
        if workplace is None:
            workplace = workplace_from_text(j.get("location"))
        jobs.append(
            _job(
                j["id"],
                j["title"],
                department=j.get("department"),
                team=j.get("team"),
                location=j.get("location"),
                workplace=workplace,
                published=j.get("publishedAt"),
            )
        )
    return jobs


def _epoch_ms(value) -> str | None:
    if not isinstance(value, int | float):
        return None
    return datetime.fromtimestamp(value / 1000, UTC).isoformat(timespec="seconds")


def parse_lever(payload: list) -> list[dict]:
    jobs = []
    for j in payload:
        categories = j.get("categories") or {}
        location = categories.get("location")
        workplace = _workplace_type(j.get("workplaceType")) or workplace_from_text(
            location
        )
        jobs.append(
            _job(
                j["id"],
                j.get("text"),
                department=categories.get("department"),
                team=categories.get("team"),
                location=location,
                workplace=workplace,
                published=_epoch_ms(j.get("createdAt")),
            )
        )
    return jobs


def parse_smartrecruiters(pages: list[dict]) -> list[dict]:
    jobs = {}
    for page in pages:
        for j in page["content"]:
            location = j.get("location") or {}
            if location.get("remote"):
                workplace = "remote"
            elif location.get("hybrid"):
                workplace = "hybrid"
            elif location.get("remote") is False:
                workplace = "onsite"
            else:
                workplace = None
            jobs[j["id"]] = _job(
                j["id"],
                j.get("name"),
                department=(j.get("department") or {}).get("label"),
                team=(j.get("function") or {}).get("label"),
                location=location.get("fullLocation") or location.get("city"),
                workplace=workplace,
                published=j.get("releasedDate"),
            )
    return list(jobs.values())


def fetch_board(client: Client, ats: str, slug: str) -> list[dict]:
    url = API[ats].format(slug=quote(slug, safe=""))
    if ats == "greenhouse":
        return parse_greenhouse(client.get(url).json())
    if ats == "ashby":
        return parse_ashby(client.get(url).json())
    if ats == "lever":
        return parse_lever(client.get(url).json())
    pages = []
    while True:
        params = {
            "limit": SMARTRECRUITERS_PAGE,
            "offset": len(pages) * SMARTRECRUITERS_PAGE,
        }
        page = client.get(url, params).json()
        pages.append(page)
        if (
            not page["content"]
            or params["offset"] + len(page["content"]) >= page["totalFound"]
        ):
            return parse_smartrecruiters(pages)


def snapshot_board(client: Client, board: dict) -> dict:
    """Fetch one board. A missing or broken board is recorded with its status, not raised:
    not_found (404/410), http_<code>, unreachable (no response at all) or error."""
    record = {**board, "fetched_at": now()}
    try:
        jobs = fetch_board(client, board["ats"], board["slug"])
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        return record | {
            "status": "not_found" if code in (404, 410) else f"http_{code}"
        }
    except (httpx.TransportError, GaveUp) as e:
        transport = isinstance(e, httpx.TransportError) or e.transport
        status = "unreachable" if transport else "error"
        return record | {"status": status, "error": f"{type(e).__name__}: {e}"[:200]}
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as e:
        return record | {"status": "error", "error": f"{type(e).__name__}: {e}"[:200]}
    jobs.sort(key=lambda j: j["id"])
    workplace = {"remote": 0, "hybrid": 0, "onsite": 0, "unknown": 0}
    for job in jobs:
        workplace[job.get("workplace", "unknown")] += 1
    return record | {
        "status": "ok" if jobs else "empty",
        "total_jobs": len(jobs),
        "engineering_jobs": sum(is_engineering_job(j) for j in jobs),
        "workplace_jobs": workplace,
        "jobs": jobs,
    }


def is_failed(result: dict) -> bool:
    """Our side or theirs broke: any HTTP error but 404/410 (stored as not_found), no
    response, bad payload. A 404 is a real answer: the board is gone."""
    return result["status"] in FAILED or result["status"].startswith("http_")


def write_snapshot(path: Path, snapshot: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(snapshot, separators=(",", ":"), ensure_ascii=False).encode()
    path.write_bytes(gzip.compress(body, mtime=0))


def has_snapshot_for_month(directory: Path, day: date) -> bool:
    return any(directory.glob(f"{day:%Y-%m}-??.json.gz"))


def ats_client() -> Client:
    return Client(
        user_agent=USER_AGENT,
        min_interval=MIN_INTERVAL,
        max_attempts=MAX_ATTEMPTS,
        timeout=TIMEOUT,
        follow_redirects=True,
    )


def run(
    con,
    args,
    directory: Path = ATS_DIR,
    client: Client | None = None,
    today: date | None = None,
) -> None:
    today = today or datetime.now(UTC).date()
    # The monthly workflow runs on days 1–12; one snapshot per calendar month is enough.
    if has_snapshot_for_month(directory, today):
        print(f"ats: a snapshot for {today:%Y-%m} already exists, skipping")
        return
    hn_months, hn = discover_hn(con)
    panel = load_panel(directory / "panel.json", today)
    boards = plan_boards(hn, panel, load_scopes(directory / "overrides.json"))
    print(
        f"ats: {len(hn)} boards from HN {hn_months}, {len(panel)} panel, {len(boards)} total"
    )
    if args.limit:
        boards = boards[: args.limit]
    if args.dry_run:
        for board in boards:
            print(f"  {board['ats']}/{board['slug']} {board['sources']}")
        return

    client = client or ats_client()
    results = []
    unreachable_run = 0
    for board in boards:
        result = snapshot_board(client, board)
        print(
            f"  {board['ats']}/{board['slug']}: {result['status']} {result.get('total_jobs', '')}"
        )
        results.append(result)
        unreachable_run = (
            unreachable_run + 1 if result["status"] == "unreachable" else 0
        )
        if unreachable_run >= MAX_CONSECUTIVE_UNREACHABLE:
            raise SystemExit(
                f"ats: {unreachable_run} boards in a row unreachable, stopping; nothing written"
            )

    ok = [r for r in results if r["status"] in ("ok", "empty")]
    failed = [r for r in results if is_failed(r)]
    summary = (
        f"{len(ok)} boards fetched, {len(results) - len(ok)} not fetched "
        f"({len(failed)} failed), {sum(r['total_jobs'] for r in ok)} jobs, "
        f"{sum(r['engineering_jobs'] for r in ok)} engineering"
    )
    if args.limit:
        print(f"ats: --limit run, not written: {summary}")
        return
    if results and len(failed) / len(results) > MAX_FAILED_SHARE:
        raise SystemExit(
            f"ats: {len(failed)} of {len(results)} boards failed, over {MAX_FAILED_SHARE:.0%}; "
            "nothing written"
        )
    snapshot = {
        "snapshot_date": today.isoformat(),
        "generated_at": now(),
        "classifier": CLASSIFIER_VERSION,
        "hn_months": hn_months,
        "boards": results,
    }
    path = directory / f"{today.isoformat()}.json.gz"
    write_snapshot(path, snapshot)
    print(f"ats: wrote {path.name}: {summary}")
