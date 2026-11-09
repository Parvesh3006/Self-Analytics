"""Background work. Celery in Docker (TASK_MODE=celery); a thread when running natively on Windows, where Celery is unsupported."""
import logging
import os

from celery import Celery

from .config import get_settings
from .db import session_scope
from .models import Source
from .services.discovery import discover_boards
from .services.embeddings import embed_pending
from .services.ingest import delete_closed, delete_outside_markets, refresh_fx
from .services.sources import due_sources, probe_source, run_source

log = logging.getLogger(__name__)
celery = Celery("self_analytics", broker=get_settings().redis_url)
celery.conf.update(
    task_acks_late=True, worker_prefetch_multiplier=1, timezone="UTC",
    beat_schedule={
        # Overdue-based, so a laptop that slept catches up instead of missing a fixed time.
        "dispatch-due": {"task": "app.tasks.dispatch_due", "schedule": 1800.0},
        "embed": {"task": "app.tasks.embed_task", "schedule": 3600.0},
        "maintain": {"task": "app.tasks.maintain", "schedule": 86400.0},
        "discover": {"task": "app.tasks.discover", "schedule": 604800.0},
    },
)


def _run(source_id: int) -> None:
    with session_scope() as db:
        source = db.get(Source, source_id)
        if source:
            run_source(db, source)


def _probe(source_id: int, then_run: bool) -> None:
    from .crawl.fetcher import PoliteFetcher

    fetcher = PoliteFetcher(delay=0.5)
    try:
        with session_scope() as db:
            source = db.get(Source, source_id)
            if source is None:
                return
            probe_source(db, source, fetcher)
            if then_run and source.status != "blocked" and source.enabled:
                run_source(db, source)
    finally:
        fetcher.close()


@celery.task(name="app.tasks.run_source_task", time_limit=3 * 3600)
def run_source_task(source_id: int) -> None:
    _run(source_id)


@celery.task(name="app.tasks.probe_task", time_limit=900)
def probe_task(source_id: int, then_run: bool = False) -> None:
    _probe(source_id, then_run)


@celery.task(name="app.tasks.dispatch_due")
def dispatch_due() -> int:
    with session_scope() as db:
        ids = [s.id for s in due_sources(db)]
    for source_id in ids:
        run_source_task.delay(source_id)
    return len(ids)


@celery.task(name="app.tasks.embed_task", time_limit=3 * 3600)
def embed_task() -> int:
    with session_scope() as db:
        return embed_pending(db, limit=4000)


@celery.task(name="app.tasks.maintain")
def maintain() -> None:
    with session_scope() as db:
        refresh_fx(db)
        delete_closed(db)
        delete_outside_markets(db)


@celery.task(name="app.tasks.discover", time_limit=3600)
def discover() -> int:
    with session_scope() as db:
        return discover_boards(db)


def _celery_mode() -> bool:
    return os.environ.get("TASK_MODE", "thread") == "celery"


def enqueue_run(background, source_id: int) -> None:
    if _celery_mode():
        run_source_task.delay(source_id)
    else:
        background.add_task(_run, source_id)


def enqueue_probe(background, source_id: int, then_run: bool) -> None:
    if _celery_mode():
        probe_task.delay(source_id, then_run)
    else:
        background.add_task(_probe, source_id, then_run)
