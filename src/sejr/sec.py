"""SEC EDGAR panel of US public tech companies → data/external/sec/, one value per series per HN month.

Every number comes from filings with an EDGAR acceptance timestamp, so month t reads only filings
accepted by its as-of date (the hiring thread's created_at + 8 days, as in external.py). Contracts
are in docs/architecture.md ("SEC EDGAR panel").

- Panel: `panel/<year>.json`, frozen each January from filings accepted before Jan 1.
- Restructuring: XBRL `RestructuringCharges` (else `SeveranceCosts1`) from 10-Q/10-K company facts,
  as first filed, summed over the panel for one calendar quarter.
- Layoff filings: 8-Ks (not amendments) that list Item 2.05, per calendar month, for the panel
  (per-company submissions JSON) and for every SIC 7370-7374 filer (nightly submissions.zip).
- Headcount: the employee count in each panel 10-K (regex over the filed text), and the quarterly
  count in Meta's, Alphabet's and Amazon's earnings releases (8-K Exhibit 99.1).
"""

import argparse
import gzip
import html
import itertools
import json
import math
import os
import re
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import duckdb
import httpx

from sejr.config import EXTERNAL_DIR, ROOT
from sejr.external import (
    MAX_UNSCOPED_MONTHS,
    as_of_date,
    hiring_threads,
    is_frozen,
    load,
    save,
    warn,
)
from sejr.fetch import Client, now

SEC_DIR = EXTERNAL_DIR / "sec"
SEC_CACHE_DIR = ROOT / "data" / "cache" / "sec"
SOURCE = "sec"
# XBRL reaches mid-size filers' 10-Ks in early 2011, so the first panel that can be ranked from
# filed numbers is January 2012's.
SEC_FIRST_MONTH = "2012-01"
# SEC fair access allows 10 requests a second; stay well under it.
MIN_INTERVAL = 0.15
# SEC blocks a client that goes over the limit for about ten minutes, answering 403.
THROTTLE_BACKOFF = 60

DATA = "https://data.sec.gov"
ARCHIVES = "https://www.sec.gov/Archives/edgar/data"
BULK_SUBMISSIONS = (
    "https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip"
)

SOFTWARE_SIC = {"7370", "7371", "7372", "7373", "7374"}
HARDWARE_SIC = {str(c) for c in (*range(3570, 3580), *range(3670, 3680))}
# Which companies compete for the panel by revenue. A scope choice, not a fact: changing
# PANEL_SCOPE and rerunning the backfill rebuilds every panel and month.
# - software_internet_chips (default): software, IT services and data processing (7370-7374)
#   plus chip companies (3674: Nvidia, Intel, AMD, Broadcom, Micron, ...) and Qualcomm, filed
#   under 3663 (radio and TV equipment, otherwise mostly not chips). Leaves out computer
#   hardware, networking gear and contract manufacturing: Apple, Cisco, IBM, Dell and HP are
#   not in this panel.
# - software_internet_hardware: 7370-7374 plus all computer hardware (3570-3579) and
#   electronic components (3670-3679), including contract manufacturers such as Jabil.
SCOPES = {
    "software_internet_chips": {
        "sic": SOFTWARE_SIC | {"3674"},
        "named": {804328: "Qualcomm (SIC 3663)"},
    },
    "software_internet_hardware": {"sic": SOFTWARE_SIC | HARDWARE_SIC, "named": {}},
}
PANEL_SCOPE = "software_internet_chips"
SCOPE_SIC = SCOPES[PANEL_SCOPE]["sic"]

# Editorial exceptions, each made with hindsight about which companies count as tech:
# - NAMED: internet platforms that no SIC rule captures (retail, services, motion pictures),
#   always candidates, plus the scope's own named companies.
# - KNOWN_RECLASSIFIED: companies whose code today is outside the candidate codes but whose
#   filings once carried a software code. Only candidates: the code in their own 10-K
#   decides, as for everyone. Others that left SIC 7370-7374 later are missed.
# - US_DESPITE_ADDRESS: a 10-K filer with a foreign business address but US headquarters.
NAMED = {
    1018724: "Amazon",
    1543151: "Uber",
    1759509: "Lyft",
    1559720: "Airbnb",
    1792789: "DoorDash",
    1633917: "PayPal",
    1065088: "eBay",
    1065280: "Netflix",
} | SCOPES[PANEL_SCOPE]["named"]
KNOWN_RECLASSIFIED = {1011006: "Yahoo (Altaba from 2017)", 1563190: "Compass"}
US_DESPITE_ADDRESS = {1649338: "Broadcom Ltd (Singapore address, 2016-2017)"}
# Business address state, as EDGAR codes it (50 states and DC).
US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID", "IL", "IN",
    "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH",
    "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT",
    "VT", "VA", "WA", "WV", "WI", "WY",
}  # fmt: skip
PANEL_SIZE = 50
# Candidates are cut to this many by the restated revenue in SEC's frames API, then ranked by
# revenue as first filed before the panel's cutoff.
PREFILTER = 120
# A company is alive for a panel when its last 10-K was accepted within this window before Jan 1.
TEN_K_WINDOW = timedelta(days=456)
TEN_K = {"10-K", "10-K405", "10-KT"}
REPORTS = TEN_K | {"10-Q", "10-QT"}
# Form 15 ends a registration (after an acquisition or going private).
DEREGISTRATION = {"15-12B", "15-12G", "15-15D"}
REVENUE_TAGS = (
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "SalesRevenueNet",
    "SalesRevenueGoodsNet",
    "SalesRevenueServicesNet",
)
# In order of preference. Each company-year uses the first tag it reported that year, so tags
# that overlap (severance is part of restructuring) are never added together.
RESTRUCTURING_TAGS = (
    "RestructuringCharges",
    "SeveranceCosts1",
    "RestructuringAndRelatedCostIncurredCost",
    "RestructuringSettlementAndImpairmentProvisions",
    "RestructuringCosts",
    "RestructuringCostsAndAssetImpairmentCharges",
)
# Companies that file their restructuring charges under their own XBRL element, which company
# facts leave out (checked by hand: Meta's 2022-23 charges of $4.6 billion and more carry no
# us-gaap restructuring tag). They are left out of the restructuring series, not read as zero.
CUSTOM_RESTRUCTURING = {1326801: "Meta"}
# Annual-length periods in these tags fix each company's fiscal calendar.
CALENDAR_TAGS = (*REVENUE_TAGS, "NetIncomeLoss", *RESTRUCTURING_TAGS)

# Earnings releases that state headcount (checked by hand, 2026-11-04). Google Inc filed under
# its own CIK until Alphabet replaced it as the registrant in October 2015.
QUARTERLY = {
    "meta": (1326801,),
    "alphabet": (1652044, 1288776),
    "amazon": (1018724,),
}


# ---------- filings ----------


@dataclass(frozen=True)
class Filing:
    accn: str
    form: str
    accepted: datetime
    items: tuple[str, ...] = ()
    primary_doc: str = ""
    report_date: str = ""
    filing_date: str = ""


def parse_accepted(text: str) -> datetime:
    """EDGAR's acceptanceDateTime, which always ends in "Z". In the per-company submissions
    JSON it is UTC (an 8-K accepted 09:15:50 Eastern reads 14:15:50Z). Many records in the
    bulk file carry the Eastern clock time with the same "Z" (21 of 30 Item 2.05 records
    checked against their headers, 2004-2024), and before 2002 only the date was kept, as
    midnight. Only cutoff comparisons use these times, so the error is a few
    hours at the as-of boundary; month counts use filingDate, EDGAR's official date."""
    return datetime.fromisoformat(text).astimezone(UTC)


def read_filings(block: dict, forms: set[str] | None = None) -> list[Filing]:
    """Rows of one columnar `filings` block of a submissions JSON."""
    out = []
    for i, form in enumerate(block["form"]):
        if forms is not None and form not in forms:
            continue
        items = block.get("items", [""] * len(block["form"]))[i] or ""
        out.append(
            Filing(
                accn=block["accessionNumber"][i],
                form=form,
                accepted=parse_accepted(block["acceptanceDateTime"][i]),
                items=tuple(x.strip() for x in items.split(",") if x.strip()),
                primary_doc=block.get("primaryDocument", [""] * len(block["form"]))[i],
                report_date=block.get("reportDate", [""] * len(block["form"]))[i],
                filing_date=block.get("filingDate", [""] * len(block["form"]))[i],
            )
        )
    return out


def cutoff(as_of: date) -> datetime:
    """Filings accepted before this instant were public on the as-of date."""
    return datetime.combine(as_of + timedelta(days=1), time(), UTC)


def is_layoff_8k(filing: Filing) -> bool:
    # Amendments re-file an earlier event, so only original 8-Ks count.
    return filing.form == "8-K" and "2.05" in filing.items


# ---------- EDGAR access with a disk cache ----------


def user_agent() -> str:
    agent = os.environ.get("SEC_USER_AGENT", "").strip()
    if not agent:
        raise SystemExit(
            "sec: SEC_USER_AGENT is not set. SEC requires a User-Agent with a contact "
            'email, for example "Name name@example.com".'
        )
    return agent


def html_text(markup: str) -> str:
    """Visible text of a filing document, whitespace collapsed."""
    markup = re.sub(r"(?is)<(script|style|ix:header)\b.*?</\1>", " ", markup)
    markup = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|li|h\d)>", "\n", markup)
    text = html.unescape(re.sub(r"<[^>]+>", " ", markup))
    text = text.replace("\xa0", " ").replace("\u200b", "")
    return re.sub(r"[ \t\r\f\v]+", " ", re.sub(r"\n\s*", "\n", text)).strip()


class Edgar:
    """EDGAR JSON and documents, cached under data/cache/sec/.

    Filed documents never change, so they are fetched once. Submissions and company facts grow
    with every filing, so a cached copy is reused only when it was fetched after `fresh_after`
    (the newest as-of date the run needs); filtering by acceptance time does the rest.
    """

    def __init__(
        self, client, cache_dir: Path = SEC_CACHE_DIR, fresh_after: date | None = None
    ) -> None:
        self.client = client
        self.cache_dir = cache_dir
        self.fresh_after = fresh_after

    def _fresh(self, path: Path) -> bool:
        if not path.exists():
            return False
        if self.fresh_after is None:
            return True
        fetched = datetime.fromtimestamp(path.stat().st_mtime, UTC).date()
        return fetched > self.fresh_after

    def _json(self, url: str, path: Path, mutable: bool = True) -> dict:
        if not (self._fresh(path) if mutable else path.exists()):
            body = self.client.get(url).content
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(gzip.compress(body, mtime=0))
        return json.loads(gzip.decompress(path.read_bytes()))

    def submissions(self, cik: int) -> tuple[dict, list[Filing]]:
        """Company metadata and every filing, newest first (the recent block plus older pages)."""
        name = f"CIK{cik:010d}.json"
        main = self._json(
            f"{DATA}/submissions/{name}", self.cache_dir / "submissions" / f"{name}.gz"
        )
        filings = read_filings(main["filings"]["recent"])
        for page in main["filings"].get("files", []):
            # Older pages are closed: their filings are all accepted before the recent block.
            older = self._json(
                f"{DATA}/submissions/{page['name']}",
                self.cache_dir / "submissions" / f"{page['name']}.gz",
                mutable=False,
            )
            filings += read_filings(older)
        return main, filings

    def companyfacts(self, cik: int) -> dict:
        name = f"CIK{cik:010d}.json"
        return self._json(
            f"{DATA}/api/xbrl/companyfacts/{name}",
            self.cache_dir / "companyfacts" / f"{name}.gz",
        )

    def frame(self, tag: str, year: int) -> dict:
        url = f"{DATA}/api/xbrl/frames/us-gaap/{tag}/USD/CY{year}.json"
        path = self.cache_dir / "frames" / f"{tag}-CY{year}.json.gz"
        try:
            # Only a pre-filter for the panel ranking, so any cached copy will do.
            return self._json(url, path, mutable=False)
        except httpx.HTTPStatusError as e:
            # No company used the tag that year.
            if e.response.status_code == 404:
                return {"data": []}
            raise

    def document(self, cik: int, accn: str, name: str) -> str:
        """Visible text of one filed document."""
        folder = accn.replace("-", "")
        path = self.cache_dir / "documents" / str(cik) / folder / f"{name}.txt.gz"
        if not path.exists():
            try:
                markup = self.client.get(f"{ARCHIVES}/{cik}/{folder}/{name}").text
            except httpx.HTTPStatusError as e:
                # A listed document that isn't there has no text; one bad link must not
                # block the panel.
                if e.response.status_code != 404:
                    raise
                markup = ""
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(gzip.compress(html_text(markup).encode(), mtime=0))
        return gzip.decompress(path.read_bytes()).decode()

    def exhibit(self, cik: int, accn: str, kind: str = "EX-99.1") -> str | None:
        """File name of an exhibit, from the filing's index page."""
        folder = accn.replace("-", "")
        path = self.cache_dir / "documents" / str(cik) / folder / "index.htm.gz"
        if not path.exists():
            page = self.client.get(f"{ARCHIVES}/{cik}/{folder}/{accn}-index.htm").text
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(gzip.compress(page.encode(), mtime=0))
        return find_exhibit(gzip.decompress(path.read_bytes()).decode(), kind)

    def filing_header(self, cik: int, accn: str) -> dict:
        """SIC code and business state in the filing's own header (`<accn>.hdr.sgml`), as
        they stood when it was filed. Headers exist for every filing; the HTML index-headers
        page does not before about 2014. A missing header is an error, never cached."""
        folder = accn.replace("-", "")
        path = self.cache_dir / "headers" / str(cik) / f"{accn}.json"
        if not path.exists():
            header = self.client.get(f"{ARCHIVES}/{cik}/{folder}/{accn}.hdr.sgml").text
            parsed = parse_header(header, cik)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(parsed))
        return json.loads(path.read_text())

    def filing_sic(self, cik: int, accn: str) -> str:
        return self.filing_header(cik, accn)["sic"]

    def bulk_submissions(self) -> Path:
        path = self.cache_dir / "submissions.zip"
        if not self._fresh(path):
            print("sec: downloading submissions.zip (about 1.6 GB)", flush=True)
            self.client.download(BULK_SUBMISSIONS, path)
        return path


def exhibit_type(text: str) -> str:
    """EX-99.01 and EX-99.1 are the same exhibit; filers write it both ways."""
    return re.sub(r"\.0+(?=\d)", ".", text.strip().upper())


def find_exhibit(index_page: str, kind: str) -> str | None:
    """The document name in the index table row whose Type is `kind` (e.g. EX-99.1)."""
    for row in re.findall(r"(?is)<tr\b.*?</tr>", index_page):
        cells = [
            html.unescape(re.sub(r"<[^>]+>", "", c)).strip()
            for c in re.findall(r"(?is)<td\b.*?</td>", row)
        ]
        link = re.search(r'(?i)href="[^"]*/([^/"]+)"', row)
        if len(cells) >= 4 and exhibit_type(cells[3]) == exhibit_type(kind) and link:
            return link[1]
    return None


# ---------- every filer, from the nightly bulk file ----------

# Every scope's codes, so switching PANEL_SCOPE needs no new scan.
SCAN_SIC = set().union(*(scope["sic"] for scope in SCOPES.values()))
SIC_RE = re.compile(rb'"sic":\s*"(\d*)"')


def filer_record(main: dict, filings: list[Filing]) -> dict:
    return {
        "name": main.get("name", ""),
        "sic": main.get("sic", ""),
        "state": ((main.get("addresses") or {}).get("business") or {}).get(
            "stateOrCountry"
        ),
        "ten_k": sorted(
            [f.accn, f.accepted.isoformat()] for f in filings if f.form in TEN_K
        ),
        "reports": sorted(f.accepted.isoformat() for f in filings if f.form in REPORTS),
        "deregistered": sorted(
            f.accepted.isoformat() for f in filings if f.form in DEREGISTRATION
        ),
    }


def scan_bulk(zip_path: Path, extra_ciks: set[int]) -> dict:
    """Two things from submissions.zip:

    - `filers`: panel candidates (today's SIC in any scope's codes, or a CIK in `extra_ciks`) with
      name, SIC, business state, original 10-Ks, periodic reports and Form 15s. Today's SIC
      only finds candidates; the panel checks the code each 10-K was filed under.
    - `layoffs`: every original 8-K that lists Item 2.05, from any filer, as
      [cik, accession, filingDate, acceptanceDateTime]. The count checks each one's SIC in
      its own filing header.
    """
    filers: dict[int, dict] = {}
    layoffs: list[list] = []
    with zipfile.ZipFile(zip_path) as z:
        names = sorted(n for n in z.namelist() if n.startswith("CIK"))
        pages: dict[int, list[str]] = {}
        for name in names:
            if "-submissions-" in name:
                pages.setdefault(int(name[3:13]), []).append(name)
        for name in names:
            if "-submissions-" in name:
                continue
            body = z.read(name)
            cik = int(name[3:13])
            sic = SIC_RE.search(body[:4000])
            candidate = (sic and sic[1].decode() in SCAN_SIC) or cik in extra_ciks
            older = [z.read(p) for p in pages.get(cik, [])]
            if (
                not candidate
                and b"2.05" not in body
                and not any(b"2.05" in page for page in older)
            ):
                continue
            main = json.loads(body)
            filings = read_filings(main["filings"]["recent"])
            for page in older:
                filings += read_filings(json.loads(page))
            if candidate:
                filers[cik] = filer_record(main, filings)
            layoffs += [
                [cik, f.accn, f.filing_date, f.accepted.isoformat()]
                for f in filings
                if is_layoff_8k(f)
            ]
    return {"filers": filers, "layoffs": sorted(layoffs, key=lambda r: (r[2], r[1]))}


def bulk_index(edgar: Edgar) -> dict:
    """scan_bulk over the cached bulk file, itself cached until the zip changes."""
    zip_path = edgar.bulk_submissions()
    index = zip_path.with_name("bulk_index.json.gz")
    stamp = int(zip_path.stat().st_mtime)
    if index.exists():
        stored = json.loads(gzip.decompress(index.read_bytes()))
        if stored["zip_mtime"] == stamp:
            stored["filers"] = {int(k): v for k, v in stored["filers"].items()}
            return stored
    scanned = scan_bulk(
        zip_path,
        set(NAMED)
        | set(KNOWN_RECLASSIFIED)
        | set(US_DESPITE_ADDRESS)
        | {cik for scope in SCOPES.values() for cik in scope["named"]},
    )
    index.write_bytes(
        gzip.compress(json.dumps({"zip_mtime": stamp, **scanned}).encode(), mtime=0)
    )
    return scanned


def parse_header(header: str, cik: int) -> dict:
    """ASSIGNED-SIC and business-address STATE for `cik` in an EDGAR SGML filing header. A
    filing made for several companies lists each filer; the one asked for wins."""
    blocks = re.split(r"<FILER>", header)[1:] or [header]
    chosen = next(
        (
            b
            for b in blocks
            if (key := re.search(r"<CIK>\s*0*(\d+)", b)) and int(key[1]) == cik
        ),
        blocks[0],
    )
    sic = re.search(r"<ASSIGNED-SIC>\s*(\d+)", chosen)
    business = re.search(
        r"<BUSINESS-ADDRESS>(.*?)</BUSINESS-ADDRESS>", chosen, re.DOTALL
    )
    state = business and re.search(r"<STATE>\s*(\w+)", business[1])
    return {"sic": sic[1] if sic else "", "state": state[1] if state else None}


def header_sic(header: str, cik: int) -> str:
    return parse_header(header, cik)["sic"]


# ---------- XBRL facts ----------


def usd_facts(companyfacts: dict, tag: str) -> list[dict]:
    return (
        companyfacts.get("facts", {})
        .get("us-gaap", {})
        .get(tag, {})
        .get("units", {})
        .get("USD", [])
    )


def days(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days + 1


def first_filed(
    facts: list[dict], accepted: dict[str, datetime], cut: datetime
) -> dict[tuple[str, str], tuple[float, datetime]]:
    """Value per (start, end) from the earliest 10-K/10-Q accepted before `cut` that reported it.

    Later filings repeat a period as a comparative, and amendments or restatements can change
    it; month t keeps the number as it was first filed.
    """
    out: dict[tuple[str, str], tuple[float, datetime]] = {}
    for fact in facts:
        if (
            "start" not in fact
            or fact.get("form", "").removesuffix("/A") not in REPORTS
        ):
            continue
        when = accepted.get(fact["accn"])
        if when is None or when >= cut:
            continue
        key, value = (fact["start"], fact["end"]), float(fact["val"])
        # A few filings tag one period twice (a sign slip in the cash flow statement, say);
        # the larger value is kept.
        if key not in out or (when, -value) < (out[key][1], -out[key][0]):
            out[key] = (value, when)
    return out


def is_quarter(start: str, end: str) -> bool:
    return 80 <= days(start, end) <= 100


def quarters(
    periods: dict[tuple[str, str], tuple[float, datetime]],
) -> dict[tuple[str, str], float]:
    """Three-month values: reported directly, or the difference of two periods that share a
    start (year-to-date figures, such as a 10-K's year less the third quarter's nine months)."""
    out = {k: v for k, (v, _) in periods.items() if is_quarter(*k)}
    by_start: dict[str, list[tuple[str, float]]] = {}
    for (start, end), (value, _) in periods.items():
        by_start.setdefault(start, []).append((end, value))
    for start, ends in by_start.items():
        ends.sort()
        for (end1, v1), (end2, v2) in itertools.pairwise(ends):
            q_start = (date.fromisoformat(end1) + timedelta(days=1)).isoformat()
            if is_quarter(q_start, end2) and (q_start, end2) not in out:
                out[(q_start, end2)] = v2 - v1
    return out


def calendar_quarter(start: str, end: str) -> str:
    """The calendar quarter holding the period's midpoint (SEC frames do the same), so a fiscal
    quarter ending January 31 counts as the fourth quarter."""
    s = date.fromisoformat(start)
    mid = s + (date.fromisoformat(end) - s) / 2
    return f"{mid.year}-Q{(mid.month - 1) // 3 + 1}"


def fiscal_year_key(end: str, fy_ends: list[str]) -> str:
    """The fiscal year a period ending `end` belongs to, named by its year end. Periods after
    the last known year end share an open key."""
    e = date.fromisoformat(end)
    for f in fy_ends:
        gap = (date.fromisoformat(f) - e).days
        if 0 <= gap < 370:
            return f
    return f"after-{fy_ends[-1]}" if fy_ends else end[:4]


def tag_quarters(
    periods: dict[tuple[str, str], tuple[float, datetime]],
    tag_accns: set[str],
    filings: list[Filing],
    cut: datetime,
) -> dict[tuple[str, str], float | None]:
    """Three-month values of one tag, plus a marker for a charge known only for the year.

    Some companies report a restructuring charge only in the 10-K (Salesforce's $828 million
    for the year to January 2023): the three 10-Qs were accepted without the tag. Putting the
    year into the fourth quarter overstates that quarter whenever the charge built up during
    the year (Dell's fiscal 2023), and the split can't be known from the filings. So the
    company counts as having a charge in the year's last quarter (value None) but adds no
    dollars to any quarter.
    """
    out: dict[tuple[str, str], float | None] = dict(quarters(periods))
    for (start, end), (value, _) in periods.items():
        if not value or not 350 <= days(start, end) <= 380:
            continue
        if any(e == end for _, e in out):
            continue
        ten_qs = [
            f
            for f in filings
            if f.form in ("10-Q", "10-QT")
            and f.accepted < cut
            and start < f.report_date < end
        ]
        quarter_ends = sorted({f.report_date for f in ten_qs})
        if len(quarter_ends) != 3 or any(f.accn in tag_accns for f in ten_qs):
            continue
        q4_start = (
            date.fromisoformat(quarter_ends[-1]) + timedelta(days=1)
        ).isoformat()
        if is_quarter(q4_start, end):
            out[(q4_start, end)] = None
    return out


def restructuring_by_quarter(
    company: "Company", cut: datetime
) -> dict[str, float | None]:
    """Calendar quarter → restructuring charge, as first filed before `cut`; None for a
    charge reported only for the full year (see tag_quarters).

    Each fiscal year uses one tag: the first in RESTRUCTURING_TAGS that the company reported
    for that year by `cut`. Mixing tags within a year would add a total to its own part.
    """
    by_tag: dict[str, dict[tuple[str, str], float | None]] = {}
    years_by_tag: dict[str, set[str]] = {}
    for tag in RESTRUCTURING_TAGS:
        facts = company.facts.get(tag, [])
        periods = first_filed(facts, company.accepted, cut)
        if not periods:
            continue
        accns = {f["accn"] for f in facts}
        by_tag[tag] = tag_quarters(periods, accns, company.filings, cut)
        years_by_tag[tag] = {fiscal_year_key(e, company.fy_ends) for _, e in periods}
    out: dict[str, float | None] = {}
    for tag, quarter_values in by_tag.items():
        for (start, end), value in quarter_values.items():
            year = fiscal_year_key(end, company.fy_ends)
            chosen = next(
                (t for t in RESTRUCTURING_TAGS if year in years_by_tag.get(t, ())), tag
            )
            if chosen == tag:
                out.setdefault(calendar_quarter(start, end), value)
    return out


def ref_quarter(month: str) -> str:
    """The quarter reported for HN month t: the latest whose last month is at least four months
    before t. Its 10-Ks and 10-Qs are due 40-90 days after it ends, so by the as-of date (day
    8-10 of t) every panel company has filed it: October reads Q2, January Q3, April Q4."""
    year, m = map(int, month.split("-"))
    m -= 4
    if m <= 0:
        year, m = year - 1, m + 12
    q = m // 3
    if q == 0:
        return f"{year - 1}-Q4"
    return f"{year}-Q{q}"


# Goods and services revenue are parts of the total; they count only when no total is tagged.
COMPONENT_REVENUE_TAGS = {"SalesRevenueGoodsNet", "SalesRevenueServicesNet"}
# A tag more than this many times the next largest is a units slip (Tigo Energy tagged $54
# million of 2024 revenue as $54 billion in one tag); it is dropped.
SCALE_SLIP = 100


def annual_revenue(
    companyfacts: dict, accepted: dict[str, datetime], cut: datetime
) -> tuple[float, str] | None:
    """(revenue, fiscal year end) for the latest fiscal year in a 10-K accepted before `cut`:
    the largest total-revenue tag for that year (goods or services alone only when no total is
    tagged), dropping a value more than SCALE_SLIP times the next largest."""
    by_end: dict[str, dict[str, float]] = {}
    for tag in REVENUE_TAGS:
        for (start, end), (value, _) in first_filed(
            usd_facts(companyfacts, tag), accepted, cut
        ).items():
            if 350 <= days(start, end) <= 380 and value > 0:
                by_end.setdefault(end, {})[tag] = value
    if not by_end:
        return None
    end = max(by_end)
    tags = by_end[end]
    totals = {t: v for t, v in tags.items() if t not in COMPONENT_REVENUE_TAGS}
    values = sorted((totals or tags).values(), reverse=True)
    if len(values) > 1 and values[0] > values[1] * SCALE_SLIP:
        values = values[1:]
    return values[0], end


# ---------- panel ----------


def panel_path(year: int, directory: Path = SEC_DIR) -> Path:
    return directory / "panel" / f"{year}.json"


def eligible(filer: dict, cut: datetime) -> bool:
    """A filer with a 10-K in the year or so before `cut` that had not deregistered by then.
    A Form 15 for one class of securities (notes, say) is followed by more 10-Qs, so only a
    Form 15 after the last periodic report counts. The address test uses the 10-K's own
    header (rank_panel)."""
    if not any(
        cut - TEN_K_WINDOW <= parse_accepted(t) < cut for _, t in filer["ten_k"]
    ):
        return False
    last_report = max(t for t in filer["reports"] if parse_accepted(t) < cut)
    return not any(
        last_report < t and parse_accepted(t) < cut for t in filer["deregistered"]
    )


def in_scope(cik: int, header: dict | None) -> bool:
    """By the code and business state in the company's latest 10-K before the cutoff."""
    if not header:
        return False
    us = header["state"] in US_STATES or cik in US_DESPITE_ADDRESS
    return us and (cik in NAMED or header["sic"] in SCOPE_SIC)


def last_ten_k(filer: dict, cut: datetime) -> str:
    return max((t, accn) for accn, t in filer["ten_k"] if parse_accepted(t) < cut)[1]


def frame_revenue(edgar: Edgar, year: int) -> dict[int, float]:
    out: dict[int, float] = {}
    for tag in REVENUE_TAGS:
        for row in edgar.frame(tag, year).get("data", []):
            out[row["cik"]] = max(out.get(row["cik"], 0.0), float(row["val"]))
    return out


def rank_panel(
    year: int,
    candidates: dict[int, dict],
    revenue: dict[int, tuple[float, str]],
    headers: dict[int, dict],
) -> dict:
    """The top PANEL_SIZE candidates by revenue as first filed before Jan 1 of `year`.
    `headers` holds each candidate's SIC and business state from its latest 10-K."""
    ranked = sorted(
        (c for c in candidates if c in revenue and in_scope(c, headers.get(c))),
        key=lambda c: (-revenue[c][0], c),
    )[:PANEL_SIZE]
    companies = [
        {
            "cik": cik,
            "name": candidates[cik]["name"],
            "sic": headers[cik]["sic"],
            "state": headers[cik]["state"],
            "reason": "named" if cik in NAMED else f"sic_{headers[cik]['sic']}",
            "rank": rank,
            "revenue_usd": revenue[cik][0],
            "revenue_fiscal_year_end": revenue[cik][1],
        }
        for rank, cik in enumerate(ranked, 1)
    ]
    return {
        "year": year,
        "cutoff": f"{year}-01-01T00:00:00Z",
        "scope": PANEL_SCOPE,
        "rule": (
            f"US-based 10-K filers whose latest 10-K before the cutoff was filed under SIC "
            f"{', '.join(sorted(SCOPE_SIC))} (scope {PANEL_SCOPE}), plus {len(NAMED)} named "
            f"companies, with a 10-K accepted in the {TEN_K_WINDOW.days} days before the "
            f"cutoff and no Form 15 since; top {PANEL_SIZE} by annual revenue in the latest "
            "10-K accepted before the cutoff. SIC and state are from that 10-K's header"
        ),
        "companies": companies,
    }


def build_panel(year: int, filers: dict[int, dict], edgar: Edgar) -> dict:
    cut = datetime(year, 1, 1, tzinfo=UTC)
    candidates = {cik: f for cik, f in filers.items() if eligible(f, cut)}
    # The frames API holds the latest restated values, so it only shortlists; the ranking uses
    # each company's revenue as first filed before the cutoff.
    restated = frame_revenue(edgar, year - 2)
    others = sorted(
        (
            c
            for c in candidates
            if c in restated
            and c not in NAMED
            and (
                candidates[c]["sic"] in SCOPE_SIC
                or c in KNOWN_RECLASSIFIED
                or c in US_DESPITE_ADDRESS
            )
        ),
        key=lambda c: -restated[c],
    )
    shortlist = [c for c in candidates if c in NAMED] + others[:PREFILTER]
    revenue, headers = {}, {}
    for cik in shortlist:
        accepted = {accn: parse_accepted(t) for accn, t in candidates[cik]["ten_k"]}
        picked = annual_revenue(edgar.companyfacts(cik), accepted, cut)
        if picked:
            revenue[cik] = picked
            headers[cik] = edgar.filing_header(cik, last_ten_k(candidates[cik], cut))
    return rank_panel(year, candidates, revenue, headers)


def load_panel(year: int, directory: Path = SEC_DIR) -> dict | None:
    path = panel_path(year, directory)
    return json.loads(path.read_text()) if path.exists() else None


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")


# ---------- headcount ----------

NUMBER = r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)"
SCALE = {"thousand": 1_000, "million": 1_000_000}
# "had approximately 8,800 regular, full-time employees", "employed more than 130,000 people",
# "employed: 29,187 employees".
LEAD = (
    r"\b(?:had|employed|employ|employs|have|has|employing|of|was|were|totaled|totaling|"
    r"comprised|consisted of|consists of|approximately|our|by|with)[:\s]+"
)
NOUN = (
    r"(?:(?:full[- ]time[- ]equivalent|full[- ]time|part[- ]time|full|regular|permanent|"
    r"total|global|worldwide|active|temporary|and|or)[,\s]+)*"
    r"(?:employees|people|persons|individuals|associates|team members|staff|personnel|professionals|"
    r"full[- ]time[- ]equivalents|FTEs|Googlers|workers)\b"
)
STATED = re.compile(
    LEAD + r"(?:a total of\s+|a (?:global )?workforce of\s+)?"
    r"(?:approximately|about|around|roughly|over|more than|nearly|almost|some)?\s*"
    + NUMBER
    + r"(\s+(?:thousand|million))?\s+"
    + NOUN,
    re.IGNORECASE,
)
# "we had a total of 58,824, 41,168, and 36,739 employees, respectively": the first is newest.
STATED_LIST = re.compile(
    LEAD
    + r"(?:a total of\s+)?"
    + NUMBER
    + r"()(?:,\s+[\d,]+)*,?\s+and\s+[\d,]+\s+"
    + NOUN,
    re.IGNORECASE,
)
# "we employed 9,060 full-time and 240 part-time employees": the full-time count.
FULL_AND_PART = re.compile(
    LEAD
    + r"(?:approximately\s+)?"
    + NUMBER
    + r"()\s+full[- ]time(?:\s+employees)?\s+and\s+(?:approximately\s+)?[\d,]+\s+part[- ]time\s+"
    + NOUN,
    re.IGNORECASE,
)
# "Headcount was 86,482 as of December 31, 2022".
HEADCOUNT_WAS = re.compile(
    r"\bheadcount (?:was|of|totaled|includes)\s+(?:approximately\s+)?" + NUMBER + r"()",
    re.IGNORECASE,
)
# "Our global workforce of 102,700 is highly educated".
WORKFORCE = re.compile(
    r"\bworkforce (?:of|was|totaled)\s+(?:approximately|about|over|more than|nearly)?\s*"
    + NUMBER
    + r"(\s+(?:thousand|million))?",
    re.IGNORECASE,
)
# A table: "Employees are summarized as follows ... Total 73,700".
TABLE = re.compile(
    r"\b(?:employees are summarized|number of employees|employees by)\b.{0,400}?"
    r"\bTotal\s+((?:\d{1,3}(?:,\d{3})+\s*){1,3})",
    re.IGNORECASE | re.DOTALL,
)
# The same, said by the words right after the count ("engaged in research", "in the Asia
# Pacific region").
NOT_TOTAL_AFTER = re.compile(
    r"^\s*(?:(?:who|that) (?:are|were) )?(?:engaged in|located in (?:the )?(?-i:[A-Z])|"
    r"in the [\w ]{1,30}region|"
    r"impacted|affected|who will|were on|who (?:exited|departed|left)|in (?:the )?(?-i:[A-Z]))|"
    r"^\W*(?:or|representing) [^.]{0,20}%|"
    # A department: "403 employees and 4 engineering consultants dedicated to research".
    r"^\s*(?:and \d[\d,]* [a-z ]{0,30}?)?(?:dedicated to|devoted to|engaged in|in) "
    r"(?:research|sales|engineering|"
    r"product development|marketing|manufacturing|operations|customer|technical support)",
    re.IGNORECASE,
)
EMPLOYEE_WORDS = re.compile(
    r"employ|workforce|headcount|team|personnel|associates|people|persons|staff",
    re.IGNORECASE,
)
# The company's own count is stated at a date ("As of December 31, 2025, we had ...").
AT_DATE = re.compile(
    r"\b(?:as of|at)\s+(?:the\s+)?(?:end of\s+)?(?:(?:our\s+)?fiscal\s+(?:year\s+)?)?"
    r"(?:[a-z]+\.?\s+\d{1,2}\s*,\s*)?(?:19|20)\d\d\b|\bend of (?:fiscal )?(?:19|20)\d\d\b",
    re.IGNORECASE,
)
# A number about part of the company, a change, or someone else.
NOT_TOTAL = re.compile(
    r"restructur|reduc|impact|terminat|severance|eliminat|layoff|increase|decrease|added|"
    r"exited|departed|affected|"
    r"sales and marketing|research and development|engineering|located|seasonal|contract|"
    r"overseeing|oversaw|led an|served as|prior to|services to|serving|serves|users|"
    r"subscribers|members|"
    r"outside|international|in india|in the region|customer|client|organizations|"
    r"businesses|fewer than|up to|union|bargaining|acquisition|joined",
    re.IGNORECASE,
)


def sentences(text: str) -> list[str]:
    """Sentences, with line breaks inside a sentence (common in older filings) joined."""
    text = re.sub(r"\n(?=[a-z0-9(])", " ", text)
    return [
        s.strip() for s in re.split(r"(?<=[.;:])\s+(?=[A-Z(•])|\n+", text) if s.strip()
    ]


def _number(digits: str, scale: str | None) -> float:
    value = float(digits.replace(",", ""))
    return value * SCALE[scale.strip().lower()] if scale else value


PART_ONLY = re.compile(r"part[- ]time|temporary", re.IGNORECASE)
MIN_SCORE = 1


def headcount(text: str) -> tuple[int, str] | None:
    """The company's employee count and the sentence that states it, from 10-K text.

    Many sentences in a 10-K pair a number with "employees": the sales team, a layoff, the
    staff in one country, a customer's size. Each candidate is scored: +2 when the count is
    stated at a date, +1 for "we had/employed" or "our workforce", -5 when the words around the number say it is
    a part (part-time staff, one country, one function), a change (a layoff, growth) or
    someone else's (customers, a director's past employer). The best score wins, then the
    earliest. A sentence needs a score of at least 1 (a date or "we had"): a bare "We have
    9,639 employees working in game development" is not the company total. Without one, a
    table row ("Total 73,700" under "Employees are summarized") is used, and failing that
    there is no count.
    """
    best: tuple[int, int, int, str] | None = None  # (score, -order, value, sentence)
    order = 0
    for sentence in sentences(text):
        if not EMPLOYEE_WORDS.search(sentence):
            continue
        for pattern in (FULL_AND_PART, STATED_LIST, STATED, HEADCOUNT_WAS, WORKFORCE):
            match = pattern.search(sentence)
            if not match:
                continue
            value = _number(match[1], match[2])
            if value < 100:
                continue
            # The clause around the number, not the whole sentence: "We serve clients ... through
            # our 120,000 employees" is the company's own count.
            before = sentence[max(0, match.start() - 80) : match.end()]
            # "We had ..." or "Our workforce consists of ..." names the whole company.
            score = 2 * bool(AT_DATE.search(sentence)) + bool(
                re.search(
                    r"\b(?:we|company|\w+) (?:had|employed|employs|has)\b|"
                    r"\b(?:our|total) (?:global )?workforce\b",
                    before,
                    re.IGNORECASE,
                )
            )
            # Part-time or temporary staff on their own are not the headline count.
            part_only = (
                pattern is not FULL_AND_PART
                and PART_ONLY.search(match[0])
                and "full" not in match[0].lower()
            )
            if (
                part_only
                or NOT_TOTAL.search(before)
                or NOT_TOTAL_AFTER.search(sentence[match.end() :])
            ):
                score -= 5
            order += 1
            candidate = (score, -order, round(value), sentence)
            if best is None or candidate[:2] > best[:2]:
                best = candidate
            break
    if best is not None and best[0] >= MIN_SCORE:
        return best[2], best[3]
    if table := TABLE.search(text):
        # A geography table ends with the total column.
        total = table[1].split()[-1]
        return int(total.replace(",", "")), table.group(0)[-300:]
    return None


COLUMNS = r"((?:\d{1,3}(?:,\d{3})+\s*)+)"
# Each pattern captures the count, or a table row whose last column is the newest quarter.
EX99_RES = {
    "meta": [re.compile(r"Headcount (?:was|of) " + NUMBER, re.IGNORECASE)],
    "alphabet": [
        re.compile(r"Number of employees\s+(?:\(\d\)\s+)?" + COLUMNS, re.IGNORECASE),
        re.compile(r"Headcount\s+" + COLUMNS),
        re.compile(r"employed (?:approximately )?" + NUMBER + r" full-time employees"),
    ],
    "amazon": [
        re.compile(r"Employees \(full-time and part-time[^)]*\)\s+" + COLUMNS),
    ],
}


def ex99_headcount(company: str, text: str) -> int | None:
    """Headcount stated in an earnings release (8-K Exhibit 99.1)."""
    for pattern in EX99_RES[company]:
        if match := pattern.search(text):
            return int(match[1].split()[-1].replace(",", ""))
    return None


# ---------- per-company data ----------

HEADCOUNT_PATH = SEC_DIR / "headcount.json"
# Earliest filings read for headcount: the 2012 panel's year-over-year change needs 10-Ks
# from 2010.
HEADCOUNT_FROM = datetime(2010, 1, 1, tzinfo=UTC)
# A release older than this at the as-of date means the company stopped stating headcount.
QUARTERLY_MAX_AGE = timedelta(days=200)


@dataclass
class Company:
    cik: int
    filings: list[Filing]
    accepted: dict[str, datetime]
    facts: dict[str, list[dict]]
    fy_ends: list[str] = field(default_factory=list)
    name: str = ""


def fiscal_year_ends(companyfacts: dict) -> list[str]:
    return sorted(
        {
            f["end"]
            for tag in CALENDAR_TAGS
            for f in usd_facts(companyfacts, tag)
            if "start" in f and 350 <= days(f["start"], f["end"]) <= 380
        }
    )


def load_company(edgar: Edgar, cik: int, name: str = "") -> Company:
    _, filings = edgar.submissions(cik)
    facts = edgar.companyfacts(cik)
    return Company(
        cik=cik,
        filings=filings,
        accepted={f.accn: f.accepted for f in filings},
        facts={tag: usd_facts(facts, tag) for tag in RESTRUCTURING_TAGS},
        fy_ends=fiscal_year_ends(facts),
        name=name or NAMED.get(cik, ""),
    )


def quarter_end_before(day: date) -> date:
    """The last day of the calendar quarter that ended before `day`."""
    first = date(day.year, 3 * ((day.month - 1) // 3) + 1, 1)
    return first - timedelta(days=1)


class Headcounts:
    """Employee counts read from filings, keyed by accession number, in data/external/sec/.

    Stored so a monthly run reads only new filings. A filing with no count stores null, so it
    isn't read again. Changing the regex means deleting this file and the month files.
    """

    def __init__(self, path: Path = HEADCOUNT_PATH) -> None:
        self.path = path
        self.rows: dict[str, dict] = (
            json.loads(path.read_text()) if path.exists() else {}
        )

    def save(self) -> None:
        save_json(self.path, self.rows)

    def annual(self, edgar: Edgar, company: Company) -> None:
        added = False
        for f in company.filings:
            if (
                f.form not in TEN_K
                or f.accepted < HEADCOUNT_FROM
                or f.accn in self.rows
            ):
                continue
            found = headcount(edgar.document(company.cik, f.accn, f.primary_doc))
            self.rows[f.accn] = {
                "cik": company.cik,
                "kind": "10-K",
                "accepted": f.accepted.isoformat(),
                "period": f.report_date,
                "value": found[0] if found else None,
            }
            added = True
        if added:
            self.save()

    def quarterly(self, edgar: Edgar, key: str, company: Company) -> None:
        added = False
        for f in company.filings:
            if f.form != "8-K" or "2.02" not in f.items or f.accepted < HEADCOUNT_FROM:
                continue
            if f.accn in self.rows:
                continue
            name = edgar.exhibit(company.cik, f.accn)
            value = (
                ex99_headcount(key, edgar.document(company.cik, f.accn, name))
                if name
                else None
            )
            self.rows[f.accn] = {
                "cik": company.cik,
                "kind": f"ex99:{key}",
                "accepted": f.accepted.isoformat(),
                "period": quarter_end_before(f.accepted.date()).isoformat(),
                "value": value,
            }
            added = True
        if added:
            self.save()

    def rows_for(self, cik: int, kind: str, cut: datetime) -> list[dict]:
        """Rows with a value, accepted before `cut`, newest first."""
        rows = [
            r
            for r in self.rows.values()
            if r["cik"] == cik
            and r["kind"] == kind
            and r["value"] is not None
            and parse_accepted(r["accepted"]) < cut
        ]
        return sorted(rows, key=lambda r: r["accepted"], reverse=True)


# ---------- one HN month ----------


def previous_month(month: str) -> str:
    year, m = map(int, month.split("-"))
    return f"{year - 1}-12" if m == 1 else f"{year}-{m - 1:02d}"


def entry(
    value, ref_period: str, as_of: date, source_url: str, n: int | None = None
) -> dict:
    out = {
        "value": value,
        "ref_period": ref_period,
        "vintage_date": as_of.isoformat(),
        "source_url": source_url,
    }
    if n is not None:
        out["n"] = n
    return out


def restructuring_values(
    month: str, as_of: date, companies: list[Company]
) -> dict[str, dict]:
    """The panel's restructuring dollars and the number of companies with a charge, for the
    reference quarter. Companies with their own restructuring element are left out of both.
    A charge known only for the full year counts in the year's last quarter but adds no
    dollars (`annual_only` lists those companies)."""
    cut, quarter = cutoff(as_of), ref_quarter(month)
    counted = [c for c in companies if c.cik not in CUSTOM_RESTRUCTURING]
    charges, annual_only = [], []
    for c in counted:
        by_quarter = restructuring_by_quarter(c, cut)
        if quarter not in by_quarter:
            continue
        value = by_quarter[quarter]
        if value is None:
            annual_only.append(c.cik)
        elif value:
            charges.append((value, c))
    total = sum(v for v, _ in charges)
    source = f"{DATA}/api/xbrl/companyfacts/"
    dollars = entry(round(total), quarter, as_of, source, len(charges))
    dollars["annual_only"] = sorted(annual_only)
    if charges and total > 0:
        value, top = max(charges, key=lambda x: (x[0], -x[1].cik))
        dollars["top"] = {
            "cik": top.cik,
            "name": top.name,
            "share": round(value / total, 4),
        }
    return {
        RESTRUCTURING_KEY: dollars,
        RESTRUCTURING_COUNT_KEY: entry(
            len(charges) + len(annual_only), quarter, as_of, source, len(counted)
        ),
    }


def panel_layoff_value(month: str, as_of: date, companies: list[Company]) -> dict:
    cut, ref = cutoff(as_of), previous_month(month)
    count = sum(
        1
        for c in companies
        for f in c.filings
        if is_layoff_8k(f) and f.filing_date[:7] == ref and f.accepted < cut
    )
    return entry(count, ref, as_of, f"{DATA}/submissions/", len(companies))


def software_layoff_value(month: str, as_of: date, layoffs: list[list], sic_of) -> dict:
    """Item 2.05 8-Ks filed in the month before `month` by companies whose filing header
    carried SIC 7370-7374. `sic_of(cik, accession)` reads that header."""
    cut, ref = cutoff(as_of), previous_month(month)
    count = sum(
        1
        for cik, accn, filed, accepted in layoffs
        if filed[:7] == ref
        and parse_accepted(accepted) < cut
        and sic_of(cik, accn) in SOFTWARE_SIC
    )
    return entry(count, ref, as_of, BULK_SUBMISSIONS)


# Corporate actions that the filings don't flag mechanically for the company itself (the
# parent of a spin-off files no Item 2.01 when the shares go out, or files it late). Checked
# by hand: date of completion and what happened.
CORPORATE_ACTIONS = {
    47217: [("2015-11-01", "HP split into HP Inc and Hewlett Packard Enterprise")],
    1645590: [
        ("2015-11-01", "Hewlett Packard Enterprise separated from HP"),
        ("2017-04-01", "Enterprise Services merged into DXC Technology"),
    ],
    1065088: [("2015-07-17", "PayPal spun off from eBay")],
    849399: [("2016-01-29", "Symantec sold Veritas")],
}
SPIN_OFF_FORMS = {"10-12B", "10-12G"}
# A corporate action excludes a company only when its count also moved by more than this in
# log terms (about 16% up or 14% down). Item 2.01 is common: Microsoft and Salesforce file one
# most years, and a small deal doesn't distort a change of a few percent.
DEAL_LOG_CHANGE = 0.15


def corporate_action(company: Company, after: str, through: str) -> str | None:
    """Why a change in headcount between fiscal year ends `after` and `through` is not
    hiring or layoffs alone: a completed acquisition or disposition (8-K Item 2.01), a Form 10
    registering the company's own spin-off, or a hand-listed action. None when there was none.
    """
    for when, what in CORPORATE_ACTIONS.get(company.cik, []):
        if after < when <= through:
            return what
    for f in company.filings:
        if not after < f.filing_date <= through:
            continue
        if f.form == "8-K" and "2.01" in f.items:
            return f"8-K Item 2.01 filed {f.filing_date} ({f.accn})"
        if f.form in SPIN_OFF_FORMS:
            return f"Form {f.form} filed {f.filing_date} ({f.accn})"
    return None


def matched_headcounts(
    as_of: date, companies: list[Company], counts: Headcounts
) -> tuple[list[tuple[int, int, int, str]], dict[int, str]]:
    """(cik, latest, previous, latest fiscal year end) for panel companies whose latest two
    10-Ks (accepted by the as-of date, the newer within a year or so) both state a count about
    a year apart, and the companies left out (cik → reason): those with a corporate action
    between the two 10-Ks whose count also moved by more than DEAL_LOG_CHANGE in log terms.
    Organic growth and layoffs stay in, however large."""
    cut = cutoff(as_of)
    matched, dropped = [], {}
    for c in companies:
        rows = counts.rows_for(c.cik, "10-K", cut)
        if len(rows) < 2 or cut - parse_accepted(rows[0]["accepted"]) > TEN_K_WINDOW:
            continue
        latest, prior = rows[0], rows[1]
        if not (latest["period"] and prior["period"]):
            continue
        if not 300 <= days(prior["period"], latest["period"]) <= 430:
            continue
        moved = abs(math.log(latest["value"] / prior["value"])) > DEAL_LOG_CHANGE
        if moved and (why := corporate_action(c, prior["period"], latest["period"])):
            dropped[c.cik] = why
            continue
        matched.append((c.cik, latest["value"], prior["value"], latest["period"]))
    return matched, dropped


def headcount_change(
    as_of: date, companies: list[Company], counts: Headcounts
) -> dict[str, dict | None]:
    """Year-over-year change in panel headcount two ways: the total (Σ latest ÷ Σ previous,
    which Amazon's warehouse staff dominate) and the median company's change. Each point
    lists the companies behind it (`companies`) and those left out for a corporate action
    (`dropped`); both change from month to month as 10-Ks arrive."""
    matched, dropped = matched_headcounts(as_of, companies, counts)
    if not matched:
        return {TOTAL_YOY_KEY: None, MEDIAN_YOY_KEY: None}
    ref = max(period for *_, period in matched)[:7]
    total = sum(m[1] for m in matched) / sum(m[2] for m in matched) - 1
    ratios = sorted(now / then - 1 for _, now, then, _ in matched)
    mid = len(ratios) // 2
    median = ratios[mid] if len(ratios) % 2 else (ratios[mid - 1] + ratios[mid]) / 2
    out = {}
    for key, value in ((TOTAL_YOY_KEY, total), (MEDIAN_YOY_KEY, median)):
        out[key] = entry(round(value, 4), ref, as_of, f"{ARCHIVES}/", len(matched))
        out[key]["companies"] = sorted(m[0] for m in matched)
        out[key]["dropped"] = sorted(dropped)
    return out


def quarterly_headcount(key: str, as_of: date, counts: Headcounts) -> dict | None:
    cut = cutoff(as_of)
    rows = [
        r for cik in QUARTERLY[key] for r in counts.rows_for(cik, f"ex99:{key}", cut)
    ]
    if not rows:
        return None
    newest = max(rows, key=lambda r: r["accepted"])
    if cut - parse_accepted(newest["accepted"]) > QUARTERLY_MAX_AGE:
        return None
    return entry(
        newest["value"], newest["period"], as_of, f"{ARCHIVES}/{newest['cik']}/"
    )


RESTRUCTURING_KEY = "sec_restructuring_usd.US"
RESTRUCTURING_COUNT_KEY = "sec_restructuring_companies.US"
TOTAL_YOY_KEY = "sec_headcount_panel.US"
MEDIAN_YOY_KEY = "sec_headcount_median_yoy.US"
PANEL_KEYS = [
    RESTRUCTURING_KEY,
    RESTRUCTURING_COUNT_KEY,
    "sec_item_205_filings_panel.US",
    TOTAL_YOY_KEY,
    MEDIAN_YOY_KEY,
]
SOFTWARE_KEY = "sec_item_205_filings_software.US"
QUARTERLY_KEYS = [f"sec_headcount_{k}.US" for k in QUARTERLY]


# ---------- the step ----------


class Sources:
    """Lazily loaded inputs for a run; each group fails once, then is skipped for the run."""

    def __init__(
        self, edgar: Edgar, counts: Headcounts, directory: Path = SEC_DIR
    ) -> None:
        self.edgar = edgar
        self.directory = directory
        self.counts = counts
        self.companies: dict[int, Company] = {}
        self._bulk: dict | None = None
        self.quarterly_ready = False
        self.failed: set[str] = set()

    def bulk(self) -> dict:
        if self._bulk is None:
            self._bulk = bulk_index(self.edgar)
        return self._bulk

    def company(self, cik: int, name: str = "") -> Company:
        if cik in self.companies and name and not self.companies[cik].name:
            # Loaded first for the quarterly releases, before it joined a panel.
            self.companies[cik].name = name
        if cik not in self.companies:
            company = load_company(self.edgar, cik, name)
            self.counts.annual(self.edgar, company)
            self.companies[cik] = company
        return self.companies[cik]

    def panel(self, year: int) -> dict:
        panel = load_panel(year, self.directory)
        if panel is None:
            print(f"sec: building the {year} panel", flush=True)
            panel = build_panel(year, self.bulk()["filers"], self.edgar)
            save_json(panel_path(year, self.directory), panel)
        return panel

    def quarterly(self) -> None:
        if not self.quarterly_ready:
            for key, ciks in QUARTERLY.items():
                for cik in ciks:
                    self.counts.quarterly(self.edgar, key, self.company(cik))
            self.quarterly_ready = True


def month_values(month: str, as_of: date, src: Sources) -> tuple[dict, list[str]]:
    values: dict[str, dict] = {}
    missing: list[str] = []

    def attempt(group: str, keys: list[str], compute) -> None:
        if group in src.failed:
            missing.extend(keys)
            return
        try:
            for key, value in compute().items():
                if value is not None:
                    values[key] = value
        except Exception as e:  # noqa: BLE001
            # EDGAR being down must not block the HN refresh; the month stays open.
            warn(f"sec: {group} failed at {month}, skipping it this run: {e!r}")
            src.failed.add(group)
            missing.extend(keys)

    def panel_group() -> dict:
        companies = [
            src.company(c["cik"], c["name"])
            for c in src.panel(int(month[:4]))["companies"]
        ]
        return {
            **restructuring_values(month, as_of, companies),
            "sec_item_205_filings_panel.US": panel_layoff_value(
                month, as_of, companies
            ),
            **headcount_change(as_of, companies, src.counts),
        }

    def quarterly_group() -> dict:
        src.quarterly()
        return {
            f"sec_headcount_{key}.US": quarterly_headcount(key, as_of, src.counts)
            for key in QUARTERLY
        }

    attempt("panel", PANEL_KEYS, panel_group)
    attempt(
        "bulk",
        [SOFTWARE_KEY],
        lambda: {
            SOFTWARE_KEY: software_layoff_value(
                month, as_of, src.bulk()["layoffs"], src.edgar.filing_sic
            )
        },
    )
    attempt("quarterly", QUARTERLY_KEYS, quarterly_group)
    return values, sorted(missing)


def plan(
    threads: dict[str, datetime], today: date, directory: Path = EXTERNAL_DIR
) -> list[str]:
    """HN months past their as-of date and not yet frozen, oldest first. A month is computed
    only after its as-of date, so its first file is final."""
    return [
        month
        for month, created_at in threads.items()
        if month >= SEC_FIRST_MONTH
        and as_of_date(created_at) < today
        and not is_frozen(load(SOURCE, month, directory))
    ]


def run(con: duckdb.DuckDBPyConnection, args: argparse.Namespace) -> None:
    threads = hiring_threads(con)
    if args.month:
        threads = {m: c for m, c in threads.items() if m == args.month}
    today = datetime.now(UTC).date()
    todo = plan(threads, today)
    if args.limit:
        todo = todo[: args.limit]
    retries = [m for m in todo if load(SOURCE, m)]
    if len(todo) - len(retries) > MAX_UNSCOPED_MONTHS and not (
        args.backfill or args.month
    ):
        raise SystemExit(
            f"sec: {len(todo)} months to compute ({todo[0]} to {todo[-1]}); "
            "run `sejr sec --backfill`"
        )
    print(f"sec: {len(todo)} months to compute")
    if args.dry_run:
        for month in todo:
            print(f"  {month}: would compute (as of {as_of_date(threads[month])})")
        return
    if not todo:
        return
    client = Client(
        min_interval=MIN_INTERVAL,
        user_agent=user_agent(),
        timeout=120,
        throttle_backoff=THROTTLE_BACKOFF,
    )
    newest = max(as_of_date(threads[m]) for m in todo)
    src = Sources(Edgar(client, fresh_after=newest), Headcounts())
    for month in todo:
        as_of = as_of_date(threads[month])
        values, missing = month_values(month, as_of, src)
        status = save(SOURCE, month, as_of, values, now(), missing=missing)
        print(
            f"  {month}: {len(values)} values{', missing ' + ', '.join(missing) if missing else ''}, {status}",
            flush=True,
        )
