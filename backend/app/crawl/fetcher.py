"""Polite fetching: robots.txt honoured, per-host delay, conditional requests. Never bypasses bot protection."""
import hashlib
import re
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx
from protego import Protego

from ..config import get_settings

WALL_MARKERS = re.compile(
    r"cf-browser-verification|challenge-platform|just a moment\.\.\.|attention required! \| cloudflare|g-recaptcha|h-captcha|"
    r"px-captcha|datadome|verify you are (a )?human|are you a robot|access denied|unusual traffic|perimeterx", re.I)


class AccessBlocked(Exception):
    """robots.txt disallows the URL, the site answered 401/403/429, or it served a bot challenge."""


@dataclass
class Page:
    url: str
    status: int
    html: str
    etag: str | None
    last_modified: str | None
    content_hash: str
    not_modified: bool = False
    rendered: bool = False


class PoliteFetcher:
    def __init__(self, delay: float | None = None):
        self.settings = get_settings()
        self.ua = self.settings.user_agent
        self.client = httpx.Client(timeout=httpx.Timeout(30, connect=12), follow_redirects=True,
                                   headers={"User-Agent": self.ua, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8", "Accept-Language": "en"})
        self.delay = delay if delay is not None else self.settings.crawl_delay_seconds
        self.robots: dict[str, Protego | None] = {}
        self.sitemaps: dict[str, list[str]] = {}
        self.last_hit: dict[str, float] = {}

    def close(self) -> None:
        self.client.close()

    def _rules(self, url: str) -> Protego | None:
        parts = urlparse(url)
        host = f"{parts.scheme}://{parts.netloc}"
        if host not in self.robots:
            rules = None
            try:
                response = self.client.get(f"{host}/robots.txt")
                if response.status_code == 200 and "<html" not in response.text[:300].lower():
                    rules = Protego.parse(response.text)
                    self.sitemaps[host] = list(rules.sitemaps)
                elif response.status_code in (401, 403):
                    # Refusing robots.txt itself is treated as refusing the crawler.
                    self.robots[host] = Protego.parse("User-agent: *\nDisallow: /")
                    return self.robots[host]
            except httpx.HTTPError:
                rules = None
            self.robots[host] = rules
        return self.robots[host]

    def allowed(self, url: str) -> bool:
        rules = self._rules(url)
        return rules is None or rules.can_fetch(url, self.ua)

    def sitemap_urls(self, url: str) -> list[str]:
        parts = urlparse(url)
        host = f"{parts.scheme}://{parts.netloc}"
        self._rules(url)
        return self.sitemaps.get(host, [])

    def _wait(self, url: str) -> None:
        host = urlparse(url).netloc
        rules = self.robots.get(f"{urlparse(url).scheme}://{host}")
        pause = max(self.delay, (rules.crawl_delay(self.ua) or 0) if rules else 0)
        elapsed = time.monotonic() - self.last_hit.get(host, 0)
        if elapsed < pause:
            time.sleep(pause - elapsed)
        self.last_hit[host] = time.monotonic()

    def get(self, url: str, etag: str | None = None, last_modified: str | None = None) -> Page:
        if not self.allowed(url):
            raise AccessBlocked("robots.txt disallows this page")
        self._wait(url)
        headers = {}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        response = self.client.get(url, headers=headers)
        if response.status_code in (401, 403, 429):
            raise AccessBlocked(f"Site returned HTTP {response.status_code}")
        if response.status_code == 304:
            return Page(str(response.url), 304, "", etag, last_modified, "", not_modified=True)
        response.raise_for_status()
        body = response.text
        if WALL_MARKERS.search(body[:6000]) and len(body) < 60000:
            raise AccessBlocked("Site served a bot challenge")
        return Page(str(response.url), response.status_code, body, response.headers.get("etag"), response.headers.get("last-modified"),
                    hashlib.sha256(body.encode("utf-8", "ignore")).hexdigest())


def render_with_browser(url: str) -> str | None:
    """Render a JavaScript page with Crawl4AI (Playwright), available in the worker image. Returns None if not installed."""
    try:
        import asyncio

        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
    except ImportError:
        return None

    async def run() -> str | None:
        browser = BrowserConfig(headless=True, user_agent=get_settings().user_agent, text_mode=True, light_mode=True)
        async with AsyncWebCrawler(config=browser) as crawler:
            result = await crawler.arun(url, config=CrawlerRunConfig(page_timeout=30000, check_robots_txt=True))
            return result.html if result.success else None

    return asyncio.run(run())


def absolute_links(html: str, base: str) -> list[str]:
    links = []
    for href in re.findall(r"""href=["']([^"'#]+)""", html):
        if href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        links.append(urljoin(base, href))
    return list(dict.fromkeys(links))
