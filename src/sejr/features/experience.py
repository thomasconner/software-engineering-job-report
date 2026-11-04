"""Experience and education a hiring post asks for: years required and degrees."""

import re

WORD_NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "twelve": 12, "fifteen": 15, "twenty": 20,
}  # fmt: skip
NUMBER = r"(?:\d{1,2}|" + "|".join(WORD_NUMBERS) + r")"
# "5+ years", "3-5 years", "3 to 5 yrs", "5+ YOE"; the low end is the requirement.
YEARS = re.compile(
    r"(?<![\w.$€£])(?<!\d[-–])(?P<low>"
    + NUMBER
    + r")\s*\+?\s*(?:(?:-|–|to)\s*(?P<high>"
    + NUMBER
    + r")\s*\+?\s*)?(?:years?|yrs?|y/o/e|yoe)\b(?:'|’)?",
    re.IGNORECASE,
)
# A bare "N years" needs the words after it to be about the candidate's work; "5+ years",
# "3-5 years" and "N years of/in/with X" read as a requirement on their own.
REQUIREMENT_SHAPE = re.compile(
    r"^(?:'|’)?\s*(?:of|in|with|as|doing|working|building|writing|developing|programming"
    r"|shipping|leading|managing|professional|industry|hands[- ]on|exp\b|xp\b)\s",
    re.IGNORECASE,
)
EXPERIENCE_AFTER = re.compile(
    r"^(?:\s*\+)?\s*(?:[\w#+./-]+[\s,/]+){0,4}?(?:experience|exp\b|xp\b|professional|industry|hands[- ]on"
    r"|track record|work(?:ing)?\b|building|writing|developing|shipping|programming|coding"
    r"|engineering|development|leading|managing|production|commercial|post[- ]?grad\w*|relevant"
    r"|software|in\s+(?:a|the)\s+(?:role|field|industry))",
    re.IGNORECASE,
)
YOE_ONLY = re.compile(r"y/o/e|yoe", re.IGNORECASE)
# "Experience: 5+ years", "Requirements - 3 years minimum".
EXPERIENCE_BEFORE = re.compile(
    r"(?:experience|exp|yoe|requirements?|required|minimum|at least|min\.?)\W{0,4}"
    r"(?:of\s+|with\s+)?(?:at\s+least\s+|minimum\s+(?:of\s+)?)?$",
    re.IGNORECASE,
)
# Company age, runway, the poster's own career and the team's combined years.
NOT_REQUIRED_BEFORE = re.compile(
    r"(?:founded|since|past|last|next|within|over\s+the|in\s+the|runway|ago|old|for\s+over"
    r"|been\s+(?:around|in\s+business|profitable|operating|doing\s+this)|profitable\s+for"
    r"|i\s+have|i've|i’ve|i\s+had|we\s+have|we've|we’ve|our\s+team|team\s+has|founders?|ceo|cto"
    r"|combined|collective|cumulative|over\s+the\s+course|up\s+to|less\s+than|under|fewer\s+than"
    r"|no\s+more\s+than|max(?:imum)?|<=?|≤|first|every|each|after|about\s+to|the\s+last"
    r"|in|spent|having\s+spent|backed\s+by)"
    r"(?:\s+(?:for|over|about|nearly|almost|just|only|around|more\s+than|than))*\W{0,3}$",
    re.IGNORECASE,
)
NOT_REQUIRED_AFTER = re.compile(
    r"^\s*(?:old|ago|of\s+(?:runway|funding|history|data|growth|operation|profitab\w*|revenue"
    r"|combined|collective|cumulative|sustained)|runway|in\s+business|later|from\s+now|combined"
    r"|collective|cumulative|of\s+(?:the\s+)?(?:company|business)|degree|college|university"
    r"|program|contract|term|plan|warranty|vesting|cliff|olds?|-old)\b",
    re.IGNORECASE,
)
# The team's or the founders' years, said earlier in the same sentence.
NOT_REQUIRED_CLAUSE = re.compile(
    r"\b(?:(?:our|current|the)\s+team\s+(?:is|are|has|have)|team\s+of\b|founders?\s+(?:have|has|with|are)"
    r"|(?:we|i)\s+(?:have|bring)\s+(?:a\s+)?(?:combined|collective|over)|i'?ve\s+been|we'?ve\s+been"
    r"|(?:most|many|all|some|several)\s+of\s+us)",
    re.IGNORECASE,
)
BUCKETS = (("0_2", 0, 2), ("3_4", 3, 4), ("5_7", 5, 7), ("8_plus", 8, 99))
MAX_YEARS = 25


def _number(word: str) -> int:
    return int(word) if word.isdigit() else WORD_NUMBERS[word.lower()]


def years_required(text: str) -> int | None:
    """The smallest number of years of experience the post asks for, across its roles."""
    found = []
    for m in YEARS.finditer(text):
        before = text[max(0, m.start() - 40) : m.start()]
        after = text[m.end() : m.end() + 90]
        clause = re.split(r"[.;!?\n]", text[max(0, m.start() - 100) : m.start()])[-1]
        if (
            NOT_REQUIRED_BEFORE.search(before)
            or NOT_REQUIRED_AFTER.search(after)
            or NOT_REQUIRED_CLAUSE.search(clause)
        ):
            continue
        if not (
            YOE_ONLY.search(m.group())
            or m["high"]
            or "+" in m.group()
            or REQUIREMENT_SHAPE.search(after)
            or EXPERIENCE_AFTER.search(after)
            or EXPERIENCE_BEFORE.search(before)
        ):
            continue
        low = _number(m["low"])
        if low <= MAX_YEARS:
            found.append(low)
    return min(found) if found else None


def years_bucket(years: int) -> str:
    return next(name for name, low, high in BUCKETS if low <= years <= high)


# Degrees. "BS" alone is too often "no BS", and "MS" is Microsoft, so the short forms need
# a field or the word degree after them.
FIELD = r"(?:in\b|degree|\(|CS\b|C\.S\.|EE\b|Computer|Math|Engineering|Physics|Stat|Electrical|Mechanical|Science|related|technical|or\s+(?:higher|above|equivalent|MS|PhD|BS|M\.S\.|B\.S\.))"
DEGREE = re.compile(
    # Case-sensitive, so "Bain" or "ms" never reads as a degree.
    r"\b(?-i:B\.?S\.?c?|B\.?A\.?|M\.?S\.?c?|B\.?Eng|M\.?Eng|B\.?Tech|M\.?Tech)\b\.?\s*"
    r"(?:/\s*(?:MS|BS|M\.S\.|PhD|Ph\.D\.?)\s*)?"
    r"(?:,\s*)?"
    + FIELD
    + r"|\b(?:Bachelor|Master)(?:'?s|’s|s)?\b(?:\s+(?:of|degree|in|or)\b|\s*/|\s*\()"
    r"|\b(?:BSCS|MSCS|BSEE)\b"
    r"|\bPh\.?\s?D\.?\s+(?:in|or|preferred|required|is|are|a\s+plus|degree|level|holders?|candidates?)\b"
    r"|\b(?:MS|M\.S\.|Master'?s|Masters)\s*(?:/|or)\s*Ph\.?\s?D\b"
    r"|\b(?:have|hold|with)\s+a\s+Ph\.?\s?D\b"
    r"|\b(?:college|university|undergrad(?:uate)?|graduate|4[- ]year|four[- ]year|CS|computer\s+science"
    r"|engineering|technical|STEM|advanced|bachelor'?s|master'?s|relevant|related)\s+degrees?\b"
    r"|\bdegree\s+in\b",
    re.IGNORECASE,
)
# A degree the team holds or a student is working toward is not one the job asks for.
NOT_ASKED_BEFORE = re.compile(
    r"\b(?:co-?founders?|founders?|ceo|cto|team\s+of|our\s+team|led\s+by|founded\s+by|started\s+by"
    r"|working\s+towards?|pursuing|completing|enrolled|students?|toward|earning|people\s+with"
    r"|back\s+to\s+school|school\s+for|staff|team\s+includes|(?:most|many|several|all)\s+with"
    r"|sponsor\w*|perks?|tuition|pay\s+for|offers?|without"
    r"|folks\s+with|colleagues|I\s+(?:have|hold|got|earned)|(?:he|she)\s+(?:has|holds))\b[^.\n]{0,40}$",
    re.IGNORECASE,
)
# A degree the company sells, teaches or pays for.
NOT_ASKED_AFTER = re.compile(
    r"^\W{0,3}(?:programs?|courses?|completely|online|students?|candidates?\s+(?:are|will))\b",
    re.IGNORECASE,
)
# "to an advanced degree", "to a degree".
IDIOM_BEFORE = re.compile(
    r"\bto\s+(?:an?|some|the|a\s+certain|what)\s*$", re.IGNORECASE
)
DEGREE_OPTIONAL = re.compile(
    r"\bor\s+(?:\w+\s+){0,2}(?:equivalent|comparable|related|relevant)\s*(?:\w+\s+){0,2}"
    r"(?:experience|background|work|training|skills|knowledge|practical|industry)"
    r"|\bor\s+equivalent\b"
    r"|\bdegrees?\s+(?:is\s+|are\s+)?(?:not\s+(?:required|necessary|needed|important|a\s+requirement)"
    r"|optional|don'?t\s+matter|irrelevant|unnecessary)"
    r"|\bno\s+(?:\w+\s+)?degrees?\s+(?:required|necessary|needed)|\bno[- ]degree\b"
    r"|\b(?:don'?t|do\s+not|doesn'?t|does\s+not)\s+(?:need|require|care\s+about|have\s+to\s+have)"
    r"\s+(?:a\s+|any\s+)?(?:\w+\s+){0,2}degrees?"
    r"|\b(?:regardless\s+of|with\s+or\s+without)\s+(?:a\s+|any\s+)?(?:formal\s+)?(?:\w+\s+)?degrees?"
    r"|\b(?:degree|credentials)\s+(?:or|and)\s+(?:not|optional)"
    r"|\bself[- ]taught\b",
    re.IGNORECASE,
)


def degree(text: str) -> str:
    """'optional' when the post says a degree isn't needed or experience can stand in,
    'required' when it asks for or prefers one, else 'none'."""
    asked = False
    for m in DEGREE.finditer(text):
        before = text[max(0, m.start() - 60) : m.start()]
        if (
            NOT_ASKED_BEFORE.search(before)
            or IDIOM_BEFORE.search(before)
            or NOT_ASKED_AFTER.search(text[m.end() : m.end() + 30])
        ):
            continue
        asked = True
        if DEGREE_OPTIONAL.search(text[m.end() : m.end() + 120]):
            return "optional"
    for m in DEGREE_OPTIONAL.finditer(text):
        # "or equivalent experience" only means something next to a degree; the others
        # ("no degree required") stand on their own.
        if not re.match(r"or\b", m.group(), re.IGNORECASE):
            return "optional"
    return "required" if asked else "none"
