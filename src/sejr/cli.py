import argparse
import importlib

from sejr.db import connect

# Each step lives in sejr.<module> and exposes run(con, args).
STEPS = [
    "fetch",
    "normalize",
    "features",
    "classify",
    "aggregate",
    "external",
    "export",
    "validate",
    "unanswered",
]


def main() -> None:
    parser = argparse.ArgumentParser(prog="sejr")
    sub = parser.add_subparsers(dest="command", required=True)
    for step in STEPS:
        p = sub.add_parser(step)
        p.add_argument("--month", help="YYYY-MM; limit the step to one month")
        p.add_argument("--limit", type=int, help="process at most N items")
        p.add_argument("--dry-run", action="store_true")
        p.add_argument(
            "--backfill", action="store_true", help="allow a full-history run"
        )
    args = parser.parse_args()

    module = importlib.import_module(f"sejr.{args.command}")
    with connect() as con:
        module.run(con, args)
