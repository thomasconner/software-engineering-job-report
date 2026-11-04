"""Jev questions → answers table. One request per in-snapshot post, cached by request hash."""

import argparse
import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path

import duckdb
from typesafe_sdk import (
    AsyncTypeSafeClient,
    TypeSafeAuthenticationError,
    TypeSafeError,
    TypeSafePermissionDeniedError,
)

from sejr.classify import store
from sejr.classify.jev import (
    CHARS_PER_TOKEN,
    CONCURRENCY,
    AnswerRow,
    JevVersionMismatch,
    Request,
    answer_rows,
    ask,
    build_request,
    cache_path,
    estimate_tokens,
    make_client,
    question_set_hash,
)
from sejr.config import ANSWERS_DIR, JEV_CACHE_DIR, JEV_USD_PER_MTOK

PROGRESS_EVERY = 1000
# Without --month, a run this large is almost certainly a backfill by accident.
MAX_UNSCOPED_CALLS = 500
# Errors that would hit every post the same way; stop instead of logging each one.
FATAL = (JevVersionMismatch, TypeSafeAuthenticationError, TypeSafePermissionDeniedError)
# Errors that belong to one post (an API error after retries, a malformed answer, a cache
# write): log them, keep going, and exit non-zero at the end.
PER_POST = (TypeSafeError, ValueError, KeyError, OSError)


@dataclass
class Post:
    post_id: int
    kind: str
    month: str
    request: Request


@dataclass
class Outcome:
    rows: list[AnswerRow] = field(default_factory=list)
    done: list[Post] = field(default_factory=list)
    failed: list[int] = field(default_factory=list)
    calls: int = 0
    input_tokens: int = 0


def select_posts(
    con: duckdb.DuckDBPyConnection,
    month: str | None,
    limit: int | None,
    post_ids: list[int] | None = None,
) -> list[Post]:
    sql = """
        SELECT p.post_id, t.kind, strftime(t.month, '%Y-%m'), p.text
        FROM posts p JOIN threads t USING (thread_id)
        WHERE p.in_snapshot AND t.kind IN ('hiring', 'seeking')
    """
    params: list[object] = []
    if month:
        sql += " AND t.month = CAST(? AS DATE)"
        params.append(f"{month}-01")
    if post_ids is not None:
        sql += " AND p.post_id IN (SELECT unnest(?::BIGINT[]))"
        params.append(post_ids)
    sql += " ORDER BY p.post_id"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    return [
        Post(post_id, kind, month, build_request(kind, text))
        for post_id, kind, month, text in con.execute(sql, params).fetchall()
    ]


def print_estimate(posts: list[Post], skipped: int, uncached: list[Post]) -> None:
    tokens = sum(estimate_tokens(p.request) for p in uncached)
    cost = tokens / 1e6 * JEV_USD_PER_MTOK
    print(
        f"posts: {len(posts) + skipped} ({skipped} already answered, "
        f"{len(posts) - len(uncached)} cached, {len(uncached)} requests to send)"
    )
    print(
        f"estimated input tokens: {tokens:,} (~{CHARS_PER_TOKEN} characters per token)"
    )
    print(
        f"estimated cost: ${cost:.4f} at ${JEV_USD_PER_MTOK} per million input tokens"
    )


async def classify(
    posts: list[Post], client: AsyncTypeSafeClient | None, cache_dir: Path
) -> Outcome:
    outcome = Outcome()
    limit = asyncio.Semaphore(CONCURRENCY)

    async def one(post: Post) -> None:
        try:
            response, called = await ask(client, post.request, cache_dir, limit)
            outcome.rows.extend(answer_rows(post.post_id, response))
        except FATAL:
            raise
        except PER_POST as error:
            print(
                f"post {post.post_id}: {type(error).__name__}: {error}", file=sys.stderr
            )
            outcome.failed.append(post.post_id)
            return
        outcome.done.append(post)
        if called:
            outcome.calls += 1
            outcome.input_tokens += response["usage"].get("input_tokens") or 0
            if outcome.calls % PROGRESS_EVERY == 0:
                print(f"  {outcome.calls} API calls so far")

    # A fatal error cancels the remaining tasks; responses cached so far are kept.
    async with asyncio.TaskGroup() as tg:
        for post in posts:
            tg.create_task(one(post))
    return outcome


async def classify_with_client(
    posts: list[Post],
    client: AsyncTypeSafeClient | None,
    cache_dir: Path,
    needs_api: bool,
) -> Outcome:
    if client is not None or not needs_api:
        return await classify(posts, client, cache_dir)
    async with make_client() as own:
        return await classify(posts, own, cache_dir)


def run(
    con: duckdb.DuckDBPyConnection,
    args: argparse.Namespace,
    *,
    client: AsyncTypeSafeClient | None = None,
    cache_dir: Path = JEV_CACHE_DIR,
    answers_dir: Path = ANSWERS_DIR,
    post_ids: list[int] | None = None,
) -> None:
    qsets = store.read_qsets(con, answers_dir)
    selected = select_posts(con, args.month, args.limit, post_ids)
    posts = [p for p in selected if qsets.get(p.post_id) != question_set_hash(p.kind)]
    skipped = len(selected) - len(posts)
    uncached = [p for p in posts if not cache_path(cache_dir, p.request).exists()]
    scoped = args.month or args.backfill or post_ids is not None
    too_many = not scoped and len(uncached) > MAX_UNSCOPED_CALLS
    if args.dry_run:
        print_estimate(posts, skipped, uncached)
        if too_many:
            print(f"a real run would refuse: over {MAX_UNSCOPED_CALLS} API calls")
        return
    if too_many:
        raise SystemExit(
            f"refusing {len(uncached)} API calls without --month; "
            "pass --backfill to classify the full history"
        )

    store.load(con, answers_dir)
    outcome = asyncio.run(
        classify_with_client(posts, client, cache_dir, bool(uncached))
    )
    store.replace(con, [p.post_id for p in outcome.done], outcome.rows)
    qsets.update({p.post_id: question_set_hash(p.kind) for p in outcome.done})
    store.save(con, answers_dir, {p.month for p in outcome.done}, qsets)

    cost = outcome.input_tokens / 1e6 * JEV_USD_PER_MTOK
    print(
        f"classified {len(outcome.done)} posts ({skipped} already answered): "
        f"{outcome.calls} API calls, {len(outcome.rows)} answers, "
        f"{outcome.input_tokens:,} input tokens (${cost:.4f})"
    )
    if outcome.failed:
        raise SystemExit(
            f"{len(outcome.failed)} posts failed (see errors above); rerun to retry them"
        )
