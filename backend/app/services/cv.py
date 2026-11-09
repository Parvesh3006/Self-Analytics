"""CV analysis and matching. Runs locally: the CV never goes to a cloud model."""
import io
import re
from collections import Counter
from datetime import timedelta

from docx import Document
from pypdf import PdfReader
from sqlalchemy import func, literal, select
from sqlalchemy.orm import Session

from ..filters import Filters, apply_filters
from ..llm import LLMUnavailable, complete_json, embed
from ..models import CVProfile, Job, JobSkill, Skill, utcnow
from ..normalize.skills import extract_skills
from ..normalize.titles import role_family, seniority

MAX_BYTES = 8 * 1024 * 1024
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"\+?\d[\d\s().-]{8,}\d")


class UnreadableCV(ValueError):
    pass


def read_text(filename: str, content: bytes) -> str:
    if len(content) > MAX_BYTES:
        raise UnreadableCV("That file is larger than 8 MB.")
    lower = filename.lower()
    try:
        if lower.endswith(".pdf"):
            text = "\n".join((page.extract_text() or "") for page in PdfReader(io.BytesIO(content)).pages)
        elif lower.endswith(".docx"):
            document = Document(io.BytesIO(content))
            cells = [c.text for t in document.tables for r in t.rows for c in r.cells]
            text = "\n".join([p.text for p in document.paragraphs] + cells)
        elif lower.endswith((".txt", ".md")):
            text = content.decode("utf-8", "ignore")
        else:
            raise UnreadableCV("Please upload a PDF, DOCX or TXT file.")
    except UnreadableCV:
        raise
    except Exception as error:
        raise UnreadableCV("That file could not be read. Is it password protected or damaged?") from error
    text = re.sub(r"[ \t]+", " ", text).strip()
    if len(text) < 150:
        raise UnreadableCV("Almost no text could be read. A scanned image CV needs to be exported as text first.")
    return text


def _years_experience(text: str) -> int | None:
    stated = [int(m) for m in re.findall(r"(\d{1,2})\+?\s*(?:years|yrs)(?:\s+of)?\s+(?:\w+\s+){0,3}?experience", text, re.I) if int(m) < 50]
    if stated:
        return max(stated)
    now = utcnow().year
    spans = re.findall(r"\b((?:19|20)\d{2})\s*(?:-|–|—|to)\s*((?:19|20)\d{2}|present|current|now)\b", text, re.I)
    starts = [int(a) for a, _ in spans if 1980 <= int(a) <= now]
    return now - min(starts) if starts else None


def _title_lines(text: str) -> list[str]:
    hits = []
    for line in text.splitlines()[:150]:
        line = line.strip(" -•|\t")
        if 5 < len(line) < 70 and re.search(r"engineer|developer|scientist|analyst|manager|architect|consultant|designer|administrator|lead\b", line, re.I):
            hits.append(line)
    return hits


def analyze(text: str) -> dict:
    skills = extract_skills(text)
    titles = _title_lines(text)
    families = Counter(role_family(t) for t in titles if role_family(t) != "Other")
    years = _years_experience(text)
    level = seniority(titles[0]) if titles else "Mid / Unspecified"
    if level == "Mid / Unspecified" and years is not None:
        level = "Senior" if years >= 6 else "Junior" if years <= 2 else level
    parsed = {
        "skills": skills, "titles": titles[:6], "target_roles": [f for f, _ in families.most_common(3)], "years_experience": years, "seniority": level,
        "headline": titles[0] if titles else None, "summary": None, "strengths": [],
    }
    # Contact details are removed before the local model reads the CV: it does not need them.
    redacted = PHONE.sub("[phone]", EMAIL.sub("[email]", text))
    try:
        data = complete_json(
            "From this CV, reply with JSON keys: headline (current professional title, under 10 words), summary (two factual sentences, "
            "no praise), strengths (up to 4 short phrases taken from the CV). Use only what the CV states.\n\nCV:\n" + redacted[:6000],
            system="You read CVs and reply with JSON only.", allow_cloud=False,
        )
        parsed.update({k: data[k] for k in ("headline", "summary") if isinstance(data.get(k), str) and data[k]})
        if isinstance(data.get("strengths"), list):
            parsed["strengths"] = [str(s) for s in data["strengths"][:4]]
    except Exception:  # model missing, timed out or returned bad JSON: the deterministic analysis stands on its own
        pass
    return parsed


def create_profile(db: Session, filename: str, content: bytes) -> CVProfile:
    text = read_text(filename, content)
    parsed = analyze(text)
    vectors = embed([f"{parsed.get('headline') or ''}\nSkills: {', '.join(parsed['skills'])}\n{text[:2500]}"])
    label = parsed.get("headline") or filename
    profile = CVProfile(label=label[:200], filename=filename[:300], text=text, parsed=parsed, embedding=vectors[0] if vectors else None)
    db.add(profile)
    db.commit()
    return profile


SEN_ORDER = {"Intern / Graduate": 0, "Junior": 1, "Mid / Unspecified": 2, "Senior": 3, "Lead": 4, "Principal / Staff": 5, "Manager": 4, "Executive": 6}


def _seniority_fit(candidate: str, job: str) -> float:
    if job == "Mid / Unspecified":
        return 0.8
    gap = abs(SEN_ORDER.get(candidate, 2) - SEN_ORDER.get(job, 2))
    return {0: 1.0, 1: 0.7, 2: 0.3}.get(gap, 0.0)


def match_jobs(db: Session, profile: CVProfile, f: Filters, limit: int = 50) -> dict:
    parsed = profile.parsed
    cv_skills = set(parsed.get("skills") or [])
    targets = parsed.get("target_roles") or []
    has_vector = profile.embedding is not None
    skill_ids = list(db.scalars(select(Skill.id).where(Skill.name.in_(cv_skills)))) if cv_skills else []

    overlap = (select(JobSkill.job_id, func.count().label("hits")).where(JobSkill.skill_id.in_(skill_ids or [-1])).group_by(JobSkill.job_id).subquery())
    similarity = (1 - Job.embedding.cosine_distance(profile.embedding)) if has_vector else literal(None)
    stmt = select(Job, func.coalesce(overlap.c.hits, 0).label("hits"), similarity.label("similarity")).outerjoin(overlap, overlap.c.job_id == Job.id)
    stmt = apply_filters(stmt, f).where(Job.is_active.is_(True))
    pool = 600
    if has_vector:
        by_vector = stmt.where(Job.embedding.is_not(None)).order_by(Job.embedding.cosine_distance(profile.embedding)).limit(pool)
        by_skill = stmt.order_by(func.coalesce(overlap.c.hits, 0).desc(), Job.first_seen.desc()).limit(pool)
        rows = {r[0].id: r for r in [*db.execute(by_vector), *db.execute(by_skill)]}.values()
    else:
        rows = db.execute(stmt.order_by(func.coalesce(overlap.c.hits, 0).desc(), Job.first_seen.desc()).limit(pool)).all()
    rows = [r for r in rows if r[1] > 0 or (r[2] is not None and r[2] > 0.5)]

    job_skills: dict[int, list[str]] = {}
    ids = [r[0].id for r in rows]
    if ids:
        for job_id, name in db.execute(select(JobSkill.job_id, Skill.name).join(Skill).where(JobSkill.job_id.in_(ids))):
            job_skills.setdefault(job_id, []).append(name)

    now, scored = utcnow(), []
    for job, _hits, sim in rows:
        wanted = job_skills.get(job.id, [])
        matched = sorted(s for s in wanted if s in cv_skills)
        missing = sorted(s for s in wanted if s not in cv_skills)
        # A posting naming one skill says little, so short lists are discounted.
        coverage = (len(matched) / len(wanted)) * min(1.0, len(wanted) / 4) if wanted else 0.0
        role_fit = 1.0 if job.role_family in targets[:1] else 0.7 if job.role_family in targets else 0.0
        level_fit = _seniority_fit(parsed.get("seniority") or "Mid / Unspecified", job.seniority)
        age_days = (now - (job.posted_at or job.first_seen)).days
        fresh = max(0.0, 1 - age_days / 60)
        if sim is not None:
            semantic = max(0.0, min(1.0, (float(sim) - 0.35) / 0.4))
            score = 0.40 * coverage + 0.30 * semantic + 0.17 * role_fit + 0.08 * level_fit + 0.05 * fresh
        else:
            semantic = None
            score = 0.60 * coverage + 0.25 * role_fit + 0.10 * level_fit + 0.05 * fresh
        reasons = []
        if matched:
            reasons.append(f"You have {len(matched)} of the {len(wanted)} skills it names")
        if role_fit:
            reasons.append(f"Fits your {job.role_family} background")
        if semantic is not None and semantic > 0.6:
            reasons.append("Description is close to your experience")
        if level_fit >= 1 and job.seniority != "Mid / Unspecified":
            reasons.append(f"{job.seniority} level matches yours")
        if level_fit <= 0.3:
            reasons.append(f"Level may not fit: this is {job.seniority}")
        if job.visa_sponsorship:
            reasons.append("Mentions visa sponsorship")
        scored.append({"job": job, "score": round(score * 100), "matched": matched, "missing": missing[:10], "reasons": reasons})
    scored.sort(key=lambda m: m["score"], reverse=True)

    strong = [m for m in scored if m["score"] >= 45][:300]
    gap_counter = Counter(s for m in strong for s in m["missing"])
    by_country: dict[str, list] = {}
    for m in strong:
        key = m["job"].country or "Remote / unspecified"
        by_country.setdefault(key, []).append(m["job"].salary_usd_min)
    markets = sorted(({"country": k, "matches": len(v), "with_salary": sum(1 for s in v if s), "median_usd": _median([s for s in v if s])} for k, v in by_country.items()), key=lambda x: -x["matches"])
    return {
        "matches": scored[:limit], "considered": len(scored), "strong": len(strong), "semantic": has_vector,
        "gaps": [{"skill": s, "jobs": n, "share": round(100 * n / len(strong))} for s, n in gap_counter.most_common(15)] if strong else [],
        "markets": markets[:12],
    }


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def explain_match(profile: CVProfile, job: Job, matched: list[str], missing: list[str]) -> str:
    redacted = PHONE.sub("[phone]", EMAIL.sub("[email]", profile.text))
    prompt = (
        f"CV:\n{redacted[:3500]}\n\nJOB: {job.title} at {job.company_name}\n{(job.description or '')[:3000]}\n\n"
        f"Skills matched: {', '.join(matched) or 'none'}. Skills not found in the CV: {', '.join(missing) or 'none'}.\n\n"
        "In under 120 words, tell this candidate plainly: why they fit, the biggest gap, and one thing to emphasise when applying. "
        "Use only facts from the CV and the job."
    )
    return _local(prompt)


def _local(prompt: str) -> str:
    from ..config import get_settings
    from ..llm import complete

    return complete(prompt, model=get_settings().ollama_assistant_model, allow_cloud=False, temperature=0.3)


__all__ = ["UnreadableCV", "create_profile", "match_jobs", "explain_match", "timedelta"]
