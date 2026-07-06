# Deployment & Operations Runbook

This runbook describes the deployment configuration, system parity checklist, logging setup, operations commands, and rollback workflow for the Spotify Review Discovery Engine.

---

## 1. Environment & API Keys Configuration

Verify the following environment variables are set in production `.env` (located at the repository root):

```ini
APP_NAME="Spotify Review Discovery Engine"
APP_ENV=production
DEBUG=false
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=https://your-dashboard-domain.com

# Database URL (Production should point to a persistent directory or postgres)
DATABASE_URL=sqlite:///data/spotify_review_engine.db

# Ingestion Source Settings
REVIEWS_CSV_PATH=data/raw/spotify_reviews.csv
PRODUCT_HUNT_TOKEN=your_ph_api_token
PRODUCT_HUNT_SLUG=spotify
YOUTUBE_API_KEY=your_youtube_api_key

# LLM Providers Configuration
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key

LOG_LEVEL=INFO
```

---

## 2. Server Startup & Daemon Configuration

### A. Development Server
To launch locally or on a staging machine:
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### B. Production Frontend Deployment (Vercel)

The React/Next.js frontend is deployed to Vercel for fast edge rendering and CDN distribution:

1. **Connect Repository**: Import the `spotify-review-engine` project in the Vercel Dashboard.
2. **Root Directory Configuration**: Set the framework preset to `Next.js` and point the root directory to `frontend`.
3. **Environment Variables**: Add the following variable in the Vercel project settings:
   - `NEXT_PUBLIC_API_URL`: Set to the deployed Streamlit backend URL (e.g., `https://spotify-reviews-backend.streamlit.app`).
4. **Deploy**: Vercel will build and host the frontend.

### C. Production Backend Deployment (Streamlit)

The Python FastAPI backend is deployed to Streamlit Community Cloud:

1. **Create App**: Connect your GitHub account to Streamlit Community Cloud and click "New App".
2. **Configuration**:
   - **Repository**: Select `spotify-review-engine`
   - **Branch**: Select your main deployment branch (e.g., `main`)
   - **Main file path**: `backend/app/main.py`
3. **Secrets Setup**: In the app settings on Streamlit, navigate to **Secrets** and add the variables from `.env` in TOML format:
   ```toml
   APP_NAME = "Spotify Review Discovery Engine"
   APP_ENV = "production"
   DEBUG = "false"
   DATABASE_URL = "sqlite:///data/spotify_review_engine.db" # Or use PostgreSQL connection string
   GEMINI_API_KEY = "your_gemini_key"
   GROQ_API_KEY = "your_groq_key"
   PRODUCT_HUNT_TOKEN = "your_ph_token"
   YOUTUBE_API_KEY = "your_youtube_key"
   ```
4. **Deploy**: Streamlit will provision the container, install packages from `backend/requirements.txt`, and start the backend service.

---

## 3. Database Migration & Schema Setup

Ensure migrations are up-to-date before starting the service:
```powershell
cd backend
# With active venv
alembic upgrade head
```

Verify that the active database contains all table structures (using `alembic current`).

---

## 4. Logging & Monitoring

* **Vercel Frontend Logs**: Next.js deployment builds and runtime executions can be monitored directly in the Vercel Dashboard under the "Logs" tab of your deployment project.
* **Streamlit Backend Logs**: Backend standard outputs and error streams can be viewed directly in the Streamlit Community Cloud console window (accessed via the lower right-hand panel on the app dashboard screen).
* **AI Job Monitor**: Check the status of background analysis runs using:
  ```bash
  curl -X GET "https://your-streamlit-app.streamlit.app/analysis/status?run_id=your_run_id"
  ```

---

## 5. Deployment Parity & Pre-deployment Checklist

1. **Verify Scope**: Only YouTube, Product Hunt, and Spotify CSV reviews are present. No Reddit assets or tables.
2. **Key Check**: Check that YouTube, Product Hunt, Gemini, and Groq keys are valid.
3. **Database Check**: Execute `alembic upgrade head` and verify that the head revision matches `ac19da346d3f`.
4. **Health Check**: Call `GET http://localhost:8000/health` and verify database connectivity returns `"connected"`.
5. **Dashboard Verify**: Load the dashboard UI page, check that KPIs populate, comparison matrix builds without error, and segment filters reflect premium subscription dropdown lists.
6. **Backup DB**: Perform a full copy backup of the database before restarting the API service.

---

## 6. Backup & Rollback Workflow

### A. Pre-Deployment Backup
Before running schema migrations:
```powershell
# Windows
Copy-Item data/spotify_review_engine.db data/spotify_review_engine.db.bak

# Linux
cp data/spotify_review_engine.db data/spotify_review_engine.db.bak
```

### B. Rollback Database Schema
If a migration crashes or is corrupt:
1. Revert to the previous database revision:
   ```powershell
   alembic downgrade -1
   ```
2. If schema rollback fails, restore the SQLite file backup:
   ```powershell
   # Windows
   Copy-Item data/spotify_review_engine.db.bak data/spotify_review_engine.db -Force
   
   # Linux
   cp data/spotify_review_engine.db.bak data/spotify_review_engine.db
   ```

### C. Revert Service Build
To rollback the application codebase:
1. Revert or checkout the stable git release tag in your repository:
   ```bash
   git checkout tags/v1.0.0-stable
   git push origin main --force
   ```
2. Both Vercel (frontend) and Streamlit (backend) will detect the repository update and automatically trigger a redeploy of the rolled-back version.
