import gzip
import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from sejr.config import FIRST_MONTH, RAW_DIR, SNAPSHOT_DAYS

ALGOLIA = "https://hn.algolia.com/api/v1"
FIREBASE = "https://hacker-news.firebaseio.com/v0"
USER_AGENT = (
    "sejr/0.1 (+https://github.com/thomasconner/software-engineering-job-report)"
)
MIN_INTERVAL = 0.5
MAX_ATTEMPTS = 6

# "Who wants to be hired?" began in May 2014; hiring threads exist from FIRST_MONTH.
SEEKING_FIRST_MONTH = "2014-05"

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

MONTH_NAMES = [
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
]
# Spelled out rather than taken from calendar/strptime, which depend on the locale.
MONTHS = (
    {name: i for i, name in enumerate(MONTH_NAMES, 1)}
    | {name[:3]: i for i, name in enumerate(MONTH_NAMES, 1)}
    | {"sept": 9}
)

MENTION_RE = re.compile(r"who (is hiring|wants to be hired)", re.IGNORECASE)
TITLE_RE = re.compile(
    r"who (is hiring|wants to be hired)\?\s*\(([a-z]+)\.?\s+(\d{4})\)", re.IGNORECASE
)


@dataclass(frozen=True)
class Thread:
    thread_id: int
    kind: str
    month: str


def parse_title(title: str) -> tuple[str, str] | None:
    """Return (kind, YYYY-MM) for a monthly thread title, or None for anything else."""
    match = TITLE_RE.search(title)
    if not match or match[2].lower() not in MONTHS:
        return None
    kind = "hiring" if match[1].lower() == "is hiring" else "seeking"
    return kind, f"{match[3]}-{MONTHS[match[2].lower()]:02d}"


def raw_paths(thread: Thread) -> tuple[Path, Path]:
    folder = RAW_DIR / thread.kind / thread.month
    return (
        folder / f"{thread.thread_id}.json.gz",
        folder / f"{thread.thread_id}.meta.json",
    )


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


class Client:
    """httpx wrapper that stays under 2 requests/sec and retries transient failures."""

    def __init__(self, min_interval: float = MIN_INTERVAL) -> None:
        self.http = httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=60)
        self.min_interval = min_interval
        self.last_request = 0.0

    def get(self, url: str, params: dict | None = None) -> httpx.Response:
        return self.request("GET", url, params=params)

    def post(self, url: str, json: dict) -> httpx.Response:
        return self.request("POST", url, json=json)

    def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        for attempt in range(MAX_ATTEMPTS):
            wait = self.last_request + self.min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self.last_request = time.monotonic()
            try:
                response = self.http.request(method, url, **kwargs)
                if response.status_code != 429 and response.status_code < 500:
                    response.raise_for_status()
                    return response
                error = f"HTTP {response.status_code}"
            except httpx.TransportError as e:
                error = repr(e)
            backoff = 2**attempt
            print(f"  {url}: {error}, retrying in {backoff}s")
            time.sleep(backoff)
        raise RuntimeError(f"giving up on {url} after {MAX_ATTEMPTS} attempts")


def search_stories(client: Client, author: str) -> list[dict]:
    """All stories by author. Pages by created_at so Algolia's 1000-hit cap never bites."""
    hits: dict[str, dict] = {}

    def search(numeric_filter: str | None) -> list[dict]:
        params = {"tags": f"story,author_{author}", "hitsPerPage": 1000}
        if numeric_filter:
            params["numericFilters"] = numeric_filter
        page = client.get(f"{ALGOLIA}/search_by_date", params).json()["hits"]
        hits.update((hit["objectID"], hit) for hit in page)
        return page

    page = search(None)
    while page:
        oldest = min(hit["created_at_i"] for hit in page)
        # A full page can cut off stories that share its oldest second, so fetch that
        # second on its own, then continue strictly below it. (A plain <= stalls when
        # a page holds nothing new.)
        search(f"created_at_i={oldest}")
        page = search(f"created_at_i<{oldest}")
    return list(hits.values())


def pick(hits: list[dict]) -> dict:
    """Deterministic choice among threads for the same (kind, month): most comments, then lowest id."""
    return max(hits, key=lambda h: (h.get("num_comments") or 0, -int(h["objectID"])))


def discover(client: Client) -> list[Thread]:
    found: dict[tuple[str, str], list[dict]] = {}
    for author in AUTHORS:
        for hit in search_stories(client, author):
            title = hit.get("title") or ""
            parsed = parse_title(title)
            if parsed is None:
                if MENTION_RE.search(title):
                    print(f"skipped title {hit['objectID']}: {title}")
            elif parsed[1] >= FIRST_MONTH:
                found.setdefault(parsed, []).append(hit)

    threads: dict[tuple[str, str], Thread] = {}
    for key, hits in found.items():
        best = pick(hits)
        if len(hits) > 1:
            ids = [h["objectID"] for h in hits]
            print(f"duplicate {key}: {ids}, kept {best['objectID']}")
        threads[key] = Thread(int(best["objectID"]), *key)
    for thread_id, key in EXTRA_THREADS.items():
        threads[key] = Thread(thread_id, *key)
    return sorted(threads.values(), key=lambda t: (t.month, t.kind))


def month_range(first: str, last: str) -> list[str]:
    year, month = map(int, first.split("-"))
    months = []
    while (current := f"{year}-{month:02d}") <= last:
        months.append(current)
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def check_complete(threads: list[Thread]) -> None:
    last = max(t.month for t in threads)
    have = {(t.kind, t.month) for t in threads}
    missing = [
        (kind, month)
        for kind, first in (("hiring", FIRST_MONTH), ("seeking", SEEKING_FIRST_MONTH))
        for month in month_range(first, last)
        if (kind, month) not in have
    ]
    if missing:
        raise RuntimeError(f"no thread found for {missing}")


def is_frozen(thread: Thread) -> bool:
    """A thread fetched after its snapshot window closed is final and never re-fetched."""
    data_path, meta_path = raw_paths(thread)
    if not meta_path.exists():
        return False
    fetched_at = datetime.fromisoformat(json.loads(meta_path.read_text())["fetched_at"])
    created_at_i = json.loads(gzip.decompress(data_path.read_bytes()))["created_at_i"]
    snapshot_at = datetime.fromtimestamp(created_at_i, UTC) + timedelta(
        days=SNAPSHOT_DAYS
    )
    return fetched_at >= snapshot_at


def plan(threads: list[Thread]) -> list[tuple[Thread, str]]:
    """'fetch' for threads still inside their window, 'kids' for frozen ones missing Firebase kids."""
    todo = []
    for thread in threads:
        meta_path = raw_paths(thread)[1]
        if not is_frozen(thread):
            todo.append((thread, "fetch"))
        elif "kids" not in json.loads(meta_path.read_text()):
            todo.append((thread, "kids"))
    return todo


def write_raw(path: Path, body: bytes) -> bool:
    """Write the raw response unless identical content is already stored."""
    if path.exists() and gzip.decompress(path.read_bytes()) == body:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    # mtime=0 keeps the gzip bytes identical for identical content, so git sees no spurious changes.
    path.write_bytes(gzip.compress(body, mtime=0))
    return True


def update(client: Client, thread: Thread, action: str) -> str:
    data_path, meta_path = raw_paths(thread)
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    checked_at = now()
    status = "kids added"
    if action == "fetch":
        response = client.get(f"{ALGOLIA}/items/{thread.thread_id}")
        status = "saved" if write_raw(data_path, response.content) else "unchanged"
        meta |= {
            "title": response.json()["title"],
            "fetched_at": checked_at,
            "source_url": str(response.url),
        }
    item = client.get(f"{FIREBASE}/item/{thread.thread_id}.json").json() or {}
    meta = {
        "thread_id": thread.thread_id,
        "kind": thread.kind,
        "month": thread.month,
        "title": meta["title"],
        "fetched_at": meta["fetched_at"],
        "checked_at": checked_at,
        "source_url": meta["source_url"],
        "kids": item.get("kids", []),
    }
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    return status


def run(con, args) -> None:
    client = Client()
    threads = discover(client)
    check_complete(threads)
    for kind in ("hiring", "seeking"):
        print(f"discovered {sum(t.kind == kind for t in threads)} {kind} threads")

    if args.month:
        threads = [t for t in threads if t.month == args.month]
    todo = plan(threads)
    if args.limit:
        todo = todo[: args.limit]
    print(f"{len(todo)} threads to update, {len(threads) - len(todo)} frozen")
    for thread, action in todo:
        label = f"{thread.month} {thread.kind} {thread.thread_id}"
        if args.dry_run:
            print(f"  {label}: would {action}")
        else:
            print(f"  {label}: {update(client, thread, action)}")
