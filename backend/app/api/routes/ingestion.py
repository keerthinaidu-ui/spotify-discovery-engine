from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.schemas.ingestion import IngestReviewsResponse, IngestionStatusResponse
from app.services.ingestion_service import (
    get_ingestion_status,
    run_product_hunt_ingestion,
    run_reviews_ingestion,
    run_youtube_ingestion,
)

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.post("/reviews", response_model=IngestReviewsResponse)
def ingest_reviews(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> IngestReviewsResponse:
    try:
        return run_reviews_ingestion(db, settings)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/product_hunt", response_model=IngestReviewsResponse)
def ingest_ph(
    slug: str | None = Query(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> IngestReviewsResponse:
    try:
        return run_product_hunt_ingestion(db, settings, slug=slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Product Hunt Ingestion failed: {exc}"
        ) from exc


@router.post("/youtube", response_model=IngestReviewsResponse)
def ingest_yt(
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> IngestReviewsResponse:
    try:
        return run_youtube_ingestion(db, settings, query=q)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"YouTube Ingestion failed: {exc}") from exc


@router.get("/status", response_model=IngestionStatusResponse)
def ingestion_status(db: Session = Depends(get_db)) -> IngestionStatusResponse:
    return get_ingestion_status(db)
