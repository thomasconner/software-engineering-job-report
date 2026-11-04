"""Jev answers in DuckDB and their durable copy, data/answers/<model>/<YYYY-MM>.parquet.

Each Parquet row is an `answers` row plus `qset`, the question-set hash it was answered
under, so a fresh checkout knows which posts are done and a question edit re-runs them.
"""

from pathlib import Path

import duckdb

from sejr.classify.jev import AnswerRow
from sejr.config import JEV_MODEL

ANSWER_TYPES = ["BIGINT", "VARCHAR", "VARCHAR", "VARCHAR", "DOUBLE", "VARCHAR", "VARCHAR", "DOUBLE"]  # fmt: skip


def model_dir(answers_dir: Path) -> Path:
    return answers_dir / JEV_MODEL


def parquet_files(answers_dir: Path) -> list[str]:
    return sorted(str(f) for f in model_dir(answers_dir).glob("*.parquet"))


def read_qsets(con: duckdb.DuckDBPyConnection, answers_dir: Path) -> dict[int, str]:
    """post_id → question-set hash, for every post in the durable copy."""
    files = parquet_files(answers_dir)
    if not files:
        return {}
    sql = "SELECT DISTINCT post_id, qset FROM read_parquet(?)"
    return dict(con.execute(sql, [files]).fetchall())


def load(con: duckdb.DuckDBPyConnection, answers_dir: Path) -> None:
    """Copy the durable answers into `answers`, replacing those posts' Jev rows."""
    files = parquet_files(answers_dir)
    if not files:
        return
    con.begin()
    con.execute(
        "CREATE OR REPLACE TEMP TABLE jev_loaded AS SELECT * FROM read_parquet(?)",
        [files],
    )
    con.execute(
        "DELETE FROM answers WHERE method = 'jev' "
        "AND post_id IN (SELECT post_id FROM jev_loaded)"
    )
    con.execute("INSERT INTO answers SELECT * EXCLUDE (qset) FROM jev_loaded")
    con.execute("DROP TABLE jev_loaded")
    con.commit()


def replace(
    con: duckdb.DuckDBPyConnection, post_ids: list[int], rows: list[AnswerRow]
) -> None:
    """Replace every Jev row of `post_ids` with `rows`, in one set-based statement."""
    columns = [list(c) for c in zip(*rows)] if rows else [[] for _ in ANSWER_TYPES]
    # One unnest per column zips the lists back into rows inside DuckDB, so a million
    # rows go in as eight list parameters instead of a million executemany calls.
    unnests = ", ".join(f"unnest(?::{t}[])" for t in ANSWER_TYPES)
    con.begin()
    con.execute(
        "DELETE FROM answers WHERE method = 'jev' "
        "AND post_id IN (SELECT unnest(?::BIGINT[]))",
        [post_ids],
    )
    con.execute(f"INSERT INTO answers SELECT {unnests}", columns)
    con.commit()


def save(
    con: duckdb.DuckDBPyConnection,
    answers_dir: Path,
    months: set[str],
    qsets: dict[int, str],
) -> None:
    """Rewrite the Parquet file of each month in `months` from `answers`."""
    out = model_dir(answers_dir)
    out.mkdir(parents=True, exist_ok=True)
    con.execute(
        "CREATE OR REPLACE TEMP TABLE jev_qsets AS "
        "SELECT unnest(?::BIGINT[]) AS post_id, unnest(?::VARCHAR[]) AS qset",
        [list(qsets), list(qsets.values())],
    )
    for month in sorted(months):
        con.execute(
            """
            CREATE OR REPLACE TEMP TABLE jev_month AS
            SELECT a.*, q.qset
            FROM answers a
            JOIN jev_qsets q USING (post_id)
            JOIN posts p USING (post_id)
            JOIN threads t USING (thread_id)
            WHERE a.method = 'jev' AND a.version = ? AND strftime(t.month, '%Y-%m') = ?
            ORDER BY a.post_id, a.question
            """,
            [JEV_MODEL, month],
        )
        path = out / f"{month}.parquet"
        tmp = path.with_suffix(".parquet.tmp")
        con.execute(f"COPY jev_month TO '{tmp}' (FORMAT parquet)")
        tmp.replace(path)
    con.execute("DROP TABLE IF EXISTS jev_month")
    con.execute("DROP TABLE jev_qsets")
