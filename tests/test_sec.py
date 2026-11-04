import json
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
    accepted = datetime(2026, 9, 30, 23, 30, tzinfo=UTC)
    company = Company(
        cik=1,
        filings=[Filing("0000000001-26-000001", "8-K", accepted, ("2.05",))],
        accepted={},
        facts={},
    )
    filers = {1: {"sic": "7372", "item_205": [accepted.isoformat()]}}
    # A month whose as-of date falls before the filing never sees it, even though the filing
    # is in the reference month.
    for as_of in (date(2026, 9, 29), date(2026, 9, 30), date(2026, 10, 9)):
        seen = accepted < cutoff(as_of)
        assert panel_layoff_value("2026-10", as_of, [company])["value"] == seen
        assert software_layoff_value("2026-10", as_of, filers)["value"] == seen
        assert (
            panel_layoff_value("2026-10", as_of, [company])["vintage_date"]
            == as_of.isoformat()
        )


def test_the_software_count_uses_software_codes_only():
    when = datetime(2026, 9, 15, tzinfo=UTC).isoformat()
    filers = {
        1: {"sic": "7372", "item_205": [when]},
        2: {"sic": "3571", "item_205": [when]},
    }
    value = software_layoff_value("2026-10", date(2026, 10, 9), filers)
    assert value == {
        "value": 1,
        "ref_period": "2026-09",
        "vintage_date": "2026-10-09",
        "source_url": sec.BULK_SUBMISSIONS,
    }


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


def test_restructuring_by_quarter_prefers_restructuring_charges():
    facts, accepted = autodesk()
    severance = [{**f, "val": 1} for f in facts]
    out = restructuring_by_quarter(
        {"RestructuringCharges": facts, "SeveranceCosts1": severance},
        accepted,
        cutoff(date(2014, 1, 9)),
    )
    assert out["2012-Q3"] == 36_700_000
    assert out["2012-Q4"] == 7_200_000


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
    }
    panel = rank_panel(
        2026, candidates, {1: (5e9, "2025-06-30"), 2: (4e11, "2025-09-27")}
    )
    assert [c["name"] for c in panel["companies"]] == ["Big hardware", "Small"]
    assert [c["reason"] for c in panel["companies"]] == ["named", "sic_7372"]
    assert panel["cutoff"] == "2026-01-01T00:00:00Z"
    assert (
        len(
            rank_panel(
                2026,
                {i: filer() for i in range(80)},
                {i: (i, "2025-12-31") for i in range(80)},
            )["companies"]
        )
        == 50
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
    [("headcount_labels.jsonl", 0.95), ("headcount_heldout.jsonl", 0.85)],
)
def test_headcount_sentences(name, floor):
    rows = [r for r in jsonl(name) if r["sentence"]]
    hits = [headcount(r["sentence"]) for r in rows]
    right = sum(bool(h) and h[0] == r["value"] for h, r in zip(hits, rows, strict=True))
    assert right / len(rows) >= floor
    # A miss is no count, never a wrong one.
    assert not any(h and h[0] != r["value"] for h, r in zip(hits, rows, strict=True))


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
    assert value["value"] == 0.1 and value["n"] == 1
    # Before the 2026 10-K, company 1 has one count only.
    assert sec.headcount_change(date(2026, 1, 9), companies, counts) is None


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
                         "source_url": "u", "n": 22}},
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
        }
    ]
    assert {k for k in section if k.startswith("sec_")} == {
        "sec_restructuring_usd.US",
        "sec_item_205_filings_panel.US",
        "sec_item_205_filings_software.US",
        "sec_headcount_panel.US",
        "sec_headcount_meta.US",
        "sec_headcount_alphabet.US",
        "sec_headcount_amazon.US",
    }
    assert timedelta(days=0) < timedelta(days=external.AS_OF_DAYS)
