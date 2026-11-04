"""Deterministic answers (regex, vocab, joins) for hiring posts."""

import argparse
import json
from datetime import date

import duckdb

from sejr.features.company import company_name
from sejr.features.salary import salary_summary
from sejr.features.tokens import (
    interns_token,
    mentions_visa,
    onsite_token,
    remote_token,
)
from sejr.features.vocab import stack_terms

# Bump whenever a rule or the vocabulary changes; aggregate reads only this version.
VERSION = "features-1"

Answer = tuple[int, str, str, str, float | None, str | None, str | None, float | None]


def post_answers(post_id: int, text: str) -> list[Answer]:
    def row(
        question: str, method: str, value=None, label=None, probabilities=None
    ) -> Answer:
        return (post_id, question, method, VERSION, value, label, probabilities, None)

    low, high, currency = salary_summary(text)
    terms = stack_terms(text)
    rows = [
        row("salary_currency", "regex", label=currency),
        row("remote_token", "regex", float(remote_token(text))),
        row("onsite_token", "regex", float(onsite_token(text))),
        row("mentions_visa", "regex", float(mentions_visa(text))),
        row("interns_token", "regex", float(interns_token(text))),
        # One row per post holding every hit, so the breakdown reads like a Choice answer.
        row(
            "stack",
            "vocab",
            float(len(terms)),
            probabilities=json.dumps(dict.fromkeys(terms, 1.0)),
        ),
    ]
    if low is not None:
        rows.append(row("salary_min_usd", "regex", low))
    if high is not None:
        rows.append(row("salary_max_usd", "regex", high))
    if company := company_name(text):
        rows.append(row("company", "regex", label=company))
    return rows


# Only earlier months' in-snapshot posts are read, so adding later months never changes a row.
# A month with no earlier hiring thread (or no thread last month) gets no answer at all,
# rather than a meaningless "everyone is new".
JOIN_SQL = """
WITH company AS (
  SELECT a.post_id, a.label AS company, t.month, p.in_snapshot
  FROM answers a
  JOIN posts p USING (post_id)
  JOIN threads t USING (thread_id)
  WHERE a.question = 'company' AND a.method = 'regex' AND a.version = $version
    AND t.kind = 'hiring'
),
hiring_months AS (SELECT DISTINCT month FROM threads WHERE kind = 'hiring'),
targets AS (
  SELECT * FROM company WHERE $month IS NULL OR month = $month
)
SELECT post_id, 'new_company', 'join', $version,
       (NOT EXISTS (
          SELECT 1 FROM company e
          WHERE e.company = t.company AND e.month < t.month AND e.in_snapshot
       ))::DOUBLE,
       NULL, NULL, NULL
FROM targets t
WHERE EXISTS (SELECT 1 FROM hiring_months h WHERE h.month < t.month)
UNION ALL
SELECT post_id, 'returned_from_last_month', 'join', $version,
       (EXISTS (
          SELECT 1 FROM company e
          WHERE e.company = t.company AND e.month = t.month - INTERVAL 1 MONTH AND e.in_snapshot
       ))::DOUBLE,
       NULL, NULL, NULL
FROM targets t
WHERE EXISTS (SELECT 1 FROM hiring_months h WHERE h.month = t.month - INTERVAL 1 MONTH)
"""


INSERT_COLUMNS = """
INSERT INTO answers
SELECT unnest(?::BIGINT[]), unnest(?::VARCHAR[]), unnest(?::VARCHAR[]), unnest(?::VARCHAR[]),
       unnest(?::DOUBLE[]), unnest(?::VARCHAR[]), unnest(?::VARCHAR[])::JSON,
       unnest(?::DOUBLE[])
"""


def _hiring_posts(
    con: duckdb.DuckDBPyConnection, month: date | None
) -> list[tuple[int, str]]:
    return con.execute(
        """
        SELECT p.post_id, p.text
        FROM posts p JOIN threads t USING (thread_id)
        WHERE t.kind = 'hiring' AND ($month IS NULL OR t.month = $month)
        ORDER BY p.post_id
        """,
        {"month": month},
    ).fetchall()


def _delete(con: duckdb.DuckDBPyConnection, month: date | None) -> None:
    con.execute(
        """
        DELETE FROM answers
        WHERE version = $version AND method IN ('regex', 'vocab', 'join')
          AND post_id IN (
            SELECT p.post_id FROM posts p JOIN threads t USING (thread_id)
            WHERE t.kind = 'hiring' AND ($month IS NULL OR t.month = $month)
          )
        """,
        {"version": VERSION, "month": month},
    )


def build(con: duckdb.DuckDBPyConnection, month: date | None = None) -> int:
    """Rewrite this version's deterministic answers for one month (YYYY-MM-01) or all."""
    rows = [
        r
        for post_id, text in _hiring_posts(con, month)
        for r in post_answers(post_id, text)
    ]
    con.begin()
    _delete(con, month)
    if rows:
        # One statement over column lists: executemany is ~50x slower at 600k rows.
        con.execute(
            INSERT_COLUMNS, [list(column) for column in zip(*rows, strict=True)]
        )
    con.execute(f"INSERT INTO answers {JOIN_SQL}", {"version": VERSION, "month": month})
    con.commit()
    return len(rows)


def run(con: duckdb.DuckDBPyConnection, args: argparse.Namespace) -> None:
    month = date.fromisoformat(f"{args.month}-01") if args.month else None
    if args.dry_run:
        posts = _hiring_posts(con, month)[: args.limit or 20]
        for post_id, text in posts:
            print(post_id, post_answers(post_id, text))
        return
    count = build(con, month)
    print(f"features: {count} regex/vocab answers plus joins, version {VERSION}")
