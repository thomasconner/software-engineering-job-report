"""answers → monthly_metrics, one month at a time and point-in-time.

compute_month(t) reads only in-snapshot posts from month t's threads and their answers.
Cross-month facts (new or returning company) arrive as join answers that were built
from earlier months only, so nothing here can see the future.
"""

import argparse
import json
from dataclasses import dataclass
from datetime import date

import duckdb

from sejr import config
from sejr.features import VERSION as FEATURES_VERSION
from sejr.features.vocab import TERMS

Row = tuple[date, str, str, str, float, int]


@dataclass(frozen=True)
class AnswerMetric:
    metric: str
    kind: str
    question: str
    method: str
    expr: str = "avg(value)"


@dataclass(frozen=True)
class Breakdown:
    metric: str
    kind: str
    question: str
    method: str
    categories: tuple[str, ...]


SCALARS = [
    AnswerMetric("salary_disclosed_share", "hiring", "salary_currency", "regex",
                 "avg((label <> 'none')::DOUBLE)"),
    AnswerMetric("salary_min_median_usd", "hiring", "salary_min_usd", "regex", "median(value)"),
    AnswerMetric("salary_max_median_usd", "hiring", "salary_max_usd", "regex", "median(value)"),
    AnswerMetric("remote_token_share", "hiring", "remote_token", "regex"),
    AnswerMetric("onsite_token_share", "hiring", "onsite_token", "regex"),
    AnswerMetric("visa_share", "hiring", "mentions_visa", "regex"),
    AnswerMetric("new_company_share", "hiring", "new_company", "join"),
    AnswerMetric("returning_company_share", "hiring", "returned_from_last_month", "join"),
    AnswerMetric("ai_native_share", "hiring", "ai_native", "jev"),
    AnswerMetric("new_grad_share", "hiring", "new_grad", "jev"),
    AnswerMetric("seeker_mood", "seeking", "seeker_mood", "jev"),
]  # fmt: skip

BREAKDOWNS = [
    Breakdown("work_mode", "hiring", "work_mode", "jev", ("remote", "hybrid", "onsite", "unclear")),
    Breakdown("seniority", "hiring", "seniority", "jev",
              ("junior", "mid", "senior", "staff_plus", "unspecified")),
    Breakdown("industry", "hiring", "industry", "jev",
              ("ai_ml", "devtools_infra", "fintech", "health", "climate_energy", "security",
               "commerce", "media_consumer", "enterprise_saas", "hardware_robotics", "other")),
    Breakdown("funding_stage", "hiring", "funding_stage", "jev",
              ("bootstrapped", "seed", "series_a", "series_b", "series_c_plus", "public_or_large",
               "unknown")),
    Breakdown("stack", "hiring", "stack", "vocab", tuple(TERMS)),
]  # fmt: skip

# Metrics counted straight from posts and replies, with method 'count'.
COUNT_METRICS = ("posts", "seekers_per_post", "replies_per_post")

SNAPSHOT = """
WITH snapshot AS (
  SELECT p.post_id, t.kind
  FROM posts p JOIN threads t USING (thread_id)
  WHERE p.in_snapshot AND t.month = $month
)
"""

ANSWERS = """
FROM answers a JOIN snapshot s USING (post_id)
WHERE s.kind = $kind AND a.question = $question AND a.method = $method AND a.version = $version
"""


def version_for(method: str) -> str:
    return config.JEV_MODEL if method == "jev" else FEATURES_VERSION


def _params(month: date, m: AnswerMetric | Breakdown) -> dict:
    return {
        "month": month,
        "kind": m.kind,
        "question": m.question,
        "method": m.method,
        "version": version_for(m.method),
    }


def _as_date(month: date | str) -> date:
    return month if isinstance(month, date) else date.fromisoformat(f"{month[:7]}-01")


def _count_rows(con: duckdb.DuckDBPyConnection, month: date) -> list[Row]:
    posts = dict(
        con.execute(
            SNAPSHOT
            + "SELECT kind, count(*) FROM snapshot GROUP BY kind ORDER BY kind",
            {"month": month},
        ).fetchall()
    )
    rows: list[Row] = [
        (month, kind, "posts", "", float(n), n) for kind, n in posts.items()
    ]
    hiring = posts.get("hiring", 0)
    if not hiring:
        return rows
    if seeking := posts.get("seeking", 0):
        rows.append((month, "hiring", "seekers_per_post", "", seeking / hiring, hiring))
    (replies,) = con.execute(
        SNAPSHOT
        + """
        SELECT avg(coalesce(r.n, 0))
        FROM snapshot s
        LEFT JOIN (
          SELECT post_id, count(*) AS n FROM replies
          WHERE depth = 1 AND in_snapshot
          GROUP BY post_id
        ) r USING (post_id)
        WHERE s.kind = 'hiring'
        """,
        {"month": month},
    ).fetchone()
    rows.append((month, "hiring", "replies_per_post", "", replies, hiring))
    return rows


def _scalar_rows(con: duckdb.DuckDBPyConnection, month: date) -> list[Row]:
    rows: list[Row] = []
    for m in SCALARS:
        value, n = con.execute(
            SNAPSHOT + f"SELECT {m.expr}, count(*) {ANSWERS}", _params(month, m)
        ).fetchone()
        if n:
            rows.append((month, m.kind, m.metric, "", value, n))
    return rows


def _distribution(probabilities: str | None, label: str | None) -> dict[str, float]:
    if probabilities:
        return json.loads(probabilities)
    return {label: 1.0} if label else {}


def _breakdown_rows(con: duckdb.DuckDBPyConnection, month: date) -> list[Row]:
    rows: list[Row] = []
    for b in BREAKDOWNS:
        answers = con.execute(
            SNAPSHOT + f"SELECT a.probabilities, a.label {ANSWERS} ORDER BY a.post_id",
            _params(month, b),
        ).fetchall()
        if not answers:
            continue
        # Expected shares: the mean probability of each category across posts.
        distributions = [_distribution(p, label) for p, label in answers]
        n = len(distributions)
        for category in b.categories:
            share = sum(float(d.get(category, 0.0)) for d in distributions) / n
            rows.append((month, b.kind, b.metric, category, share, n))
    return rows


def compute_month(con: duckdb.DuckDBPyConnection, month: date | str) -> list[Row]:
    month = _as_date(month)
    return (
        _count_rows(con, month) + _scalar_rows(con, month) + _breakdown_rows(con, month)
    )


def run(con: duckdb.DuckDBPyConnection, args: argparse.Namespace) -> None:
    only = _as_date(args.month) if args.month else None
    months = [
        m
        for (m,) in con.execute(
            "SELECT DISTINCT month FROM threads WHERE $month IS NULL OR month = $month ORDER BY month",
            {"month": only},
        ).fetchall()
    ]
    rows = [row for month in months for row in compute_month(con, month)]
    if args.dry_run:
        for row in rows:
            print(*row, sep="\t")
        return
    con.begin()
    con.execute(
        "DELETE FROM monthly_metrics WHERE $month IS NULL OR month = $month",
        {"month": only},
    )
    if rows:
        con.executemany("INSERT INTO monthly_metrics VALUES (?, ?, ?, ?, ?, ?)", rows)
    con.commit()
    print(f"aggregate: {len(rows)} rows for {len(months)} months")
