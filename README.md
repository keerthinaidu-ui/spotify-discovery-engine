# Spotify AI-Powered Review Discovery Engine

Analyzes Spotify App Store / Play Store reviews to surface discovery struggles, recommendation frustrations, listening behaviors, user segments, and unmet needs.

**Current status:** Phase 1 (CSV ingestion) — ingest reviews via API or CLI.

## Documentation

- [Problem Statement](docs/problemStatement.md)
- [Phase-Wise Architecture](docs/phase-wise-architecture.md)
- [Phase 0 Plan](docs/phase-0-plan.md)
- [Unified Feedback Schema](docs/schema/unified-feedback-schema.md)

## Prerequisites

- Python 3.11+ (Windows: use `py -3` if `python` is not on PATH)

## Setup

From the repository root:

```powershell
Copy-Item .env.example .env
cd backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
py -3 -m pip install -r requirements.txt
py -3 -m alembic revision --autogenerate -m "initial schema"
py -3 -m alembic upgrade head
```

If the initial migration file already exists in `backend/alembic/versions/`, skip the `revision` step and run only `upgrade head`.

After pulling Phase 1 changes, apply new migrations:

```powershell
py -3 -m alembic upgrade head
```

## Ingest reviews (Phase 1)

Place the CSV at `data/raw/spotify_reviews.csv` (or set `REVIEWS_CSV_PATH` in `.env`).

```powershell
# API (server must be running)
curl -X POST http://localhost:8000/ingestion/reviews

# CLI (from backend/ with venv active)
py -3 -m scripts.ingest_reviews
```

| Endpoint | Purpose |
|----------|---------|
| `POST /ingestion/reviews` | Run CSV ingest |
| `GET /ingestion/status` | Row counts and last run |
| `GET /raw/reviews?limit=10` | Preview ingested rows |

## Run

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
py -3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Or from the repo root:

```powershell
.\scripts\run_dev.ps1
```

## Verify

| Endpoint | URL |
|----------|-----|
| Root | http://localhost:8000/ |
| Health | http://localhost:8000/health |
| API docs | http://localhost:8000/docs |

Expected `GET /health` response:

```json
{
  "status": "ok",
  "app_name": "Spotify Review Discovery Engine",
  "environment": "development",
  "database": "connected",
  "version": "0.1.0"
}
```

## Environment Variables

See [.env.example](.env.example). Phase 0 works with defaults:

- `.env` is loaded from the **repository root**
- SQLite database defaults to `data/spotify_review_engine.db`
- LLM variables are placeholders for later phases

## Project Structure

```
backend/          FastAPI app, models, Alembic
data/raw/         Merged review CSV (Phase 1)
docs/             Architecture and schema docs
frontend/         Dashboard UI (Phase 5)
scripts/          Dev helpers
```

## Phases

| Phase | Status | Description |
|-------|--------|-------------|
| 0 | Complete | Foundation, DB schema, health endpoint |
| 1 | Complete | CSV review ingestion into `raw_reviews` |
| 2 | Planned | Normalization |
| 3 | Planned | Query and filters |
| 4 | Planned | LLM analysis |
| 5 | Planned | Dashboard |
| 6 | Planned | PM exports |

## Migrations

From `backend/` with venv activated:

```powershell
py -3 -m alembic upgrade head
py -3 -m alembic revision --autogenerate -m "description"
```
