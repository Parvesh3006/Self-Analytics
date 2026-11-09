"""Sources with a public API or feed that needs no key."""
import re
import time

from bs4 import BeautifulSoup

from ..normalize.text import html_to_text
from .base import RawJob, adapter, get_json, number, parse_date


@adapter("remotive")
def remotive(http, config):
    # Remotive asks for no more than a few requests a day; one full fetch per scheduled run.
    for j in get_json(http, "https://remotive.com/api/remote-jobs")["jobs"]:
        yield RawJob(
            external_id=str(j["id"]), title=j["title"], company=j.get("company_name"),
            description=html_to_text(j.get("description")), location=j.get("candidate_required_location"), remote=True,
            url=j.get("url"), employment_type=j.get("job_type"), salary_text=j.get("salary") or None,
            posted_at=parse_date(j.get("publication_date")), tags=j.get("tags") or [],
        )


@adapter("remoteok")
def remoteok(http, config):
    for j in get_json(http, "https://remoteok.com/api"):
        if "id" not in j:  # first element is the legal notice
            continue
        yield RawJob(
            external_id=str(j["id"]), title=j.get("position") or "", company=j.get("company"),
            description=html_to_text(j.get("description")), location=j.get("location") or None, remote=True,
            url=j.get("url"), salary_min=number(j.get("salary_min")), salary_max=number(j.get("salary_max")),
            salary_currency="USD" if number(j.get("salary_min")) else None, salary_period="year",
            posted_at=parse_date(j.get("date")), tags=j.get("tags") or [],
        )


@adapter("arbeitnow")
def arbeitnow(http, config):
    url = "https://www.arbeitnow.com/api/job-board-api"
    for _ in range(int(config.get("max_pages", 15))):
        data = get_json(http, url)
        for j in data["data"]:
            yield RawJob(
                external_id=j["slug"], title=j["title"], company=j.get("company_name"),
                description=html_to_text(j.get("description")), location=j.get("location"), remote=bool(j.get("remote")),
                url=j.get("url"), employment_type=", ".join(j.get("job_types") or []) or None,
                posted_at=parse_date(j.get("created_at")), tags=j.get("tags") or [],
            )
        url = (data.get("links") or {}).get("next")
        if not url:
            break
        time.sleep(1.5)


@adapter("himalayas")
def himalayas(http, config):
    offset = 0
    limit = 20
    for _ in range(int(config.get("max_pages", 60))):
        data = get_json(http, "https://himalayas.app/jobs/api", params={"limit": limit, "offset": offset})
        jobs = data.get("jobs") or []
        for j in jobs:
            restrictions = j.get("locationRestrictions") or []
            yield RawJob(
                external_id=str(j.get("guid") or j.get("applicationLink")), title=j["title"], company=j.get("companyName"),
                description=html_to_text(j.get("description") or j.get("excerpt")),
                location=", ".join(restrictions[:1]) or "Worldwide", remote=True, url=j.get("applicationLink"),
                employment_type=j.get("employmentType"), salary_min=number(j.get("minSalary")),
                salary_max=number(j.get("maxSalary")), salary_currency=j.get("currency") or None, salary_period="year",
                posted_at=parse_date(j.get("pubDate")), valid_through=parse_date(j.get("expiryDate")),
                tags=j.get("categories") or [],
            )
        if len(jobs) < limit:
            break
        offset += limit
        time.sleep(1.2)


@adapter("jobicy")
def jobicy(http, config):
    for j in get_json(http, "https://jobicy.com/api/v2/remote-jobs", params={"count": 100})["jobs"]:
        yield RawJob(
            external_id=str(j["id"]), title=j["jobTitle"], company=j.get("companyName"),
            description=html_to_text(j.get("jobDescription")), location=j.get("jobGeo"), remote=True, url=j.get("url"),
            employment_type=", ".join(j["jobType"]) if isinstance(j.get("jobType"), list) else j.get("jobType"),
            salary_min=number(j.get("annualSalaryMin")), salary_max=number(j.get("annualSalaryMax")),
            salary_currency=j.get("salaryCurrency") or None, salary_period="year", posted_at=parse_date(j.get("pubDate")),
        )


@adapter("muse")
def muse(http, config):
    for page in range(1, int(config.get("max_pages", 20)) + 1):
        data = get_json(http, "https://www.themuse.com/api/public/jobs", params={"page": page})
        for j in data.get("results", []):
            locations = [l["name"] for l in j.get("locations") or []]
            yield RawJob(
                external_id=str(j["id"]), title=j["name"], company=(j.get("company") or {}).get("name"),
                description=html_to_text(j.get("contents")), location=locations[0] if locations else None,
                remote=any("remote" in l.lower() or "flexible" in l.lower() for l in locations),
                url=(j.get("refs") or {}).get("landing_page"), posted_at=parse_date(j.get("publication_date")),
            )
        if page >= int(data.get("page_count") or 0):
            break
        time.sleep(1.0)


@adapter("workingnomads")
def workingnomads(http, config):
    for j in get_json(http, "https://www.workingnomads.com/api/exposed_jobs/"):
        yield RawJob(
            external_id=j["url"], title=j["title"], company=j.get("company_name"),
            description=html_to_text(j.get("description")), location=j.get("location"), remote=True, url=j["url"],
            posted_at=parse_date(j.get("pub_date")),
            tags=[t.strip() for t in (j.get("tags") or "").split(",") if t.strip()],
        )


@adapter("getonbrd")
def getonbrd(http, config):
    categories = [c["id"] for c in get_json(http, "https://www.getonbrd.com/api/v0/categories")["data"]]
    for category in categories:
        for page in range(1, 11):
            data = get_json(http, f"https://www.getonbrd.com/api/v0/categories/{category}/jobs",
                            params={"per_page": 100, "page": page, "expand": '["company"]'})
            for j in data["data"]:
                a = j["attributes"]
                company = ((a.get("company") or {}).get("data") or {}).get("attributes") or {}
                countries = a.get("countries") or []
                yield RawJob(
                    external_id=str(j["id"]), title=a["title"], company=company.get("name"),
                    description=html_to_text(" ".join(filter(None, [a.get("description"), a.get("functions"), a.get("desirable")]))),
                    location=", ".join(countries[:1]) or None, remote=bool(a.get("remote")),
                    url=(j.get("links") or {}).get("public_url"), salary_min=number(a.get("min_salary")),
                    salary_max=number(a.get("max_salary")), salary_currency="USD" if number(a.get("min_salary")) else None,
                    salary_period="month", posted_at=parse_date(a.get("published_at")),
                )
            if page >= int((data.get("meta") or {}).get("total_pages") or 0):
                break
            time.sleep(0.6)


@adapter("mycareersfuture")
def mycareersfuture(http, config):
    for page in range(int(config.get("max_pages", 30))):
        data = get_json(http, "https://api.mycareersfuture.gov.sg/v2/jobs", params={"limit": 100, "page": page})
        results = data.get("results") or []
        for j in results:
            salary = j.get("salary") or {}
            meta = j.get("metadata") or {}
            address = j.get("address") or {}
            districts = address.get("districts") or []
            yield RawJob(
                external_id=j["uuid"], title=j["title"], company=(j.get("postedCompany") or {}).get("name"),
                description=html_to_text(j.get("description")), country_code="SG",
                location=(districts[0].get("region") if districts else None) or "Singapore",
                url=meta.get("jobDetailsUrl"), salary_min=number(salary.get("minimum")), salary_max=number(salary.get("maximum")),
                salary_currency="SGD" if number(salary.get("minimum")) else None,
                salary_period="month" if ((salary.get("type") or {}).get("salaryType") or "Monthly") == "Monthly" else "year",
                posted_at=parse_date(meta.get("newPostingDate")), valid_through=parse_date(meta.get("expiryDate")),
                employment_type=", ".join(e.get("employmentType", "") for e in j.get("employmentTypes") or []) or None,
                tags=[s["skill"] for s in j.get("skills") or [] if s.get("skill")],
            )
        if len(results) < 100:
            break
        time.sleep(1.5)


@adapter("arbeitsagentur")
def arbeitsagentur(http, config):
    # Documented at jobsuche.api.bund.dev; the key below is the service's published client id.
    headers = {"X-API-Key": "jobboerse-jobsuche"}
    terms = config.get("terms") or ["Informatik", "Softwareentwickler", "Data", "IT-Administrator", "Ingenieur"]
    for term in terms:
        for page in range(1, int(config.get("max_pages", 10)) + 1):
            data = get_json(http, "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs", headers=headers,
                            params={"angebotsart": 1, "page": page, "size": 100, "was": term})
            rows = data.get("stellenangebote") or []
            for j in rows:
                place = j.get("arbeitsort") or {}
                yield RawJob(
                    external_id=j["refnr"], title=j.get("titel") or j.get("beruf") or "", company=j.get("arbeitgeber"),
                    description=j.get("beruf") or "", location=", ".join(filter(None, [place.get("ort"), place.get("region")])),
                    country_code="DE", url=f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{j['refnr']}",
                    posted_at=parse_date(j.get("aktuelleVeroeffentlichungsdatum")),
                )
            if len(rows) < 100:
                break
            time.sleep(1.0)


_HN_SPLIT = re.compile(r"\s*\|\s*")


@adapter("hn_hiring")
def hn_hiring(http, config):
    stories = get_json(http, "https://hn.algolia.com/api/v1/search_by_date",
                       params={"tags": "story,author_whoishiring", "query": "who is hiring", "hitsPerPage": 5})["hits"]
    story = next((s for s in stories if "who is hiring" in s["title"].lower()), None)
    if story is None:
        return
    thread = get_json(http, f"https://hn.algolia.com/api/v1/items/{story['objectID']}")
    for comment in thread.get("children") or []:
        if not comment.get("text"):
            continue
        body = html_to_text(comment["text"])
        first = body.split("\n", 1)[0]
        parts = _HN_SPLIT.split(first)
        # A real posting opens with pipe-separated fields; anything else is discussion and is not a vacancy.
        if len(parts) < 3:
            continue
        location = next((p for p in parts[1:] if re.search(r"remote|onsite|on-site|hybrid|,", p, re.I)), None)
        role = next((p for p in parts[1:] if p != location and re.search(r"engineer|developer|scientist|manager|designer|analyst|lead|founding|sre|devops", p, re.I)), None)
        if not role:
            continue
        yield RawJob(
            external_id=str(comment["id"]), title=role[:300], company=parts[0][:200], description=body, location=location,
            remote=bool(location and re.search("remote", location, re.I)),
            url=f"https://news.ycombinator.com/item?id={comment['id']}", posted_at=parse_date(comment.get("created_at")),
            salary_text=first,
        )


def _rss(http, url: str):
    response = http.get(url)
    response.raise_for_status()
    return BeautifulSoup(response.content, "xml").find_all("item")


@adapter("rss")
def rss(http, config):
    """Generic RSS job feed. Titles are often 'Company: Role'."""
    for item in _rss(http, config["feed_url"]):
        title = item.title.get_text(strip=True) if item.title else ""
        company = None
        if ": " in title:
            company, title = title.split(": ", 1)
        region = item.find("region")
        link = item.link.get_text(strip=True) if item.link else None
        guid = item.guid.get_text(strip=True) if item.guid else link
        pub = item.pubDate.get_text(strip=True) if item.pubDate else None
        yield RawJob(
            external_id=guid or title, title=title, company=company,
            description=html_to_text(item.description.get_text() if item.description else ""),
            location=region.get_text(strip=True) if region else config.get("default_location"),
            remote=config.get("remote"), url=link, posted_at=parse_date(pub),
        )


@adapter("weworkremotely")
def weworkremotely(http, config):
    yield from rss(http, {"feed_url": "https://weworkremotely.com/remote-jobs.rss", "remote": True, "default_location": "Worldwide"})


@adapter("pythonjobs")
def pythonjobs(http, config):
    for item in _rss(http, "https://www.python.org/jobs/feed/rss/"):
        title = item.title.get_text(strip=True)
        # Format: "Role, Company, Location"
        parts = [p.strip() for p in title.split(",")]
        link = item.link.get_text(strip=True)
        yield RawJob(
            external_id=link, title=parts[0], company=parts[1] if len(parts) > 1 else None,
            location=", ".join(parts[2:]) or None, url=link,
            description=html_to_text(item.description.get_text() if item.description else ""),
            posted_at=parse_date(item.pubDate.get_text(strip=True) if item.pubDate else None), tags=["Python"],
        )
