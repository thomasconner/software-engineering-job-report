import gzip
import json
from argparse import Namespace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from sejr import ats
from sejr.db import connect
from sejr.fetch import GaveUp

TODAY = date(2026, 11, 4)

FIXTURES = Path(__file__).parent / "fixtures" / "ats"


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text())


class FakeClient:
    """Serves recorded board responses by URL; anything else is a 404, as the real APIs do."""

    def __init__(self, responses: dict[str, object]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict | None]] = []

    def get(self, url: str, params: dict | None = None):
        self.calls.append((url, params))
        payload = self.responses.get(url)
        if isinstance(payload, Exception):
            raise payload
        request = httpx.Request("GET", url, params=params)
        if payload is None:
            httpx.Response(404, request=request).raise_for_status()
        if callable(payload):
            payload = payload(params)
        return httpx.Response(200, json=payload, request=request)


def test_extract_slugs_from_post_text():
    text = (
        "Acme | Backend | REMOTE\n\nApply: https://jobs.ashbyhq.com/Acme-Labs/0269aeaa-8d8f-4c8d"
        " or https://job-boards.greenhouse.io/oklo/jobs/6123408004.\n"
        "More at https://boards.greenhouse.io/embed/job_app?token=123&for=relativity and "
        "https://boards.greenhouse.io/embed/job_board?for=Coast\n"
        '<script src="https://boards.greenhouse.io/embed/job_board/js?for=mattermost"></script>\n'
        "Lever: (https://jobs.lever.co/shieldai/e74514eb-0abd-4bae...) "
        "Ashby root: jobs.ashbyhq.com/footprint. and jobs.ashbyhq.com/somana.tech/b3b7\n"
        "SmartRecruiters: https://jobs.smartrecruiters.com/ServiceNow/744000159668209 and "
        "https://careers.smartrecruiters.com/WesternDigital\n"
        "Not boards: https://www.ashbyhq.com/customers https://greenhouse.io/ https://lever.co"
    )
    assert ats.extract_slugs(text) == {
        ("ashby", "acme-labs"),
        ("ashby", "footprint"),
        ("ashby", "somana.tech"),
        ("greenhouse", "oklo"),
        ("greenhouse", "relativity"),
        ("greenhouse", "coast"),
        ("greenhouse", "mattermost"),
        ("lever", "shieldai"),
        ("smartrecruiters", "ServiceNow"),
        ("smartrecruiters", "WesternDigital"),
    }


def _thread(con, thread_id, month, complete=True, kind="hiring"):
    created = datetime.fromisoformat(f"{month}-01T15:00:00+00:00")
    snapshot = created + timedelta(days=7)
    fetched = snapshot + timedelta(days=1 if complete else -4)
    con.execute(
        "INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
        [thread_id, kind, f"{month}-01", "t", created, snapshot, fetched],
    )


def _post(con, post_id, thread_id, text, in_snapshot=True):
    con.execute(
        "INSERT INTO posts VALUES (?, ?, 'a', ?, '', ?, ?)",
        [post_id, thread_id, datetime(2026, 1, 1, tzinfo=UTC), text, in_snapshot],
    )


def test_discover_hn_uses_latest_complete_months_and_snapshot_posts(tmp_path):
    con = connect(tmp_path / "db.duckdb")
    for thread_id, month in enumerate(["2026-06", "2026-07", "2026-08", "2026-09"], 1):
        _thread(con, thread_id, month)
    _thread(con, 5, "2026-10", complete=False)
    _thread(con, 6, "2026-09", kind="seeking")
    _post(con, 10, 1, "https://jobs.lever.co/tooold")  # outside the 3-month window
    _post(con, 11, 2, "https://jobs.ashbyhq.com/acme")
    _post(con, 12, 4, "https://jobs.ashbyhq.com/Acme/123 https://jobs.lever.co/beta")
    _post(con, 13, 4, "https://jobs.lever.co/late", in_snapshot=False)
    _post(con, 14, 5, "https://jobs.lever.co/pending")
    _post(con, 15, 6, "https://jobs.lever.co/seeker")

    months, boards = ats.discover_hn(con)

    # The selected thread months, even 2026-08, which links no board.
    assert months == ["2026-07", "2026-08", "2026-09"]
    assert boards == {
        ("ashby", "acme"): {
            "ats": "ashby",
            "slug": "acme",
            "sources": ["hn:2026-07", "hn:2026-09"],
        },
        ("lever", "beta"): {"ats": "lever", "slug": "beta", "sources": ["hn:2026-09"]},
    }


def test_plan_boards_merges_panel_and_skips_removed(tmp_path):
    panel_path = tmp_path / "panel.json"
    panel_path.write_text(
        json.dumps(
            {
                "boards": [
                    {"ats": "lever", "slug": "beta", "added": "2026-11-04"},
                    {"ats": "greenhouse", "slug": "stripe", "added": "2026-11-04"},
                    {"ats": "lever", "slug": "gone", "added": "2026-01-01",
                     "removed": "2026-11-04"},
                    {"ats": "lever", "slug": "later", "added": "2026-12-01"},
                ]
            }
        )
    )  # fmt: skip
    hn = {
        ("lever", "beta"): {"ats": "lever", "slug": "beta", "sources": ["hn:2026-09"]}
    }
    overrides = tmp_path / "overrides.json"
    overrides.write_text(json.dumps({"scope": {"Lever/Beta": "portfolio"}}))
    boards = ats.plan_boards(
        hn, ats.load_panel(panel_path, TODAY), ats.load_scopes(overrides)
    )
    assert [(b["ats"], b["slug"], b["sources"], b["scope"]) for b in boards] == [
        ("greenhouse", "stripe", ["panel"], "company"),
        ("lever", "beta", ["hn:2026-09", "panel"], "portfolio"),
    ]
    assert ats.load_scopes(tmp_path / "missing.json") == {}
    on_dec_1 = [b["slug"] for b in ats.load_panel(panel_path, date(2026, 12, 1))]
    on_nov_3 = [b["slug"] for b in ats.load_panel(panel_path, date(2026, 11, 3))]
    assert on_dec_1 == ["beta", "stripe", "later"]
    assert on_nov_3 == ["gone"]
    assert hn[("lever", "beta")]["sources"] == ["hn:2026-09"]


def test_parse_greenhouse_departments_with_parent_path():
    jobs = ats.parse_greenhouse(fixture("greenhouse_departments.json"))
    by_title = {j["title"]: j for j in jobs}
    assert len(jobs) == 8
    senior = by_title["Senior Software Engineer"]
    assert senior["department"] == "Engineering > Software Engineering"
    assert senior["location"] == "Santa Clara, CA or Remote"
    assert senior["workplace"] == "remote"
    assert senior["published"] and senior["updated"]
    assert set(senior) == {
        "id", "title", "department", "location", "workplace", "published", "updated",
    }  # fmt: skip
    assert "workplace" not in by_title["Open Call for Engineers"]  # location "Any"
    assert by_title["Cost Accountant"]["workplace"] == "remote"  # "Distributed"
    assert by_title["Cost Accountant"]["department"] == "Finance"


def test_parse_greenhouse_keeps_a_job_in_two_departments_once_under_the_deeper():
    payload = fixture("greenhouse_departments.json")
    ids = [j["id"] for d in payload["departments"] for j in d["jobs"]]
    assert ids.count(4018702004) == 2
    jobs = [j for j in ats.parse_greenhouse(payload) if j["id"] == "4018702004"]
    assert [j["department"] for j in jobs] == ["Engineering > Software Engineering"]
    payload["departments"].reverse()
    jobs = [j for j in ats.parse_greenhouse(payload) if j["id"] == "4018702004"]
    assert [j["department"] for j in jobs] == ["Engineering > Software Engineering"]


def test_parse_ashby_workplace_prefers_workplace_type_over_is_remote():
    jobs = ats.parse_ashby(fixture("ashby_job_board.json"))
    assert [
        (j["title"], j["department"], j["team"], j.get("workplace")) for j in jobs
    ] == [
        ("Software Engineer, Agents", "R&D", "Engineering", "remote"),
        ("Security Engineer, Infrastructure Security", "R&D", "Trust", "remote"),
        ("Senior Brand Designer", "R&D", "Design", "remote"),
        # Ashby sets isRemote for hybrid jobs; workplaceType says what they are.
        ("Backend Engineer, Billing", "R&D", "Engineering", "hybrid"),
        ("Office Manager", "G&A", "Workplace", "onsite"),
        # No workplaceType or isRemote: the location text decides.
        ("Account Executive", "Sales", "Sales", "remote"),
    ]
    assert jobs[0]["published"] == "2026-08-11T00:18:10.574+00:00"
    assert jobs[0]["location"] == "North America"


def test_parse_lever():
    jobs = ats.parse_lever(fixture("lever_postings.json"))
    assert [(j["title"], j["department"], j.get("workplace")) for j in jobs] == [
        ("Medical Assistant", "Clinical", "remote"),
        ("Senior Software Engineer, Agentic AI", "AI", "remote"),
        ("Senior Software Engineer, Full-Stack", "Engineering", "remote"),
        ("Senior Software Engineer, Full-Stack", "Engineering", "onsite"),
        ("Senior Software Engineer, Full-Stack", "Engineering", None),
    ]
    assert jobs[1]["team"] == "AI/ML Engineering"
    assert jobs[0]["published"].startswith("2026-")


def test_parse_smartrecruiters():
    jobs = ats.parse_smartrecruiters([fixture("smartrecruiters_postings.json")])
    assert [(j["title"], j["workplace"]) for j in jobs] == [
        ("Scientist 2, Data Science", "onsite"),
        ("Internship - Software Development (Embedded)", "onsite"),
        ("Scientist 1, Data Science", "hybrid"),
    ]
    assert jobs[1]["location"] == "Petaling Jaya, Selangor, Malaysia"


@pytest.mark.parametrize(
    ("location", "expected"),
    [
        ("Remote - Distributed", "remote"),
        ("Distributed", "remote"),
        ("New York (Hybrid) or Remote", "remote"),
        ("San Francisco, CA - Hybrid", "hybrid"),
        ("Onsite - Austin", "onsite"),
        ("San Francisco, CA", None),
        (None, None),
    ],
)
def test_workplace_from_text(location, expected):
    assert ats.workplace_from_text(location) == expected


def test_smartrecruiters_pages_until_total_found(monkeypatch):
    monkeypatch.setattr(ats, "SMARTRECRUITERS_PAGE", 2)
    full = fixture("smartrecruiters_postings.json")

    def page(params):
        start = params["offset"]
        return full | {"content": full["content"][start : start + params["limit"]]}

    url = ats.API["smartrecruiters"].format(slug="WesternDigital")
    client = FakeClient({url: page})
    jobs = ats.fetch_board(client, "smartrecruiters", "WesternDigital")
    assert len(jobs) == 3
    assert [params["offset"] for _, params in client.calls] == [0, 2]


def test_snapshot_board_records_failures():
    broken = ats.API["lever"].format(slug="broken")
    flaky = ats.API["lever"].format(slug="flaky")
    client = FakeClient(
        {
            broken: httpx.ConnectError("refused"),
            flaky: GaveUp("giving up after 2 attempts", transport=False),
        }
    )
    missing = ats.snapshot_board(
        client, {"ats": "ashby", "slug": "gone", "sources": []}
    )
    unreachable = ats.snapshot_board(
        client, {"ats": "lever", "slug": "broken", "sources": []}
    )
    error = ats.snapshot_board(client, {"ats": "lever", "slug": "flaky", "sources": []})
    assert missing["status"] == "not_found"
    assert "jobs" not in missing
    assert unreachable["status"] == "unreachable"
    assert unreachable["error"].startswith("ConnectError")
    assert error["status"] == "error"
    assert not ats.is_failed(missing)
    assert ats.is_failed(unreachable) and ats.is_failed(error)
    assert ats.is_failed({"status": "http_503"}) and not ats.is_failed(
        {"status": "http_403"}
    )


def _setup_run(tmp_path, posts: str, panel: list[dict]):
    con = connect(tmp_path / "db.duckdb")
    _thread(con, 1, "2026-10")
    _post(con, 10, 1, posts)
    out = tmp_path / "ats"
    out.mkdir()
    (out / "panel.json").write_text(json.dumps({"boards": panel}))
    return con, out


ARGS = Namespace(limit=None, dry_run=False)


def test_run_writes_compact_snapshot_without_job_text(tmp_path):
    con, out = _setup_run(
        tmp_path,
        "https://jobs.ashbyhq.com/livekit/1757f49e and https://jobs.lever.co/gone",
        [{"ats": "lever", "slug": "curai", "added": "2026-11-04"}],
    )
    raw_ashby = fixture("ashby_job_board.json")
    raw_ashby["jobs"][0]["descriptionPlain"] = "SECRET JOB TEXT"
    client = FakeClient(
        {
            ats.API["ashby"].format(slug="livekit"): raw_ashby,
            ats.API["lever"].format(slug="curai"): fixture("lever_postings.json"),
        }
    )

    ats.run(con, ARGS, directory=out, client=client, today=TODAY)

    [path] = out.glob("*.json.gz")
    assert path.name == "2026-11-04.json.gz"
    raw = gzip.decompress(path.read_bytes())
    assert b"SECRET JOB TEXT" not in raw
    snapshot = json.loads(raw)
    assert snapshot["snapshot_date"] == "2026-11-04"
    assert snapshot["hn_months"] == ["2026-10"]
    assert snapshot["classifier"] == ats.CLASSIFIER_VERSION
    boards = {(b["ats"], b["slug"]): b for b in snapshot["boards"]}
    livekit = boards[("ashby", "livekit")]
    assert livekit["sources"] == ["hn:2026-10"]
    assert (livekit["status"], livekit["total_jobs"], livekit["engineering_jobs"]) == (
        "ok",
        6,
        3,
    )
    assert livekit["workplace_jobs"] == {
        "remote": 4,
        "hybrid": 1,
        "onsite": 1,
        "unknown": 0,
    }
    assert set(livekit) == {
        "ats", "slug", "sources", "scope", "fetched_at", "status", "total_jobs",
        "engineering_jobs", "workplace_jobs", "jobs",
    }  # fmt: skip
    allowed = {
        "id",
        "title",
        "department",
        "team",
        "location",
        "workplace",
        "published",
        "updated",
    }
    assert all(
        set(job) <= allowed for b in boards.values() for job in b.get("jobs", [])
    )
    curai = boards[("lever", "curai")]
    assert curai["engineering_jobs"] == 4
    assert curai["workplace_jobs"] == {
        "remote": 3,
        "hybrid": 0,
        "onsite": 1,
        "unknown": 1,
    }
    assert boards[("lever", "gone")]["status"] == "not_found"

    # A second run in the same month leaves the snapshot alone.
    client.calls.clear()
    ats.run(con, ARGS, directory=out, client=client, today=TODAY)
    assert client.calls == []


def test_limit_run_fetches_but_never_writes(tmp_path):
    con, out = _setup_run(tmp_path, "https://jobs.lever.co/curai", [])
    client = FakeClient(
        {ats.API["lever"].format(slug="curai"): fixture("lever_postings.json")}
    )
    ats.run(
        con,
        Namespace(limit=1, dry_run=False),
        directory=out,
        client=client,
        today=TODAY,
    )
    assert len(client.calls) == 1
    assert list(out.glob("*.json.gz")) == []


def test_run_writes_nothing_when_too_many_boards_fail(tmp_path):
    # 2 of 5 boards fail (40% > 20%); the 404 doesn't count as a failure.
    con, out = _setup_run(
        tmp_path, " ".join(f"https://jobs.lever.co/b{i}" for i in range(5)), []
    )
    ok = fixture("lever_postings.json")
    request = httpx.Request("GET", "https://api.lever.co")
    client = FakeClient(
        {
            ats.API["lever"].format(slug="b0"): ok,
            ats.API["lever"].format(slug="b1"): ok,
            ats.API["lever"].format(slug="b2"): httpx.HTTPStatusError(
                "503", request=request, response=httpx.Response(503, request=request)
            ),
            ats.API["lever"].format(slug="b3"): httpx.ReadTimeout("slow"),
        }
    )
    with pytest.raises(SystemExit, match="2 of 5 boards failed"):
        ats.run(con, ARGS, directory=out, client=client, today=TODAY)
    assert list(out.glob("*.json.gz")) == []


def test_run_stops_after_consecutive_unreachable_boards(tmp_path, monkeypatch):
    monkeypatch.setattr(ats, "MAX_CONSECUTIVE_UNREACHABLE", 3)
    con, out = _setup_run(
        tmp_path, " ".join(f"https://jobs.lever.co/b{i}" for i in range(6)), []
    )
    client = FakeClient(
        {
            ats.API["lever"].format(slug=f"b{i}"): httpx.ConnectError("down")
            for i in range(6)
        }
    )
    with pytest.raises(SystemExit, match="3 boards in a row unreachable"):
        ats.run(con, ARGS, directory=out, client=client, today=TODAY)
    assert len(client.calls) == 3
    assert list(out.glob("*.json.gz")) == []


def test_panel_file_is_valid():
    panel = json.loads((ats.ATS_DIR / "panel.json").read_text())["boards"]
    keys = [ats.board_key(b["ats"], b["slug"]) for b in panel]
    assert len(keys) == len(set(keys))
    assert all(b["ats"] in ats.API and b["added"] and b["company"] for b in panel)


@pytest.mark.parametrize(
    ("title", "department", "expected"),
    [
        ("Senior Software Engineer, Sales Platform", None, True),
        ("Engineering Manager, Payments", None, True),
        ("Technical Recruiter, Engineering", "People", False),
        ("Solutions Engineer", "Sales", False),
        ("Mechanical Engineer - Fuel Recycling", "Engineering", False),
        ("Engineer II", "Engineering > Platform", True),
        ("Engineer II", "Manufacturing", False),
        ("Data Scientist", "Data", False),
        ("Member of Technical Staff", None, True),
        ("Product Manager, Developer Platform", "Product", False),
        ("Research Engineer, Customer Data", None, True),
        ("Site Reliability Engineer, Support Tooling", None, True),
        ("Fuel Systems Engineer", "Engineering", False),
        ("IT Systems Engineer", None, False),
        ("Financial Systems Engineer", None, False),
        ("Business Systems Engineer", None, False),
        ("Distributed Systems Engineer", None, True),
        ("Technical Customer Support Engineer", "Engineering", False),
        ("Curriculum Developer", None, False),
        ("Senior Backend Engineer | Accounting", "Engineering", True),
    ],
)
def test_is_engineering_rules(title, department, expected):
    assert ats.is_engineering(title, department) is expected


def test_engineering_classifier_accuracy_on_labeled_titles():
    """150 titles from the first snapshot (2026-11-04), labeled by hand before tuning.
    The rule scored 0.967 untuned, 0.98 after adding GTM to the customer-facing words, and
    0.98 again with eng-2's review fixes."""
    lines = (FIXTURES / "engineering_labels.jsonl").read_text().splitlines()
    rows = [json.loads(line) for line in lines]
    correct = sum(
        ats.is_engineering(r["title"], r["department"]) == r["engineering"]
        for r in rows
    )
    assert len(rows) == 150
    assert correct / len(rows) >= 0.95


@pytest.mark.parametrize(
    ("location", "expected"),
    [
        ("San Francisco, CA", True),
        ("Remote U.S.", True),
        ("New York, NY or Remote", True),
        ("Remote (US)", True),
        ("Remote - US or Canada", True),
        ("Remote - TX", True),
        ("Remote; NY", True),
        ("Austin (TX)", True),
        ("Remote - Phoenix", True),
        ("Remote - Seattle", True),
        ("London, UK", False),
        ("Remote - Canada", False),
        ("Canada - Remote (ON, AB, BC, or NS Only)", False),
        ("Toronto, ON, CA", False),
        ("Bengaluru, India", False),
        ("LONDON OR PARIS", False),
        ("Remote, Global", None),
        ("North America", None),
        ("N/A", None),
        (None, None),
    ],
)
def test_is_us_location(location, expected):
    assert ats.is_us_location(location) is expected


def test_us_jobs_counts_by_location():
    jobs = [{"location": loc} for loc in ["London, UK", "Austin, TX", "Remote", "N/A"]]
    assert ats.us_jobs(jobs + [{}]) == {"us": 1, "non_us": 1, "unknown": 3}
