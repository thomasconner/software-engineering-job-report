import gzip
import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

from sejr.config import FIRST_MONTH, RAW_DIR

API = "https://hn.algolia.com/api/v1"
USER_AGENT = (
    "sejr/0.1 (+https://github.com/thomasconner/software-engineering-job-report)"
)
MIN_INTERVAL = 0.5
MAX_ATTEMPTS = 6

# _whoishiring posted April and May 2015 while the main account was unavailable.
AUTHORS = ["whoishiring", "_whoishiring"]

# Canonical threads posted by other users. These override whatever the accounts above
# posted for the same (kind, month):
# - 2011-07: whoishiring skipped the month; Aloisius posted it.
# - 2011-12: whoishiring's script broke; lpolovets' thread got the posts and whoishiring's
#   own late thread (3300371) only points to it.
# - 2014-05/06: "Who wants to be hired?" started as jader201's experiment; whoishiring
#   took it over in July 2014. The May 2014 title has no month in it.
EXTRA_THREADS: dict[int, tuple[str, str]] = {
    2719028: ("hiring", "2011-07"),
    3300290: ("hiring", "2011-12"),
    7685170: ("seeking", "2014-05"),
    7833250: ("seeking", "2014-06"),
}

TITLE_RE = re.compile(
    r"who (is hiring|wants to be hired)\?\s*\((\w+)\s+(\d{4})\)", re.IGNORECASE
)


@dataclass(frozen=True)
class Thread:
    thread_id: int
    kind: str
    month: str
    num_comments: int


def parse_title(title: str) -> tuple[str, str] | None:
    """Return (kind, YYYY-MM) for a monthly thread title, or None for anything else."""
    match = TITLE_RE.search(title)
    if not match:
        return None
    kind = "hiring" if match[1].lower() == "is hiring" else "seeking"
    try:
        month = datetime.strptime(f"{match[2]} {match[3]}", "%B %Y")
    except ValueError:
        return None
    return kind, month.strftime("%Y-%m")


def raw_paths(kind: str, month: str, thread_id: int) -> tuple[Path, Path]:
    folder = RAW_DIR / kind / month
    return folder / f"{thread_id}.json.gz", folder / f"{thread_id}.meta.json"


class Client:
    """httpx wrapper that stays under 2 requests/sec and retries transient failures."""

    def __init__(self) -> None:
        self.http = httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=60)
        self.last_request = 0.0

    def get(self, path: str, params: dict | None = None) -> httpx.Response:
        for attempt in range(MAX_ATTEMPTS):
            wait = self.last_request + MIN_INTERVAL - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self.last_request = time.monotonic()
            try:
                response = self.http.get(f"{API}{path}", params=params)
                if response.status_code != 429 and response.status_code < 500:
                    response.raise_for_status()
                    return response
                error = f"HTTP {response.status_code}"
            except httpx.TransportError as e:
                error = repr(e)
            backoff = 2**attempt
            print(f"  {path}: {error}, retrying in {backoff}s")
            time.sleep(backoff)
        raise RuntimeError(f"giving up on {path} after {MAX_ATTEMPTS} attempts")


def search_stories(client: Client, author: str) -> list[dict]:
    """All stories by author, newest first. Pages by created_at so Algolia's 1000-hit cap never bites."""
    hits: list[dict] = []
    before: int | None = None
    while True:
        params = {"tags": f"story,author_{author}", "hitsPerPage": 1000}
        if before is not None:
            params["numericFilters"] = f"created_at_i<{before}"
        page = client.get("/search_by_date", params).json()["hits"]
        if not page:
            return hits
        hits.extend(page)
        before = min(hit["created_at_i"] for hit in page)


def pick(candidates: list[Thread]) -> Thread:
    """Deterministic choice among threads for the same (kind, month): most comments, then lowest id."""
    return max(candidates, key=lambda t: (t.num_comments, -t.thread_id))


def discover(client: Client) -> list[Thread]:
    found: dict[tuple[str, str], list[Thread]] = {}
    for author in AUTHORS:
        for hit in search_stories(client, author):
            parsed = parse_title(hit["title"] or "")
            if parsed and parsed[1] >= FIRST_MONTH:
                thread = Thread(
                    int(hit["objectID"]), *parsed, hit.get("num_comments") or 0
                )
                found.setdefault(parsed, []).append(thread)

    threads = {key: pick(candidates) for key, candidates in found.items()}
    for key, candidates in found.items():
        if len(candidates) > 1:
            print(
                f"duplicate {key}: {[t.thread_id for t in candidates]}, kept {threads[key].thread_id}"
            )
    for thread_id, (kind, month) in EXTRA_THREADS.items():
        threads[(kind, month)] = Thread(thread_id, kind, month, 0)
    return sorted(threads.values(), key=lambda t: (t.month, t.kind))


def store(thread: Thread, body: bytes, title: str, source_url: str) -> bool:
    """Write the raw response and its sidecar. Returns False when the stored content is unchanged."""
    data_path, meta_path = raw_paths(thread.kind, thread.month, thread.thread_id)
    if data_path.exists() and gzip.decompress(data_path.read_bytes()) == body:
        return False
    data_path.parent.mkdir(parents=True, exist_ok=True)
    # mtime=0 keeps the gzip bytes identical for identical content, so git sees no spurious changes.
    data_path.write_bytes(gzip.compress(body, mtime=0))
    meta = {
        "thread_id": thread.thread_id,
        "kind": thread.kind,
        "month": thread.month,
        "title": title,
        "fetched_at": datetime.now(UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "source_url": source_url,
    }
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    return True


def select(threads: list[Thread], month: str | None) -> list[Thread]:
    if month:
        return [t for t in threads if t.month == month]
    latest = sorted({t.month for t in threads})[-2:]
    return [
        t
        for t in threads
        if t.month in latest or not raw_paths(t.kind, t.month, t.thread_id)[0].exists()
    ]


def run(con, args) -> None:
    client = Client()
    threads = discover(client)
    for kind in ("hiring", "seeking"):
        print(f"discovered {sum(t.kind == kind for t in threads)} {kind} threads")

    todo = select(threads, args.month)
    if args.limit:
        todo = todo[: args.limit]
    print(f"{len(todo)} threads to fetch")
    if args.dry_run:
        for t in todo:
            print(f"  {t.month} {t.kind} {t.thread_id}")
        return

    for t in todo:
        response = client.get(f"/items/{t.thread_id}")
        title = response.json()["title"]
        changed = store(t, response.content, title, str(response.url))
        print(
            f"  {t.month} {t.kind} {t.thread_id}: {'saved' if changed else 'unchanged'}"
        )
