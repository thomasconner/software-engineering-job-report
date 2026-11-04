"""Place names used to read headers: where a post is, and what a bare "$" means there."""

import re

# Countries (and their big tech cities) whose own currency is written with "$".
DOLLAR_PLACES = {
    "CAD": r"canada|toronto|vancouver|montreal|ottawa|calgary|waterloo",
    "AUD": r"australia|sydney|melbourne|brisbane|perth",
    "NZD": r"new zealand|auckland|wellington",
    "SGD": r"singapore",
    "HKD": r"hong kong",
    "MXN": r"mexico|ciudad de m[eé]xico|guadalajara",
    "BRL": r"brazil|brasil|s[aã]o paulo",
}
OTHER_COUNTRIES = (
    r"uk|united kingdom|england|scotland|ireland|germany|france|spain|portugal|italy"
    r"|netherlands|the netherlands|belgium|switzerland|austria|sweden|norway|denmark"
    r"|finland|poland|czechia|czech republic|estonia|israel|india|japan|china|korea"
    r"|taiwan|vietnam|philippines|indonesia|argentina|chile|colombia|nigeria|kenya"
    r"|south africa|egypt|turkey|ukraine|romania|bulgaria|greece|hungary|europe|eu|emea"
    r"|latam|apac|uae|dubai"
)
NON_US_CITIES = (
    r"london|berlin|munich|paris|amsterdam|zurich|dublin|madrid|barcelona|lisbon|stockholm"
    r"|copenhagen|oslo|helsinki|warsaw|prague|vienna|tel aviv|bangalore|bengaluru|tokyo"
)
DOLLAR_PLACE = {
    code: re.compile(rf"\b(?:{names})\b", re.IGNORECASE)
    for code, names in DOLLAR_PLACES.items()
}
NON_US_PLACE = re.compile(
    rf"\b(?:{OTHER_COUNTRIES}|{NON_US_CITIES}|{'|'.join(DOLLAR_PLACES.values())})\b",
    re.IGNORECASE,
)
US_PLACE = re.compile(
    r"\b(?:US|USA|U\.S\.A?\.?|United States|America|SF|NYC|Bay Area|Silicon Valley"
    r"|San Francisco|New York|Seattle|Boston|Austin|Chicago|Los Angeles|Denver|Atlanta"
    r"|Washington|Miami|Portland|San Diego|San Jose|Palo Alto|Mountain View)\b"
    # A state code after a comma; the exclusions are Canadian provinces and regions.
    r"|,\s*(?!UK|EU|BC|ON|QC|AB|NS|MB|SK|NB|NL)[A-Z]{2}\b"
)
# Whole first segments that are a place, not a company.
PLACE_ONLY = re.compile(
    rf"^(?:{OTHER_COUNTRIES}|{NON_US_CITIES}|{'|'.join(DOLLAR_PLACES.values())}"
    r"|san francisco|sf|new york|nyc|seattle|boston|austin|chicago|los angeles|denver"
    r"|atlanta|washington|dc|miami|portland|san diego|san jose|palo alto|mountain view"
    r"|menlo park|oakland|berkeley|brooklyn|manhattan|cambridge|philadelphia|pittsburgh"
    r"|bay area|silicon valley|remote|anywhere|worldwide|global|usa|us|united states)$",
    re.IGNORECASE,
)
# "Amsterdam, Netherlands - Acme" or "Palo Alto, CA - Box.net": a place, then the name.
LOCATION_FIRST = re.compile(
    rf"^(?:[A-Z][\w.]*\s?){{1,4}},\s*(?:(?!AG|SA|BV|AB|OY)[A-Z]{{2}}\b|(?i:{OTHER_COUNTRIES}"
    rf"|{'|'.join(DOLLAR_PLACES.values())})\b)\.?\s*(?P<sep>[-–—:|]{{1,2}})?"
)


def dollar_currency(header: str) -> str | None:
    """What a bare "$" most likely means given the header: None when it's plain USD."""
    if US_PLACE.search(header) or not NON_US_PLACE.search(header):
        return None
    codes = [code for code, place in DOLLAR_PLACE.items() if place.search(header)]
    return codes[0] if len(codes) == 1 else "unknown"
