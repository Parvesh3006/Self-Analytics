from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select, text
from sqlalchemy.orm import Session

from ..db import get_db
from ..filters import EUROPE_CODE, PRIORITY, Filters, apply_filters, filters_dep
from ..llm import status as llm_status
from ..models import CrawlRun, FxRate, GeoCountry, Job, JobSighting, JobSkill, Skill, Source, utcnow

router = APIRouter(prefix="/api", tags=["market"])
POSTED = func.coalesce(Job.posted_at, Job.first_seen)
MEDIAN = func.percentile_cont(0.5).within_group(Job.salary_usd_min)
REMOTE_SHARE = func.avg(case((Job.workplace == "remote", 100.0), else_=0.0))
MIN_POSTINGS_PER_WEEK = 25


@router.get("/status")
def app_status(db: Session = Depends(get_db)):
    jobs = db.scalar(select(func.count()).select_from(Job).where(Job.is_active.is_(True))) or 0
    embedded = db.scalar(select(func.count()).select_from(Job).where(Job.is_active.is_(True), Job.embedding.is_not(None))) or 0
    last = db.execute(select(CrawlRun.finished_at).where(CrawlRun.status.in_(["ok", "partial"])).order_by(CrawlRun.finished_at.desc()).limit(1)).scalar()
    first = db.scalar(select(func.min(Job.first_seen)))
    sources = dict(db.execute(select(Source.status, func.count()).group_by(Source.status)).all())
    return {"jobs": jobs, "embedded": embedded, "last_collected": last, "first_collected": first, "sources": sources, "llm": llm_status(), "now": utcnow()}


@router.get("/fx")
def fx(db: Session = Depends(get_db)):
    return {c: r for c, r in db.execute(select(FxRate.currency, FxRate.per_usd))}


@router.get("/facets")
def facets(f: Filters = Depends(filters_dep), db: Session = Depends(get_db)):
    """Filter choices with live counts. Each dimension ignores its own selection so alternatives stay visible."""
    def counts(column, skip, limit=400):
        stmt = apply_filters(select(column, func.count()).where(column.is_not(None)), f, skip=skip).group_by(column).order_by(func.count().desc()).limit(limit)
        return [{"value": v, "count": c} for v, c in db.execute(stmt)]

    country_rows = db.execute(apply_filters(select(Job.country_code, Job.country, func.count()).where(Job.country_code.is_not(None)), f, skip=("country", "state", "city"))
                              .group_by(Job.country_code, Job.country).order_by(func.count().desc())).all()
    europe = set(db.scalars(select(GeoCountry.code).where(GeoCountry.continent == "EU")))
    no_country = db.scalar(apply_filters(select(func.count()).select_from(Job).where(Job.country_code.is_(None)), f, skip=("country", "state", "city"))) or 0
    europe_total = sum(r[2] for r in country_rows if r[0] in europe)
    skills = db.execute(apply_filters(select(Skill.name, func.count()).join(JobSkill, JobSkill.skill_id == Skill.id).join(Job, Job.id == JobSkill.job_id), f, skip=("skill",))
                        .group_by(Skill.name).order_by(func.count().desc()).limit(250)).all()
    states = counts(Job.state, ("state", "city")) if f.country else []
    cities = counts(Job.city, ("city",)) if f.country or f.state else []
    return {
        "countries": [{"value": r[0], "label": r[1], "count": r[2], "priority": r[0] in PRIORITY, "europe": r[0] in europe} for r in country_rows],
        "europe_total": europe_total, "no_country": no_country, "europe_code": EUROPE_CODE, "states": states, "cities": cities,
        "roles": counts(Job.role_family, ("role",)), "seniority": counts(Job.seniority, ("seniority",)), "skills": [{"value": n, "count": c} for n, c in skills],
    }


@router.get("/market/overview")
def overview(f: Filters = Depends(filters_dep), db: Session = Depends(get_db)):
    now = utcnow()
    row = db.execute(apply_filters(select(
        func.count().label("jobs"), MEDIAN.label("median"), func.count(Job.salary_usd_min).label("with_salary"), REMOTE_SHARE.label("remote"),
        func.count(func.distinct(Job.company_id)).label("companies"), func.count(func.distinct(Job.country_code)).label("countries"),
        func.count().filter(POSTED >= now - timedelta(days=7)).label("new7"),
        func.count().filter(POSTED < now - timedelta(days=7), POSTED >= now - timedelta(days=14)).label("prev7"),
    ).select_from(Job), f)).one()
    sparkline = db.execute(apply_filters(select(func.date_trunc("day", POSTED).label("d"), func.count()).select_from(Job).where(POSTED >= now - timedelta(days=30)), f).group_by(text("1")).order_by(text("1"))).all()
    return {
        "jobs": row.jobs, "median_usd": row.median, "with_salary": row.with_salary, "remote_share": float(row.remote or 0), "companies": row.companies, "countries": row.countries,
        "new_7d": row.new7, "prev_7d": row.prev7, "daily": [{"date": d, "count": c} for d, c in sparkline],
    }


@router.get("/market/countries")
def countries(f: Filters = Depends(filters_dep), db: Session = Depends(get_db)):
    now = utcnow()
    rows = db.execute(apply_filters(select(
        Job.country_code, Job.country, func.count().label("jobs"), MEDIAN.label("median"), func.count(Job.salary_usd_min).label("with_salary"), REMOTE_SHARE.label("remote"),
        func.count().filter(POSTED >= now - timedelta(days=7)).label("new7"),
    ).where(Job.country_code.is_not(None)), f, skip=("state", "city")).group_by(Job.country_code, Job.country).order_by(func.count().desc())).all()
    codes = [r.country_code for r in rows]
    tops: dict[str, str] = {}
    if codes:
        skill_rows = db.execute(apply_filters(select(Job.country_code, Skill.name, func.count().label("n")).join(JobSkill, JobSkill.job_id == Job.id).join(Skill, Skill.id == JobSkill.skill_id), f, skip=("state", "city"))
                                .group_by(Job.country_code, Skill.name).order_by(Job.country_code, func.count().desc())).all()
        for code, name, _n in skill_rows:
            tops.setdefault(code, name)
    return [{
        "code": r.country_code, "name": r.country, "jobs": r.jobs, "median_usd": r.median, "with_salary": r.with_salary, "remote_share": float(r.remote or 0), "new_7d": r.new7,
        "top_skill": tops.get(r.country_code), "priority": r.country_code in PRIORITY,
    } for r in rows]


@router.get("/market/locations")
def locations(level: str = Query("state", pattern="^(state|city)$"), f: Filters = Depends(filters_dep), db: Session = Depends(get_db)):
    column = Job.state if level == "state" else Job.city
    skip = ("state", "city") if level == "state" else ("city",)
    rows = db.execute(apply_filters(select(column.label("name"), func.count().label("jobs"), MEDIAN.label("median"), func.count(Job.salary_usd_min).label("with_salary")).where(column.is_not(None)), f, skip=skip)
                      .group_by(column).order_by(func.count().desc()).limit(40)).all()
    return [{"name": r.name, "jobs": r.jobs, "median_usd": r.median, "with_salary": r.with_salary} for r in rows]


@router.get("/market/roles")
def roles(f: Filters = Depends(filters_dep), db: Session = Depends(get_db)):
    rows = db.execute(apply_filters(select(Job.role_family, func.count().label("jobs"), MEDIAN.label("median"), func.count(Job.salary_usd_min).label("with_salary")), f)
                      .group_by(Job.role_family).order_by(func.count().desc()).limit(20)).all()
    return [{"role": r.role_family, "jobs": r.jobs, "median_usd": r.median, "with_salary": r.with_salary} for r in rows]


@router.get("/market/companies")
def companies(f: Filters = Depends(filters_dep), db: Session = Depends(get_db)):
    rows = db.execute(apply_filters(select(Job.company_name, func.count().label("jobs")).where(Job.company_name != "Unknown"), f).group_by(Job.company_name).order_by(func.count().desc()).limit(15)).all()
    return [{"company": r.company_name, "jobs": r.jobs} for r in rows]


@router.get("/market/skills")
def top_skills(limit: int = Query(20, le=100), f: Filters = Depends(filters_dep), db: Session = Depends(get_db)):
    total = db.scalar(apply_filters(select(func.count()).select_from(Job), f, skip=("skill",))) or 0
    rows = db.execute(apply_filters(select(Skill.name, Skill.category, func.count().label("jobs"), MEDIAN.label("median")).join(JobSkill, JobSkill.skill_id == Skill.id).join(Job, Job.id == JobSkill.job_id), f, skip=("skill",))
                      .group_by(Skill.name, Skill.category).order_by(func.count().desc()).limit(limit)).all()
    return {"total": total, "skills": [{"skill": r.name, "category": r.category, "jobs": r.jobs, "share": round(100 * r.jobs / total, 1) if total else 0, "median_usd": r.median} for r in rows]}


@router.get("/trends/volume")
def volume(weeks: int = Query(16, le=52), f: Filters = Depends(filters_dep), db: Session = Depends(get_db)):
    cutoff = utcnow() - timedelta(weeks=weeks)
    rows = db.execute(apply_filters(select(func.date_trunc("week", POSTED).label("w"), func.count()).select_from(Job).where(POSTED >= cutoff), f).group_by(text("1")).order_by(text("1"))).all()
    return [{"week": w, "jobs": c} for w, c in rows]


@router.get("/trends/skills")
def skill_trends(weeks: int = Query(16, le=52), skills: str | None = Query(None), f: Filters = Depends(filters_dep), db: Session = Depends(get_db)):
    """Weekly share of postings naming each skill. Share, not count, so a bigger crawl does not look like rising demand."""
    cutoff = utcnow() - timedelta(weeks=weeks)
    week = func.date_trunc("week", POSTED).label("w")
    # The current week is incomplete, and would read as a collapse in demand.
    this_week = func.date_trunc("week", func.now())
    totals = dict(db.execute(apply_filters(select(week, func.count()).select_from(Job).where(POSTED >= cutoff, POSTED < this_week), f, skip=("skill",)).group_by(text("1"))).all())
    names = [s.strip() for s in skills.split(",") if s.strip()] if skills else None
    if not names:
        names = [r[0] for r in db.execute(apply_filters(select(Skill.name, func.count()).join(JobSkill, JobSkill.skill_id == Skill.id).join(Job, Job.id == JobSkill.job_id), f, skip=("skill",)).group_by(Skill.name).order_by(func.count().desc()).limit(5))]
    rows = db.execute(apply_filters(select(week, Skill.name, func.count()).join(JobSkill, JobSkill.skill_id == Skill.id).join(Job, Job.id == JobSkill.job_id).where(POSTED >= cutoff, POSTED < this_week, Skill.name.in_(names)), f, skip=("skill",)).group_by(text("1"), Skill.name)).all()
    table: dict = {}
    for w, name, count in rows:
        table.setdefault(name, {})[w] = count
    # A week with a handful of surviving postings gives meaningless percentages like 100%.
    ordered = sorted(w for w, total in totals.items() if total >= MIN_POSTINGS_PER_WEEK)
    return {
        "weeks": ordered, "totals": [totals[w] for w in ordered],
        "series": [{"skill": n, "share": [round(100 * table.get(n, {}).get(w, 0) / totals[w], 2) if totals[w] else 0 for w in ordered], "count": [table.get(n, {}).get(w, 0) for w in ordered]} for n in names],
    }


@router.get("/trends/movers")
def movers(f: Filters = Depends(filters_dep), db: Session = Depends(get_db)):
    """Skills gaining or losing share: last 14 days against the 42 days before."""
    now = utcnow()
    recent, base = now - timedelta(days=14), now - timedelta(days=56)
    totals = db.execute(apply_filters(select(func.count().filter(POSTED >= recent), func.count().filter(POSTED < recent, POSTED >= base)).select_from(Job), f, skip=("skill",))).one()
    if not totals[0] or not totals[1]:
        return {"rising": [], "falling": [], "recent_jobs": totals[0], "base_jobs": totals[1], "enough": False}
    first = db.scalar(select(func.min(Job.first_seen)))
    collecting_for = (now - first).days if first else 0  # early on, "recent" mostly reflects which sources post short-lived ads
    rows = db.execute(apply_filters(select(Skill.name, func.count().filter(POSTED >= recent).label("now"), func.count().filter(POSTED < recent, POSTED >= base).label("before")).join(JobSkill, JobSkill.skill_id == Skill.id).join(Job, Job.id == JobSkill.job_id), f, skip=("skill",)).group_by(Skill.name)).all()
    items = []
    for name, current, before in rows:
        if current + before < 30:
            continue
        share_now, share_before = 100 * current / totals[0], 100 * before / totals[1]
        items.append({"skill": name, "share_now": round(share_now, 2), "share_before": round(share_before, 2), "change": round(share_now - share_before, 2), "jobs_now": current})
    items.sort(key=lambda x: x["change"], reverse=True)
    return {"rising": [i for i in items[:10] if i["change"] > 0], "falling": [i for i in reversed(items[-10:]) if i["change"] < 0], "recent_jobs": totals[0], "base_jobs": totals[1], "enough": totals[0] >= 200 and totals[1] >= 200 and collecting_for >= 28}


@router.get("/trends/heatmap")
def heatmap(f: Filters = Depends(filters_dep), db: Session = Depends(get_db)):
    """Share of each country's postings that name each top skill."""
    codes = [r[0] for r in db.execute(apply_filters(select(Job.country_code, func.count()).where(Job.country_code.is_not(None)), f).group_by(Job.country_code).order_by(case((Job.country_code.in_(PRIORITY), 0), else_=1), func.count().desc()).limit(10))]
    if not codes:
        return {"countries": [], "skills": [], "cells": []}
    names = dict(db.execute(select(GeoCountry.code, GeoCountry.name).where(GeoCountry.code.in_(codes))).all())
    totals = dict(db.execute(apply_filters(select(Job.country_code, func.count()).where(Job.country_code.in_(codes)), f, skip=("skill",)).group_by(Job.country_code)).all())
    skills = [r[0] for r in db.execute(apply_filters(select(Skill.name, func.count()).join(JobSkill, JobSkill.skill_id == Skill.id).join(Job, Job.id == JobSkill.job_id).where(Job.country_code.in_(codes)), f, skip=("skill",)).group_by(Skill.name).order_by(func.count().desc()).limit(12))]
    rows = db.execute(apply_filters(select(Job.country_code, Skill.name, func.count()).join(JobSkill, JobSkill.job_id == Job.id).join(Skill, Skill.id == JobSkill.skill_id).where(Job.country_code.in_(codes), Skill.name.in_(skills)), f, skip=("skill",)).group_by(Job.country_code, Skill.name)).all()
    return {
        "countries": [{"code": c, "name": names.get(c, c), "jobs": totals.get(c, 0)} for c in codes], "skills": skills,
        "cells": [{"country": c, "skill": s, "jobs": n, "share": round(100 * n / totals[c], 1)} for c, s, n in rows if totals.get(c)],
    }


@router.get("/market/provenance")
def provenance(f: Filters = Depends(filters_dep), db: Session = Depends(get_db)):
    """Which sources the current view is built from: powers the postmark beside each headline number."""
    rows = db.execute(apply_filters(select(Source.name, func.count(func.distinct(Job.id)).label("jobs"), func.max(JobSighting.last_seen).label("seen")).join(JobSighting, JobSighting.source_id == Source.id).join(Job, Job.id == JobSighting.job_id), f).group_by(Source.name).order_by(func.count(func.distinct(Job.id)).desc()).limit(8)).all()
    total_sources = db.scalar(apply_filters(select(func.count(func.distinct(JobSighting.source_id))).join(Job, Job.id == JobSighting.job_id), f)) or 0
    return {"total_sources": total_sources, "top": [{"name": r.name, "jobs": r.jobs, "last_seen": r.seen} for r in rows]}
