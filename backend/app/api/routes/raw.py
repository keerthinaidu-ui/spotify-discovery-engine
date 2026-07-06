from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.raw_review import RawReview
from app.models.raw_product_hunt import RawProductHuntPost
from app.models.raw_youtube import RawYouTubeVideo
from app.schemas.ingestion import (
    RawReviewListResponse,
    RawReviewResponse,
    RawProductHuntListResponse,
    RawProductHuntPostResponse,
    RawYouTubeListResponse,
    RawYouTubeVideoResponse,
)

router = APIRouter(prefix="/raw", tags=["raw"])


@router.get("/reviews", response_model=RawReviewListResponse)
def list_raw_reviews(
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> RawReviewListResponse:
    total = db.query(func.count(RawReview.id)).scalar() or 0
    items = db.query(RawReview).order_by(RawReview.ingested_at.desc()).limit(limit).all()
    return RawReviewListResponse(
        items=[RawReviewResponse.model_validate(item) for item in items],
        total=total,
    )


@router.get("/product_hunt", response_model=RawProductHuntListResponse)
def list_raw_ph(
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> RawProductHuntListResponse:
    total = db.query(func.count(RawProductHuntPost.id)).scalar() or 0
    items = (
        db.query(RawProductHuntPost)
        .order_by(RawProductHuntPost.ingested_at.desc())
        .limit(limit)
        .all()
    )
    return RawProductHuntListResponse(
        items=[RawProductHuntPostResponse.model_validate(item) for item in items],
        total=total,
    )


@router.get("/youtube", response_model=RawYouTubeListResponse)
def list_raw_yt(
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> RawYouTubeListResponse:
    total = db.query(func.count(RawYouTubeVideo.id)).scalar() or 0
    items = (
        db.query(RawYouTubeVideo).order_by(RawYouTubeVideo.ingested_at.desc()).limit(limit).all()
    )
    return RawYouTubeListResponse(
        items=[RawYouTubeVideoResponse.model_validate(item) for item in items],
        total=total,
    )
