from argparse import Namespace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import duckdb
import pytest
from conftest import CLASSIFIED, MONTHS, NO_HIRING, NO_SEEKING

from sejr import aggregate, export, features
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
        WHERE a.question = 'work_mode' AND a.version = 'jev-1.13.0' AND p.in_snapshot
          AND t.month = $m
        """,
        {"m": month},
    ).fetchone()
    assert metrics[("hiring", "work_mode", "hybrid")][0] == pytest.approx(expected)


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
        "INSERT INTO threads VALUES (?, 'hiring', ?, 'Ask HN: Who is hiring?', ?, ?)",
        [thread_id, month, created, created + timedelta(days=7)],
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


def test_export_follows_contract(db):
    features.build(db)
    aggregate.run(db, Namespace(month=None, dry_run=False, limit=None))
    data = export.build(db, generated_at=datetime(2026, 11, 9, 12, tzinfo=UTC))

    assert data["generated_at"] == "2026-11-09T12:00:00Z"
    assert data["latest_month"] == "2024-07"
    assert data["months"] == [f"{t:%Y-%m}" for t in MONTHS]
    posts = data["metrics"]["posts.hiring"]
    assert set(posts) == {"label", "unit", "method", "description", "series"}
    assert posts["unit"] == "count" and posts["method"] == "count"
    assert posts["series"][0] == {"month": "2024-01", "value": 4, "n": 4}
    assert "2024-04" not in [p["month"] for p in posts["series"]]
    for metric in data["metrics"].values():
        assert metric["unit"] in {"count", "share", "usd", "ratio", "score"}
        assert metric["method"] in {"count", "regex", "join", "jev"}

    work_mode = data["breakdowns"]["work_mode"]
    assert set(work_mode) == {"label", "method", "categories", "series"}
    assert work_mode["categories"] == ["remote", "hybrid", "onsite", "unclear"]
    assert [p["month"] for p in work_mode["series"]] == [
        "2024-01",
        "2024-03",
        "2024-06",
    ]
    assert set(work_mode["series"][0]) == {"month", "n", "values"}
    assert data["breakdowns"]["stack"]["method"] == "vocab"
