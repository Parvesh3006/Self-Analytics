from dataclasses import dataclass, field
from datetime import timedelta

from fastapi import Query
from sqlalchemy import exists, func, select

from .models import GeoCountry, Job, JobSkill, Skill, utcnow

# Shortcut used by the filter bar: "EU" expands to all European countries.
EUROPE_CODE = "EU"
PRIORITY = ["AU", "CA", "US", "IN", "GB", "SG", "NZ", "IE"]
_REMOTE_ROW = "XX"  # country filter value for postings with no single country


@dataclass
class Filters:
    country: list[str] = field(default_factory=list)
    state: str | None = None
    city: str | None = None
    role: list[str] = field(default_factory=list)
    skill: list[str] = field(default_factory=list)
    workplace: str | None = None
    salary_min: float | None = None
    days: int | None = None
    q: str | None = None
    company: str | None = None
    seniority: str | None = None
    visa: bool = False


def _split(value: str | None) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()] if value else []


def filters_dep(
    country: str | None = Query(None), state: str | None = Query(None), city: str | None = Query(None), role: str | None = Query(None),
    skill: str | None = Query(None), workplace: str | None = Query(None), salary_min: float | None = Query(None), days: int | None = Query(None),
    q: str | None = Query(None), company: str | None = Query(None), seniority: str | None = Query(None), visa: bool = Query(False),
) -> Filters:
    return Filters(_split(country), state or None, city or None, _split(role), _split(skill), workplace or None, salary_min, days, q or None, company or None, seniority or None, visa)


def apply_filters(stmt, f: Filters, *, skip: tuple[str, ...] = ()):
    """Apply the shared filter bar. `skip` leaves a dimension out, so its own facet keeps showing alternatives."""
    stmt = stmt.where(Job.is_active.is_(True))
    if f.country and "country" not in skip:
        codes = [c for c in f.country if c not in (EUROPE_CODE, _REMOTE_ROW)]
        clauses = []
        if EUROPE_CODE in f.country:
            clauses.append(Job.country_code.in_(select(GeoCountry.code).where(GeoCountry.continent == "EU")))
        if codes:
            clauses.append(Job.country_code.in_(codes))
        if _REMOTE_ROW in f.country:
            clauses.append(Job.country_code.is_(None))
        from sqlalchemy import or_

        stmt = stmt.where(or_(*clauses))
    if f.state and "state" not in skip:
        stmt = stmt.where(Job.state == f.state)
    if f.city and "city" not in skip:
        stmt = stmt.where(Job.city == f.city)
    if f.role and "role" not in skip:
        stmt = stmt.where(Job.role_family.in_(f.role))
    if f.skill and "skill" not in skip:
        for name in f.skill:
            stmt = stmt.where(exists(select(JobSkill.job_id).join(Skill).where(JobSkill.job_id == Job.id, Skill.name == name)))
    if f.workplace and "workplace" not in skip:
        stmt = stmt.where(Job.workplace == f.workplace)
    if f.salary_min is not None and "salary" not in skip:
        stmt = stmt.where(Job.salary_usd_min >= f.salary_min)
    if f.days and "days" not in skip:
        cutoff = utcnow() - timedelta(days=f.days)
        stmt = stmt.where(func.coalesce(Job.posted_at, Job.first_seen) >= cutoff)
    if f.q:
        stmt = stmt.where(Job.search.op("@@")(func.websearch_to_tsquery("simple", f.q)))
    if f.company:
        stmt = stmt.where(Job.company_name == f.company)
    if f.seniority:
        stmt = stmt.where(Job.seniority == f.seniority)
    if f.visa:
        stmt = stmt.where(Job.visa_sponsorship.is_(True))
    return stmt
