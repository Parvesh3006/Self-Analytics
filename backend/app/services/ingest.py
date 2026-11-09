"""Normalise RawJobs and store them: location, skills, salary, role, dedupe, sightings."""
import hashlib
from datetime import datetime, timedelta, timezone

import httpx
from rapidfuzz import fuzz
from sqlalchemy import delete, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..adapters.base import RawJob
from ..models import Company, FxRate, Job, JobSighting, JobSkill, Skill, Source, utcnow
from ..normalize.geo import Resolver, infer_workplace
from ..normalize.salary import parse_salary_text, to_annual_usd
from ..normalize.skills import extract_skills, load_taxonomy
from ..normalize.text import norm_key
from ..normalize.titles import role_family, seniority

MAX_DESCRIPTION = 20000
BATCH = 200


def sync_skills(db: Session) -> None:
    rows = [{"name": s.name, "category": s.category} for s in load_taxonomy()]
    stmt = insert(Skill).values(rows)
    db.execute(stmt.on_conflict_do_update(index_elements=["name"], set_={"category": stmt.excluded.category}))
    db.commit()


def refresh_fx(db: Session) -> int:
    """ECB reference rates via Frankfurter (no key)."""
    data = httpx.get("https://api.frankfurter.dev/v1/latest", params={"base": "USD"}, timeout=30, follow_redirects=True).raise_for_status().json()
    rates = {**data["rates"], "USD": 1.0}
    for currency, value in rates.items():
        stmt = insert(FxRate).values(currency=currency, per_usd=value, updated_at=utcnow())
        db.execute(stmt.on_conflict_do_update(index_elements=["currency"], set_={"per_usd": value, "updated_at": utcnow()}))
    db.commit()
    return len(rates)


def fingerprint(title: str, company: str, country: str | None, city: str | None, location_raw: str | None) -> str:
    place = f"{country or ''}|{norm_key(city or '')}" if (country or city) else norm_key(location_raw or "")
    return hashlib.sha256(f"{norm_key(title)}|{norm_key(company)}|{place}".encode()).hexdigest()


class Ingestor:
    def __init__(self, db: Session, source: Source):
        self.db = db
        self.source = source
        self.resolver = Resolver(db)
        self.companies: dict[str, int] = {}
        self.skill_ids = {name: id_ for id_, name in db.execute(select(Skill.id, Skill.name))}
        self.per_usd = {c: r for c, r in db.execute(select(FxRate.currency, FxRate.per_usd))}
        self.seen = self.new = self.updated = 0
        self.pending = 0

    def _company(self, name: str) -> int | None:
        key = norm_key(name)[:300]
        if not key:
            return None
        if key not in self.companies:
            stmt = insert(Company).values(name=name[:300], norm_name=key).on_conflict_do_nothing(index_elements=["norm_name"])
            self.db.execute(stmt)
            self.companies[key] = self.db.scalar(select(Company.id).where(Company.norm_name == key))
        return self.companies[key]

    def add(self, raw: RawJob) -> None:
        if not raw.title or not raw.title.strip():
            return
        self.seen += 1
        now = utcnow()
        title = raw.title.strip()[:400]
        company = (raw.company or "Unknown").strip()[:300] or "Unknown"
        place = self.resolver.resolve(raw.location, raw.country_code)
        workplace = raw.workplace or infer_workplace(raw.location, title, raw.remote)

        salary_min, salary_max, currency, period = raw.salary_min, raw.salary_max, raw.salary_currency, raw.salary_period
        if salary_min is None and (raw.salary_text or raw.description):
            parsed = parse_salary_text(raw.salary_text, place.country_code) or parse_salary_text(raw.description, place.country_code)
            if parsed:
                salary_min, salary_max, currency, period = parsed.min, parsed.max, parsed.currency, parsed.period
        usd_min = to_annual_usd(salary_min, currency, period, self.per_usd)
        usd_max = to_annual_usd(salary_max, currency, period, self.per_usd)
        if usd_min is None:  # failed the plausibility check, so the raw figures are not shown either
            salary_min = salary_max = currency = period = usd_max = None

        description = (raw.description or "")[:MAX_DESCRIPTION]
        fp = fingerprint(title, company, place.country_code, place.city, raw.location)

        sighting = self.db.scalar(select(JobSighting).where(
            JobSighting.source_id == self.source.id, JobSighting.external_id == raw.external_id[:500]))
        job = self.db.get(Job, sighting.job_id) if sighting else self.db.scalar(select(Job).where(Job.fingerprint == fp))

        if job is None:
            job = Job(
                fingerprint=fp, title=title, title_norm=norm_key(title)[:400], role_family=role_family(title), seniority=seniority(title),
                company_id=self._company(company), company_name=company, description=description, location_raw=(raw.location or "")[:500] or None,
                country_code=place.country_code, country=place.country, state=place.state, city=place.city, lat=place.lat, lng=place.lng,
                workplace=workplace, employment_type=(raw.employment_type or None) and raw.employment_type[:40],
                salary_min=salary_min, salary_max=salary_max, salary_currency=currency, salary_period=period, salary_usd_min=usd_min, salary_usd_max=usd_max,
                posted_at=raw.posted_at, valid_through=raw.valid_through, first_seen=now, last_seen=now, is_active=True,
                apply_url=(raw.url or "")[:1500] or None, primary_source=self.source.name,
                visa_sponsorship=_visa(description),
            )
            self.db.add(job)
            self.db.flush()
            self._link_skills(job.id, title, description, raw.tags, company)
            self.new += 1
        else:
            changed = False
            # A longer description or an advertised salary from another board improves the record.
            if len(description) > len(job.description or ""):
                job.description = description
                self._link_skills(job.id, title, description, raw.tags, company)
                changed = True
            if job.salary_usd_min is None and usd_min is not None:
                job.salary_min, job.salary_max, job.salary_currency, job.salary_period = salary_min, salary_max, currency, period
                job.salary_usd_min, job.salary_usd_max = usd_min, usd_max
                changed = True
            job.last_seen = now
            job.is_active = True
            self.updated += int(changed)

        if sighting:
            sighting.last_seen = now
        else:
            self.db.execute(insert(JobSighting).values(
                job_id=job.id, source_id=self.source.id, external_id=raw.external_id[:500], url=(raw.url or "")[:1500] or None,
                first_seen=now, last_seen=now,
            ).on_conflict_do_nothing(index_elements=["source_id", "external_id"]))

        self.pending += 1
        if self.pending >= BATCH:
            self.db.commit()
            self.pending = 0

    def _link_skills(self, job_id: int, title: str, description: str, tags: list[str], company: str = "") -> None:
        names = set(extract_skills(f"{title}\n{description}\n{' , '.join(tags or [])}"))
        # A company naming itself ("Datadog is hiring") is not asking for that product as a skill.
        own_name = set(norm_key(company).split())
        ids = [self.skill_ids[n] for n in names if n in self.skill_ids and norm_key(n) not in own_name]
        if ids:
            self.db.execute(insert(JobSkill).values([{"job_id": job_id, "skill_id": i} for i in ids]).on_conflict_do_nothing())

    def finish(self) -> None:
        self.db.commit()


def _visa(description: str) -> bool | None:
    lowered = description.lower()
    if any(p in lowered for p in ("no visa sponsorship", "unable to sponsor", "cannot sponsor", "not able to sponsor", "without sponsorship", "does not offer sponsorship", "not offer visa")):
        return False
    if any(p in lowered for p in ("visa sponsorship", "sponsor visas", "will sponsor", "relocation and visa", "visa support")):
        return True
    return None


def expire_stale(db: Session, days: int = 21) -> int:
    cutoff = utcnow() - timedelta(days=days)
    result = db.execute(update(Job).where(Job.is_active.is_(True), (Job.last_seen < cutoff) | (Job.valid_through < utcnow())).values(is_active=False))
    db.commit()
    return result.rowcount


def merge_near_duplicates(db: Session, since: datetime | None = None) -> int:
    """Second dedupe pass: same company and city, nearly identical title. The oldest record survives."""
    since = since or (utcnow() - timedelta(days=2))
    groups = db.execute(text("""
        SELECT company_id, coalesce(country_code,'') cc, coalesce(city,'') city
        FROM jobs WHERE first_seen >= :since AND company_id IS NOT NULL AND is_active
        GROUP BY 1,2,3
    """), {"since": since}).all()
    merged = 0
    for group in groups:
        rows = db.execute(select(Job.id, Job.title_norm).where(
            Job.company_id == group.company_id, Job.is_active.is_(True),
            text("coalesce(country_code,'') = :cc AND coalesce(city,'') = :city")).params(cc=group.cc, city=group.city).order_by(Job.first_seen)).all()
        kept: list[tuple[int, str]] = []
        for row in rows:
            duplicate_of = next((k for k in kept if fuzz.token_sort_ratio(k[1], row.title_norm) >= 96), None)
            if duplicate_of is None:
                kept.append((row.id, row.title_norm))
                continue
            db.execute(update(JobSighting).where(JobSighting.job_id == row.id).values(job_id=duplicate_of[0]))
            db.execute(delete(Job).where(Job.id == row.id))
            merged += 1
    db.commit()
    return merged


__all__ = ["Ingestor", "sync_skills", "refresh_fx", "fingerprint", "expire_stale", "merge_near_duplicates", "datetime", "timezone"]
