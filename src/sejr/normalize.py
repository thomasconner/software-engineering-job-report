import gzip
import json
import re
import tempfile
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path

import duckdb

from sejr.config import RAW_DIR, SNAPSHOT_DAYS

DROPPED_TEXTS = {"", "[dead]", "[flagged]", "[deleted]"}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.paragraphs: list[str] = [""]
        self.in_pre = False
        self.href: str | None = None
        self.link_text = ""

    def _write(self, text: str) -> None:
        if self.href is not None:
            self.link_text += text
            return
        if not self.in_pre and not self.paragraphs[-1].strip():
            self.paragraphs[-1] = ""
            text = text.lstrip()
        self.paragraphs[-1] += text

    def _break(self) -> None:
        if self.paragraphs[-1].strip():
            self.paragraphs.append("")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "p":
            self._break()
        elif tag == "pre":
            self._break()
            self.in_pre = True
        elif tag == "a":
            self.href = dict(attrs).get("href") or ""
            self.link_text = ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "pre":
            self.in_pre = False
            self._break()
        elif tag == "a" and self.href is not None:
            href, label = self.href, self.link_text.strip()
            self.href = None
            # HN shortens long link labels to "https://example.com/long/pa..."; the href is the full URL.
            if not label or href.startswith(label.removesuffix("...")):
                self._write(href)
            else:
                self._write(f"{label} ({href})")

    def handle_data(self, data: str) -> None:
        if not self.in_pre:
            # A bare newline is one the author typed; keep it as a single line break.
            data = re.sub(r"[^\S\n]*\n\s*", "\n", data)
            data = re.sub(r"[^\S\n]+", " ", data)
        self._write(data)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    text = "\n\n".join(p.strip("\n").rstrip() for p in parser.paragraphs if p.strip())
    return re.sub(r"[ \t]+\n", "\n", text).lstrip()


def to_datetime(epoch: int) -> datetime:
    return datetime.fromtimestamp(epoch, UTC)


def is_dropped(comment: dict) -> bool:
    return (
        comment.get("author") is None
        or (comment.get("text") or "").strip() in DROPPED_TEXTS
    )


def raw_files(raw_dir: Path) -> list[tuple[dict, Path]]:
    files = []
    for meta_path in sorted(raw_dir.glob("*/*/*.meta.json")):
        meta = json.loads(meta_path.read_text())
        files.append((meta, meta_path.with_name(f"{meta['thread_id']}.json.gz")))
    return files


def flatten(
    meta: dict, item: dict, dropped: Counter
) -> tuple[dict, list[dict], list[dict]]:
    created_at = to_datetime(item["created_at_i"])
    snapshot_at = created_at + timedelta(days=SNAPSHOT_DAYS)
    thread = {
        "thread_id": meta["thread_id"],
        "kind": meta["kind"],
        "month": date.fromisoformat(f"{meta['month']}-01"),
        "title": meta["title"],
        "created_at": created_at,
        "snapshot_at": snapshot_at,
        "fetched_at": datetime.fromisoformat(meta["fetched_at"]),
        "removed_in_snapshot": None,
    }
    posts: list[dict] = []
    replies: list[dict] = []

    def walk(node: dict, post_id: int, depth: int) -> None:
        for child in node.get("children") or []:
            if is_dropped(child):
                dropped["post" if depth == 0 else "reply"] += 1
                dropped["descendant"] += count_descendants(child)
                continue
            child_created = to_datetime(child["created_at_i"])
            row = {
                "author": child["author"],
                "created_at": child_created,
                "text": html_to_text(child["text"]),
                "in_snapshot": child_created <= snapshot_at,
            }
            if depth == 0:
                posts.append(
                    {
                        "post_id": child["id"],
                        "thread_id": meta["thread_id"],
                        "text_html": child["text"],
                    }
                    | row
                )
                walk(child, child["id"], 1)
            else:
                replies.append(
                    {
                        "reply_id": child["id"],
                        "post_id": post_id,
                        "parent_id": child["parent_id"],
                        "thread_id": meta["thread_id"],
                        "depth": depth,
                    }
                    | row
                )
                walk(child, post_id, depth + 1)

    walk(item, 0, 0)
    if "kids" in meta:
        thread["removed_in_snapshot"] = count_removed(meta["kids"], posts, replies)
    return thread, posts, replies


def count_removed(kids: list[int], posts: list[dict], replies: list[dict]) -> int:
    """Top-level comments Firebase lists but Algolia omits, within the snapshot window.

    HN ids rise over time, so a removed kid belongs to the window when its id is no
    higher than the newest comment we can date inside the window.
    """
    in_window = [p["post_id"] for p in posts if p["in_snapshot"]]
    in_window += [r["reply_id"] for r in replies if r["in_snapshot"]]
    if not in_window:
        return 0
    cutoff = max(in_window)
    present = {p["post_id"] for p in posts}
    return sum(1 for kid in kids if kid not in present and kid <= cutoff)


def count_descendants(node: dict) -> int:
    return sum(1 + count_descendants(child) for child in node.get("children") or [])


def insert(
    con: duckdb.DuckDBPyConnection, table: str, rows: list[dict], folder: Path
) -> None:
    # Bulk-loading through a JSON file is far faster than executemany for hundreds of thousands of rows.
    if not rows:
        return
    path = folder / f"{table}.jsonl"
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, default=str) + "\n")
    types = {
        name: kind for name, kind, *_ in con.execute(f"DESCRIBE {table}").fetchall()
    }
    columns = list(types)
    spec = "{" + ", ".join(f"'{c}': '{t}'" for c, t in types.items()) + "}"
    con.execute(
        f"INSERT INTO {table} ({', '.join(columns)}) "
        f"SELECT {', '.join(columns)} FROM read_json(?, format='newline_delimited', columns={spec})",
        [str(path)],
    )


def run(con: duckdb.DuckDBPyConnection, args, raw_dir: Path = RAW_DIR) -> None:
    files = raw_files(raw_dir)
    if args.month:
        files = [(meta, path) for meta, path in files if meta["month"] == args.month]
    if args.limit:
        files = files[: args.limit]

    threads, posts, replies = [], [], []
    dropped: Counter = Counter()
    for meta, path in files:
        thread, thread_posts, thread_replies = flatten(
            meta, json.loads(gzip.decompress(path.read_bytes())), dropped
        )
        threads.append(thread)
        posts.extend(thread_posts)
        replies.extend(thread_replies)

    print(f"{len(threads)} threads, {len(posts)} posts, {len(replies)} replies")
    print(
        f"dropped {dropped['post']} posts and {dropped['reply']} replies (empty, deleted, dead or flagged), "
        f"plus {dropped['descendant']} comments beneath them"
    )
    if args.dry_run:
        return

    thread_ids = [t["thread_id"] for t in threads]
    con.execute("BEGIN")
    if args.month or args.limit:
        for table in ("replies", "posts", "threads"):
            con.execute(
                f"DELETE FROM {table} WHERE thread_id IN (SELECT unnest(?))",
                [thread_ids],
            )
    else:
        for table in ("replies", "posts", "threads"):
            con.execute(f"DELETE FROM {table}")
    with tempfile.TemporaryDirectory() as folder:
        try:
            insert(con, "threads", threads, Path(folder))
        except duckdb.ConstraintException as e:
            con.execute("ROLLBACK")
            raise RuntimeError(
                "two raw files claim the same thread or the same (kind, month); "
                f"keep one per month under {raw_dir}: {e}"
            ) from e
        insert(con, "posts", posts, Path(folder))
        insert(con, "replies", replies, Path(folder))
    con.execute("COMMIT")
