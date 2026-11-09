"""Public job-board APIs of applicant tracking systems. One source row per employer board (config: {'token': ...})."""
import time

import httpx

from ..normalize.text import html_to_text
from .base import RawJob, adapter, get_json, number, parse_date


class BoardNotFound(Exception):
    pass


def _board_json(http, url, **kwargs):
    try:
        return get_json(http, url, **kwargs)
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 404:
            raise BoardNotFound(url) from error
        raise


@adapter("greenhouse")
def greenhouse(http, config):
    data = _board_json(http, f"https://boards-api.greenhouse.io/v1/boards/{config['token']}/jobs", params={"content": "true"})
    for j in data.get("jobs", []):
        location = (j.get("location") or {}).get("name")
        offices = j.get("offices") or []
        # Some employers put "Hybrid" in the location field and the real place on the office record.
        if offices and (not location or location.split(";")[0].strip().lower() in ("hybrid", "in-office", "distributed", "remote", "onsite", "on-site")):
            office = offices[0].get("location") or offices[0].get("name")
            location = f"{office} ({location})" if location and office else office or location
        yield RawJob(
            external_id=str(j["id"]), title=j["title"], company=config.get("company"), description=html_to_text(j.get("content")),
            location=location, workplace="hybrid" if location and "hybrid" in location.lower() else None, url=j.get("absolute_url"),
            posted_at=parse_date(j.get("first_published") or j.get("updated_at")),
        )


@adapter("lever")
def lever(http, config):
    data = _board_json(http, f"https://api.lever.co/v0/postings/{config['token']}", params={"mode": "json"})
    for j in data:
        categories = j.get("categories") or {}
        salary = j.get("salaryRange") or {}
        lists = "\n".join(f"{l.get('text', '')}\n{html_to_text(l.get('content'))}" for l in j.get("lists") or [])
        interval = (salary.get("interval") or "").lower()
        yield RawJob(
            external_id=j["id"], title=j["text"], company=config.get("company"),
            description="\n".join(filter(None, [j.get("descriptionPlain"), lists, j.get("additionalPlain")])),
            location=categories.get("location"), url=j.get("hostedUrl"), employment_type=categories.get("commitment"),
            workplace={"remote": "remote", "hybrid": "hybrid", "on-site": "onsite", "onsite": "onsite"}.get((j.get("workplaceType") or "").lower()),
            salary_min=number(salary.get("min")), salary_max=number(salary.get("max")), salary_currency=salary.get("currency"),
            salary_period="hour" if "hour" in interval else "month" if "month" in interval else "year",
            posted_at=parse_date(j.get("createdAt")),
        )


@adapter("ashby")
def ashby(http, config):
    data = _board_json(http, f"https://api.ashbyhq.com/posting-api/job-board/{config['token']}", params={"includeCompensation": "true"})
    for j in data.get("jobs", []):
        if not j.get("isListed", True):
            continue
        comp = next((c for c in ((j.get("compensation") or {}).get("summaryComponents") or []) if c.get("compensationType") == "Salary"), {})
        address = ((j.get("address") or {}).get("postalAddress") or {})
        location = ", ".join(filter(None, [address.get("addressLocality"), address.get("addressRegion"), address.get("addressCountry")])) or j.get("location")
        interval = (comp.get("interval") or "").upper()
        yield RawJob(
            external_id=j["id"], title=j["title"], company=config.get("company"), description=j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml")),
            location=location, remote=bool(j.get("isRemote")), url=j.get("jobUrl"), employment_type=j.get("employmentType"),
            workplace={"remote": "remote", "hybrid": "hybrid", "onsite": "onsite"}.get((j.get("workplaceType") or "").lower()),
            salary_min=number(comp.get("minValue")), salary_max=number(comp.get("maxValue")), salary_currency=comp.get("currencyCode"),
            salary_period="hour" if "HOUR" in interval else "month" if "MONTH" in interval else "year", posted_at=parse_date(j.get("publishedAt")),
        )


@adapter("smartrecruiters")
def smartrecruiters(http, config):
    token = config["token"]
    limit = 100
    detail_budget = int(config.get("max_details", 150))
    for offset in range(0, 3000, limit):
        data = _board_json(http, f"https://api.smartrecruiters.com/v1/companies/{token}/postings", params={"limit": limit, "offset": offset})
        rows = data.get("content") or []
        for j in rows:
            place = j.get("location") or {}
            description = ""
            if detail_budget > 0:  # the list omits descriptions, and each detail is one more request
                detail_budget -= 1
                detail = http.get(f"https://api.smartrecruiters.com/v1/companies/{token}/postings/{j['id']}")
                if detail.status_code == 200:
                    sections = ((detail.json().get("jobAd") or {}).get("sections") or {}).values()
                    description = html_to_text(" ".join(s.get("text", "") for s in sections if isinstance(s, dict)))
                time.sleep(0.3)
            yield RawJob(
                external_id=str(j["id"]), title=j["name"], company=(j.get("company") or {}).get("name") or config.get("company"),
                description=description, location=", ".join(filter(None, [place.get("city"), place.get("region")])) or None,
                country_code=(place.get("country") or "").upper() or None, remote=bool(place.get("remote")),
                url=f"https://jobs.smartrecruiters.com/{token}/{j['id']}", employment_type=(j.get("typeOfEmployment") or {}).get("label"),
                posted_at=parse_date(j.get("releasedDate")),
            )
        if len(rows) < limit:
            break


@adapter("workable")
def workable(http, config):
    data = _board_json(http, f"https://apply.workable.com/api/v1/widget/accounts/{config['token']}", params={"details": "true"})
    for j in data.get("jobs", []):
        yield RawJob(
            external_id=j.get("shortcode") or j["url"], title=j["title"], company=data.get("name") or config.get("company"),
            description=html_to_text(j.get("description")), location=", ".join(filter(None, [j.get("city"), j.get("state"), j.get("country")])) or None,
            remote=bool(j.get("telecommuting")), url=j.get("url"), employment_type=j.get("employment_type"), posted_at=parse_date(j.get("published_on")),
        )


@adapter("recruitee")
def recruitee(http, config):
    data = _board_json(http, f"https://{config['token']}.recruitee.com/api/offers/")
    for j in data.get("offers", []):
        yield RawJob(
            external_id=str(j["id"]), title=j["title"], company=j.get("company_name") or config.get("company"),
            description=html_to_text(f"{j.get('description', '')} {j.get('requirements', '')}"), location=j.get("location"),
            country_code=j.get("country_code") or None, remote=bool(j.get("remote")), url=j.get("careers_url"), posted_at=parse_date(j.get("published_at")),
        )
