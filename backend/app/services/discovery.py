"""Find employer boards on public ATS platforms, from crawled links and permitted search APIs."""
import re
from urllib.parse import urlparse

import httpx
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Source

ATS_PATTERNS = [
    ("greenhouse", re.compile(r"https?://(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/([a-zA-Z0-9_-]+)")),
    ("lever", re.compile(r"https?://jobs(?:\.eu)?\.lever\.co/([a-zA-Z0-9_.-]+)")),
    ("ashby", re.compile(r"https?://jobs\.ashbyhq\.com/([a-zA-Z0-9_.%-]+)")),
    ("workable", re.compile(r"https?://apply\.workable\.com/([a-zA-Z0-9_-]+)")),
    ("smartrecruiters", re.compile(r"https?://(?:jobs|careers)\.smartrecruiters\.com/([a-zA-Z0-9_-]+)")),
    ("recruitee", re.compile(r"https?://([a-zA-Z0-9-]+)\.recruitee\.com")),
]
IGNORED_TOKENS = {"embed", "api", "v1", "jobs", "www", "careers", "static"}
BOARD_URLS = {
    "greenhouse": "https://boards.greenhouse.io/{}", "lever": "https://jobs.lever.co/{}", "ashby": "https://jobs.ashbyhq.com/{}",
    "workable": "https://apply.workable.com/{}", "smartrecruiters": "https://jobs.smartrecruiters.com/{}", "recruitee": "https://{}.recruitee.com",
}
ATS_LABEL = {"greenhouse": "Greenhouse", "lever": "Lever", "ashby": "Ashby", "workable": "Workable", "smartrecruiters": "SmartRecruiters", "recruitee": "Recruitee"}


def add_board(db: Session, ats: str, token: str, company: str | None = None) -> None:
    url = BOARD_URLS[ats].format(token)
    label = company or token.replace("-", " ").replace("_", " ").title()
    db.execute(insert(Source).values(
        name=f"{label} ({ATS_LABEL[ats]})", url=url, domain=urlparse(url).netloc, section="Company boards", kind="employer", region="Worldwide",
        strategy="api", adapter=ats, config={"token": token, "company": label}, status="new", enabled=True, schedule_hours=24, probe={}, jobs_total=0,
    ).on_conflict_do_nothing(index_elements=["url"]))


def boards_in(urls: list[str]) -> set[tuple[str, str]]:
    found = set()
    for url in urls:
        for ats, pattern in ATS_PATTERNS:
            match = pattern.match(url)
            if match and match.group(1).lower() not in IGNORED_TOKENS:
                found.add((ats, match.group(1)))
    return found


def register_boards_from_links(db: Session, links: list[str]) -> int:
    boards = boards_in(links)
    for ats, token in boards:
        add_board(db, ats, token)
    if boards:
        db.commit()
    return len(boards)


def _search(query: str) -> list[dict]:
    """Search through whichever permitted provider is configured. Returns [{'url', 'title', 'snippet'}]."""
    s = get_settings()
    if s.brave_api_key:
        data = httpx.get("https://api.search.brave.com/res/v1/web/search", params={"q": query, "count": 20},
                         headers={"X-Subscription-Token": s.brave_api_key, "Accept": "application/json"}, timeout=30).raise_for_status().json()
        return [{"url": r["url"], "title": r.get("title", ""), "snippet": r.get("description", "")} for r in data.get("web", {}).get("results", [])]
    if s.tavily_api_key:
        data = httpx.post("https://api.tavily.com/search", json={"query": query, "max_results": 20},
                          headers={"Authorization": f"Bearer {s.tavily_api_key}"}, timeout=30).raise_for_status().json()
        return [{"url": r["url"], "title": r.get("title", ""), "snippet": r.get("content", "")} for r in data.get("results", [])]
    if s.searxng_url:
        data = httpx.get(f"{s.searxng_url}/search", params={"q": query, "format": "json"}, timeout=30).raise_for_status().json()
        return [{"url": r["url"], "title": r.get("title", ""), "snippet": r.get("content", "")} for r in data.get("results", [])]
    return []


def search_available() -> bool:
    s = get_settings()
    return bool(s.brave_api_key or s.tavily_api_key or s.searxng_url)


DISCOVERY_MARKETS = ["Australia", "Canada", "India", "United Kingdom", "Ireland", "Singapore", "New Zealand", "Germany", "Netherlands", "United States"]
ATS_SITES = ["boards.greenhouse.io", "job-boards.greenhouse.io", "jobs.lever.co", "jobs.ashbyhq.com"]


def discover_boards(db: Session) -> int:
    """Search for employer boards in priority markets. Results become ordinary sources."""
    if not search_available():
        return 0
    found = 0
    for market in DISCOVERY_MARKETS:
        for site in ATS_SITES:
            try:
                results = _search(f"site:{site} software engineer {market}")
            except httpx.HTTPError:
                continue
            found += register_boards_from_links(db, [r["url"] for r in results])
    return found
