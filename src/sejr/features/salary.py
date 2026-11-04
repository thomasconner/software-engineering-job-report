import re
from dataclasses import dataclass
from statistics import median

from sejr.features.places import dollar_currency
from sejr.features.tokens import header_end, header_line

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
CODES = "|".join(c for c in CURRENCIES if c.isalpha())
SUFFIX = re.compile(rf"^\s*(?:/\s*)?({CODES})\b")
# "$120k (USD)" or "$120k base, CAD": a code shortly after a bare "$" settles it.
CODE_AFTER = re.compile(rf"\b({CODES})\b")
THOUSANDS = r"[kK](?=[A-Z]{3}\b|[^a-zA-Z]|$)"  # also "140kUSD"
NUM = r"\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?"

AMOUNT = re.compile(
    rf"""
    (?<![\w.,$€£¥₹])
    (?:(?P<cur1>{PREFIX})\s?)?
    (?P<lo>{NUM})\s?(?P<k1>{THOUSANDS})?
    (?:\s?(?:--?|–|—|to)\s?(?:(?P<cur2>{PREFIX})\s?)?(?P<hi>{NUM})\s?(?P<k2>{THOUSANDS})?)?
    (?P<plus>\+(?![a-zA-Z]))?  # "$150k+bonus" is not "$150k or more"
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
    r"|(?:in\s+)?(?:funding|revenue|arr|mrr|raised|seed|series|valuation|users|customers"
    r"|grants?))",
    re.IGNORECASE,
)
# Amounts that are perks or stock grants rather than pay ("$10k signing bonus", "$50k RSUs").
PERK_AFTER = re.compile(
    r"^\s*(?:in\s+)?(?:signing|bonus|stipend|budget|relocation|learning|education)"
    r"|\b(?:rsus?|psus?|share units)\b",
    re.IGNORECASE,
)
NOT_SALARY_BEFORE = re.compile(
    r"\b(?:raised?|raising|funding|funded|series [a-f]|seed|valuation|revenue|arr|mrr|fund"
    r"|grants?|budget|prize|bounty|invest\w*|backed|acquired|worth|assets|aum|stipend|bonus"
    r"|houses?|homes?|rent|apartments?|prices?|costs?)\b",
    re.IGNORECASE,
)
UP_TO = re.compile(r"\bup to\s*~?\s*$", re.IGNORECASE)
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


def _sentence_before(text: str, start: int) -> str:
    before = text[max(0, start - 60) : start]
    breaks = list(SENTENCE_BREAK.finditer(before))
    return before[breaks[-1].end() :] if breaks else before


def _currency(m: re.Match[str], suffix: re.Match[str] | None, after: str, header: str):
    if suffix:
        return CURRENCIES[suffix.group(1)]
    symbol = m["cur1"] or m["cur2"]
    if symbol != "$":
        return CURRENCIES.get(symbol) if symbol else None
    if code := CODE_AFTER.search(after):
        return CURRENCIES[code.group(1)]
    # A bare "$" in a header that names only non-US places may not be US dollars.
    return dollar_currency(header) or "USD"


def _salary(
    text: str, m: re.Match[str], header: str, header_stop: int
) -> Salary | None:
    before = _sentence_before(text, m.start())
    after = text[m.end() : m.end() + 30]
    suffix = SUFFIX.search(after)
    rest = after[suffix.end() :] if suffix else after
    salary_word = bool(SALARY_BEFORE.search(before))
    if NOT_ANNUAL_AFTER.search(rest) or NOT_SALARY_BEFORE.search(before):
        return None
    # A range right after "Salary:" stays a salary even if stock is mentioned next to it.
    if PERK_AFTER.search(rest) and not (m["hi"] and salary_word):
        return None

    currency = _currency(m, suffix, after, header)
    thousands = bool(m["k1"] or m["k2"])
    in_header = m.start() < header_stop
    has_context = in_header or salary_word or bool(SALARY_AFTER.search(rest))

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
    header, header_stop = header_line(text), header_end(text)
    found = (_salary(text, m, header, header_stop) for m in AMOUNT.finditer(text))
    return [s for s in found if s]


def salary_summary(text: str) -> tuple[float | None, float | None, str]:
    """Median USD low and median USD high across the post's ranges, plus the currency label.

    Medians, not the extreme floor and ceiling, so a post listing an intern and a staff
    role doesn't report one absurdly wide range.
    """
    found = salaries(text)
    usd = [s for s in found if s.currency == "USD"]
    if not usd:
        known = [s.currency for s in found if s.currency != "unknown"]
        return None, None, known[0] if known else ("unknown" if found else "none")
    lows = [s.low for s in usd if s.low is not None]
    highs = [s.high for s in usd if s.high is not None]
    return (median(lows) if lows else None), (median(highs) if highs else None), "USD"
