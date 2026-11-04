import gzip
import json
from argparse import Namespace
from pathlib import Path

import pytest

from sejr.db import connect
from sejr.normalize import html_to_text, run

FIXTURE = Path(__file__).parent / "fixtures" / "item_50338728.json"
THREAD_CREATED = 1793635297


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ("First<p>Second<p>Third", "First\n\nSecond\n\nThird"),
        ("Tom &amp; Jerry&#x27;s &quot;shop&quot; &lt;3", 'Tom & Jerry\'s "shop" <3'),
        ("typed\nline  break", "typed\nline break"),
        ("  one \n\n  line\t\tbreak", "one\nline break"),
        (
            '<a href="https:&#x2F;&#x2F;example.com&#x2F;jobs" rel="nofollow">https:&#x2F;&#x2F;example.com&#x2F;jobs</a>',
            "https://example.com/jobs",
        ),
        (
            'Apply: <a href="https://jobs.example.com/a/very/long/path/123">https://jobs.example.com/a/very/...</a>',
            "Apply: https://jobs.example.com/a/very/long/path/123",
        ),
        (
            'See <a href="https://example.com/careers">our careers page</a>.',
            "See our careers page (https://example.com/careers).",
        ),
        ("We <i>love</i> Rust", "We love Rust"),
        (
            "Apply:<p><pre><code>  curl https://x.dev/jobs\n  | sh\n</code></pre>\nThanks",
            "Apply:\n\n  curl https://x.dev/jobs\n  | sh\n\nThanks",
        ),
        ("", ""),
    ],
)
def test_html_to_text(html, expected):
    assert html_to_text(html) == expected


@pytest.fixture
def raw_dir(tmp_path: Path) -> Path:
    folder = tmp_path / "hiring" / "2026-11"
    folder.mkdir(parents=True)
    (folder / "50338728.json.gz").write_bytes(gzip.compress(FIXTURE.read_bytes()))
    meta = {
        "thread_id": 50338728,
        "kind": "hiring",
        "month": "2026-11",
        "title": "Ask HN: Who is hiring? (November 2026)",
        "fetched_at": "2026-11-04T12:00:00Z",
        "checked_at": "2026-11-04T12:00:00Z",
        "source_url": "https://hn.algolia.com/api/v1/items/50338728",
        # 50338740 is missing from Algolia inside the window; 50339999 is after it.
        "kids": [50338732, 50338736, 50338740, 50338768, 50339999],
    }
    (folder / "50338728.meta.json").write_text(json.dumps(meta))
    return tmp_path


def normalize(con, raw_dir: Path, month: str | None = None) -> None:
    run(con, Namespace(month=month, limit=None, dry_run=False), raw_dir=raw_dir)


def test_normalize_loads_thread_posts_and_replies(raw_dir):
    con = connect(":memory:")
    normalize(con, raw_dir)

    assert con.execute(
        "SELECT kind, month::VARCHAR, epoch(created_at), epoch(snapshot_at),"
        " fetched_at::VARCHAR, removed_in_snapshot FROM threads"
    ).fetchall() == [
        (
            "hiring",
            "2026-11-01",
            THREAD_CREATED,
            THREAD_CREATED + 7 * 24 * 3600,
            "2026-11-04 12:00:00+00",
            1,
        )
    ]
    posts = con.execute(
        "SELECT post_id, author, in_snapshot FROM posts ORDER BY post_id"
    ).fetchall()
    assert posts == [
        (50338732, "AdriaanvRossum", True),
        (50338736, "benchaupt", True),
        (50338768, "sadiq", True),
    ]
    replies = con.execute(
        "SELECT reply_id, post_id, parent_id, depth, in_snapshot FROM replies ORDER BY reply_id"
    ).fetchall()
    assert replies == [
        (50339964, 50338732, 50338732, 1, True),
        (50340270, 50338732, 50339964, 2, False),
    ]
    text = con.execute("SELECT text FROM posts WHERE post_id = 50338736").fetchone()[0]
    assert text.startswith(
        "Synteq | Growth Lead & Systems Administrator | Austin, TX | REMOTE (US)"
    )


def test_snapshot_boundary_is_inclusive(raw_dir):
    con = connect(":memory:")
    normalize(con, raw_dir)
    on_boundary = con.execute(
        "SELECT p.in_snapshot, p.created_at = t.snapshot_at FROM posts p JOIN threads t USING (thread_id) WHERE post_id = 50338768"
    ).fetchone()
    one_second_late = con.execute(
        "SELECT r.in_snapshot, epoch(r.created_at) - epoch(t.snapshot_at) FROM replies r JOIN threads t USING (thread_id) WHERE reply_id = 50340270"
    ).fetchone()
    assert on_boundary == (True, True)
    assert one_second_late == (False, 1)


def test_normalize_drops_dead_deleted_and_empty_comments(raw_dir, capsys):
    con = connect(":memory:")
    normalize(con, raw_dir)
    ids = {
        row[0]
        for row in con.execute(
            "SELECT post_id FROM posts UNION ALL SELECT reply_id FROM replies"
        ).fetchall()
    }
    assert ids.isdisjoint({90000001, 90000002, 90000003, 90000004})
    assert "dropped 2 posts and 1 replies" in capsys.readouterr().out


def test_normalize_is_idempotent(raw_dir):
    con = connect(":memory:")
    snapshot = "SELECT COLUMNS(*)::VARCHAR FROM {} ORDER BY 1"
    tables = ("threads", "posts", "replies")

    normalize(con, raw_dir)
    first = {t: con.execute(snapshot.format(t)).fetchall() for t in tables}
    normalize(con, raw_dir)
    normalize(con, raw_dir, month="2026-11")
    second = {t: con.execute(snapshot.format(t)).fetchall() for t in tables}

    assert first == second
    assert len(first["posts"]) == 3


def test_removed_count_is_null_without_kids(raw_dir):
    meta_path = raw_dir / "hiring" / "2026-11" / "50338728.meta.json"
    meta = json.loads(meta_path.read_text())
    del meta["kids"]
    meta_path.write_text(json.dumps(meta))
    con = connect(":memory:")
    normalize(con, raw_dir)
    assert con.execute("SELECT removed_in_snapshot FROM threads").fetchone() == (None,)


def test_two_threads_for_one_month_fail_clearly(raw_dir):
    folder = raw_dir / "hiring" / "2026-11"
    item = json.loads(FIXTURE.read_text())
    item |= {"id": 1, "children": []}
    (folder / "1.json.gz").write_bytes(gzip.compress(json.dumps(item).encode()))
    meta = json.loads((folder / "50338728.meta.json").read_text())
    (folder / "1.meta.json").write_text(json.dumps(meta | {"thread_id": 1}))

    con = connect(":memory:")
    with pytest.raises(RuntimeError, match="same \\(kind, month\\)"):
        normalize(con, raw_dir)
