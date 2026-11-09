"""Salary normalisation: everything comparable becomes annual USD. Amounts are kept in the original currency too."""
import re
from dataclasses import dataclass

ANNUAL_FACTOR = {"year": 1, "month": 12, "week": 52, "day": 260, "hour": 2080}
# Outside this range, a parsed "annual" salary is almost always a parsing or unit error.
MIN_ANNUAL_USD, MAX_ANNUAL_USD = 3_000, 800_000
# A bare "$" means the local dollar in these countries.
LOCAL_DOLLAR = {"AU": "AUD", "CA": "CAD", "NZ": "NZD", "SG": "SGD", "HK": "HKD"}

# Longest first: "US$" contains "S$" and "CA$" contains "A$".
SYMBOLS = [("US$", "USD"), ("AU$", "AUD"), ("CA$", "CAD"), ("NZ$", "NZD"), ("A$", "AUD"), ("C$", "CAD"), ("S$", "SGD"),
           ("£", "GBP"), ("€", "EUR"), ("₹", "INR"), ("$", "USD")]
CODES = "USD|AUD|CAD|NZD|SGD|GBP|EUR|INR|CHF|SEK|NOK|DKK|PLN|JPY|BRL|ZAR|AED"

_MONEY = r"(?:A\$|AU\$|C\$|CA\$|NZ\$|S\$|US\$|£|€|₹|\$|(?:" + CODES + r")\s?)\s?(\d[\d,.]*)\s?(k|K|m|L|lpa|LPA)?"
_RANGE = re.compile(
    _MONEY + r"(?:\s*(?:-|–|—|to)\s*(?:A\$|AU\$|C\$|CA\$|NZ\$|S\$|US\$|£|€|₹|\$|(?:" + CODES + r")\s?)?\s?(\d[\d,.]*)\s?(k|K|m|L|lpa|LPA)?)?"
    r"(?:\s*(?:/|per|an?|p\.?)\s*(hour|hr|h|day|week|month|mo|year|yr|annum|a))?"
)
_PERIOD_MAP = {"hour": "hour", "hr": "hour", "h": "hour", "day": "day", "week": "week", "month": "month", "mo": "month",
               "year": "year", "yr": "year", "annum": "year", "a": "year"}


@dataclass
class Salary:
    min: float | None
    max: float | None
    currency: str | None
    period: str | None


def _amount(number: str, suffix: str | None) -> float | None:
    number = number.rstrip(".,")
    # "120,000" and "120.000" are thousands; "12.5" is a decimal.
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", number):
        number = re.sub(r"[.,]", "", number)
    else:
        number = number.replace(",", "")
    try:
        value = float(number)
    except ValueError:
        return None
    if suffix in ("k", "K"):
        value *= 1_000
    elif suffix == "m":
        value *= 1_000_000
    elif suffix in ("L", "lpa", "LPA"):
        value *= 100_000
    return value


def _currency(snippet: str, country: str | None) -> str | None:
    match = re.search(CODES, snippet)
    if match:
        return match.group(0)
    for symbol, code in SYMBOLS:
        if symbol in snippet:
            return LOCAL_DOLLAR.get(country or "", code) if symbol == "$" else code
    return None


def parse_salary_text(text: str | None, country: str | None = None) -> Salary | None:
    """Pick the first money amount that looks like pay. Bare amounts under 10,000 with no period are ignored."""
    if not text:
        return None
    for match in _RANGE.finditer(text[:20000]):
        low = _amount(match.group(1), match.group(2))
        high = _amount(match.group(3), match.group(4) or match.group(2)) if match.group(3) else None
        if low is None:
            continue
        period = _PERIOD_MAP.get((match.group(5) or "").lower())
        if period is None:
            if low < 10_000 and not match.group(2):
                continue
            period = "year"
        context = text[max(0, match.start() - 40): match.end() + 25].lower()
        if re.search(r"funding|raised|revenue|valuation|series [a-e]|million|billion|arr\b|bonus|stipend for", context):
            continue
        currency = _currency(match.group(0), country)
        if high is not None and high < low:
            high = None
        return Salary(low, high, currency, period)
    return None


def to_annual_usd(amount: float | None, currency: str | None, period: str | None, per_usd: dict[str, float]) -> float | None:
    if amount is None or not currency:
        return None
    rate = 1.0 if currency == "USD" else per_usd.get(currency)
    if not rate:
        return None
    annual = amount * ANNUAL_FACTOR.get(period or "year", 1) / rate
    if not MIN_ANNUAL_USD <= annual <= MAX_ANNUAL_USD:
        return None
    return round(annual, 2)
