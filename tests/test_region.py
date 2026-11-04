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

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> list[dict]:
    return [json.loads(line) for line in (FIXTURES / name).read_text().splitlines()]


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
        ("Royal Oak, Mi", "us"),
        ("Santa Fe, In the mountains", "unknown"),
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
        ("Acme IT | Engineer", ["unknown"], None),
        ("Acme | Remote | EU, UK", ["uk", "europe"], False),
        ("Acme | Remote (US, CA)", ["us", "canada"], True),
        ("Acme | Durham, UK | ONSITE", ["uk"], False),
        ("Acme | H1B OK | Part-time OK | Berlin", ["europe"], False),
        ("Acme | FULL-TIME, OR CONTRACT | Berlin", ["europe"], False),
        ("Acme | REMOTE OK, CAN OFFER VISA", ["unknown"], True),
        ("Acme | Remote in US & CAN", ["us", "canada"], True),
        ("Bank of America | London, UK | Onsite", ["uk"], False),
        ("Acme | Elixir/Phoenix/LiveView | Vancouver | Onsite", ["canada"], False),
        ("Acme | Phoenix, AZ | Onsite", ["us"], True),
        ("Acme | Amman-Jordan | Onsite", ["africa_mideast"], False),
        ("Acme | Seattle, WA-US | Onsite", ["us"], True),
        ("Acme | Ciudad de México | Onsite", ["latam"], False),
        ("Acme | Lima, Perú | Onsite", ["latam"], False),
        ("Acme | Remote, VA", ["us"], True),
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


# Two hand-labeled sets of Location lines and hiring headers. region_sample was drawn
# seeded and stratified by era (2011–26) and labeled blind to the regex, but rules were
# then tuned against it, so it is in-sample. region_heldout is a reviewer's seeded draw
# from 2015–26 (posts with no Location line dropped), labeled blind to the regex before
# the second round of rules; only general patterns were fixed after it. Current scores:
# in-sample seekers 147/150, hiring and open_to_us 150/150; held-out seekers 188/190,
# hiring 197/200, open_to_us 199/200. The US ratio scales by the US seeker share and the
# open-to-US share, so a 5% error on either side moves it about 5%, well inside its noise
# bar (about 30% a year apart). The floors leave room for a few new misses but fail a rule
# change that breaks several labeled lines.
ACCURACY_FLOOR = 0.95
US_FLOOR = 0.95
SETS = [("region_sample.jsonl", 150, 150), ("region_heldout.jsonl", 190, 200)]


@pytest.mark.parametrize(("name", "seekers", "headers"), SETS)
def test_seeker_region_accuracy(name, seekers, headers):
    rows = [r for r in _load(name) if r["kind"] == "seeking"]
    assert len(rows) == seekers
    pairs = [({r["region"]}, {seeker_region(f"Location: {r['text']}")}) for r in rows]
    accuracy = sum(gold == predicted for gold, predicted in pairs) / len(pairs)
    assert accuracy >= ACCURACY_FLOOR
    precision, recall = _scores(pairs)["us"]
    assert precision >= US_FLOOR and recall >= US_FLOOR


@pytest.mark.parametrize(("name", "seekers", "headers"), SETS)
def test_hiring_region_accuracy(name, seekers, headers):
    rows = [r for r in _load(name) if r["kind"] == "hiring"]
    assert len(rows) == headers
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
