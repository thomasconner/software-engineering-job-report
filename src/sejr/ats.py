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
from sejr.fetch import Client, now

USER_AGENT = "software-engineering-job-report (github.com/thomasconner/software-engineering-job-report)"
MIN_INTERVAL = 1.0
# Boards linked from this many of the latest complete hiring threads. Three months lets a
# later run ask whether a company that posted in month t is still hiring at t+3.
HN_MONTHS = 3
SMARTRECRUITERS_PAGE = 100
# Bumped whenever is_engineering changes; jobs keep title and department, so old
# snapshots can be reclassified.
CLASSIFIER_VERSION = "eng-1"

API = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/departments",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{slug}",
    "lever": "https://api.lever.co/v0/postings/{slug}?mode=json",
    "smartrecruiters": "https://api.smartrecruiters.com/v1/companies/{slug}/postings",
}

# Slugs are the first path segment. Greenhouse embeds name the board in ?for=<slug>.
# EU-hosted Greenhouse and Lever boards use other API hosts and are not matched.
SLUG = r"([A-Za-z0-9][A-Za-z0-9._%-]*)"
LINK_PATTERNS = [
    ("greenhouse", re.compile(r"(?:job-)?boards\.greenhouse\.io/embed/job_(?:app|board)\?(?:[^\s\"'<>]*&)?for=" + SLUG, re.IGNORECASE)),
    ("greenhouse", re.compile(r"(?:job-)?boards\.greenhouse\.io/" + SLUG, re.IGNORECASE)),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/" + SLUG, re.IGNORECASE)),
    ("lever", re.compile(r"jobs\.lever\.co/" + SLUG, re.IGNORECASE)),
    ("smartrecruiters", re.compile(r"(?:jobs|careers)\.smartrecruiters\.com/" + SLUG, re.IGNORECASE)),
]  # fmt: skip
NOT_SLUGS = {"embed", "oneclick-ui", "api", "v1"}


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


def discover_hn(con, months: int = HN_MONTHS) -> dict[tuple[str, str], dict]:
    """Boards linked from in-snapshot posts of the latest complete hiring threads."""
    rows = con.execute(
        """
        WITH recent AS (
          SELECT thread_id, strftime(month, '%Y-%m') AS month FROM threads
          WHERE kind = 'hiring' AND fetched_at >= snapshot_at
          ORDER BY month DESC LIMIT ?
        )
        SELECT r.month, p.text FROM posts p JOIN recent r USING (thread_id)
        WHERE p.in_snapshot ORDER BY r.month, p.post_id
        """,
        [months],
    ).fetchall()
    boards: dict[tuple[str, str], dict] = {}
    for month, text in rows:
        for ats, slug in extract_slugs(text):
            board = boards.setdefault(
                board_key(ats, slug), {"ats": ats, "slug": slug, "sources": []}
            )
            if f"hn:{month}" not in board["sources"]:
                board["sources"].append(f"hn:{month}")
    return boards


def load_panel(path: Path) -> list[dict]:
    """Current panel members; entries keep their history as "added" and "removed" dates."""
    return [b for b in json.loads(path.read_text())["boards"] if not b.get("removed")]


def plan_boards(hn: dict[tuple[str, str], dict], panel: list[dict]) -> list[dict]:
    boards = {key: dict(board) for key, board in hn.items()}
    for entry in panel:
        key = board_key(entry["ats"], entry["slug"])
        board = boards.setdefault(
            key, {"ats": entry["ats"], "slug": entry["slug"], "sources": []}
        )
        board["sources"] = [*board["sources"], "panel"]
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
# The rule reads the title first, the department only when the title is a bare
# "Engineer": 1) other-discipline or customer-facing engineering titles are out;
# 2) non-engineering roles are out; 3) titles that name software work are in; 4) a bare
# engineer/architect title is in unless its department names a non-software function.

NON_SOFTWARE_ENGINEERING = re.compile(
    r"\b(sales|gtm|go[- ]to[- ]market|solutions?|pre-?sales|customer|support|implementation|onboarding|field|"
    r"services?|deployment strategist|data cent(?:er|re)|mechanical|electrical|electronics?|civil|structural|"
    r"chemical|manufacturing|process|industrial|mechatronics?|hardware|rf|analog|asic|fpga|"
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
    r"intern(?:ship)? program)\b",
    re.IGNORECASE,
)
SOFTWARE_TITLE = re.compile(
    r"\b(software|swe|sde|developer|programmer|devops|devsecops|sre|site reliability|"
    r"full[- ]?stack|front[- ]?end|back[- ]?end|mobile|ios|android|web|platform|"
    r"infrastructure|infra|cloud|data|machine learning|ml|ai|llm|security|reliability|"
    r"systems?|distributed|firmware|embedded|api|application|applied|product engineer|"
    r"forward[- ]deployed|founding|research engineer|qa|quality assurance|test automation|"
    r"automation|sdet|database|kernel|compiler|graphics|game|gameplay|rendering|"
    r"analytics engineer|frontier|inference|training|gpu|performance|observability|"
    r"build|release|tooling|developer experience|member of technical staff|"
    r"technical staff|mts|cto|chief technology officer|tech lead|engineering manager|"
    r"(?:head|director|vp|vice president|manager)(?:,| of)? (?:software )?engineering|"
    r"engineering (?:lead|director|head))\b",
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
    r"mobile|ios|android|ml|machine learning|infrastructure|devops|sre)\b",
    re.IGNORECASE,
)
ROLE_OVERRIDE = re.compile(
    r"\b(software engineer\w*|software developer|engineering manager)\b", re.IGNORECASE
)


def is_engineering(title: str, department: str | None = None) -> bool:
    title = title or ""
    if NON_SOFTWARE_ENGINEERING.search(title) and not SOFTWARE_OVERRIDE.search(title):
        return False
    if NON_ENGINEERING_ROLE.search(title) and not ROLE_OVERRIDE.search(title):
        return False
    if SOFTWARE_TITLE.search(title) and GENERIC_ENGINEERING.search(title):
        return True
    if re.search(
        r"\b(developer|programmer|sre|devops|sdet|member of technical staff|"
        r"technical staff|cto|chief technology officer|tech lead)\b",
        title,
        re.IGNORECASE,
    ):
        return True
    if GENERIC_ENGINEERING.search(title):
        return not NON_SOFTWARE_DEPARTMENT.search(department or "")
    return False


def is_engineering_job(job: dict) -> bool:
    """Department and team both describe where a job sits (Ashby: "R&D" / "Engineering")."""
    unit = " > ".join(filter(None, [job.get("department"), job.get("team")]))
    return is_engineering(job["title"], unit)


# --- Parsers: one API response → compact jobs ------------------------------------------


def _text_remote(*values: str | None) -> bool:
    return any(v and re.search(r"\bremote\b", v, re.IGNORECASE) for v in values)


def _job(
    id_,
    title,
    department=None,
    team=None,
    location=None,
    remote=None,
    published=None,
    updated=None,
) -> dict:
    job = {
        "id": str(id_),
        "title": (title or "").strip(),
        "department": department or None,
        "team": team or None,
        "location": location or None,
        "remote": remote,
        "published": published,
        "updated": updated,
    }
    return {k: v for k, v in job.items() if v is not None}


def parse_greenhouse(payload: dict) -> list[dict]:
    """The /departments response lists every job once, under its leaf department (or
    "No Department"). The department is stored with its parents, "Engineering > Platform"."""
    departments = {d["id"]: d for d in payload["departments"]}

    def path(dep: dict) -> str:
        names, seen = [], set()
        while dep and dep["id"] not in seen:
            seen.add(dep["id"])
            names.append(dep["name"])
            dep = departments.get(dep.get("parent_id"))
        return " > ".join(reversed(names))

    jobs = {}
    for dep in payload["departments"]:
        department = None if dep["id"] == 0 else path(dep)
        for j in dep["jobs"]:
            location = (j.get("location") or {}).get("name")
            jobs[j["id"]] = _job(
                j["id"],
                j["title"],
                department=department,
                location=location,
                remote=_text_remote(location),
                published=j.get("first_published"),
                updated=j.get("updated_at"),
            )
    return list(jobs.values())


def parse_ashby(payload: dict) -> list[dict]:
    jobs = []
    for j in payload["jobs"]:
        if j.get("isListed") is False:
            continue
        remote = j.get("isRemote")
        if remote is None:
            remote = j.get("workplaceType") == "Remote" or _text_remote(
                j.get("location")
            )
        jobs.append(
            _job(
                j["id"],
                j["title"],
                department=j.get("department"),
                team=j.get("team"),
                location=j.get("location"),
                remote=bool(remote),
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
        workplace = j.get("workplaceType")
        remote = (
            workplace == "remote"
            if workplace and workplace != "unspecified"
            else _text_remote(location)
        )
        jobs.append(
            _job(
                j["id"],
                j.get("text"),
                department=categories.get("department"),
                team=categories.get("team"),
                location=location,
                remote=remote,
                published=_epoch_ms(j.get("createdAt")),
            )
        )
    return jobs


def parse_smartrecruiters(pages: list[dict]) -> list[dict]:
    jobs = {}
    for page in pages:
        for j in page["content"]:
            location = j.get("location") or {}
            jobs[j["id"]] = _job(
                j["id"],
                j.get("name"),
                department=(j.get("department") or {}).get("label"),
                team=(j.get("function") or {}).get("label"),
                location=location.get("fullLocation") or location.get("city"),
                remote=location.get("remote"),
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
    """Fetch one board. A missing or broken board is recorded with its status, not raised."""
    record = {**board, "fetched_at": now()}
    try:
        jobs = fetch_board(client, board["ats"], board["slug"])
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        return record | {
            "status": "not_found" if code in (404, 410) else f"http_{code}"
        }
    except (httpx.HTTPError, RuntimeError, ValueError, KeyError, TypeError) as e:
        return record | {"status": "error", "error": f"{type(e).__name__}: {e}"[:200]}
    jobs.sort(key=lambda j: j["id"])
    return record | {
        "status": "ok" if jobs else "empty",
        "total_jobs": len(jobs),
        "engineering_jobs": sum(is_engineering_job(j) for j in jobs),
        "remote_jobs": sum(j.get("remote") is True for j in jobs),
        "jobs": jobs,
    }


def write_snapshot(path: Path, snapshot: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(snapshot, separators=(",", ":"), ensure_ascii=False).encode()
    path.write_bytes(gzip.compress(body, mtime=0))


def has_snapshot_for_month(directory: Path, day: date) -> bool:
    return any(directory.glob(f"{day:%Y-%m}-??.json.gz"))


def run(con, args, directory: Path = ATS_DIR, client: Client | None = None) -> None:
    today = datetime.now(UTC).date()
    # The monthly workflow runs on days 1–12; one snapshot per calendar month is enough.
    if has_snapshot_for_month(directory, today):
        print(f"ats: a snapshot for {today:%Y-%m} already exists, skipping")
        return
    hn = discover_hn(con)
    panel = load_panel(directory / "panel.json")
    boards = plan_boards(hn, panel)
    hn_months = sorted({s[3:] for b in hn.values() for s in b["sources"]})
    print(
        f"ats: {len(hn)} boards from HN {hn_months}, {len(panel)} panel, {len(boards)} total"
    )
    if args.limit:
        boards = boards[: args.limit]
    if args.dry_run:
        for board in boards:
            print(f"  {board['ats']}/{board['slug']} {board['sources']}")
        return

    client = client or Client(user_agent=USER_AGENT, min_interval=MIN_INTERVAL)
    results = []
    for board in boards:
        result = snapshot_board(client, board)
        print(
            f"  {board['ats']}/{board['slug']}: {result['status']} {result.get('total_jobs', '')}"
        )
        results.append(result)
    snapshot = {
        "snapshot_date": today.isoformat(),
        "generated_at": now(),
        "classifier": CLASSIFIER_VERSION,
        "hn_months": hn_months,
        "boards": results,
    }
    path = directory / f"{today.isoformat()}.json.gz"
    write_snapshot(path, snapshot)
    ok = [r for r in results if r["status"] in ("ok", "empty")]
    print(
        f"ats: wrote {path.name}: {len(ok)} boards fetched, {len(results) - len(ok)} failed, "
        f"{sum(r['total_jobs'] for r in ok)} jobs, "
        f"{sum(r['engineering_jobs'] for r in ok)} engineering"
    )
