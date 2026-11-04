"""The committed site data agrees with the split export contract (docs/architecture.md)."""

import json
from pathlib import Path

DATA = Path(__file__).parent.parent / "site" / "data"


def test_every_breakdown_file_exists_and_matches_the_core():
    core = json.loads((DATA / "metrics.json").read_text())
    for name, breakdown in core["breakdowns"].items():
        assert "series" not in breakdown, name
        assert breakdown["file"] == f"breakdowns/{name}.json"
        part = json.loads((DATA / breakdown["file"]).read_text())
        assert part["id"] == name
        assert set(part) == {"id", "series"}
    files = {p.stem for p in (DATA / "breakdowns").glob("*.json")}
    assert files == set(core["breakdowns"])
