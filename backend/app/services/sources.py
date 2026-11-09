"""Source registry: seeding, probing, running."""
import csv
import hashlib
import logging
import re
from datetime import timedelta
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..adapters import ADAPTERS, Blocked, NeedsKey, client
from ..adapters.ats import BoardNotFound
from ..config import get_settings
from ..crawl.extract import jobpostings_from_html, same_site
from ..crawl.fetcher import AccessBlocked, PoliteFetcher, absolute_links
from ..crawl.graph import crawl_source
from ..llm import LLMUnavailable, complete, embed
from ..models import CrawlRun, Insight, InsightChunk, JobSighting, Source, utcnow
from .discovery import add_board
from .ingest import Ingestor, merge_near_duplicates

log = logging.getLogger(__name__)

REASONS = {
    "blocked": "Terms prohibit automated collection, or the site is protected against bots. Not collected. Its jobs reach this app only through permitted aggregators.",
    "none": "Not a job feed: a resource, directory, or landing page.",
    "discover": "A platform, not a feed. Employer boards on it are found and collected individually.",
}
SCHEDULE = {"api": 24, "rss": 24, "jsonld": 168, "crawl": 168, "insight": 720}
INSIGHT_LINK = re.compile(r"report|statistic|labou?r|employment|skills?|trend|publication|outlook|shortage|vacanc|occupation|wage|data", re.I)


def seed_registry(db: Session) -> int:
    path = get_settings().data_dir / "sources" / "registry.txt"
    section, kind, default_region = "", "job_board", "Worldwide"
    count = 0
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            section, kind, default_region = line[1:-1].split("|")
            continue
        name, url, region, strategy, adapter = line.split("|")
        status = {"blocked": "blocked", "none": "reference", "discover": "reference"}.get(strategy, "new")
        stmt = insert(Source).values(
            name=name, url=url, domain=urlparse(url).netloc, section=section, kind=kind, region=region or default_region, strategy=strategy,
            adapter=adapter or None, config={}, status=status, status_reason=REASONS.get(strategy), enabled=strategy not in ("blocked", "none", "discover"),
            schedule_hours=SCHEDULE.get(strategy, 168), probe={}, jobs_total=0,
        )
        db.execute(stmt.on_conflict_do_update(index_elements=["url"], set_={"name": name, "section": section, "kind": kind, "region": region or default_region}))
        count += 1
    with (get_settings().data_dir / "sources" / "boards.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            add_board(db, row["ats"], row["token"], row["company"])
            count += 1
    db.commit()
    return count


def probe_source(db: Session, source: Source, fetcher: PoliteFetcher) -> None:
    """Decide how to collect a site: robots.txt, reachability, JSON-LD, RSS. Reads at most one page per site."""
    result: dict = {}
    source.probed_at = utcnow()
    try:
        if not fetcher.allowed(source.url):
            result["robots"] = "disallowed"
            source.strategy, source.status, source.enabled = "blocked", "blocked", False
            source.status_reason = "robots.txt disallows crawlers on this site."
        else:
            result["robots"] = "allowed"
            page = fetcher.get(source.url)
            postings = jobpostings_from_html(page.html)
            soup = BeautifulSoup(page.html, "lxml")
            feeds = [l.get("href") for l in soup.find_all("link", attrs={"type": re.compile("rss|atom")}) if re.search("job|career|vacanc", l.get("href", "") + l.get("title", ""), re.I)]
            links = absolute_links(page.html, page.url)
            job_links = [l for l in links if same_site(l, source.url) and re.search(r"/jobs?|/career|/vacanc|/position", l, re.I)]
            text_size = len(soup.get_text(strip=True))
            result.update(jsonld=len(postings), feeds=feeds[:3], job_links=len(job_links), text_size=text_size, final_url=page.url)
            if feeds:
                feed = httpx.URL(page.url).join(feeds[0])
                source.strategy, source.adapter, source.config = "api", "rss", {**(source.config or {}), "feed_url": str(feed)}
                source.schedule_hours = 24
                source.status_reason = "Collected from its public RSS feed."
            elif postings:
                source.strategy, source.schedule_hours = "jsonld", 168
                source.status_reason = "Pages expose structured job data."
            else:
                source.strategy, source.schedule_hours = "crawl", 168
                source.status_reason = "Polite crawl within robots.txt."
            source.status = "new"
            source.enabled = True
    except AccessBlocked as error:
        result["blocked"] = str(error)
        source.strategy, source.status, source.enabled = "blocked", "blocked", False
        source.status_reason = f"{error}. Not collected."
    except httpx.HTTPError as error:
        result["error"] = str(error)[:300]
        source.status, source.enabled = "error", False
        source.status_reason = "Site could not be reached. It may have closed or moved."
    source.probe = result
    db.commit()


def _finish(db: Session, source: Source, run: CrawlRun, status: str, message: str | None = None) -> CrawlRun:
    run.status, run.finished_at, run.message = status, utcnow(), message
    source.last_run_at = run.finished_at
    if status in ("ok", "partial"):
        source.last_success_at = run.finished_at
    source.jobs_total = db.scalar(select(func.count(func.distinct(JobSighting.job_id))).where(JobSighting.source_id == source.id)) or 0
    db.commit()
    return run


def run_source(db: Session, source: Source) -> CrawlRun:
    run = CrawlRun(source_id=source.id, status="running")
    db.add(run)
    db.commit()
    log.info("Running %s (%s)", source.name, source.strategy)
    try:
        if source.strategy == "api":
            return _run_adapter(db, source, run)
        if source.strategy in ("auto", "crawl", "jsonld"):
            return _run_crawl(db, source, run)
        if source.strategy == "insight":
            return _run_insight(db, source, run)
        return _finish(db, source, run, "skipped", "This source is not collected.")
    except Exception as error:  # a broken source must never stop the others
        db.rollback()
        log.exception("Source %s failed", source.name)
        source.status, source.status_reason = "error", f"{type(error).__name__}: {error}"[:400]
        return _finish(db, source, run, "error", str(error)[:800])


def _run_adapter(db: Session, source: Source, run: CrawlRun) -> CrawlRun:
    ingestor = Ingestor(db, source)
    try:
        with client() as http:
            for raw in ADAPTERS[source.adapter](http, source.config or {}):
                ingestor.add(raw)
    except NeedsKey as error:
        db.rollback()
        source.status, source.status_reason = "needs_key", f"Add {error} to .env to collect this source."
        return _finish(db, source, run, "skipped", source.status_reason)
    except Blocked as error:
        ingestor.finish()
        source.status, source.status_reason = "blocked", f"{error}. Collection stopped."
        run.seen, run.new, run.updated = ingestor.seen, ingestor.new, ingestor.updated
        return _finish(db, source, run, "error", source.status_reason)
    except BoardNotFound:
        db.rollback()
        source.status, source.enabled, source.status_reason = "error", False, "This employer board no longer exists."
        return _finish(db, source, run, "error", source.status_reason)
    ingestor.finish()
    run.pages, run.seen, run.new, run.updated = 1, ingestor.seen, ingestor.new, ingestor.updated
    source.status, source.status_reason = "active", None
    merge_near_duplicates(db, run.started_at)
    return _finish(db, source, run, "ok", f"{ingestor.seen} postings read, {ingestor.new} new.")


def _run_crawl(db: Session, source: Source, run: CrawlRun) -> CrawlRun:
    ingestor = Ingestor(db, source)
    ctx = crawl_source(db, source, ingestor)
    run.pages, run.seen, run.new, run.updated = ctx.pages, ingestor.seen, ingestor.new, ingestor.updated
    if ctx.blocked:
        source.strategy, source.status, source.enabled, source.status_reason = "blocked", "blocked", False, f"{ctx.blocked}. Collection stopped."
        return _finish(db, source, run, "error", source.status_reason)
    if ctx.pages == 0:
        source.status, source.status_reason = "error", "No pages could be fetched."
        return _finish(db, source, run, "error", source.status_reason)
    source.status = "active"
    source.status_reason = None if ingestor.seen else "Reachable, but no job postings could be read from its pages yet."
    merge_near_duplicates(db, run.started_at)
    message = f"{ctx.pages} pages, {ctx.unchanged} unchanged, {ingestor.seen} postings, {ingestor.new} new."
    return _finish(db, source, run, "partial" if ctx.errors else "ok", message)


def _chunks(body: str, size: int = 1200, overlap: int = 150) -> list[str]:
    return [body[i:i + size] for i in range(0, min(len(body), 24000), size - overlap)]


def _run_insight(db: Session, source: Source, run: CrawlRun) -> CrawlRun:
    """Trend and statistics pages become summaries for the assistant. They are never counted as vacancies."""
    fetcher = PoliteFetcher()
    frontier, seen, saved, pages = [source.url], set(), 0, 0
    max_pages = int((source.config or {}).get("max_pages", 12))
    try:
        while frontier and pages < max_pages:
            url = frontier.pop(0)
            if url in seen:
                continue
            seen.add(url)
            try:
                page = fetcher.get(url)
            except AccessBlocked as error:
                if pages == 0:
                    source.strategy, source.status, source.enabled, source.status_reason = "blocked", "blocked", False, f"{error}. Not collected."
                    return _finish(db, source, run, "error", source.status_reason)
                break
            except httpx.HTTPError:
                continue
            pages += 1
            soup = BeautifulSoup(page.html, "lxml")
            for link in absolute_links(page.html, page.url):
                if same_site(link, source.url) and INSIGHT_LINK.search(link) and not re.search(r"\.(pdf|xlsx?|zip|png|jpg)", link, re.I) and len(frontier) < 60:
                    frontier.append(link)
            for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "form", "aside"]):
                tag.decompose()
            body = re.sub(r"\n{2,}", "\n", (soup.find("main") or soup.body or soup).get_text("\n", strip=True))
            if len(body) < 900:
                continue
            digest = hashlib.sha256(body.encode()).hexdigest()
            existing = db.scalar(select(Insight).where(Insight.url == page.url[:1500]))
            if existing and existing.content_hash == digest:
                continue
            title = (soup.title.get_text(strip=True) if soup.title else source.name)[:500]
            try:
                summary = complete("Summarise the labour-market facts on this page in at most 120 words. Keep figures, dates and places exactly. "
                                   "State only what the text says.\n\n" + body[:6000])
            except (LLMUnavailable, httpx.HTTPError):
                summary = body[:700]
            if existing:
                db.delete(existing)
                db.flush()
            insight = Insight(source_id=source.id, url=page.url[:1500], title=title, summary=summary, region=source.region, content_hash=digest)
            db.add(insight)
            db.flush()
            pieces = _chunks(body)
            vectors = embed(pieces)
            db.add_all(InsightChunk(insight_id=insight.id, text=p, embedding=vectors[i] if vectors else None) for i, p in enumerate(pieces))
            db.commit()
            saved += 1
    finally:
        fetcher.close()
    run.pages, run.seen, run.new = pages, saved, saved
    source.status, source.status_reason = "active", None
    return _finish(db, source, run, "ok", f"{pages} pages read, {saved} reports stored or updated.")


def due_sources(db: Session) -> list[Source]:
    """Overdue rather than clock-bound: a laptop that was asleep catches up when it wakes."""
    rows = db.scalars(select(Source).where(Source.enabled.is_(True), Source.status.notin_(["blocked", "reference", "needs_key"]))).all()
    now = utcnow()
    return [s for s in rows if s.last_run_at is None or s.last_run_at + timedelta(hours=s.schedule_hours) <= now]


def source_counts(db: Session) -> dict:
    return dict(db.execute(text("SELECT status, count(*) FROM sources GROUP BY status")).all())
