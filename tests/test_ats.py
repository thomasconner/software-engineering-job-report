import gzip
import json
from argparse import Namespace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from sejr import ats
from sejr.db import connect

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

    boards = ats.discover_hn(con)

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
                    {"ats": "lever", "slug": "gone", "added": "2026-11-04",
                     "removed": "2026-12-01"},
                ]
            }
        )
    )  # fmt: skip
    hn = {
        ("lever", "beta"): {"ats": "lever", "slug": "beta", "sources": ["hn:2026-09"]}
    }
    boards = ats.plan_boards(hn, ats.load_panel(panel_path))
    assert [(b["ats"], b["slug"], b["sources"]) for b in boards] == [
        ("greenhouse", "stripe", ["panel"]),
        ("lever", "beta", ["hn:2026-09", "panel"]),
    ]
    assert hn[("lever", "beta")]["sources"] == ["hn:2026-09"]


def test_parse_greenhouse_departments_with_parent_path():
    jobs = ats.parse_greenhouse(fixture("greenhouse_departments.json"))
    by_title = {j["title"]: j for j in jobs}
    assert len(jobs) == 8
    senior = by_title["Senior Software Engineer"]
    assert senior["department"] == "Engineering > Software Engineering"
    assert (senior["location"], senior["remote"]) == ("Santa Clara, CA or Remote", True)
    assert senior["published"] and senior["updated"]
    assert set(senior) == {
        "id",
        "title",
        "department",
        "location",
        "remote",
        "published",
        "updated",
    }
    assert by_title["Open Call for Engineers"]["remote"] is False
    assert by_title["Cost Accountant"]["department"] == "Finance"


def test_parse_ashby():
    jobs = ats.parse_ashby(fixture("ashby_job_board.json"))
    assert [(j["title"], j["department"], j["team"], j["remote"]) for j in jobs] == [
        ("Software Engineer, Agents", "R&D", "Engineering", True),
        ("Security Engineer, Infrastructure Security", "R&D", "Trust", True),
        ("Senior Brand Designer", "R&D", "Design", True),
    ]
    assert jobs[0]["published"] == "2026-08-11T00:18:10.574+00:00"
    assert jobs[0]["location"] == "North America"


def test_parse_lever():
    jobs = ats.parse_lever(fixture("lever_postings.json"))
    assert [(j["title"], j["department"], j["team"], j["remote"]) for j in jobs] == [
        ("Medical Assistant", "Clinical", "Medical Assistant", True),
        ("Senior Software Engineer, Agentic AI", "AI", "AI/ML Engineering", True),
        (
            "Senior Software Engineer, Full-Stack",
            "Engineering",
            "Product Engineering",
            True,
        ),
    ]
    assert jobs[0]["published"].startswith("2026-")


def test_parse_smartrecruiters():
    jobs = ats.parse_smartrecruiters([fixture("smartrecruiters_postings.json")])
    assert [(j["title"], j["remote"]) for j in jobs] == [
        ("Scientist 2, Data Science", False),
        ("Internship - Software Development (Embedded)", False),
        ("Scientist 1, Data Science", False),
    ]
    assert jobs[1]["location"] == "Petaling Jaya, Selangor, Malaysia"


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
    client = FakeClient({broken: httpx.ConnectError("refused")})
    missing = ats.snapshot_board(
        client, {"ats": "ashby", "slug": "gone", "sources": []}
    )
    error = ats.snapshot_board(
        client, {"ats": "lever", "slug": "broken", "sources": []}
    )
    assert missing["status"] == "not_found"
    assert "jobs" not in missing
    assert error["status"] == "error"
    assert error["error"].startswith("ConnectError")


def test_run_writes_compact_snapshot_without_job_text(tmp_path):
    con = connect(tmp_path / "db.duckdb")
    _thread(con, 1, "2026-10")
    _post(
        con,
        10,
        1,
        "https://jobs.ashbyhq.com/livekit/1757f49e and https://jobs.lever.co/gone",
    )
    out = tmp_path / "ats"
    out.mkdir()
    (out / "panel.json").write_text(
        json.dumps(
            {"boards": [{"ats": "lever", "slug": "curai", "added": "2026-11-04"}]}
        )
    )
    raw_ashby = fixture("ashby_job_board.json")
    raw_ashby["jobs"][0]["descriptionPlain"] = "SECRET JOB TEXT"
    client = FakeClient(
        {
            ats.API["ashby"].format(slug="livekit"): raw_ashby,
            ats.API["lever"].format(slug="curai"): fixture("lever_postings.json"),
        }
    )
    args = Namespace(limit=None, dry_run=False)

    ats.run(con, args, directory=out, client=client)

    [path] = out.glob("*.json.gz")
    raw = gzip.decompress(path.read_bytes())
    assert b"SECRET JOB TEXT" not in raw
    snapshot = json.loads(raw)
    assert path.name == f"{snapshot['snapshot_date']}.json.gz"
    assert snapshot["hn_months"] == ["2026-10"]
    assert snapshot["classifier"] == ats.CLASSIFIER_VERSION
    boards = {(b["ats"], b["slug"]): b for b in snapshot["boards"]}
    livekit = boards[("ashby", "livekit")]
    assert livekit["sources"] == ["hn:2026-10"]
    assert (livekit["status"], livekit["total_jobs"]) == ("ok", 3)
    assert (livekit["engineering_jobs"], livekit["remote_jobs"]) == (2, 3)
    assert set(livekit) == {
        "ats", "slug", "sources", "fetched_at", "status", "total_jobs",
        "engineering_jobs", "remote_jobs", "jobs",
    }  # fmt: skip
    allowed = {
        "id",
        "title",
        "department",
        "team",
        "location",
        "remote",
        "published",
        "updated",
    }
    assert all(
        set(job) <= allowed for b in boards.values() for job in b.get("jobs", [])
    )
    assert boards[("lever", "curai")]["engineering_jobs"] == 2
    assert boards[("lever", "gone")]["status"] == "not_found"

    # A second run in the same month leaves the snapshot alone.
    client.calls.clear()
    ats.run(con, args, directory=out, client=client)
    assert client.calls == []


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
    ],
)
def test_is_engineering_rules(title, department, expected):
    assert ats.is_engineering(title, department) is expected


def test_engineering_classifier_accuracy_on_labeled_titles():
    """150 titles from the first snapshot (2026-11-04), labeled by hand before tuning.
    The rule scored 0.967 untuned and 0.98 after adding GTM to the customer-facing words."""
    lines = (FIXTURES / "engineering_labels.jsonl").read_text().splitlines()
    rows = [json.loads(line) for line in lines]
    correct = sum(
        ats.is_engineering(r["title"], r["department"]) == r["engineering"]
        for r in rows
    )
    assert len(rows) == 150
    assert correct / len(rows) >= 0.95
