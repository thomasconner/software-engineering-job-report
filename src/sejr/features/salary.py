import re
from dataclasses import dataclass

from sejr.features.tokens import header_end

MIN_ANNUAL = 30_000
MAX_ANNUAL = 1_000_000

CURRENCIES = {
    "$": "USD", "US$": "USD", "USD": "USD",
    "€": "EUR", "EUR": "EUR",
    "£": "GBP", "GBP": "GBP",
    "CHF": "CHF",
    "C$": "CAD", "CA$": "CAD", "CAD": "CAD",
    "A$": "AUD", "AU$": "AUD", "AUD": "AUD",
    "S$": "SGD", "SGD": "SGD",
    "NZ$": "NZD", "NZD": "NZD",
    "₹": "INR", "INR": "INR",
    "¥": "JPY", "JPY": "JPY",
    "R$": "BRL", "BRL": "BRL",
    "HKD": "HKD", "SEK": "SEK", "NOK": "NOK", "DKK": "DKK", "PLN": "PLN", "ILS": "ILS",
    "MXN": "MXN",
}  # fmt: skip
PREFIX = "|".join(re.escape(c) for c in sorted(CURRENCIES, key=len, reverse=True))
SUFFIX = re.compile(
    r"^\s*(?:/\s*)?(" + "|".join(c for c in CURRENCIES if c.isalpha()) + r")\b"
)
NUM = r"\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?"

AMOUNT = re.compile(
    rf"""
    (?<![\w.,$€£¥₹])
    (?:(?P<cur1>{PREFIX})\s?)?
    (?P<lo>{NUM})\s?(?P<k1>[kK](?![a-zA-Z]))?
    (?:\s?(?:--?|–|—|to)\s?(?:(?P<cur2>{PREFIX})\s?)?(?P<hi>{NUM})\s?(?P<k2>[kK](?![a-zA-Z]))?)?
    (?P<plus>\+)?
    """,
    re.VERBOSE,
)

SENTENCE_BREAK = re.compile(r"[.;!?\n|]\s")
SALARY_BEFORE = re.compile(
    r"\b(?:salary|salaries|compensation|comp|pay|pays|paying|base|range|ote|earn|package)\b",
    re.IGNORECASE,
)
SALARY_AFTER = re.compile(
    r"^\s*(?:/\s*(?:yr|year|annum|y)\b|per (?:year|annum)\b|a year\b|annual|yearly|p\.?a\.?\b"
    r"|base\b|salary|ote\b|\+?\s*(?:and\s+)?(?:equity|bonus|stock|options|benefits))",
    re.IGNORECASE,
)
NOT_ANNUAL_AFTER = re.compile(
    r"^\s*(?:(?:/|per\b|an?\b|each\b)\s*(?:hour|hr|h|day|week|wk|month|mo)\b"
    r"|hourly|daily|weekly|monthly|%"
    r"|(?:m|mm|mn|b|bn|million|billion|trillion)\b"
    r"|(?:in\s+)?(?:funding|revenue|arr|mrr|raised|seed|series|valuation|users|customers|grants?"
    r"|signing|bonus|stipend|budget|relocation|learning|education))",
    re.IGNORECASE,
)
NOT_SALARY_BEFORE = re.compile(
    r"\b(?:raised?|raising|funding|funded|series [a-f]|seed|valuation|revenue|arr|mrr|fund"
    r"|grants?|budget|prize|bounty|invest\w*|backed|acquired|worth|assets|aum|stipend|bonus)\b",
    re.IGNORECASE,
)
UP_TO = re.compile(r"\bup to\s*~?\s*$", re.IGNORECASE)
# Stock grants quoted in dollars per year are not salary.
EQUITY_GRANT = re.compile(r"\b(?:rsus?|psus?|share units)\b", re.IGNORECASE)
AT_LEAST = re.compile(
    r"\b(?:from|starting(?: at)?|at least|min(?:imum)?\.?)\s*:?\s*$", re.IGNORECASE
)


@dataclass(frozen=True)
class Salary:
    low: float | None
    high: float | None
    currency: str  # ISO code, or 'unknown' when no currency is written


def _value(number: str, thousands: bool) -> float:
    value = float(number.replace(",", ""))
    return value * 1000 if thousands and value < 1000 else value


def _sane(*values: float | None) -> bool:
    return all(v is None or MIN_ANNUAL <= v <= MAX_ANNUAL for v in values)


def _clause_before(text: str, start: int) -> str:
    before = text[max(0, start - 60) : start]
    breaks = list(SENTENCE_BREAK.finditer(before))
    return before[breaks[-1].end() :] if breaks else before


def _salary(text: str, m: re.Match[str], header_stop: int) -> Salary | None:
    before = _clause_before(text, m.start())
    after = text[m.end() : m.end() + 30]
    suffix = SUFFIX.search(after)
    if suffix:
        after = after[suffix.end() :]
    if (
        NOT_ANNUAL_AFTER.search(after)
        or EQUITY_GRANT.search(after)
        or NOT_SALARY_BEFORE.search(before)
    ):
        return None

    symbol = suffix.group(1) if suffix else m["cur1"] or m["cur2"]
    currency = CURRENCIES.get(symbol) if symbol else None
    thousands = bool(m["k1"] or m["k2"])
    in_header = m.start() < header_stop
    has_context = in_header or bool(
        SALARY_BEFORE.search(before) or SALARY_AFTER.search(after)
    )

    low = _value(m["lo"], thousands)
    if m["hi"]:
        high = _value(m["hi"], thousands)
        # A bare "100k-120k" is only a salary when something nearby says so.
        if not currency and not (thousands and has_context):
            return None
    else:
        if not currency or not has_context:
            return None
        if UP_TO.search(before):
            low, high = None, low
        elif m["plus"] or AT_LEAST.search(before):
            high = None
        else:
            high = low

    if not _sane(low, high) or (low and high and low > high):
        return None
    return Salary(low, high, currency or "unknown")


def salaries(text: str) -> list[Salary]:
    header_stop = header_end(text)
    found = (_salary(text, m, header_stop) for m in AMOUNT.finditer(text))
    return [s for s in found if s]


def salary_summary(text: str) -> tuple[float | None, float | None, str]:
    """USD floor and ceiling across every range in the post, plus the currency label."""
    found = salaries(text)
    usd = [s for s in found if s.currency == "USD"]
    if not usd:
        known = [s.currency for s in found if s.currency != "unknown"]
        return None, None, known[0] if known else ("unknown" if found else "none")
    lows = [s.low for s in usd if s.low is not None]
    highs = [s.high for s in usd if s.high is not None]
    return min(lows, default=None), max(highs, default=None), "USD"
