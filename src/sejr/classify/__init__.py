"""Jev questions → answers table. One request per in-snapshot post, cached by request hash."""

import argparse
import asyncio
from pathlib import Path

import duckdb
from typesafe_sdk import AsyncTypeSafeClient

from sejr.classify.jev import (
    CHARS_PER_TOKEN,
    CONCURRENCY,
    Request,
    answer_rows,
    ask,
    build_request,
    cache_path,
    estimate_tokens,
    make_client,
)
from sejr.config import JEV_CACHE_DIR, JEV_USD_PER_MTOK

PROGRESS_EVERY = 1000


def select_posts(
    con: duckdb.DuckDBPyConnection, month: str | None, limit: int | None
) -> list[tuple[int, str, str]]:
    sql = """
        SELECT p.post_id, t.kind, p.text
        FROM posts p JOIN threads t USING (thread_id)
        WHERE p.in_snapshot AND t.kind IN ('hiring', 'seeking')
    """
    params: list[object] = []
    if month:
        sql += " AND t.month = CAST(? AS DATE)"
        params.append(f"{month}-01")
    sql += " ORDER BY p.post_id"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    return con.execute(sql, params).fetchall()


def print_estimate(requests: list[tuple[int, Request]], cache_dir: Path) -> None:
    todo = [r for _, r in requests if not cache_path(cache_dir, r).exists()]
    tokens = sum(estimate_tokens(r) for r in todo)
    print(
        f"requests: {len(requests)} ({len(requests) - len(todo)} cached, {len(todo)} to send)"
    )
    print(
        f"estimated input tokens: {tokens:,} (~{CHARS_PER_TOKEN} characters per token)"
    )
    cost = tokens / 1e6 * JEV_USD_PER_MTOK
    print(
        f"estimated cost: ${cost:.4f} at ${JEV_USD_PER_MTOK} per million input tokens"
    )


async def classify(
    con: duckdb.DuckDBPyConnection,
    requests: list[tuple[int, Request]],
    client: AsyncTypeSafeClient | None,
    cache_dir: Path,
) -> None:
    needs_api = any(not cache_path(cache_dir, r).exists() for _, r in requests)
    own_client = client is None and needs_api
    if own_client:
        client = make_client()
    limit = asyncio.Semaphore(CONCURRENCY)
    rows = []
    calls = input_tokens = 0

    async def one(post_id: int, request: Request) -> None:
        nonlocal calls, input_tokens
        response, called = await ask(client, request, cache_dir, limit)
        rows.extend(answer_rows(post_id, response))
        if called:
            calls += 1
            input_tokens += response["usage"]["input_tokens"]
            if calls % PROGRESS_EVERY == 0:
                print(f"  {calls} API calls so far")

    try:
        # A TaskGroup cancels the rest on the first failure, so a version mismatch or a
        # non-retryable API error stops the run. Responses already cached are kept.
        async with asyncio.TaskGroup() as tg:
            for post_id, request in requests:
                tg.create_task(one(post_id, request))
    finally:
        if own_client:
            await client.aclose()

    post_ids = [post_id for post_id, _ in requests]
    con.begin()
    # One Jev version per post: drop older Jev answers before writing the new ones.
    con.execute(
        "DELETE FROM answers WHERE method = 'jev' AND list_contains(?, post_id)",
        [post_ids],
    )
    if rows:
        con.executemany("INSERT INTO answers VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
    con.commit()
    print(
        f"classified {len(requests)} posts: {calls} API calls, "
        f"{len(requests) - calls} from cache, {len(rows)} answers, "
        f"{input_tokens:,} input tokens (${input_tokens / 1e6 * JEV_USD_PER_MTOK:.4f})"
    )


def run(
    con: duckdb.DuckDBPyConnection,
    args: argparse.Namespace,
    *,
    client: AsyncTypeSafeClient | None = None,
    cache_dir: Path = JEV_CACHE_DIR,
) -> None:
    posts = select_posts(con, args.month, args.limit)
    requests = [(post_id, build_request(kind, text)) for post_id, kind, text in posts]
    if args.dry_run:
        print_estimate(requests, cache_dir)
        return
    cache_dir.mkdir(parents=True, exist_ok=True)
    asyncio.run(classify(con, requests, client, cache_dir))
