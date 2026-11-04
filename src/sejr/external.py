"""Outside benchmarks → data/external/<source>/<YYYY-MM>.json, one value per series per HN month.

Each HN month t gets the value of each outside series as it had been published by t's as-of
date: the hiring thread's created_at + 8 days (UTC date). Contracts are in docs/architecture.md
("External benchmarks").

- Indeed Hiring Lab (CC BY 4.0): the version of the CSV in the hiring-lab GitHub repo at the
  last commit on or before the as-of date. Git history is the vintage record.
- BLS (public domain): the BLS API v2 while the as-of date is today or later, otherwise the
  ALFRED vintage in effect on the as-of date. Only the one value per month is stored.
"""

import argparse
import csv
import io
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import duckdb
import httpx

from sejr.config import EXTERNAL_CACHE_DIR, EXTERNAL_DIR, FIRST_MONTH
from sejr.fetch import Client, now

AS_OF_DAYS = 8
WINDOW_DAYS = 7
# The Hiring Lab job postings repo starts 2020-05-04; no month before can have a vintage.
INDEED_FIRST_MONTH = "2020-05"
# A daily reading older than this at the window end means the file stopped updating. The
# postings tracker updates weekly; the remote tracker monthly, with data to the previous month end.
MAX_DAILY_LAG = {"postings": timedelta(days=31), "remote": timedelta(days=75)}
MAX_MONTHLY_LAG = 6
# Normal runs refresh only the newest months; more than this is a backfill.
MAX_UNSCOPED_MONTHS = 3
# ALFRED and GitHub are free services; one request a second is plenty for a one-off backfill.
BACKFILL_INTERVAL = 1.0

BLS_API = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
ALFRED_CSV = "https://alfred.stlouisfed.org/graph/alfredgraph.csv"
GITHUB = "https://github.com/hiring-lab"
RAW_GITHUB = "https://raw.githubusercontent.com/hiring-lab"

INDEED = "Indeed Hiring Lab"
BLS = "U.S. Bureau of Labor Statistics"
SEC = "SEC EDGAR"
CC_BY = ("CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/")
PUBLIC_DOMAIN = ("public domain", "https://www.bls.gov/opub/copyright-information.htm")
# "Information presented on sec.gov is considered public information and may be copied or
# further distributed ... without the SEC's permission."
SEC_PUBLIC = (
    "public domain",
    "https://www.sec.gov/about/privacy-information#dissemination",
)
PUBLISHERS = {
    "indeed": (INDEED, CC_BY),
    "bls": (BLS, PUBLIC_DOMAIN),
    "sec": (SEC, SEC_PUBLIC),
}
FIRST_PUBLISHED = (
    "Each month shows the value as first published by that month's as-of date; later "
    "revisions are not applied."
)
# Every BLS series here has ALFRED vintages from before the first HN month (checked
# 2026-11-04). A 404 for a vintage before this date means "no value yet"; after it, an error.
BLS_FIRST_VINTAGE = date(2011, 4, 9)
# Hiring Lab files have named the sector both ways, and switched back and forth.
SOFTWARE_SECTOR = {"Software Development", "techsoftware"}


@dataclass(frozen=True)
class Series:
    name: str
    country: str
    source: str  # 'indeed' | 'bls' | 'sec'
    label: str
    unit: str  # 'index' | 'share' | 'thousands' | 'count' | 'usd' | 'change'
    description: str
    credit: str
    repo: str = ""
    path: str = ""
    reader: str = ""  # 'postings' | 'remote' | 'pay'
    seasonally_adjusted: bool = True
    # Drawn as a 12-month trailing average on indexed charts. Only JOLTS: its counts swing with
    # the seasons. Indeed's remote and pay shares are unadjusted too, but their seasonality is
    # minor and smoothing would cost a year of their short history.
    smooth_12m: bool = False
    bls_id: str = ""
    fred_id: str = ""
    source_url: str = ""

    @property
    def key(self) -> str:
        return f"{self.name}.{self.country}"

    @property
    def publisher(self) -> str:
        return PUBLISHERS[self.source][0]

    @property
    def license(self) -> tuple[str, str]:
        return PUBLISHERS[self.source][1]

    @property
    def url(self) -> str:
        if self.source_url:
            return self.source_url
        if self.source == "indeed":
            return f"{GITHUB}/{self.repo}"
        return f"https://data.bls.gov/timeseries/{self.bls_id}"


COUNTRY_NAME = {"US": "US", "GB": "UK"}


def _postings(country: str) -> Series:
    return Series(
        name="indeed_software_postings",
        country=country,
        source="indeed",
        label=f"Indeed {COUNTRY_NAME[country]} software development job postings",
        unit="index",
        description=(
            "Seasonally adjusted Software Development postings on Indeed, 7-day trailing "
            "average, indexed to February 1, 2020 = 100."
        ),
        credit="Indeed Hiring Lab, job postings tracker",
        repo="job_postings_tracker",
        path=f"{country}/job_postings_by_sector_{country}.csv",
        reader="postings",
    )


def _remote(country: str) -> Series:
    return Series(
        name="indeed_software_remote_share",
        country=country,
        source="indeed",
        label=f"Indeed {COUNTRY_NAME[country]} software postings offering remote or hybrid work",
        unit="share",
        description=(
            "Share of Indeed software development postings that mention remote or hybrid "
            "work, 7-day trailing average."
        ),
        credit="Indeed Hiring Lab, remote tracker",
        seasonally_adjusted=False,
        repo="remote-tracker",
        path="remote_postings_sector.csv",
        reader="remote",
    )


def _jolts(name: str, bls_id: str, fred_id: str, label: str) -> Series:
    # FRED carries only the unadjusted (JTU) series for these industries, so the BLS pulls
    # use JTU too and current values and vintages are the same series.
    return Series(
        name=name,
        country="US",
        source="bls",
        label=label,
        unit="thousands",
        description=(
            f"{label}, thousands, not seasonally adjusted. The newest month BLS had "
            "published by the as-of date, usually two months before the HN month."
        ),
        credit="U.S. Bureau of Labor Statistics, JOLTS; vintages via ALFRED",
        seasonally_adjusted=False,
        smooth_12m=True,
        bls_id=bls_id,
        fred_id=fred_id,
    )


SERIES: list[Series] = [
    _postings("US"),
    _postings("GB"),
    _remote("US"),
    _remote("GB"),
    Series(
        name="indeed_software_pay_transparency",
        country="US",
        source="indeed",
        label="Indeed US software postings that state pay",
        unit="share",
        description=(
            "Share of Indeed software development postings with explicit pay, by month "
            "posted. Indeed publishes it for the US only."
        ),
        credit="Indeed Hiring Lab, pay transparency tracker",
        seasonally_adjusted=False,
        repo="pay-transparency",
        path="pay-transparency-sector.csv",
        reader="pay",
    ),
    _jolts("jolts_openings_information", "JTU510000000000000JOL", "JTU5100JOL", "Job openings, information sector"),
    _jolts("jolts_hires_information", "JTU510000000000000HIL", "JTU5100HIL", "Hires, information sector"),
    _jolts("jolts_layoffs_information", "JTU510000000000000LDL", "JTU5100LDL", "Layoffs and discharges, information sector"),
    _jolts("jolts_openings_professional", "JTU540099000000000JOL", "JTU540099JOL", "Job openings, professional and business services"),
    _jolts("jolts_hires_professional", "JTU540099000000000HIL", "JTU540099HIL", "Hires, professional and business services"),
    _jolts("jolts_layoffs_professional", "JTU540099000000000LDL", "JTU540099LDL", "Layoffs and discharges, professional and business services"),
    Series(
        name="ces_computer_systems_design",
        country="US",
        source="bls",
        label="Employment in computer systems design",
        unit="thousands",
        description=(
            "Employees in computer systems design and related services (NAICS 5415), "
            "thousands, seasonally adjusted. The newest month BLS had published by the "
            "as-of date, usually the month before the HN month."
        ),
        credit="U.S. Bureau of Labor Statistics, Current Employment Statistics; vintages via ALFRED",
        bls_id="CES6054150001",
        fred_id="CES6054150001",
    ),
]  # fmt: skip


def _sec(name: str, label: str, unit: str, description: str, credit: str) -> Series:
    return Series(
        name=name,
        country="US",
        source="sec",
        label=label,
        unit=unit,
        description=description,
        credit=f"SEC EDGAR filings; {credit}",
        seasonally_adjusted=False,
        source_url="https://www.sec.gov/search-filings/edgar-application-programming-interfaces",
    )


PANEL = "the SEC panel (about 50 US public tech companies, fixed each January)"
LATE_FILERS = (
    "The same quarter is shown for three HN months, and its value can change between them "
    "as late filers arrive."
)
MATCHED = (
    "Each point lists the companies behind it (CIKs); the set changes from month to month as "
    "10-Ks arrive. Companies whose count moved by more than about a third (a spin-off or a "
    "large acquisition, such as HP's split or eBay without PayPal) are left out, because "
    "their change is not hiring or layoffs."
)
SERIES += [
    _sec(
        "sec_restructuring_usd",
        "Restructuring and other charges, US public tech panel",
        "usd",
        "Restructuring and other charges for one calendar quarter, summed over "
        f"{PANEL}. Each company-year uses the first of these XBRL tags it reported: "
        "RestructuringCharges, SeveranceCosts1, RestructuringAndRelatedCostIncurredCost, "
        "RestructuringSettlementAndImpairmentProvisions, RestructuringCosts, "
        "RestructuringCostsAndAssetImpairmentCharges; some include impairments and other "
        "exit costs. Meta files its charges under its own XBRL element and is left out. n is "
        "the number of companies with a charge; top names the largest and its share of the "
        "total. The quarter is the latest that every company had to file by the as-of date, "
        f"so it trails the HN month by four to six months. {LATE_FILERS}",
        "panel and sums by this report",
    ),
    _sec(
        "sec_restructuring_companies",
        "Panel companies reporting restructuring charges",
        "count",
        "Number of companies in "
        f"{PANEL} that reported a restructuring or similar charge for the quarter (tags as in "
        "sec_restructuring_usd; Meta, which uses its own element, is left out). Sturdier than "
        f"the dollar sum, which one large charge can dominate. n is the number of companies "
        f"counted. {LATE_FILERS}",
        "panel and counts by this report",
    ),
    _sec(
        "sec_item_205_filings_panel",
        "Layoff filings (8-K Item 2.05), US public tech panel",
        "count",
        "8-K filings (not amendments) that report Item 2.05, exit or disposal costs, with an "
        f"EDGAR filing date in the calendar month before the HN month, by {PANEL}; n is the "
        "panel size. Item 2.05 is required only for a committed plan with material costs, so "
        "it rarely captures big tech layoffs: Meta's 11,000 job cuts in November 2022 came "
        "with no Item 2.05 filing.",
        "panel and counts by this report",
    ),
    _sec(
        "sec_item_205_filings_software",
        "Layoff filings (8-K Item 2.05), all software and IT-services filers",
        "count",
        "8-K filings (not amendments) that report Item 2.05, exit or disposal costs, with an "
        "EDGAR filing date in the calendar month before the HN month, by any company whose "
        "filing header carried SIC code 7370-7374 (computer programming, software, systems "
        "design, data processing) when it filed. Item 2.05 rarely captures big tech layoffs "
        "(Meta filed none for its November 2022 cuts).",
        "counts by this report",
    ),
    _sec(
        "sec_headcount_panel",
        "Employees at US public tech panel companies, change over a year",
        "change",
        f"Year-over-year change in employees across {PANEL}, from the employee count in each "
        "company's latest 10-K against its previous 10-K, over the companies that state both; "
        "n is that number of companies. 10-Ks come once a year, so the series moves as each "
        "company files. Amazon has about a third of the panel's employees, mostly warehouse "
        "and delivery staff, so it drives this total; sec_headcount_median_yoy shows the "
        f"typical company. {MATCHED}",
        "counts read from 10-K text and summed by this report",
    ),
    _sec(
        "sec_headcount_median_yoy",
        "Employees at the median US public tech panel company, change over a year",
        "change",
        f"Median company's year-over-year change in employees across {PANEL}, from each "
        "company's latest 10-K against its previous 10-K, over the companies that state both "
        "(the same companies as sec_headcount_panel); n is that number. Unlike the total, no "
        'single company drives it. Many companies round their count ("approximately '
        '19,000") and some repeat it from year to year, so the median can sit at exactly '
        f"zero for months at a time. {MATCHED}",
        "counts read from 10-K text; median by this report",
    ),
    *(
        _sec(
            f"sec_headcount_{key}",
            f"{name} employees",
            "count",
            f"{name}'s employee count at the end of the latest quarter, as stated in its "
            "earnings release (8-K Exhibit 99.1).",
            "count read from the release by this report",
        )
        for key, name in (
            ("meta", "Meta"),
            ("alphabet", "Alphabet"),
            ("amazon", "Amazon"),
        )
    ),
]
SOURCES = ("indeed", "bls")


# ---------- dates ----------


def as_of_date(created_at: datetime) -> date:
    return (created_at.astimezone(UTC) + timedelta(days=AS_OF_DAYS)).date()


def window_end(created_at: datetime) -> date:
    return (created_at.astimezone(UTC) + timedelta(days=WINDOW_DAYS)).date()


def months_between(earlier: str, later: str) -> int:
    (y1, m1), (y2, m2) = (map(int, s.split("-")[:2]) for s in (earlier, later))
    return (y2 - y1) * 12 + (m2 - m1)


# ---------- Indeed: CSV readers ----------

Observations = dict[
    str, list[tuple[str, float]]
]  # country → [(date or month, value)], ascending


def _first(row: dict, *names: str) -> str | None:
    return next((row[n] for n in names if n in row), None)


def warn(message: str) -> None:
    """A GitHub Actions warning annotation; plain text anywhere else."""
    print(f"::warning::{message}", flush=True)


SECTOR_COLUMNS = {
    "postings": ("display_name",),
    "remote": ("normtitlecategory_consistent", "sector"),
    "pay": ("sector",),
}


def read_indeed(reader: str, text: str, label: str = "") -> Observations:
    """Parse one Hiring Lab file into software-development observations per country.

    Column names changed over the years; each reader accepts every variant seen in the repo
    history. A version missing the country column (remote tracker, 2024-11-11) yields nothing.
    """
    out: Observations = {}
    matched = 0
    for row in csv.DictReader(io.StringIO(text)):
        if _first(row, *SECTOR_COLUMNS[reader]) not in SOFTWARE_SECTOR:
            continue
        if reader == "postings":
            if row.get("variable") != "total postings":
                continue
            if "indeed_job_postings_index" in row:
                value = float(row["indeed_job_postings_index"])
            else:  # before mid-2022 the file held the percent change since Feb 1, 2020
                value = 100 + float(row["pct_chng_feb_1"])
            key, value = row["date"], round(value, 2)
        elif reader == "remote":
            key = row["date"]
            value = round(float(row["remote_share_postings"]) / 100, 4)
        else:
            key = row["date"][:7]
            value = round(float(row["pay_transparency_pct"]) / 100, 4)
        matched += 1
        if country := _first(row, "jobcountry", "country_code", "country"):
            out.setdefault(country, []).append((key, value))
    if not matched:
        warn(f"external: no software development rows in {label or reader}")
    for points in out.values():
        points.sort()
    return out


def pick_observation(
    series: Series, points: list[tuple[str, float]], month: str, end: date
) -> tuple[str, float] | None:
    """The reading for HN month `month` from one vintage.

    Daily series (7-day trailing averages): the latest reading on or before the thread's window
    end. When the file reaches the window end, that reading is exactly the mean over the thread's
    7 days. Monthly pay data: the latest month on or before the HN month.
    """
    if series.reader == "pay":
        eligible = [p for p in points if p[0] <= month]
        if eligible and months_between(eligible[-1][0], month) <= MAX_MONTHLY_LAG:
            return eligible[-1]
        return None
    eligible = [p for p in points if p[0] <= end.isoformat()]
    if (
        eligible
        and end - date.fromisoformat(eligible[-1][0]) <= MAX_DAILY_LAG[series.reader]
    ):
        return eligible[-1]
    return None


# ---------- Indeed: vintages from git history ----------


class IndeedRepos:
    """Blobless mirrors of the hiring-lab repos: full commit history, file contents on demand."""

    def __init__(
        self, cache_dir: Path = EXTERNAL_CACHE_DIR, remote: str = GITHUB
    ) -> None:
        self.cache_dir = cache_dir
        self.remote = remote
        self.synced: set[str] = set()
        self.history: dict[tuple[str, str], list[tuple[str, date]]] = {}
        self.parsed: dict[tuple[str, str, str], Observations] = {}

    def _git(self, *args: str) -> str:
        return subprocess.run(
            ["git", *args], check=True, capture_output=True, text=True
        ).stdout

    def _repo_dir(self, repo: str) -> Path:
        path = self.cache_dir / f"{repo}.git"
        if repo not in self.synced:
            if path.exists():
                self._git("-C", str(path), "fetch", "--quiet", "--prune")
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                self._git(
                    "clone", "--quiet", "--mirror", "--filter=blob:none",
                    f"{self.remote}/{repo}.git", str(path),
                )  # fmt: skip
            self.synced.add(repo)
        return path

    def commits(self, repo: str, path: str) -> list[tuple[str, date]]:
        """Commits on the default branch's first-parent line that added or changed `path`,
        newest first, with their UTC commit date.

        Hiring Lab often lands data through pull requests. A branch commit's date is when it
        was written, not when it reached the default branch; the merge commit's date is. So
        only first-parent commits count, and the file is read at that commit.
        """
        if (repo, path) not in self.history:
            out = self._git(
                "-C", str(self._repo_dir(repo)), "log", "--first-parent",
                "--format=%H %ct", "--diff-filter=AM", "HEAD", "--", path,
            )  # fmt: skip
            self.history[(repo, path)] = [
                (sha, datetime.fromtimestamp(int(ts), UTC).date())
                for sha, ts in (line.split() for line in out.splitlines())
            ]
        return self.history[(repo, path)]

    def text(self, repo: str, sha: str, path: str) -> str:
        return self._git(
            "-C", str(self._repo_dir(repo)), "cat-file", "blob", f"{sha}:{path}"
        )

    def observations(self, series: Series, sha: str) -> Observations:
        key = (series.repo, sha, series.path)
        if key not in self.parsed:
            self.parsed[key] = read_indeed(
                series.reader,
                self.text(series.repo, sha, series.path),
                f"{series.repo}@{sha[:7]}:{series.path}",
            )
        return self.parsed[key]


# The 2024-11 remote file had no country column; a couple of older versions cover that gap.
MAX_VERSIONS_TRIED = 5


def indeed_value(
    repos: IndeedRepos, series: Series, month: str, as_of: date, end: date
) -> dict | None:
    """The value of one Indeed series for HN month `month`, from the newest version published
    on or before `as_of` that has a reading for it."""
    published = [
        (sha, d) for sha, d in repos.commits(series.repo, series.path) if d <= as_of
    ]
    for sha, committed in published[:MAX_VERSIONS_TRIED]:
        points = repos.observations(series, sha).get(series.country, [])
        if not points:
            continue
        picked = pick_observation(series, points, month, end)
        if picked is None:
            return None
        ref_period, value = picked
        return {
            "value": value,
            "ref_period": ref_period,
            "vintage_date": committed.isoformat(),
            "source_url": f"{RAW_GITHUB}/{series.repo}/{sha}/{series.path}",
        }
    return None


# ---------- BLS ----------


def bls_latest(client, series: list[Series], year: int, api_key: str | None) -> dict:
    """Newest monthly value per series from the BLS API v2, in one request."""
    body = {
        "seriesid": [s.bls_id for s in series],
        "startyear": str(year - 1),
        "endyear": str(year),
    }
    if api_key:
        body["registrationkey"] = api_key
    payload = client.post(BLS_API, body).json()
    if payload.get("status") != "REQUEST_SUCCEEDED":
        raise RuntimeError(f"BLS API: {payload.get('status')} {payload.get('message')}")
    latest = {}
    for result in payload["Results"]["series"]:
        monthly = [
            (f"{d['year']}-{d['period'][1:]}", float(d["value"]))
            for d in result["data"]
            if d["period"].startswith("M")
            and d["period"] != "M13"
            and d["value"] != "-"
        ]
        if monthly:
            latest[result["seriesID"]] = max(monthly)
    return latest


def read_alfred(text: str) -> tuple[str, float] | None:
    """The last observation of an ALFRED vintage CSV ('.' marks a missing value)."""
    rows = [
        r
        for r in csv.reader(io.StringIO(text))
        if len(r) == 2 and r[1] not in (".", "")
    ]
    if len(rows) < 2:
        return None
    observed, value = rows[-1]
    return observed[:7], float(value)


def alfred_value(client, series: Series, as_of: date) -> tuple[str, float] | None:
    try:
        response = client.get(
            ALFRED_CSV, {"id": series.fred_id, "vintage_date": as_of.isoformat()}
        )
    except httpx.HTTPStatusError as e:
        # ALFRED answers 404 for a vintage date before the series existed. Any other 404
        # is a broken id or URL, and must not pass as "no value".
        if e.response.status_code == 404 and as_of < BLS_FIRST_VINTAGE:
            return None
        raise
    return read_alfred(response.text)


def bls_values(client, as_of: date, today: date, api_key: str | None) -> dict:
    series = [s for s in SERIES if s.source == "bls"]
    values = {}
    if today <= as_of:
        latest = bls_latest(client, series, as_of.year, api_key)
        for s in series:
            if s.bls_id in latest:
                ref_period, value = latest[s.bls_id]
                values[s.key] = {
                    "value": value,
                    "ref_period": ref_period,
                    "vintage_date": today.isoformat(),
                    "source_url": s.url,
                }
        return values
    for s in series:
        picked = alfred_value(client, s, as_of)
        if picked:
            values[s.key] = {
                "value": picked[1],
                "ref_period": picked[0],
                "vintage_date": as_of.isoformat(),
                "source_url": (
                    f"{ALFRED_CSV}?id={s.fred_id}&vintage_date={as_of.isoformat()}"
                ),
            }
    return values


# ---------- storage ----------


def month_path(source: str, month: str, directory: Path = EXTERNAL_DIR) -> Path:
    return directory / source / f"{month}.json"


def load(source: str, month: str, directory: Path = EXTERNAL_DIR) -> dict | None:
    path = month_path(source, month, directory)
    return json.loads(path.read_text()) if path.exists() else None


def is_frozen(stored: dict | None) -> bool:
    """A month pulled after its as-of date is final: later releases can never reach it.

    A month still missing an expected series stays open, so the next run retries it. ALFRED
    at vintage = as-of date returns the same answer whenever it is asked, so a retry is safe.
    """
    if stored is None or stored.get("missing"):
        return False
    return date.fromisoformat(stored["fetched_at"][:10]) > date.fromisoformat(
        stored["as_of"]
    )


def save(source: str, month: str, as_of: date, values: dict, fetched_at: str,
         directory: Path = EXTERNAL_DIR, missing: list[str] | None = None) -> str:  # fmt: skip
    """Write unless nothing changed. A pull that would freeze the month is always written."""
    stored = load(source, month, directory)
    record = {
        "month": month,
        "as_of": as_of.isoformat(),
        "fetched_at": fetched_at,
        "values": values,
    }
    if missing:
        record["missing"] = missing
    if stored and stored["values"] == values and not is_frozen(record):
        return "unchanged"
    path = month_path(source, month, directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return "saved"


# ---------- the step ----------


def hiring_threads(con: duckdb.DuckDBPyConnection) -> dict[str, datetime]:
    return {
        month.strftime("%Y-%m"): created_at
        for month, created_at in con.execute(
            "SELECT month, created_at FROM threads WHERE kind = 'hiring' ORDER BY month"
        ).fetchall()
    }


def plan(
    threads: dict[str, datetime], directory: Path = EXTERNAL_DIR
) -> list[tuple[str, str]]:
    """(source, month) pairs not yet frozen, oldest first."""
    first = {"indeed": INDEED_FIRST_MONTH, "bls": FIRST_MONTH}
    return [
        (source, month)
        for month in threads
        for source in SOURCES
        if month >= first[source] and not is_frozen(load(source, month, directory))
    ]


def pull(source: str, month: str, created_at: datetime, *, client, repos: IndeedRepos,
         today: date, api_key: str | None) -> dict:  # fmt: skip
    as_of = as_of_date(created_at)
    if source == "bls":
        return bls_values(client, as_of, today, api_key)
    end = window_end(created_at)
    values = {}
    for s in SERIES:
        if s.source == "indeed" and (v := indeed_value(repos, s, month, as_of, end)):
            values[s.key] = v
    return values


def run(con: duckdb.DuckDBPyConnection, args: argparse.Namespace) -> None:
    threads = hiring_threads(con)
    if args.month:
        threads = {m: c for m, c in threads.items() if m == args.month}
    todo = plan(threads)
    if args.limit:
        todo = todo[: args.limit]
    # A month already past its as-of date that is open only because a series is missing is a
    # retry, not a backfill; a series gone for good must not block everything else.
    retries = {(src, m) for src, m in todo if is_retry(load(src, m))}
    if len({m for pair in todo if pair not in retries for m in pair[1:]}) > (
        MAX_UNSCOPED_MONTHS
    ) and not (args.backfill or args.month):
        raise SystemExit(
            f"external: {len(todo)} month pulls needed ({todo[0][1]} to {todo[-1][1]}); "
            "run `sejr external --backfill`"
        )
    print(f"external: {len(todo)} month pulls")
    if args.dry_run:
        for source, month in todo:
            print(
                f"  {month} {source}: would pull (as of {as_of_date(threads[month])})"
            )
        return
    client = Client(min_interval=BACKFILL_INTERVAL)
    repos = IndeedRepos()
    api_key = os.environ.get("BLS_API_KEY") or None
    failed: set[str] = set()
    for source, month in todo:
        if source in failed:
            continue
        created_at = threads[month]
        fetched_at = now()
        try:
            values = pull(
                source, month, created_at, client=client, repos=repos,
                today=date.fromisoformat(fetched_at[:10]), api_key=api_key,
            )  # fmt: skip
        except Exception as e:  # noqa: BLE001
            # An outside source being down must not block the HN refresh. The month stays
            # unfrozen and the next run tries again.
            warn(f"external: {source} failed at {month}, skipping it this run: {e!r}")
            failed.add(source)
            continue
        missing = expected_missing(source, as_of_date(created_at), values)
        for key in missing:
            warn(f"external: {month} has no {key} yet; the month stays open")
        for key in dropped(source, month, values):
            warn(f"external: {key} had a value last month but none in {month}")
        status = save(
            source, month, as_of_date(created_at), values, fetched_at, missing=missing
        )
        print(f"  {month} {source}: {len(values)} values, {status}", flush=True)


def is_retry(stored: dict | None) -> bool:
    """Pulled after its as-of date but still missing a series."""
    return bool(stored and stored.get("missing")) and date.fromisoformat(
        stored["fetched_at"][:10]
    ) > date.fromisoformat(stored["as_of"])


def expected_missing(source: str, as_of: date, values: dict) -> list[str]:
    """BLS series that should have a value but don't. Indeed gaps come from git history and
    can't change on a retry, so they are warned about (see `dropped`) but never block."""
    if source != "bls" or as_of < BLS_FIRST_VINTAGE:
        return []
    return sorted(s.key for s in SERIES if s.source == "bls" and s.key not in values)


def previous_month(month: str) -> str:
    year, m = map(int, month.split("-"))
    return f"{year - 1}-12" if m == 1 else f"{year}-{m - 1:02d}"


def dropped(
    source: str, month: str, values: dict, directory: Path = EXTERNAL_DIR
) -> list[str]:
    before = load(source, previous_month(month), directory)
    return sorted(set(before["values"]) - set(values)) if before else []


# ---------- export ----------


def build_section(months: list[str], directory: Path = EXTERNAL_DIR) -> dict:
    """The `external` section of metrics.json for the given (complete) months."""
    section = {}
    stored = {
        (source, month): load(source, month, directory)
        for source in {s.source for s in SERIES}
        for month in months
    }
    for s in SERIES:
        points = []
        for month in months:
            record = stored[(s.source, month)]
            entry = record and record["values"].get(s.key)
            # Defensive: a value published after the month's as-of date never reaches the site.
            if not entry or entry["vintage_date"] > record["as_of"]:
                continue
            # Everything stored except the fetch URL; SEC points add n, top and companies.
            point = {"month": month} | {
                k: v for k, v in entry.items() if k != "source_url"
            }
            points.append(point)
        section[s.key] = {
            "id": s.key,
            "label": s.label,
            "country": s.country,
            "publisher": s.publisher,
            "credit": s.credit,
            "license": s.license[0],
            "license_url": s.license[1],
            "unit": s.unit,
            "seasonally_adjusted": s.seasonally_adjusted,
            "smooth_12m": s.smooth_12m,
            "description": f"{s.description} {FIRST_PUBLISHED}",
            "source_url": s.url,
            "series": points,
        }
    return section
