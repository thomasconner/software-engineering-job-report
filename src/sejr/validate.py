"""Score Jev answers against the hand-labeled reference set → site/data/validation.json."""

import argparse
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from statistics import fmean

import duckdb
from typesafe_sdk import AsyncTypeSafeClient

from sejr import classify
from sejr.classify.jev import question_set_hash
from sejr.config import (
    ANSWERS_DIR,
    JEV_CACHE_DIR,
    JEV_MODEL,
    LABELS_PATH,
    SITE_DATA_DIR,
)

ERAS = ["2011-14", "2015-19", "2020-22", "2023-26"]
CHOICES = ["work_mode", "seniority", "industry", "funding_stage"]
NOULS = ["ai_native", "new_grad", "eng_leadership"]
SCORES = ["seeker_mood"]
# Rows sampled to have enough non-neutral moods; they would skew any share estimate.
OVERSAMPLED = "oversample_mood"


def read_labels(path: Path) -> list[dict]:
    with path.open() as f:
        rows = [json.loads(line) for line in f if line.strip()]
    return [r for r in rows if not r.get("exclude")]


def load_answers(
    con: duckdb.DuckDBPyConnection, post_ids: list[int]
) -> dict[tuple[int, str], tuple[float | None, str | None, dict | None]]:
    rows = con.execute(
        """
        SELECT post_id, question, value, label, probabilities FROM answers
        WHERE method = 'jev' AND version = ? AND post_id IN (SELECT unnest(?::BIGINT[]))
        """,
        [JEV_MODEL, post_ids],
    ).fetchall()
    return {
        (pid, q): (value, label, json.loads(p) if p else None)
        for pid, q, value, label, p in rows
    }


def brier(probabilities: dict[str, float], truth: str) -> float:
    """Multiclass Brier score: squared error summed over every category."""
    categories = set(probabilities) | {truth}
    return sum((probabilities.get(k, 0.0) - (k == truth)) ** 2 for k in categories)


def scored_rows(question: str, label: object, answer: tuple) -> dict:
    """One labeled post → the per-row numbers the summary averages."""
    value, top, probabilities = answer
    if question in NOULS:
        y = float(label)
        return {
            "hit": (value >= 0.5) == bool(label),
            "brier": (value - y) ** 2,
            "p": value,
            "y": y,
        }
    truth = str(label)
    if question in SCORES:
        top = max(probabilities, key=probabilities.__getitem__)
        strained = probabilities.get("0", 0.0) + probabilities.get("1", 0.0)
        return {
            "hit": top == truth,
            "brier": brier(probabilities, truth),
            "abs_err": abs(value - int(label)),
            "score": value,
            "y": int(label),
            "p": strained,
            "y_strained": float(int(label) <= 1),
        }
    return {
        "hit": top == truth,
        "brier": brier(probabilities, truth),
        "probabilities": probabilities,
        "truth": truth,
    }


def summarize(question: str, rows: list[dict]) -> dict:
    """rows carry an `in_share` flag: False for oversampled rows, kept out of share bias."""
    if not rows:
        return {"n": 0}
    out = {
        "n": len(rows),
        "accuracy": fmean(r["hit"] for r in rows),
        "brier": fmean(r["brier"] for r in rows),
    }
    share = [r for r in rows if r["in_share"]]
    if question in NOULS and share:
        out["mean_p"] = fmean(r["p"] for r in share)
        out["mean_label"] = fmean(r["y"] for r in share)
        out["share_error"] = abs(out["mean_p"] - out["mean_label"])
    if question in SCORES:
        out["mae"] = fmean(r["abs_err"] for r in rows)
        if share:
            out["n_share"] = len(share)
            out["mean_score_error"] = abs(
                fmean(r["score"] for r in share) - fmean(r["y"] for r in share)
            )
            # The published seeker_strained_share: mean of P(level 0) + P(level 1).
            out["strained_share_error"] = abs(
                fmean(r["p"] for r in share) - fmean(r["y_strained"] for r in share)
            )
    if question in CHOICES:
        # Breakdowns publish mean probabilities per category; this is how far that
        # distribution sits from the labeled one (total variation, 0–1).
        categories = {k for r in rows for k in r["probabilities"]} | {
            r["truth"] for r in rows
        }
        out["share_tv"] = 0.5 * sum(
            abs(
                fmean(r["probabilities"].get(k, 0.0) for r in rows)
                - fmean(r["truth"] == k for r in rows)
            )
            for k in categories
        )
    return out


def evaluate(labels: list[dict], answers: dict) -> tuple[dict, dict[str, int]]:
    by_question: dict[str, dict[str, list[dict]]] = defaultdict(
        lambda: defaultdict(list)
    )
    missing: dict[str, int] = defaultdict(int)
    for ref in labels:
        for question, label in ref["labels"].items():
            if label is None or question not in CHOICES + NOULS + SCORES:
                continue
            answer = answers.get((ref["post_id"], question))
            if answer is None:
                missing[question] += 1
                continue
            row = scored_rows(question, label, answer)
            row["in_share"] = ref.get("source") != OVERSAMPLED
            by_question[question][ref["era"]].append(row)
    result = {}
    for question in CHOICES + NOULS + SCORES:
        eras = by_question.get(question, {})
        result[question] = {
            "overall": summarize(question, [r for e in eras.values() for r in e]),
            "by_era": {era: summarize(question, eras.get(era, [])) for era in ERAS},
        }
    return result, dict(missing)


def print_table(questions: dict, missing: dict[str, int]) -> None:
    def fmt(x: float | None) -> str:
        return "" if x is None else f"{x:.3f}"

    print(
        f"{'question':<15} {'era':<8} {'n':>4} {'acc':>6} {'brier':>6} {'share':>6} {'mae':>6}"
    )
    for question, scores in questions.items():
        for era, s in [("all", scores["overall"]), *scores["by_era"].items()]:
            if not s["n"]:
                continue
            share = s.get(
                "share_error", s.get("strained_share_error", s.get("share_tv"))
            )
            print(
                f"{question:<15} {era:<8} {s['n']:>4} {fmt(s['accuracy']):>6} "
                f"{fmt(s['brier']):>6} {fmt(share):>6} {fmt(s.get('mae')):>6}"
            )
    for question, n in missing.items():
        print(f"warning: {n} labeled posts have no {question} answer")


def run(
    con: duckdb.DuckDBPyConnection,
    args: argparse.Namespace,
    *,
    labels_path: Path = LABELS_PATH,
    out_path: Path = SITE_DATA_DIR / "validation.json",
    client: AsyncTypeSafeClient | None = None,
    cache_dir: Path = JEV_CACHE_DIR,
    answers_dir: Path = ANSWERS_DIR,
) -> None:
    labels = read_labels(labels_path)
    post_ids = [r["post_id"] for r in labels]
    known = {
        pid
        for (pid,) in con.execute(
            "SELECT post_id FROM posts WHERE post_id IN (SELECT unnest(?::BIGINT[]))",
            [post_ids],
        ).fetchall()
    }
    if absent := [pid for pid in post_ids if pid not in known]:
        raise SystemExit(
            f"{len(absent)} reference posts are not in the database, e.g. {absent[:5]}"
        )

    # Classify only the reference posts; already-answered ones are skipped.
    scope = argparse.Namespace(
        month=None, limit=None, dry_run=args.dry_run, backfill=False
    )
    classify.run(
        con,
        scope,
        client=client,
        cache_dir=cache_dir,
        answers_dir=answers_dir,
        post_ids=post_ids,
    )
    if args.dry_run:
        return

    questions, missing = evaluate(labels, load_answers(con, post_ids))
    report = {
        "model": JEV_MODEL,
        "qset": {kind: question_set_hash(kind) for kind in ("hiring", "seeking")},
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "n_labels": len(labels),
        "questions": questions,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n")
    print_table(questions, missing)
    print(f"wrote {out_path}")
