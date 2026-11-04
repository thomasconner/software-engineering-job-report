import json
import os
import subprocess
from argparse import Namespace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from sejr import export, external
from sejr.external import (
    SERIES,
    as_of_date,
    bls_values,
    build_section,
    indeed_value,
    is_frozen,
    load,
    pick_observation,
    read_alfred,
    read_indeed,
    save,
)

FIXTURES = Path(__file__).parent / "fixtures" / "external"
BY_KEY = {s.key: s for s in SERIES}
POSTINGS_US = BY_KEY["indeed_software_postings.US"]
REMOTE_US = BY_KEY["indeed_software_remote_share.US"]
REMOTE_GB = BY_KEY["indeed_software_remote_share.GB"]
PAY_US = BY_KEY["indeed_software_pay_transparency.US"]
# The October 2026 hiring thread: created 2026-10-01 15:02 UTC.
OCT_2026 = datetime(2026, 10, 1, 15, 2, 7, tzinfo=UTC)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


class FakeRepos:
    """IndeedRepos without git: commits and file contents per (repo, path)."""

    def __init__(self, versions: dict[tuple[str, str], list[tuple[str, date, str]]]):
        self.versions = versions  # newest first: (sha, commit date, file text)
        self.read: list[str] = []

    def commits(self, repo, path):
        return [(sha, d) for sha, d, _ in self.versions.get((repo, path), [])]

    def observations(self, series, sha):
        self.read.append(sha)
        text = next(
            t for s, _, t in self.versions[(series.repo, series.path)] if s == sha
        )
        return read_indeed(series.reader, text)


class FakeResponse:
    def __init__(self, text: str):
        self.text = text

    def json(self):
        return json.loads(self.text)


class FakeClient:
    def __init__(self, alfred: dict[str, str] | None = None, bls: str | None = None):
        self.alfred = alfred or {}
        self.bls = bls
        self.calls: list[tuple] = []

    def get(self, url, params=None):
        self.calls.append(("GET", params["id"], params["vintage_date"]))
        return FakeResponse(self.alfred[params["id"]])

    def post(self, url, json):
        self.calls.append(("POST", tuple(json["seriesid"])))
        return FakeResponse(self.bls)


def test_as_of_is_eight_days_after_the_thread():
    assert as_of_date(OCT_2026) == date(2026, 10, 9)
    # A thread posted late in the UTC day still counts from its UTC date.
    assert as_of_date(datetime(2025, 11, 3, 23, 30, tzinfo=UTC)) == date(2025, 11, 11)


def test_reads_both_postings_formats():
    new = read_indeed("postings", fixture("job_postings_by_sector_US.csv"))
    assert list(new) == ["US"]
    assert ("2026-10-02", 78.34) in new["US"]
    # Only "total postings" for Software Development, one reading per day.
    assert len({d for d, _ in new["US"]}) == len(new["US"])
    # The 2021 files held the percent change since Feb 1, 2020; the index is 100 + that.
    old = read_indeed("postings", fixture("job_postings_by_sector_US_2021.csv"))
    assert old["US"][-1] == ("2021-05-21", 130.82)


def test_reads_every_remote_format():
    new = read_indeed("remote", fixture("remote_postings_sector.csv"))
    assert set(new) == {"US", "GB"}
    assert new["US"][-1] == ("2026-09-30", 0.3041)
    old = read_indeed("remote", fixture("remote_postings_sector_2024.csv"))
    assert set(old) == {"US", "GB"}
    assert all(0 < v < 1 for _, v in old["US"])
    assert read_indeed("remote", fixture("remote_postings_sector_nocountry.csv")) == {}


def test_reads_pay_by_month():
    pay = read_indeed("pay", fixture("pay-transparency-sector.csv"))
    assert pay["US"][-1] == ("2026-09", 0.4908)
    assert [m for m, _ in pay["US"]] == ["2026-06", "2026-07", "2026-08", "2026-09"]


def test_daily_reading_is_the_latest_on_or_before_the_window_end():
    points = read_indeed("postings", fixture("job_postings_by_sector_US.csv"))["US"]
    end = date(2026, 10, 8)
    picked = pick_observation(POSTINGS_US, points, "2026-10", end)
    assert picked[0] <= end.isoformat()
    assert picked == max(p for p in points if p[0] <= end.isoformat())
    # A file that stopped updating gives no value rather than a stale one.
    assert pick_observation(POSTINGS_US, points, "2027-01", date(2027, 1, 8)) is None


def test_pay_reading_never_comes_from_a_later_month():
    points = read_indeed("pay", fixture("pay-transparency-sector.csv"))["US"]
    assert pick_observation(PAY_US, points, "2026-08", date(2026, 8, 8))[0] == "2026-08"
    assert pick_observation(PAY_US, points, "2026-05", date(2026, 5, 8)) is None


def postings_repos(*commits: tuple[str, date]) -> FakeRepos:
    text = fixture("job_postings_by_sector_US.csv")
    return FakeRepos(
        {(POSTINGS_US.repo, POSTINGS_US.path): [(s, d, text) for s, d in commits]}
    )


def test_indeed_uses_the_last_version_published_by_the_as_of_date():
    repos = postings_repos(
        ("c3", date(2026, 10, 12)), ("c2", date(2026, 10, 6)), ("c1", date(2026, 9, 29))
    )
    value = indeed_value(
        repos, POSTINGS_US, "2026-10", date(2026, 10, 9), date(2026, 10, 8)
    )
    assert repos.read == ["c2"]
    assert value["vintage_date"] == "2026-10-06"
    assert value["source_url"].endswith(
        "/job_postings_tracker/c2/US/job_postings_by_sector_US.csv"
    )
    assert value["ref_period"] <= "2026-10-08"


def test_indeed_has_no_value_before_its_first_published_version():
    repos = postings_repos(("c1", date(2021, 5, 27)))
    assert (
        indeed_value(
            repos, POSTINGS_US, "2021-05", date(2021, 5, 11), date(2021, 5, 10)
        )
        is None
    )


def test_indeed_skips_a_version_without_the_country():
    repos = FakeRepos(
        {
            (REMOTE_US.repo, REMOTE_US.path): [
                (
                    "bad",
                    date(2024, 11, 11),
                    fixture("remote_postings_sector_nocountry.csv"),
                ),
                ("good", date(2024, 9, 10), fixture("remote_postings_sector_2024.csv")),
            ]
        }
    )
    value = indeed_value(
        repos, REMOTE_GB, "2024-11", date(2024, 11, 12), date(2024, 11, 11)
    )
    # The newest file has no country column, so the September version supplies the value.
    assert value["vintage_date"] == "2024-09-10"
    value = indeed_value(
        repos, REMOTE_GB, "2024-09", date(2024, 9, 11), date(2024, 9, 10)
    )
    assert value["vintage_date"] == "2024-09-10"
    assert value["ref_period"] == "2024-08-31"


def test_no_indeed_value_has_a_vintage_after_the_as_of_date():
    # A new version every three days from Sep 25 through October; the thread date moves
    # through September and October.
    commits = [(f"c{d}", date(2026, 10, d)) for d in range(30, 0, -3)] + [
        ("c0", date(2026, 9, 25))
    ]
    repos = postings_repos(*commits)
    found = []
    for created in (
        datetime(2026, 9, 15, 15, tzinfo=UTC) + timedelta(days=d) for d in range(40)
    ):
        as_of, end = as_of_date(created), external.window_end(created)
        value = indeed_value(repos, POSTINGS_US, f"{created:%Y-%m}", as_of, end)
        if value is None:
            # No value only before the first version (Sep 25) or before its first reading.
            assert min(as_of, end) < date(2026, 9, 25), created
            continue
        found.append(value)
        assert value["vintage_date"] <= as_of.isoformat()
        assert value["ref_period"] <= end.isoformat()
        newest = max(d for _, d in commits if d <= as_of)
        assert value["vintage_date"] == newest.isoformat()
    assert len(found) >= 25


def test_bls_before_the_as_of_date_comes_from_the_api():
    client = FakeClient(bls=fixture("bls_response.json"))
    values = bls_values(client, date(2026, 10, 9), date(2026, 10, 5), None)
    assert [c[0] for c in client.calls] == ["POST"]
    assert values["jolts_openings_information.US"] == {
        "value": 122.0,
        "ref_period": "2026-09",
        # The fixture's short history has no exact comparison months; see the same_vintage tests.
        "compare": {},
        "vintage_date": "2026-10-05",
        "source_url": "https://data.bls.gov/timeseries/JTU510000000000000JOL",
    }
    assert values["ces_computer_systems_design.US"]["value"] == 2355.4


def test_bls_after_the_as_of_date_comes_from_the_alfred_vintage():
    csv = fixture("alfred_JTU5100JOL_2025-10-09.csv")
    bls = [s for s in SERIES if s.source == "bls"]
    client = FakeClient(alfred={s.fred_id: csv for s in bls})
    values = bls_values(client, date(2025, 10, 9), date(2026, 11, 4), None)
    assert {c[2] for c in client.calls} == {"2025-10-09"}
    assert len(client.calls) == len(bls)
    for entry in values.values():
        assert entry["vintage_date"] == "2025-10-09"
        assert entry["ref_period"] == "2025-08"
    assert values["jolts_openings_information.US"]["value"] == 169.0


def test_alfred_missing_values_are_skipped():
    assert read_alfred(
        "observation_date,X_20251009\n2025-07-01,10\n2025-08-01,.\n"
    ) == (
        "2025-07",
        10.0,
    )
    assert read_alfred("observation_date,X_20251009\n") is None


def test_a_month_freezes_once_pulled_after_its_as_of_date(tmp_path):
    values = {
        "x.US": {"value": 1, "ref_period": "2026-09", "vintage_date": "2026-10-05"}
    }
    as_of = date(2026, 10, 9)
    assert (
        save("bls", "2026-10", as_of, values, "2026-10-05T17:00:00Z", tmp_path)
        == "saved"
    )
    assert not is_frozen(load("bls", "2026-10", tmp_path))
    # Same values before the as-of date: nothing to write.
    assert (
        save("bls", "2026-10", as_of, values, "2026-10-06T17:00:00Z", tmp_path)
        == "unchanged"
    )
    # The first pull after the as-of date is written, and freezes the month.
    assert (
        save("bls", "2026-10", as_of, values, "2026-10-10T17:00:00Z", tmp_path)
        == "saved"
    )
    assert is_frozen(load("bls", "2026-10", tmp_path))
    threads = {"2026-10": OCT_2026}
    assert external.plan(threads, tmp_path) == [("indeed", "2026-10")]


def write_month(directory, source, month, as_of, values):
    path = directory / source / f"{month}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "month": month,
        "as_of": as_of,
        "fetched_at": "2026-11-04T00:00:00Z",
        "values": values,
    }
    path.write_text(json.dumps(record))


def test_export_section_shape_and_point_in_time_guard(tmp_path):
    entry = {
        "value": 78.33,
        "ref_period": "2026-10-02",
        "vintage_date": "2026-10-06",
        "source_url": "u",
    }
    late = {
        "value": 99.0,
        "ref_period": "2026-09-01",
        "vintage_date": "2026-09-20",
        "source_url": "u",
    }
    write_month(tmp_path, "indeed", "2026-10", "2026-10-09", {POSTINGS_US.key: entry})
    write_month(tmp_path, "indeed", "2026-09", "2026-09-09", {POSTINGS_US.key: late})
    write_month(tmp_path, "indeed", "2026-11", "2026-11-10", {POSTINGS_US.key: entry})
    section = build_section(["2026-09", "2026-10"], tmp_path)
    assert set(section) == {s.key for s in SERIES}
    postings = section[POSTINGS_US.key]
    assert {k: postings[k] for k in ("id", "country", "publisher", "unit")} == {
        "id": "indeed_software_postings.US",
        "country": "US",
        "publisher": "Indeed Hiring Lab",
        "unit": "index",
    }
    assert postings["license"] == "CC BY 4.0"
    assert postings["license_url"].startswith("https://creativecommons.org/")
    assert postings["seasonally_adjusted"] is True
    assert "revisions are not applied" in postings["description"]
    assert section["jolts_hires_information.US"]["seasonally_adjusted"] is False
    assert section["jolts_hires_information.US"]["smooth_12m"] is True
    # Unadjusted shares are not smoothed: seasonality is minor and their history is short.
    assert section["indeed_software_remote_share.US"]["seasonally_adjusted"] is False
    assert section["indeed_software_remote_share.US"]["smooth_12m"] is False
    # September's value was published after its as-of date, and November isn't a listed month.
    assert postings["series"] == [
        {
            "month": "2026-10",
            "value": 78.33,
            "ref_period": "2026-10-02",
            "vintage_date": "2026-10-06",
        }
    ]
    assert all(s["country"] for s in section.values())
    assert section["jolts_openings_information.US"]["series"] == []


def test_export_build_carries_the_external_section(db, tmp_path):
    data = export.build(db, tmp_path / "validation.json", tmp_path / "external")
    assert set(data["external"]) == {s.key for s in SERIES}
    assert all(not s["series"] for s in data["external"].values())


def test_unscoped_run_refuses_a_backfill(db, monkeypatch, capsys):
    monkeypatch.setattr(external, "load", lambda *args, **kwargs: None)
    args = Namespace(month=None, limit=None, dry_run=True, backfill=False)
    with pytest.raises(SystemExit, match="--backfill"):
        external.run(db, args)
    external.run(db, Namespace(**{**vars(args), "backfill": True}))
    assert "would pull" in capsys.readouterr().out


def test_every_series_names_its_country_and_credit():
    assert {s.country for s in SERIES} == {"US", "GB"}
    assert len({s.key for s in SERIES}) == len(SERIES)
    for s in SERIES:
        assert s.credit and s.publisher
        assert s.unit in ("index", "share", "thousands", "count", "usd", "change")
    # One BLS API request covers every BLS series (the keyless limit is 25 per request).
    assert sum(s.source == "bls" for s in SERIES) <= 25
    assert timedelta(days=external.AS_OF_DAYS) > timedelta(days=external.WINDOW_DAYS)


def git(repo: Path, *args: str, when: str | None = None) -> None:
    env = {
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
        "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
        "PATH": os.environ["PATH"],
    }  # fmt: skip
    if when:
        env |= {"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when}
    subprocess.run(
        ["git", "-C", str(repo), *args], check=True, env=env, capture_output=True
    )


def test_indeed_dates_a_version_by_when_it_reached_the_default_branch(tmp_path):
    """A branch commit written on the 2nd but merged on the 5th counts from the 5th."""
    upstream = tmp_path / "upstream" / "job_postings_tracker.git"
    upstream.mkdir(parents=True)
    git(upstream, "init", "-q", "-b", "main")
    old = fixture("job_postings_by_sector_US_2021.csv")
    new = fixture("job_postings_by_sector_US.csv")
    target = upstream / POSTINGS_US.path
    target.parent.mkdir()
    target.write_text(old)
    git(upstream, "add", ".")
    git(upstream, "commit", "-qm", "old data", when="2026-10-01T12:00:00Z")
    git(upstream, "checkout", "-qb", "update")
    target.write_text(new)
    git(upstream, "commit", "-qam", "new data", when="2026-10-02T12:00:00Z")
    git(upstream, "checkout", "-q", "main")
    git(
        upstream,
        "merge",
        "-q",
        "--no-ff",
        "-m",
        "merge",
        "update",
        when="2026-10-05T12:00:00Z",
    )

    repos = external.IndeedRepos(tmp_path / "cache", remote=f"file://{upstream.parent}")
    commits = repos.commits(POSTINGS_US.repo, POSTINGS_US.path)
    assert [d.isoformat() for _, d in commits] == ["2026-10-05", "2026-10-01"]
    # Before the merge only the old file was on main, and its readings are too stale to use.
    early = indeed_value(
        repos, POSTINGS_US, "2026-10", date(2026, 10, 3), date(2026, 10, 2)
    )
    assert early is None
    merged = indeed_value(
        repos, POSTINGS_US, "2026-10", date(2026, 10, 6), date(2026, 10, 6)
    )
    assert merged["vintage_date"] == "2026-10-05"
    assert merged["ref_period"] == "2026-10-06"


def test_sector_name_variants_and_a_file_without_software_rows(capsys):
    text = (
        "date,jobcountry,sector,remote_share_postings\n2025-03-31,US,techsoftware,30\n"
    )
    text += "2025-03-31,GB,Software Development,40\n"
    assert read_indeed("remote", text) == {
        "US": [("2025-03-31", 0.3)],
        "GB": [("2025-03-31", 0.4)],
    }
    assert capsys.readouterr().out == ""
    assert (
        read_indeed(
            "remote",
            text.replace("techsoftware", "x").replace("Software Development", "y"),
            "f",
        )
        == {}
    )
    assert "::warning::" in capsys.readouterr().out


def test_alfred_404_is_no_value_only_before_the_first_vintage():
    class NotFound:
        def get(self, url, params=None):
            request = httpx.Request("GET", url)
            raise httpx.HTTPStatusError(
                "404", request=request, response=httpx.Response(404, request=request)
            )

    bls = next(s for s in SERIES if s.source == "bls")
    assert external.alfred_value(NotFound(), bls, date(2010, 1, 9)) is None
    with pytest.raises(httpx.HTTPStatusError):
        external.alfred_value(NotFound(), bls, date(2025, 10, 9))


def test_a_month_missing_a_bls_series_stays_open(tmp_path):
    some = {"x.US": {"value": 1, "ref_period": "2025-08", "vintage_date": "2025-10-09"}}
    missing = external.expected_missing("bls", date(2025, 10, 9), some)
    assert len(missing) == sum(s.source == "bls" for s in SERIES)
    save(
        "bls",
        "2025-10",
        date(2025, 10, 9),
        some,
        "2026-11-04T00:00:00Z",
        tmp_path,
        missing,
    )
    assert not is_frozen(load("bls", "2025-10", tmp_path))
    assert external.expected_missing("indeed", date(2025, 10, 9), {}) == []


def test_a_failing_source_warns_and_leaves_the_month_open(
    db, tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(external, "load", lambda *a, **k: None)
    saved = []
    monkeypatch.setattr(
        external, "save", lambda *a, **k: saved.append(a[:2]) or "saved"
    )

    def pull(source, month, *args, **kwargs):
        if source == "bls":
            raise RuntimeError("BLS is down")
        return {}

    monkeypatch.setattr(external, "pull", pull)
    external.run(db, Namespace(month=None, limit=None, dry_run=False, backfill=True))
    out = capsys.readouterr().out
    assert out.count("::warning::external: bls failed") == 1
    assert saved and all(source == "indeed" for source, _ in saved)


def test_a_month_open_only_for_a_missing_series_is_not_a_backfill(
    db, monkeypatch, capsys
):
    retry = {
        "as_of": "2024-01-10",
        "fetched_at": "2026-11-04T00:00:00Z",
        "missing": ["x.US"],
        "values": {},
    }
    monkeypatch.setattr(
        external, "load", lambda source, month, *a: retry if month < "2024-07" else None
    )
    external.run(db, Namespace(month=None, limit=None, dry_run=True, backfill=False))
    assert "would pull" in capsys.readouterr().out


def test_same_vintage_readings_come_from_one_vintage():
    monthly = [
        ("2021-09", 2278.0),
        ("2025-06", 2380.0),
        ("2025-09", 2386.0),
        ("2026-06", 2370.0),
        ("2026-09", 2355.4),
    ]
    assert external.same_vintage(monthly, "2026-09") == {
        "3m": {"ref_period": "2026-06", "value": 2370.0},
        "1y": {"ref_period": "2025-09", "value": 2386.0},
        "5y": {"ref_period": "2021-09", "value": 2278.0},
    }
    # Monthly periods must match exactly: a missing month is left out, never filled.
    assert "1y" not in external.same_vintage(
        [("2025-08", 1.0), ("2026-09", 2.0)], "2026-09"
    )
    # Daily readings: the latest on or before the target day, within a week.
    daily = [("2025-09-30", 63.0), ("2026-07-02", 72.0), ("2026-10-02", 78.3)]
    compare = external.same_vintage(daily, "2026-10-02")
    assert compare["3m"] == {"ref_period": "2026-07-02", "value": 72.0}
    assert compare["1y"] == {"ref_period": "2025-09-30", "value": 63.0}
    assert "5y" not in compare
    assert external.shift_period("2026-05-31", -3) == "2026-02-28"


def test_alfred_value_carries_the_vintage_comparisons():
    rows = "\n".join(
        f"{m}-01,{v}"
        for m, v in [
            ("2021-08", 120),
            ("2025-05", 83),
            ("2025-08", 72),
            ("2026-05", 85),
            ("2026-08", 42),
        ]
    )
    client = FakeClient(alfred={"JTU5100HIL": f"observation_date,X\n{rows}\n"})
    hires = BY_KEY["jolts_hires_information.US"]
    ref, value, compare = external.alfred_value(client, hires, date(2026, 10, 9))
    assert (ref, value) == ("2026-08", 42.0)
    assert compare["1y"] == {"ref_period": "2025-08", "value": 72.0}
    assert compare["5y"] == {"ref_period": "2021-08", "value": 120.0}


def test_add_compare_only_attaches_when_the_value_comes_back_unchanged(
    tmp_path, monkeypatch
):
    stored = {
        "jolts_hires_information.US": {
            "value": 42.0,
            "ref_period": "2026-08",
            "vintage_date": "2026-10-09",
        },
        "jolts_openings_information.US": {
            "value": 128.0,
            "ref_period": "2026-08",
            "vintage_date": "2026-10-09",
        },
    }
    save("bls", "2026-10", date(2026, 10, 9), stored, "2026-11-04T00:00:00Z", tmp_path)
    compare = {"1y": {"ref_period": "2025-08", "value": 72.0}}
    fresh = {
        "jolts_hires_information.US": {
            "value": 42.0,
            "ref_period": "2026-08",
            "compare": compare,
        },
        "jolts_openings_information.US": {
            "value": 130.0,
            "ref_period": "2026-08",
            "compare": {},
        },
    }
    monkeypatch.setattr(external, "pull", lambda *a, **k: fresh)
    external.add_compare(
        {"2026-10": OCT_2026},
        client=None,
        repos=None,
        today=date(2026, 11, 4),
        directory=tmp_path,
    )
    values = load("bls", "2026-10", tmp_path)["values"]
    assert values["jolts_hires_information.US"]["compare"] == compare
    assert values["jolts_hires_information.US"]["value"] == 42.0
    assert "compare" not in values["jolts_openings_information.US"]
