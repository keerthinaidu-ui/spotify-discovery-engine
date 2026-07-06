from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.feedback_item import FeedbackItem
from app.models.analysis_run import AnalysisRun
from app.services.analysis_service import trigger_analysis_run
from app.schemas.feedback_item import (
    FeedbackItemListResponse,
    FeedbackItemResponse,
    NormalizationResponse,
    FeedbackStatsOverviewResponse,
    FeedbackStatsCompareResponse,
    DateBucket,
    SourceCompareMetric,
)
from app.services.normalization_service import run_normalization

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("/normalize", response_model=NormalizationResponse)
def normalize_reviews(db: Session = Depends(get_db)) -> NormalizationResponse:
    try:
        counts = run_normalization(db)
        status = "success" if counts["failed"] == 0 else "completed_with_errors"
        return NormalizationResponse(
            status=status,
            processed=counts["processed"],
            inserted=counts["inserted"],
            skipped=counts["skipped"],
            dropped=counts["dropped"],
            failed=counts["failed"],
        )
    except Exception:
        return NormalizationResponse(
            status="failed",
            processed=0,
            inserted=0,
            skipped=0,
            dropped=0,
            failed=0,
        )


@router.get("", response_model=FeedbackItemListResponse)
def list_feedback(
    limit: int | None = Query(default=None, ge=1, le=100),
    offset: int | None = Query(default=None, ge=0),
    page: int | None = Query(default=None, ge=1),
    per_page: int | None = Query(default=None, ge=1, le=100),
    platform: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    sentiment: str | None = Query(default=None),
    rating: float | None = Query(default=None, ge=1.0, le=5.0),
    rating_min: float | None = Query(default=None, ge=1.0, le=5.0),
    rating_max: float | None = Query(default=None, ge=1.0, le=5.0),
    from_date: datetime | None = Query(default=None, alias="from"),
    to_date: datetime | None = Query(default=None, alias="to"),
    from_date_direct: datetime | None = Query(default=None, alias="from_date"),
    to_date_direct: datetime | None = Query(default=None, alias="to_date"),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    q: str | None = Query(default=None),
    issue_category: str | None = Query(default=None),
    primary_theme: str | None = Query(default=None),
    secondary_tag: str | None = Query(default=None),
    topic: str | None = Query(default=None),
    user_segment: str | None = Query(default=None),
    app_version: str | None = Query(default=None),
    has_mixed_sentiment: bool | None = Query(default=None),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc"),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None,
) -> FeedbackItemListResponse:
    # 1. Validate parameters
    if rating is not None and (rating_min is not None or rating_max is not None):
        raise HTTPException(
            status_code=400,
            detail="Cannot specify 'rating' together with 'rating_min' or 'rating_max'.",
        )

    if sort_by not in ("created_at", "rating", "id"):
        raise HTTPException(
            status_code=400,
            detail="Invalid sort_by parameter. Allowed values: 'created_at', 'rating', 'id'.",
        )

    if sort_order not in ("asc", "desc"):
        raise HTTPException(
            status_code=400,
            detail="Invalid sort_order parameter. Allowed values: 'asc', 'desc'.",
        )

    if sentiment is not None and sentiment.strip():
        sentiments = [s.strip() for s in sentiment.split(",") if s.strip()]
        for s in sentiments:
            if s not in ("positive", "neutral", "negative", "unclear", "unknown"):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid sentiment parameter. Allowed values: 'positive', 'neutral', 'negative', 'unclear', 'unknown'.",
                )

    # 2. Handle Pagination (support page/per_page or limit/offset)
    if page is not None or per_page is not None:
        p = page if page is not None else 1
        pp = per_page if per_page is not None else 10
        actual_limit = pp
        actual_offset = (p - 1) * pp
    else:
        actual_limit = limit if limit is not None else 10
        actual_offset = offset if offset is not None else 0

    # 3. Handle Date filters (support 'from'/'to', 'from_date'/'to_date', and 'start_date'/'end_date')
    actual_from = from_date if from_date is not None else (from_date_direct if from_date_direct is not None else start_date)
    actual_to = to_date if to_date is not None else (to_date_direct if to_date_direct is not None else end_date)

    # 4. Build filtered query
    query = db.query(FeedbackItem)

    # Filter by platform
    if platform is not None and platform.strip():
        platforms = [p.strip() for p in platform.split(",") if p.strip()]
        if platforms:
            # Map 'google_play' to 'play_store' to align with the database normalization schema
            normalized_platforms = ["play_store" if p == "google_play" else p for p in platforms]
            query = query.filter(FeedbackItem.platform.in_(normalized_platforms))

    # Filter by source_type
    if source_type is not None:
        query = query.filter(FeedbackItem.source_type == source_type)

    # Filter by sentiment (with rating-based fallback when sentiment is null)
    if sentiment is not None and sentiment.strip():
        sentiments = [s.strip() for s in sentiment.split(",") if s.strip()]
        if sentiments:
            clauses = []
            for sent in sentiments:
                if sent == "positive":
                    clauses.append(
                        or_(
                            FeedbackItem.sentiment.in_(["positive", "User Satisfaction"]),
                            and_(
                                FeedbackItem.sentiment.is_(None),
                                FeedbackItem.rating_or_score >= 4.0
                            )
                        )
                    )
                elif sent == "negative":
                    clauses.append(
                        or_(
                            FeedbackItem.sentiment.in_(["negative", "User Frustration"]),
                            and_(
                                FeedbackItem.sentiment.is_(None),
                                FeedbackItem.rating_or_score <= 2.0
                            )
                        )
                    )
                elif sent == "neutral":
                    clauses.append(
                        or_(
                            FeedbackItem.sentiment.in_(["neutral", "Neutral"]),
                            and_(
                                FeedbackItem.sentiment.is_(None),
                                FeedbackItem.rating_or_score == 3.0
                            )
                        )
                    )
                elif sent in ("unclear", "unknown"):
                    clauses.append(
                        or_(
                            FeedbackItem.sentiment.in_(["unclear", "unknown"]),
                            and_(
                                FeedbackItem.sentiment.is_(None),
                                FeedbackItem.rating_or_score.is_(None)
                            )
                        )
                    )
            if clauses:
                query = query.filter(or_(*clauses))

    if has_mixed_sentiment is not None:
        query = query.filter(FeedbackItem.has_mixed_sentiment == has_mixed_sentiment)

    # Filter by issue_category or primary_theme (with legacy fallback)
    if primary_theme is not None:
        query = query.filter(
            or_(
                FeedbackItem.primary_theme == primary_theme,
                and_(FeedbackItem.primary_theme.is_(None), FeedbackItem.issue_category == primary_theme)
            )
        )
    elif issue_category is not None:
        query = query.filter(
            or_(
                FeedbackItem.primary_theme == issue_category,
                and_(FeedbackItem.primary_theme.is_(None), FeedbackItem.issue_category == issue_category)
            )
        )

    # Filter by secondary_tag
    if secondary_tag is not None:
        secondary_tag_lower = secondary_tag.strip().lower()
        query = query.filter(func.lower(FeedbackItem.secondary_tags).like(f'%"{secondary_tag_lower}"%'))

    # Filter by topic
    if topic is not None and topic.strip():
        topic_lower = topic.strip().lower()
        query = query.filter(func.lower(FeedbackItem.topics).like(f"%{topic_lower}%"))

    # Filter by user_segment
    if user_segment is not None and user_segment.strip():
        segment_lower = user_segment.strip().lower()
        query = query.filter(func.lower(FeedbackItem.user_segment).like(f"%{segment_lower}%"))

    # Filter by app_version
    if app_version is not None and app_version.strip():
        query = query.filter(FeedbackItem.app_version == app_version.strip())

    # Filter by rating (exact or range)
    if rating is not None:
        query = query.filter(FeedbackItem.rating_or_score == rating)
    else:
        if rating_min is not None:
            query = query.filter(FeedbackItem.rating_or_score >= rating_min)
        if rating_max is not None:
            query = query.filter(FeedbackItem.rating_or_score <= rating_max)

    # Filter by date range
    if actual_from is not None:
        query = query.filter(FeedbackItem.created_at >= actual_from)
    if actual_to is not None:
        query = query.filter(FeedbackItem.created_at <= actual_to)

    # Filter by case-insensitive text search on text/title
    if q is not None and q.strip():
        q_lower = q.strip().lower()
        query = query.filter(
            func.lower(FeedbackItem.text).like(f"%{q_lower}%")
            | func.coalesce(func.lower(FeedbackItem.title), "").like(f"%{q_lower}%")
        )

    # 5. Count filtered total
    total = query.count()

    # 6. Apply deterministic ordering
    order_clauses = []
    if sort_by == "created_at":
        order_clauses.append(
            FeedbackItem.created_at.desc()
            if sort_order == "desc"
            else FeedbackItem.created_at.asc()
        )
    elif sort_by == "rating":
        order_clauses.append(
            FeedbackItem.rating_or_score.desc()
            if sort_order == "desc"
            else FeedbackItem.rating_or_score.asc()
        )

    # Fallback to ID sorting to guarantee determinism
    order_clauses.append(FeedbackItem.id.desc() if sort_order == "desc" else FeedbackItem.id.asc())
    query = query.order_by(*order_clauses)

    # 7. Apply offset/limit
    items = query.offset(actual_offset).limit(actual_limit).all()

    # Background analysis trigger removed to run strictly via scheduled worker and manual triggers

    # 8. Return response
    return FeedbackItemListResponse(
        items=[FeedbackItemResponse.model_validate(item) for item in items],
        total=total,
    )


@router.get("/stats/overview", response_model=FeedbackStatsOverviewResponse)
def get_stats_overview(
    from_date: datetime | None = Query(default=None, alias="from"),
    to_date: datetime | None = Query(default=None, alias="to"),
    from_date_direct: datetime | None = Query(default=None, alias="from_date"),
    to_date_direct: datetime | None = Query(default=None, alias="to_date"),
    db: Session = Depends(get_db),
) -> FeedbackStatsOverviewResponse:
    actual_from = from_date if from_date is not None else from_date_direct
    actual_to = to_date if to_date is not None else to_date_direct

    # Build base query
    base_query = db.query(FeedbackItem)
    if actual_from is not None:
        base_query = base_query.filter(FeedbackItem.created_at >= actual_from)
    if actual_to is not None:
        base_query = base_query.filter(FeedbackItem.created_at <= actual_to)

    # total_records
    total_records = base_query.count()

    # platform_counts
    platform_rows = (
        base_query.with_entities(FeedbackItem.platform, func.count(FeedbackItem.id))
        .group_by(FeedbackItem.platform)
        .all()
    )
    platform_counts = {row[0]: row[1] for row in platform_rows}

    # source_type_counts
    source_rows = (
        base_query.with_entities(FeedbackItem.source_type, func.count(FeedbackItem.id))
        .group_by(FeedbackItem.source_type)
        .all()
    )
    source_type_counts = {row[0]: row[1] for row in source_rows}

    # Dialect-aware time-series date_buckets grouping
    if db.bind.dialect.name == "postgresql":
        date_expr = func.to_char(FeedbackItem.created_at, "YYYY-MM-DD")
    else:
        date_expr = func.strftime("%Y-%m-%d", FeedbackItem.created_at)

    date_rows = (
        base_query.with_entities(
            date_expr.label("date"),
            func.count(FeedbackItem.id).label("count"),
        )
        .filter(FeedbackItem.created_at.isnot(None))
        .group_by(date_expr)
        .order_by(date_expr)
        .all()
    )
    date_buckets = [
        DateBucket(date=row[0], count=row[1]) for row in date_rows if row[0] is not None
    ]

    return FeedbackStatsOverviewResponse(
        total_records=total_records,
        platform_counts=platform_counts,
        source_type_counts=source_type_counts,
        date_buckets=date_buckets,
    )


@router.get("/stats/compare", response_model=FeedbackStatsCompareResponse)
def get_stats_compare(
    from_date: datetime | None = Query(default=None, alias="from"),
    to_date: datetime | None = Query(default=None, alias="to"),
    from_date_direct: datetime | None = Query(default=None, alias="from_date"),
    to_date_direct: datetime | None = Query(default=None, alias="to_date"),
    db: Session = Depends(get_db),
) -> FeedbackStatsCompareResponse:
    actual_from = from_date if from_date is not None else from_date_direct
    actual_to = to_date if to_date is not None else to_date_direct

    # Build base query
    base_query = db.query(FeedbackItem)
    if actual_from is not None:
        base_query = base_query.filter(FeedbackItem.created_at >= actual_from)
    if actual_to is not None:
        base_query = base_query.filter(FeedbackItem.created_at <= actual_to)

    # Group by source_type to get count and average rating
    rows = (
        base_query.with_entities(
            FeedbackItem.source_type,
            func.count(FeedbackItem.id),
            func.avg(FeedbackItem.rating_or_score),
        )
        .group_by(FeedbackItem.source_type)
        .all()
    )

    sources = {}
    for row in rows:
        source_type, count, avg_rating = row
        rounded_avg = round(avg_rating, 2) if avg_rating is not None else None
        sources[source_type] = SourceCompareMetric(count=count, avg_rating=rounded_avg)

    return FeedbackStatsCompareResponse(sources=sources)
