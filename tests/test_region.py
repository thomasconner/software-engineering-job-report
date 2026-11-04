import json
from collections import Counter
from pathlib import Path

import pytest

from sejr.features.region import (
    REGIONS,
    hiring_regions,
    location_line,
    seeker_region,
)

SAMPLE = [
    json.loads(line)
    for line in (Path(__file__).parent / "fixtures" / "region_sample.jsonl")
    .read_text()
    .splitlines()
]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Location: Berlin, Germany\nRemote: Yes", "Berlin, Germany"),
        ("  * Location : Austin, TX\nRemote: No", "Austin, TX"),
        ("Location:\nToronto, ON\nRemote: Yes", "Toronto, ON"),
        ("Location: Reykjavik, Iceland Remote: Yes Willing to relocate: No", "Reykjavik, Iceland"),
        ("SEEKING WORK | Berlin | Remote", None),
    ],
)  # fmt: skip
def test_location_line(text, expected):
    assert location_line(text) == expected


@pytest.mark.parametrize(
    ("location", "region"),
    [
        ("Hanford, CA", "us"),
        ("Toronto, CA", "canada"),
        ("Valencia, CA", "us"),
        ("Valencia, Spain", "europe"),
        ("Indianapolis, IN", "us"),
        ("Hyderabad, IN", "india"),
        ("Lisbon, PT", "europe"),
        ("New Orleans, LA", "us"),
        ("LA", "us"),
        ("Portland, OR", "us"),
        ("Paris, TX", "us"),
        ("Berlin, DE", "europe"),
        ("Wilmington, DE", "us"),
        ("London, ON", "canada"),
        ("Cambridge, MA", "us"),
        ("Cambridge, UK", "uk"),
        ("New Mexico", "us"),
        ("Mexico City", "latam"),
        ("Sydney, Australia", "asia_pacific"),
        ("New South Wales", "asia_pacific"),
        ("Tel Aviv, Israel", "africa_mideast"),
        ("Georgia, UTC+4", "unknown"),
        ("Atlanta, Georgia", "us"),
        ("North America", "unknown"),
        ("EST", "unknown"),
        ("US time zones", "unknown"),
        ("Remote, CET", "unknown"),
        ("India (open to relocating to the US)", "india"),
    ],
)  # fmt: skip
def test_seeker_region(location, region):
    assert seeker_region(f"Location: {location}\nRemote: Yes") == region


def test_seeker_without_location_line_is_unknown():
    assert seeker_region("SEEKING WORK | Austin, TX | Remote") == "unknown"


@pytest.mark.parametrize(
    ("header", "regions", "open_to_us"),
    [
        ("Acme | Engineer | REMOTE (US)", ["us"], True),
        ("Acme | Engineer | REMOTE", ["unknown"], True),
        ("Acme | Engineer | REMOTE (EU)", ["europe"], False),
        ("Acme | Berlin, Germany | REMOTE", ["europe"], False),
        ("Acme | Remote (non-US)", ["unknown"], False),
        ("Acme | Remote (North America)", ["us", "canada"], True),
        ("Acme | Remote (Worldwide) | London", ["uk"], True),
        ("Acme | Remote (anywhere in India)", ["india"], False),
        ("Acme | Remote (US time zones)", ["unknown"], True),
        ("Acme | Remote (CET +/- 2h)", ["unknown"], False),
        ("Acme | London, UK or NYC | ONSITE", ["us", "uk"], True),
        ("Acme | Toronto | ONSITE", ["canada"], False),
        ("Acme | Paris | No remote", ["europe"], False),
        ("Acme IT | Engineer", ["unknown"], False),
    ],
)  # fmt: skip
def test_hiring_regions(header, regions, open_to_us):
    assert hiring_regions(header + "\n\nWe build things.") == (regions, open_to_us)


def _scores(pairs: list[tuple[set[str], set[str]]]) -> dict[str, tuple[float, float]]:
    """Per region (precision, recall) over (gold, predicted) region sets."""
    tp, fp, fn = Counter(), Counter(), Counter()
    for gold, predicted in pairs:
        for region in REGIONS:
            if region in gold and region in predicted:
                tp[region] += 1
            elif region in predicted:
                fp[region] += 1
            elif region in gold:
                fn[region] += 1
    return {
        r: (tp[r] / (tp[r] + fp[r] or 1), tp[r] / (tp[r] + fn[r] or 1)) for r in REGIONS
    }


# 150 Location lines and 150 hiring headers, seeded and stratified by era, labeled by hand
# blind to the regex. At the time of writing seekers scored 146/150 and hiring 150/150
# (146 before the "US time zones is a time zone" rule). The US ratio divides US seekers
# by US-open hiring posts, so a 5% error on either side moves it about 5%, well inside its
# noise bar (about 18% a year apart). The floors leave room for a couple of new misses but
# fail a rule change that breaks several labeled lines.
ACCURACY_FLOOR = 0.95
US_FLOOR = 0.95


def test_seeker_region_accuracy_on_labeled_sample():
    rows = [r for r in SAMPLE if r["kind"] == "seeking"]
    assert len(rows) == 150
    pairs = [({r["region"]}, {seeker_region(f"Location: {r['text']}")}) for r in rows]
    accuracy = sum(gold == predicted for gold, predicted in pairs) / len(pairs)
    assert accuracy >= ACCURACY_FLOOR
    precision, recall = _scores(pairs)["us"]
    assert precision >= US_FLOOR and recall >= US_FLOOR


def test_hiring_region_accuracy_on_labeled_sample():
    rows = [r for r in SAMPLE if r["kind"] == "hiring"]
    assert len(rows) == 150
    predicted = [hiring_regions(r["text"]) for r in rows]
    pairs = [
        (set(r["regions"]), set(p[0])) for r, p in zip(rows, predicted, strict=True)
    ]
    accuracy = sum(gold == found for gold, found in pairs) / len(pairs)
    assert accuracy >= ACCURACY_FLOOR
    precision, recall = _scores(pairs)["us"]
    assert precision >= US_FLOOR and recall >= US_FLOOR
    open_ok = sum(r["open_to_us"] == p[1] for r, p in zip(rows, predicted, strict=True))
    assert open_ok / len(rows) >= ACCURACY_FLOOR
