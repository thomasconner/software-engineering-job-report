"""monthly_metrics → site/data/metrics.json, per the contract in docs/architecture.md."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from sejr.aggregate import BREAKDOWNS, COUNT_METRICS, INDUSTRY_KNOWN, SCALARS
from sejr.config import SITE_DATA_DIR

# key → (label, unit, description). Descriptions are written for a newspaper reader.
SCALAR_TEXT: dict[str, tuple[str, str, str]] = {
    "posts.hiring": (
        "Companies hiring",
        "count",
        (
            "Job posts in the monthly Hacker News “Who is hiring?” thread during its first 7 days. "
            "One post often covers several roles, so this counts employers, not jobs."
        ),
    ),
    "posts.seeking": (
        "People looking for work",
        "count",
        "Posts in the monthly “Who wants to be hired?” thread during its first 7 days.",
    ),
    "seekers_per_post.hiring": (
        "Job seekers per hiring post",
        "ratio",
        (
            "People posting that they want work, divided by companies posting that they are hiring, "
            "in the same month."
        ),
    ),
    "replies_per_post.hiring": (
        "Replies per job post",
        "ratio",
        "Average number of direct replies a job post got in its first 7 days.",
    ),
    "salary_disclosed_share.hiring": (
        "Posts that show pay",
        "share",
        (
            "Share of job posts that state a yearly salary figure or range, in any currency. "
            "Hourly rates, equity and funding amounts don’t count."
        ),
    ),
    "salary_min_median_usd.hiring": (
        "Typical bottom of the pay range",
        "usd",
        "Median of the lowest yearly salary quoted, among posts that give pay in US dollars.",
    ),
    "salary_max_median_usd.hiring": (
        "Typical top of the pay range",
        "usd",
        "Median of the highest yearly salary quoted, among posts that give pay in US dollars.",
    ),
    "remote_token_share.hiring": (
        "Posts that say remote",
        "share",
        "Share of job posts whose first line mentions remote work (and doesn’t rule it out).",
    ),
    "onsite_token_share.hiring": (
        "Posts that say onsite",
        "share",
        "Share of job posts whose first line says the job is onsite.",
    ),
    "visa_share.hiring": (
        "Posts that offer visa help",
        "share",
        (
            "Share of job posts that offer visa sponsorship or transfers. Posts that say they "
            "can’t sponsor are not counted."
        ),
    ),
    "new_company_share.hiring": (
        "First-time posters",
        "share",
        (
            "Share of companies posting that had never appeared in an earlier month’s thread. "
            "Early months run high because there is little history to compare against."
        ),
    ),
    "returning_company_share.hiring": (
        "Back from last month",
        "share",
        "Share of companies posting that also posted the month before.",
    ),
    "ai_native_share.hiring": (
        "AI-native companies",
        "share",
        (
            "Expected share of job posts from companies whose product is built on AI or machine "
            "learning, as judged by a language model reading each post."
        ),
    ),
    "new_grad_share.hiring": (
        "Open to new grads",
        "share",
        (
            "Expected share of job posts open to new graduates or junior engineers, as judged by a "
            "language model reading each post."
        ),
    ),
    "seeker_mood.seeking": (
        "Job seeker mood",
        "score",
        (
            "Average mood of “Who wants to be hired?” posts on a 0 (discouraged) to 4 (upbeat) "
            "scale, as judged by a language model reading each post."
        ),
    ),
    "seeker_strained_share.seeking": (
        "Job seekers under strain",
        "share",
        (
            "Expected share of “Who wants to be hired?” posts that sound discouraged or strained: "
            "a long search, a layoff, urgency or money worries, as judged by a language model."
        ),
    ),
    "eng_leadership_share.hiring": (
        "Hiring engineering leads",
        "share",
        (
            "Expected share of job posts hiring engineering managers or leads, as judged by a "
            "language model reading each post."
        ),
    ),
    "interns_token_share.hiring": (
        "Posts that mention interns",
        "share",
        "Share of job posts that mention interns or internships anywhere in the text.",
    ),
}

BREAKDOWN_LABELS = {
    "work_mode": "How companies want people to work",
    "seniority": "Which levels companies are hiring",
    "industry": "What hiring companies do",
    "industry_known": "What hiring companies do, among posts that say",
    "funding_stage": "How far along hiring companies are",
    "stack": "Technologies job posts mention",
    "seniority_ai_native": "Which levels AI-native companies are hiring",
    "seniority_not_ai_native": "Which levels other companies are hiring",
}


def _method(key: str) -> str:
    answer_methods = {f"{m.metric}.{m.kind}": m.method for m in SCALARS}
    return answer_methods.get(key) or (
        "count" if key.split(".")[0] in COUNT_METRICS else ""
    )


def _month(d) -> str:
    return d.strftime("%Y-%m")


def _number(value: float, unit: str) -> float | int:
    if unit in ("count", "usd") and float(value).is_integer():
        return int(value)
    return round(value, 4)


def build(con: duckdb.DuckDBPyConnection, generated_at: datetime | None = None) -> dict:
    rows = con.execute(
        "SELECT month, kind, metric, category, value, n FROM monthly_metrics "
        "WHERE value IS NOT NULL ORDER BY month, kind, metric, category"
    ).fetchall()
    months = sorted({_month(r[0]) for r in rows})

    metrics = {
        key: {"label": label, "unit": unit, "method": _method(key), "description": description,
              "series": []}
        for key, (label, unit, description) in SCALAR_TEXT.items()
    }  # fmt: skip
    breakdowns = {
        b.metric: {"label": BREAKDOWN_LABELS[b.metric], "method": b.method,
                   "categories": list(b.categories), "series": []}
        for b in [*BREAKDOWNS, INDUSTRY_KNOWN]
    }  # fmt: skip
    points: dict[tuple[str, str], dict] = {}

    for month, kind, metric, category, value, n in rows:
        if not category:
            key = f"{metric}.{kind}"
            if key in metrics:
                unit = metrics[key]["unit"]
                metrics[key]["series"].append(
                    {"month": _month(month), "value": _number(value, unit), "n": n}
                )
        elif metric in breakdowns and category in breakdowns[metric]["categories"]:
            point = points.get((metric, _month(month)))
            if point is None:
                point = {"month": _month(month), "n": n, "values": {}}
                points[(metric, _month(month))] = point
                breakdowns[metric]["series"].append(point)
            point["values"][category] = round(value, 4)

    generated_at = generated_at or datetime.now(UTC)
    return {
        "generated_at": generated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "latest_month": months[-1] if months else None,
        "months": months,
        "metrics": metrics,
        "breakdowns": breakdowns,
    }


def write(data: dict, path: Path = SITE_DATA_DIR / "metrics.json") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return path


def run(con: duckdb.DuckDBPyConnection, args: argparse.Namespace) -> None:
    data = build(con)
    if args.dry_run:
        print(json.dumps(data, indent=2, ensure_ascii=False)[:5000])
        return
    path = write(data)
    print(f"export: {len(data['months'])} months → {path}")
