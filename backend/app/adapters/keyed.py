"""Official APIs that need a free key. Without a key each raises NeedsKey and the source shows as 'needs key'."""
import time

import httpx

from ..config import get_settings
from ..normalize.text import html_to_text
from .base import Blocked, NeedsKey, RawJob, adapter, get_json, number, parse_date

ADZUNA_COUNTRIES = {"au": "AUD", "ca": "CAD", "us": "USD", "in": "INR", "nz": "NZD"}
PRIORITY_LOCATIONS = ["Australia", "Canada", "United States", "India", "New Zealand"]
SEARCH_TERMS = ["software engineer", "data", "developer", "cloud", "cyber security", "engineer"]


@adapter("adzuna")
def adzuna(http, config):
    s = get_settings()
    if not (s.adzuna_app_id and s.adzuna_app_key):
        raise NeedsKey("ADZUNA_APP_ID and ADZUNA_APP_KEY")
    pages = int(config.get("pages_per_category", 5))
    for country, currency in ADZUNA_COUNTRIES.items():
        for category in ("it-jobs", "engineering-jobs"):
            for page in range(1, pages + 1):
                data = get_json(http, f"https://api.adzuna.com/v1/api/jobs/{country}/search/{page}", params={
                    "app_id": s.adzuna_app_id, "app_key": s.adzuna_app_key, "results_per_page": 50,
                    "category": category, "sort_by": "date",
                })
                rows = data.get("results") or []
                for j in rows:
                    area = (j.get("location") or {}).get("area") or []
                    predicted = str(j.get("salary_is_predicted")) == "1"
                    yield RawJob(
                        external_id=str(j["id"]), title=html_to_text(j["title"]), company=(j.get("company") or {}).get("display_name"),
                        description=html_to_text(j.get("description")), location=", ".join(reversed(area)) or None,
                        country_code=country.upper().replace("GB", "GB"), url=j.get("redirect_url"),
                        employment_type=j.get("contract_time"),
                        # Adzuna's modelled salaries are estimates, not advertised pay, so they are left out.
                        salary_min=None if predicted else number(j.get("salary_min")),
                        salary_max=None if predicted else number(j.get("salary_max")),
                        salary_currency=None if predicted else currency, salary_period="year",
                        posted_at=parse_date(j.get("created")),
                    )
                if len(rows) < 50:
                    break
                time.sleep(2.6)  # free tier: 25 calls a minute


@adapter("jooble")
def jooble(http, config):
    key = get_settings().jooble_api_key
    if not key:
        raise NeedsKey("JOOBLE_API_KEY")
    for location in PRIORITY_LOCATIONS:
        for term in SEARCH_TERMS[:4]:
            for page in range(1, 4):
                response = http.post(f"https://jooble.org/api/{key}", json={"keywords": term, "location": location, "page": str(page)})
                if response.status_code in (401, 403, 429):
                    raise Blocked(f"Jooble returned {response.status_code}")
                response.raise_for_status()
                rows = response.json().get("jobs") or []
                for j in rows:
                    yield RawJob(
                        external_id=str(j["id"]), title=html_to_text(j["title"]), company=j.get("company"),
                        description=html_to_text(j.get("snippet")), location=j.get("location") or location, url=j.get("link"),
                        employment_type=j.get("type") or None, salary_text=j.get("salary") or None, posted_at=parse_date(j.get("updated")),
                    )
                if not rows:
                    break
                time.sleep(1.0)


@adapter("careerjet")
def careerjet(http, config):
    key = get_settings().careerjet_api_key
    if not key:
        raise NeedsKey("CAREERJET_API_KEY")
    locales = {"en_AU": "AU", "en_CA": "CA", "en_US": "US", "en_IN": "IN", "en_GB": "GB", "en_IE": "IE", "en_NZ": "NZ", "en_SG": "SG", "de_DE": "DE", "fr_FR": "FR", "nl_NL": "NL"}
    # The API requires the end user's IP. For a personal app that is this machine's public address.
    user_ip = httpx.get("https://api.ipify.org", timeout=15).text.strip()
    for locale, country in locales.items():
        for term in SEARCH_TERMS[:3]:
            for page in range(1, 4):
                response = http.get("https://search.api.careerjet.net/v4/query", auth=(key, ""), params={
                    "locale_code": locale, "keywords": term, "page": page, "page_size": 100, "sort": "date",
                    "user_ip": user_ip, "user_agent": get_settings().user_agent,
                })
                if response.status_code in (401, 403, 429):
                    raise Blocked(f"Careerjet returned {response.status_code}")
                response.raise_for_status()
                rows = response.json().get("jobs") or []
                for j in rows:
                    yield RawJob(
                        external_id=j.get("url"), title=html_to_text(j.get("title")), company=j.get("company"),
                        description=html_to_text(j.get("description")), location=j.get("locations"), country_code=country,
                        url=j.get("url"), salary_text=j.get("salary") or None, posted_at=parse_date(j.get("date")),
                    )
                if len(rows) < 100:
                    break
                time.sleep(1.0)


@adapter("usajobs")
def usajobs(http, config):
    s = get_settings()
    if not (s.usajobs_email and s.usajobs_api_key):
        raise NeedsKey("USAJOBS_EMAIL and USAJOBS_API_KEY")
    # USAJOBS identifies callers by the email they registered, which the owner supplies in .env.
    headers = {"Host": "data.usajobs.gov", "User-Agent": s.usajobs_email, "Authorization-Key": s.usajobs_api_key}
    for page in range(1, int(config.get("max_pages", 10)) + 1):
        data = get_json(http, "https://data.usajobs.gov/api/search", headers=headers, params={"ResultsPerPage": 500, "Page": page})
        rows = data["SearchResult"]["SearchResultItems"]
        for row in rows:
            j = row["MatchedObjectDescriptor"]
            pay = (j.get("PositionRemuneration") or [{}])[0]
            details = (j.get("UserArea") or {}).get("Details") or {}
            interval = {"PA": "year", "PH": "hour", "PD": "day", "BW": "week"}.get(pay.get("RateIntervalCode"))
            yield RawJob(
                external_id=j["PositionID"], title=j["PositionTitle"], company=j.get("OrganizationName"),
                description=" ".join(filter(None, [j.get("QualificationSummary"), details.get("JobSummary")])),
                location=j.get("PositionLocationDisplay"), country_code="US", url=j.get("PositionURI"),
                salary_min=number(pay.get("MinimumRange")), salary_max=number(pay.get("MaximumRange")),
                salary_currency="USD", salary_period=interval or "year",
                posted_at=parse_date(j.get("PublicationStartDate")), valid_through=parse_date(j.get("ApplicationCloseDate")),
            )
        if len(rows) < 500:
            break
        time.sleep(1.0)


@adapter("reed")
def reed(http, config):
    key = get_settings().reed_api_key
    if not key:
        raise NeedsKey("REED_API_KEY")
    for term in SEARCH_TERMS:
        for skip in range(0, 1000, 100):
            rows = get_json(http, "https://www.reed.co.uk/api/1.0/search", auth=(key, ""),
                            params={"keywords": term, "resultsToTake": 100, "resultsToSkip": skip}).get("results") or []
            for j in rows:
                yield RawJob(
                    external_id=str(j["jobId"]), title=j["jobTitle"], company=j.get("employerName"),
                    description=html_to_text(j.get("jobDescription")), location=j.get("locationName"), country_code="GB",
                    url=j.get("jobUrl"), salary_min=number(j.get("minimumSalary")), salary_max=number(j.get("maximumSalary")),
                    salary_currency=j.get("currency") or "GBP", salary_period="year", posted_at=_uk_date(j.get("date")),
                    valid_through=_uk_date(j.get("expirationDate")),
                )
            if len(rows) < 100:
                break
            time.sleep(1.0)


def _uk_date(value):
    if value and "/" in value:
        day, month, year = value.split("/")
        return parse_date(f"{year}-{month}-{day}")
    return parse_date(value)


@adapter("findwork")
def findwork(http, config):
    key = get_settings().findwork_api_key
    if not key:
        raise NeedsKey("FINDWORK_API_KEY")
    url = "https://findwork.dev/api/jobs/"
    for _ in range(int(config.get("max_pages", 20))):
        data = get_json(http, url, headers={"Authorization": f"Token {key}"})
        for j in data.get("results") or []:
            yield RawJob(
                external_id=str(j["id"]), title=j["role"], company=j.get("company_name"), description=html_to_text(j.get("text")),
                location=j.get("location"), remote=bool(j.get("remote")), url=j.get("url"), employment_type=j.get("employment_type"),
                posted_at=parse_date(j.get("date_posted")), tags=j.get("keywords") or [],
            )
        url = data.get("next")
        if not url:
            break
        time.sleep(2.0)


@adapter("francetravail")
def francetravail(http, config):
    s = get_settings()
    if not (s.francetravail_client_id and s.francetravail_client_secret):
        raise NeedsKey("FRANCETRAVAIL_CLIENT_ID and FRANCETRAVAIL_CLIENT_SECRET")
    token = http.post(
        "https://entreprise.francetravail.fr/connexion/oauth2/access_token", params={"realm": "/partenaire"},
        data={"grant_type": "client_credentials", "client_id": s.francetravail_client_id,
              "client_secret": s.francetravail_client_secret, "scope": "api_offresdemploiv2 o2dsoffre"},
    ).raise_for_status().json()["access_token"]
    for start in range(0, 3000, 150):
        response = http.get("https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search",
                            headers={"Authorization": f"Bearer {token}"}, params={"range": f"{start}-{start + 149}", "grandDomaine": "M18"})
        if response.status_code == 204:
            break
        response.raise_for_status()
        rows = response.json().get("resultats") or []
        for j in rows:
            place = j.get("lieuTravail") or {}
            yield RawJob(
                external_id=j["id"], title=j["intitule"], company=(j.get("entreprise") or {}).get("nom"),
                description=j.get("description") or "", location=place.get("libelle"), country_code="FR",
                url=(j.get("origineOffre") or {}).get("urlOrigine"), employment_type=j.get("typeContratLibelle"),
                salary_text=(j.get("salaire") or {}).get("libelle"), posted_at=parse_date(j.get("dateCreation")),
            )
        if len(rows) < 150:
            break
        time.sleep(0.5)
