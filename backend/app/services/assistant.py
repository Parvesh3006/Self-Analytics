"""LangGraph assistant. Routes a question to tools over the collected data; every answer cites what it used."""
import re
from dataclasses import dataclass, field
from typing import TypedDict
from urllib.parse import urlencode

from langgraph.graph import END, StateGraph
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..filters import EUROPE_CODE, Filters, apply_filters
from ..llm import LLMUnavailable, embed, stream
from ..models import CVProfile, GeoCountry, Insight, InsightChunk, Job, JobSighting, JobSkill, Skill, Source
from ..normalize.geo import COUNTRY_ALIASES
from ..normalize.skills import CASE_SENSITIVE, load_taxonomy
from ..normalize.text import norm_key
from ..normalize.titles import role_family
from .cv import match_jobs

NOT_ROLES = {"Other", "Engineering (other)", "Operations", "Business Analysis"}
INSIGHT_WORDS = re.compile(r"\b(report|reports|forecast|outlook|according to|shortage|shortages|unemployment|statistics|labou?r force|future of|policy|projection|skills priority)\b", re.I)
AGG_WORDS = re.compile(r"\b(how many|number of|count|average|median|salary|salaries|pay|paying|top|most|compare|which (country|city|cities|state|skill|skills|role|roles|company|companies)|demand|in demand|trend|rising|popular)\b", re.I)
CV_WORDS = re.compile(r"\b(my (cv|resume|profile|skills)|suit me|fit me|for me|best for my|should i (apply|learn))\b", re.I)


@dataclass
class Evidence:
    text: str
    citations: list[dict] = field(default_factory=list)


class State(TypedDict, total=False):
    question: str
    filters: Filters
    tools: list[str]
    evidence: list[Evidence]
    uses_cv: bool


def parse_question(db: Session, question: str) -> Filters:
    f = Filters()
    key = f" {norm_key(question)} "
    for code, name in db.execute(select(GeoCountry.code, GeoCountry.name)):
        if f" {norm_key(name)} " in key and code not in f.country:
            f.country.append(code)
    for alias, code in COUNTRY_ALIASES.items():
        if len(alias) > 2 and f" {alias} " in key and code not in f.country:
            f.country.append(code)
    if re.search(r"\bUK\b", question) and "GB" not in f.country:
        f.country.append("GB")
    if re.search(r"\b(USA|US)\b", question) and "US" not in f.country:
        f.country.append("US")
    if " europe " in key or " european " in key:
        f.country.append(EUROPE_CODE)
    for skill in load_taxonomy():
        strict = skill.name in CASE_SENSITIVE or len(skill.name) <= 2
        if strict:
            if skill.pattern.search(question):
                f.skill.append(skill.name)
        elif re.search(rf"(?<![\w+#]){re.escape(skill.name)}(?![\w+#])", question, re.I):
            f.skill.append(skill.name)
    role = role_family(question)
    if role not in NOT_ROLES:
        f.role.append(role)
    if re.search(r"\bremote\b", question, re.I):
        f.workplace = "remote"
    if re.search(r"\bhybrid\b", question, re.I):
        f.workplace = "hybrid"
    if re.search(r"\bvisa|sponsor", question, re.I):
        f.visa = True
    if re.search(r"this week|past week|last week", question, re.I):
        f.days = 7
    elif re.search(r"this month|past month|last month", question, re.I):
        f.days = 30
    match = re.search(r"last (\d{1,3}) days", question, re.I)
    if match:
        f.days = int(match.group(1))
    return f


def _filter_label(f: Filters) -> str:
    parts = [*f.country, *f.role, *f.skill]
    if f.workplace:
        parts.append(f.workplace)
    if f.days:
        parts.append(f"last {f.days} days")
    if f.visa:
        parts.append("mentions visa sponsorship")
    return ", ".join(parts) or "all collected jobs"


def _jobs_link(f: Filters) -> str:
    params = {k: v for k, v in {
        "country": ",".join(f.country), "role": ",".join(f.role), "skill": ",".join(f.skill), "workplace": f.workplace, "days": f.days}.items() if v}
    return "/jobs?" + urlencode(params)


def sql_tool(db: Session, f: Filters) -> Evidence:
    total = db.scalar(apply_filters(select(func.count()).select_from(Job), f)) or 0
    salary = db.execute(apply_filters(select(func.percentile_cont(0.5).within_group(Job.salary_usd_min), func.count(Job.salary_usd_min)), f)).one()

    def top(column, n=8):
        rows = db.execute(apply_filters(select(column, func.count()).where(column.is_not(None)), f).group_by(column).order_by(func.count().desc()).limit(n)).all()
        return ", ".join(f"{name} ({count})" for name, count in rows) or "none"

    skills = db.execute(apply_filters(select(Skill.name, func.count()).join(JobSkill, JobSkill.skill_id == Skill.id).join(Job, Job.id == JobSkill.job_id), f)
                        .group_by(Skill.name).order_by(func.count().desc()).limit(12)).all()
    source_rows = db.execute(apply_filters(select(Source.name, Source.url, func.count(func.distinct(Job.id))).join(JobSighting, JobSighting.source_id == Source.id).join(Job, Job.id == JobSighting.job_id), f)
                             .group_by(Source.name, Source.url).order_by(func.count(func.distinct(Job.id)).desc()).limit(4)).all()
    median_text = f"Median advertised salary: US${salary[0]:,.0f} a year, from the {salary[1]} postings that state pay." if salary[0] else "No postings in this set state a usable salary."
    text = (
        f"Filters: {_filter_label(f)}. Open postings collected: {total}. {median_text} "
        f"Top countries: {top(Job.country)}. Top cities: {top(Job.city)}. Top roles: {top(Job.role_family)}. Top companies: {top(Job.company_name)}. "
        f"Top skills: {', '.join(f'{n} ({c})' for n, c in skills) or 'none'}."
    )
    citations = [{"title": f"Collected jobs: {_filter_label(f)}", "url": _jobs_link(f), "kind": "database"}]
    citations += [{"title": f"{name} ({count} of these jobs)", "url": url, "kind": "source"} for name, url, count in source_rows]
    return Evidence(text, citations)


def _job_evidence(db: Session, jobs: list[Job]) -> Evidence:
    lines, citations = [], []
    for index, job in enumerate(jobs):
        pay = f", about US${job.salary_usd_min:,.0f} a year" if job.salary_usd_min else ""
        place = ", ".join(filter(None, [job.city, job.state, job.country])) or job.location_raw or "location not stated"
        lines.append(f"{{c{index}}} {job.title} at {job.company_name} ({place}, {job.workplace}{pay}): {(job.description or '')[:280]}")
        citations.append({"title": f"{job.title}, {job.company_name}", "url": job.apply_url or f"/jobs/{job.id}", "kind": "job", "job_id": job.id})
    return Evidence("\n".join(lines) or "No matching postings were found.", citations)


def vector_tool(db: Session, question: str, f: Filters) -> Evidence:
    vectors = embed([question])
    stmt = apply_filters(select(Job), f)
    if vectors:
        stmt = stmt.where(Job.embedding.is_not(None)).order_by(Job.embedding.cosine_distance(vectors[0]))
    else:
        terms = " OR ".join(w for w in re.findall(r"[A-Za-z+#.]{3,}", question)[:10])
        stmt = stmt.where(Job.search.op("@@")(func.websearch_to_tsquery("simple", terms))).order_by(Job.first_seen.desc())
    return _job_evidence(db, list(db.scalars(stmt.limit(8))))


def insights_tool(db: Session, question: str) -> Evidence:
    vectors = embed([question])
    if vectors:
        rows = db.execute(select(InsightChunk.text, Insight.title, Insight.url, Source.name).join(Insight, Insight.id == InsightChunk.insight_id).join(Source, Source.id == Insight.source_id)
                          .where(InsightChunk.embedding.is_not(None)).order_by(InsightChunk.embedding.cosine_distance(vectors[0])).limit(5)).all()
    else:
        terms = " | ".join(w for w in re.findall(r"[A-Za-z]{4,}", question)[:10]) or "labour"
        rows = db.execute(select(InsightChunk.text, Insight.title, Insight.url, Source.name).join(Insight, Insight.id == InsightChunk.insight_id).join(Source, Source.id == Insight.source_id)
                          .where(func.to_tsvector("simple", InsightChunk.text).op("@@")(func.to_tsquery("simple", terms))).limit(5)).all()
    return Evidence("\n".join(f"{{c{i}}} From {r.name}: {r.text[:700]}" for i, r in enumerate(rows)) or "No stored report covers this.",
                    [{"title": f"{r.title} ({r.name})", "url": r.url, "kind": "report"} for r in rows])


def cv_tool(db: Session, f: Filters) -> Evidence:
    profile = db.scalars(select(CVProfile).order_by(CVProfile.created_at.desc()).limit(1)).first()
    if profile is None:
        return Evidence("The user has not uploaded a CV yet. Tell them to add one on the My CV page.", [{"title": "My CV", "url": "/cv", "kind": "database"}])
    result = match_jobs(db, profile, f, limit=8)
    evidence = _job_evidence(db, [m["job"] for m in result["matches"]])
    gaps = ", ".join(f"{g['skill']} (in {g['share']}% of strong matches)" for g in result["gaps"][:8]) or "none found"
    evidence.text = (f"CV skills: {', '.join((profile.parsed.get('skills') or [])[:25])}. Strong matches: {result['strong']}. Most common missing skills: {gaps}.\nBest matching postings:\n" + evidence.text)
    return evidence


def build_graph(db: Session):
    def route(state: State) -> State:
        q = state["question"]
        tools: list[str] = []
        if CV_WORDS.search(q):
            tools.append("cv")
        if INSIGHT_WORDS.search(q):
            tools.append("insights")
        if AGG_WORDS.search(q):
            tools.append("sql")
        if not tools:
            tools.append("vector")
        return {"tools": tools, "filters": parse_question(db, q), "uses_cv": "cv" in tools}

    def run_tools(state: State) -> State:
        evidence = []
        for tool in state["tools"]:
            if tool == "sql":
                evidence.append(sql_tool(db, state["filters"]))
            elif tool == "vector":
                evidence.append(vector_tool(db, state["question"], state["filters"]))
            elif tool == "insights":
                evidence.append(insights_tool(db, state["question"]))
            elif tool == "cv":
                evidence.append(cv_tool(db, state["filters"]))
        return {"evidence": evidence}

    graph = StateGraph(State)
    graph.add_node("route", route)
    graph.add_node("run_tools", run_tools)
    graph.set_entry_point("route")
    graph.add_edge("route", "run_tools")
    graph.add_edge("run_tools", END)
    return graph.compile()


SYSTEM = (
    "You are the assistant inside a personal job-market app. Answer only from the EVIDENCE. Cite claims with the bracketed numbers given, like [1]. "
    "If the evidence does not answer the question, say so plainly. Never invent figures, employers or trends. These counts cover collected postings, "
    "not the whole job market, so never present them as market totals. Be concise and plain."
)


def answer_events(db: Session, question: str, history: list[dict]):
    """Yield (event, payload) tuples for the streaming endpoint."""
    yield "status", {"text": "Searching collected data"}
    state = build_graph(db).invoke({"question": question})
    citations, blocks = [], []
    for evidence in state["evidence"]:
        text, numbers = evidence.text, []
        for index, citation in enumerate(evidence.citations):
            citations.append({**citation, "n": len(citations) + 1})
            numbers.append(f"[{len(citations)}]")
            text = text.replace(f"{{c{index}}}", f"[{len(citations)}]")  # each item carries its own citation number
        blocks.append(f"{text}\n(Cite as: {' '.join(numbers) or 'none'})")
    yield "sources", {"citations": citations, "tools": state["tools"]}
    context = "".join(f"{m['role']}: {m['content'][:400]}\n" for m in history[-4:])
    prompt = f"{('Conversation so far:' + chr(10) + context) if context else ''}EVIDENCE:\n" + "\n\n".join(blocks) + f"\n\nQUESTION: {question}"
    yield "status", {"text": "Writing the answer"}
    try:
        for token in stream(prompt, system=SYSTEM, allow_cloud=not state["uses_cv"]):
            yield "token", {"text": token}
    except LLMUnavailable:
        yield "token", {"text": "No language model is available right now, so here is the raw evidence:\n\n" + "\n\n".join(blocks)}
    yield "done", {}
