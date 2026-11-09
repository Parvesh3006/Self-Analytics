"""Operator commands. Run from backend/: python -m app.cli <command>"""
import argparse
import concurrent.futures as cf
import logging

from sqlalchemy import func, select

from .crawl.fetcher import PoliteFetcher
from .db import SessionLocal, session_scope
from .models import GeoPlace, Source
from .normalize.geo import load_geonames
from .services.discovery import discover_boards
from .services.embeddings import embed_pending
from .services.ingest import expire_stale, refresh_fx, sync_skills
from .services.sources import due_sources, probe_source, run_source, seed_registry


def bootstrap() -> None:
    with session_scope() as db:
        sync_skills(db)
        print("sources seeded:", seed_registry(db))
        try:
            print("fx currencies:", refresh_fx(db))
        except Exception as error:
            print("fx refresh failed:", error)
        if not db.scalar(select(func.count()).select_from(GeoPlace)):
            print("places loaded:", load_geonames(db))


def _probe_one(source_id: int) -> str:
    fetcher = PoliteFetcher(delay=0.2)
    db = SessionLocal()
    try:
        source = db.get(Source, source_id)
        probe_source(db, source, fetcher)
        return f"{source.name}: {source.strategy}/{source.status}"
    finally:
        fetcher.close()
        db.close()


def probe_all(only_new: bool) -> None:
    with session_scope() as db:
        stmt = select(Source.id).where(Source.strategy.in_(["auto", "crawl", "jsonld"] if not only_new else ["auto"]))
        ids = list(db.scalars(stmt))
    print(f"probing {len(ids)} sources")
    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        for line in pool.map(_probe_one, ids):
            print(line, flush=True)


def run(selector: str, limit: int | None) -> None:
    with session_scope() as db:
        if selector == "due":
            sources = due_sources(db)
        elif selector in ("api", "insight", "crawl", "jsonld"):
            sources = [s for s in due_sources(db) if s.strategy == selector]
        else:
            sources = list(db.scalars(select(Source).where(Source.name.ilike(f"%{selector}%"))))
        for source in sources[:limit]:
            result = run_source(db, source)
            print(f"{source.name}: {result.status} seen={result.seen} new={result.new} {result.message or ''}"[:200], flush=True)


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("bootstrap")
    probe = sub.add_parser("probe")
    probe.add_argument("--only-new", action="store_true")
    run_cmd = sub.add_parser("run")
    run_cmd.add_argument("selector", help="due, api, crawl, jsonld, insight, or part of a source name")
    run_cmd.add_argument("--limit", type=int)
    embed_cmd = sub.add_parser("embed")
    embed_cmd.add_argument("--limit", type=int, default=2000)
    sub.add_parser("discover")
    sub.add_parser("maintain")
    args = parser.parse_args()
    if args.command == "bootstrap":
        bootstrap()
    elif args.command == "probe":
        probe_all(args.only_new)
    elif args.command == "run":
        run(args.selector, args.limit)
    elif args.command == "embed":
        with session_scope() as db:
            print("embedded", embed_pending(db, limit=args.limit))
    elif args.command == "discover":
        with session_scope() as db:
            print("boards found", discover_boards(db))
    elif args.command == "maintain":
        with session_scope() as db:
            refresh_fx(db)
            print("expired", expire_stale(db))


if __name__ == "__main__":
    main()
