from argparse import Namespace

from sejr import aggregate, export, features, sources


def _ext(publisher, credit, points, license=("CC BY 4.0", "https://l")):
    return {
        "publisher": publisher,
        "credit": credit,
        "label": f"{credit} label",
        "license": license[0],
        "license_url": license[1],
        "source_url": f"https://src/{credit}",
        "series": [{"month": m, "value": 1.0, "ref_period": m} for m in points],
    }


METRICS = {
    "posts.hiring": {"series": [{"month": "2011-04"}, {"month": "2026-10"}]},
    "posts.seeking": {"series": [{"month": "2014-05"}, {"month": "2026-10"}]},
    "salary_max_median_usd.hiring": {"series": []},
}


def test_one_row_per_source_with_coverage_computed():
    external = {
        "indeed_software_postings.US": _ext("Indeed Hiring Lab", "postings", ["2021-06", "2026-10"]),
        "indeed_software_pay_transparency.US": _ext("Indeed Hiring Lab", "pay", ["2025-09", "2026-10"]),
        "jolts_openings_information.US": _ext("U.S. Bureau of Labor Statistics", "JOLTS", ["2011-04", "2026-10"]),
        "jolts_hires_information.US": _ext("U.S. Bureau of Labor Statistics", "JOLTS", ["2011-04", "2026-09"]),
        "ces_computer_systems_design.US": _ext("U.S. Bureau of Labor Statistics", "CES", ["2011-04", "2026-10"]),
        "indeed_software_remote_share.GB": _ext("Indeed Hiring Lab", "remote", []),
    }  # fmt: skip
    rows = sources.build(METRICS, external)
    assert [r["id"] for r in rows] == ["hn", "indeed", "bls_jolts", "bls_ces"]
    hn, indeed, jolts, ces = rows
    assert (hn["coverage_start"], hn["coverage_end"]) == ("2011-04", "2026-10")
    # Empty series don't count toward coverage or the series list.
    assert "salary_max_median_usd.hiring" not in hn["series"]
    assert indeed["coverage_start"] == "2021-06"
    assert "indeed_software_remote_share.GB" not in indeed["series"]
    # Two Indeed trackers credit differently, so the row credits the publisher.
    assert indeed["credit"] == "Indeed Hiring Lab"
    assert indeed["license"] == "CC BY 4.0"
    assert jolts["credit"] == "JOLTS"
    assert jolts["coverage_end"] == "2026-10"
    assert ces["series"] == ["ces_computer_systems_design.US"]
    for row in rows:
        for field in ("name", "measures", "lag", "caveat", "coverage_start", "url"):
            assert row[field], (row["id"], field)


def test_a_new_publisher_gets_a_row_without_code_changes():
    external = {
        "sec_headcount_panel.US": _ext("SEC EDGAR", "SEC EDGAR filings", ["2026-01"]),
        "warn_notices.US": _ext("Big Local News", "WARN", ["2022-04"], ("CC0", "")),
    }
    rows = {r["id"]: r for r in sources.build({}, external)}
    assert set(rows) == {"sec", "big_local_news"}
    assert rows["sec"]["name"] == "SEC EDGAR filings"
    assert rows["sec"]["caveat"]
    # Unknown publishers are described by their own series.
    assert rows["big_local_news"]["name"] == "Big Local News"
    assert rows["big_local_news"]["measures"] == "WARN label."
    assert rows["big_local_news"]["license"] == "CC0"
    assert rows["big_local_news"]["coverage_start"] == "2022-04"


def test_export_carries_the_sources_section(db, tmp_path):
    features.build(db)
    aggregate.run(db, Namespace(month=None, dry_run=False, limit=None))
    data = export.build(db, tmp_path / "validation.json", tmp_path / "external")
    # No outside values in the fixture, so only Hacker News has a row.
    assert [r["id"] for r in data["sources"]] == ["hn"]
    hn = data["sources"][0]
    assert (hn["coverage_start"], hn["coverage_end"]) == (
        data["months"][0],
        data["months"][-1],
    )
    assert "posts.hiring" in hn["series"]


def test_sources_from_the_real_external_section():
    from sejr.config import EXTERNAL_DIR
    from sejr.external import build_section

    months = [f"{y}-{m:02d}" for y in range(2011, 2027) for m in range(1, 13)]
    months = [m for m in months if "2011-04" <= m <= "2026-10"]
    rows = {
        r["id"]: r for r in sources.build(METRICS, build_section(months, EXTERNAL_DIR))
    }
    assert list(rows) == ["hn", "indeed", "bls_jolts", "bls_ces"]
    assert rows["indeed"]["coverage_start"] == "2021-06"
    assert rows["bls_jolts"]["coverage_end"] == "2026-10"
    assert rows["bls_ces"]["license"] == "public domain"
