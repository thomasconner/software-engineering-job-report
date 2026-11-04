"""Traits of the post itself: how the company interviews and how many days it wants in the office."""

import re

from sejr.features.tokens import is_negated

INTERVIEW_CONTEXT = re.compile(
    r"\b(?:interview\w*|hiring\s+process|our\s+process|recruiting\s+process|application\s+process"
    r"|rounds?|stages?|steps?|screen\w*)\b",
    re.IGNORECASE,
)
CONTEXT_CHARS = 100
# style → (pattern, needs interview words nearby)
STYLES: dict[str, tuple[re.Pattern[str], bool]] = {
    "take_home": (
        re.compile(
            r"\btake[- ]?homes?\b(?!\s+(?:pay|salary|comp\w*))|\bhome\s*(?:work\s+)?assignments?\b"
            r"|\bhomework\s+(?:assignments?|exercises?|projects?|tasks?)\b",
            re.IGNORECASE,
        ),
        False,
    ),
    # Counted only when the post says it doesn't do them: "no LeetCode", "we don't whiteboard".
    "no_leetcode": (
        re.compile(
            r"\bleet\s?code\w*|\bwhite\s?board(?:ing)?\b|\bbrain\s?teasers?\b"
            r"|\b(?:algorithm\w*|algo|coding|trick)\s+(?:puzzles?|quizzes|questions|trivia|gotchas?|riddles?)\b",
            re.IGNORECASE,
        ),
        False,
    ),
    "pair_programming": (
        re.compile(
            r"\bpair(?:ed)?[- ]?(?:programming|program|coding|code)\b|\bpairing\s+(?:sessions?"
            r"|exercises?|interviews?|on\s+a\s+(?:real|problem))\b",
            re.IGNORECASE,
        ),
        True,
    ),
    "paid_trial": (
        re.compile(
            r"\bpaid\s+(?:work\s+|test\s+)?(?:trials?|take[- ]?homes?|work\s+samples?"
            r"|(?:trial|sample|test)\s+(?:projects?|periods?|weeks?|days?|tasks?))\b"
            r"|\b(?:trial|sample|test)\s+(?:project|period|week|day|task)s?\s*(?:\(\s*(?:fully\s+)?paid"
            r"|(?:is|are|will\s+be)\s+(?:fully\s+)?(?:paid|compensated))"
            r"|\bpay\s+(?:you\s+)?(?:\$\d[\d,]*\w*\s+)?for\s+(?:your\s+|the\s+)?(?:time|take[- ]?homes?"
            r"|projects?|assignments?|trials?|exercises?)"
            r"|\bpaid\s+for\s+(?:any\s+|the\s+|your\s+)?(?:take[- ]?homes?|trials?|projects?|assignments?"
            r"|exercises?|tests?)",
            re.IGNORECASE,
        ),
        False,
    ),
}
STYLE_NAMES = tuple(STYLES)
# "Leetcode" in a post that says nothing against it is the interview, not its absence.
LEETCODE_NEGATION = re.compile(
    r"\b(?:no|not|never(?!-)|without|zero|skip|avoid|hate|free\s+of|instead\s+of|rather\s+than|nor)\b"
    r"|n['’]t\b|-free\b",
    re.IGNORECASE,
)


def _no_leetcode(text: str, m: re.Match[str]) -> bool:
    before = text[max(0, m.start() - 40) : m.start()]
    after = text[m.end() : m.end() + 12]
    return bool(
        LEETCODE_NEGATION.search(re.split(r"[.!?\n]", before)[-1])
        or re.match(r"-free\b", after)
    )


def interview_styles(text: str) -> list[str]:
    found = []
    for name, (pattern, needs_context) in STYLES.items():
        for m in pattern.finditer(text):
            if needs_context and not INTERVIEW_CONTEXT.search(
                text[max(0, m.start() - CONTEXT_CHARS) : m.end() + CONTEXT_CHARS]
            ):
                continue
            if name == "no_leetcode":
                ok = _no_leetcode(text, m)
            else:
                ok = not is_negated(text, m.start(), m.end())
            if ok:
                found.append(name)
                break
    return found


DAY_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
DAY_NUMBER = r"(?P<n>[1-5]|one|two|three|four|five)"
OFFICE = r"(?:office|onsite|on-site|on\s+site|in[- ]person|hq|in\s+the\s+office|at\s+the\s+office|in-office|co-?located|studio|lab)"
# "3 days a week in the office", "hybrid (2 days/wk)", "in office 3x/week", "4 days onsite".
# "In-office 3-4 days", "hybrid: 2 days".
OFFICE_FIRST = re.compile(
    r"(?:"
    + OFFICE
    + r"|hybrid)\W{0,3}"
    + DAY_NUMBER
    + r"(?:\s*(?:-|–|to|or)\s*[1-5])?\s*\+?\s*(?:days?|d)\b",
    re.IGNORECASE,
)
OFFICE_DAYS = re.compile(
    r"\b" + DAY_NUMBER + r"(?:\s*(?:-|–|to|or)\s*[1-5])?\s*\+?\s*(?:x|days?|d)\s*"
    r"(?:(?:a|per|/|each|every|in\s+a)\s*(?:week|wk)\b|(?=\s*(?:in|at|on|onsite|on-site|in-office)\b))",
    re.IGNORECASE,
)
NEAR_OFFICE = re.compile(r"\b" + OFFICE + r"\b|\bhybrid\b|\bcommute\b", re.IGNORECASE)
# Days at home, a four-day week, on-call or a support rota are not office days.
NOT_OFFICE = re.compile(
    r"^\W{0,3}(?:(?:a|per|/)\s*(?:week|wk)\s*)?(?:\W{0,3})?(?:remote(?:ly)?|from\s+home|wfh|at\s+home"
    r"|work\s*week|workweek|off\b|on[- ]call|support)",
    re.IGNORECASE,
)
HOME_BEFORE = re.compile(
    r"\b(?:wfh|work\s+from\s+home|from\s+home|remote(?:ly)?)\W*$", re.IGNORECASE
)
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri")
DAY_RANGE = re.compile(
    r"\b(mon|tue|wed|thu|fri)\w*\s*(?:-|–|to|through|thru)\s*(mon|tue|wed|thu|fri)\w*",
    re.IGNORECASE,
)


def office_days(text: str) -> int | None:
    """The fewest in-office days a week the post states, if it states any."""
    found = []
    for m in OFFICE_DAYS.finditer(text):
        window = text[max(0, m.start() - 60) : m.end() + 60]
        if (
            not NEAR_OFFICE.search(window)
            or NOT_OFFICE.search(text[m.end() : m.end() + 30])
            or HOME_BEFORE.search(text[max(0, m.start() - 20) : m.start()])
        ):
            continue
        n = m["n"].lower()
        found.append(int(n) if n.isdigit() else DAY_WORDS[n])
    for m in OFFICE_FIRST.finditer(text):
        n = m["n"].lower()
        found.append(int(n) if n.isdigit() else DAY_WORDS[n])
    for m in DAY_RANGE.finditer(text):
        window = text[max(0, m.start() - 40) : m.end() + 40]
        if not re.search(r"\b" + OFFICE + r"\b", window, re.IGNORECASE):
            continue
        first, last = (WEEKDAYS.index(d.lower()[:3]) for d in m.groups())
        if last > first:
            found.append(last - first + 1)
    return min(found) if found else None
