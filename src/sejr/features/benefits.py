"""Benefits a hiring post offers, from a fixed list. Adding one means rerunning every month."""

import re

from sejr.features.tokens import is_negated, mentions_visa

NUMBER = r"(?:\d{1,2}(?:\.\d)?|one|two|three|four|five|six|seven|eight|ten|twelve|fifteen|twenty(?:[- ]\w+)?|thirty)"
TIME_OFF = r"(?:pto|paid time[- ]off|vacation|holidays?|time[- ]off|annual leave|days off|weeks off)"

# Each benefit is a list of patterns; a post offers it when any match is not negated
# ("no equity", "we can't offer relocation") and is not one of its false friends.
BENEFITS: dict[str, list[str]] = {
    "equity": [
        r"\bequity\b",
        r"\bstock\s+options?\b|\boptions?\s+(?:package|grants?|pool)\b|\+\s*options\b",
        r"\b(?:salary|pay|compensation|cash)\W+(?:\w+\W+){0,2}options\b",
        # A header field that is only a percentage: "| €60k | <1% |".
        r"\|\s*[<~]?\s*\d+(?:\.\d+)?\s*%(?:\s*[-–]\s*\d+(?:\.\d+)?\s*%)?\s*(?=\||$)",
        r"\bstock\s+(?:compensation|packages?|plans?)\b",
        r"\bRSUs?\b|\bESOP\b|\bemployee\s+stock\b|\bstock\s+(?:grants?|awards?|units?)\b",
        r"\bownership\s+stake\b|\bphantom\s+(?:stock|equity)\b",
    ],
    "retirement": [
        r"\b401\s?\(?k\)?(?!\w)",
        r"\bpensions?\b|\bsuperannuation\b|\bRRSP\b|\bKiwiSaver\b",
        r"\bretirement\s+(?:plans?|match\w*|savings|contributions?|benefits?|accounts?|fund)\b",
        r"\bretirement\s*(?:\+|and|with)\s*(?:company\s+)?match",
        # Retirement in a benefits list: "(medical, dental, retirement)".
        r"\b(?:medical|dental|vision|health\s?care|health)\s*,\s*(?:\w+\s*,\s*)*(?:and\s+)?retirement\b",
        r"\bretirement\s*,\s*(?:\w+\s*,\s*)*(?:and\s+)?(?:medical|dental|vision|health)\b",
    ],
    "health_insurance": [
        r"\b(?:health|medical)(?:\s?care)?\s+(?:insurance|benefits?|coverage|plans?|cover|premiums?)\b",
        r"\b(?:health|medical|med)(?:\s?care)?\s*(?:,|/|&|\+|and)\s*(?:health\s*,?\s*)?(?:dental|vision)\b",
        r"\bfull\s+(?:health\s?care|medical)\b",
        # "health care" as an item in a benefits list ("time off, health care, 401k"), not in a
        # list of industries ("retail, and healthcare").
        (
            r"(?:^|[,:;•*(]\s*|\band\s+)health\s?care(?=\s*(?:[,;/.)]|and\b|$))"
            r"(?=[^.\n]{0,60}\b(?:401|dental|vision|pto|vacation|insurance|perks|equity|stipends?"
            r"|retirement|pension|time\s+off|bonus|salary|life)\b)"
        ),
        (
            r"\b(?:401k?|dental|vision|pto|vacation|perks|benefits|equity|stipends?|salary|pay|bonus"
            r"|time\s+off)\b[^.\n]{0,60}(?:[,:;•*]\s*|\band\s+)health\s?care(?=\s*(?:[,;/.)]|and\b|$))"
        ),
        r"\b(?:dental|vision)\s*(?:,|/|&|\+|and)\s*(?:\w+\s*(?:,|/|&|and)\s*)?(?:health|medical)\b",
        (
            r"\b(?:private|fully[- ]paid|fully[- ]covered|(?:fully\s+)?subsidi[sz]ed|100%(?:\s+(?:paid|covered))?)"
            r"\s+(?:\w+\s+)?(?:health|medical)(?:\s?care)?\b"
        ),
        r"\binsurance\s*[(:]\s*(?:\w+\s*[,/&]\s*)*(?:medical|health)\b",
        r"\b(?:health|medical)(?:\s?care)?\s+(?:is\s+|are\s+)?(?:100%\s+|fully\s+)?(?:covered|paid)\b",
    ],
    "dental_vision": [
        r"\bdental\b(?=[^.\n]{0,40}\b(?:insurance|vision|health|medical|benefits?|coverage|plans?|401|pto)\b)",
        r"\b(?:health|medical|insurance|benefits)\b[^.\n]{0,40}\bdental\b",
        r"\b(?:dental|medical|health|med)\s*(?:,|/|&|\+|and)\s*(?:\w+\s*(?:,|/|&|and)\s*)?vision\b",
        r"\bvision\s+(?:insurance|coverage|plans?|benefits?)\b",
    ],
    "unlimited_pto": [
        r"\b(?:unlimited|uncapped|untracked|unmetered|flexible|open|self-managed|discretionary"
        r"|take what you need)\s+(?:paid\s+)?" + TIME_OFF + r"\b",
        r"\btake\s+(?:the\s+)?(?:time\s+off|vacation)\s+(?:you\s+need|when\s+you\s+need)",
    ],
    # A stated amount of paid time off, whatever it is: "25 days vacation", "4 weeks PTO".
    "pto_days": [
        r"\b"
        + NUMBER
        + r"\+?[\s-]*(?:working\s+|paid\s+|business\s+)?(?:days?|weeks?)'?\s*(?:of\s+)?"
        r"(?:paid\s+|annual\s+)?(?:pto|paid time off|vacation|holidays?|time off|annual leave|off)\b",
        # "75 paid vacation days", "12 holidays".
        r"\b" + NUMBER + r"\s+(?:paid\s+)?(?:vacation|holiday|pto)s?(?:\s+days?)?\b",
        r"\b(?:pto|paid time off|vacation|holidays?|annual leave)\s*(?::|of|-|–)?\s*"
        + NUMBER
        + r"\+?\s*(?:working\s+)?(?:days?|weeks?)\b",
    ],
    "parental_leave": [
        r"\b(?:parental|maternity|paternity|family|parent|caregiver|bonding|baby)\s+leave\b",
        r"\bpaid\s+(?:parental|maternity|paternity)\b",
    ],
    "four_day_week": [
        r"\b(?:4|four)[- ]?day\s+(?:work\s*)?(?:weeks?|workweeks?)\b(?![^.\n]{0,25}\b(?:in[- ]office|onsite|on-site|in the office|in person))",
        r"\b32[- ]hours?\s+(?:work\s*)?weeks?\b",
    ],
    "learning_budget": [
        (
            r"\b(?:learning|education(?:al)?|training|conferences?|development|books?|L&D|courses?)"
            r"(?:\s+(?:and|&|/)\s+\w+)?\s+(?:budgets?|stipends?|allowances?|reimbursements?"
            r"|expense\s+accounts?)\b"
        ),
        r"\b(?:learning|education(?:al)?|training)\s+funds?\b",
        r"\btuition\s+(?:reimbursement|assistance|support)\b",
        r"\bspend\s+on\s+(?:continuing\s+)?(?:education|learning|training|conferences|books)\b",
    ],
    "remote_stipend": [
        (
            r"\b(?:home[- ]office|work[- ]from[- ]home|wfh|remote(?:[- ]work)?|co-?working|workspace"
            r"|desk|office\s+setup|equipment|gear|internet|home\s+workplace)(?:\s*/\s*\w+)?\s+(?:\w+\s+)?(?:stipends?|budgets?"
            r"|allowances?|reimbursements?)\b"
        ),
        r"\bhome[- ]office\s+(?:support|expenses?)\b",
    ],
    "relocation": [
        (
            r"\breloc(?:ation)?\s*(?:assistance|support|package|help|bonus|reimbursement|expenses"
            r"|available|offered|provided|benefits?|possible|ok|paid|costs|stipend|allowance|budget|incentives?"
            r"|\+|and\s+(?:visa|h-?1b|immigration|sponsorship))\b"
        ),
        (
            r"\b(?:help|assist|support|cover|pay|offer|provide|sponsor)\w*\s+(?:with\s+|for\s+|to\s+)?(?:your\s+|the\s+)?"
            r"(?:relocation|relocating|relocate)\b"
        ),
        r"\bmoving\s+(?:costs|expenses|allowance|stipend|assistance)\b",
        (
            r"\brelocation\b[^.\n]{0,40}\b(?:taken care|covered|paid for|included|provided|supported"
            r"|possible|available|negotiable|considered|an option|on the table)\b"
        ),
        # "relocation to the Bay Area" in a perks list.
        r"\brelocation\s+to\s+(?:the\s+)?(?-i:[A-Z])",
        r"\bconsider\w*\s+(?:\w+\s+)?relocation\b",
        r"\b(?:assist\w*|help|support)\s+(?:in|with)\s+relocat\w*",
        # A token in a header list: "(Local, Remote, Visa, Relocation)".
        r"[(,|]\s*reloc(?:ation)?\s*(?=[,)|])",
        r"\b(?:relocate|relocating)\s+(?:\w+\s+)?(?:you|people|candidates|employees|engineers|folks|hires)\b",
        r"\breloc(?:ation)?\s+(?:for|to)\s+(?:the\s+)?(?:right|good|great|strong|qualified|exceptional)\b",
        (
            r"\brelo\b\s*(?:supported|assistance|support|ok|available|package|offered|provided|help)"
            r"|\b(?:visa|h-?1b)\s*(?:&|and|\+|/)\s*relo\b"
        ),
        r"(?:^|\||\n)\s*reloc(?:ation)?\s*(?=\||\n|$)",
    ],
    "sign_on_bonus": [r"\bsign(?:ing|[- ]on)[- ]bonus(?:es)?\b"],
    "bonus": [r"\bbonus(?:es)?\b"],
}
# Words that look like a benefit but name something else.
NOT_A_BENEFIT: dict[str, re.Pattern[str]] = {
    "equity": re.compile(
        r"(?:private|home|pay|health|racial|social|brand|gender|digital|educational|tax"
        r"|diversity,?|inclusion,)\s+equity\b|\bequity\s+(?:and|&)\s+inclusion"
        r"|\bequity\s+(?:research|markets?|trading|derivatives|analysts?|crowdfunding|financing"
        r"|investors?|investments?|investing|firms?|funds?|partners?|round|raise|capital|backed"
        r"|management|portfolios?|compensation\s+plans?\s+for\s+clients|platform|plans\s+for)\b"
        r"|equity-backed|\bDEI\b|\bequity\s+of\b|\bequity[- ]free\b|\bequity\s+equivalent"
        r"|\b(?:their|employees'?|founders'?)\s+equity\b",
        re.IGNORECASE,
    ),
    "bonus": re.compile(
        r"\bsign(?:ing|[- ]on)[- ]bonus|\bbonus\s+points?\b|\bbonus(?:es)?\s*:|\bbonus\s+if\b|\(\s*bonus\s*\)"
        r"|\b(?:is|are|be|as|'s|’s|a|an)\s+(?:a\s+|an\s+)?(?:big|huge|major|nice|definite|great"
        r"|added|extra|strong|massive|real|significant|serious|bonus|plus|small)?\s*bonus\b"
        r"|\b(?:big|huge|major|nice|definite|great|added|extra|massive|significant)\s+bonus\b"
        r"|\b(?:referral|patent)\s+bonus|\bbonus\s+(?:for|to|but|skills?|qualifications?|points?"
        r"|experience|if|questions?|round)\b|\bplus\s*/\s*bonus|\bbonus\s*/(?!\s*carry)|/\s*bonus\b"
        r"|\b(?:nice[- ]to[- ]haves?|preferred)\W+bonus|\bbonus\s+system",
        re.IGNORECASE,
    ),
    # Product words: "insurance eligibility", "health plans" a company builds for others.
    "health_insurance": re.compile(
        r"(?:rebuild\w*|reinvent\w*|disrupt\w*|fix\w*|transform\w*|navigat\w*|simplif\w*"
        r"|access\s+to|afford\w*|buy\w*|sell\w*|creat\w*|build\w*|employers?|members?|carriers?"
        r"|claims?|customers?|from|people|help\w*|approach\s+to|pick\w*|choos\w*|make|understand\w*"
        r"|compar\w*|manag\w*|enroll\w*|shop\w*|platform\s+for|marketplace\s+for|interact\w*\s+with)"
        r"\s+(?:\w+\s+){0,2}(?:health|medical)(?:\s?care)?\s+(?:insurance|plans?|benefits?|coverage)"
        # Health insurance as the company's domain: "the health insurance industry".
        r"|\b(?:health|medical)(?:\s?care)?\s+(?:insurance|benefits?)\s+(?:industry|market|space"
        r"|companies|carriers|brokers|claims|plans\s+for|navigation)\b",
        re.IGNORECASE,
    ),
    # A move the candidate must make: "require relocation to Japan", "willing to relocate".
    "relocation": re.compile(
        r"(?:requir\w*|must|willing\s+to|open\s+to(?!\s+(?:provid|offer|cover|help|assist|pay|support))"
        r"|need\w*|expect\w*)\s+(?:[\w()]+\s+){0,2}relocat\w*\b"
        r"(?!\s+(?:people|you|candidates|employees|engineers|folks|hires))"
        # "relocation to Austin is required", but not "relocation support if required".
        r"|\brelocat\w*\s+(?:to\s+(?:[\w,]+\s+){1,4}?)?(?:is\s+|will\s+be\s+|would\s+be\s+)?"
        r"(?:required|preferred|expected|mandatory|a\s+must)\b",
        re.IGNORECASE,
    ),
    "parental_leave": re.compile(
        r"\bleave\s+(?:requests?|management|tracking|administration|software|platform|policies\s+for)\b",
        re.IGNORECASE,
    ),
    "retirement": re.compile(
        r"\bpension\s+(?:funds?|providers?|industry|market|administrators?|consultants?)\b"
        r"|\bretirement\s+(?:planning|savers?)\b|401\s?\(?k\)?\s+(?:platforms?|plans?\s+for"
        r"|providers?|administration|industry|market|space|recordkeep\w*|software)\b",
        re.IGNORECASE,
    ),
}
NOT_A_BENEFIT_CHARS = 40
NON_PREFIX = re.compile(r"\bnon-(?=\w)", re.IGNORECASE)
NEGATED_INSIDE = re.compile(
    r"\b(?:not|no|cannot|unable|never)\b|n['’]t\b", re.IGNORECASE
)
PATTERNS = {
    name: [re.compile(p, re.IGNORECASE) for p in patterns]
    for name, patterns in BENEFITS.items()
}
CATEGORIES = (*BENEFITS, "visa")


def _counts(text: str, name: str, m: re.Match[str]) -> bool:
    if false_friend := NOT_A_BENEFIT.get(name):
        start = max(0, m.start() - NOT_A_BENEFIT_CHARS)
        window = text[start : m.end() + NOT_A_BENEFIT_CHARS]
        # Only a false friend that covers this match counts against it.
        if any(
            f.start() + start < m.end() and f.end() + start > m.start()
            for f in false_friend.finditer(window)
        ):
            return False
    # "Relocation not provided": the negation can sit inside a longer match.
    # "non-trivial equity" is not a negation.
    plain = NON_PREFIX.sub("non_", text)
    return not (
        NEGATED_INSIDE.search(m.group()) or is_negated(plain, m.start(), m.end())
    )


def offered_benefits(text: str) -> list[str]:
    found = [
        name
        for name, patterns in PATTERNS.items()
        if any(_counts(text, name, m) for p in patterns for m in p.finditer(text))
    ]
    # Visa help reuses the visa_share rule, so the two never disagree.
    return found + ["visa"] if mentions_visa(text) else found
