import gzip

import pytest

from sejr import fetch
from sejr.fetch import Thread, parse_title, pick


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Ask HN: Who is Hiring? (April 2011)", ("hiring", "2011-04")),
        ("Ask HN: Who Is Hiring? (May 2012)", ("hiring", "2012-05")),
        ("Ask HN: Who is hiring? (November 2026)", ("hiring", "2026-11")),
        ("Ask HN: Who wants to be hired? (July 2014)", ("seeking", "2014-07")),
        ("Ask HN: Freelancer? Seeking freelancer? (May 2015)", None),
        ("Ask HN: Who is hiring right now?", None),
        ("Ask HN: Who wants to be hired?", None),
        ("Ask HN: Who is hiring? (Smarch 2020)", None),
    ],
)
def test_parse_title(title, expected):
    assert parse_title(title) == expected


def test_pick_prefers_most_comments_then_lowest_id():
    small = Thread(3, "hiring", "2011-12", 4)
    big = Thread(2, "hiring", "2011-12", 251)
    tie = Thread(1, "hiring", "2011-12", 251)
    assert pick([small, big]) == big
    assert pick([big, tie, small]) == tie


def test_store_writes_only_when_content_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch, "RAW_DIR", tmp_path)
    thread = Thread(42, "hiring", "2026-11", 0)
    data_path, meta_path = fetch.raw_paths("hiring", "2026-11", 42)

    assert fetch.store(thread, b'{"id": 42}', "title", "https://example/items/42")
    first_meta = meta_path.read_text()
    assert gzip.decompress(data_path.read_bytes()) == b'{"id": 42}'

    assert not fetch.store(thread, b'{"id": 42}', "title", "https://example/items/42")
    assert meta_path.read_text() == first_meta

    assert fetch.store(
        thread, b'{"id": 42, "children": []}', "title", "https://example/items/42"
    )
    assert gzip.decompress(data_path.read_bytes()) == b'{"id": 42, "children": []}'
