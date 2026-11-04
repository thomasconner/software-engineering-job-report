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
from sejr.db import insert_rows
from sejr.features import VERSION as FEATURES_VERSION
from sejr.features.benefits import CATEGORIES as BENEFITS
from sejr.features.experience import BUCKETS
from sejr.features.region import REGIONS
from sejr.features.traits import STYLE_NAMES
from sejr.features.vocab import GROUP_TERMS, TERMS

Row = tuple[date, str, str, str, float, int]


@dataclass(frozen=True)
class AnswerMetric:
    metric: str
    kind: str
    question: str
    method: str
    expr: str = "avg(value)"
    counted: str = "value"  # the column whose non-null rows make up n


@dataclass(frozen=True)
class Breakdown:
    metric: str
    kind: str
    method: str
    categories: tuple[str, ...]
    question: str | None = None  # defaults to the metric id
    # Extra SQL condition on the answer's post, e.g. to split by another answer.
    post_filter: str = "TRUE"


SCALARS = [
    AnswerMetric("salary_disclosed_share", "hiring", "salary_currency", "regex",
                 "avg((label <> 'none')::DOUBLE)", "label"),
    AnswerMetric("salary_min_median_usd", "hiring", "salary_min_usd", "regex", "median(value)"),
    AnswerMetric("salary_max_median_usd", "hiring", "salary_max_usd", "regex", "median(value)"),
    AnswerMetric("remote_token_share", "hiring", "remote_token", "regex"),
    AnswerMetric("onsite_token_share", "hiring", "onsite_token", "regex"),
    AnswerMetric("visa_share", "hiring", "mentions_visa", "regex"),
    AnswerMetric("new_company_share", "hiring", "new_company", "join"),
    AnswerMetric("returning_company_share", "hiring", "returned_from_last_month", "join"),
    AnswerMetric("ai_native_share", "hiring", "ai_native", "jev"),
    AnswerMetric("new_grad_share", "hiring", "new_grad", "jev"),
    AnswerMetric("eng_leadership_share", "hiring", "eng_leadership", "jev"),
    AnswerMetric("interns_token_share", "hiring", "interns_token", "regex"),
    AnswerMetric("seeker_mood", "seeking", "seeker_mood", "jev"),
    # Score levels are keyed "0".."4"; 0 is Discouraged and 1 is Strained.
    AnswerMetric("seeker_strained_share", "seeking", "seeker_mood", "jev",
                 """avg(coalesce(json_extract(probabilities, '$."0"')::DOUBLE, 0)
                      + coalesce(json_extract(probabilities, '$."1"')::DOUBLE, 0))""",
                 "probabilities"),
    # Among seekers whose Location line names a region.
    AnswerMetric("seeker_us_share", "seeking", "region", "regex",
                 "avg((label = 'us')::DOUBLE) FILTER (WHERE label <> 'unknown')",
                 "nullif(label, 'unknown')"),
    # What employers ask for and how posts read. years_required and office_days always have
    # a row (NULL when the post states none), so their shares count every post.
    AnswerMetric("years_required_median", "hiring", "years_required", "regex", "median(value)"),
    AnswerMetric("years_required_share", "hiring", "years_required", "regex",
                 "avg((value IS NOT NULL)::DOUBLE)", "post_id"),
    AnswerMetric("degree_required_share", "hiring", "degree", "regex",
                 "avg((label = 'required')::DOUBLE)", "label"),
    AnswerMetric("degree_optional_share", "hiring", "degree", "regex",
                 "avg((label = 'optional')::DOUBLE)", "label"),
    AnswerMetric("post_length_median", "hiring", "post_length", "count", "median(value)"),
    AnswerMetric("interview_style_share", "hiring", "interview_style", "regex",
                 "avg((value > 0)::DOUBLE)"),
    AnswerMetric("office_days_share", "hiring", "office_days", "regex",
                 "avg((value IS NOT NULL)::DOUBLE)", "post_id"),
]  # fmt: skip

SENIORITY = ("junior", "mid", "senior", "staff_plus", "unspecified")
INDUSTRY = ("ai_ml", "devtools_infra", "fintech", "health", "climate_energy", "security",
            "commerce", "media_consumer", "enterprise_saas", "hardware_robotics", "other",
            "unstated")  # fmt: skip
AI_NATIVE_POSTS = """post_id IN (
  SELECT post_id FROM answers
  WHERE question = 'ai_native' AND method = 'jev' AND version = $version AND value {} 0.5
)"""

BREAKDOWNS = [
    Breakdown("work_mode", "hiring", "jev", ("remote", "hybrid", "onsite", "unclear")),
    Breakdown("seniority", "hiring", "jev", SENIORITY),
    Breakdown("industry", "hiring", "jev", INDUSTRY),
    Breakdown("funding_stage", "hiring", "jev",
              ("bootstrapped", "seed", "series_a", "series_b", "series_c_plus", "public_or_large",
               "venture_unspecified", "unknown")),
    Breakdown("stack", "hiring", "vocab", tuple(TERMS)),
    *(Breakdown(f"stack_{group}", "hiring", "vocab", terms, "stack")
      for group, terms in GROUP_TERMS.items()),
    Breakdown("benefits", "hiring", "regex", BENEFITS),
    # Among posts that state years: the post's smallest number, bucketed.
    Breakdown("years_required", "hiring", "regex", tuple(name for name, _, _ in BUCKETS),
              post_filter="a.value IS NOT NULL"),
    Breakdown("interview_style", "hiring", "regex", STYLE_NAMES),
    # Hiring headers can name several regions, so these shares don't sum to 1.
    Breakdown("region", "hiring", "regex", REGIONS),
    Breakdown("seeker_region", "seeking", "regex", REGIONS, "region"),
    # Cross-tab: seniority mix of posts judged AI-native (ai_native >= 0.5) and of the rest.
    Breakdown("seniority_ai_native", "hiring", "jev", SENIORITY, "seniority",
              AI_NATIVE_POSTS.format(">=")),
    Breakdown("seniority_not_ai_native", "hiring", "jev", SENIORITY, "seniority",
              AI_NATIVE_POSTS.format("<")),
]  # fmt: skip
# Industry shares among posts that say what the company does, derived from `industry`.
INDUSTRY_KNOWN = Breakdown(
    "industry_known", "hiring", "jev", tuple(c for c in INDUSTRY if c != "unstated")
)
# Jev metrics publish a month only when nearly every post has an answer, so a half-run
# classify can't pass for a trend.
JEV_COVERAGE = 0.98

# Metrics counted straight from posts and replies, with method 'count'.
COUNT_METRICS = ("posts", "removed_share", "seekers_per_post", "replies_per_post")

# A thread fetched before its snapshot closed is still filling up, so it is skipped.
COMPLETE = "fetched_at >= snapshot_at"
SNAPSHOT = f"""
WITH snapshot AS (
  SELECT p.post_id, t.kind
  FROM posts p JOIN threads t USING (thread_id)
  WHERE p.in_snapshot AND t.month = $month AND t.{COMPLETE}
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
        "question": m.question or m.metric,
        "method": m.method,
        "version": version_for(m.method),
    }


def _as_date(month: date | str) -> date:
    return month if isinstance(month, date) else date.fromisoformat(f"{month[:7]}-01")


def _count_rows(con: duckdb.DuckDBPyConnection, month: date) -> list[Row]:
    live = dict(
        con.execute(
            SNAPSHOT
            + "SELECT kind, count(*) FROM snapshot GROUP BY kind ORDER BY kind",
            {"month": month},
        ).fetchall()
    )
    removed = dict(
        con.execute(
            f"""
            SELECT kind, sum(removed_in_snapshot)::INTEGER FROM threads
            WHERE month = $month AND {COMPLETE} AND removed_in_snapshot IS NOT NULL
            GROUP BY kind ORDER BY kind
            """,
            {"month": month},
        ).fetchall()
    )
    # Counts include posts deleted after the window: how many survive depends on how long
    # after the window a thread was fetched (years for history, days for new months).
    submitted = {kind: n + removed.get(kind, 0) for kind, n in live.items()}
    for kind, gone in removed.items():
        submitted.setdefault(kind, gone)
    rows: list[Row] = [
        (month, kind, "posts", "", float(n), n)
        for kind, n in sorted(submitted.items())
        if n
    ]
    rows += [
        (month, kind, "removed_share", "", gone / submitted[kind], submitted[kind])
        for kind, gone in removed.items()
        if submitted[kind]
    ]
    hiring = submitted.get("hiring", 0)
    if not hiring:
        return rows
    if seeking := submitted.get("seeking", 0):
        rows.append((month, "hiring", "seekers_per_post", "", seeking / hiring, hiring))
    if not live.get("hiring"):
        return rows
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
    rows.append((month, "hiring", "replies_per_post", "", replies, live["hiring"]))
    return rows


# Fewer located seekers than this and the US share is too noisy to scale the ratio by; the
# same floor as export.MIN_N_SHARE.
MIN_KNOWN_SEEKERS = 50


def _us_ratio_rows(
    con: duckdb.DuckDBPyConnection, month: date, counts: list[Row]
) -> list[Row]:
    """US-located seekers per hiring post open to US workers, on the submitted basis.

    Region needs the text, which removed posts don't have, so the US shares come from live
    posts and scale seekers_per_post. Both shares leave out posts whose location is unknown
    (no recognized seeker location; a header with no place and no "remote"), so both
    assume those split like the rest, as removed posts are assumed to. Counting live posts
    directly would let each thread's removed share, which depends on fetch age, move it.
    """
    ratio = next((r[4] for r in counts if r[2] == "seekers_per_post"), None)
    if ratio is None:
        return []
    us_seekers, known_seekers, open_posts, known_hiring = con.execute(
        SNAPSHOT
        + """
        SELECT
          count(*) FILTER (WHERE s.kind = 'seeking' AND a.question = 'region'
                           AND a.label = 'us'),
          count(*) FILTER (WHERE s.kind = 'seeking' AND a.question = 'region'
                           AND a.label <> 'unknown'),
          count(*) FILTER (WHERE s.kind = 'hiring' AND a.question = 'open_to_us'
                           AND a.value = 1),
          count(*) FILTER (WHERE s.kind = 'hiring' AND a.question = 'open_to_us')
        FROM snapshot s JOIN answers a USING (post_id)
        WHERE a.method = 'regex' AND a.version = $version
        """,
        {"month": month, "version": FEATURES_VERSION},
    ).fetchone()
    if known_seekers < MIN_KNOWN_SEEKERS or not open_posts:
        return []
    us_ratio = ratio * (us_seekers / known_seekers) / (open_posts / known_hiring)
    return [(month, "hiring", "seekers_per_post_us", "", us_ratio, open_posts)]


def _covered(
    con: duckdb.DuckDBPyConnection, month: date, m: AnswerMetric | Breakdown
) -> bool:
    """Deterministic answers always cover the month; Jev ones need JEV_COVERAGE of posts."""
    if m.method != "jev":
        return True
    answered, posts = con.execute(
        SNAPSHOT
        + """
        SELECT count(DISTINCT a.post_id), (SELECT count(*) FROM snapshot WHERE kind = $kind)
        FROM answers a JOIN snapshot s USING (post_id)
        WHERE s.kind = $kind AND a.question = $question AND a.method = $method
          AND a.version = $version
        """,
        _params(month, m),
    ).fetchone()
    return bool(posts) and answered >= JEV_COVERAGE * posts


def _scalar_rows(con: duckdb.DuckDBPyConnection, month: date) -> list[Row]:
    rows: list[Row] = []
    for m in SCALARS:
        if not _covered(con, month, m):
            continue
        value, n = con.execute(
            SNAPSHOT + f"SELECT {m.expr}, count({m.counted}) {ANSWERS}",
            _params(month, m),
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
        if not _covered(con, month, b):
            continue
        answers = con.execute(
            SNAPSHOT
            + f"SELECT a.probabilities, a.label {ANSWERS} AND {b.post_filter} ORDER BY a.post_id",
            _params(month, b),
        ).fetchall()
        if not answers:
            continue
        # Expected shares: the mean probability of each category across posts.
        distributions = [_distribution(p, label) for p, label in answers]
        totals = {
            c: sum(float(d.get(c, 0.0)) for d in distributions) for c in b.categories
        }
        n = len(distributions)
        rows += [
            (month, b.kind, b.metric, c, total / n, n) for c, total in totals.items()
        ]
        if b.metric == "industry":
            # n here is an expected count: the summed probability that a post's sector is
            # stated, rounded. Summing the known categories (not n - unstated) keeps the
            # shares at 1 even when a distribution doesn't.
            k = INDUSTRY_KNOWN
            if (known := sum(totals[c] for c in k.categories)) > 0:
                rows += [
                    (month, k.kind, k.metric, c, totals[c] / known, round(known))
                    for c in k.categories
                ]
    return rows


def compute_month(con: duckdb.DuckDBPyConnection, month: date | str) -> list[Row]:
    month = _as_date(month)
    counts = _count_rows(con, month)
    return (
        counts
        + _us_ratio_rows(con, month, counts)
        + _scalar_rows(con, month)
        + _breakdown_rows(con, month)
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
    insert_rows(con, "monthly_metrics", rows)
    con.commit()
    print(f"aggregate: {len(rows)} rows for {len(months)} months")
