import asyncio
import json
from argparse import Namespace
from pathlib import Path

import httpx2
import pytest
from fakes import HIRING_TEXT, SEEKING_TEXT, FakeJev, make_db

from sejr import classify
from sejr.classify import jev
from sejr.classify.questions import QUESTIONS
from sejr.config import JEV_MODEL


@pytest.fixture
def con(tmp_path: Path):
    con = make_db(tmp_path / "test.duckdb")
    yield con
    con.close()


@pytest.fixture
def dirs(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "cache", tmp_path / "answers"


def run(con, fake: FakeJev, dirs: tuple[Path, Path], **kwargs) -> None:
    args = Namespace(
        month=kwargs.get("month", "2014-03"),
        limit=kwargs.get("limit"),
        dry_run=kwargs.get("dry_run", False),
        backfill=kwargs.get("backfill", False),
    )
    cache_dir, answers_dir = dirs
    classify.run(
        con, args, client=fake.client(), cache_dir=cache_dir, answers_dir=answers_dir
    )


def answers(con) -> dict[tuple[int, str], tuple]:
    rows = con.execute(
        "SELECT post_id, question, method, version, value, label, probabilities, "
        "confidence FROM answers"
    ).fetchall()
    return {(r[0], r[1]): r[2:] for r in rows}


def test_request_has_all_questions_for_kind_and_pinned_model():
    request = jev.build_request("hiring", HIRING_TEXT)
    assert list(request) == ["model", "state", "questions"]
    assert request["model"] == JEV_MODEL
    assert set(request["questions"]) == set(QUESTIONS["hiring"])
    assert set(jev.build_request("seeking", SEEKING_TEXT)["questions"]) == {
        "seeker_mood"
    }


def test_golden_request_hash(tmp_path: Path):
    # Fails on any change to the questions, the state cleaning or the model pin. If the
    # change was deliberate, update the hash: every post of that kind will re-run.
    path = jev.cache_path(tmp_path, jev.build_request("hiring", HIRING_TEXT))
    assert path.relative_to(tmp_path).as_posix() == (
        "a7/a79c8049c157ed68a3d238e18c80341514349600fa5dd697f0d54d134a2950ec.json"
    )


def test_fits_sector_list_comes_from_industry_options():
    fits = jev.wire_questions("hiring")["industry_fits"]["instructions"]["sectors"]
    assert fits == jev.wire_questions("hiring")["industry"]["criteria"]


def test_state_is_cleaned_and_truncated():
    assert jev.build_state("  a  \n\n\n\nb \n") == "a\n\nb"
    long_text = ("word " * 400 + "\n\n") * 5
    state = jev.build_state(long_text)
    assert len(state) <= jev.MAX_STATE_CHARS + len(jev.TRUNCATION_MARK)
    assert state.endswith(jev.TRUNCATION_MARK)


def test_question_change_changes_cache_key(tmp_path: Path):
    request = jev.build_request("hiring", HIRING_TEXT)
    edited = json.loads(json.dumps(request))
    edited["questions"]["new_grad"]["instructions"] += " Edited."
    assert jev.cache_path(tmp_path, request) != jev.cache_path(tmp_path, edited)


def test_only_in_snapshot_posts_and_no_dates_in_request(con, dirs):
    fake = FakeJev()
    run(con, fake, dirs)
    assert sorted(b["state"] for b in fake.bodies) == sorted(
        [HIRING_TEXT, SEEKING_TEXT]
    )
    for body in fake.bodies:
        assert set(body) == {"model", "state", "questions"}
        sent = json.dumps(body)
        for leak in ("2014", "March", "03-0", "Mar "):
            assert leak not in sent


def test_second_run_makes_zero_calls(con, dirs):
    first = FakeJev()
    run(con, first, dirs)
    assert first.calls == 2
    before = answers(con)
    cache_dir, _ = dirs
    cached = json.loads(next(cache_dir.glob("*/*.json")).read_text())
    assert set(cached) == {"request", "response"}

    second = FakeJev()
    run(con, second, dirs)
    assert second.calls == 0
    assert answers(con) == before


def test_fresh_checkout_loads_durable_answers(con, dirs, tmp_path: Path):
    run(con, FakeJev(), dirs)
    expected = answers(con)
    cache_dir, answers_dir = dirs
    assert [f.name for f in (answers_dir / JEV_MODEL).iterdir()] == ["2014-03.parquet"]

    fresh = make_db(tmp_path / "fresh.duckdb")
    for f in cache_dir.glob("*/*.json"):
        f.unlink()
    fake = FakeJev()
    run(fresh, fake, dirs)
    assert fake.calls == 0
    assert answers(fresh) == expected


def test_question_set_change_reruns_answered_posts(con, dirs, monkeypatch):
    run(con, FakeJev(), dirs)
    monkeypatch.setattr(classify, "question_set_hash", lambda kind: "edited")
    fake = FakeJev(nouls={"ai_native": 0.1})
    cache_dir, _ = dirs
    for f in cache_dir.glob("*/*.json"):
        f.unlink()
    run(con, fake, dirs)
    assert fake.calls == 2
    assert answers(con)[(10, "ai_native")][2] == 0.1


def test_answer_rows_for_each_primitive(con, dirs):
    run(con, FakeJev(), dirs)
    rows = answers(con)

    method, version, value, label, probabilities, confidence = rows[(10, "work_mode")]
    assert (method, version, value, label, confidence) == (
        "jev",
        JEV_MODEL,
        None,
        "remote",
        0.6,
    )
    assert json.loads(probabilities)["remote"] == 0.7

    _, _, value, label, probabilities, confidence = rows[(11, "seeker_mood")]
    assert (value, label, confidence) == (2.5, None, 0.4)
    assert json.loads(probabilities) == {
        "0": 0.0,
        "1": 0.0,
        "2": 0.5,
        "3": 0.5,
        "4": 0.0,
    }

    assert rows[(10, "ai_native")][2:] == (0.8, None, None, None)
    assert {q for p, q in rows if p == 10} == set(QUESTIONS["hiring"])


def test_industry_folds_both_companion_nouls(con, dirs):
    run(con, FakeJev(nouls={"industry_fits": 0.8, "industry_stated": 0.75}), dirs)
    _, _, _, label, probabilities, confidence = answers(con)[(10, "industry")]
    industry = json.loads(probabilities)
    assert industry["enterprise_saas"] == pytest.approx(0.56)
    assert industry["other"] == pytest.approx(0.15)
    assert industry["unstated"] == pytest.approx(0.05)
    assert sum(industry.values()) == pytest.approx(1.0)
    assert (label, confidence) == ("enterprise_saas", 0.6)


def test_folded_unstated_label_has_no_confidence(con, dirs):
    run(con, FakeJev(nouls={"industry_fits": 0.1, "industry_stated": 0.2}), dirs)
    _, _, _, label, _, confidence = answers(con)[(10, "industry")]
    assert (label, confidence) == ("unstated", None)


def test_version_mismatch_fails_loudly_and_caches_nothing(con, dirs):
    with pytest.raises(ExceptionGroup) as raised:
        run(con, FakeJev(model="jev-9.9.9"), dirs)
    assert raised.group_contains(jev.JevVersionMismatch)
    cache_dir, answers_dir = dirs
    assert list(cache_dir.glob("*/*.json")) == []
    assert answers(con) == {}
    assert not answers_dir.exists()


def test_partial_failure_writes_the_rest_and_exits_nonzero(con, dirs, capsys):
    with pytest.raises(SystemExit) as raised:
        run(con, FakeJev(reject="Acme"), dirs)
    assert raised.value.code != 0
    assert "post 10:" in capsys.readouterr().err
    rows = answers(con)
    assert (11, "seeker_mood") in rows
    assert not any(p == 10 for p, _ in rows)


def test_missing_industry_companion_fails_that_post(con, dirs, capsys):
    with pytest.raises(SystemExit):
        run(con, FakeJev(drop="industry_fits"), dirs)
    assert "industry_fits" in capsys.readouterr().err
    assert (11, "seeker_mood") in answers(con)


def test_missing_usage_tokens_count_as_zero(con, dirs, capsys):
    run(con, FakeJev(usage={}), dirs)
    assert "0 input tokens" in capsys.readouterr().out


def test_stale_jev_rows_are_deleted_and_other_methods_kept(con, dirs):
    con.execute(
        """INSERT INTO answers VALUES
        (10, 'retired_question', 'jev', 'jev-1.13.0', 1, NULL, NULL, NULL),
        (10, 'mentions_visa', 'regex', 'v1', 1, NULL, NULL, NULL)"""
    )
    run(con, FakeJev(), dirs)
    rows = answers(con)
    assert (10, "retired_question") not in rows
    assert (10, "mentions_visa") in rows


def test_month_run_leaves_other_months_alone(con, dirs):
    run(con, FakeJev(), dirs, month="2014-04")
    april = {k: v for k, v in answers(con).items() if k[0] == 30}
    _, answers_dir = dirs
    april_file = answers_dir / JEV_MODEL / "2014-04.parquet"
    april_bytes = april_file.read_bytes()

    run(con, FakeJev(nouls={"ai_native": 0.1}), dirs, month="2014-03")
    assert {k: v for k, v in answers(con).items() if k[0] == 30} == april
    assert april_file.read_bytes() == april_bytes
    assert (answers_dir / JEV_MODEL / "2014-03.parquet").exists()


def test_rate_limit_is_retried(con, dirs):
    fake = FakeJev(rate_limit_first=1)
    run(con, fake, dirs, limit=1)
    assert fake.calls == 2
    assert (10, "work_mode") in answers(con)


def test_month_and_limit_filters(con, dirs):
    fake = FakeJev()
    run(con, fake, dirs, month="2014-05")
    assert fake.calls == 0
    run(con, fake, dirs, limit=1)
    assert fake.calls == 1


def test_unscoped_run_needs_backfill_flag(con, dirs, monkeypatch):
    monkeypatch.setattr(classify, "MAX_UNSCOPED_CALLS", 2)
    fake = FakeJev()
    with pytest.raises(SystemExit, match="--backfill"):
        run(con, fake, dirs, month=None)
    assert fake.calls == 0
    run(con, fake, dirs, month=None, backfill=True)
    assert fake.calls == 3


def test_dry_run_estimates_without_calling(con, dirs, capsys):
    fake = FakeJev()
    run(con, fake, dirs, dry_run=True)
    assert fake.calls == 0
    out = capsys.readouterr().out
    tokens = sum(
        jev.estimate_tokens(jev.build_request(k, t))
        for k, t in [("hiring", HIRING_TEXT), ("seeking", SEEKING_TEXT)]
    )
    assert "2 requests to send" in out
    assert f"estimated input tokens: {tokens:,}" in out
    assert f"${tokens / 1e6 * 0.042:.4f}" in out
    _, answers_dir = dirs
    assert not answers_dir.exists()


def test_concurrency_is_bounded(con, dirs, monkeypatch):
    monkeypatch.setattr(classify, "CONCURRENCY", 2)
    con.executemany(
        "INSERT INTO posts VALUES (?, 1, 'a', TIMESTAMPTZ '2014-03-04 10:00:00Z', '', ?, true)",
        [(20 + i, f"Post number {i}") for i in range(4)],
    )
    fake = FakeJev()
    in_flight = peak = 0
    pair = asyncio.Barrier(2)
    handle = fake.handle

    async def gated(request: httpx2.Request) -> httpx2.Response:
        # Requests pass in pairs, so two must be in flight at once. Without the bound,
        # later requests arrive while the first of a pair is still waiting to resume.
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        # A broken pool would leave a request waiting for a partner forever; fail instead.
        async with asyncio.timeout(5):
            await pair.wait()
        in_flight -= 1
        return await handle(request)

    fake.handle = gated
    run(con, fake, dirs)
    assert fake.calls == 6
    assert peak == 2
