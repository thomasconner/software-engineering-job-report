"""Print complete months that have posts without current Jev answers, one per line."""

from sejr.classify import unanswered_months
from sejr.config import ANSWERS_DIR


def run(con, args) -> None:
    for month in unanswered_months(con, ANSWERS_DIR):
        print(month)
