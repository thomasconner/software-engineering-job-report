import asyncio
import json
from argparse import Namespace
from pathlib import Path

import httpx2
import pytest
from typesafe_sdk import AsyncTypeSafeClient

from sejr import classify
from sejr.classify import jev
from sejr.classify.questions import QUESTIONS
from sejr.config import JEV_MODEL
from sejr.db import connect

HIRING_TEXT = "Acme Robotics | Senior Backend Engineer | Boston, ONSITE | Series A\n\nWe build warehouse robots."
SEEKING_TEXT = "Location: Lisbon\nRemote: Yes\nTechnologies: Go, Postgres"


class FakeJev:
    """A fake TypeSafe API behind the real SDK client, so tests exercise the SDK too."""

    def __init__(self, model: str = JEV_MODEL, rate_limit_first: int = 0) -> None:
        self.model = model
        self.rate_limit_first = rate_limit_first
        self.bodies: list[dict] = []
        self.calls = 0

    def answer(self, question: dict) -> dict:
        match question["type"]:
            case "choice":
                options = list(question["criteria"])
                probabilities = {o: 0.0 for o in options}
                probabilities[options[0]] = 0.7
                probabilities[options[1]] = 0.3
                return {
                    "type": "choice",
                    "choice": options[0],
                    "confidence": 0.6,
                    "probabilities": probabilities,
                }
            case "score":
                levels = range(len(question["criteria"]))
                return {
                    "type": "score",
                    "score": 2.5,
                    "confidence": 0.4,
                    "legend": {str(i): question["criteria"][i] for i in levels},
                    "probabilities": {
                        str(i): 0.5 if i in (2, 3) else 0.0 for i in levels
                    },
                }
            case "noul":
                return {"type": "noul", "noul": 0.8}

    async def handle(self, request: httpx2.Request) -> httpx2.Response:
        self.calls += 1
        if self.calls <= self.rate_limit_first:
            # retry-after-ms 0 makes the SDK retry at once, so the test never waits.
            return httpx2.Response(
                429, headers={"retry-after-ms": "0"}, json={"error": "slow down"}
            )
        body = json.loads(request.content)
        self.bodies.append(body)
        answers = {name: self.answer(q) for name, q in body["questions"].items()}
        return httpx2.Response(
            200,
            json={
                "model": self.model,
                "answers": answers,
                "usage": {"input_tokens": 100, "output_tokens": 5},
            },
        )

    def client(self) -> AsyncTypeSafeClient:
        return AsyncTypeSafeClient(
            api_key="test",
            model=JEV_MODEL,
            compression=False,
            transport=httpx2.MockTransport(self.handle),
        )


@pytest.fixture
def con(tmp_path: Path):
    con = connect(tmp_path / "test.duckdb")
    con.execute(
        """INSERT INTO threads VALUES
        (1, 'hiring', DATE '2014-03-01', 'Ask HN: Who is hiring? (March 2014)', TIMESTAMPTZ '2014-03-03 15:00:00Z', TIMESTAMPTZ '2014-03-10 15:00:00Z'),
        (2, 'seeking', DATE '2014-03-01', 'Ask HN: Who wants to be hired? (March 2014)', TIMESTAMPTZ '2014-03-03 15:00:00Z', TIMESTAMPTZ '2014-03-10 15:00:00Z')"""
    )
    con.executemany(
        "INSERT INTO posts VALUES (?, ?, 'a', TIMESTAMPTZ '2014-03-04 10:00:00Z', '', ?, ?)",
        [
            (10, 1, HIRING_TEXT, True),
            (11, 2, SEEKING_TEXT, True),
            (12, 1, "Late post", False),
        ],
    )
    yield con
    con.close()


def run(con, fake: FakeJev, cache_dir: Path, **kwargs) -> None:
    args = Namespace(
        month=kwargs.get("month"),
        limit=kwargs.get("limit"),
        dry_run=kwargs.get("dry_run", False),
    )
    classify.run(con, args, client=fake.client(), cache_dir=cache_dir)


def answers(con) -> dict[tuple[int, str], tuple]:
    rows = con.execute(
        "SELECT post_id, question, method, version, value, label, probabilities, confidence FROM answers"
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
    assert jev.cache_path(tmp_path, request) == jev.cache_path(
        tmp_path, jev.build_request("hiring", HIRING_TEXT)
    )


def test_only_in_snapshot_posts_and_no_dates_in_request(con, tmp_path: Path):
    fake = FakeJev()
    run(con, fake, tmp_path)
    assert sorted(b["state"] for b in fake.bodies) == sorted(
        [HIRING_TEXT, SEEKING_TEXT]
    )
    for body in fake.bodies:
        assert set(body) == {"model", "state", "questions"}
        sent = json.dumps(body)
        for leak in ("2014", "March", "03-0", "Mar "):
            assert leak not in sent


def test_second_run_makes_zero_calls(con, tmp_path: Path):
    first = FakeJev()
    run(con, first, tmp_path)
    assert first.calls == 2
    before = answers(con)
    cached = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert set(cached) == {"request", "response"}

    second = FakeJev()
    run(con, second, tmp_path)
    assert second.calls == 0
    assert answers(con) == before


def test_answer_rows_for_each_primitive(con, tmp_path: Path):
    run(con, FakeJev(), tmp_path)
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

    # The companion Noul folds into industry as the `other` category.
    _, _, _, label, probabilities, _ = rows[(10, "industry")]
    industry = json.loads(probabilities)
    assert industry["other"] == pytest.approx(0.2)
    assert industry["ai_ml"] == pytest.approx(0.56)
    assert sum(industry.values()) == pytest.approx(1.0)
    assert label == "ai_ml"
    assert rows[(10, "industry_fits")][2] == 0.8

    assert {q for p, q in rows if p == 10} == set(QUESTIONS["hiring"])


def test_version_mismatch_fails_loudly_and_caches_nothing(con, tmp_path: Path):
    with pytest.raises(ExceptionGroup) as raised:
        run(con, FakeJev(model="jev-9.9.9"), tmp_path)
    assert raised.group_contains(jev.JevVersionMismatch)
    assert list(tmp_path.glob("*.json")) == []
    assert answers(con) == {}


def test_rate_limit_is_retried(con, tmp_path: Path):
    fake = FakeJev(rate_limit_first=1)
    run(con, fake, tmp_path, limit=1)
    assert fake.calls == 2
    assert (10, "work_mode") in answers(con)


def test_month_and_limit_filters(con, tmp_path: Path):
    fake = FakeJev()
    run(con, fake, tmp_path, month="2014-04")
    assert fake.calls == 0
    run(con, fake, tmp_path, limit=1)
    assert fake.calls == 1


def test_dry_run_estimates_without_calling(con, tmp_path: Path, capsys):
    fake = FakeJev()
    run(con, fake, tmp_path, dry_run=True)
    assert fake.calls == 0
    out = capsys.readouterr().out
    tokens = sum(
        jev.estimate_tokens(jev.build_request(k, t))
        for k, t in [("hiring", HIRING_TEXT), ("seeking", SEEKING_TEXT)]
    )
    assert "requests: 2 (0 cached, 2 to send)" in out
    assert f"estimated input tokens: {tokens:,}" in out
    assert f"${tokens / 1e6 * 0.042:.4f}" in out


def test_concurrency_is_bounded(con, tmp_path: Path, monkeypatch):
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
        await pair.wait()
        in_flight -= 1
        return await handle(request)

    fake.handle = gated
    run(con, fake, tmp_path)
    assert fake.calls == 6
    assert peak == 2
