import gzip
import json
import re

import pytest

from sejr import fetch
from sejr.fetch import Thread, check_complete, discover, parse_title, pick


class FakeResponse:
    def __init__(self, url: str, payload) -> None:
        self.url = url
        self.payload = payload
        self.content = json.dumps(payload).encode()

    def json(self):
        return self.payload


class FakeClient:
    """Serves Algolia search pages (page_size hits, honoring created_at_i filters) and items."""

    def __init__(self, stories: dict[str, list[dict]], items=None, page_size=2):
        self.stories = stories
        self.items = items or {}
        self.page_size = page_size
        self.urls: list[str] = []

    def get(self, url: str, params: dict | None = None) -> FakeResponse:
        self.urls.append(url)
        if url.endswith("/search_by_date"):
            author = params["tags"].removeprefix("story,author_")
            hits = sorted(
                self.stories.get(author, []), key=lambda h: -h["created_at_i"]
            )
            if "numericFilters" in params:
                op, value = re.fullmatch(
                    r"created_at_i([<=])(\d+)", params["numericFilters"]
                ).groups()
                if op == "<":
                    hits = [h for h in hits if h["created_at_i"] < int(value)]
                else:
                    hits = [h for h in hits if h["created_at_i"] == int(value)]
            return FakeResponse(url, {"hits": hits[: self.page_size]})
        return FakeResponse(url, self.items[url])


def hit(object_id: int, title: str, created_at_i: int, num_comments: int = 100) -> dict:
    return {
        "objectID": str(object_id),
        "title": title,
        "created_at_i": created_at_i,
        "num_comments": num_comments,
    }


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Ask HN: Who is Hiring? (April 2011)", ("hiring", "2011-04")),
        ("Ask HN: Who Is Hiring? (May 2012)", ("hiring", "2012-05")),
        ("Ask HN: Who is hiring? (November 2026)", ("hiring", "2026-11")),
        ("Ask HN: Who wants to be hired? (July 2014)", ("seeking", "2014-07")),
        ("Ask HN: Who is hiring? (Sept 2019)", ("hiring", "2019-09")),
        ("Ask HN: Who is hiring? (Jan. 2020)", ("hiring", "2020-01")),
        ("Ask HN: Freelancer? Seeking freelancer? (May 2015)", None),
        ("Ask HN: Who is hiring right now?", None),
        ("Ask HN: Who wants to be hired?", None),
        ("Ask HN: Who is hiring? (Smarch 2020)", None),
    ],
)
def test_parse_title(title, expected):
    assert parse_title(title) == expected


def test_pick_prefers_most_comments_then_lowest_id():
    small = hit(3, "", 0, 4)
    big = hit(2, "", 0, 251)
    tie = hit(1, "", 0, 251)
    assert pick([small, big]) == big
    assert pick([big, tie, small]) == tie


def test_discover_pages_filters_and_applies_overrides(monkeypatch, capsys):
    monkeypatch.setattr(fetch, "EXTRA_THREADS", {900: ("hiring", "2011-12")})
    stories = {
        "whoishiring": [
            hit(1, "Ask HN: Who is Hiring? (March 2011)", 100),
            hit(2, "Ask HN: Who is Hiring? (April 2011)", 200),
            # Three stories in one second straddle the first page boundary.
            hit(3, "Ask HN: Who is Hiring? (May 2011)", 300),
            hit(4, "Ask HN: Freelancer? Seeking freelancer? (May 2011)", 300),
            hit(8, "Ask HN: Who wants to be hired? (May 2011)", 300),
            hit(5, "Ask HN: Who is Hiring? (December 2011)", 400, num_comments=4),
            hit(6, "Ask HN: Who is hiring right now?", 500),
        ],
        "_whoishiring": [hit(7, "Ask HN: Who wants to be hired? (May 2015)", 600)],
    }
    threads = discover(FakeClient(stories, page_size=3))

    assert threads == [
        Thread(2, "hiring", "2011-04"),
        Thread(3, "hiring", "2011-05"),
        Thread(8, "seeking", "2011-05"),
        Thread(900, "hiring", "2011-12"),
        Thread(7, "seeking", "2015-05"),
    ]
    assert (
        "skipped title 6: Ask HN: Who is hiring right now?" in capsys.readouterr().out
    )


def test_check_complete_fails_on_missing_month():
    threads = [Thread(1, "hiring", "2011-04"), Thread(2, "hiring", "2011-06")]
    with pytest.raises(RuntimeError, match=r"\('hiring', '2011-05'\)"):
        check_complete(threads)


def test_check_complete_requires_seeking_from_may_2014(monkeypatch):
    monkeypatch.setattr(fetch, "FIRST_MONTH", "2014-04")
    threads = [Thread(1, "hiring", "2014-04"), Thread(2, "hiring", "2014-05")]
    with pytest.raises(RuntimeError, match=r"\('seeking', '2014-05'\)"):
        check_complete(threads)
    check_complete([*threads, Thread(3, "seeking", "2014-05")])


def test_write_raw_only_when_content_changes(tmp_path):
    path = tmp_path / "1.json.gz"
    assert fetch.write_raw(path, b'{"id": 1}')
    first = path.read_bytes()
    assert not fetch.write_raw(path, b'{"id": 1}')
    assert path.read_bytes() == first
    assert fetch.write_raw(path, b'{"id": 1, "children": []}')
    assert gzip.decompress(path.read_bytes()) == b'{"id": 1, "children": []}'


def test_threads_freeze_once_fetched_after_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch, "RAW_DIR", tmp_path)
    thread = Thread(42, "hiring", "2026-11")
    created = 1_793_635_297
    item_url = f"{fetch.ALGOLIA}/items/42"
    kids_url = f"{fetch.FIREBASE}/item/42.json"
    client = FakeClient(
        {},
        {
            item_url: {"id": 42, "title": "T", "created_at_i": created, "children": []},
            kids_url: {"id": 42, "kids": [7, 8]},
        },
    )
    week = 7 * 24 * 3600
    times = iter([created + week - 1, created + week])
    monkeypatch.setattr(
        fetch,
        "now",
        lambda: fetch.datetime.fromtimestamp(next(times), fetch.UTC).isoformat(),
    )

    assert fetch.plan([thread]) == [(thread, "fetch")]
    assert fetch.update(client, thread, "fetch") == "saved"
    assert fetch.plan([thread]) == [(thread, "fetch")]

    assert fetch.update(client, thread, "fetch") == "unchanged"
    meta = json.loads(fetch.raw_paths(thread)[1].read_text())
    assert meta["kids"] == [7, 8]
    assert meta["fetched_at"] == meta["checked_at"]
    assert fetch.plan([thread]) == []

    del meta["kids"]
    fetch.raw_paths(thread)[1].write_text(json.dumps(meta))
    assert fetch.plan([thread]) == [(thread, "kids")]
