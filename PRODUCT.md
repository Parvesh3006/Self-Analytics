# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Set in CLAUDE.md: Next.js App Router, Tailwind, shadcn/ui, TanStack Table/Query, Apache ECharts; FastAPI, LangGraph, Crawl4AI, Celery, PostgreSQL + pgvector. Local first; the web app may later move to Vercel.

## Users

One person: the owner, a job seeker looking across borders. They use it often, on a laptop, to decide where to look, what to apply to and what to learn next. There are no accounts and no other audiences.

## Product Purpose

Turn scattered worldwide job postings and labour-market reports into one trustworthy picture. Three jobs carry equal weight:

1. Compare countries: where demand, pay and skills are strongest. Priority markets are Australia, Canada, USA, India, UK, Europe, Singapore, New Zealand and Ireland, down to state and city, with the rest of the world still covered.
2. Find my best jobs: drop in a CV and get ranked matches with reasons and skill gaps.
3. Track skill trends: which skills and roles are rising or falling over time.

Success means the owner can answer "where should I look, what should I apply to, what should I learn" in minutes and can trace every answer to a source.

## Positioning

A personal labour-market desk that combines live postings from official APIs and company boards, national statistics and the owner's own CV in one place, and is honest about what it could and could not collect.

## Operating Context

Runs on a 16 GB laptop with an 8 GB GPU using local models and free cloud tiers. Data grows over time, so early trend views are thin and must say so. Hundreds of sources are registered; many are blocked or reference-only by design.

## Capabilities and Constraints

- Filters: country, state, city, role, skill, remote, salary, date.
- Job detail with specifications and a link to the original posting.
- CV drop zone with analysis against collected jobs; CV content stays out of cloud calls unless the owner opts in.
- Assistant answers questions over collected data with source citations.
- No CAPTCHA or anti-bot bypass; sites that prohibit collection are shown as blocked rather than scraped.
- Free of cost wherever possible.

## Evidence on Hand

The owner's source list of roughly 340 URLs. No testimonials, customers or benchmarks exist and none may be invented. All figures shown must come from collected data.

## Product Principles

- Every number traces to a source.
- Say what is missing: coverage gaps, blocked sources and thin history are shown, never hidden.
- Clearly understandable first: plain labels and one obvious next step before density.
- A posting is not a trend: separate vacancies from discussion, and counts from statistics.
- The CV is private by default.
