from __future__ import annotations

import logging
from datetime import datetime, timezone
import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.ingestion_run import IngestionRun
from app.models.raw_review import RawReview
from app.models.raw_product_hunt import RawProductHuntPost, RawProductHuntComment
from app.models.raw_youtube import RawYouTubeVideo, RawYouTubeComment
from app.schemas.ingestion import (
    IngestionRunResponse,
    IngestionStatusResponse,
    IngestReviewsResponse,
    SourceStatus,
)
from app.services.csv_ingestion import ingest_reviews_csv
from app.services.product_hunt_ingestion import ingest_product_hunt
from app.services.youtube_ingestion import ingest_youtube

logger = logging.getLogger(__name__)


def validate_ingestion_env(settings: Settings) -> None:
    """Validates that all required env variables are present before running integrations."""
    ph_token = settings.product_hunt_access_token or settings.product_hunt_token
    ph_slug = settings.product_hunt_slug
    yt_key = settings.youtube_api_key
    gemini_key = settings.gemini_api_key
    groq_key = settings.groq_api_key

    missing = []
    if not ph_token:
        missing.append("PRODUCT_HUNT_ACCESS_TOKEN / PRODUCT_HUNT_TOKEN")
    if not ph_slug:
        missing.append("PRODUCT_HUNT_SLUG")
    if not yt_key:
        missing.append("YOUTUBE_API_KEY")
    if not gemini_key:
        missing.append("GEMINI_API_KEY")
    if not groq_key:
        missing.append("GROQ_API_KEY")

    if missing:
        err_msg = f"Missing required configuration variables: {', '.join(missing)}"
        logger.error(err_msg)
        raise ValueError(err_msg)


def run_reviews_ingestion(db: Session, settings: Settings) -> IngestReviewsResponse:
    """Orchestrates CSV review ingestion."""
    validate_ingestion_env(settings)

    run = IngestionRun(
        id=str(uuid.uuid4()),
        source="csv_reviews",
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        rows_read, rows_inserted, rows_skipped = ingest_reviews_csv(
            db, settings.reviews_csv_absolute
        )
        run.status = "success"
        run.rows_read = rows_read
        run.rows_inserted = rows_inserted
        run.rows_skipped = rows_skipped
        
        # Auto-normalize and wake worker
        from app.services.normalization_service import run_normalization
        from app.worker import worker
        try:
            logger.info("Automatically running normalization after CSV ingestion...")
            run_normalization(db)
            worker.wake()
        except Exception as norm_exc:
            logger.error(f"Auto-normalization failed: {norm_exc}")
            
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)
        logger.error(f"CSV reviews ingestion failed: {exc}")
    finally:
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)

    return IngestReviewsResponse(run=_to_run_response(run))


def run_product_hunt_ingestion(
    db: Session, settings: Settings, slug: str | None = None
) -> IngestReviewsResponse:
    """Orchestrates Product Hunt API ingestion."""
    validate_ingestion_env(settings)
    target_slug = slug or settings.product_hunt_slug or "spotify"
    ph_token = settings.product_hunt_access_token or settings.product_hunt_token

    run = IngestionRun(
        id=str(uuid.uuid4()),
        source="product_hunt",
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        rows_read, rows_inserted, rows_skipped = ingest_product_hunt(
            db, token=ph_token, slug=target_slug
        )
        run.status = "success"
        run.rows_read = rows_read
        run.rows_inserted = rows_inserted
        run.rows_skipped = rows_skipped
        
        # Auto-normalize and wake worker
        from app.services.normalization_service import run_normalization
        from app.worker import worker
        try:
            logger.info("Automatically running normalization after Product Hunt ingestion...")
            run_normalization(db)
            worker.wake()
        except Exception as norm_exc:
            logger.error(f"Auto-normalization failed: {norm_exc}")
            
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)
        logger.error(f"Product Hunt ingestion failed: {exc}")
    finally:
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)

    return IngestReviewsResponse(run=_to_run_response(run))


def run_youtube_ingestion(
    db: Session, settings: Settings, query: str | None = None
) -> IngestReviewsResponse:
    """Orchestrates YouTube search + comment threads ingestion."""
    validate_ingestion_env(settings)
    target_query = query or "spotify recommendation"
    yt_key = settings.youtube_api_key

    run = IngestionRun(
        id=str(uuid.uuid4()),
        source="youtube",
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        # Default limits to protect search quotas
        rows_read, rows_inserted, rows_skipped = ingest_youtube(
            db, api_key=yt_key, query=target_query, max_videos=5, max_comments=20
        )
        run.status = "success"
        run.rows_read = rows_read
        run.rows_inserted = rows_inserted
        run.rows_skipped = rows_skipped
        
        # Auto-normalize and wake worker
        from app.services.normalization_service import run_normalization
        from app.worker import worker
        try:
            logger.info("Automatically running normalization after YouTube ingestion...")
            run_normalization(db)
            worker.wake()
        except Exception as norm_exc:
            logger.error(f"Auto-normalization failed: {norm_exc}")
            
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)
        logger.error(f"YouTube ingestion failed: {exc}")
    finally:
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)

    return IngestReviewsResponse(run=_to_run_response(run))


def get_ingestion_status(db: Session) -> IngestionStatusResponse:
    """Retrieves combined ingestion statistics for CSV, Product Hunt, and YouTube."""
    # 1. CSV reviews
    total_csv = db.query(func.count(RawReview.id)).scalar() or 0
    last_csv = (
        db.query(IngestionRun)
        .filter(IngestionRun.source == "csv_reviews")
        .order_by(IngestionRun.started_at.desc())
        .first()
    )

    # 2. Product Hunt
    posts_count = db.query(func.count(RawProductHuntPost.id)).scalar() or 0
    comments_count_ph = db.query(func.count(RawProductHuntComment.id)).scalar() or 0
    total_ph = posts_count + comments_count_ph
    last_ph = (
        db.query(IngestionRun)
        .filter(IngestionRun.source == "product_hunt")
        .order_by(IngestionRun.started_at.desc())
        .first()
    )

    # 3. YouTube
    videos_count = db.query(func.count(RawYouTubeVideo.id)).scalar() or 0
    comments_count_yt = db.query(func.count(RawYouTubeComment.id)).scalar() or 0
    total_yt = videos_count + comments_count_yt
    last_yt = (
        db.query(IngestionRun)
        .filter(IngestionRun.source == "youtube")
        .order_by(IngestionRun.started_at.desc())
        .first()
    )

    return IngestionStatusResponse(
        csv_reviews=SourceStatus(
            total_records=total_csv,
            last_run=_to_run_response(last_csv) if last_csv else None,
        ),
        product_hunt=SourceStatus(
            total_records=total_ph,
            last_run=_to_run_response(last_ph) if last_ph else None,
        ),
        youtube=SourceStatus(
            total_records=total_yt,
            last_run=_to_run_response(last_yt) if last_yt else None,
        ),
    )


def _to_run_response(run: IngestionRun) -> IngestionRunResponse:
    return IngestionRunResponse(
        id=run.id,
        source=run.source,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        rows_read=run.rows_read,
        rows_inserted=run.rows_inserted,
        rows_skipped=run.rows_skipped,
        error_message=run.error_message,
    )
