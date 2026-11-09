"""Extraction ladder: schema.org JobPosting JSON-LD first, LLM only for pages that clearly hold one unstructured job."""
import hashlib
import json
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from ..adapters.base import RawJob, number, parse_date
from ..llm import LLMUnavailable, complete_json
from ..normalize.text import html_to_text

JOB_URL = re.compile(r"/(jobs?|careers?|vacanc(y|ies)|positions?|openings?|stellen|stellenangebote|emploi|offres?|empleo|vagas?|viewjob|job-detail|opportunit(y|ies))(/|-|$|\?)", re.I)
DETAIL_HINT = re.compile(r"/(jobs?|careers?|vacanc(y|ies)|positions?|stellenangebote|offres?|viewjob|job-detail)/[^/?]*[a-z0-9-]{6,}", re.I)
APPLY_WORDS = re.compile(r"\b(apply now|apply for this|responsibilities|requirements|qualifications|what you.ll do|about the role|bewerben|postuler)\b", re.I)
SKIP_URL = re.compile(r"\.(pdf|jpe?g|png|gif|svg|zip|docx?|xlsx?|mp4|css|js)(\?|$)|/(login|signin|sign-in|register|signup|privacy|terms|cookie|contact|about|press|blog|cart)(/|$|\?)", re.I)


def _walk_jsonld(node):
    if isinstance(node, list):
        for item in node:
            yield from _walk_jsonld(item)
    elif isinstance(node, dict):
        kind = node.get("@type")
        if kind == "JobPosting" or (isinstance(kind, list) and "JobPosting" in kind):
            yield node
        for key in ("@graph", "mainEntity", "itemListElement", "item"):
            if key in node:
                yield from _walk_jsonld(node[key])


def jobpostings_from_html(html: str) -> list[dict]:
    found = []
    for block in re.findall(r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", html, re.S | re.I):
        try:
            found.extend(_walk_jsonld(json.loads(block.strip().replace("\n", " "), strict=False)))
        except (json.JSONDecodeError, ValueError):
            continue
    return found


def _place_text(location) -> tuple[str | None, str | None]:
    """Return (location text, ISO country if the posting states one)."""
    if isinstance(location, list):
        location = location[0] if location else None
    if not isinstance(location, dict):
        return (str(location) if location else None), None
    address = location.get("address") or location
    if isinstance(address, str):
        return address, None
    country = address.get("addressCountry")
    if isinstance(country, dict):
        country = country.get("name")
    parts = [address.get("addressLocality"), address.get("addressRegion"), country]
    code = country.upper() if isinstance(country, str) and len(country) == 2 else None
    return ", ".join(p for p in parts if isinstance(p, str) and p) or None, code


def rawjob_from_jsonld(posting: dict, page_url: str) -> RawJob | None:
    title = posting.get("title") or posting.get("name")
    if not title:
        return None
    org = posting.get("hiringOrganization")
    company = org.get("name") if isinstance(org, dict) else org if isinstance(org, str) else None
    location, code = _place_text(posting.get("jobLocation"))
    remote = str(posting.get("jobLocationType", "")).upper() == "TELECOMMUTE"
    if remote and not location:
        applicant = posting.get("applicantLocationRequirements")
        location = (applicant[0] if isinstance(applicant, list) and applicant else applicant or {}).get("name") if isinstance(applicant, (list, dict)) else None
    salary = posting.get("baseSalary") if isinstance(posting.get("baseSalary"), dict) else {}
    value = salary.get("value") if isinstance(salary.get("value"), dict) else {"value": salary.get("value")}
    low = number(value.get("minValue") or value.get("value"))
    period = {"HOUR": "hour", "DAY": "day", "WEEK": "week", "MONTH": "month", "YEAR": "year"}.get(str(value.get("unitText", "YEAR")).upper(), "year")
    identifier = posting.get("identifier")
    ext = (identifier.get("value") if isinstance(identifier, dict) else identifier) or posting.get("url") or page_url
    employment = posting.get("employmentType")
    return RawJob(
        external_id=str(ext), title=html_to_text(str(title)), company=company, description=html_to_text(posting.get("description")),
        location=location, country_code=code, url=posting.get("url") or page_url, remote=remote or None,
        employment_type=", ".join(employment) if isinstance(employment, list) else employment,
        salary_min=low, salary_max=number(value.get("maxValue")), salary_currency=salary.get("currency") if low else None, salary_period=period,
        posted_at=parse_date(posting.get("datePosted")), valid_through=parse_date(posting.get("validThrough")),
    )


def classify_page(url: str, html: str) -> str:
    """listing | detail | article | irrelevant. Deterministic; costs no model time."""
    if jobpostings_from_html(html):
        return "detail"
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True)
    links = [a.get("href", "") for a in soup.find_all("a")]
    job_links = sum(1 for href in links if JOB_URL.search(href))
    if DETAIL_HINT.search(url) and len(APPLY_WORDS.findall(text)) >= 2 and len(text) > 800:
        return "detail"
    if job_links >= 8:
        return "listing"
    if soup.find("article") or len(text) > 2500:
        return "article"
    return "irrelevant"


def llm_extract(url: str, html: str) -> RawJob | None:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)[:6000]
    prompt = (
        "Extract the single job posting from this web page text. Reply with JSON keys: "
        "title, company, location, remote (true/false), employment_type, salary_text, description (the responsibilities and "
        "requirements, under 1500 characters). Use null for anything the text does not state. Never guess. "
        "If the page is not one job posting, reply {\"title\": null}.\n\nPAGE:\n" + text
    )
    try:
        data = complete_json(prompt, system="You extract facts from text and reply with JSON only.")
    except (LLMUnavailable, ValueError):
        return None
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return None
    return RawJob(
        external_id=hashlib.sha1(url.encode()).hexdigest(), title=title, company=data.get("company"), description=str(data.get("description") or text[:3000]),
        location=data.get("location"), remote=data.get("remote") if isinstance(data.get("remote"), bool) else None, url=url,
        employment_type=data.get("employment_type"), salary_text=data.get("salary_text"),
    )


def same_site(url: str, seed: str) -> bool:
    a, b = urlparse(url).netloc.removeprefix("www."), urlparse(seed).netloc.removeprefix("www.")
    return a == b or a.endswith("." + b)
