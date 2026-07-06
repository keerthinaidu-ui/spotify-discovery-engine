# Phase 0 Implementation Plan: Foundation & Infrastructure

Detailed build plan for Phase 0 of the Spotify AI-Powered Review Discovery Engine, based on [problemStatement.md](./problemStatement.md) and [phase-wise-architecture.md](./phase-wise-architecture.md).

**Phase 0 goal:** A runnable backend with configuration, database migrations, and a `/health` endpoint. No ingestion, analysis, or dashboard yet.

**Phase 0 done when:**

- Backend starts without errors
- Database migrations apply cleanly
- `GET /health` returns status and DB connectivity
- README documents setup and run steps
- Unified schema tables exist (empty): `raw_reviews`, , `feedback_items`, `analysis_results`

---

## 1. Technology Choices

### 1.1 Backend: FastAPI (recommended over Flask)

| Criterion | FastAPI | Flask |
|-----------|---------|-------|
| Request/response validation | Built-in via Pydantic | Requires extensions (Marshmallow, etc.) |
| API documentation | Auto-generated OpenAPI at `/docs` | Manual or add-on (flask-smorest, etc.) |
| Async I/O | Native `async`/`await | Possible but not first-class |
| Type safety | Encouraged; IDE-friendly | Optional |
| Performance | High (Starlette/uvicorn) | Good; lower for I/O-heavy workloads |
| Learning curve | Moderate | Lower |

**Decision: FastAPI**

Reasons specific to this project:

1. **Future LLM calls are I/O-bound.** Phases 1 and 4 will call external APIs in batches. FastAPI's async model fits without restructuring later.
2. **Auto OpenAPI docs** help the Phase 5 dashboard team discover endpoints without extra documentation work.
3. **Pydantic settings and schemas** give a single source of truth for env config (Phase 0) and the unified `feedback_items` contract (Phase 2+).
4. **Aligns with phase-wise architecture**, which already recommends Python + FastAPI.

Flask remains viable for a minimal CRUD API, but would require more boilerplate for validation, docs, and async ingestion jobs.

---

### 1.2 Database: SQLite for prototype (PostgreSQL later)

| Criterion | SQLite | PostgreSQL |
|-----------|--------|------------|
| Setup | None — single file | Requires server install or Docker|
| Prototype speed | Immediate | Extra infra step |
| Data volume fit | CSV batch — typically thousands to low millions of rows | Same, with headroom |
| Concurrent writes | Single writer; fine for batch jobs | Multi-writer, production-grade |
| Portability | Copy `.db` file | Connection string + server |
| Migration path | Same SQLAlchemy + Alembic code | Change `DATABASE_URL` only |

**Decision: SQLite for Phase 0–prototype; design for PostgreSQL swap**

Reasons:

1. **Zero infrastructure** — one developer on Windows can run the full stack with no Dockeror cloud DB.
2. **Batch-oriented workload** — ingestion and LLM analysis run as jobs, not high-concurrency OLTP.
3. **SQLAlchemy abstracts the engine** — `DATABASE_URL=sqlite:///./data/spotify_review_engine.db` today; `postgresql://...` in production without model changes.
4. **Architecture explicitly says** "SQLite → PostgreSQL" for prototype-to-scale.

Use PostgreSQL when: multiple concurrent writers, hosted deployment, or dataset exceeds comfortable SQLite limits (~millions of rows with heavy indexing).

---

## 2. Project Folder Structure

Exact layout to create in the repository root (`spotify-review-engine/`):

```
spotify-review-engine/
├── docs/
│   ├── problemStatement.md
│   ├── phase-wise-architecture.md
│   ├── phase-0-plan.md
│   └── schema/
│       └── unified-feedback-schema.md      # Phase 0 deliverable: field contract
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                         # FastAPI app entry, CORS, router mount
│   │   ├── config.py                       # Pydantic Settings from env
│   │   ├── database.py                     # SQLAlchemy engine, SessionLocal, get_db
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── routes/
│   │   │       ├── __init__.py
│   │   │       └── health.py               # GET /health
│   │   ├── models/
│   │   │   ├── __init__.py                 # re-export all models for Alembic
│   │   │   ├── raw_review.py
│   │   │   ├── 
│   │   │   ├── feedback_item.py
│   │   │   └── analysis_result.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   └── health.py                   # HealthResponse Pydantic model
│   │   └── services/                       # empty until Phase 1+
│   │       └── __init__.py
│   │
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── <generated_revision>_initial_schema.py
│   │
│   ├── alembic.ini
│   ├── requirements.txt
│   └── pyproject.toml                      # optional: tool config (ruff, pytest)
│
├── data/
│   ├── raw/                                # gitignored; place merged CSV here
│   │   └── .gitkeep
│   └── spotify_review_engine.db            # gitignored; created by migrations
│
├── scripts/
│   └── run_dev.ps1                         # optional Windows helper
│
├── frontend/                               # optional Phase 0 stub; full UI in Phase 5
│   └── .gitkeep
│
├── .env.example
├── .gitignore
└── README.md
```

**Conventions:**

- All Python application code lives under `backend/app/`.
- Run commands from `backend/` unless noted.
- Raw CSV path: `data/raw/spotify_reviews.csv` (configurable via env).
- Database file: `data/spotify_review_engine.db` (relative to repo root or backend — pick one and docsument in README; plan uses repo root `data/`).

---

## 3. Environment Variables

Create `.env` at the **repository root** (copy from `.env.example`). Backend loads it via Pydantic Settings.

### 3.1 `.env.example`

```env
# --- Application ---
APP_NAME=Spotify Review Discovery Engine
APP_ENV=development
DEBUG=true
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# --- Database ---
# SQLite (prototype default)
# DATABASE_URL=sqlite:///C:/absolute/path/to/spotify-review-engine/data/spotify_review_engine.db
# Leave unset to use the default REPO_ROOT-based SQLite path from config.py
# PostgreSQL (future): postgresql+psycopg2://user:pass@localhost:5432/spotify_reviews

# --- Data paths (relative to repo root) ---
REVIEWS_CSV_PATH=data/raw/spotify_reviews.csv

# --- LLM API (Phase 4; define now, use later) ---
LLM_PROVIDER=gemini
GEMINI_API_KEY=
GROQ_API_KEY=

# --- Logging ---
LOG_LEVEL=INFO
```

### 3.2 Variable reference

| Variable | Required in Phase 0 | Used in | Description |
|----------|---------------------|---------|-------------|
| `APP_NAME` | No | Health response | Display name |
| `APP_ENV` | No | Config, logs | `development` \| `staging` \| `production` |
| `DEBUG` | No | Uvicorn reload | `true` enables auto-reload |
| `API_HOST` | No | Uvicorn | Bind address |
| `API_PORT` | No | Uvicorn | Default `8000` |
| `CORS_ORIGINS` | No | FastAPI middleware | Comma-separated frontend URLs |
|`DATABASE_URL` | No | SQLAlchemy | SQLite or PostgreSQL connection string (optional; default SQLite path from     config.py)
| `REVIEWS_CSV_PATH` | No | Phase 1 | Path to merged review CSV |
| `LLM_PROVIDER` | No | Phase 4 | `gemini` |
| `GEMINI_API_KEY` | No | Phase 4 | Gemini API key |
| `GROQ_API_KEY` | No | Phase 4 | Groq API key |
| `LOG_LEVEL` | No | Logging | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

Phase 0 can run with the default SQLite path from config.py; DATABASE_URL is optional unless you want to override the default. LLM variables are placeholders so `.env` stays stable across phases.

---

## 4. Commands: Create Backend Skeleton

Prerequisites: **Python 3.11+**, **pip**, **git**.

Run from repository root (`spotify-review-engine/`). Commands work in PowerShell; bash equivalents noted where different.

### 4.1 Create directories

```powershell
mkdir backend\app\api\routes, backend\app\models, backend\app\schemas, backend\app\services, data\raw, scripts, docs\schema, frontend
New-Item -ItemType File -Path data\raw\.gitkeep, frontend\.gitkeep -Force
```

### 4.2 Create virtual environment and install dependencies

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install fastapi uvicorn[standard] sqlalchemy alembic pydantic-settings python-dotenv
pip freeze > requirements.txt
cd ..
```

**`backend/requirements.txt` (pinned baseline):**

```text
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
sqlalchemy>=2.0.0
alembic>=1.14.0
pydantic-settings>=2.6.0
python-dotenv>=1.0.0
```

Phase 1+ will add: `pandas`, `httpx`, and LLM connectivity.

### 4.3 Scaffold Python package files

Create empty modules (PowerShell):

```powershell
@(
  "backend\app\__init__.py",
  "backend\app\api\__init__.py",
  "backend\app\api\routes\__init__.py",
  "backend\app\models\__init__.py",
  "backend\app\schemas\__init__.py",
  "backend\app\services\__init__.py"
) | ForEach-Object { New-Item -ItemType File -Path $_ -Force }
```

Copy `.env.example` to `.env`:

```powershell
Copy-Item .env.example .env
```

### 4.4 Initialize Alembic

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
alembic init alembic
cd ..
```

Then edit `backend/alembic/env.py` to import `Base` and settings (see Section 6).

---

## 5. Core Implementation Files

### 5.1 `backend/app/config.py`

```python
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root = parent of backend/
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Spotify Review Discovery Engine"
    app_env: str = "development"
    debug: bool = True
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173"

    database_url: str = f"sqlite:///{REPO_ROOT / 'data' / 'spotify_review_engine.db'}"

    reviews_csv_path: str = "data/raw/spotify_reviews.csv"
    gemini_api_key: str = ""
    groq_api_key: str = ""
    llm_provider: str = "gemini"

    log_level: str = "INFO"


    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def reviews_csv_absolute(self) -> Path:
        p = Path(self.reviews_csv_path)
        return p if p.is_absolute() else REPO_ROOT / p


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### 5.2 `backend/app/database.py`

```python
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
```

### 5.3 SQLAlchemy models (Phase 0 schema draft)

**`backend/app/models/raw_review.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RawReview(Base):
    __tablename__ = "raw_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[float | None] = mapped_column(Float)
    title: Mapped[str | None] = mapped_column(String(512))
    author: Mapped[str | None] = mapped_column(String(256))
    platform: Mapped[str | None] = mapped_column(String(64))  # app_store | play_store
    review_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    app_version: Mapped[str | None] = mapped_column(String(64))
    url: Mapped[str | None] = mapped_column(String(1024))
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```


**`backend/app/models/feedback_item.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FeedbackItem(Base):
    __tablename__ = "feedback_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(String(512))
    rating_or_score: Mapped[float | None] = mapped_column(Float)
    author: Mapped[str | None] = mapped_column(String(256))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    app_version: Mapped[str | None] = mapped_column(String(64))
    url: Mapped[str | None] = mapped_column(String(1024))
    raw_table: Mapped[str | None] = mapped_column(String(32))  # raw_reviews
    raw_id: Mapped[str | None] = mapped_column(String(36), index=True)
    sentiment: Mapped[str | None] = mapped_column(String(16))  # Phase 3
    normalized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

**`backend/app/models/analysis_result.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    feedback_item_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("feedback_items.id"), index=True
    )
    result_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # e.g. theme, complaint, segment, unmet_need, summary, cross_source_compare
    label: Mapped[str | None] = mapped_column(String(256))
    payload_json: Mapped[str | None] = mapped_column(Text)  # JSON blob for flexible LLM output
    model: Mapped[str | None] = mapped_column(String(128))
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

**`backend/app/models/__init__.py`**

```python
from app.models.analysis_result import AnalysisResult
from app.models.feedback_item import FeedbackItem
from app.models.raw_review import RawReview

__all__ = ["RawReview", "FeedbackItem", "AnalysisResult"]
```

---

## 6. Database Setup and Migrations

### 6.1 Configure Alembic `env.py`

Replace the target metadata import in `backend/alembic/env.py`:

```python
from app.config import get_settings
from app.database import Base
from app.models import AnalysisResult, FeedbackItem, RawReview  # noqa: F401

config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata
```

Ensure `env.py` adds the backend directory to `sys.path` so `app` imports resolve when running from `backend/`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
```

### 6.2 Commands to create and apply migrations

```powershell
cd backend
.\.venv\Scripts\Activate.ps1

# Generate initial migration from models
alembic revision --autogenerate -m "initial schema"

# Apply migration (creates data/spotify_review_engine.db)
alembic upgrade head

# Verify current revision
alembic current

cd ..
```

**Expected result:** File `backend/alembic/versions/xxxx_initial_schema.py` created; SQLite DB at `data/spotify_review_engine.db` with four tables.

### 6.3 Useful migration commands (reference)

| Command | Purpose |
|---------|---------|
| `alembic upgrade head` | Apply all pending migrations |
| `alembic downgrade -1` | Roll back one revision |
| `alembic history` | List migration history |
| `alembic revision --autogenerate -m "msg"` | New migration after model changes |

### 6.4 PostgreSQL switch (future)

1. Install driver: `pip install psycopg2-binary`
2. Update `.env`: `DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/spotify_reviews`
3. Run `alembic upgrade head` against the new database

No model code changes required.

---

## 7. `/health` Endpoint Implementation

### 7.1 `backend/app/schemas/health.py`

```python
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    app_name: str
    environment: str
    database: str
    version: str = "0.1.0"
```

### 7.2 `backend/app/api/routes/health.py`

```python
from fastapi import APIRouter

from app.config import get_settings
from app.database import check_db_connection
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    settings = get_settings()
    db_ok = check_db_connection()
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        app_name=settings.app_name,
        environment=settings.app_env,
        database="connected" if db_ok else "disconnected",
    )
```

### 7.3 `backend/app/main.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs",
    redocs_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Spotify Review Discovery Engine API", "docs": "/docs"}
```

### 7.4 Run the server

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 7.5 Verify

```powershell
curl http://localhost:8000/health
```

**Expected response:**

```json
{
  "status": "ok",
  "app_name": "Spotify Review Discovery Engine",
  "environment": "development",
  "database": "connected",
  "version": "0.1.0"
}
```

Also open `http://localhost:8000/docs` for interactive OpenAPI UI.

---

## 8. `.gitignore` (minimum)

```gitignore
# Python
backend/.venv/
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/

# Environment and secrets
.env

# Data and database
data/*.db
data/raw/*.csv
!data/raw/.gitkeep

# IDE
.vscode/
.idea/

# Frontend (Phase 5)
frontend/node_modules/
frontend/dist/
```

---

## 9. README Outline

Use this structure for the root `README.md` created in Phase 0.

```markdown
# Spotify AI-Powered Review Discovery Engine

Prototype system that analyzes Spotify App Store / Play Store reviews 
discussions to surface discovery struggles, recommendation frustrations, listening
behaviors, user segments, and unmet needs.

## documentation

- [Problem Statement](docs/problemStatement.md)
- [Phase-Wise Architecture](docs/phase-wise-architecture.md)
- [Phase 0 Plan](docs/phase-0-plan.md)

## Prerequisites

- Python 3.11+
- (Phase 1+) 
- (Phase 4+) Gemini or Groq API key
- (Phase 5+) Node.js 20+ for frontend

## Quick Start

### 1. Clone and configure

\`\`\`powershell
git clone <repo-url>
cd spotify-review-engine
Copy-Item .env.example .env
# Edit .env — at minimum DATABASE_URL is set by default for SQLite
\`\`\`

### 2. Backend setup

\`\`\`powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
\`\`\`

### 3. Run API

\`\`\`powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
\`\`\`

### 4. Verify

- Health: http://localhost:8000/health
- API docs: http://localhost:8000/docs

## Environment Variables

See [.env.example](.env.example). Phase 0 requires only `DATABASE_URL`.
LLM variables are used in later phases.

## Project Structure

\`\`\`
backend/     FastAPI application, models, migrations
data/raw/    Merged review CSV (not committed)
docs/         Architecture and phase plans
frontend/    Dashboard UI (Phase 5)
\`\`\`

## Development Phases

| Phase | Status | Description |
|-------|--------|-------------|
| 0 | In progress | Foundation, DB schema, health endpoint |
| 1 | Planned | CSV ingestion |
| 2 | Planned | Normalization to unified schema |
| 3 | Planned | Query and filters |
| 4 | Planned | LLM analysis |
| 5 | Planned | Dashboard UI |
| 6 | Planned | Integration and PM exports |

## Database Migrations

From `backend/` with venv activated:

\`\`\`powershell
alembic upgrade head          # apply migrations
alembic revision --autogenerate -m "description"  # after model changes
\`\`\`

## License

TBD
```

---

## 10. Phase 0 Task Checklist

Execute in order:

| # | Task | Verification |
|---|------|--------------|
| 1 | Create folder structure (Section 2) | Directories exist |
| 2 | Add `.env.example`, `.gitignore`, copy `.env` | Env loads in config |
| 3 | Create venv; install requirements | `pip list` shows FastAPI, SQLAlchemy, Alembic |
| 4 | Implement `config.py`, `database.py` | Import without error |
| 5 | Implement four SQLAlchemy models | Models registered in `models/__init__.py` |
| 6 | Configure Alembic; run `upgrade head` | DB file exists; four tables present |
| 7 | Implement `/health` route and `main.py` | curl returns `"status": "ok"` |
| 8 | Write `docs/schema/unified-feedback-schema.md` | Field contract documentedfor Phase 2 |
| 9 | Write root `README.md` from outline (Section 9) | Setup steps reproducible |

**Optional Phase 0 extras (not blocking):**

- `scripts/run_dev.ps1` wrapping venv activate + uvicorn
- Root endpoint `GET /` redirecting to docs
- Structured logging in `main.py` using `LOG_LEVEL`

---

## 11. Handoff to Phase 1

When Phase 0 checklist is complete, Phase 1 can begin with:

- `RawReview` and  tables ready for bulk insert
- `REVIEWS_CSV_PATH`  env vars already defined
- `GET /health` for CI smoke tests
- OpenAPI at `/docs` for docsumenting new ingestion endpoints

No code changes to Phase 0 foundation should be required unless CSV column names force adjustments to `raw_reviews` columns (docsument any changes in a new Alembic migration).
