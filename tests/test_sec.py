import json
import zipfile
from argparse import Namespace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from sejr import external, sec
from sejr.sec import (
    Company,
    Filing,
    Headcounts,
    Sources,
    calendar_quarter,
    cutoff,
    eligible,
    ex99_headcount,
    find_exhibit,
    first_filed,
    headcount,
    header_sic,
    is_layoff_8k,
    panel_layoff_value,
    parse_accepted,
    quarters,
    rank_panel,
    read_filings,
    ref_quarter,
    restructuring_by_quarter,
    software_layoff_value,
)

FIXTURES = Path(__file__).parent / "fixtures" / "sec"


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text())


def jsonl(name: str) -> list[dict]:
    return [json.loads(line) for line in (FIXTURES / name).read_text().splitlines()]


def synopsys() -> list[Filing]:
    return read_filings(fixture("submissions_synopsys.json")["recent"])


def autodesk() -> tuple[list[dict], dict[str, datetime]]:
    """Real Autodesk facts. companyfacts gives only a filing date, so each accession is given
    an acceptance time of 21:00 UTC that day."""
    facts = fixture("companyfacts_autodesk.json")["facts"]
    accepted = {
        f["accn"]: datetime.fromisoformat(f["filed"] + "T21:00:00+00:00") for f in facts
    }
    return facts, accepted


# ---------- filings and items ----------


def test_acceptance_time_is_utc():
    when = parse_accepted("2026-10-21T20:03:35.000Z")
    assert when == datetime(2026, 10, 21, 20, 3, 35, tzinfo=UTC)


def test_items_are_parsed_and_amendments_do_not_count():
    filings = synopsys()
    layoffs = [f for f in filings if "2.05" in f.items]
    assert [(f.form, f.accepted.date()) for f in layoffs] == [
        ("8-K/A", date(2026, 8, 26)),
        ("8-K", date(2025, 11, 12)),
    ]
    assert [is_layoff_8k(f) for f in layoffs] == [False, True]
    earnings = next(
        f for f in filings if f.accepted.date() == date(2026, 8, 26) and f.form == "8-K"
    )
    assert earnings.items == ("2.02", "9.01")
    assert not any(is_layoff_8k(f) for f in filings if f.form == "10-Q")


def test_a_filing_counts_only_once_accepted_by_the_as_of_date():
    company = Company(cik=883241, filings=synopsys(), accepted={}, facts={})
    # HN December 2025 counts November filings; its as-of date is after the 2.05 8-K.
    assert panel_layoff_value("2025-12", date(2025, 12, 9), [company])["value"] == 1
    # The as-of date is the last day a filing can be accepted, in UTC.
    assert cutoff(date(2025, 11, 12)) == datetime(2025, 11, 13, tzinfo=UTC)


def test_nothing_after_the_as_of_date_is_used():
    accepted = datetime(2026, 9, 30, 20, 30, tzinfo=UTC)
    company = Company(
        cik=1,
        filings=[
            Filing(
                "0000000001-26-000001",
                "8-K",
                accepted,
                ("2.05",),
                filing_date="2026-09-30",
            )
        ],
        accepted={},
        facts={},
    )
    layoffs = [[1, "0000000001-26-000001", "2026-09-30", accepted.isoformat()]]
    # A month whose as-of date falls before the filing never sees it, even though the filing
    # is in the reference month.
    for as_of in (date(2026, 9, 29), date(2026, 9, 30), date(2026, 10, 9)):
        seen = accepted < cutoff(as_of)
        assert panel_layoff_value("2026-10", as_of, [company])["value"] == seen
        value = software_layoff_value("2026-10", as_of, layoffs, lambda c, a: "7372")
        assert value["value"] == seen and value["vintage_date"] == as_of.isoformat()


def test_months_follow_the_edgar_filing_date_not_the_utc_clock():
    # Accepted 19:30 Eastern on September 30 (23:30 UTC), after the 17:30 cutoff: EDGAR dates
    # it October 1, so it belongs to October, though the UTC timestamp still reads September.
    accepted = datetime(2026, 9, 30, 23, 30, tzinfo=UTC)
    layoffs = [[1, "a", "2026-10-01", accepted.isoformat()]]
    sic = lambda c, a: "7372"
    assert (
        software_layoff_value("2026-10", date(2026, 10, 9), layoffs, sic)["value"] == 0
    )
    assert (
        software_layoff_value("2026-11", date(2026, 11, 9), layoffs, sic)["value"] == 1
    )


def test_the_software_count_uses_the_code_in_each_filing():
    when = datetime(2026, 9, 15, 15, tzinfo=UTC).isoformat()
    layoffs = [
        [1, "a", "2026-09-15", when],
        [2, "b", "2026-09-15", when],
        [3, "c", "2026-09-15", when],
    ]
    # Company 2's code today is software, but it filed as a retailer; company 3 is the reverse
    # (Yahoo filed under 7370 before it became Altaba).
    at_filing = {"a": "7372", "b": "5961", "c": "7370"}
    asked = []

    def sic_of(cik, accn):
        asked.append(accn)
        return at_filing[accn]

    value = software_layoff_value("2026-10", date(2026, 10, 9), layoffs, sic_of)
    assert value == {
        "value": 2,
        "ref_period": "2026-09",
        "vintage_date": "2026-10-09",
        "source_url": sec.BULK_SUBMISSIONS,
    }
    assert sorted(asked) == ["a", "b", "c"]


def test_the_sic_comes_from_the_filing_header():
    header = (FIXTURES / "header_synopsys_8k.txt").read_text()
    assert header_sic(header, 883241) == "7372"
    two = (
        "<SEC-HEADER>\n<FILER>\n<COMPANY-DATA>\n<CIK>0000000001\n<ASSIGNED-SIC>6798\n"
        "</COMPANY-DATA>\n</FILER>\n<FILER>\n<COMPANY-DATA>\n<CIK>0000000002\n"
        "<ASSIGNED-SIC>7372\n</COMPANY-DATA>\n</FILER>\n</SEC-HEADER>"
    )
    assert header_sic(two, 2) == "7372"
    assert header_sic(two, 1) == "6798"
    assert header_sic("no header", 1) == ""


def submissions_json(
    cik: int, sic: str, recent: dict, state: str = "CA", pages=()
) -> bytes:
    return json.dumps(
        {
            "cik": str(cik),
            "name": f"Company {cik}",
            "sic": sic,
            "addresses": {"business": {"stateOrCountry": state}},
            "filings": {"recent": recent, "files": [{"name": p} for p in pages]},
        }
    ).encode()


def columns(rows: list[tuple]) -> dict:
    keys = [
        "accessionNumber",
        "filingDate",
        "reportDate",
        "acceptanceDateTime",
        "form",
        "items",
        "primaryDocument",
    ]
    return {k: [r[i] for r in rows] for i, k in enumerate(keys)}


def test_scan_bulk_finds_candidates_and_every_layoff_filing(tmp_path):
    synopsys_recent = fixture("submissions_synopsys.json")["recent"]
    retailer = columns(
        [("r1", "2026-03-02", "", "2026-03-02T21:00:00.000Z", "8-K", "2.05,9.01", "x.htm"),
         ("r2", "2026-04-02", "", "2026-04-02T21:00:00.000Z", "8-K/A", "2.05", "x.htm")]
    )  # fmt: skip
    older = columns(
        [("o1", "2019-05-01", "", "2019-05-01T20:00:00.000Z", "8-K", "2.05", "x.htm"),
         ("o2", "2019-02-01", "2018-12-31", "2019-02-01T20:00:00.000Z", "10-K", "", "k.htm")]
    )  # fmt: skip
    empty = columns([])
    path = tmp_path / "submissions.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(
            "CIK0000883241.json", submissions_json(883241, "7372", synopsys_recent)
        )
        z.writestr("CIK0000000002.json", submissions_json(2, "5961", retailer))
        z.writestr(
            "CIK0000000003.json",
            submissions_json(
                3, "3674", empty, pages=["CIK0000000003-submissions-001.json"]
            ),
        )
        z.writestr("CIK0000000003-submissions-001.json", json.dumps(older))
        z.writestr("CIK0000000004.json", submissions_json(4, "2834", empty))
    scanned = sec.scan_bulk(path, extra_ciks=set())
    # Candidates by today's code: software and semiconductors, not the retailer or drug maker.
    assert set(scanned["filers"]) == {883241, 3}
    assert scanned["filers"][3]["ten_k"] == [["o2", "2019-02-01T20:00:00+00:00"]]
    assert scanned["filers"][883241]["sic"] == "7372"
    # Every original Item 2.05 8-K, whatever the filer's code, with its EDGAR filing date;
    # older pages are read and the amendment is not.
    assert scanned["layoffs"] == [
        [3, "o1", "2019-05-01", "2019-05-01T20:00:00+00:00"],
        [883241, "0001193125-25-276232", "2025-11-12", "2025-11-12T14:15:50+00:00"],
        [2, "r1", "2026-03-02", "2026-03-02T21:00:00+00:00"],
    ]


# ---------- XBRL facts ----------


def test_a_value_keeps_its_first_filed_version():
    facts, accepted = autodesk()
    fiscal_year = ("2012-02-01", "2013-01-31")
    # The fiscal 2013 10-K reported $43.9 million; the next year's 10-K restated it as $44.3
    # million. Both before and after the restatement, month t sees $43.9 million.
    for as_of in (date(2013, 4, 9), date(2014, 4, 9), date(2026, 10, 9)):
        assert first_filed(facts, accepted, cutoff(as_of))[fiscal_year][0] == 43_900_000
    # Before the 10-K was filed there is no fiscal-year value at all.
    assert fiscal_year not in first_filed(facts, accepted, cutoff(date(2013, 3, 17)))


def test_an_amendment_never_replaces_the_original():
    facts, accepted = autodesk()
    amended = {**facts[2], "accn": "amended", "form": "10-Q/A", "val": 9_999_999}
    accepted["amended"] = datetime(2014, 1, 1, tzinfo=UTC)
    periods = first_filed([*facts, amended], accepted, cutoff(date(2026, 10, 9)))
    assert periods[("2012-02-01", "2012-07-31")][0] == 0
    # An amendment alone counts, as first filed.
    only = first_filed([amended], accepted, cutoff(date(2026, 10, 9)))
    assert only[("2012-02-01", "2012-07-31")][0] == 9_999_999


def test_quarters_come_direct_or_from_year_to_date_differences():
    facts, accepted = autodesk()
    # Drop the directly reported fourth quarter: it must come back as year less nine months.
    no_q4 = [f for f in facts if (f["start"], f["end"]) != ("2012-11-01", "2013-01-31")]
    q = quarters(first_filed(no_q4, accepted, cutoff(date(2013, 4, 9))))
    assert q[("2012-11-01", "2013-01-31")] == pytest.approx(7_200_000)
    assert q[("2012-08-01", "2012-10-31")] == 36_700_000
    # Before the 10-K, the fourth quarter does not exist.
    early = quarters(first_filed(no_q4, accepted, cutoff(date(2013, 3, 1))))
    assert ("2012-11-01", "2013-01-31") not in early


def test_fiscal_quarters_map_to_calendar_quarters_by_midpoint():
    assert calendar_quarter("2012-11-01", "2013-01-31") == "2012-Q4"
    assert calendar_quarter("2026-04-01", "2026-06-30") == "2026-Q2"
    assert calendar_quarter("2025-06-29", "2025-09-27") == "2025-Q3"


def company_from(
    facts: dict[str, list[dict]], filings=(), fy_ends=(), cik=1, name="X"
) -> Company:
    accepted = {f.accn: f.accepted for f in filings}
    for tag_facts in facts.values():
        for f in tag_facts:
            accepted.setdefault(
                f["accn"], datetime.fromisoformat(f["filed"] + "T21:00:00+00:00")
            )
    ends = sorted(
        {
            f["end"]
            for fs in facts.values()
            for f in fs
            if sec.days(f["start"], f["end"]) > 350
        }
    )
    return Company(cik, list(filings), accepted, facts, list(fy_ends) or ends, name)


def test_the_tag_list_and_its_order():
    assert sec.RESTRUCTURING_TAGS == (
        "RestructuringCharges",
        "SeveranceCosts1",
        "RestructuringAndRelatedCostIncurredCost",
        "RestructuringSettlementAndImpairmentProvisions",
        "RestructuringCosts",
        "RestructuringCostsAndAssetImpairmentCharges",
    )


def test_each_fiscal_year_reads_one_tag():
    facts, _ = autodesk()
    # Severance is part of restructuring: in fiscal 2013 both are tagged, and adding them
    # would count it twice, so only RestructuringCharges is read. A later year with only
    # RestructuringCosts (a lower-priority tag) is read from that tag.
    severance = [{**f, "val": 1} for f in facts]
    later = [
        {**f, "start": f["start"].replace("2012", "2014").replace("2013", "2015"),
         "end": f["end"].replace("2012", "2014").replace("2013", "2015"),
         "accn": f["accn"] + "-later", "filed": f["filed"].replace("2013", "2015").replace("2012", "2014"),
         "val": 5_000_000}
        for f in facts
    ]  # fmt: skip
    company = company_from(
        {
            "RestructuringCharges": facts,
            "SeveranceCosts1": severance,
            "RestructuringCosts": later,
        }
    )
    out = restructuring_by_quarter(company, cutoff(date(2016, 1, 9)))
    assert out["2012-Q3"] == 36_700_000
    assert out["2012-Q4"] == 7_200_000
    assert out["2014-Q3"] == 5_000_000


def test_a_charge_reported_only_in_the_10k_lands_in_the_fourth_quarter():
    crm = fixture("salesforce_fy2023.json")
    filings = read_filings(crm["recent"])
    company = company_from(
        {"RestructuringCharges": crm["facts"]}, filings, cik=1108524, name="Salesforce"
    )
    # HN April 2023 reads 2022-Q4 (Salesforce's quarter to January 31, 2023). The three
    # fiscal 2023 10-Qs carried no restructuring tag, so the $828 million year is all Q4.
    out = restructuring_by_quarter(company, cutoff(date(2023, 4, 11)))
    assert out["2022-Q4"] == 828_000_000
    assert "2022-Q3" not in out
    # A 10-Q that had tagged it would block the rule: then the nine months are unknown.
    tagged = {
        "RestructuringCharges": [
            *crm["facts"],
            {"start": "2022-08-01", "end": "2022-10-31", "val": 1, "form": "10-Q",
             "accn": next(f.accn for f in filings if f.report_date == "2022-10-31"), "filed": "2022-11-30"},
        ]
    }  # fmt: skip
    blocked = restructuring_by_quarter(
        company_from(tagged, filings), cutoff(date(2023, 4, 11))
    )
    assert "2022-Q4" not in blocked
    # Before the 10-K there is nothing.
    assert "2022-Q4" not in restructuring_by_quarter(company, cutoff(date(2023, 3, 1)))


def test_a_custom_tag_company_is_left_out_of_both_restructuring_series():
    crm = fixture("salesforce_fy2023.json")
    filings = read_filings(crm["recent"])
    facts = {"RestructuringCharges": crm["facts"]}
    meta = company_from(facts, filings, cik=1326801, name="Meta")
    salesforce = company_from(facts, filings, cik=1108524, name="Salesforce")
    values = sec.restructuring_values("2023-04", date(2023, 4, 11), [meta, salesforce])
    dollars = values[sec.RESTRUCTURING_KEY]
    assert dollars["value"] == 828_000_000 and dollars["n"] == 1
    assert dollars["top"] == {"cik": 1108524, "name": "Salesforce", "share": 1.0}
    count = values[sec.RESTRUCTURING_COUNT_KEY]
    assert count["value"] == 1 and count["n"] == 1
    description = {s.key: s for s in external.SERIES}[sec.RESTRUCTURING_KEY].description
    assert all(name in description for name in sec.CUSTOM_RESTRUCTURING.values())


def test_a_filing_with_two_values_for_a_period_keeps_the_larger():
    when = datetime(2020, 2, 1, tzinfo=UTC)
    fact = {"start": "2019-10-01", "end": "2019-12-31", "accn": "a", "form": "10-K"}
    periods = first_filed(
        [{**fact, "val": -6_000_000}, {**fact, "val": 6_000_000}],
        {"a": when},
        cutoff(date(2020, 3, 1)),
    )
    assert periods[("2019-10-01", "2019-12-31")][0] == 6_000_000


def test_the_reported_quarter_has_had_time_to_be_filed():
    assert ref_quarter("2026-10") == "2026-Q2"
    assert ref_quarter("2026-11") == "2026-Q2"
    assert ref_quarter("2027-01") == "2026-Q3"
    assert ref_quarter("2026-04") == "2025-Q4"
    assert ref_quarter("2026-03") == "2025-Q3"
    for month in ("2026-01", "2026-04", "2026-07", "2026-10", "2026-12"):
        year, q = map(int, ref_quarter(month).split("-Q"))
        quarter_end = date(year, 3 * q, 28)
        assert (date(int(month[:4]), int(month[5:]), 9) - quarter_end).days >= 95


# ---------- panel ----------


def filer(sic="7372", state="CA", ten_k=(), reports=None, deregistered=()) -> dict:
    ten_k = [[f"a{i}", t] for i, t in enumerate(ten_k)]
    return {
        "name": "X",
        "sic": sic,
        "state": state,
        "ten_k": ten_k,
        "reports": sorted(reports if reports is not None else [t for _, t in ten_k]),
        "deregistered": list(deregistered),
    }


def test_panel_eligibility_uses_only_filings_before_january():
    cut = datetime(2026, 1, 1, tzinfo=UTC)
    assert eligible(filer(ten_k=["2025-02-20T21:00:00+00:00"]), cut)
    # First 10-K after the cutoff (an IPO in 2025): not yet eligible.
    assert not eligible(filer(ten_k=["2026-01-15T21:00:00+00:00"]), cut)
    # Last 10-K too long ago.
    assert not eligible(filer(ten_k=["2024-08-01T21:00:00+00:00"]), cut)
    # Not US-based.
    assert not eligible(filer(state="L2", ten_k=["2025-02-20T21:00:00+00:00"]), cut)
    # Deregistered after its last report (acquired), before the cutoff.
    gone = filer(
        ten_k=["2025-02-20T21:00:00+00:00"], deregistered=["2025-10-01T21:00:00+00:00"]
    )
    assert not eligible(gone, cut)
    # A Form 15 for one class of securities, followed by more 10-Qs, does not count.
    notes = filer(
        ten_k=["2025-02-20T21:00:00+00:00"],
        reports=["2025-02-20T21:00:00+00:00", "2025-11-01T21:00:00+00:00"],
        deregistered=["2025-05-01T21:00:00+00:00"],
    )
    assert eligible(notes, cut)
    # A Form 15 after the cutoff is not known yet.
    later = filer(
        ten_k=["2025-02-20T21:00:00+00:00"], deregistered=["2026-02-01T21:00:00+00:00"]
    )
    assert eligible(later, cut)


def test_panel_ranks_by_revenue_and_records_the_reason():
    candidates = {
        1: {**filer(), "name": "Small"},
        2: {**filer(sic="3571"), "name": "Big hardware"},
        3: {**filer(), "name": "No revenue"},
        4: {**filer(sic="5961"), "name": "Retailer"},
        1018724: {**filer(sic="5961"), "name": "Amazon"},
        6: {**filer(sic="7372"), "name": "Filed as a bank"},
    }
    revenue = {1: (5e9, "2025-06-30"), 2: (4e11, "2025-09-27"), 4: (9e11, "2025-12-31"),
               1018724: (6e11, "2025-12-31"), 6: (8e11, "2025-12-31")}  # fmt: skip
    # The code in each company's latest 10-K decides, not today's code.
    sics = {1: "7372", 2: "3571", 4: "5961", 1018724: "5961", 6: "6022"}
    panel = rank_panel(2026, candidates, revenue, sics)
    assert [c["name"] for c in panel["companies"]] == [
        "Amazon",
        "Big hardware",
        "Small",
    ]
    assert [c["reason"] for c in panel["companies"]] == [
        "named",
        "sic_3571",
        "sic_7372",
    ]
    assert panel["cutoff"] == "2026-01-01T00:00:00Z"
    many = rank_panel(
        2026,
        {i: filer() for i in range(80)},
        {i: (i, "2025-12-31") for i in range(80)},
        dict.fromkeys(range(80), "7372"),
    )
    assert len(many["companies"]) == 50


def test_candidate_codes_and_names():
    assert {"7370", "7374", "3570", "3579", "3670", "3679"} <= sec.CANDIDATE_SIC
    assert "3663" not in sec.CANDIDATE_SIC and "5961" not in sec.CANDIDATE_SIC
    assert set(sec.NAMED.values()) == {
        "Amazon", "Uber", "Lyft", "Airbnb", "DoorDash", "PayPal", "eBay", "Netflix"
    }  # fmt: skip
    cut = datetime(2017, 1, 1, tzinfo=UTC)
    singapore = filer(state="U0", ten_k=["2016-12-23T21:00:00+00:00"])
    assert eligible(singapore, cut, 1649338)
    assert not eligible(singapore, cut, 1)
    assert (
        "SalesRevenueGoodsNet" in sec.REVENUE_TAGS
        and "SalesRevenueServicesNet" in sec.REVENUE_TAGS
    )


def test_annual_revenue_ignores_10ks_after_the_cutoff():
    fact = {"start": "2024-01-01", "end": "2024-12-31", "form": "10-K"}
    facts = {"facts": {"us-gaap": {"Revenues": {"units": {"USD": [
        {**fact, "val": 100, "accn": "old"},
        {**fact, "start": "2025-01-01", "end": "2025-12-31", "val": 200, "accn": "new"},
    ]}}}}}  # fmt: skip
    accepted = {
        "old": datetime(2025, 2, 1, tzinfo=UTC),
        "new": datetime(2026, 2, 1, tzinfo=UTC),
    }
    cut = datetime(2026, 1, 1, tzinfo=UTC)
    assert sec.annual_revenue(facts, accepted, cut) == (100, "2024-12-31")


def test_a_revenue_tag_off_by_a_thousand_is_ignored():
    def fact(tag_val):
        return {
            "start": "2024-01-01",
            "end": "2024-12-31",
            "form": "10-K",
            "accn": "a",
            "val": tag_val,
        }

    facts = {"facts": {"us-gaap": {
        "Revenues": {"units": {"USD": [fact(54_014_000)]}},
        "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [fact(54_014_000_000)]}},
        "SalesRevenueNet": {"units": {"USD": [fact(60_000_000)]}},
    }}}  # fmt: skip
    accepted = {"a": datetime(2025, 3, 20, tzinfo=UTC)}
    cut = datetime(2026, 1, 1, tzinfo=UTC)
    assert sec.annual_revenue(facts, accepted, cut) == (60_000_000, "2024-12-31")


class NoEdgar:
    def __getattr__(self, name):
        raise AssertionError(f"a frozen panel must not touch EDGAR ({name})")


def test_a_stored_panel_is_frozen(tmp_path):
    stored = {"year": 2026, "companies": [{"cik": 1, "name": "Kept"}]}
    sec.save_json(sec.panel_path(2026, tmp_path), stored)
    src = Sources(NoEdgar(), Headcounts(tmp_path / "headcount.json"), tmp_path)
    assert src.panel(2026) == stored


# ---------- headcount ----------


@pytest.mark.parametrize(
    ("name", "floor"),
    # The tuning set's one miss is DST's table, which counts affiliates. The held-out set's two
    # misses are abstentions: "2,700 full-time and approximately 20 part-time employees", and
    # a company total in a sentence about clients.
    [
        ("headcount_labels.jsonl", 0.94),
        ("headcount_heldout.jsonl", 0.9),
        ("headcount_review_draw.jsonl", 0.95),
    ],
)
def test_headcount_sentences(name, floor):
    rows = [r for r in jsonl(name) if r["sentence"]]
    hits = [headcount(r["sentence"]) for r in rows]
    right = sum(bool(h) and h[0] == r["value"] for h, r in zip(hits, rows, strict=True))
    assert right / len(rows) >= floor
    # A miss is no count, never a wrong one.
    assert not any(h and h[0] != r["value"] for h, r in zip(hits, rows, strict=True))


def test_competing_sentences_from_whole_filings():
    """Every sentence in each labeled 10-K that pairs a number with employees (and its
    employee table), so the company total has to beat the parts, the layoffs and the
    customers. 85 filings across three hand-labeled draws."""
    rows = jsonl("headcount_filings.jsonl")
    got = [headcount("\n".join(r["sentences"])) for r in rows]
    values = [g[0] if g else None for g in got]
    # IBM states no count in its 10-K: no count is right there.
    right = sum(v == r["value"] for v, r in zip(values, rows, strict=True))
    assert right / len(rows) >= 0.95
    assert not any(v and v != r["value"] for v, r in zip(values, rows, strict=True))


def test_full_time_and_part_time_counts_take_the_full_time_number():
    text = "As of December 31, 2019 , we employed 9,060 full-time and 240 part-time employees."
    assert headcount(text)[0] == 9060


def test_a_count_without_a_date_or_we_had_is_not_enough():
    text = (
        "We have 9,639 employees working in game development in studios around the world. "
        "With 12,371 full-time employees as of March 31, 2024, of which 7,621 were located "
        "outside of the United States, we are constantly focused on our teams."
    )
    assert headcount(text)[0] == 12371
    assert headcount("We have 9,639 employees working in game development.") is None


@pytest.mark.parametrize(
    "text",
    [
        "Small businesses, or organizations with fewer than 100 employees, require simple tools.",
        "In August 2016, we announced a restructuring plan that will impact up to 5,500 employees.",
        (
            "As of the end of fiscal 2016, our worldwide sales and marketing departments consisted of "
            "approximately 25,500 employees."
        ),
        "As of December 31, 2011, we had 579 part-time and temporary employees.",
        "We had approximately 380 employees, or 42% of our total headcount, involved in research.",
        "We employed approximately 111,600 persons in the Asia Pacific region.",
        "At June 30, 2012, approximately 800 employees were on assignments in international locations.",
        (
            "ADP TotalSource is the largest PEO in the United States, serving approximately 340,000 "
            "worksite employees in all 50 states."
        ),
    ],
)
def test_parts_changes_and_other_peoples_staff_are_not_headcount(text):
    assert headcount(text) is None


def test_the_company_total_beats_a_part():
    text = (
        "Enterprise customers typically employ 1,000 or more employees. "
        "As of the end of fiscal 2025, our worldwide sales and marketing functions consisted of "
        "approximately 25,600 employees. "
        "As of July 26, 2025, we had approximately 86,200 employees and they are categorized as follows:"
    )
    assert headcount(text)[0] == 86_200


def test_a_headcount_table_is_read_when_no_sentence_states_it():
    text = (
        "Employees\nEmployees are summarized as follows (approximate numbers):\nJuly 30, 2016\n"
        "Employees by geography:\nUnited States\n37,550\nRest of world\n36,150\nTotal\n73,700\n"
    )
    assert headcount(text)[0] == 73_700


@pytest.mark.parametrize("case", fixture("ex99_snippets.json"), ids=lambda c: c["accn"])
def test_earnings_release_headcount(case):
    assert ex99_headcount(case["company"], case["text"]) == case["value"]


def test_finds_the_exhibit_however_it_is_numbered():
    page = (FIXTURES / "index_alphabet_2021q3.htm").read_text()
    assert find_exhibit(page, "EX-99.1") == "googexhibit991q32021.htm"
    assert find_exhibit(page, "EX-99.2") is None


def test_quarterly_headcount_uses_the_newest_release_by_the_as_of_date(tmp_path):
    counts = Headcounts(tmp_path / "h.json")
    counts.rows = {
        "q2": {"cik": 1326801, "kind": "ex99:meta", "accepted": "2026-07-29T20:00:00+00:00",
               "period": "2026-06-30", "value": 75472},
        "q3": {"cik": 1326801, "kind": "ex99:meta", "accepted": "2026-10-21T20:03:35+00:00",
               "period": "2026-09-30", "value": 66775},
    }  # fmt: skip
    assert sec.quarterly_headcount("meta", date(2026, 10, 9), counts)["value"] == 75472
    assert sec.quarterly_headcount("meta", date(2026, 11, 9), counts)["value"] == 66775
    # A company that stopped stating it gives no value rather than a stale one.
    assert sec.quarterly_headcount("meta", date(2027, 6, 9), counts) is None


def test_headcount_change_matches_companies_across_two_10ks(tmp_path):
    counts = Headcounts(tmp_path / "h.json")

    def row(cik, accepted, period, value):
        return {
            "cik": cik,
            "kind": "10-K",
            "accepted": accepted,
            "period": period,
            "value": value,
        }

    counts.rows = {
        "a1": row(1, "2025-02-01T21:00:00+00:00", "2024-12-31", 100),
        "a2": row(1, "2026-02-01T21:00:00+00:00", "2025-12-31", 110),
        "b1": row(2, "2025-08-01T21:00:00+00:00", "2025-06-30", 50),
        # Only one 10-K stating a count: left out.
        "c1": row(3, "2026-02-01T21:00:00+00:00", "2025-12-31", 999),
    }
    companies = [Company(cik, [], {}, {}) for cik in (1, 2, 3)]
    value = sec.headcount_change(date(2026, 3, 9), companies, counts)
    assert value[sec.TOTAL_YOY_KEY]["value"] == 0.1
    assert value[sec.TOTAL_YOY_KEY]["n"] == 1
    # Before the 2026 10-K, company 1 has one count only.
    none = sec.headcount_change(date(2026, 1, 9), companies, counts)
    assert none == {sec.TOTAL_YOY_KEY: None, sec.MEDIAN_YOY_KEY: None}


def ten_k_rows(sizes: dict[int, tuple[int, int]]) -> dict:
    return {
        f"{cik}-{i}": {
            "cik": cik,
            "kind": "10-K",
            "accepted": f"{2025 + i}-02-01T21:00:00+00:00",
            "period": f"{2024 + i}-12-31",
            "value": value,
        }
        for cik, pair in sizes.items()
        for i, value in enumerate(pair)
    }


def test_one_giant_moves_the_total_but_not_the_median(tmp_path):
    counts = Headcounts(tmp_path / "h.json")
    sizes = {1: (1_000_000, 1_250_000), 2: (100, 90), 3: (200, 190), 4: (300, 270)}
    counts.rows = ten_k_rows(sizes)
    companies = [Company(cik, [], {}, {}) for cik in sizes]
    value = sec.headcount_change(date(2026, 3, 9), companies, counts)
    assert value[sec.TOTAL_YOY_KEY]["value"] > 0.2
    # Changes -10%, -5%, -10%, +25%: the median is the mean of the middle two.
    assert value[sec.MEDIAN_YOY_KEY]["value"] == -0.075
    assert value[sec.MEDIAN_YOY_KEY]["n"] == 4
    assert value[sec.MEDIAN_YOY_KEY]["ref_period"] == "2025-12"
    assert value[sec.MEDIAN_YOY_KEY]["companies"] == [1, 2, 3, 4]


def test_a_spin_off_is_not_a_layoff(tmp_path):
    counts = Headcounts(tmp_path / "h.json")
    # HP's 10-Ks: 287,000, then 49,000 after Hewlett Packard Enterprise split off. eBay
    # without PayPal: 34,600 to 11,600. Neither is hiring or firing.
    sizes = {
        47217: (287_000, 49_000),
        1065088: (34_600, 11_600),
        3: (1_000, 1_100),
        4: (1_000, 1_500),
    }
    counts.rows = ten_k_rows(sizes)
    companies = [Company(cik, [], {}, {}) for cik in sizes]
    value = sec.headcount_change(date(2026, 3, 9), companies, counts)
    for key in (sec.TOTAL_YOY_KEY, sec.MEDIAN_YOY_KEY):
        assert value[key]["companies"] == [3]
        assert value[key]["value"] == 0.1
    assert sec.MAX_LOG_CHANGE == 0.3


# ---------- the step ----------


def test_months_are_computed_only_after_their_as_of_date(tmp_path):
    threads = {
        "2011-12": datetime(2011, 12, 1, 15, tzinfo=UTC),
        "2026-09": datetime(2026, 9, 1, 15, tzinfo=UTC),
        "2026-10": datetime(2026, 10, 1, 15, tzinfo=UTC),
    }
    assert sec.plan(threads, date(2026, 10, 9), tmp_path) == ["2026-09"]
    assert sec.plan(threads, date(2026, 10, 10), tmp_path) == ["2026-09", "2026-10"]
    # A month written after its as-of date is frozen.
    external.save(
        "sec", "2026-09", date(2026, 9, 9), {}, "2026-10-01T00:00:00Z", tmp_path
    )
    assert sec.plan(threads, date(2026, 10, 10), tmp_path) == ["2026-10"]
    # One still missing a series is retried.
    external.save("sec", "2026-10", date(2026, 10, 9), {}, "2026-10-11T00:00:00Z", tmp_path,
                  missing=["sec_item_205_filings_software.US"])  # fmt: skip
    assert sec.plan(threads, date(2026, 10, 12), tmp_path) == ["2026-10"]


def test_a_backfill_needs_the_flag(db, monkeypatch, capsys):
    monkeypatch.setattr(sec, "load", lambda *args, **kwargs: None)
    args = Namespace(month=None, limit=None, dry_run=True, backfill=False)
    with pytest.raises(SystemExit, match="--backfill"):
        sec.run(db, args)
    sec.run(db, Namespace(**{**vars(args), "backfill": True}))
    assert "would compute" in capsys.readouterr().out


def test_the_user_agent_is_required(monkeypatch):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    with pytest.raises(SystemExit, match="SEC_USER_AGENT"):
        sec.user_agent()
    monkeypatch.setenv("SEC_USER_AGENT", "Name name@example.com")
    assert sec.user_agent() == "Name name@example.com"


def test_requests_stay_under_the_fair_access_limit():
    assert 1 / sec.MIN_INTERVAL <= 8


def test_sec_series_export_with_n(tmp_path):
    key = "sec_restructuring_usd.US"
    record = {
        "month": "2026-10", "as_of": "2026-10-09", "fetched_at": "2026-11-04T00:00:00Z",
        "values": {key: {"value": 3.6e9, "ref_period": "2026-Q2", "vintage_date": "2026-10-09",
                         "source_url": "u", "n": 22,
                         "top": {"cik": 1, "name": "X", "share": 0.4}}},
    }  # fmt: skip
    path = tmp_path / "sec" / "2026-10.json"
    path.parent.mkdir()
    path.write_text(json.dumps(record))
    section = external.build_section(["2026-10"], tmp_path)
    entry = section[key]
    assert entry["publisher"] == "SEC EDGAR" and entry["country"] == "US"
    assert entry["license"] == "public domain"
    assert entry["series"] == [
        {
            "month": "2026-10",
            "value": 3.6e9,
            "ref_period": "2026-Q2",
            "vintage_date": "2026-10-09",
            "n": 22,
            "top": {"cik": 1, "name": "X", "share": 0.4},
        }
    ]
    assert {k for k in section if k.startswith("sec_")} == {
        "sec_restructuring_usd.US",
        "sec_restructuring_companies.US",
        "sec_item_205_filings_panel.US",
        "sec_item_205_filings_software.US",
        "sec_headcount_panel.US",
        "sec_headcount_median_yoy.US",
        "sec_headcount_meta.US",
        "sec_headcount_alphabet.US",
        "sec_headcount_amazon.US",
    }
    assert timedelta(days=0) < timedelta(days=external.AS_OF_DAYS)
