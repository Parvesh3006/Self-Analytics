import json
import logging
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import SessionLocal, get_db
from ..filters import Filters, filters_dep
from ..llm import LLMUnavailable
from ..models import CrawlRun, CVProfile, Insight, Job, Source
from ..services import assistant as assistant_service
from ..services import cv as cv_service
from ..tasks import enqueue_probe, enqueue_run
from .jobs import job_row, skills_for

router = APIRouter(prefix="/api", tags=["admin"])


def source_row(s: Source) -> dict:
    return {"id": s.id, "name": s.name, "url": s.url, "section": s.section, "kind": s.kind, "region": s.region, "strategy": s.strategy, "adapter": s.adapter, "status": s.status, "status_reason": s.status_reason, "enabled": s.enabled, "schedule_hours": s.schedule_hours, "last_run_at": s.last_run_at, "last_success_at": s.last_success_at, "jobs_total": s.jobs_total}


@router.get("/sources")
def list_sources(status: str | None = None, q: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Source)
    if status:
        stmt = stmt.where(Source.status == status)
    if q:
        stmt = stmt.where(Source.name.ilike(f"%{q}%") | Source.url.ilike(f"%{q}%"))
    rows = db.scalars(stmt.order_by(Source.jobs_total.desc(), Source.name)).all()
    counts = dict(db.execute(select(Source.status, func.count()).group_by(Source.status)).all())
    return {"counts": counts, "sources": [source_row(s) for s in rows]}


class SourceIn(BaseModel):
    url: str
    name: str | None = None


@router.post("/sources")
def add_source(body: SourceIn, background: BackgroundTasks, db: Session = Depends(get_db)):
    url = body.url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    parts = urlparse(url)
    if not parts.netloc or "." not in parts.netloc:
        raise HTTPException(422, "That does not look like a web address.")
    if db.scalar(select(Source).where(Source.url == url)):
        raise HTTPException(409, "That source is already in your list.")
    source = Source(name=body.name or parts.netloc.removeprefix("www."), url=url, domain=parts.netloc, config={}, probe={}, section="Added by you")
    db.add(source)
    db.commit()
    enqueue_probe(background, source.id, then_run=True)
    return source_row(source)


@router.post("/sources/{source_id}/run")
def run_now(source_id: int, background: BackgroundTasks, db: Session = Depends(get_db)):
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(404, "Source not found.")
    if source.status == "blocked":
        raise HTTPException(409, source.status_reason or "This source is blocked and is not collected.")
    enqueue_run(background, source.id)
    return {"queued": True}


@router.post("/sources/{source_id}/probe")
def probe_now(source_id: int, background: BackgroundTasks):
    enqueue_probe(background, source_id, then_run=False)
    return {"queued": True}


@router.get("/runs")
def runs(limit: int = Query(40, le=200), db: Session = Depends(get_db)):
    rows = db.execute(select(CrawlRun, Source.name).join(Source).order_by(CrawlRun.started_at.desc()).limit(limit)).all()
    return [{"id": r.id, "source": name, "status": r.status, "started_at": r.started_at, "finished_at": r.finished_at, "pages": r.pages, "seen": r.seen, "new": r.new, "updated": r.updated, "message": r.message} for r, name in rows]


@router.get("/insights")
def insights(q: str | None = None, limit: int = Query(40, le=100), db: Session = Depends(get_db)):
    stmt = select(Insight, Source.name).join(Source).order_by(Insight.fetched_at.desc()).limit(limit)
    if q:
        stmt = stmt.where(Insight.title.ilike(f"%{q}%") | Insight.summary.ilike(f"%{q}%"))
    return [{"id": i.id, "title": i.title, "summary": i.summary, "url": i.url, "source": name, "region": i.region, "fetched_at": i.fetched_at} for i, name in db.execute(stmt)]


def profile_row(p: CVProfile) -> dict:
    return {"id": p.id, "label": p.label, "filename": p.filename, "parsed": p.parsed, "created_at": p.created_at, "semantic": p.embedding is not None}


@router.get("/cv")
def list_cvs(db: Session = Depends(get_db)):
    return [profile_row(p) for p in db.scalars(select(CVProfile).order_by(CVProfile.created_at.desc()))]


@router.post("/cv")
def upload_cv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    # A plain def runs in the thread pool, so the model call cannot stall other requests.
    content = file.file.read()
    try:
        profile = cv_service.create_profile(db, file.filename or "cv", content)
    except cv_service.UnreadableCV as error:
        raise HTTPException(422, str(error)) from error
    return profile_row(profile)


def _profile(db: Session, cv_id: int) -> CVProfile:
    profile = db.get(CVProfile, cv_id)
    if profile is None:
        raise HTTPException(404, "That CV has been deleted.")
    return profile


@router.delete("/cv/{cv_id}")
def delete_cv(cv_id: int, db: Session = Depends(get_db)):
    db.delete(_profile(db, cv_id))
    db.commit()
    return {"ok": True}


@router.get("/cv/{cv_id}/matches")
def cv_matches(cv_id: int, limit: int = Query(50, le=200), f: Filters = Depends(filters_dep), db: Session = Depends(get_db)):
    profile = _profile(db, cv_id)
    result = cv_service.match_jobs(db, profile, f, limit)
    skills = skills_for(db, [m["job"].id for m in result["matches"]])
    return {**result, "matches": [{**{k: m[k] for k in ("score", "matched", "missing", "reasons")}, "job": job_row(m["job"], skills.get(m["job"].id))} for m in result["matches"]]}


class ExplainIn(BaseModel):
    matched: list[str] = []
    missing: list[str] = []


@router.post("/cv/{cv_id}/explain/{job_id}")
def explain(cv_id: int, job_id: int, body: ExplainIn, db: Session = Depends(get_db)):
    profile, job = _profile(db, cv_id), db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "This job is no longer stored.")
    try:
        return {"text": cv_service.explain_match(profile, job, body.matched, body.missing)}
    except LLMUnavailable as error:
        raise HTTPException(503, "The local model is not running. Start Ollama to get a written explanation.") from error


class ChatIn(BaseModel):
    question: str
    history: list[dict] = []


@router.post("/assistant")
def assistant(body: ChatIn):
    def events():
        db = SessionLocal()
        try:
            for event, payload in assistant_service.answer_events(db, body.question[:2000], body.history):
                yield f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"
        except Exception as error:  # the stream has already started, so the failure has to travel inside it
            logging.getLogger(__name__).exception("Assistant failed")
            yield f"event: error\ndata: {json.dumps({'text': f'The assistant hit a problem: {type(error).__name__}'})}\n\n"
        finally:
            db.close()

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})
