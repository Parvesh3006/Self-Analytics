# Self Analytics — Job Market Intelligence App

## Project goal
A personal web app with an AI agent that:
- Crawls and analyzes user-provided URLs (job boards, job-trend/analysis sites, job-posting sites — worldwide) thoroughly, page by page.
- Also discovers additional data via web search (permitted search APIs, not raw Google scraping).
- Shows a dashboard of current job-market trends with filters: country, state, city, role, skill, remote, salary, date.
- Shows job details and job specifications.
- Includes an in-app AI assistant that answers custom questions over the collected data, with source citations.

> **Maintenance rule:** keep this file current. At the end of any work session, update "Current status", "Yet to be done", "Known issues" and "Work log" so they match reality. Record only what was actually verified, and date the entries.

Companion docs: `README.md` (how to run), `DESIGN.md` (visual system), `PRODUCT.md` (product facts).

---

## Current status (last updated 2026-11-09)

**Built and working locally on real data. Vercel deployment is in progress and not live.** Code is on GitHub (`Parvesh3006/Self-Analytics`, branch `main`, commit `d02de0a`). A full copy of the database is on the user's Neon project (`self-analytics`, Singapore, Free plan), but the app still uses the local database.

### Update 2026-11-09
18,118 jobs and 2,299 companies on both local (301 MB) and Neon (291 MB); 2,606 vectors. United States 12,508, India 1,095, Canada 928, Australia 270, New Zealand 11, no known country 3,306. Only those five countries are kept. Collection is off for Arbeitnow, Delivery Hero, France Travail, MyCareersFuture and Reed because they list jobs elsewhere. The tables below are the 2026-11-08 figures and are out of date.

### Data snapshot
| Measure | Value |
|---|---|
| Open jobs | 25,796 |
| Companies | 3,077 |
| Jobs with a country / a stated salary | 24,039 / 10,804 |
| Jobs with search vectors | 4,000 |
| Stored reports | 12 (Australian Bureau of Statistics) |

Jobs by priority market: United States 8,225; Europe 7,732 (includes the UK and Ireland); Singapore 2,677; United Kingdom 1,673; India 1,071; Canada 725; Ireland 399; **Australia 247; New Zealand 11**. Australia and New Zealand are thin until the Adzuna and Jooble keys are added.

Collection started on 2026-11-08, so there is no real history yet.

### Sources (385 registered: the user's 319 sites + 66 employer boards)
| Status | Count | Meaning |
|---|---|---|
| Collecting (`active`) | 94 | 81 API or feed, 11 crawl, 2 report sites |
| Waiting for first run (`new`) | 138 | 110 crawl, 28 report sites. They run on the schedule or with `run due` |
| Blocked | 68 | Terms, robots.txt, HTTP 401/403, or bot challenge. Not collected, by design |
| Problem (`error`) | 37 | 27 unreachable sites, 10 API sources (see Known issues) |
| Needs API key | 7 | Adzuna, Jooble, Careerjet, USAJOBS, Reed, Findwork, France Travail |
| Not a job feed (`reference`) | 41 | ATS vendor homepages, communities, directories |

Blocked: Akhtaboot, Bayt, BDJobs, Bundesagentur für Arbeit, CareerBuilder, CareerCross, CareerOne, Catho, ClearedJobs, CV-Library, CyberSecurityJobs, DevITjobs, Duunitori, Echojobs, Eluta, FastJobs, Fiverr, Foundit, Glassdoor, Go Jobs, Google Careers, Google Jobs, GulfTalent, Guru, Indeed, Indeed France, InfoJobs Brazil, IrishJobs, I Work for NSW, Jobboom, JobisJob, JobsCentral, JobsDB, JobsDB Thailand, Jobs.ie, JobStreet, JobStreet Malaysia, JobStreet Philippines, Jora, Levels.fyi Jobs, LinkedIn Jobs, Meta Careers, Monster, Naukri, Naukrigulf, Nigel Frank, Oracle Careers, Pracuj.pl, Remote First Jobs, Revolut Careers, r/forhire, r/RemoteJobs, Security Clearance Jobs, SEEK, SEEK Engineering, SimplyHired, Sony Jobs, StepStone, TechJobs.ca, Tesla Careers, Totaljobs, Upwork, Wellfound, Workforce Australia, WorkIndia, Workopolis, XING Jobs, ZipRecruiter.

### Phase status
| Phase | Status |
|---|---|
| 0. Foundation | Done |
| 1. Sources and ingestion | Done, except keyed adapters are untested until keys arrive |
| 2. Crawl agent | Done. Yield is low on JavaScript-heavy sites |
| 3. Normalization | Done (skills use a curated list, see Deviations) |
| 4. Dashboard | Done (no per-country state maps, see Deviations) |
| 5. AI assistant | Done |
| 6. Discovery and insights | Reports and alerts done. Search discovery is written but untested until a search key arrives |
| 7. Hardening | Partial: 57 tests, retries by schedule, saved views, CSV export. No observability |
| Added: CV matching | Done |

### What was verified, and how
- 57 backend tests pass (`pytest`): skills, salary, roles, fingerprints, JSON-LD, location resolver against real GeoNames data.
- Production web build and TypeScript compile. Every page and API route returned 200 in a smoke test.
- Real collection from the no-key APIs and company boards.
- Crawl agent ran on 15 real sites. JSON-LD extraction produced jobs on some (No Fluff Jobs, Kalibrr). On Hays the local model correctly refused to invent a job from category pages.
- Report reader stored 12 ABS pages.
- CV upload with a synthetic DOCX: skills, years and seniority correct, a bad file type rejected, semantic matching ran. The test CV was deleted afterwards.
- Assistant: SQL, vector and CV routes through the web proxy, with citations and token streaming.
- Docker images built. One Celery task ran successfully inside the worker container.
- Markets, CV, Skills, Jobs, Job detail, Sources and Ask AI inspected by screenshot at desktop; Markets also at phone width. Design detector found no issues.

### Not verified yet
- All 7 keyed adapters, and search discovery (`discover`).
- The full `docker compose --profile app up`: only image builds and one worker task were tested. Celery Beat, SearXNG, and the API and web containers have not been run.
- Crawl4AI browser rendering (only installed in the Docker image; the native run has no browser).
- PDF CV upload (only DOCX tested), the "Explain this match" button, `APP_PASSWORD` protection, cloud LLM fallback.
- Filter popovers and other interactions were not clicked through in a browser; only API routes and rendered pages were checked.

---

## Yet to be done

**Waiting on the user**
1. Supply API keys (table below).

**Next steps once keys arrive**
2. Add keys to `.env`, restart the API, run `python -m app.cli run api`, and fix any adapter that fails.
3. Run `python -m app.cli discover` to find more employer boards.

**Should do**
4. Finish vectors: `python -m app.cli embed --limit 26000` (only 4,000 of about 26,000 are done; this limits CV matching and assistant job search).
5. Run the first crawl and report pass: `run due`, or start the Docker schedule. Stop the native servers first, since they use the same ports.
6. Test the items under "Not verified yet".
7. Replace wrong employer board tokens (see Known issues).

**Could do**
8. Per-country state and province maps.
9. Handle JavaScript-heavy recruiter sites better (check Crawl4AI rendering in Docker).
10. Vercel deployment (plan in README.md). Decide on the Neon free-tier size limit first.
11. `git init` and a first commit, when the user asks.
12. Observability, and a one-command start script for Windows.
13. Independent design finish review: it was done in-thread, not by the separate reviewer.

### API keys
Status on 2026-11-09: tested and working: Findwork, Reed, USAJOBS, Jooble (real runs), Tavily (one search; `discover` not run yet), Groq through `llm.py` with Ollama off (`LLM_FALLBACK=groq`). Careerjet and France Travail both require a live website URL, so they wait for the Vercel deployment. Adzuna is held back for cost. Gemini, OpenRouter and Brave are not needed. `APP_PASSWORD` must be set before hosting. The Neon connection string is in `.env.neon` (git-ignored).

Jooble does not fill Australia or New Zealand: a live "software engineer / Australia" search returned a total of 11 results, and the run added 23 Australian jobs and no New Zealand jobs. `au.` and `nz.jooble.org` returned 403 for this key. Adzuna remains the likely route for those two markets.

Vercel plan (not built yet): one project using Services, Next.js in `web/` and FastAPI in `backend/`, region `sin1`, on the user's own Vercel account. The connected Vercel and Neon tools belong to a different account (Buildify), so they cannot see this project. Needed first: `vercel.json`, make `data/taxonomy/skills.txt` available to the backend bundle, smaller database pool. Whether Hobby allows Services is unconfirmed. Collection stays on the laptop.

Set in `.env`. Pricing notes from 2026-11-09:
- **Adzuna is paid.** The sign-up page the user saw gives 25 test calls until activation, then £8/month for 5,000 calls a month and 500 a day. A full `adzuna` adapter run is up to 160 calls (16 countries x 2 categories x 5 pages), so a normal run would use up the test calls. The user has not decided whether to pay.
- **Brave no longer has a free request tier**, per third-party reports: $5 of monthly credits, about 1,000 queries. Tavily is reported at 1,000 free credits a month with no card, so try Tavily first.
- Jooble, USAJOBS and Findwork are reported as free keys, and Careerjet as free for non-commercial use, all from third-party pages. Reed and France Travail were not confirmed. Check each official page when signing up.

| Priority | Service | Sign up | Setting(s) | Adds |
|---|---|---|---|---|
| 1 | Adzuna | developer.adzuna.com | `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | AU, NZ, CA, US, IN, GB, SG, Europe |
| 2 | Jooble | jooble.org/api/about | `JOOBLE_API_KEY` | All priority markets, including Ireland |
| 3 | Careerjet | careerjet.com/partners | `CAREERJET_API_KEY` | 11 countries |
| 4 | Reed | reed.co.uk/developers | `REED_API_KEY` | UK |
| 5 | USAJOBS | developer.usajobs.gov | `USAJOBS_EMAIL`, `USAJOBS_API_KEY` | US government |
| 6 | Findwork | findwork.dev/developers | `FINDWORK_API_KEY` | Developer jobs |
| 7 | France Travail | francetravail.io | `FRANCETRAVAIL_CLIENT_ID`, `FRANCETRAVAIL_CLIENT_SECRET` | France |
| 8 | Brave or Tavily | brave.com/search/api, tavily.com | `BRAVE_API_KEY` or `TAVILY_API_KEY` | Employer board discovery |
| 9 (optional) | Groq or Gemini | console.groq.com, aistudio.google.com | `GROQ_API_KEY` or `GEMINI_API_KEY`, plus `LLM_FALLBACK` | Cloud AI for public data; needed if hosted |

Never paste keys into chat. Never commit `.env`.

---

## Known issues
- **Failing API sources (10):** The Muse (API returned 403, then 404). Kubernetes Jobs (feed timed out). Employer board tokens that were guessed and no longer exist or were wrong: Airwallex, Canva, HashiCorp, Rippling, SafetyCulture (Greenhouse); Atlassian, Mistral AI, Plaid (Lever). Those employers may use another system. Separately, Bundesagentur für Arbeit's API returned 403, so it is marked blocked.
- **Unreachable sites (27):** AMD Careers, Android Jobs, Apec, Australian Engineering Jobs, Careers in Energy, Cooper Lomaz, FlexJobs, GOV.UK Find a Job, Graduate Opportunities, GraduatePrograms, IamExpat Jobs, Jobs.com.au, ML Jobs, Neuvoo, OzJobs, PHP Jobs, PNet, PublicJobs, Rail Careers, Remote.co, Ruby Now, SR2, Talent Street, Tasmanian Government Careers, TimesJobs, Toozly, Work in Paradise. Probably closed, moved, or refusing the connection. Worth checking the Australian ones by hand.
- **Reachable but no jobs read:** Booking.com, Deel, Dell, GermanTechJobs, Hasjob, Hays IT Australia, Hired, HP, Ignite, Jobspresso, KDnuggets, Kraken, Peoplebank, SwissDevJobs, Visa, Welcome to the Jungle. Mostly JavaScript listings, or a board with no open jobs.
- **Source mix skews the data:** Singapore is high because MyCareersFuture is a full national feed, and it includes many non-tech jobs. US counts lean toward employers with public boards. Counts are collected postings, never market totals.
- **Trends are not reliable yet:** history began 2026-11-08. The UI labels them as early hints for about four weeks.
- **Salary data:** self-reported figures can be wrong, so medians need 5+ postings, and annual USD over 800k or under 3k is discarded.
- **Local model citations:** an earlier run mislabelled one citation. Evidence items now carry their own numbers, but a small model can still err.
- **Machine load:** 16 GB RAM. Starting Docker Desktop also starts the user's other projects (`arn_*`, `cvat_*`), which take several GB. Leave them alone unless the user says otherwise.

---

## How it runs (operational facts)
- URLs: web http://127.0.0.1:3100, API http://127.0.0.1:8100. Host ports: Postgres 5544, Redis 6380, SearXNG 8888 (5433, 3000, 8080 are used by other projects here).
- **Always use `127.0.0.1`, never `localhost`.** On this machine `localhost` caused a 130-second IPv6 timeout on database connections.
- **Docker CLI:** `C:\windows\system32\docker` is a 0-byte file that shadows the real one. Use `C:\Program Files\Docker\Docker\resources\bin\docker.exe`.
- Native services: start the database with Docker, then uvicorn and `next start` (commands in README.md). Stop whatever holds port 3100 before running `npm run build`, or the old server serves broken CSS.
- Celery is unsupported on Windows, so native mode runs background tasks in a thread (`TASK_MODE=thread`, the default). Docker uses `TASK_MODE=celery`.
- Scheduling is overdue-based: Beat dispatches every 30 minutes, so a sleeping laptop catches up. APIs every 24 h, crawls every 168 h, reports every 720 h.
- Ollama runs natively. Models installed: `qwen3:4b`, `qwen3:8b`, `bge-m3` (plus the user's existing `devstral`).
- Python: `backend/.venv`. CLI from `backend/`: `python -m app.cli bootstrap | probe | run <due|api|crawl|jsonld|insight|name> | embed | discover | maintain`.

### Code map
| Path | Purpose |
|---|---|
| `data/sources/registry.txt`, `boards.csv` | Source list with strategy; employer boards |
| `data/taxonomy/skills.txt` | Skill names and aliases |
| `backend/app/adapters/` | `public.py` (no key), `keyed.py`, `ats.py`, `base.py` |
| `backend/app/crawl/` | `fetcher.py` (robots, delay), `extract.py` (JSON-LD, LLM), `graph.py` (LangGraph) |
| `backend/app/normalize/` | `geo.py`, `skills.py`, `salary.py`, `titles.py`, `text.py` |
| `backend/app/services/` | `ingest.py`, `sources.py`, `cv.py`, `assistant.py`, `discovery.py`, `embeddings.py` |
| `backend/app/api/` | `market.py`, `jobs.py`, `admin.py` |
| `backend/app/filters.py`, `llm.py`, `models.py`, `tasks.py`, `cli.py` | Shared filters, LLM layer, schema, Celery, CLI |
| `web/src/app/` | Pages: `/`, `/cv`, `/skills`, `/jobs`, `/jobs/[id]`, `/assistant`, `/reports`, `/sources` |
| `web/src/components/` | `shell`, `filter-bar`, `facet`, `postmark`, `charts`, `ui` |

### Data and product rules (keep these)
- CV text never reaches a cloud model (`allow_cloud=False`), embeddings are local only, and contact details are redacted before the local model reads a CV.
- Never bypass CAPTCHAs or bot protection. A refusal marks the source blocked.
- Reports are never counted as vacancies. Hacker News comments count only if they read as a job post.
- Salary medians need at least 5 postings. Trends use share of postings, weeks under 25 postings are hidden, and the unfinished current week is excluded.
- Adzuna's modelled salaries are ignored; only advertised pay counts. A bare "$" means the local dollar in AU, CA, NZ, SG and HK.
- A company naming itself is not a skill signal ("Datadog" on Datadog's own ads).

### Deviations from the original plan
| Plan | Actual | Why |
|---|---|---|
| ESCO taxonomy | Curated `skills.txt` | ESCO's long phrase labels match poorly against postings |
| Country choropleth maps | World map plus ranked state and city lists | Not built yet |
| Fingerprint + embedding dedupe | Fingerprint + fuzzy title match within company and city | Works without vectors |
| Pandas and SQL views | Direct SQL queries | Pandas was not needed |
| shadcn/ui CLI components | Hand-written components in the same pattern, on Radix and cmdk | To match the Airmail design |
| Ollama in Docker | Native on Windows | Direct GPU use, outside the WSL memory cap |
| Crawl4AI for every fetch | httpx first, browser only for nearly empty pages | Far less memory on 16 GB |

---

## Work log

### 2026-11-07
Planning. Hardware detected, cloud fallback answered.

### 2026-11-08
- Received the URL list, priority markets, the CV feature request, and the Vercel intent. User chose: single user, no login; three equal main jobs; **Airmail** visual direction.
- Built the whole stack: registry and probe of 319 sites, 27 adapters, crawl agent, normalizers, ingestion, CV matching, assistant, 8 pages, Docker setup.
- Downloaded GeoNames (171,811 places) and three Ollama models.
- Bugs found by testing and fixed: `localhost` 130 s IPv6 timeout; CV upload blocking the server; "US$" read as SGD and "CA$" as AUD; bare "$" treated as USD outside the US; Singapore losing its city; several location formats; Cloudflare locations hidden in the office field; duplicate check rescanning all sources; LangGraph node name clash in the assistant; Redis library mismatch that crashed Celery (now `celery==5.6.*`, `redis>=6.1,<7`); map stripe from countries crossing the date line; company names counted as skills; meaningless "+3113%" weekly change; medians from two postings; incomplete weeks reading as collapsing demand.
- All job data was wiped and recollected once after the location and salary fixes.
- Removed 2,498 false company-name skills (a run started before the fix, so this was done twice):

```sql
DELETE FROM job_skills js USING jobs j, skills s
WHERE js.job_id = j.id AND js.skill_id = s.id AND s.name ~ '^[A-Za-z]{5,}$'
  AND regexp_replace(lower(j.company_name), '[^a-z0-9]+', ' ', 'g') ~ ('\m' || lower(s.name) || '\M');
```

- The web server had stopped after the session's last check, because it was tied to a shell that ended. It was restarted as a detached process. `Get-NetTCPConnection` and `netstat` proved unreliable for checking port 3100 here; use `curl http://127.0.0.1:3100/`.

### 2026-11-09
- User confirmed Vercel hosting, added API keys, created the Neon project, and pushed the first commit to GitHub.
- Adzuna found to be paid. Brave's free tier reported gone, so Tavily is used.
- Fixed the Groq model in `llm.py` (the old name no longer exists; now `qwen/qwen3.8-27b`). Included in the first commit.
- Real runs added new jobs: Findwork 1,710, Reed 3,098, USAJOBS 4,075, Jooble 1,125.
- Copied the database to Neon with `pg_dump` in a single transaction and compared row counts for every table.
- Small gap seen: "Italian Republic" and "Kingdom of Spain" from Jooble do not resolve to a country.
- User decision: closed jobs are permanently deleted, replacing "expired jobs are kept as history". `delete_closed` in `ingest.py` replaces `expire_stale`. User rule (final): delete when the deadline passed more than a day ago, or when the employer removed the job. Removal is only provable on full-list boards (`FULL_LIST_ADAPTERS`: missing from `ABSENT_RUNS` = 2 later `ok` runs with `seen > 0`). A job known only from search or "latest" feeds is deleted only by deadline. It runs from `maintain` (daily under Celery Beat; native mode needs `python -m app.cli maintain`). Tested in a rolled-back transaction on the local database. Not pushed yet.
- User decision: keep only US, AU, IN, CA, NZ. `delete_outside_markets` removed 17,552 jobs from local and Neon, and `Ingestor.add` refuses other countries. The user chose to keep jobs with no known country (3,306, mostly worldwide remote), because remote work matters to them. `geo_*` tables are kept because the resolver needs them to recognise and refuse other countries.

---

## Key design decisions (from analysis)

1. **Legality / ToS** — LinkedIn, Indeed, Glassdoor prohibit scraping and use heavy bot protection; scraping Google SERPs violates Google ToS. → Use a **source adapter** per source with priority: official API > structured data > polite crawl. **No CAPTCHA/anti-bot bypass.** Blocked sources are flagged as "blocked" in the dashboard.
2. **Structured data first** — many job pages embed schema.org `JobPosting` JSON-LD. Extract that deterministically first; use the LLM only for unstructured pages (5–10× less LLM compute).
3. **Free job APIs** cover most volume: Adzuna, Jooble, USAJobs, Reed (UK), Arbeitnow (EU), Remotive, RemoteOK, The Muse, HN "Who's Hiring" (Algolia API), and ATS public boards (Greenhouse, Lever, Ashby, Workable).
4. **Search discovery** — self-hosted SearXNG + Brave Search API / Tavily free tiers. Avoid relying on Google Custom Search JSON API (closing to new customers).
5. **Two pipelines by source type** — job boards/posting sites → structured `jobs` table; trend/report sites → summarized `insights` (RAG for the assistant).
6. **Location normalization** — GeoNames dataset so country/state/city filters work ("Bengaluru" = "Bangalore, KA").
7. **Deduplication** — fingerprint (normalized title + company + location) + embedding similarity, since the same job appears on multiple boards.
8. **Local LLM throughput** — CPU-only 7–8B ≈ 10–30 s/page. Use a small Qwen model for extraction, a medium one for the assistant; optional cloud-LLM fallback for bulk crawls. Model sizes depend on user's GPU VRAM.
9. **Windows** — Celery isn't officially supported on Windows → run everything in **Docker Compose on WSL2**.
10. **Browser Use dropped for v1** — Crawl4AI already drives Playwright. Add Browser Use later only for complex search-form sites.
11. **Multilingual** — worldwide sources → multilingual embeddings (bge-m3); Qwen handles multilingual extraction.
12. **"Analyze completely"** is implemented as bounded crawls: per-source depth/page/path limits, robots.txt respected, rate limiting, incremental re-crawl (ETag / Last-Modified / content hash).

---

## Final tech stack

| Layer | Choice |
|---|---|
| Frontend | Next.js (App Router) + Tailwind CSS + shadcn/ui + TanStack Table/Query |
| Charts | Apache ECharts (incl. world/country choropleth maps) |
| Backend API | FastAPI + SQLAlchemy + Alembic; SSE streaming for chat |
| Agent orchestration | LangGraph (crawl agent + assistant agent) |
| Crawling | Crawl4AI (Playwright under the hood) |
| Source adapters | API → JSON-LD → LLM extraction |
| Search discovery | SearXNG (self-hosted) + Brave / Tavily free tier |
| LLM runtime | Ollama — Qwen3 small (extraction) + Qwen3 medium (assistant); optional cloud fallback |
| Embeddings | bge-m3 via Ollama |
| Database | PostgreSQL 16 + pgvector |
| Normalization | GeoNames (locations), ESCO taxonomy (skills/titles), FX rates (salaries) |
| Jobs / scheduling | Celery + Celery Beat + Redis |
| Analytics | SQL views + Pandas for trend computations |
| Runtime | Docker Compose on WSL2 |

---

## Architecture

```
[User URLs] + [Search discovery] + [Job APIs]
        │
  LangGraph CRAWL AGENT (Celery scheduled)
  Plan → Fetch (Crawl4AI) → Classify page (listing/detail/article/irrelevant)
       → Extract (JSON-LD → LLM) → Normalize (geo, skills, salary)
       → Dedupe → Store (Postgres + embeddings)
        │
  PostgreSQL: jobs, companies, locations, skills, sources, crawl_runs, insights
        │
  FastAPI ── Dashboard API (filters: country/state/city/role/skill/remote/salary/date)
          └─ LangGraph ASSISTANT (tool-routing):
               • SQL tool      → aggregate questions ("How many React jobs in Germany this month?")
               • Vector search → semantic questions ("roles like mine that sponsor visas")
               • Insights RAG  → trend-article questions
             Answers cite source URLs.
```

---

## Phased plan

| Phase | Deliverable | Est. |
|---|---|---|
| 0. Foundation | Docker Compose (Postgres+pgvector, Redis, Ollama, SearXNG), FastAPI skeleton, Next.js shell, DB schema | 2–3 days |
| 1. Sources & ingestion | Source manager UI (add URL, auto-detect type), API adapters (Adzuna, Greenhouse/Lever, Remotive…), JSON-LD extractor | 1 week |
| 2. Crawl agent | LangGraph crawl graph, Crawl4AI integration, LLM extraction fallback, scheduling, crawl-status page | 1–1.5 weeks |
| 3. Normalization | GeoNames location resolver, skills/title taxonomy, salary normalization, dedupe | 1 week |
| 4. Dashboard | Filters, KPIs, trend charts, world/country map, top skills/companies/roles, job table + detail view | 1 week |
| 5. AI assistant | Chat UI (streaming), SQL / vector / insights tools, source citations | 1 week |
| 6. Discovery & insights | Search discovery, trend-article summarization, alerts ("new jobs matching X") | 1 week |
| 7. Hardening | Tests, observability, retries, saved filters, CSV export | ongoing |

MVP with real data on the dashboard = Phases 0–4 (~4–5 weeks part-time).

---

## Questions asked during planning (all answered)

1. The list of URLs. 2. Hardware. 3. Whether a cloud LLM fallback is acceptable. 4. Priority countries and roles.

Still unanswered, and defaulted: salary display currency (a selector in the app, default USD). Data retention was answered on 2026-11-09: closed jobs are deleted.

## Answers

### Q2 — Hardware (detected 2026-11-07)
- GPU: NVIDIA GeForce RTX 4060 Laptop, **8 GB VRAM** (+ Intel UHD iGPU)
- CPU: Intel i7-13620H (10 cores / 16 threads)
- RAM: **16 GB** (tight with Docker + Postgres + Playwright + Ollama → keep crawl concurrency low, cap Docker/WSL memory)
- Disk: ~322 GB free on C:

Model plan for this hardware (Q4 quantization via Ollama):
- Extraction: `qwen3:4b` (~2.5–3 GB VRAM, fast)
- Assistant: `qwen3:8b` (~5–5.5 GB VRAM) — 14B+ won't fit fully in 8 GB
- Embeddings: `bge-m3` (~1.2 GB)
- Not all loaded at once; Ollama swaps models as needed.

### Q3 — Cloud LLM fallback
User: **anything free of cost is fine.** → Local Ollama is the default; free-tier cloud APIs (e.g. Google Gemini free tier, Groq free tier, OpenRouter free models) as optional fallback via a provider-agnostic LLM layer. Caveats: free tiers have rate/daily limits and may use inputs for training — OK for public job data; keep personal info out of cloud calls.

### Q1 — URLs (answered 2026-11-08)
User supplied about 340 URLs (319 after removing duplicates): global, tech, remote, AI/data, security, DevOps, freelance, regional boards, ATS platforms, employer career sites, labour statistics, data platforms, communities, and an Australia-specific list. They live in `data/sources/` and are classified per decision 1.

### Q4 — Priority markets (answered 2026-11-08)
Superseded on 2026-11-09: only USA, Australia, India, Canada and New Zealand, each down to every state and city. Other countries are not stored. (Originally also UK, Europe, Singapore and Ireland, with worldwide coverage.)

### Other decisions (2026-11-08)
- Single user, no login. Equal main jobs: compare countries, find best jobs from a CV, track skill trends.
- New feature: CV/resume drop zone; AI ranks suitable jobs and explains fit. CV data stays local by default.
- Ollama runs natively on Windows (uses GPU directly, stays outside the WSL memory cap), not in Docker.
- Hosting: the user confirmed Vercel on 2026-11-09 (not deployed yet). Neon's free plan is 1 GB per project per its FAQ of 2026-10-01, and pgvector is on every plan. Local database size was not measured because Postgres did not respond on 2026-11-09, so whether the data fits is unknown.
- Earlier note: probably Vercel later. Vercel can host the web app/API only; crawling, Celery and local LLMs cannot run there → production plan is Vercel + Neon (Postgres/pgvector) + ingestion run elsewhere + cloud LLM free tier.
