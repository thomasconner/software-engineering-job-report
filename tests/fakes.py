"""A fake TypeSafe API and a small database shared by the classify and validate tests."""

import json
from pathlib import Path

import httpx2
from typesafe_sdk import AsyncTypeSafeClient

from sejr.config import JEV_MODEL
from sejr.db import connect

HIRING_TEXT = (
    "Acme Robotics | Senior Backend Engineer | Boston, ONSITE | Series A\n\n"
    "We build warehouse robots."
)
SEEKING_TEXT = "Location: Lisbon\nRemote: Yes\nTechnologies: Go, Postgres"
APRIL_TEXT = "Beta Corp | Engineer | REMOTE"


class FakeJev:
    """A fake TypeSafe API behind the real SDK client, so tests exercise the SDK too."""

    def __init__(
        self,
        model: str = JEV_MODEL,
        rate_limit_first: int = 0,
        nouls: dict[str, float] | None = None,
        reject: str | None = None,
        drop: str | None = None,
        usage: dict | None = None,
    ) -> None:
        self.model = model
        self.rate_limit_first = rate_limit_first
        self.nouls = nouls or {}
        self.reject = reject  # a state containing this gets a 400
        self.drop = drop  # an answer id left out of every response
        self.usage = (
            {"input_tokens": 100, "output_tokens": 5} if usage is None else usage
        )
        self.bodies: list[dict] = []
        self.calls = 0

    def answer(self, name: str, question: dict) -> dict:
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
                return {"type": "noul", "noul": self.nouls.get(name, 0.8)}

    async def handle(self, request: httpx2.Request) -> httpx2.Response:
        self.calls += 1
        if self.calls <= self.rate_limit_first:
            # retry-after-ms 0 makes the SDK retry at once, so the test never waits.
            return httpx2.Response(
                429, headers={"retry-after-ms": "0"}, json={"error": "slow down"}
            )
        body = json.loads(request.content)
        if self.reject and self.reject in body["state"]:
            return httpx2.Response(400, json={"error": "bad post"})
        self.bodies.append(body)
        answers = {
            name: self.answer(name, q)
            for name, q in body["questions"].items()
            if name != self.drop
        }
        return httpx2.Response(
            200, json={"model": self.model, "answers": answers, "usage": self.usage}
        )

    def client(self) -> AsyncTypeSafeClient:
        return AsyncTypeSafeClient(
            api_key="test",
            model=JEV_MODEL,
            compression=False,
            transport=httpx2.MockTransport(self.handle),
        )


def make_db(path: Path):
    con = connect(path)
    con.execute(
        """INSERT INTO threads (thread_id, kind, month, title, created_at, snapshot_at,
            fetched_at) VALUES
        (1, 'hiring', DATE '2014-03-01', 'Ask HN: Who is hiring? (March 2014)',
         TIMESTAMPTZ '2014-03-03 15:00:00Z', TIMESTAMPTZ '2014-03-10 15:00:00Z', now()),
        (2, 'seeking', DATE '2014-03-01', 'Ask HN: Who wants to be hired? (March 2014)',
         TIMESTAMPTZ '2014-03-03 15:00:00Z', TIMESTAMPTZ '2014-03-10 15:00:00Z', now()),
        (3, 'hiring', DATE '2014-04-01', 'Ask HN: Who is hiring? (April 2014)',
         TIMESTAMPTZ '2014-04-01 15:00:00Z', TIMESTAMPTZ '2014-04-08 15:00:00Z', now())"""
    )
    con.executemany(
        "INSERT INTO posts VALUES (?, ?, 'a', TIMESTAMPTZ '2014-03-04 10:00:00Z', '', ?, ?)",
        [
            (10, 1, HIRING_TEXT, True),
            (11, 2, SEEKING_TEXT, True),
            (12, 1, "Late post", False),
            (30, 3, APRIL_TEXT, True),
        ],
    )
    return con
