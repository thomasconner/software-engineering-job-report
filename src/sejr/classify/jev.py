"""Jev requests: build the state, cache responses, call the API, map answers to rows."""

import asyncio
import hashlib
import json
import os
import re
from functools import cache
from pathlib import Path
from typing import Any

from typesafe_sdk import AsyncTypeSafeClient, RetryPolicy

from sejr.classify.questions import QUESTIONS
from sejr.config import JEV_MODEL

# Almost every post fits: in a 2026 sample the longest of ~940 posts was 3.5k characters.
# The cap (~1.5k tokens) only trims outliers. Jev loses accuracy on long, noisy state
# (docs: model-jaggedness), and the facts we ask about sit near the top of a post.
MAX_STATE_CHARS = 6000
TRUNCATION_MARK = "\n\n[post truncated]"

CONCURRENCY = 16
CHARS_PER_TOKEN = 3

# The SDK already retries 408, 429 and 5xx (including 529 Overloaded) with exponential
# backoff and honors retry-after. Its defaults give up after 2 retries or 30 s, which a
# long backfill against a per-organization rate limit will hit, so allow far more.
RETRY = RetryPolicy(max_retries=8, backoff_initial=1.0, backoff_max=60.0, timeout=600.0)

Request = dict[str, Any]
Response = dict[str, Any]
AnswerRow = tuple[
    int, str, str, str, float | None, str | None, str | None, float | None
]


class JevVersionMismatch(RuntimeError):
    pass


def build_state(text: str) -> str:
    """The post text only: no ids, dates or month, so Jev cannot place it in time."""
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) <= MAX_STATE_CHARS:
        return text
    half = MAX_STATE_CHARS // 2
    cut = text.rfind("\n\n", half, MAX_STATE_CHARS)
    if cut == -1:
        cut = text.rfind(" ", half, MAX_STATE_CHARS)
    if cut == -1:
        cut = MAX_STATE_CHARS
    return text[:cut].rstrip() + TRUNCATION_MARK


@cache
def wire_questions(kind: str) -> dict[str, Any]:
    return {name: q.model_dump(mode="json") for name, q in QUESTIONS[kind].items()}


def build_request(kind: str, text: str) -> Request:
    """One request per post with every question for its kind (speculative fan-out)."""
    return {
        "model": JEV_MODEL,
        "state": build_state(text),
        "questions": wire_questions(kind),
    }


def canonical_json(request: Request) -> str:
    # Keys keep their insertion order rather than being sorted: Choice option order can
    # move Jev's answer (docs: model-jaggedness), so reordering options must re-run.
    return json.dumps(request, ensure_ascii=False, separators=(",", ":"))


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def request_digest(request: Request) -> str:
    """Identifies the exact request: model, questions and post text."""
    return sha256(canonical_json(request))


def cache_path(cache_dir: Path, request: Request) -> Path:
    # Sharded by the first two hex characters so no directory holds 150k files.
    digest = request_digest(request)
    return cache_dir / digest[:2] / f"{digest}.json"


@cache
def question_set_hash(kind: str) -> str:
    """Identifies the model plus every question for a kind; any edit re-runs those posts."""
    return sha256(
        canonical_json({"model": JEV_MODEL, "questions": wire_questions(kind)})
    )


def estimate_tokens(request: Request) -> int:
    # No public tokenizer. A live check of 20 posts on jev-1.14.0 billed one token per
    # 3.4 request characters for hiring posts and per 2.6 for seeking posts; 3 is close
    # for both and errs high on hiring, which dominates the total.
    return len(canonical_json(request)) // CHARS_PER_TOKEN


def make_client() -> AsyncTypeSafeClient:
    return AsyncTypeSafeClient(model=JEV_MODEL, retry=RETRY, timeout=30.0)


def check_version(response: Response) -> None:
    if response.get("model") != JEV_MODEL:
        raise JevVersionMismatch(
            f"Jev answered with {response.get('model')!r}, but {JEV_MODEL!r} is pinned. "
            "Mixing versions would break the series; nothing was cached for this request."
        )


async def ask(
    client: AsyncTypeSafeClient | None,
    request: Request,
    cache_dir: Path,
    limit: asyncio.Semaphore,
) -> tuple[Response, bool]:
    """Return (response JSON, whether the API was called). Cached requests never call it."""
    path = cache_path(cache_dir, request)
    if path.exists():
        response = json.loads(path.read_text())["response"]
        check_version(response)
        return response, False
    if client is None:
        raise RuntimeError("an uncached request needs a Jev client")
    async with limit:
        result = await client.system_one(
            state=request["state"],
            questions=request["questions"],
            model=request["model"],
        )
    # Cache the body exactly as the API sent it, not the SDK's parsed view of it.
    response = json.loads(result.raw_http_response.content)
    check_version(response)
    entry = {"request": request, "response": response}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(entry, ensure_ascii=False))
    tmp.replace(path)
    return response, True


def fold_industry(
    answers: dict[str, Any],
) -> tuple[str, dict[str, float], float | None]:
    """Fold the two companion Nouls into the sector Choice (docs/architecture.md).

    P(sector) = P(fits) * P(sector | Choice); the rest splits into `other` (the post says
    what the company does) and `unstated` (it doesn't). Returns (label, probabilities,
    confidence), where confidence is the Choice's only when a sector is the label.
    """
    choice = answers["industry"]
    try:
        fits = answers["industry_fits"]["noul"]
        stated = answers["industry_stated"]["noul"]
    except KeyError as missing:
        raise ValueError(f"industry answer without companion Noul {missing}") from None
    probabilities = {k: p * fits for k, p in choice["probabilities"].items()}
    probabilities["other"] = (1 - fits) * stated
    probabilities["unstated"] = (1 - fits) * (1 - stated)
    label = max(probabilities, key=probabilities.__getitem__)
    confidence = choice["confidence"] if label in choice["probabilities"] else None
    return label, probabilities, confidence


def answer_rows(post_id: int, response: Response) -> list[AnswerRow]:
    version = response["model"]
    answers = response["answers"]
    rows: list[AnswerRow] = []
    for question, a in answers.items():
        value = label = probabilities = confidence = None
        match a["type"]:
            case "choice" if question == "industry":
                label, probabilities, confidence = fold_industry(answers)
            case "choice":
                label, probabilities = a["choice"], a["probabilities"]
                confidence = a["confidence"]
            case "score":
                value, probabilities = a["score"], a["probabilities"]
                confidence = a["confidence"]
            case "noul":
                value = a["noul"]
            case other:
                raise ValueError(f"unexpected Jev answer type {other!r} for {question}")
        if probabilities is not None:
            probabilities = json.dumps(probabilities)
        rows.append(
            (post_id, question, "jev", version, value, label, probabilities, confidence)
        )
    return rows
