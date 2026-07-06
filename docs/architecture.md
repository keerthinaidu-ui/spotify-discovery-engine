# System Architecture & Data Dictionary

This document details the architecture, data dictionary, refresh procedures, known limitations, rollback workflow, and deployment architecture for the Spotify Review Discovery Engine.

---

## 1. System Architecture

The application is structured into four main operational layers: Ingestion, Normalization, AI Analysis, and Query/Dashboard.

```mermaid
flowchart TD
    subgraph Data Sources
        CSV[Spotify Reviews CSV]
        PH[Product Hunt GraphQL API]
        YT[YouTube Data API v3]
    end

    subgraph Raw Database Storage (SQLite)
        R_REV[(raw_reviews)]
        R_PH_P[(raw_product_hunt_posts)]
        R_PH_C[(raw_product_hunt_comments)]
        R_YT_V[(raw_youtube_videos)]
        R_YT_C[(raw_youtube_comments)]
    end

    subgraph Core Normalization & Unified Storage
        NORM[Normalization Service]
        FB[(feedback_items)]
    end

    subgraph AI Analysis Engine
        AI_SCHED[Batch Analysis Runner]
        LLM_GEM[Gemini AI Client]
        LLM_GROQ[Groq AI Client Fallback]
    end

    subgraph API & UI Presentation (Deployment)
        API[FastAPI Backend (Streamlit)]
        DASH[Next.js Frontend (Vercel)]
    end

    CSV --> R_REV
    PH --> R_PH_P & R_PH_C
    YT --> R_YT_V & R_YT_C

    R_REV & R_PH_P & R_PH_C & R_YT_V & R_YT_C --> NORM
    NORM --> FB

    FB --> AI_SCHED
    AI_SCHED --> LLM_GEM
    LLM_GEM -- Fail / Rate Limit --> LLM_GROQ
    LLM_GEM & LLM_GROQ --> FB

    FB --> API
    API --> DASH
```

### A. Data Ingestion Layer
* **App Reviews (CSV)**: Parses play store and app store reviews, storing them in `raw_reviews`.
* **Product Hunt API**: Connects to the GraphQL endpoint utilizing slug-based lookup (`spotify`) and saves posts and comments.
* **YouTube Data API**: Searches and retrieves metadata and comment threads based on keywords.

### B. Preprocessing & Normalization Layer
Processes raw cache inputs into the unified `feedback_items` table. It ensures:
* Standardized date parsing and rating mapping.
* Cleaned whitespace and stripped HTML tokens.
* Idempotency checks to prevent duplicate inserts based on `raw_id` and `raw_table`.

### C. AI Analysis Layer
Enriches normalized feedback with machine learning features:
* **LLM Engine**: Extracts issue categories, topics, user segments, loop causes, unmet needs, and highlighted quote evidence.
* **Fallback Strategy**: Executes runs on Gemini (structured JSON mode). If rate limits or timeouts are encountered, it automatically rolls over to Groq.

### D. Presentation & API Layer
* **Backend API Service**: A FastAPI server that handles review ingestion, normalization, AI pipeline runs (Gemini/Groq), SQL queries/aggregations, and data exports. Deployed as a web service via Streamlit.
* **Frontend Dashboard**: A Next.js (TypeScript/React) web application that serves as the UI client, presenting interactive dashboards, query filters, charts, and AI analysis reports. Deployed to Vercel.

---

## 2. Data Dictionary

### Target Table: `feedback_items`

| Field Name | Type | Key | Description |
| :--- | :--- | :---: | :--- |
| `id` | String(36) | PK | Unique identifier (UUID). |
| `source_type` | String(32) | Index | Source type identifier (`app_review`, `producthunt_post`, `producthunt_comment`, `youtube_video`, `youtube_comment`). |
| `platform` | String(32) | Index | Platform identifier (`app_store`, `play_store`, `product_hunt`, `youtube`). |
| `text` | Text | — | Main body of the review or comment. |
| `title` | String(512) | — | Review title or post header (nullable). |
| `rating_or_score`| Float | Index | Numeric rating (1.0-5.0) or engagement/likes count. |
| `author` | String(256) | — | Anonymized user identifier or channel name. |
| `created_at` | DateTime | Index | Standardized date of original posting. |
| `app_version` | String(64) | — | App version code (app reviews only). |
| `url` | String(1024) | — | Source URL linking back to the post or video. |
| `raw_table` | String(32) | — | The source database table name. |
| `raw_id` | String(255) | Unique | The unique external ID of the raw feedback. |
| `sentiment` | String(16) | — | AI sentiment label (`positive`, `neutral`, `negative`, `unknown`). |
| `issue_category` | String(128) | — | Broad issue classification. |
| `topics` | Text (JSON) | — | Extracted keywords or themes list. |
| `user_segment` | String(128) | — | Customer segment label. |
| `unmet_needs` | Text (JSON) | — | List of identified unmet product needs. |
| `analysis_evidence`| Text (JSON) | — | Quote snippets matched to topic tags. |
| `analyzed_at` | DateTime | — | Timestamp of AI run execution. |
| `normalized_at` | DateTime | — | Timestamp of target normalization. |

---

## 3. Refresh and Re-run Steps

To completely refresh ingestion, normalization, and AI analysis data pipelines, follow these steps:

### Step 1: Run Ingestion
Run the raw ingestion scripts to pull latest source data:
```powershell
# From backend directory with virtual environment active:
python -m scripts.ingest_reviews
python -m scripts.ingest_external_sources
```
Alternatively, call the API endpoints:
* `POST /ingestion/reviews`
* `POST /ingestion/product_hunt`
* `POST /ingestion/youtube`

### Step 2: Trigger Normalization
To process raw rows into unified feedback items, execute:
```powershell
python -m scripts.normalize_feedback
# Or call: POST /feedback/normalize
```

### Step 3: Execute AI Analysis Run
To categorize newly normalized items, trigger the background scheduler:
```powershell
# Trigger a run for 100 unanalyzed items:
curl -X POST "http://localhost:8000/analysis/run?limit=100"
```

---

## 4. Known Limitations
1. **SQLite Database Locks**: SQLite does not support concurrent write operations. Running multiple ingestion runs or high-volume parallel analysis runs might throw database lock warnings.
2. **LLM API Quota Constraints**: Large batch runs on Gemini or Groq are constrained by model tokens-per-minute (TPM) and requests-per-minute (RPM) limits. 
3. **No Auto-Refresh**: The dashboard UI reads data statically at page load. Re-running normalization requires manual reload of the dashboard.

---

## 5. Rollback Steps

If a database schema change or migration fails:
1. **Identify current database revision**:
   ```powershell
   alembic current
   ```
2. **Revert the head migration**:
   To downgrade the database schema to the previous revision, run:
   ```powershell
   alembic downgrade -1
   # Or revert to a specific migration code:
   alembic downgrade 730156d05dab
   ```
3. **Restore Database Backup**:
   SQLite database is stored at `data/spotify_review_engine.db`. A pre-deployment backup of this single file should be copied back to revert all data changes instantly.

---

## 6. Deployment Architecture

The application uses a decoupled deployment strategy to separate presentation (frontend) and logic (backend) hosting:

### A. Frontend Deployment (Vercel)
* **Hosting Provider**: [Vercel](https://vercel.com)
* **Technology**: Next.js (TypeScript, React)
* **Deployment Workflow**:
  - Automatically triggered upon code pushes or merge events to the repository's `main` branch (via Git integration).
  - Preview URLs are auto-generated for each pull request.
* **Environment Configuration**:
  - `NEXT_PUBLIC_API_URL`: Points to the live backend URL hosted on Streamlit.

### B. Backend Deployment (Streamlit)
* **Hosting Provider**: [Streamlit Community Cloud](https://streamlit.io/cloud) or equivalent streamlit platform.
* **Technology**: Python 3.11, FastAPI, SQLAlchemy
* **Deployment Workflow**:
  - Automated deployment linking the GitHub repository's python environment to Streamlit.
  - Automatically rebuilds the app container when changes are pushed to the deployment branch.
* **Database & Storage**:
  - **SQLite**: Local SQLite data directory (`data/spotify_review_engine.db`) for lightweight testing/caching, or configured to point to a managed PostgreSQL cluster (e.g., Supabase or Neon) via the `DATABASE_URL` environment variable for robust persistency.
* **Environment Variables & Secrets**:
  - Configured via the Streamlit dashboard settings under Secrets management:
    - `DATABASE_URL`: SQL connection string.
    - `GEMINI_API_KEY`: API access token for Gemini.
    - `GROQ_API_KEY`: API access token for Groq fallback.
    - `YOUTUBE_API_KEY`: YouTube API v3 developer key.
    - `PRODUCT_HUNT_TOKEN`: Product Hunt API GraphQL client credentials.
