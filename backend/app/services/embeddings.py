from sqlalchemy import case, select, update
from sqlalchemy.orm import Session

from ..llm import embed
from ..models import Job, JobSkill, Skill

PRIORITY = ["AU", "CA", "US", "IN", "GB", "SG", "NZ", "IE"]


def job_text(title: str, company: str, skills: list[str], description: str) -> str:
    return f"{title} at {company}\nSkills: {', '.join(skills)}\n{(description or '')[:1200]}"


def embed_pending(db: Session, limit: int = 2000, batch: int = 32) -> int:
    """Embed jobs without vectors, priority markets and newest first. Returns the count embedded."""
    done = 0
    rank = case((Job.country_code.in_(PRIORITY), 0), else_=1)
    while done < limit:
        rows = db.execute(select(Job.id, Job.title, Job.company_name, Job.description).where(Job.embedding.is_(None), Job.is_active.is_(True))
                          .order_by(rank, Job.first_seen.desc()).limit(batch)).all()
        if not rows:
            break
        skills: dict[int, list[str]] = {}
        for job_id, name in db.execute(select(JobSkill.job_id, Skill.name).join(Skill).where(JobSkill.job_id.in_([r.id for r in rows]))):
            skills.setdefault(job_id, []).append(name)
        vectors = embed([job_text(r.title, r.company_name, skills.get(r.id, []), r.description) for r in rows])
        if vectors is None:
            break
        for row, vector in zip(rows, vectors):
            db.execute(update(Job).where(Job.id == row.id).values(embedding=vector))
        db.commit()
        done += len(rows)
    return done
