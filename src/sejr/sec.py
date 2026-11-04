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
import os
import re
import zipfile
from dataclasses import dataclass
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

DATA = "https://data.sec.gov"
ARCHIVES = "https://www.sec.gov/Archives/edgar/data"
BULK_SUBMISSIONS = (
    "https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip"
)

SOFTWARE_SIC = {"7370", "7371", "7372", "7373", "7374"}
# Big tech filed under other SIC codes (hardware, retail, services). Predecessor CIKs are listed
# too; a company is only ever eligible while it files 10-Ks.
NAMED = {
    320193: "Apple",
    1018724: "Amazon",
    1045810: "Nvidia",
    50863: "Intel",
    858877: "Cisco",
    51143: "IBM",
    1065280: "Netflix",
    804328: "Qualcomm",
    2488: "AMD",
    1730168: "Broadcom",
    1054374: "Broadcom Corp (to 2016)",
    1571996: "Dell Technologies",
    826083: "Dell Inc (to 2013)",
    47217: "HP",
    1645590: "Hewlett Packard Enterprise",
    1633917: "PayPal",
    1065088: "eBay",
    1543151: "Uber",
    1759509: "Lyft",
    1559720: "Airbnb",
    1792789: "DoorDash",
}
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
PREFILTER = 100
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
)
# In order of preference: a company tagging both reports severance as part of restructuring.
RESTRUCTURING_TAGS = ("RestructuringCharges", "SeveranceCosts1")

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


def parse_accepted(text: str) -> datetime:
    # EDGAR's acceptanceDateTime is UTC ("Z"): an 8-K accepted 16:03 Eastern reads 20:03Z.
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


# ---------- every SIC 7370-7374 filer, from the nightly bulk file ----------

SIC_RE = re.compile(rb'"sic":"(\d*)"')


def scan_bulk(zip_path: Path, extra_ciks: set[int]) -> dict[int, dict]:
    """SIC 7370-7374 filers and the named companies: name, SIC, business state, original 10-Ks
    and the acceptance times of their Item 2.05 8-Ks.

    SIC and address are as of the bulk file's date, not as of each month: EDGAR keeps no history
    of either. Companies that stopped filing keep their last SIC, so dead filers still count.
    """
    keep = {}
    with zipfile.ZipFile(zip_path) as z:
        names = set(z.namelist())
        for name in sorted(names):
            if "-submissions-" in name or not name.startswith("CIK"):
                continue
            body = z.read(name)
            sic = SIC_RE.search(body[:4000])
            cik = int(name[3:13])
            if not ((sic and sic[1].decode() in SOFTWARE_SIC) or cik in extra_ciks):
                continue
            main = json.loads(body)
            filings = read_filings(main["filings"]["recent"])
            for page in main["filings"].get("files", []):
                if page["name"] in names:
                    filings += read_filings(json.loads(z.read(page["name"])))
            keep[cik] = {
                "name": main.get("name", ""),
                "sic": main.get("sic", ""),
                "state": ((main.get("addresses") or {}).get("business") or {}).get(
                    "stateOrCountry"
                ),
                "ten_k": sorted(
                    [f.accn, f.accepted.isoformat()] for f in filings if f.form in TEN_K
                ),
                "reports": sorted(
                    f.accepted.isoformat() for f in filings if f.form in REPORTS
                ),
                "deregistered": sorted(
                    f.accepted.isoformat() for f in filings if f.form in DEREGISTRATION
                ),
                "item_205": sorted(
                    f.accepted.isoformat() for f in filings if is_layoff_8k(f)
                ),
            }
    return keep


def software_filers(edgar: Edgar) -> dict[int, dict]:
    """scan_bulk over the cached bulk file, itself cached until the zip changes."""
    zip_path = edgar.bulk_submissions()
    index = zip_path.with_name("software_filers.json.gz")
    stamp = int(zip_path.stat().st_mtime)
    if index.exists():
        stored = json.loads(gzip.decompress(index.read_bytes()))
        if stored["zip_mtime"] == stamp:
            return {int(k): v for k, v in stored["filers"].items()}
    filers = scan_bulk(zip_path, set(NAMED))
    index.write_bytes(
        gzip.compress(
            json.dumps({"zip_mtime": stamp, "filers": filers}).encode(), mtime=0
        )
    )
    return filers


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


def restructuring_by_quarter(
    facts: dict[str, list[dict]], accepted: dict[str, datetime], cut: datetime
) -> dict[str, float]:
    """Calendar quarter → restructuring charge, as first filed before `cut`. `facts` maps
    each tag in RESTRUCTURING_TAGS to its USD facts."""
    out: dict[str, float] = {}
    for tag in RESTRUCTURING_TAGS:
        for (start, end), value in quarters(
            first_filed(facts.get(tag, []), accepted, cut)
        ).items():
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


def annual_revenue(
    companyfacts: dict, accepted: dict[str, datetime], cut: datetime
) -> tuple[float, str] | None:
    """(revenue, fiscal year end) for the latest fiscal year in a 10-K accepted before `cut`."""
    best: tuple[str, float] | None = None
    for tag in REVENUE_TAGS:
        for (start, end), (value, _) in first_filed(
            usd_facts(companyfacts, tag), accepted, cut
        ).items():
            if 350 <= days(start, end) <= 380 and (best is None or (end, value) > best):
                best = (end, value)
    return (best[1], best[0]) if best else None


# ---------- panel ----------


def panel_path(year: int, directory: Path = SEC_DIR) -> Path:
    return directory / "panel" / f"{year}.json"


def eligible(filer: dict, cut: datetime) -> bool:
    """A US-based filer with a 10-K in the year or so before `cut` that had not deregistered by
    then. A Form 15 for one class of securities (notes, say) is followed by more 10-Qs, so only
    a Form 15 after the last periodic report counts."""
    if filer["state"] not in US_STATES:
        return False
    if not any(
        cut - TEN_K_WINDOW <= parse_accepted(t) < cut for _, t in filer["ten_k"]
    ):
        return False
    last_report = max(t for t in filer["reports"] if parse_accepted(t) < cut)
    return not any(
        last_report < t and parse_accepted(t) < cut for t in filer["deregistered"]
    )


def frame_revenue(edgar: Edgar, year: int) -> dict[int, float]:
    out: dict[int, float] = {}
    for tag in REVENUE_TAGS:
        for row in edgar.frame(tag, year).get("data", []):
            out[row["cik"]] = max(out.get(row["cik"], 0.0), float(row["val"]))
    return out


def rank_panel(
    year: int, candidates: dict[int, dict], revenue: dict[int, tuple[float, str]]
) -> dict:
    """The top PANEL_SIZE candidates by revenue as first filed before Jan 1 of `year`."""
    ranked = sorted(
        (cik for cik in candidates if cik in revenue),
        key=lambda c: (-revenue[c][0], c),
    )[:PANEL_SIZE]
    companies = []
    for rank, cik in enumerate(ranked, 1):
        filer = candidates[cik]
        companies.append(
            {
                "cik": cik,
                "name": filer["name"],
                "sic": filer["sic"],
                "reason": f"sic_{filer['sic']}"
                if filer["sic"] in SOFTWARE_SIC
                else "named",
                "rank": rank,
                "revenue_usd": revenue[cik][0],
                "revenue_fiscal_year_end": revenue[cik][1],
            }
        )
    return {
        "year": year,
        "cutoff": f"{year}-01-01T00:00:00Z",
        "rule": (
            f"US-based 10-K filers in SIC 7370-7374 plus {len(NAMED)} named big-tech CIKs, "
            f"with a 10-K accepted in the {TEN_K_WINDOW.days} days before the cutoff; top "
            f"{PANEL_SIZE} by annual revenue in the latest 10-K accepted before the cutoff"
        ),
        "companies": companies,
    }


def build_panel(year: int, filers: dict[int, dict], edgar: Edgar) -> dict:
    cut = datetime(year, 1, 1, tzinfo=UTC)
    candidates = {cik: f for cik, f in filers.items() if eligible(f, cut)}
    # The frames API holds the latest restated values, so it only shortlists; the ranking uses
    # each company's revenue as first filed before the cutoff.
    restated = frame_revenue(edgar, year - 2)
    shortlist = sorted(
        (c for c in candidates if c in restated or c in NAMED),
        key=lambda c: (c not in NAMED, -restated.get(c, 0.0)),
    )
    shortlist = [c for c in shortlist if c in NAMED] + [
        c for c in shortlist if c not in NAMED
    ][:PREFILTER]
    revenue = {}
    for cik in shortlist:
        accepted = {accn: parse_accepted(t) for accn, t in candidates[cik]["ten_k"]}
        picked = annual_revenue(edgar.companyfacts(cik), accepted, cut)
        if picked:
            revenue[cik] = picked
    return rank_panel(year, candidates, revenue)


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
    r"comprised|consisted of|approximately|our|by)[:\s]+"
)
NOUN = (
    r"(?:(?:full[- ]time[- ]equivalent|full[- ]time|part[- ]time|full|regular|permanent|"
    r"total|global|worldwide|active|temporary|and|or)[,\s]+)*"
    r"(?:employees|people|persons|associates|team members|staff|personnel|professionals|"
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
    r"^\s*(?:(?:who|that) (?:are|were) )?(?:engaged in|located|in the [\w ]{1,30}region|"
    r"impacted|affected|who will|were on|in (?:the )?(?-i:[A-Z]))|^\W*(?:or|representing) [^.]{0,20}%",
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


def headcount(text: str) -> tuple[int, str] | None:
    """The company's employee count and the sentence that states it, from 10-K text.

    Many sentences in a 10-K pair a number with "employees": the sales team, a layoff, the
    staff in one country, a customer's size. Each candidate is scored: +2 when the count is
    stated at a date, +1 for "we had/employed", -5 when the words around the number say it is
    a part (part-time staff, one country, one function), a change (a layoff, growth) or
    someone else's (customers, a director's past employer). The best score wins, then the
    earliest; a negative best means no count. When no sentence scores 1 or more, a table row
    ("Total 73,700" under "Employees are summarized") is used.
    """
    best: tuple[int, int, int, str] | None = None  # (score, -order, value, sentence)
    order = 0
    for sentence in sentences(text):
        if not EMPLOYEE_WORDS.search(sentence):
            continue
        for pattern in (STATED_LIST, STATED, HEADCOUNT_WAS, WORKFORCE):
            match = pattern.search(sentence)
            if not match:
                continue
            value = _number(match[1], match[2])
            if value < 100:
                continue
            # The clause around the number, not the whole sentence: "We serve clients ... through
            # our 120,000 employees" is the company's own count.
            before = sentence[max(0, match.start() - 80) : match.end()]
            score = 2 * bool(AT_DATE.search(sentence)) + bool(
                re.search(
                    r"\b(?:we|company|\w+) (?:had|employed|employs|has)\b",
                    before,
                    re.IGNORECASE,
                )
            )
            # Part-time or temporary staff on their own are not the headline count.
            part_only = PART_ONLY.search(match[0]) and "full" not in match[0].lower()
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
    if (best is None or best[0] < 1) and (table := TABLE.search(text)):
        # A geography table ends with the total column.
        total = table[1].split()[-1]
        return int(total.replace(",", "")), table.group(0)[-300:]
    if best is None or best[0] < 0:
        return None
    return best[2], best[3]


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


def load_company(edgar: Edgar, cik: int) -> Company:
    _, filings = edgar.submissions(cik)
    facts = edgar.companyfacts(cik)
    return Company(
        cik=cik,
        filings=filings,
        accepted={f.accn: f.accepted for f in filings},
        facts={tag: usd_facts(facts, tag) for tag in RESTRUCTURING_TAGS},
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


def in_month(accepted: datetime, month: str) -> bool:
    return accepted.strftime("%Y-%m") == month


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


def restructuring_value(
    month: str, as_of: date, companies: list[Company]
) -> dict | None:
    cut, quarter = cutoff(as_of), ref_quarter(month)
    reported = []
    for c in companies:
        by_quarter = restructuring_by_quarter(c.facts, c.accepted, cut)
        if quarter in by_quarter:
            reported.append(by_quarter[quarter])
    if not reported:
        return None
    return entry(
        round(sum(reported)),
        quarter,
        as_of,
        f"{DATA}/api/xbrl/companyfacts/",
        len(reported),
    )


def panel_layoff_value(month: str, as_of: date, companies: list[Company]) -> dict:
    cut, ref = cutoff(as_of), previous_month(month)
    count = sum(
        1
        for c in companies
        for f in c.filings
        if is_layoff_8k(f) and in_month(f.accepted, ref) and f.accepted < cut
    )
    return entry(count, ref, as_of, f"{DATA}/submissions/", len(companies))


def software_layoff_value(month: str, as_of: date, filers: dict[int, dict]) -> dict:
    cut, ref = cutoff(as_of), previous_month(month)
    count = sum(
        1
        for filer in filers.values()
        if filer["sic"] in SOFTWARE_SIC
        for t in filer["item_205"]
        if in_month(when := parse_accepted(t), ref) and when < cut
    )
    return entry(count, ref, as_of, BULK_SUBMISSIONS)


def headcount_change(
    as_of: date, companies: list[Company], counts: Headcounts
) -> dict | None:
    """Year-over-year change over panel companies whose latest two 10-Ks (accepted by the as-of
    date, the newer within a year or so) both state a count about a year apart."""
    cut = cutoff(as_of)
    now_total = then_total = 0
    periods = []
    for c in companies:
        rows = counts.rows_for(c.cik, "10-K", cut)
        if len(rows) < 2 or cut - parse_accepted(rows[0]["accepted"]) > TEN_K_WINDOW:
            continue
        latest, prior = rows[0], rows[1]
        if not (latest["period"] and prior["period"]):
            continue
        if not 300 <= days(prior["period"], latest["period"]) <= 430:
            continue
        now_total += latest["value"]
        then_total += prior["value"]
        periods.append(latest["period"])
    if not periods:
        return None
    return entry(
        round(now_total / then_total - 1, 4),
        max(periods)[:7],
        as_of,
        f"{ARCHIVES}/",
        len(periods),
    )


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


PANEL_KEYS = [
    "sec_restructuring_usd.US",
    "sec_item_205_filings_panel.US",
    "sec_headcount_panel.US",
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
        self._filers: dict[int, dict] | None = None
        self.quarterly_ready = False
        self.failed: set[str] = set()

    def filers(self) -> dict[int, dict]:
        if self._filers is None:
            self._filers = software_filers(self.edgar)
        return self._filers

    def company(self, cik: int) -> Company:
        if cik not in self.companies:
            company = load_company(self.edgar, cik)
            self.counts.annual(self.edgar, company)
            self.companies[cik] = company
        return self.companies[cik]

    def panel(self, year: int) -> dict:
        panel = load_panel(year, self.directory)
        if panel is None:
            print(f"sec: building the {year} panel", flush=True)
            panel = build_panel(year, self.filers(), self.edgar)
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
            src.company(c["cik"]) for c in src.panel(int(month[:4]))["companies"]
        ]
        return {
            "sec_restructuring_usd.US": restructuring_value(month, as_of, companies),
            "sec_item_205_filings_panel.US": panel_layoff_value(
                month, as_of, companies
            ),
            "sec_headcount_panel.US": headcount_change(as_of, companies, src.counts),
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
        lambda: {SOFTWARE_KEY: software_layoff_value(month, as_of, src.filers())},
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
    client = Client(min_interval=MIN_INTERVAL, user_agent=user_agent(), timeout=120)
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
