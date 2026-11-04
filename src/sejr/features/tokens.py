import re

# The header is the first line; posts with no line breaks put the whole body on it.
HEADER_CHARS = 200

# A clause ends at punctuation, list separators or "but", so a "no" earlier in the
# header ("NO REMOTE, VISA") does not negate a later token.
CLAUSE_END = re.compile(r"[.;:|!?\n,()\[\]]|\bbut\b", re.IGNORECASE)
NEGATION_BEFORE = re.compile(
    r"\b(?:no|not|non|cannot|unable|without|never|unfortunately)\b|n['’]t\b",
    re.IGNORECASE,
)
NEGATION_AFTER = re.compile(
    r"^\s*(?:[:\-–]\s*)?(?:no|none|n/a)\b|\b(?:not|unavailable|cannot|unable)\b|n['’]t\b",
    re.IGNORECASE,
)

REMOTE = re.compile(r"\bremote", re.IGNORECASE)
ONSITE = re.compile(r"\bon-?\s?site\b", re.IGNORECASE)
INTERNS = re.compile(r"\binterns?\b|\binternships?\b", re.IGNORECASE)

VISA = re.compile(
    r"\bvisas?\b|\bvisa['’]s\b|\bH-?1-?Bs?\b|\bgreen cards?\b", re.IGNORECASE
)
# "Visa" in title case is often the payments company ("clients include Google, Visa").
VISA_COMPANY = re.compile(r"^Visa(?:['’]s)?$")
VISA_OFFER_AFTER = re.compile(
    r"^\W{0,3}(?:sponsor|transfer|support|assist|welcome|ok|considered|possib|available|provid"
    r"|offer|relocation|for\b)",
    re.IGNORECASE,
)
# A bare "Visa" between pipes or at a line edge is the header token, not the company.
PIPE_BEFORE = re.compile(r"(?:^|\||\n)\s*$")
PIPE_AFTER = re.compile(r"^\s*(?:\||\n|$)")
# A visa the candidate must already hold is a requirement, not an offer.
VISA_HELD = re.compile(
    r"^\s*holders?\b|^\s*on your own\b|(?:valid|own|existing work|current)\s+(?:work\s+)?$",
    re.IGNORECASE,
)


def header_line(text: str) -> str:
    return text.lstrip().split("\n", 1)[0][:HEADER_CHARS]


def header_end(text: str) -> int:
    """Offset in `text` where the header line ends."""
    return len(text) - len(text.lstrip()) + len(header_line(text))


def _clause_before(text: str, start: int) -> str:
    before = text[max(0, start - 60) : start]
    ends = list(CLAUSE_END.finditer(before))
    return before[ends[-1].end() :] if ends else before


def _clause_after(text: str, end: int) -> str:
    after = text[end : end + 40]
    stop = CLAUSE_END.search(after)
    # "Remote: no" puts the answer after the colon, so keep one separator.
    if stop and stop.start() == 0 and stop.group() == ":":
        stop = CLAUSE_END.search(after, 1)
    return after[: stop.start()] if stop else after


def is_negated(text: str, start: int, end: int) -> bool:
    return bool(
        NEGATION_BEFORE.search(_clause_before(text, start))
        or NEGATION_AFTER.search(_clause_after(text, end))
    )


def _has_token(pattern: re.Pattern[str], text: str) -> bool:
    return any(not is_negated(text, m.start(), m.end()) for m in pattern.finditer(text))


def remote_token(text: str) -> bool:
    return _has_token(REMOTE, header_line(text))


def onsite_token(text: str) -> bool:
    return _has_token(ONSITE, header_line(text))


def interns_token(text: str) -> bool:
    # Anywhere in the post: the HN convention puts INTERNS in the header, but many posts
    # list internships further down.
    return _has_token(INTERNS, text)


def _is_visa_offer(text: str, m: re.Match[str]) -> bool:
    after = text[m.end() : m.end() + 30]
    if VISA_COMPANY.match(m.group()) and not (
        VISA_OFFER_AFTER.search(after)
        or m.end() <= header_end(text)
        or PIPE_BEFORE.search(text[: m.start()])
        or PIPE_AFTER.search(after)
    ):
        return False
    if VISA_HELD.search(after) or VISA_HELD.search(
        text[max(0, m.start() - 20) : m.start()]
    ):
        return False
    return not is_negated(text, m.start(), m.end())


def mentions_visa(text: str) -> bool:
    return any(_is_visa_offer(text, m) for m in VISA.finditer(text))
