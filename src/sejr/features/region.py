"""Where a post is: a seeker's `Location:` line, or the regions a hiring header names.

Precision comes first. A name shared by two regions (Cambridge, Victoria) counts only
when a code next to it settles it ("Cambridge, MA"), and a time zone alone never sets a
region, because Canada and Latin America share US time zones.
"""

import re

from sejr.features.tokens import header_line, remote_token

REGIONS = (
    "us", "canada", "uk", "europe", "india", "latam", "asia_pacific", "africa_mideast",
    "unknown",
)  # fmt: skip

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN",
    "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV",
    "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN",
    "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}  # fmt: skip

# Codes that may follow a city ("Berlin, DE", "London, ON"). When a city is followed by a
# code from its own region it stays put; a US state code moves it ("Paris, TX").
CODES = {
    "canada": {"CA", "CAN", "ON", "BC", "QC", "AB", "NS", "MB", "SK", "NB", "NL", "PE"},
    "uk": {"UK", "GB"},
    "europe": {
        "DE", "FR", "NL", "ES", "PT", "IT", "SE", "NO", "DK", "FI", "PL", "CZ", "AT", "CH",
        "BE", "IE", "GR", "RO", "BG", "HU", "EE", "LV", "LT", "UA", "RU", "SK", "SI", "HR",
        "RS", "LU", "IS", "EU",
    },
    "india": {"IN", "IND"},
    "latam": {"MX", "BR", "AR", "CO", "CL", "PE", "UY", "CR", "EC", "VE"},
    "asia_pacific": {"AU", "NZ", "SG", "JP", "CN", "HK", "TW", "KR", "PH", "VN", "TH", "MY",
                     "ID", "PK", "BD", "LK", "NP"},
    "africa_mideast": {"IL", "AE", "ZA", "NG", "KE", "EG", "TR", "SA", "MA", "GH"},
}  # fmt: skip

# Countries, continents and groupings, matched case-insensitively.
AREAS = {
    "us": r"united states(?: of america)?|(?<!north )(?<!south )(?<!latin )(?<!central )"
    r"america(?!s)|puerto rico",
    "canada": r"canada",
    "uk": r"united kingdom|great britain|britain|england|scotland|(?<!new south )wales"
    r"|northern ireland",
    "europe": r"europe(?:an union)?|european|eea|schengen|germany|deutschland|france"
    r"|spain|portugal|italy|(?:the )?netherlands|belgium|switzerland|austria|sweden|norway"
    r"|denmark|finland|iceland|(?<!northern )ireland|poland|czechia|czech republic"
    r"|slovakia|slovenia|croatia|serbia|bosnia|montenegro|albania|macedonia|kosovo"
    r"|hungary|romania|bulgaria|greece|estonia|latvia|lithuania|ukraine|belarus|moldova"
    r"|russia|luxembourg|malta|cyprus",
    "india": r"india",
    "latam": r"latin america|south america|central america|latam|mexico|brazil|brasil"
    r"|argentina|chile|colombia|peru|ecuador|uruguay|paraguay|bolivia|venezuela"
    r"|costa rica|panama|guatemala|honduras|el salvador|nicaragua|dominican republic"
    r"|cuba|jamaica|caribbean",
    "asia_pacific": r"asia|apac|oceania|australia|new zealand|singapore|japan|china"
    r"|hong kong|taiwan|(?:south )?korea|philippines|vietnam|thailand|malaysia"
    r"|indonesia|cambodia|myanmar|mongolia|kazakhstan|uzbekistan|kyrgyzstan|pakistan"
    r"|bangladesh|sri lanka|nepal",
    "africa_mideast": r"africa|middle east|mena|israel|turkey|t[uü]rkiye|armenia"
    r"|azerbaijan|united arab emirates|uae|saudi arabia|qatar|bahrain|kuwait|oman"
    r"|jordan|lebanon|iran|iraq|egypt|morocco|tunisia|algeria|nigeria|ghana|kenya"
    r"|ethiopia|uganda|rwanda|tanzania|zimbabwe|zambia|cameroon|senegal",
}
# Groupings that span regions; a seeker in one of these has no single region.
MULTI = {
    "north america": ("us", "canada"),
    "americas": ("us", "canada", "latam"),
    "emea": ("europe", "uk", "africa_mideast"),
}

# Cities and sub-national areas. A trailing code can move these (see CODES).
CITIES = {
    "us": r"san francisco|bay area|silicon valley|silicon beach|new york|brooklyn"
    r"|manhattan|queens|seattle|boston|austin|chicago|los angeles|denver|boulder|atlanta"
    r"|washington|miami|portland|san diego|san jos[eé](?!,?\s*costa rica)|palo alto"
    r"|mountain view|menlo park|redwood city|san mateo|sunnyvale|santa clara|cupertino"
    r"|oakland|berkeley|santa monica|irvine|pasadena|sacramento|philadelphia|pittsburgh"
    r"|houston|dallas|phoenix|minneapolis|detroit|ann arbor|nashville|raleigh|durham"
    r"|salt lake city|baltimore|columbus|cleveland|cincinnati|st\.? louis|kansas city"
    r"|tampa|orlando|charlotte|new orleans|las vegas|honolulu|indianapolis|milwaukee"
    r"|madison|providence|new haven|somerville|waltham|jersey city|hoboken|soma|socal"
    r"|norcal|new england|midwest|pacific northwest|east coast|west coast|tri-?state"
    r"|alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida"
    r"|georgia(?!\W{0,3}(?:utc|gmt|tbilisi|\(country|europe))|hawaii|idaho|illinois"
    r"|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan"
    r"|minnesota|mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey"
    r"|new mexico|north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania"
    r"|rhode island|south carolina|south dakota|tennessee|texas|utah|vermont|virginia"
    r"|wisconsin|wyoming|district of columbia",
    "canada": r"toronto|vancouver|montr[eé]al|ottawa|calgary|edmonton|waterloo|kitchener"
    r"|mississauga|kanata|winnipeg|halifax|qu[eé]bec|ontario|british columbia|alberta"
    r"|nova scotia|manitoba|saskatchewan|new brunswick|newfoundland",
    "uk": r"london|manchester|edinburgh|glasgow|bristol|oxford|leeds|birmingham|belfast"
    r"|cardiff|brighton|liverpool|sheffield|nottingham",
    "europe": r"berlin|munich|m[uü]nchen|hamburg|frankfurt|cologne|k[oö]ln|stuttgart"
    r"|d[uü]sseldorf|darmstadt|karlsruhe|leipzig|dresden|paris|lyon|toulouse|amsterdam"
    r"|rotterdam|utrecht|eindhoven|the hague|delft|brussels|antwerp|ghent|z[uü]rich"
    r"|geneva|lausanne|basel|vienna|prague|brno|warsaw|krak[oó]w|wroc[lł]aw|gda[nń]sk"
    r"|budapest|bucharest|cluj|sofia|athens|thessaloniki|belgrade|zagreb|ljubljana"
    r"|bratislava|tallinn|riga|vilnius|helsinki|stockholm|gothenburg|g[oö]teborg"
    r"|malm[oö]|copenhagen|aarhus|oslo|reykjav[ií]k|dublin|cork|galway|madrid|barcelona"
    r"|valencia|seville|m[aá]laga|lisbon|lisboa|porto(?! alegre)|milan|rome|turin"
    r"|bologna|kyiv|kiev|kharkiv|lviv|odessa|minsk|moscow|st\.? petersburg"
    r"|saint petersburg|novosibirsk|bavaria",
    "india": r"bangalore|bengaluru|mumbai|bombay|new delhi|delhi|ncr|gurgaon|gurugram|noida"
    r"|hyderabad|chennai|pune|kolkata|calcutta|ahmedabad|jaipur|kochi|cochin|kerala"
    r"|chandigarh|indore|coimbatore|trivandrum|thiruvananthapuram|mysore|nagpur|surat"
    r"|lucknow|bhubaneswar|goa|karnataka|maharashtra|tamil nadu|gujarat|rajasthan"
    r"|telangana|andhra pradesh|uttar pradesh|west bengal|vadodara|rajkot"
    r"|visakhapatnam|mangalore|kanpur|bhopal|patna|dehradun|srinagar",
    "latam": r"mexico city|cdmx|guadalajara|monterrey|tijuana|s[aã]o paulo|rio de janeiro"
    r"|belo horizonte|florian[oó]polis|porto alegre|curitiba|recife|bras[ií]lia|campinas"
    r"|buenos aires|c[oó]rdoba|rosario|mendoza|santiago|bogot[aá]|medell[ií]n"
    r"|barranquilla|lima|quito|guayaquil|montevideo|asunci[oó]n|caracas"
    r"|san jos[eé],?\s*costa rica",
    "asia_pacific": r"karachi|lahore|islamabad|dhaka|colombo|kathmandu|beijing|shanghai"
    r"|shenzhen|hangzhou|guangzhou|chengdu|suzhou|taipei|tokyo|osaka|kyoto|seoul|busan"
    r"|kuala lumpur|penang|jakarta|bali|bandung|manila|cebu|hanoi|ho chi minh|saigon"
    r"|bangkok|chiang mai|phnom penh|almaty|tashkent|bishkek|sydney|melbourne|brisbane"
    r"|perth|adelaide|canberra|hobart|gold coast|auckland|wellington|christchurch"
    r"|new south wales|queensland",
    "africa_mideast": r"tel[ -]?aviv|jerusalem|haifa|dubai|abu dhabi|riyadh|doha|amman"
    r"|beirut|tehran|cairo|casablanca|lagos|abuja|accra|nairobi|addis ababa|kampala"
    r"|kigali|cape town|johannesburg|durban|pretoria|istanbul|ankara|tbilisi|yerevan"
    r"|baku",
}
# Case-sensitive abbreviations: "us" is a pronoun and "LA" is only a place in capitals.
ABBREVIATIONS = {
    "us": r"USA|US|U\.S\.(?:A\.)?|SF|NYC|NY|LA|DC|D\.C\.|ATX|PDX",
    "canada": r"CAN|GTA|(?<=US/)CA|(?<=US & )CA|(?<=USA/)CA",
    "uk": r"UK|U\.K\.",
    "europe": r"EU",
    "asia_pacific": r"NZ|ANZ|APAC",
    "africa_mideast": r"UAE|MENA",
    "latam": r"LATAM|LatAm",
}

CITY_CODE = re.compile(r",?\s*([A-Z]{2})\b(?![\w'’-])")
# A code after an unknown town: "Fargo, ND", "Eindhoven, NL", or "Irvine CA" at the end
# of a field. Without a comma only US state codes count, since "Acme IT" or "Acme SA" is
# a company name.
CODE_AFTER_TOWN = re.compile(
    r"(?P<town>[A-Z][\w.'’-]{2,})"
    r"(?P<sep>,\s*|\s+(?=[A-Z]{2}\s*(?:$|[,|;/)\]·•.(]|[-–—]\s)))"
    r"(?P<code>[A-Z]{2})\b(?![\w'’-])"
)
LEGAL_SUFFIXES = {"AB", "AG", "AS", "BV", "OY", "SA"}
NOT_A_TOWN = re.compile(
    r"^(?:remote|onsite|on-site|hybrid|visa|relocation|interns?|time|contract|yes|no"
    r"|only|full|part|and|or)$",
    re.IGNORECASE,
)
# "Remote (non-US)", "outside the EU": the place is excluded, not named.
EXCLUDING = r"(?:\bnon|\boutside(?: of)?(?: the)?|\bexcept|\bexcluding|\bex)[\s-]*"
EXCLUDED = re.compile(EXCLUDING + "$", re.IGNORECASE)
NOT_US = re.compile(
    EXCLUDING + r"(?:US|USA|U\.S\.|united states|america)\b", re.IGNORECASE
)

# Time zones only decide whether a remote post takes US workers. "US time zones" or
# "EU hours" is a time zone too, not a place.
ZONE_AFTER = re.compile(
    r"[\s-]*(?:(?:pacific|eastern|central|mountain)\s+)?(?:time|tz\b|hours|business hours)",
    re.IGNORECASE,
)
US_TIME = re.compile(
    r"\b(?-i:PST|PDT|PT|EST|EDT|ET|CST|CDT|CT|MST|MDT|MT)\b"
    r"|\b(?:pacific|eastern|central|mountain)(?: standard| daylight)? time"
    r"|\b(?:UTC|GMT)\s?[-−–]\s?(?:[4-9]|10)\b"
    r"|\b(?:(?-i:US|U\.S\.|USA)|american?|north american?|(?:east|west)[- ]coast(?: US)?)"
    + ZONE_AFTER.pattern,
    re.IGNORECASE,
)
OTHER_TIME = re.compile(
    r"\b(?-i:CET|CEST|EET|EEST|WET|BST|GMT|IST|AEST|AEDT|JST|SGT)\b"
    r"|\b(?:UTC|GMT)\s?\+\s?\d"
    r"|\b(?:(?-i:EU|UK|APAC)|europe(?:an)?|india(?:n)?|asian?)" + ZONE_AFTER.pattern,
    re.IGNORECASE,
)
WORLDWIDE = re.compile(
    r"\b(?:world-?wide|anywhere(?!\s+(?:in|within)\b)|global(?:ly)?|international(?:ly)?"
    r"|any (?:time ?zone|location|country)|all time ?zones)\b",
    re.IGNORECASE,
)

LOCATION_LINE = re.compile(
    r"^[^\w\n]{0,6}location\b[^\w\n]{0,4}(?P<value>[^\n]*)(?:\n(?P<next>[^\n]*))?",
    re.IGNORECASE | re.MULTILINE,
)
# Posts written on one line run the next field on after the location.
NEXT_FIELD = re.compile(
    r"\s(?:remote|willing to relocate|relocat\w*|technologies|tech stack|stack|r[eé]sum[eé]"
    r"|cv|email|e-mail|contact|github|linkedin|website|portfolio)\s*[:?]",
    re.IGNORECASE,
)
LOCATION_CHARS = 100


def _alternation(names: dict[str, str], flags: int) -> list[tuple[re.Pattern, str]]:
    return [
        (re.compile(rf"(?<![\w-])(?:{pattern})(?![\w-])", flags), region)
        for region, pattern in names.items()
    ]


AREA_PATTERNS = _alternation(AREAS, re.IGNORECASE)
MULTI_PATTERN = re.compile(rf"\b(?:{'|'.join(MULTI)})\b", re.IGNORECASE)
CITY_PATTERNS = _alternation(CITIES, re.IGNORECASE)
ABBREVIATION_PATTERNS = [
    (re.compile(rf"(?<![\w.-])(?:{pattern})(?![\w-])"), region)
    for region, pattern in ABBREVIATIONS.items()
]


def _city_region(region: str, code: str) -> str:
    if code in CODES.get(region, set()):
        return region
    if code in US_STATES:
        return "us"
    return "canada" if code in CODES["canada"] else region


def _code_region(code: str) -> str | None:
    if code in US_STATES:
        return "us"
    for region, codes in CODES.items():
        if code in codes:
            return region
    return None


def place_mentions(text: str) -> list[tuple[int, tuple[str, ...]]]:
    """(offset, regions) for each place named in `text`, in reading order."""
    found: list[tuple[int, int, tuple[str, ...], bool]] = []
    for pattern, region in AREA_PATTERNS:
        found += [
            (m.start(), m.end(), (region,), False) for m in pattern.finditer(text)
        ]
    for m in MULTI_PATTERN.finditer(text):
        found.append((m.start(), m.end(), MULTI[m.group().lower()], False))
    for pattern, region in CITY_PATTERNS:
        found += [(m.start(), m.end(), (region,), True) for m in pattern.finditer(text)]
    for pattern, region in ABBREVIATION_PATTERNS:
        found += [
            (m.start(), m.end(), (region,), False) for m in pattern.finditer(text)
        ]
    # Longest match wins where names overlap ("New Mexico" over "Mexico").
    found.sort(key=lambda f: (f[0], f[0] - f[1]))
    mentions: list[tuple[int, tuple[str, ...]]] = []
    taken: list[tuple[int, int]] = []
    end = -1
    for start, stop, regions, is_city in found:
        if start < end:
            continue
        end = stop
        if EXCLUDED.search(text[max(0, start - 20) : start]) or ZONE_AFTER.match(
            text, stop
        ):
            taken.append((start, stop))
            continue
        code = CITY_CODE.match(text, stop)
        if code and _code_region(code.group(1)):
            end = code.end()
            if is_city:
                regions = (_city_region(regions[0], code.group(1)),)
        taken.append((start, end))
        mentions.append((start, regions))
    for m in CODE_AFTER_TOWN.finditer(text):
        code_at = m.start("code")
        if NOT_A_TOWN.match(m["town"]) or any(a <= code_at < b for a, b in taken):
            continue
        code = m["code"]
        if code in LEGAL_SUFFIXES or ("," not in m["sep"] and code not in US_STATES):
            continue
        if region := _code_region(code):
            mentions.append((code_at, (region,)))
    return sorted(mentions)


def location_line(text: str) -> str | None:
    """The value of a seeker's `Location:` line, cut before any field run on after it."""
    m = LOCATION_LINE.search(text)
    if not m:
        return None
    value = m["value"].strip(" :-–=*\t")
    # "Location:" alone on its line, with the place on the next.
    if not value and m["next"] and ":" not in m["next"]:
        value = m["next"].strip()
    if stop := NEXT_FIELD.search(" " + value):
        value = value[: max(0, stop.start() - 1)]
    return value[:LOCATION_CHARS].strip() or None


def seeker_region(text: str) -> str:
    """The first single-region place on the Location line (where the person is now)."""
    line = location_line(text)
    for _, regions in place_mentions(line or ""):
        if len(regions) == 1:
            return regions[0]
    return "unknown"


def hiring_regions(text: str) -> tuple[list[str], bool]:
    """Regions the header names, and whether the post is open to US workers.

    A remote post is open to US workers when it names a US place, or a worldwide, North
    American, Americas or US-time-zone restriction, or no place at all. "REMOTE (EU)" or
    "Berlin | Remote" is not.
    """
    header = header_line(text)
    regions = sorted(
        {r for _, rs in place_mentions(header) for r in rs}, key=REGIONS.index
    )
    if "us" in regions:
        return regions, True
    if not remote_token(text) or NOT_US.search(header):
        return regions or ["unknown"], False
    open_to_us = bool(
        WORLDWIDE.search(header)
        or US_TIME.search(header)
        or not (regions or OTHER_TIME.search(header))
    )
    return regions or ["unknown"], open_to_us
