import csv
import io
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..filters import Filters, apply_filters, filters_dep
from ..models import Job, JobSighting, JobSkill, SavedFilter, Skill, Source, utcnow

router = APIRouter(prefix="/api", tags=["jobs"])
POSTED = func.coalesce(Job.posted_at, Job.first_seen)


def job_row(job: Job, skills: list[str] | None = None) -> dict:
    return {
        "id": job.id, "title": job.title, "company": job.company_name, "role_family": job.role_family, "seniority": job.seniority, "country_code": job.country_code, "country": job.country,
        "state": job.state, "city": job.city, "location_raw": job.location_raw, "workplace": job.workplace, "employment_type": job.employment_type, "salary_min": job.salary_min, "salary_max": job.salary_max,
        "salary_currency": job.salary_currency, "salary_period": job.salary_period, "salary_usd_min": job.salary_usd_min, "salary_usd_max": job.salary_usd_max, "posted_at": job.posted_at, "first_seen": job.first_seen,
        "last_seen": job.last_seen, "apply_url": job.apply_url, "source": job.primary_source, "visa_sponsorship": job.visa_sponsorship, "skills": skills or [],
    }


def skills_for(db: Session, ids: list[int]) -> dict[int, list[str]]:
    result: dict[int, list[str]] = {}
    if ids:
        for job_id, name in db.execute(select(JobSkill.job_id, Skill.name).join(Skill).where(JobSkill.job_id.in_(ids))):
            result.setdefault(job_id, []).append(name)
    return result


SORTS = {"newest": POSTED.desc(), "salary": Job.salary_usd_min.desc().nulls_last(), "company": Job.company_name.asc(), "title": Job.title.asc()}


@router.get("/jobs")
def list_jobs(page: int = Query(1, ge=1), size: int = Query(25, le=100), sort: Literal["newest", "salary", "company", "title"] = "newest", f: Filters = Depends(filters_dep), db: Session = Depends(get_db)):
    total = db.scalar(apply_filters(select(func.count()).select_from(Job), f)) or 0
    jobs = list(db.scalars(apply_filters(select(Job), f).order_by(SORTS[sort], Job.id.desc()).offset((page - 1) * size).limit(size)))
    skills = skills_for(db, [j.id for j in jobs])
    return {"total": total, "page": page, "size": size, "jobs": [job_row(j, skills.get(j.id)) for j in jobs]}


@router.get("/jobs/export.csv")
def export(f: Filters = Depends(filters_dep), db: Session = Depends(get_db)):
    jobs = list(db.scalars(apply_filters(select(Job), f).order_by(POSTED.desc()).limit(10000)))
    skills = skills_for(db, [j.id for j in jobs])
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["title", "company", "role", "seniority", "city", "state", "country", "workplace", "salary_usd_min", "salary_usd_max", "posted", "skills", "url", "source"])
    for j in jobs:
        writer.writerow([j.title, j.company_name, j.role_family, j.seniority, j.city, j.state, j.country, j.workplace, j.salary_usd_min, j.salary_usd_max, (j.posted_at or j.first_seen).date(), "; ".join(skills.get(j.id, [])), j.apply_url, j.primary_source])
    return StreamingResponse(iter([buffer.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=self-analytics-jobs.csv"})


@router.get("/jobs/{job_id}")
def job_detail(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "This job is no longer stored.")
    skills = skills_for(db, [job.id]).get(job.id, [])
    sightings = db.execute(select(JobSighting, Source).join(Source).where(JobSighting.job_id == job.id).order_by(JobSighting.first_seen)).all()
    similar: list[Job] = []
    if job.embedding is not None:
        similar = list(db.scalars(select(Job).where(Job.id != job.id, Job.is_active.is_(True), Job.embedding.is_not(None)).order_by(Job.embedding.cosine_distance(job.embedding)).limit(6)))
    else:
        similar = list(db.scalars(select(Job).where(Job.id != job.id, Job.is_active.is_(True), Job.role_family == job.role_family, Job.country_code == job.country_code).order_by(POSTED.desc()).limit(6)))
    return {
        **job_row(job, skills), "description": job.description, "is_active": job.is_active,
        "sightings": [{"source": s.name, "url": g.url, "first_seen": g.first_seen, "last_seen": g.last_seen} for g, s in sightings],
        "similar": [job_row(j) for j in similar],
    }


class SavedFilterIn(BaseModel):
    name: str
    filters: dict
    alert: bool = False


def _as_filters(raw: dict) -> Filters:
    split = lambda k: [v for v in str(raw.get(k) or "").split(",") if v]  # noqa: E731
    return Filters(split("country"), raw.get("state"), raw.get("city"), split("role"), split("skill"), raw.get("workplace"), float(raw["salary_min"]) if raw.get("salary_min") else None, int(raw["days"]) if raw.get("days") else None, raw.get("q"), raw.get("company"), raw.get("seniority"), str(raw.get("visa")) == "true")


@router.get("/saved-filters")
def saved_filters(db: Session = Depends(get_db)):
    rows = db.scalars(select(SavedFilter).order_by(SavedFilter.created_at.desc())).all()
    return [{"id": s.id, "name": s.name, "filters": s.filters, "alert": s.alert, "new_jobs": db.scalar(apply_filters(select(func.count()).select_from(Job).where(Job.first_seen > s.last_checked), _as_filters(s.filters))) if s.alert else None} for s in rows]


@router.post("/saved-filters")
def create_saved(body: SavedFilterIn, db: Session = Depends(get_db)):
    item = SavedFilter(name=body.name[:120], filters=body.filters, alert=body.alert)
    db.add(item)
    db.commit()
    return {"id": item.id}


@router.post("/saved-filters/{item_id}/seen")
def mark_seen(item_id: int, db: Session = Depends(get_db)):
    item = db.get(SavedFilter, item_id)
    if item:
        item.last_checked = utcnow()
        db.commit()
    return {"ok": True}


@router.delete("/saved-filters/{item_id}")
def delete_saved(item_id: int, db: Session = Depends(get_db)):
    item = db.get(SavedFilter, item_id)
    if item:
        db.delete(item)
        db.commit()
    return {"ok": True}
