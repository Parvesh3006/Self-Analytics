"""LangGraph crawl agent: plan -> fetch -> classify -> extract -> store, looping until the budget is spent."""
import re
from dataclasses import dataclass, field
from typing import TypedDict

import httpx
from bs4 import BeautifulSoup
from langgraph.graph import END, StateGraph
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import CrawlPage, Source, utcnow
from ..services.discovery import register_boards_from_links
from ..services.ingest import Ingestor
from .extract import DETAIL_HINT, JOB_URL, SKIP_URL, classify_page, jobpostings_from_html, llm_extract, rawjob_from_jsonld, same_site
from .fetcher import AccessBlocked, Page, PoliteFetcher, absolute_links, render_with_browser

LLM_PAGES_PER_RUN = 20
MAX_BROWSER_RENDERS = 25


class CrawlState(TypedDict, total=False):
    frontier: list[tuple[str, int]]
    current: tuple[str, int] | None
    page_type: str | None
    done: bool


@dataclass
class Ctx:
    db: Session
    source: Source
    ingestor: Ingestor
    fetcher: PoliteFetcher
    max_pages: int
    max_depth: int
    visited: set[str] = field(default_factory=set)
    pages: int = 0
    unchanged: int = 0
    errors: int = 0
    llm_used: int = 0
    renders: int = 0
    blocked: str | None = None
    page: Page | None = None


def _sitemap_job_urls(ctx: Ctx, limit: int) -> list[str]:
    found: list[str] = []
    queue = ctx.fetcher.sitemap_urls(ctx.source.url)[:4]
    while queue and len(found) < limit:
        sitemap = queue.pop(0)
        try:
            page = ctx.fetcher.get(sitemap)
        except (AccessBlocked, httpx.HTTPError):
            continue
        soup = BeautifulSoup(page.html, "xml")
        for loc in soup.find_all("loc"):
            url = loc.get_text(strip=True)
            if url.endswith(".xml") or ".xml?" in url:
                if re.search(r"job|career|vacanc|position", url, re.I) and len(queue) < 6:
                    queue.append(url)
            elif DETAIL_HINT.search(url) and same_site(url, ctx.source.url):
                found.append(url)
                if len(found) >= limit:
                    break
    return found


def build_graph(ctx: Ctx):
    def plan(state: CrawlState) -> CrawlState:
        seed = ctx.source.url
        if not ctx.fetcher.allowed(seed):
            ctx.blocked = "robots.txt disallows this site for crawlers"
            return {"frontier": [], "done": True}
        frontier = [(seed, 0)]
        frontier += [(u, 1) for u in _sitemap_job_urls(ctx, ctx.max_pages)]
        return {"frontier": frontier, "done": False}

    def fetch(state: CrawlState) -> CrawlState:
        frontier = list(state["frontier"])
        while frontier and ctx.pages < ctx.max_pages:
            url, depth = frontier.pop(0)
            if url in ctx.visited or SKIP_URL.search(url) or not same_site(url, ctx.source.url):
                continue
            ctx.visited.add(url)
            known = ctx.db.scalar(select(CrawlPage).where(CrawlPage.source_id == ctx.source.id, CrawlPage.url == url[:1500]))
            try:
                # Listing pages always refresh; a detail page unchanged since last crawl is skipped.
                conditional = known is not None and known.page_type == "detail"
                page = ctx.fetcher.get(url, known.etag if conditional else None, known.last_modified if conditional else None)
            except AccessBlocked as error:
                ctx.blocked = str(error)
                return {"frontier": [], "current": None, "done": True}
            except httpx.HTTPError:
                ctx.errors += 1
                continue
            ctx.pages += 1
            if page.not_modified or (known is not None and known.page_type == "detail" and known.content_hash == page.content_hash):
                ctx.unchanged += 1
                continue
            if len(BeautifulSoup(page.html, "lxml").get_text(strip=True)) < 400 and not jobpostings_from_html(page.html) and ctx.renders < MAX_BROWSER_RENDERS:
                # A nearly empty document usually means a JavaScript app, so ask the browser.
                rendered = render_with_browser(url)
                if rendered:
                    ctx.renders += 1
                    page.html, page.rendered = rendered, True
            ctx.page = page
            return {"frontier": frontier, "current": (url, depth), "done": False}
        return {"frontier": [], "current": None, "done": True}

    def classify(state: CrawlState) -> CrawlState:
        return {"page_type": classify_page(ctx.page.url, ctx.page.html)}

    def extract(state: CrawlState) -> CrawlState:
        page, kind = ctx.page, state["page_type"]
        if kind == "detail":
            postings = jobpostings_from_html(page.html)
            if postings:
                for posting in postings:
                    raw = rawjob_from_jsonld(posting, page.url)
                    if raw:
                        ctx.ingestor.add(raw)
            elif ctx.llm_used < LLM_PAGES_PER_RUN:
                ctx.llm_used += 1
                raw = llm_extract(page.url, page.html)
                if raw:
                    ctx.ingestor.add(raw)
        return {}

    def store(state: CrawlState) -> CrawlState:
        url, depth = state["current"]
        page, kind = ctx.page, state["page_type"]
        values = dict(source_id=ctx.source.id, url=url[:1500], etag=(page.etag or "")[:300] or None, last_modified=(page.last_modified or "")[:100] or None,
                      content_hash=page.content_hash, page_type=kind, fetched_at=utcnow())
        stmt = insert(CrawlPage).values(**values)
        ctx.db.execute(stmt.on_conflict_do_update(index_elements=["source_id", "url"], set_={k: v for k, v in values.items() if k not in ("source_id", "url")}))
        ctx.db.commit()
        frontier = list(state["frontier"])
        links = absolute_links(page.html, page.url)
        register_boards_from_links(ctx.db, links)
        if kind == "listing" and depth < ctx.max_depth:
            for link in links:
                if link not in ctx.visited and same_site(link, ctx.source.url) and not SKIP_URL.search(link) and JOB_URL.search(link):
                    frontier.append((link, depth + 1))
        return {"frontier": frontier}

    graph = StateGraph(CrawlState)
    for name, fn in [("plan", plan), ("fetch", fetch), ("classify", classify), ("extract", extract), ("store", store)]:
        graph.add_node(name, fn)
    graph.set_entry_point("plan")
    graph.add_conditional_edges("plan", lambda s: END if s.get("done") else "fetch")
    graph.add_conditional_edges("fetch", lambda s: END if s.get("done") else "classify")
    graph.add_edge("classify", "extract")
    graph.add_edge("extract", "store")
    graph.add_edge("store", "fetch")
    return graph.compile()


def crawl_source(db: Session, source: Source, ingestor: Ingestor) -> Ctx:
    settings = get_settings()
    config = source.config or {}
    fetcher = PoliteFetcher()
    ctx = Ctx(db=db, source=source, ingestor=ingestor, fetcher=fetcher,
              max_pages=int(config.get("max_pages", settings.crawl_max_pages)), max_depth=int(config.get("max_depth", settings.crawl_max_depth)))
    try:
        build_graph(ctx).invoke({"frontier": [], "current": None}, {"recursion_limit": ctx.max_pages * 6 + 20})
    finally:
        ingestor.finish()
        fetcher.close()
    return ctx
