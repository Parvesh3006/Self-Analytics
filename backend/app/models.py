from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON, Boolean, Computed, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

EMBED_DIM = 1024  # bge-m3


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(1000), unique=True)
    domain: Mapped[str] = mapped_column(String(255), index=True)
    section: Mapped[str] = mapped_column(String(120), default="Added by you")
    kind: Mapped[str] = mapped_column(String(40), default="job_board")
    region: Mapped[str] = mapped_column(String(80), default="Worldwide")
    # api | auto | jsonld | rss | crawl | insight | discover | blocked | none
    strategy: Mapped[str] = mapped_column(String(20), default="auto")
    adapter: Mapped[str | None] = mapped_column(String(40))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    # new | active | needs_key | blocked | error | reference
    status: Mapped[str] = mapped_column(String(20), default="new", index=True)
    status_reason: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    schedule_hours: Mapped[int] = mapped_column(Integer, default=24)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    probed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    probe: Mapped[dict] = mapped_column(JSON, default=dict)
    jobs_total: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CrawlRun(Base):
    __tablename__ = "crawl_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="running")  # running | ok | partial | error | skipped
    pages: Mapped[int] = mapped_column(Integer, default=0)
    seen: Mapped[int] = mapped_column(Integer, default=0)
    new: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str | None] = mapped_column(Text)

    source: Mapped[Source] = relationship()


class CrawlPage(Base):
    """Remembers what a page looked like so unchanged pages are skipped on re-crawl."""

    __tablename__ = "crawl_pages"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(String(1500))
    etag: Mapped[str | None] = mapped_column(String(300))
    last_modified: Mapped[str | None] = mapped_column(String(100))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    page_type: Mapped[str | None] = mapped_column(String(20))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("source_id", "url"),)


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(300))
    norm_name: Mapped[str] = mapped_column(String(300), unique=True)


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    category: Mapped[str] = mapped_column(String(60), index=True)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(String(400))
    title_norm: Mapped[str] = mapped_column(String(400))
    role_family: Mapped[str] = mapped_column(String(80), index=True, default="Other")
    seniority: Mapped[str] = mapped_column(String(30), index=True, default="Unspecified")
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), index=True)
    company_name: Mapped[str] = mapped_column(String(300), default="Unknown")
    description: Mapped[str] = mapped_column(Text, default="")

    location_raw: Mapped[str | None] = mapped_column(String(500))
    country_code: Mapped[str | None] = mapped_column(String(2), index=True)
    country: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(150), index=True)
    city: Mapped[str | None] = mapped_column(String(200), index=True)
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    # onsite | hybrid | remote | unknown
    workplace: Mapped[str] = mapped_column(String(10), default="unknown", index=True)
    employment_type: Mapped[str | None] = mapped_column(String(40))

    salary_min: Mapped[float | None] = mapped_column(Float)
    salary_max: Mapped[float | None] = mapped_column(Float)
    salary_currency: Mapped[str | None] = mapped_column(String(3))
    salary_period: Mapped[str | None] = mapped_column(String(10))
    salary_usd_min: Mapped[float | None] = mapped_column(Float, index=True)
    salary_usd_max: Mapped[float | None] = mapped_column(Float)

    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    valid_through: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    apply_url: Mapped[str | None] = mapped_column(String(1500))
    visa_sponsorship: Mapped[bool | None] = mapped_column(Boolean)
    primary_source: Mapped[str | None] = mapped_column(String(200))

    embedding = mapped_column(Vector(EMBED_DIM), nullable=True)
    search = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('simple', coalesce(title,'')), 'A') || "
            "setweight(to_tsvector('simple', coalesce(company_name,'')), 'B') || "
            "setweight(to_tsvector('simple', left(coalesce(description,''), 4000)), 'C')",
            persisted=True,
        ),
    )

    skills: Mapped[list["JobSkill"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    sightings: Mapped[list["JobSighting"]] = relationship(back_populates="job", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_jobs_search", "search", postgresql_using="gin"),
        Index("ix_jobs_active_country", "is_active", "country_code"),
        Index(
            "ix_jobs_embedding", "embedding", postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class JobSkill(Base):
    __tablename__ = "job_skills"

    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True, index=True)

    job: Mapped[Job] = relationship(back_populates="skills")
    skill: Mapped[Skill] = relationship()


class JobSighting(Base):
    """One posting on one source. The same job can have several after dedupe."""

    __tablename__ = "job_sightings"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(500))
    url: Mapped[str | None] = mapped_column(String(1500))
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    job: Mapped[Job] = relationship(back_populates="sightings")
    source: Mapped[Source] = relationship()

    __table_args__ = (UniqueConstraint("source_id", "external_id"),)


class Insight(Base):
    __tablename__ = "insights"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(String(1500), unique=True)
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str] = mapped_column(Text, default="")
    region: Mapped[str | None] = mapped_column(String(80))
    content_hash: Mapped[str] = mapped_column(String(64))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    source: Mapped[Source] = relationship()
    chunks: Mapped[list["InsightChunk"]] = relationship(cascade="all, delete-orphan")


class InsightChunk(Base):
    __tablename__ = "insight_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    insight_id: Mapped[int] = mapped_column(ForeignKey("insights.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    embedding = mapped_column(Vector(EMBED_DIM), nullable=True)


class CVProfile(Base):
    __tablename__ = "cv_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(200))
    filename: Mapped[str] = mapped_column(String(300))
    text: Mapped[str] = mapped_column(Text)
    parsed: Mapped[dict] = mapped_column(JSON, default=dict)
    embedding = mapped_column(Vector(EMBED_DIM), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FxRate(Base):
    __tablename__ = "fx_rates"

    currency: Mapped[str] = mapped_column(String(3), primary_key=True)
    per_usd: Mapped[float] = mapped_column(Float)  # units of this currency per 1 USD
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SavedFilter(Base):
    __tablename__ = "saved_filters"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    alert: Mapped[bool] = mapped_column(Boolean, default=False)
    last_checked: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GeoCountry(Base):
    __tablename__ = "geo_countries"

    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    continent: Mapped[str] = mapped_column(String(2))
    currency: Mapped[str | None] = mapped_column(String(3))


class GeoPlace(Base):
    __tablename__ = "geo_places"

    id: Mapped[int] = mapped_column(primary_key=True)  # GeoNames id
    name: Mapped[str] = mapped_column(String(200))
    country_code: Mapped[str] = mapped_column(String(2), index=True)
    admin1: Mapped[str | None] = mapped_column(String(150))
    admin1_code: Mapped[str | None] = mapped_column(String(20))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    population: Mapped[int] = mapped_column(Integer, default=0)


class GeoName(Base):
    """Normalised lookup: every spelling of a place points at it."""

    __tablename__ = "geo_names"

    norm: Mapped[str] = mapped_column(String(200), primary_key=True)
    place_id: Mapped[int] = mapped_column(ForeignKey("geo_places.id", ondelete="CASCADE"), primary_key=True)


# Trigram index on company names supports the company filter.
extensions_sql = [text("CREATE EXTENSION IF NOT EXISTS vector"), text("CREATE EXTENSION IF NOT EXISTS pg_trgm")]
