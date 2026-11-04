import re

from sejr.features.tokens import header_line

SEPARATOR = re.compile(
    r"\||\s[-–—~]{1,2}\s|—|–|\(|\[|,|:|\.\s|\s(?:is|are)\s(?:hiring|looking)\b",
    re.IGNORECASE,
)
ROLE_AT_COMPANY = re.compile(r"\s(?:at|@)\s+(?P<company>.+)$", re.IGNORECASE)
LEADING_AT = re.compile(r"^(?:at|@)\s+", re.IGNORECASE)

# A first segment with these words is a job title, a location or a sentence, not a name.
NOT_A_NAME = re.compile(
    r"\b(?:engineers?|engineering|developers?|programmers?|scientists?|designers?|managers?"
    r"|architects?|interns?|internships?|devops|sre|cto|vp|director|lead|founding|co-?founder"
    r"|full[- ]?time|part[- ]?time|contract|remote|onsite|on-site|hybrid|hiring|looking|seeking"
    r"|position|positions|roles?|jobs?|location|we|we're|i|i'm|i’m|our|hi|hello|hey|https?|www"
    r"|san francisco|new york|nyc|london|berlin|seattle|boston|bay area|los angeles|chicago"
    r"|austin|toronto|anywhere|worldwide|usa|us only)\b",
    re.IGNORECASE,
)
LEGAL_SUFFIX = re.compile(
    r"\b(?:inc|incorporated|llc|l\.l\.c|ltd|limited|corp|corporation|co|gmbh|ag|sa|bv|b\.v"
    r"|plc|oy|ab|pty|srl|sas|lp|llp)\b\.?",
    re.IGNORECASE,
)
DOMAIN_SUFFIX = re.compile(
    r"\.(?:com|io|ai|dev|co|app|net|org|so|xyz|tech|us|uk|de|me)\b", re.IGNORECASE
)
# "Grand Rapids, MI - Hiring ..." opens with a location, not a company.
US_LOCATION_FIRST = re.compile(r"^[^,|()\-–—]+,\s*(?!AG|SA|BV|AB|OY)[A-Z]{2}\b")
MAX_WORDS = 5


def normalize_company(name: str) -> str | None:
    name = name.casefold().replace("&", " and ")
    name = DOMAIN_SUFFIX.sub("", name)
    name = LEGAL_SUFFIX.sub("", name)
    name = re.sub(r"[^\w\s]", "", name)
    name = re.sub(r"^the\s+", "", " ".join(name.split()))
    return name or None


def company_name(text: str) -> str | None:
    header = header_line(text)
    if US_LOCATION_FIRST.match(header):
        return None
    segment = SEPARATOR.split(header, maxsplit=1)[0].strip()
    segment = LEADING_AT.sub("", segment)
    if m := ROLE_AT_COMPANY.search(segment):
        segment = m.group("company")
    if not segment or len(segment.split()) > MAX_WORDS or NOT_A_NAME.search(segment):
        return None
    return normalize_company(segment)
