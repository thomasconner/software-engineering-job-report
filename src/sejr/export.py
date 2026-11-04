"""monthly_metrics → site/data/metrics.json, per the contract in docs/architecture.md."""

import argparse
import json
from datetime import UTC
from pathlib import Path

import duckdb

from sejr import noise
from sejr.aggregate import BREAKDOWNS, COMPLETE, COUNT_METRICS, INDUSTRY_KNOWN, SCALARS
from sejr.config import EXTERNAL_DIR, JEV_MODEL, SITE_DATA_DIR
from sejr.external import build_section as build_external

VALIDATION_PATH = SITE_DATA_DIR / "validation.json"
from sejr.features import VERSION as FEATURES_VERSION
from sejr.features.tokens import header_line
from sejr.features.vocab import GROUP_TERMS

# key → (label, unit, description). Descriptions are written for a newspaper reader.
SCALAR_TEXT: dict[str, tuple[str, str, str]] = {
    "removed_share.hiring": (
        "Hiring posts later removed",
        "share",
        (
            "Share of hiring posts from the first 7 days that were deleted or killed before we "
            "fetched the thread. It depends on how long after the window we fetched (years for "
            "old months, about a day for new ones), so it is for the methodology note only and "
            "not comparable across months."
        ),
    ),
    "removed_share.seeking": (
        "Job seeker posts later removed",
        "share",
        (
            "Share of “Who wants to be hired?” posts from the first 7 days that were deleted or "
            "killed before we fetched the thread. It depends on how long after the window we "
            "fetched, so it is for the methodology note only and not comparable across months."
        ),
    ),
    "posts.hiring": (
        "Hiring posts",
        "count",
        (
            "Top-level posts in the first 7 days of the monthly Hacker News “Who is hiring?” "
            "thread, including ones later deleted. One post often covers several roles, so this "
            "counts posts, not jobs."
        ),
    ),
    "posts.seeking": (
        "People looking for work",
        "count",
        (
            "Top-level posts in the first 7 days of the monthly “Who wants to be hired?” "
            "thread, including ones later deleted."
        ),
    ),
    "seekers_per_post.hiring": (
        "Job seekers per hiring post",
        "ratio",
        (
            "Posts from people who want work divided by posts from companies hiring, in the "
            "same month. Both counts include posts later deleted."
        ),
    ),
    "seekers_per_post_us.hiring": (
        "US job seekers per hiring post open to US workers",
        "ratio",
        (
            "Job seekers per hiring post, counting only seekers whose Location line is in the "
            "US and hiring posts whose first line names a US place or offers remote work US "
            "workers can take (no region stated, or the US, North America, the Americas, "
            "worldwide or US time zones). Both counts include posts later deleted. Deleted "
            "posts, seekers whose location we can't place, and hiring posts that name no place "
            "and don't mention remote work are assumed to split the same way as the rest. "
            "Shown only when at least 50 seekers have a known location."
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
        (
            "Median across posts of each post’s typical low end of pay (the median of its "
            "ranges’ lows), among posts that give yearly pay in US dollars."
        ),
    ),
    "salary_max_median_usd.hiring": (
        "Typical top of the pay range",
        "usd",
        (
            "Median across posts of each post’s typical high end of pay (the median of its "
            "ranges’ highs), among posts that give yearly pay in US dollars."
        ),
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
        "New or returning after two years",
        "share",
        (
            "Share of companies posting that had not posted in any of the previous 24 months’ "
            "threads."
        ),
    ),
    "returning_company_share.hiring": (
        "Back from last month",
        "share",
        "Share of companies posting that also posted the month before.",
    ),
    "ai_native_share.hiring": (
        "Posts describing an AI product",
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
    "seeker_us_share.seeking": (
        "Job seekers in the US",
        "share",
        (
            "Share of “Who wants to be hired?” posts whose Location line is in the US, among "
            "posts whose Location line names a place we recognize."
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
    # What employers ask for, and how the posts themselves read (features-4).
    "years_required_median.hiring": (
        "Typical years of experience asked for",
        "years",
        (
            "Median across posts of the fewest years of experience each post asks for "
            "(“3-5 years” counts as 3; a post with several roles counts its lowest), "
            "among posts that state a number. Company age, runway and the team’s own years "
            "are not counted."
        ),
    ),
    "years_required_share.hiring": (
        "Posts that state years of experience",
        "share",
        "Share of job posts that ask for a stated number of years of experience.",
    ),
    "degree_required_share.hiring": (
        "Posts that ask for a degree",
        "share",
        (
            "Share of job posts that require or prefer a degree (BS, MS, PhD, a CS degree) and "
            "don’t say experience can stand in for it."
        ),
    ),
    "degree_optional_share.hiring": (
        "Posts that say a degree is optional",
        "share",
        (
            "Share of job posts that say a degree isn’t needed or that equivalent "
            "experience will do (“or equivalent experience”, “no degree "
            "required”)."
        ),
    ),
    "post_length_median.hiring": (
        "Typical post length",
        "count",
        "Median length of a job post in characters, after HTML is stripped.",
    ),
    "interview_style_share.hiring": (
        "Posts that describe the interview",
        "share",
        (
            "Share of job posts that say how they interview: a take-home, no LeetCode or "
            "whiteboard, a pair-programming session, or a paid trial."
        ),
    ),
    "office_days_share.hiring": (
        "Posts that state office days",
        "share",
        (
            "Share of job posts that say how many days a week to be in the office "
            "(“3 days a week in office”, “hybrid, 2 days”, "
            "“onsite Mon–Fri”)."
        ),
    ),
}

# The 2011–12 posts are about half as long as later ones, so any "mentions X" share starts
# lower partly because there is less text to mention it in.
SHORT_POSTS = (
    " Posts from 2011–12 are about half as long as later ones, so early shares run low."
)
for _key in (
    "salary_disclosed_share.hiring",
    "visa_share.hiring",
    "interns_token_share.hiring",
    "years_required_share.hiring",
    "degree_required_share.hiring",
    "degree_optional_share.hiring",
    "interview_style_share.hiring",
    "office_days_share.hiring",
):
    _label, _unit, _description = SCALAR_TEXT[_key]
    SCALAR_TEXT[_key] = (_label, _unit, _description + SHORT_POSTS)

# Points before these months are not exported, because the thing measured changed meaning.
COMPARABLE_FROM = {
    "remote_token_share.hiring": (
        "2015-07",
        "Starts in July 2015, when the REMOTE/ONSITE header convention took hold.",
    ),
    "onsite_token_share.hiring": (
        "2015-07",
        "Starts in July 2015, when the REMOTE/ONSITE header convention took hold.",
    ),
    "new_company_share.hiring": (
        "2013-04",
        "Starts in April 2013, the first month with a full 24 months of history behind it.",
    ),
}
MIN_N_SALARY = 30
MIN_N_SHARE = 50
# A median of whole years, like a salary median, needs a few dozen posts behind it.
MIN_N_MEDIAN = {"usd": MIN_N_SALARY, "years": MIN_N_SALARY}

# 1 when a rise is good news for job seekers, -1 when bad; anything unlisted is neutral (0).
POLARITY = {
    "posts.hiring": 1,
    "posts.seeking": -1,
    "seekers_per_post.hiring": -1,
    "seekers_per_post_us.hiring": -1,
    "salary_disclosed_share.hiring": 1,
    "salary_min_median_usd.hiring": 1,
    "salary_max_median_usd.hiring": 1,
    "visa_share.hiring": 1,
    "new_grad_share.hiring": 1,
    "interns_token_share.hiring": 1,
    "seeker_mood.seeking": 1,
    "seeker_strained_share.seeking": -1,
}

BREAKDOWN_LABELS = {
    "work_mode": "How companies want people to work",
    "seniority": "Which levels companies are hiring",
    "industry": "What hiring companies do",
    "industry_known": "What hiring companies do, among posts that say",
    "funding_stage": "How far along hiring companies are",
    "stack": "Technologies job posts mention",
    "region": "Where hiring posts are, by region",
    "seeker_region": "Where job seekers are, by region",
    "seniority_ai_native": "Which levels AI-native companies are hiring",
    "seniority_not_ai_native": "Which levels other companies are hiring",
    "stack_language": "Programming languages job posts mention",
    "stack_framework": "Frameworks job posts mention",
    "stack_database": "Databases job posts mention",
    "stack_cloud_devops": "Cloud and DevOps tools job posts mention",
    "stack_data": "Data tools job posts mention",
    "stack_ai_ml": "AI and ML tools job posts mention",
    "stack_mobile": "Mobile platforms job posts mention",
    "benefits": "Benefits job posts offer",
    "years_required": "Years of experience asked for",
    "interview_style": "How job posts say they interview",
}
# Breakdowns whose categories are separate yes/no questions, so shares don't sum to 1.
MENTIONS = (
    "Each category is its own share of hiring posts, so they do not add up to 100%. A mention "
    "is not usage: a post can name a tool it is replacing or one it would like to try."
)
BREAKDOWN_DESCRIPTIONS = {
    "stack": MENTIONS,
    **{f"stack_{group}": MENTIONS for group in GROUP_TERMS},
    "region": "A header can name several regions, so shares do not add up to 100%.",
    "benefits": (
        "Share of hiring posts that offer each benefit; posts that rule one out (“no "
        "equity”, “we can’t sponsor visas”) don’t count. Vague "
        "phrases (“great benefits”, “generous PTO”) don’t count "
        "either. Paid time off, days stated means a number of days or weeks. Visa uses the same "
        "rule as visa_share. Each category is its own share."
    ),
    "years_required": (
        "Among posts that state years of experience, the share whose smallest stated number "
        "falls in each band."
    ),
    "interview_style": (
        "Share of hiring posts that mention each interview style. “No LeetCode” counts "
        "posts that say they skip LeetCode, whiteboard or puzzle questions. Each category is "
        "its own share."
    ),
}
CATEGORY_LABELS = {
    "equity": "Equity", "retirement": "401(k) or pension", "health_insurance": "Health insurance",
    "dental_vision": "Dental or vision", "unlimited_pto": "Unlimited PTO",
    "pto_days": "Paid time off, days stated", "parental_leave": "Parental leave",
    "four_day_week": "Four-day week", "learning_budget": "Learning budget",
    "remote_stipend": "Home-office stipend", "relocation": "Relocation help",
    "sign_on_bonus": "Sign-on bonus", "bonus": "Bonus", "visa": "Visa sponsorship",
    "0_2": "0–2 years", "3_4": "3–4 years", "5_7": "5–7 years", "8_plus": "8+ years",
    "take_home": "Take-home", "no_leetcode": "No LeetCode or whiteboard",
    "pair_programming": "Pair programming", "paid_trial": "Paid trial",
}  # fmt: skip
# Validation puts the sector shares about 0.13 off the hand labels; the site badges these.
ROUGH = {"industry", "industry_known"}

ANSWER_METRICS = {f"{m.metric}.{m.kind}": m for m in SCALARS}
ALL_BREAKDOWNS = {b.metric: b for b in [*BREAKDOWNS, INDUSTRY_KNOWN]}


def _method(key: str) -> str:
    if key in ANSWER_METRICS:
        return ANSWER_METRICS[key].method
    if key == "seekers_per_post_us.hiring":
        return "regex"
    return "count" if key.split(".")[0] in COUNT_METRICS else ""


def _sources(key: str) -> list[str]:
    metric, kind = key.split(".")
    both = metric in ("seekers_per_post", "seekers_per_post_us")
    return ["hiring", "seeking"] if both else [kind]


def _min_n(key: str, unit: str) -> int:
    if unit in MIN_N_MEDIAN:
        return MIN_N_MEDIAN[unit]
    return MIN_N_SHARE if unit == "share" else 0


def _question(key: str) -> str | None:
    """The Jev question a metric or breakdown is scored on, if any."""
    if key in ANSWER_METRICS:
        m = ANSWER_METRICS[key]
    elif key in ALL_BREAKDOWNS:
        m = ALL_BREAKDOWNS[key]
    else:
        return None
    if m.method != "jev":
        return None
    return "industry" if key == "industry_known" else m.question or m.metric


def load_validation(path: Path = VALIDATION_PATH) -> dict[str, dict]:
    """question → overall scores, from the holdout set when present, else the reference set."""
    try:
        report = json.loads(path.read_text())
    except FileNotFoundError:
        return {}
    scored: dict[str, dict] = {}
    # Per question: the holdout score wins when it has any posts, else the reference one.
    for name in ("reference", "holdout"):
        for question, scores in (report.get(name) or {}).get("questions", {}).items():
            if scores.get("overall", {}).get("n"):
                scored[question] = {"set": name, **scores["overall"]}
    return scored


def _breakdown_text(name: str, b) -> dict:
    """Optional description and display names, added only where a breakdown has them."""
    text = {}
    if name in BREAKDOWN_DESCRIPTIONS:
        text["description"] = BREAKDOWN_DESCRIPTIONS[name]
    if labels := {c: CATEGORY_LABELS[c] for c in b.categories if c in CATEGORY_LABELS}:
        text["category_labels"] = labels
    return text


def _month(d) -> str:
    return d.strftime("%Y-%m")


def _number(value: float, unit: str) -> float | int:
    if unit in ("count", "usd") and float(value).is_integer():
        return int(value)
    return round(value, 4)


def _generated_at(con: duckdb.DuckDBPyConnection) -> str | None:
    """The newest fetch of a complete thread, so the file changes only when the data does."""
    (fetched,) = con.execute(
        f"SELECT max(fetched_at) FROM threads WHERE {COMPLETE}"
    ).fetchone()
    return fetched.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if fetched else None


def _publishable(key: str, month: str, n: int, min_n: int) -> bool:
    start = COMPARABLE_FROM.get(key, ("",))[0]
    return month >= start and n >= min_n


def build(
    con: duckdb.DuckDBPyConnection,
    validation_path: Path = VALIDATION_PATH,
    external_dir: Path = EXTERNAL_DIR,
) -> dict:
    pending = [
        _month(m)
        for (m,) in con.execute(
            f"SELECT DISTINCT month FROM threads WHERE NOT ({COMPLETE}) ORDER BY month"
        ).fetchall()
    ]
    # The site never shows a pending month, even the half of it that is complete.
    rows = [
        row
        for row in con.execute(
            "SELECT month, kind, metric, category, value, n FROM monthly_metrics "
            "WHERE value IS NOT NULL ORDER BY month, kind, metric, category"
        ).fetchall()
        if _month(row[0]) not in pending
    ]
    validation = load_validation(validation_path)

    def scored(key: str) -> dict | None:
        question = _question(key)
        return validation.get(question) if question else None

    metrics = {}
    for key, (label, unit, description) in SCALAR_TEXT.items():
        start, why = COMPARABLE_FROM.get(key, (None, ""))
        metrics[key] = {
            "label": label,
            "unit": unit,
            "method": _method(key),
            "description": f"{description} {why}".strip(),
            "polarity": POLARITY.get(key, 0),
            "sources": _sources(key),
            "comparable_from": start,
            "validation": scored(key),
            "series": [],
        }
    breakdowns = {
        name: {
            "label": BREAKDOWN_LABELS[name],
            "method": b.method,
            "categories": list(b.categories),
            "polarity": 0,
            "sources": [b.kind],
            "comparable_from": None,
            "validation": scored(name),
            "confidence": "rough" if name in ROUGH else None,
            "series": [],
        }
        | _breakdown_text(name, b)
        for name, b in ALL_BREAKDOWNS.items()
    }
    points: dict[tuple[str, str], dict] = {}

    for month, kind, metric, category, value, n in rows:
        month = _month(month)
        if not category:
            key = f"{metric}.{kind}"
            if key not in metrics:
                continue
            unit = metrics[key]["unit"]
            if _publishable(key, month, n, _min_n(key, unit)):
                metrics[key]["series"].append(
                    {"month": month, "value": _number(value, unit), "n": n}
                )
        elif metric in breakdowns and category in breakdowns[metric]["categories"]:
            if not _publishable(metric, month, n, MIN_N_SHARE):
                continue
            point = points.get((metric, month))
            if point is None:
                point = points[(metric, month)] = {"month": month, "n": n, "values": {}}
                breakdowns[metric]["series"].append(point)
            point["values"][category] = round(value, 4)

    months = sorted({_month(r[0]) for r in rows})
    data = {
        "generated_at": _generated_at(con),
        "latest_month": months[-1] if months else None,
        "months": months,
        "pending": pending,
        "metrics": metrics,
        "breakdowns": breakdowns,
        "external": build_external(months, external_dir),
    }
    noise.attach(con, data)
    return data


SAMPLE_SIZE = 30
SAMPLE_CHARS = 600


def _sample_answers(
    con: duckdb.DuckDBPyConnection, post_ids: list[int]
) -> dict[int, dict]:
    rows = con.execute(
        """
        SELECT post_id, question, value, label, probabilities FROM answers
        WHERE post_id IN (SELECT unnest($posts::BIGINT[]))
          AND question NOT IN ('salary_currency', 'company')
          AND ((method = 'jev' AND version = $jev) OR (method <> 'jev' AND version = $features))
        ORDER BY post_id, question
        """,
        {"posts": post_ids, "jev": JEV_MODEL, "features": FEATURES_VERSION},
    ).fetchall()
    answers: dict[int, dict] = {post_id: {} for post_id in post_ids}
    for post_id, question, value, label, probabilities in rows:
        if question in ("stack", "region", "benefits", "interview_style"):
            answers[post_id][question] = sorted(json.loads(probabilities))
        else:
            answers[post_id][question] = label if label is not None else value
    return answers


def build_samples(con: duckdb.DuckDBPyConnection) -> dict[str, dict]:
    """Up to 30 in-snapshot hiring posts per complete month, seeded by month.

    Job seekers are never quoted, so seeking posts are never sampled.
    """
    rows = con.execute(
        f"""
        SELECT strftime(t.month, '%Y-%m') AS month, p.post_id, p.text
        FROM posts p JOIN threads t USING (thread_id)
        WHERE p.in_snapshot AND t.kind = 'hiring' AND t.{COMPLETE}
        QUALIFY row_number() OVER (
          PARTITION BY t.month ORDER BY md5(strftime(t.month, '%Y-%m') || p.post_id)
        ) <= $size
        ORDER BY month, md5(strftime(t.month, '%Y-%m') || p.post_id)
        """,
        {"size": SAMPLE_SIZE},
    ).fetchall()
    answers = _sample_answers(con, [post_id for _, post_id, _ in rows])
    samples: dict[str, dict] = {}
    for month, post_id, text in rows:
        samples.setdefault(month, {"month": month, "posts": []})["posts"].append(
            {
                "id": post_id,
                "kind": "hiring",
                "url": f"https://news.ycombinator.com/item?id={post_id}",
                "header": header_line(text),
                "text": text[:SAMPLE_CHARS],
                "answers": answers[post_id],
            }
        )
    return samples


def write_samples(
    samples: dict[str, dict], directory: Path = SITE_DATA_DIR / "samples"
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for month, sample in samples.items():
        (directory / f"{month}.json").write_text(
            json.dumps(sample, indent=2, ensure_ascii=False) + "\n"
        )


def write(data: dict, path: Path = SITE_DATA_DIR / "metrics.json") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Compact: the per-point noise bars nearly triple the file when indented.
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")
    return path


def run(con: duckdb.DuckDBPyConnection, args: argparse.Namespace) -> None:
    data = build(con)
    if args.dry_run:
        print(json.dumps(data, indent=2, ensure_ascii=False)[:5000])
        return
    path = write(data)
    samples = build_samples(con)
    write_samples(samples)
    print(f"export: {len(data['months'])} months → {path}, {len(samples)} sample files")
