"""A small multi-month database that follows the schema in docs/architecture.md.

Post texts are real "Who is hiring?" headers (2014–2026) so the regexes see realistic input.
"""

import json
import random
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import duckdb
import pytest

from sejr.config import JEV_MODEL
from sejr.db import connect

HIRING_TEXTS = {
    "discord": "Discord | Senior Software Engineer, Application Security | REMOTE (US West Coast) "
    "or San Francisco, CA | $196K-$245K base + equity\n\nWe use Python, Rust and Elixir.",
    "paramark": "Paramark | Software Engineer (L4) | San Francisco HYBRID (3 days/wk) or REMOTE (US) "
    "| Full-time | $199K–$249K + equity\n\nStack: TypeScript, React, Postgres, AWS.",
    "planlab": "Planlab.ai | | Product Engineer (Design) & Platform Engineer | ONSITE in London, UK "
    "| 100k-160k GBP + 0.25-0.75% Equity | Visa sponsorship\n\nWe build AI agents on LLMs.",
    "gusto": "Gusto | VISA, ONSITE | Sr. Rails/React Engineer | San Francisco\n\n"
    "Gusto is building payroll for small businesses. Ruby on Rails, React.",
    "canonical": "Canonical | www.canonical.com | Remote (work from home) | Full Time | Developer, "
    "Project Manager\n\nWe write Go and Python. We are not able to sponsor visas.",
    "lambda": "Lambda | Senior Software Engineer | San Francisco, CA (Dogpatch) | Onsite | Full Time"
    "\n\nKubernetes, Terraform, PyTorch.",
    "spade": "Spade | Multiple Engineering, AI/ML Data Science, Revenue, and Ops Roles | ONSITE NYC "
    "or REMOTE (US/Can) | $130-240K+ (depending on role/level) + equity",
    "modash": "Modash.io | Senior Product Engineer | Remote (Europe) | Full-time | €75k–110k | "
    "https://modash.io\n\nNode.js, Vue, MongoDB.",
    "hubspot": "HubSpot - Cambridge/Boston, MA - http://www.hubspot.com\n\n"
    "We raised $35 Million in our Series B. Java and Kafka.",
    "citymapper": "Citymapper (London, UK) - Help build the world's most loved urban navigation "
    "app!\n\nNo remote work. Python, Go, Swift and Kotlin.",
}

SEEKING_TEXT = "Location: Berlin, Germany\nRemote: Yes\nWilling to relocate: No\n\nTechnologies: Python"

MONTHS = [date(2024, m, 1) for m in range(1, 8)]
# April has no hiring thread, so May has no "last month" to compare against.
NO_HIRING = {date(2024, 4, 1)}
NO_SEEKING = {date(2024, 2, 1)}
# Months that Jev has classified; the rest must not get Jev metrics.
CLASSIFIED = {date(2024, 1, 1), date(2024, 3, 1), date(2024, 6, 1)}
CHOICES = {
    "work_mode": ["remote", "hybrid", "onsite", "unclear"],
    "seniority": ["junior", "mid", "senior", "staff_plus", "unspecified"],
    "funding_stage": ["seed", "series_a", "public_or_large", "unknown"],
    "industry": ["ai_ml", "fintech", "devtools_infra", "other", "unstated"],
}


def _ts(day: date, hours: float) -> datetime:
    return datetime(day.year, day.month, day.day, 15, tzinfo=UTC) + timedelta(
        hours=hours
    )


def _distribution(rng: random.Random, categories: list[str]) -> dict[str, float]:
    weights = [rng.random() for _ in categories]
    total = sum(weights)
    return {c: round(w / total, 3) for c, w in zip(categories, weights, strict=True)}


def populate(con: duckdb.DuckDBPyConnection) -> None:
    rng = random.Random(155)
    next_id = iter(range(1000, 10**6))
    for month in MONTHS:
        for kind in ("hiring", "seeking"):
            if month in (NO_HIRING if kind == "hiring" else NO_SEEKING):
                continue
            thread_id = next(next_id)
            created = _ts(month, 0)
            label = "Who is hiring?" if kind == "hiring" else "Who wants to be hired?"
            con.execute(
                "INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?)",
                [thread_id, kind, month, f"Ask HN: {label} ({month:%B %Y})", created,
                 created + timedelta(days=7)],
            )  # fmt: skip
            if kind == "hiring":
                companies = rng.sample(sorted(HIRING_TEXTS), 6)
                texts = [HIRING_TEXTS[c] for c in companies]
            else:
                texts = [SEEKING_TEXT] * rng.randint(4, 9)
            for i, text in enumerate(texts):
                # Every month a couple of posts land after the 7-day snapshot.
                hours = 24 * 9 if i >= len(texts) - 2 else rng.uniform(0, 24 * 6)
                _add_post(
                    con, rng, next_id, thread_id, kind, month, text, created, hours
                )


def _add_post(con, rng, next_id, thread_id, kind, month, text, created, hours) -> None:
    post_id = next(next_id)
    posted = created + timedelta(hours=hours)
    in_snapshot = posted <= created + timedelta(days=7)
    con.execute(
        "INSERT INTO posts VALUES (?, ?, ?, ?, ?, ?, ?)",
        [post_id, thread_id, "author", posted, f"<p>{text}</p>", text, in_snapshot],
    )
    for _ in range(rng.randint(0, 4)):
        reply_id = next(next_id)
        replied = posted + timedelta(hours=rng.uniform(1, 24 * 12))
        depth = rng.choice([1, 1, 2])
        con.execute(
            "INSERT INTO replies VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [reply_id, post_id, post_id if depth == 1 else reply_id - 1, thread_id, "someone",
             replied, "Interested!", depth, replied <= created + timedelta(days=7)],
        )  # fmt: skip
    if month in CLASSIFIED:
        _add_jev(con, rng, post_id, kind)


def _add_jev(con, rng, post_id, kind) -> None:
    def answer(question, value=None, label=None, probabilities=None, version=JEV_MODEL):
        con.execute(
            "INSERT INTO answers VALUES (?, ?, 'jev', ?, ?, ?, ?, ?)",
            [post_id, question, version, value, label,
             json.dumps(probabilities) if probabilities else None, 0.9],
        )  # fmt: skip

    if kind == "seeking":
        # Score levels are keyed "0".."4", as Jev returns them.
        mood = _distribution(rng, ["0", "1", "2", "3", "4"])
        answer(
            "seeker_mood",
            value=sum(int(k) * p for k, p in mood.items()),
            probabilities=mood,
        )
        return
    answer("ai_native", value=rng.random())
    answer("new_grad", value=rng.random())
    answer("eng_leadership", value=rng.random())
    # An old model version that aggregate must ignore.
    answer("ai_native", value=1.0, version="jev-1.12.0")
    for question, categories in CHOICES.items():
        dist = _distribution(rng, categories)
        answer(question, label=max(dist, key=dist.get), probabilities=dist)


@pytest.fixture
def db(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    con = connect(tmp_path / "full.duckdb")
    con.begin()
    populate(con)
    con.commit()
    yield con
    con.close()
