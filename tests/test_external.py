import json
from argparse import Namespace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

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


@pytest.mark.parametrize("day", range(1, 31))
def test_no_indeed_value_has_a_vintage_after_the_as_of_date(day):
    # A new version every three days through October; the thread date moves through the month.
    commits = [(f"c{d}", date(2026, 10, d)) for d in range(30, 0, -3)] + [
        ("c0", date(2026, 9, 25))
    ]
    repos = postings_repos(*commits)
    created = datetime(2026, 9, day, 15, tzinfo=UTC)
    as_of = as_of_date(created)
    value = indeed_value(
        repos, POSTINGS_US, "2026-09", as_of, external.window_end(created)
    )
    if value is not None:
        assert value["vintage_date"] <= as_of.isoformat()
        assert value["ref_period"] <= external.window_end(created).isoformat()


def test_bls_before_the_as_of_date_comes_from_the_api():
    client = FakeClient(bls=fixture("bls_response.json"))
    values = bls_values(client, date(2026, 10, 9), date(2026, 10, 5), None)
    assert [c[0] for c in client.calls] == ["POST"]
    assert values["jolts_openings_information.US"] == {
        "value": 122.0,
        "ref_period": "2026-09",
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
    assert "CC BY 4.0" in postings["credit"]
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
        assert s.credit and s.publisher and s.unit in ("index", "share", "thousands")
    # One BLS API request covers every BLS series (the keyless limit is 25 per request).
    assert sum(s.source == "bls" for s in SERIES) <= 25
    assert timedelta(days=external.AS_OF_DAYS) > timedelta(days=external.WINDOW_DAYS)
