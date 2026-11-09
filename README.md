# Self Analytics

A personal job-market desk: compare countries, match jobs to your CV, track skill trends, and ask questions with cited answers.

## Everyday use

From PowerShell in this folder:

```powershell
# 1. Start Docker Desktop, then the database and queue
docker compose up -d db redis

# 2. API (first terminal)
cd backend; .\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8100

# 3. Web app (second terminal)
cd web; npx next start -p 3100
```

Open <http://127.0.0.1:3100>.

Ollama runs natively on Windows and must be running for the CV analysis, assistant and semantic matching. Without it, those features fall back to skills-only matching and raw evidence.

## Collecting data

Run from `backend/`:

| Command | What it does |
|---|---|
| `.\.venv\Scripts\python.exe -m app.cli run due` | Collect every source that is overdue |
| `... -m app.cli run api` | API and feed sources only |
| `... -m app.cli run crawl` / `jsonld` / `insight` | Crawled sites or report sites only |
| `... -m app.cli run "Stripe"` | One source, by part of its name |
| `... -m app.cli embed --limit 5000` | Create search vectors for jobs (needs Ollama) |
| `... -m app.cli probe` | Re-check robots.txt and structure of crawlable sites |
| `... -m app.cli discover` | Find more employer boards (needs a search key) |
| `... -m app.cli maintain` | Refresh exchange rates, close stale jobs |

For automatic scheduling, run everything in Docker: `docker compose --profile app up -d --build`, then open <http://127.0.0.1:3100>. Celery is not supported on Windows, so scheduling only runs in Docker. Collection is based on what is overdue, so a laptop that was asleep catches up when it wakes.

## API keys

Add keys to `.env`, then restart the API and run `-m app.cli run api`. See `.env.example` for every setting.

## Tests

`cd backend; .\.venv\Scripts\python.exe -m pytest -q`

## Hosting on Vercel later

Vercel can host the web app and API, but not long-running crawlers, Celery or local models. The plan:

1. Database: Neon (Postgres with pgvector). Set `DATABASE_URL`, run `alembic upgrade head` and `python -m app.cli bootstrap`. A large job history will outgrow a free tier.
2. Web: deploy `web/` to Vercel with `BACKEND_URL` set to the API and `APP_PASSWORD` set.
3. API: deploy `backend/` as a separate service with the same `APP_PASSWORD`.
4. Collection: keep running it on this laptop against the Neon database, or on a small always-on server.
5. Models: local Ollama is not reachable from Vercel, so set `LLM_FALLBACK`. CV analysis deliberately never uses a cloud model, so on a hosted deployment it runs skills-only.

Set `APP_PASSWORD` before exposing it: a CV is personal data.
