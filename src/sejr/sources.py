"""The `sources` section of metrics.json: one row per data source, for the page's Sources block.

Descriptions are written here by hand; coverage is computed from the exported series, so a new
outside series shows up under its source without code changes. A publisher with no text here
still gets a row, built from its series' own credit and license.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceText:
    name: str
    measures: str
    lag: str
    caveat: str
    credit: str = ""
    license: str = ""
    license_url: str = ""
    url: str = ""


HN = "hn"

TEXT: dict[str, SourceText] = {
    HN: SourceText(
        name="Hacker News hiring threads",
        measures=(
            "Employer posts in the monthly “Ask HN: Who is hiring?” thread and posts from "
            "people looking for work in “Who wants to be hired?”, read in the first 7 days. "
            "The job-seeker thread began in May 2014."
        ),
        lag="None: each issue reads that month's threads once their first week is over.",
        caveat=(
            "A startup-leaning panel, not the market: it skews toward venture-backed "
            "companies, engineering roles and the Bay Area, many posters are outside the US, "
            "and one post can list many roles."
        ),
        credit="Hacker News, public threads",
        url="https://news.ycombinator.com/submitted?id=whoishiring",
    ),
    "indeed": SourceText(
        name="Indeed Hiring Lab",
        measures=(
            "Software development job postings on Indeed in the US and UK (an index, "
            "February 2020 = 100), "
            "the share offering remote or hybrid work, and the share that state pay."
        ),
        url="https://github.com/hiring-lab",
        lag=(
            "Days for postings; the remote share runs to the previous month end and pay "
            "transparency about two months behind."
        ),
        caveat=(
            "Postings are ads, not hires, and Indeed's mix of sites and employers changes over "
            "time. The remote and pay shares are not seasonally adjusted."
        ),
    ),
    "bls_jolts": SourceText(
        name="BLS Job Openings and Labor Turnover Survey (JOLTS)",
        measures=(
            "Job openings, hires and layoffs in the information sector and in professional "
            "and business services, all occupations, US."
        ),
        url="https://www.bls.gov/jlt/",
        lag="About two months: an issue carries the newest month published by its date.",
        caveat=(
            "Industries, not occupations: these counts include every job in those sectors, "
            "not only software work. Not seasonally adjusted, so compare a month with the same "
            "month a year earlier, or use the 12-month average."
        ),
    ),
    "bls_ces": SourceText(
        name="BLS Current Employment Statistics (CES)",
        measures=(
            "People employed by computer systems design and related services firms "
            "(NAICS 5415), US, seasonally adjusted."
        ),
        url="https://www.bls.gov/ces/",
        lag="About one month.",
        caveat=(
            "An industry, not an occupation, and it leaves out software engineers employed "
            "elsewhere. Values are as first published, so BLS's annual benchmark revision "
            "shows up as a step in early-year months."
        ),
    ),
    "sec": SourceText(
        name="SEC EDGAR filings",
        measures="Headcount, restructuring costs and layoff filings from a fixed panel of US tech companies.",
        lag="Quarterly or annual, dated by each filing's acceptance time.",
        caveat="Large public companies only, and headcount is company-wide, not engineering.",
    ),
}

# Publisher → source id for the outside series; BLS splits by survey (see source_id).
PUBLISHER_ID = {"Indeed Hiring Lab": "indeed", "SEC EDGAR": "sec"}


def source_id(key: str, entry: dict) -> str:
    name = key.split(".")[0]
    if name.startswith("jolts_"):
        return "bls_jolts"
    if name.startswith("ces_"):
        return "bls_ces"
    publisher = entry.get("publisher") or name
    return PUBLISHER_ID.get(publisher) or "".join(
        c if c.isalnum() else "_" for c in publisher.lower()
    )


def _hn_row(metrics: dict) -> dict | None:
    live = {k: m["series"] for k, m in metrics.items() if m["series"]}
    if not live:
        return None
    starts = {k: s[0]["month"] for k, s in live.items()}
    end = max(s[-1]["month"] for s in live.values())
    # HN describes the issue month itself.
    return _row(HN, TEXT[HN], list(live), starts, end) | {"latest_ref_period": end}


def _row(
    sid: str, text: SourceText, keys: list[str], starts: dict[str, str], end: str
) -> dict:
    return {
        "id": sid,
        "name": text.name,
        "measures": text.measures,
        "lag": text.lag,
        "caveat": text.caveat,
        "credit": text.credit,
        "license": text.license,
        "license_url": text.license_url,
        "url": text.url,
        "coverage_start": min(starts.values()),
        "coverage_end": end,
        "series": sorted(keys),
    }


def build(metrics: dict, external: dict) -> list[dict]:
    """Rows in reading order: Hacker News first, then outside sources by first appearance."""
    rows = []
    hn = _hn_row(metrics)
    if hn:
        rows.append(hn)
    groups: dict[str, list[tuple[str, dict]]] = {}
    for key, entry in external.items():
        if entry["series"]:
            groups.setdefault(source_id(key, entry), []).append((key, entry))
    for sid, members in groups.items():
        first = members[0][1]
        known = TEXT.get(sid)
        # An unknown publisher still gets a row, described by its own series.
        text = known or SourceText(
            name=first["publisher"],
            measures="; ".join(e["label"] for _, e in members) + ".",
            lag="See each series' reference period.",
            caveat="",
        )
        row = _row(
            sid,
            text,
            [k for k, _ in members],
            {k: e["series"][0]["month"] for k, e in members},
            max(e["series"][-1]["month"] for _, e in members),
        )
        # Credit and license come from the series themselves, so they match the chart credits.
        credits = {e["credit"] for _, e in members}
        row["credit"] = first["credit"] if len(credits) == 1 else first["publisher"]
        row["license"] = first["license"]
        row["license_url"] = first["license_url"]
        row["url"] = text.url or first["source_url"]
        # The newest period any of its series describes in the latest issue.
        row["latest_ref_period"] = max(
            e["series"][-1]["ref_period"]
            for _, e in members
            if e["series"][-1]["month"] == row["coverage_end"]
        )
        rows.append(row)
    return rows
