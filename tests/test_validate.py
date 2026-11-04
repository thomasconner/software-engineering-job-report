import json
from argparse import Namespace
from pathlib import Path

import pytest
from fakes import FakeJev, make_db

from sejr import validate
from sejr.config import JEV_MODEL


@pytest.fixture
def con(tmp_path: Path):
    con = make_db(tmp_path / "test.duckdb")
    con.execute(
        "INSERT INTO posts VALUES (13, 2, 'b', TIMESTAMPTZ '2014-03-04 10:00:00Z', '',"
        " 'Location: Oslo. Six months of rejections, I will take anything.', true)"
    )
    yield con
    con.close()


LABELS = [
    {"post_id": 10, "kind": "hiring", "era": "2011-14", "month": "2014-03",
     "labels": {"work_mode": "remote", "seniority": "senior", "ai_native": 1},
     "source": "agreed"},
    {"post_id": 30, "kind": "hiring", "era": "2015-19", "month": "2014-04",
     "labels": {"work_mode": "onsite"}, "source": "adjudicated"},
    {"post_id": 11, "kind": "seeking", "era": "2011-14", "month": "2014-03",
     "labels": {"seeker_mood": 2}, "source": "agreed"},
    {"post_id": 13, "kind": "seeking", "era": "2011-14", "month": "2014-03",
     "labels": {"seeker_mood": 0}, "source": "oversample_mood"},
    {"post_id": 12, "kind": "hiring", "era": "2011-14", "month": "2014-03",
     "labels": {"work_mode": "hybrid"}, "source": "agreed", "exclude": True},
]  # fmt: skip


def run(con, tmp_path: Path, fake: FakeJev, labels=LABELS, dry_run=False) -> dict:
    labels_path = tmp_path / "reference.jsonl"
    labels_path.write_text("".join(json.dumps(r) + "\n" for r in labels))
    out = tmp_path / "validation.json"
    validate.run(
        con,
        Namespace(dry_run=dry_run),
        labels_path=labels_path,
        out_path=out,
        client=fake.client(),
        cache_dir=tmp_path / "cache",
        answers_dir=tmp_path / "answers",
    )
    return json.loads(out.read_text()) if out.exists() else {}


def test_classifies_only_reference_posts_once(con, tmp_path: Path):
    first = FakeJev()
    run(con, tmp_path, first)
    # 10, 30, 11 and 13; 12 is excluded (and out of snapshot).
    assert first.calls == 4
    second = FakeJev()
    run(con, tmp_path, second)
    assert second.calls == 0


def test_choice_metrics(con, tmp_path: Path):
    # The fake gives the first option 0.7 and the second 0.3.
    report = run(con, tmp_path, FakeJev())
    assert (report["model"], set(report["qset"])) == (JEV_MODEL, {"hiring", "seeking"})
    work_mode = report["questions"]["work_mode"]
    assert work_mode["by_era"]["2011-14"]["n"] == 1  # excluded post 12 skipped
    assert work_mode["by_era"]["2011-14"]["accuracy"] == 1
    assert work_mode["by_era"]["2011-14"]["brier"] == pytest.approx(0.18)
    assert work_mode["by_era"]["2015-19"]["accuracy"] == 0
    assert work_mode["overall"]["n"] == 2
    seniority = report["questions"]["seniority"]["overall"]
    assert (seniority["accuracy"], seniority["brier"]) == (0, pytest.approx(1.58))
    assert report["questions"]["industry"]["overall"] == {"n": 0}


def test_noul_metrics(con, tmp_path: Path):
    ai = run(con, tmp_path, FakeJev(nouls={"ai_native": 0.8}))["questions"]["ai_native"]
    overall = ai["overall"]
    assert (overall["n"], overall["accuracy"]) == (1, 1)
    assert overall["brier"] == pytest.approx(0.04)
    assert overall["share_error"] == pytest.approx(0.2)


def test_score_metrics_keep_oversampled_rows_out_of_share_bias(con, tmp_path: Path):
    # The fake scores every seeker 2.5 with P(2) = P(3) = 0.5.
    mood = run(con, tmp_path, FakeJev())["questions"]["seeker_mood"]["overall"]
    assert mood["n"] == 2
    assert mood["accuracy"] == 0.5
    assert mood["brier"] == pytest.approx((0.5 + 1.5) / 2)
    assert mood["mae"] == pytest.approx((0.5 + 2.5) / 2)
    assert mood["n_share"] == 1
    assert mood["mean_score_error"] == pytest.approx(0.5)
    # With the oversampled discouraged post included this would be 0.5.
    assert mood["strained_share_error"] == 0


def test_reference_post_missing_from_db_fails(con, tmp_path: Path):
    labels = [*LABELS, {**LABELS[0], "post_id": 999}]
    with pytest.raises(SystemExit, match="1 reference posts"):
        run(con, tmp_path, FakeJev(), labels=labels)


def test_dry_run_writes_nothing(con, tmp_path: Path):
    fake = FakeJev()
    assert run(con, tmp_path, fake, dry_run=True) == {}
    assert fake.calls == 0
