import json
from argparse import Namespace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import duckdb
import pytest
from conftest import CLASSIFIED, MONTHS, NO_HIRING, NO_SEEKING, PENDING

from sejr import aggregate, export, features
from sejr.config import JEV_MODEL
from sejr.db import connect


def truncated_copy(
    full: duckdb.DuckDBPyConnection, path: Path, t: date
) -> duckdb.DuckDBPyConnection:
    """Copy only the raw inputs a run on month t would have had: threads <= t and Jev answers."""
    connect(path).close()
    full.execute(f"ATTACH '{path}' AS cut")
    for table, where in [
        ("threads", "month <= $t"),
        ("posts", "thread_id IN (SELECT thread_id FROM threads WHERE month <= $t)"),
        ("replies", "thread_id IN (SELECT thread_id FROM threads WHERE month <= $t)"),
        ("answers", ("method = 'jev' AND post_id IN (SELECT post_id FROM posts "
                    "JOIN threads USING (thread_id) WHERE month <= $t)")),
    ]:  # fmt: skip
        full.execute(
            f"INSERT INTO cut.{table} SELECT * FROM {table} WHERE {where}", {"t": t}
        )
    full.execute("DETACH cut")
    return connect(path)


def test_month_is_the_same_with_or_without_later_months(db, tmp_path):
    features.build(db)
    for t in MONTHS:
        cut = truncated_copy(db, tmp_path / f"cut-{t}.duckdb", t)
        features.build(cut)
        assert aggregate.compute_month(cut, t) == aggregate.compute_month(db, t), t
        cut.close()


def test_later_months_exist_in_full_db(db):
    # Guard against a vacuous point-in-time test: the full DB must hold data after each t.
    (latest,) = db.execute("SELECT max(month) FROM threads").fetchone()
    assert latest == MONTHS[-1]


def _metrics(rows) -> dict[tuple[str, str, str], tuple[float, int]]:
    return {
        (kind, metric, category): (value, n)
        for _, kind, metric, category, value, n in rows
    }


def test_jev_metrics_only_where_classified(db):
    features.build(db)
    for t in MONTHS:
        metrics = _metrics(aggregate.compute_month(db, t))
        has_jev = ("hiring", "ai_native_share", "") in metrics
        assert has_jev == (t in CLASSIFIED and t not in NO_HIRING), t
        assert (("seeking", "seeker_mood", "") in metrics) == (
            t in CLASSIFIED and t not in NO_SEEKING
        )


def test_choice_breakdown_is_expected_share(db):
    features.build(db)
    month = date(2024, 3, 1)
    metrics = _metrics(aggregate.compute_month(db, month))
    shares = [v for (k, m, c), (v, n) in metrics.items() if m == "work_mode"]
    assert len(shares) == 4
    assert sum(shares) == pytest.approx(1.0, abs=0.01)
    (expected,) = db.execute(
        """
        SELECT avg(json_extract(a.probabilities, '$.hybrid')::DOUBLE)
        FROM answers a JOIN posts p USING (post_id) JOIN threads t USING (thread_id)
        WHERE a.question = 'work_mode' AND a.version = $v AND p.in_snapshot AND t.month = $m
        """,
        {"m": month, "v": JEV_MODEL},
    ).fetchone()
    assert metrics[("hiring", "work_mode", "hybrid")][0] == pytest.approx(expected)


def _snapshot_answers(db, month: date, question: str) -> list[tuple]:
    return db.execute(
        """
        SELECT a.value, a.probabilities
        FROM answers a JOIN posts p USING (post_id) JOIN threads t USING (thread_id)
        WHERE a.question = $q AND a.version = $v AND p.in_snapshot AND t.month = $m
        """,
        {"q": question, "m": month, "v": JEV_MODEL},
    ).fetchall()


def test_seeker_strained_share_sums_levels_0_and_1(db):
    month = date(2024, 3, 1)
    metrics = _metrics(aggregate.compute_month(db, month))
    moods = [json.loads(p) for _, p in _snapshot_answers(db, month, "seeker_mood")]
    expected = sum(m["0"] + m["1"] for m in moods) / len(moods)
    assert metrics[("seeking", "seeker_strained_share", "")] == (
        pytest.approx(expected),
        len(moods),
    )


def test_industry_known_renormalizes_without_unstated(db):
    metrics = _metrics(aggregate.compute_month(db, date(2024, 3, 1)))
    industry = {c: v for (_, m, c), (v, _) in metrics.items() if m == "industry"}
    known = {c: v for (_, m, c), (v, _) in metrics.items() if m == "industry_known"}
    assert "unstated" not in known
    assert sum(known.values()) == pytest.approx(1.0)
    stated = sum(v for c, v in industry.items() if c != "unstated")
    for category, share in known.items():
        assert share == pytest.approx(industry[category] / stated)


def test_industry_known_when_distributions_dont_sum_to_one(tmp_path):
    con = connect(tmp_path / "industry.duckdb")
    _thread(con, 1, date(2020, 1, 1))
    for post_id, probabilities in [
        (10, {"ai_ml": 0.3, "fintech": 0.3, "unstated": 0.2}),  # sums to 0.8
        (11, {"ai_ml": 0.2, "health": 0.2, "unstated": 0.4}),
    ]:
        _post(con, post_id, 1, "Acme | Engineer")
        con.execute(
            "INSERT INTO answers VALUES (?, 'industry', 'jev', ?, NULL, 'ai_ml', ?, 0.5)",
            [post_id, JEV_MODEL, json.dumps(probabilities)],
        )
    metrics = _metrics(aggregate.compute_month(con, date(2020, 1, 1)))
    # Stated mass is 0.6 + 0.4 = 1.0; ai_ml holds 0.5 of it.
    assert metrics[("hiring", "industry_known", "ai_ml")] == (pytest.approx(0.5), 1)
    assert metrics[("hiring", "industry_known", "fintech")][0] == pytest.approx(0.3)
    assert metrics[("hiring", "industry_known", "health")][0] == pytest.approx(0.2)
    assert metrics[("hiring", "industry", "unstated")][0] == pytest.approx(0.3)


def test_jev_metrics_need_98_percent_coverage(db):
    month = date(2024, 3, 1)
    assert ("hiring", "work_mode", "remote") in _metrics(
        aggregate.compute_month(db, month)
    )
    db.execute(
        """
        DELETE FROM answers WHERE question = 'work_mode' AND post_id = (
          SELECT min(p.post_id) FROM posts p JOIN threads t USING (thread_id)
          WHERE t.month = $m AND t.kind = 'hiring' AND p.in_snapshot
        )
        """,
        {"m": month},
    )
    metrics = _metrics(aggregate.compute_month(db, month))
    assert ("hiring", "work_mode", "remote") not in metrics  # 3 of 4 answered
    assert ("hiring", "ai_native_share", "") in metrics


def test_seniority_split_by_ai_native(db):
    month = date(2024, 6, 1)
    metrics = _metrics(aggregate.compute_month(db, month))
    ai_values = [v for v, _ in _snapshot_answers(db, month, "ai_native")]
    n_ai = sum(v >= 0.5 for v in ai_values)
    for metric, n in [
        ("seniority_ai_native", n_ai),
        ("seniority_not_ai_native", len(ai_values) - n_ai),
    ]:
        shares = {c: v for (_, m, c), v in metrics.items() if m == metric}
        if n:
            assert {count for _, count in shares.values()} == {n}
            assert sum(v for v, _ in shares.values()) == pytest.approx(1.0, abs=0.01)


def test_new_jev_scalars_present(db):
    features.build(db)
    metrics = _metrics(aggregate.compute_month(db, date(2024, 1, 1)))
    assert ("hiring", "eng_leadership_share", "") in metrics
    assert ("hiring", "interns_token_share", "") in metrics


def test_old_jev_versions_are_ignored(db):
    features.build(db)
    metrics = _metrics(aggregate.compute_month(db, date(2024, 1, 1)))
    value, _ = metrics[("hiring", "ai_native_share", "")]
    assert value < 1.0  # the jev-1.12.0 rows are all 1.0


def test_counts_use_only_snapshot_posts(db):
    features.build(db)
    t = date(2024, 1, 1)
    metrics = _metrics(aggregate.compute_month(db, t))
    # Every fixture month has 6 hiring posts, the last 2 posted after the snapshot.
    assert metrics[("hiring", "posts", "")] == (4.0, 4)
    seeking, _ = metrics[("seeking", "posts", "")]
    assert metrics[("hiring", "seekers_per_post", "")][0] == pytest.approx(seeking / 4)


def test_no_join_metrics_without_history(db):
    features.build(db)
    first = _metrics(aggregate.compute_month(db, MONTHS[0]))
    assert ("hiring", "new_company_share", "") not in first
    assert ("hiring", "returning_company_share", "") not in first
    may = _metrics(aggregate.compute_month(db, date(2024, 5, 1)))
    assert ("hiring", "new_company_share", "") in may
    assert ("hiring", "returning_company_share", "") not in may  # April had no thread


def _thread(con, thread_id: int, month: date) -> None:
    created = datetime(month.year, month.month, 1, 15, tzinfo=UTC)
    con.execute(
        "INSERT INTO threads VALUES (?, 'hiring', ?, 'Ask HN: Who is hiring?', ?, ?, ?, 0)",
        [
            thread_id,
            month,
            created,
            created + timedelta(days=7),
            created + timedelta(days=8),
        ],
    )


def _post(
    con, post_id: int, thread_id: int, text: str, in_snapshot: bool = True
) -> None:
    con.execute(
        "INSERT INTO posts VALUES (?, ?, 'a', now(), ?, ?, ?)",
        [post_id, thread_id, text, text, in_snapshot],
    )


def test_new_and_returning_company_joins(tmp_path):
    con = connect(tmp_path / "join.duckdb")
    for thread_id, month in [
        (1, date(2020, 1, 1)),
        (2, date(2020, 2, 1)),
        (3, date(2020, 3, 1)),
    ]:
        _thread(con, thread_id, month)
    _post(con, 10, 1, "Acme Inc. | Engineer | REMOTE")
    _post(con, 11, 1, "Late Co | Engineer | REMOTE", in_snapshot=False)
    _post(con, 20, 2, "ACME, Inc | Engineer | ONSITE")
    _post(con, 21, 2, "Late Co | Engineer | REMOTE")
    _post(con, 30, 3, "The Acme | Engineer")
    features.build(con)

    def join(post_id: int, question: str) -> float | None:
        row = con.execute(
            "SELECT value FROM answers WHERE post_id = ? AND question = ?",
            [post_id, question],
        ).fetchone()
        return row[0] if row else None

    assert join(10, "new_company") is None  # nothing earlier to compare against
    assert join(20, "new_company") == 0.0
    assert join(20, "returned_from_last_month") == 1.0
    # Late Co's January post missed the snapshot, so February is its first appearance.
    assert join(21, "new_company") == 1.0
    assert join(21, "returned_from_last_month") == 0.0
    assert join(30, "returned_from_last_month") == 1.0


def test_features_build_is_idempotent(db):
    features.build(db)
    first = db.execute("SELECT count(*) FROM answers").fetchone()
    features.build(db)
    assert db.execute("SELECT count(*) FROM answers").fetchone() == first


def test_incomplete_threads_are_skipped_and_listed_as_pending(db):
    features.build(db)
    metrics = _metrics(aggregate.compute_month(db, PENDING))
    assert ("hiring", "posts", "") in metrics
    assert ("seeking", "posts", "") not in metrics
    assert ("hiring", "seekers_per_post", "") not in metrics
    aggregate.run(db, Namespace(month=None, dry_run=False, limit=None))
    assert export.build(db)["pending"] == [f"{PENDING:%Y-%m}"]


def test_removed_share(db):
    rows = db.execute(
        "SELECT month, kind, removed_in_snapshot FROM threads "
        "WHERE removed_in_snapshot IS NOT NULL AND fetched_at >= snapshot_at"
    ).fetchall()
    assert rows
    for month, kind, removed in rows:
        metrics = _metrics(aggregate.compute_month(db, month))
        posts, _ = metrics[(kind, "posts", "")]
        assert metrics[(kind, "removed_share", "")] == (
            pytest.approx(removed / (posts + removed)),
            posts + removed,
        )
    no_count = db.execute(
        "SELECT month, kind FROM threads WHERE removed_in_snapshot IS NULL"
    ).fetchall()
    for month, kind in no_count:
        assert (kind, "removed_share", "") not in _metrics(
            aggregate.compute_month(db, month)
        )


def _validation_file(tmp_path, sets: dict) -> Path:
    path = tmp_path / "validation.json"
    path.write_text(json.dumps({"model": JEV_MODEL, **sets}))
    return path


def _scores(accuracy: float) -> dict:
    return {"questions": {"work_mode": {"overall": {"n": 40, "accuracy": accuracy}}}}


def test_export_follows_contract(db, tmp_path, monkeypatch):
    monkeypatch.setattr(export, "MIN_N_SHARE", 0)
    features.build(db)
    aggregate.run(db, Namespace(month=None, dry_run=False, limit=None))
    path = _validation_file(
        tmp_path, {"holdout": _scores(0.8), "reference": _scores(0.9)}
    )
    data = export.build(db, path)

    (fetched,) = db.execute(
        "SELECT max(fetched_at) FROM threads WHERE fetched_at >= snapshot_at"
    ).fetchone()
    assert data["generated_at"] == fetched.astimezone(UTC).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    assert data["generated_at"] == export.build(db, path)["generated_at"]
    # The pending month is left out everywhere, even its complete hiring half.
    assert data["pending"] == [f"{PENDING:%Y-%m}"]
    assert data["months"] == [f"{t:%Y-%m}" for t in MONTHS if t != PENDING]
    assert data["latest_month"] == data["months"][-1]

    posts = data["metrics"]["posts.hiring"]
    assert set(posts) == {
        "label", "unit", "method", "description", "polarity", "sources",
        "comparable_from", "validation", "series",
    }  # fmt: skip
    assert posts["unit"] == "count" and posts["method"] == "count"
    assert posts["series"][0] == {"month": "2024-01", "value": 4, "n": 4}
    months = [p["month"] for p in posts["series"]]
    assert "2024-04" not in months and f"{PENDING:%Y-%m}" not in months
    for metric in data["metrics"].values():
        assert metric["unit"] in {"count", "share", "usd", "ratio", "score"}
        assert metric["method"] in {"count", "regex", "join", "jev"}
    assert data["metrics"]["new_company_share.hiring"]["polarity"] == 0

    work_mode = data["breakdowns"]["work_mode"]
    assert set(work_mode) == {
        "label", "method", "categories", "polarity", "sources", "comparable_from",
        "validation", "confidence", "series",
    }  # fmt: skip
    assert work_mode["categories"] == ["remote", "hybrid", "onsite", "unclear"]
    assert [p["month"] for p in work_mode["series"]] == [
        "2024-01",
        "2024-03",
        "2024-06",
    ]
    assert set(work_mode["series"][0]) == {"month", "n", "values"}
    assert work_mode["validation"] == {"set": "holdout", "n": 40, "accuracy": 0.8}
    assert work_mode["confidence"] is None
    assert data["breakdowns"]["industry"]["confidence"] == "rough"
    assert data["breakdowns"]["industry_known"]["confidence"] == "rough"
    assert data["breakdowns"]["stack"]["method"] == "vocab"
    assert data["breakdowns"]["stack"]["validation"] is None


def test_validation_falls_back_to_reference_then_null(db, tmp_path):
    reference = export.load_validation(
        _validation_file(tmp_path, {"reference": _scores(0.9)})
    )
    assert reference["work_mode"] == {"set": "reference", "n": 40, "accuracy": 0.9}
    # A holdout section with no scored posts for a question falls back per question.
    empty_holdout = {"questions": {"work_mode": {"overall": {"n": 0}}}}
    mixed = export.load_validation(
        _validation_file(
            tmp_path, {"holdout": empty_holdout, "reference": _scores(0.9)}
        )
    )
    assert mixed["work_mode"]["set"] == "reference"
    assert export.load_validation(tmp_path / "missing.json") == {}
    data = export.build(db, tmp_path / "missing.json")
    assert data["breakdowns"]["work_mode"]["validation"] is None


def _metric_db(tmp_path, rows: list[tuple]) -> duckdb.DuckDBPyConnection:
    con = connect(tmp_path / "metrics.duckdb")
    for row in rows:
        con.execute("INSERT INTO monthly_metrics VALUES (?, 'hiring', ?, ?, ?, ?)", row)
    return con


def test_min_n_omits_small_months(tmp_path):
    con = _metric_db(tmp_path, [
        (date(2020, 1, 1), "visa_share", "", 0.1, 49),
        (date(2020, 2, 1), "visa_share", "", 0.1, 50),
        (date(2020, 1, 1), "salary_min_median_usd", "", 150_000, 29),
        (date(2020, 2, 1), "salary_min_median_usd", "", 150_000, 30),
        (date(2020, 1, 1), "work_mode", "remote", 0.5, 49),
        (date(2020, 2, 1), "work_mode", "remote", 0.5, 50),
        (date(2020, 1, 1), "posts", "", 3, 3),
    ])  # fmt: skip
    data = export.build(con, tmp_path / "missing.json")
    assert [p["month"] for p in data["metrics"]["visa_share.hiring"]["series"]] == [
        "2020-02"
    ]
    salary = data["metrics"]["salary_min_median_usd.hiring"]["series"]
    assert [p["month"] for p in salary] == ["2020-02"]
    assert [p["month"] for p in data["breakdowns"]["work_mode"]["series"]] == [
        "2020-02"
    ]
    assert data["metrics"]["posts.hiring"]["series"][0]["value"] == 3


def test_comparable_from_drops_earlier_points(tmp_path):
    con = _metric_db(tmp_path, [
        (date(2015, 6, 1), "remote_token_share", "", 0.2, 100),
        (date(2015, 7, 1), "remote_token_share", "", 0.4, 100),
        (date(2013, 3, 1), "new_company_share", "", 0.5, 100),
        (date(2013, 4, 1), "new_company_share", "", 0.4, 100),
    ])  # fmt: skip
    data = export.build(con, tmp_path / "missing.json")
    remote = data["metrics"]["remote_token_share.hiring"]
    assert remote["comparable_from"] == "2015-07"
    assert [p["month"] for p in remote["series"]] == ["2015-07"]
    assert "July 2015" in remote["description"]
    new = data["metrics"]["new_company_share.hiring"]
    assert [p["month"] for p in new["series"]] == ["2013-04"]
    assert data["metrics"]["visa_share.hiring"]["comparable_from"] is None


def test_samples_are_hiring_only_deterministic_and_complete_only(db):
    features.build(db)
    samples = export.build_samples(db)
    assert samples == export.build_samples(db)
    assert all(p["kind"] == "hiring" for s in samples.values() for p in s["posts"])
    post = samples["2024-01"]["posts"][0]
    assert set(post) == {"id", "kind", "url", "header", "text", "answers"}
    assert post["url"] == f"https://news.ycombinator.com/item?id={post['id']}"
    assert len(post["text"]) <= 600
    assert post["answers"]["work_mode"] in {"remote", "hybrid", "onsite", "unclear"}
    assert isinstance(post["answers"]["stack"], list)
    hiring_snapshot = {
        post_id
        for (post_id,) in db.execute(
            "SELECT post_id FROM posts JOIN threads USING (thread_id) "
            "WHERE in_snapshot AND kind = 'hiring'"
        ).fetchall()
    }
    assert all(p["id"] in hiring_snapshot for s in samples.values() for p in s["posts"])


def test_sources(db):
    features.build(db)
    aggregate.run(db, Namespace(month=None, dry_run=False, limit=None))
    data = export.build(db)
    assert data["metrics"]["seekers_per_post.hiring"]["sources"] == [
        "hiring",
        "seeking",
    ]
    assert data["metrics"]["seeker_mood.seeking"]["sources"] == ["seeking"]
    assert data["breakdowns"]["stack"]["sources"] == ["hiring"]


def _answer_rows(con) -> list[tuple]:
    return con.execute(
        "SELECT * FROM answers WHERE method <> 'jev' ORDER BY post_id, question"
    ).fetchall()


def test_month_by_month_build_matches_full_build(db, tmp_path):
    features.build(db)
    full = _answer_rows(db)
    db.execute("DELETE FROM answers WHERE method <> 'jev'")
    # Newest first, so each earlier month's build has to refresh later months' joins.
    for t in reversed(MONTHS):
        features.build(db, t)
    assert _answer_rows(db) == full
