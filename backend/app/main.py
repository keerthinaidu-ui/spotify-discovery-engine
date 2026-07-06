import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import feedback, health, ingestion, raw, analysis, insights, export
from app.config import get_settings
from app.worker import worker

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize DB tables if they don't exist
    import logging
    logger = logging.getLogger("app.main")
    try:
        from app.database import Base, engine
        import app.models  # Registers all models with Base
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully.")
        
        # Ensure has_mixed_sentiment and sentiment_profile columns exist (SQLite ALTER TABLE fallback)
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(engine)
            columns = [c["name"] for c in inspector.get_columns("feedback_items")]
            if "has_mixed_sentiment" not in columns:
                logger.info("Adding column has_mixed_sentiment to feedback_items table...")
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE feedback_items ADD COLUMN has_mixed_sentiment BOOLEAN"))
            if "sentiment_profile" not in columns:
                logger.info("Adding column sentiment_profile to feedback_items table...")
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE feedback_items ADD COLUMN sentiment_profile TEXT"))
        except Exception as col_err:
            logger.warning(f"Failed to check/alter database columns for mixed sentiment: {col_err}")
        
        # Run issue category taxonomy database migration for backward compatibility
        try:
            from app.database import SessionLocal
            from app.models.feedback_item import FeedbackItem
            from sqlalchemy import or_
            db_mig = SessionLocal()
            try:
                # Discovery Quality -> Discovery & Recommendation
                updated_discovery = db_mig.query(FeedbackItem).filter(FeedbackItem.issue_category == "Discovery Quality").update(
                    {FeedbackItem.issue_category: "Discovery & Recommendation"}, synchronize_session=False
                )
                # Playlist Management -> Library & Playlists
                updated_playlists = db_mig.query(FeedbackItem).filter(FeedbackItem.issue_category == "Playlist Management").update(
                    {FeedbackItem.issue_category: "Library & Playlists"}, synchronize_session=False
                )
                # Cross-Device Sync -> Cross-Device & Connectivity
                updated_connectivity = db_mig.query(FeedbackItem).filter(FeedbackItem.issue_category == "Cross-Device Sync").update(
                    {FeedbackItem.issue_category: "Cross-Device & Connectivity"}, synchronize_session=False
                )
                # other / Quality of Service / empty -> Unidentified
                updated_unidentified = db_mig.query(FeedbackItem).filter(
                    or_(
                        FeedbackItem.issue_category == "other",
                        FeedbackItem.issue_category == "",
                        FeedbackItem.issue_category == "Quality of Service"
                    )
                ).update(
                    {FeedbackItem.issue_category: "Unidentified"}, synchronize_session=False
                )
                
                if updated_discovery or updated_playlists or updated_connectivity or updated_unidentified:
                    db_mig.commit()
                    logger.info(f"Database issue category taxonomy migrated. Discovery: {updated_discovery}, Playlists: {updated_playlists}, Connectivity: {updated_connectivity}, Unidentified: {updated_unidentified}")
                else:
                    logger.info("Database issue category taxonomy is already up to date.")
                    
                # Conditional full backfill for any NULL categories
                null_count = db_mig.query(FeedbackItem).filter(FeedbackItem.issue_category.is_(None)).count()
                if null_count > 0:
                    logger.info(f"Detected {null_count} uncategorized reviews on startup. Running keyword backfill...")
                    db_path = settings.database_url.replace("sqlite:///", "")
                    if not os.path.isabs(db_path):
                        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", db_path))
                    
                    from scripts.backfill_taxonomy import run_backfill
                    run_backfill(db_path)
                    
            finally:
                db_mig.close()
        except Exception as migration_error:
            logger.warning(f"Failed to run database issue category taxonomy migration: {migration_error}")
            
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {e}")

    # Start background analysis worker
    worker.start()
    
    # Run LLM provider startup health checks
    try:
        from app.services.llm_service import LLMService
        llm = LLMService(settings)
        health_status = llm.check_health()
        logger.info(f"LLM Providers Startup Health Check: {health_status}")
    except Exception as e:
        logger.warning(f"Failed to run LLM startup health checks: {e}")

    # Build embedding indexes for any unindexed reviews
    try:
        from app.services.embedding_service import EmbeddingService
        from app.database import SessionLocal
        embedding_service = EmbeddingService(settings)
        if embedding_service.enabled:
            db_session = SessionLocal()
            try:
                res = embedding_service.index_reviews_with_embeddings(db_session)
                logger.info(f"Embedding index update on startup completed: {res}")
            finally:
                db_session.close()
    except Exception as e:
        logger.warning(f"Failed to run startup review embedding index builder: {e}")
        
    yield
    # Shutdown: Cleanly stop background analysis worker
    worker.stop()



app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, _exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(health.router)
app.include_router(ingestion.router)
app.include_router(raw.router)
app.include_router(feedback.router)
app.include_router(analysis.router)
app.include_router(insights.router)
app.include_router(export.router)


# Serve frontend static files from the root URL
current_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.abspath(os.path.join(current_dir, "..", "..", "frontend", "out"))

# Ensure directory and fallback index.html exist so FastAPI doesn't crash on startup
os.makedirs(frontend_dir, exist_ok=True)
placeholder_index = os.path.join(frontend_dir, "index.html")
if not os.path.exists(placeholder_index) or os.path.getsize(placeholder_index) == 0:
    with open(placeholder_index, "w", encoding="utf-8") as f:
        f.write("<!DOCTYPE html><html><head><title>Spotify Review Discovery Engine</title></head><body style='background:#0b0c0e;color:#c9d1d9;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;'><div><h2>Building Frontend...</h2><p>Please wait for the Next.js static build to complete.</p></div></body></html>")

app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

