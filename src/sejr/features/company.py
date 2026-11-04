import re

from sejr.features.places import LOCATION_FIRST, PLACE_ONLY
from sejr.features.tokens import header_line

SEPARATOR = re.compile(
    r"\||\s[-–—~]{1,2}\s|—|–|\(|\[|,|:|\.\s|\s(?:is|are)\s(?:hiring|looking)\b",
    re.IGNORECASE,
)
ROLE_AT_COMPANY = re.compile(r"\s(?:at|@)\s+(?P<company>.+)$", re.IGNORECASE)
LEADING_AT = re.compile(r"^(?:at|@)\s+", re.IGNORECASE)

# A first segment with these words is a job title or a sentence, not a name. Places are
# rejected only as the whole segment (PLACE_ONLY), so "Boston Dynamics" survives.
NOT_A_NAME = re.compile(
    r"\b(?:engineers?|engineering|developers?|programmers?|scientists?|designers?|managers?"
    r"|architects?|interns?|internships?|devops|sre|cto|ceo|cfo|coo|vp|director|head of|chief"
    r"|lead|senior|sr|junior|jr|staff|principal|founding|co-?founder|recruiters?|recruiting"
    r"|analysts?|consultants?|specialists?|administrators?|freelance|freelancers?"
    r"|full[- ]?time|part[- ]?time|contract|remote|onsite|on-site|hybrid|hiring|looking|seeking"
    r"|position|positions|roles?|jobs?|location|we|we're|i|i'm|i’m|our|hi|hello|hey|https?|www"
    r"|anywhere|worldwide|us only)\b",
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
    # 2011-era headers often open with a place ("Palo Alto, CA - Box.net"); the name, if
    # any, follows it after a separator.
    if location := LOCATION_FIRST.match(header):
        if not location["sep"]:
            return None
        header = header[location.end() :].strip()
    segment = SEPARATOR.split(header, maxsplit=1)[0].strip()
    segment = LEADING_AT.sub("", segment)
    if m := ROLE_AT_COMPANY.search(segment):
        segment = m.group("company")
    if (
        not re.search(r"[^\W\d_]", segment)
        or len(segment.split()) > MAX_WORDS
        or NOT_A_NAME.search(segment)
        or PLACE_ONLY.match(segment)
    ):
        return None
    return normalize_company(segment)
