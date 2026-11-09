from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

import httpx

from ..config import get_settings


@dataclass
class RawJob:
    external_id: str
    title: str
    company: str | None = None
    description: str = ""  # plain text
    location: str | None = None
    country_code: str | None = None
    url: str | None = None
    remote: bool | None = None
    workplace: str | None = None
    employment_type: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    salary_period: str | None = None
    salary_text: str | None = None
    posted_at: datetime | None = None
    valid_through: datetime | None = None
    tags: list[str] = field(default_factory=list)


class NeedsKey(Exception):
    """The adapter requires an API key that is not configured."""


class Blocked(Exception):
    """The source refused automated access. It is flagged and not retried until re-probed."""


Fetch = Callable[[httpx.Client, dict], Iterator[RawJob]]
ADAPTERS: dict[str, Fetch] = {}


def adapter(name: str):
    def register(fn: Fetch) -> Fetch:
        ADAPTERS[name] = fn
        return fn
    return register


def client() -> httpx.Client:
    return httpx.Client(
        timeout=httpx.Timeout(45, connect=15), follow_redirects=True,
        headers={"User-Agent": get_settings().user_agent, "Accept": "application/json, */*"},
    )


def get_json(http: httpx.Client, url: str, **kwargs):
    response = http.get(url, **kwargs)
    if response.status_code in (401, 403, 429):
        raise Blocked(f"{response.status_code} from {httpx.URL(url).host}")
    response.raise_for_status()
    return response.json()


def parse_date(value) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        # Accept seconds or milliseconds since epoch.
        seconds = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        from email.utils import parsedate_to_datetime

        try:
            parsed = parsedate_to_datetime(text)
        except (TypeError, ValueError):
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def number(value) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None
