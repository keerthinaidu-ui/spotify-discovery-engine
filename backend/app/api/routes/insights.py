import json
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.feedback_item import FeedbackItem
from app.models.analysis_run import AnalysisRun
from app.services.analysis_service import trigger_analysis_run
from app.worker import worker
from app.schemas.analysis import (
    EvidenceItemResponse,
    InsightsCompareResponse,
    InsightsSummaryResponse,
    MetricCount,
    ChatRequest,
    ChatResponse,
)


router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/summary", response_model=InsightsSummaryResponse)
def get_insights_summary(
    platform: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    sentiment: str | None = Query(default=None),
    from_date: datetime | None = Query(default=None, alias="from"),
    to_date: datetime | None = Query(default=None, alias="to"),
    from_date_direct: datetime | None = Query(default=None, alias="from_date"),
    to_date_direct: datetime | None = Query(default=None, alias="to_date"),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    q: str | None = Query(default=None),
    user_segment: str | None = Query(default=None),
    rating: float | None = Query(default=None, ge=1.0, le=5.0),
    app_version: str | None = Query(default=None),
    issue_category: str | None = Query(default=None),
    primary_theme: str | None = Query(default=None),
    secondary_tag: str | None = Query(default=None),
    has_mixed_sentiment: bool | None = Query(default=None),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
) -> InsightsSummaryResponse:
    # 1. Handle Date filters
    actual_from = from_date if from_date is not None else (from_date_direct if from_date_direct is not None else start_date)
    actual_to = to_date if to_date is not None else (to_date_direct if to_date_direct is not None else end_date)

    # 2. Build filtered query
    query = db.query(FeedbackItem)

    # Filter by platform
    if platform is not None:
        normalized_platform = "play_store" if platform == "google_play" else platform
        query = query.filter(FeedbackItem.platform == normalized_platform)

    # Filter by source_type
    if source_type is not None:
        query = query.filter(FeedbackItem.source_type == source_type)

    if has_mixed_sentiment is not None:
        query = query.filter(FeedbackItem.has_mixed_sentiment == has_mixed_sentiment)

    # Filter by sentiment
    if sentiment is not None:
        if sentiment == "positive":
            query = query.filter(
                or_(
                    FeedbackItem.sentiment.in_(["positive", "User Satisfaction"]),
                    and_(
                        FeedbackItem.sentiment.is_(None),
                        FeedbackItem.rating_or_score >= 4.0
                    )
                )
            )
        elif sentiment == "negative":
            query = query.filter(
                or_(
                    FeedbackItem.sentiment.in_(["negative", "User Frustration"]),
                    and_(
                        FeedbackItem.sentiment.is_(None),
                        FeedbackItem.rating_or_score <= 2.0
                    )
                )
            )
        elif sentiment == "neutral":
            query = query.filter(
                or_(
                    FeedbackItem.sentiment.in_(["neutral", "Neutral"]),
                    and_(
                        FeedbackItem.sentiment.is_(None),
                        FeedbackItem.rating_or_score == 3.0
                    )
                )
            )
        elif sentiment in ("unclear", "unknown"):
            query = query.filter(
                or_(
                    FeedbackItem.sentiment.in_(["unclear", "unknown"]),
                    and_(
                        FeedbackItem.sentiment.is_(None),
                        FeedbackItem.rating_or_score.is_(None)
                    )
                )
            )

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

    # Filter by issue_category or primary_theme (with legacy fallback)
    if primary_theme is not None and primary_theme.strip():
        val = primary_theme.strip()
        query = query.filter(
            or_(
                FeedbackItem.primary_theme == val,
                and_(FeedbackItem.primary_theme.is_(None), FeedbackItem.issue_category == val)
            )
        )
    elif issue_category is not None and issue_category.strip():
        val = issue_category.strip()
        query = query.filter(
            or_(
                FeedbackItem.primary_theme == val,
                and_(FeedbackItem.primary_theme.is_(None), FeedbackItem.issue_category == val)
            )
        )

    # Filter by secondary_tag
    if secondary_tag is not None and secondary_tag.strip():
        secondary_tag_lower = secondary_tag.strip().lower()
        query = query.filter(func.lower(FeedbackItem.secondary_tags).like(f'%"{secondary_tag_lower}"%'))

    # Filter by date range
    if actual_from is not None:
        query = query.filter(FeedbackItem.created_at >= actual_from)
    if actual_to is not None:
        query = query.filter(FeedbackItem.created_at <= actual_to)

    # Filter by case-insensitive text search
    if q is not None and q.strip():
        q_lower = q.strip().lower()
        query = query.filter(
            func.lower(FeedbackItem.text).like(f"%{q_lower}%")
            | func.coalesce(func.lower(FeedbackItem.title), "").like(f"%{q_lower}%")
        )

    # 3. Check for active runs or pending items to see if analysis is in progress
    pending_count = db.query(FeedbackItem).filter(
        FeedbackItem.analysis_status.in_(["pending", "processing"])
    ).count()
    active_run = db.query(AnalysisRun).filter(AnalysisRun.status == "running").first()
    is_analyzing = worker.is_running and ((active_run is not None) or (pending_count > 0))

    # 4. Query matching analyzed items (strictly complete status)
    items = query.filter(FeedbackItem.analysis_status == "complete").all()
    total_analyzed = len(items)

    categories_map = {}
    segments_map = {}
    topics_map = {}
    unmet_needs_map = {}
    secondary_tags_map = {}

    for item in items:
        # Category (Primary Theme)
        prim_theme = item.primary_theme or item.issue_category
        if prim_theme:
            categories_map[prim_theme] = categories_map.get(prim_theme, 0) + 1
        # Segment
        if item.user_segment:
            segments_map[item.user_segment] = segments_map.get(item.user_segment, 0) + 1

        # Topics (JSON list)
        if item.topics:
            try:
                topics_list = json.loads(item.topics)
                if isinstance(topics_list, list):
                    for t in topics_list:
                        topics_map[t] = topics_map.get(t, 0) + 1
            except Exception:
                pass

        # Unmet Needs (JSON list)
        if item.unmet_needs:
            try:
                needs_list = json.loads(item.unmet_needs)
                if isinstance(needs_list, list):
                    for n in needs_list:
                        unmet_needs_map[n] = unmet_needs_map.get(n, 0) + 1
            except Exception:
                pass

        # Secondary Tags (JSON list)
        if item.secondary_tags:
            try:
                tags_list = json.loads(item.secondary_tags)
                if isinstance(tags_list, list):
                    for tag in tags_list:
                        secondary_tags_map[tag] = secondary_tags_map.get(tag, 0) + 1
            except Exception:
                pass

    top_categories = [
        MetricCount(name=k, count=v)
        for k, v in sorted(categories_map.items(), key=lambda x: x[1], reverse=True)
    ]
    top_topics = [
        MetricCount(name=k, count=v)
        for k, v in sorted(topics_map.items(), key=lambda x: x[1], reverse=True)
    ]
    top_segments = [
        MetricCount(name=k, count=v)
        for k, v in sorted(segments_map.items(), key=lambda x: x[1], reverse=True)
    ]
    top_unmet_needs = [
        MetricCount(name=k, count=v)
        for k, v in sorted(unmet_needs_map.items(), key=lambda x: x[1], reverse=True)
    ]
    top_secondary_tags = [
        MetricCount(name=k, count=v)
        for k, v in sorted(secondary_tags_map.items(), key=lambda x: x[1], reverse=True)
    ]

    return InsightsSummaryResponse(
        total_analyzed=total_analyzed,
        top_categories=top_categories,
        top_topics=top_topics,
        top_segments=top_segments,
        top_unmet_needs=top_unmet_needs,
        top_secondary_tags=top_secondary_tags,
        is_analyzing=is_analyzing,
    )


@router.get("/compare", response_model=InsightsCompareResponse)
def get_insights_compare(
    compare_by: str = Query(default="source_type"),
    platform: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    sentiment: str | None = Query(default=None),
    from_date: datetime | None = Query(default=None, alias="from"),
    to_date: datetime | None = Query(default=None, alias="to"),
    from_date_direct: datetime | None = Query(default=None, alias="from_date"),
    to_date_direct: datetime | None = Query(default=None, alias="to_date"),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    q: str | None = Query(default=None),
    user_segment: str | None = Query(default=None),
    rating: float | None = Query(default=None, ge=1.0, le=5.0),
    app_version: str | None = Query(default=None),
    issue_category: str | None = Query(default=None),
    primary_theme: str | None = Query(default=None),
    secondary_tag: str | None = Query(default=None),
    has_mixed_sentiment: bool | None = Query(default=None),
    db: Session = Depends(get_db),
) -> InsightsCompareResponse:
    if compare_by not in ("source_type", "platform"):
        raise HTTPException(
            status_code=400,
            detail="Invalid compare_by value. Allowed values: 'source_type', 'platform'.",
        )

    # 1. Handle Date filters
    actual_from = from_date if from_date is not None else (from_date_direct if from_date_direct is not None else start_date)
    actual_to = to_date if to_date is not None else (to_date_direct if to_date_direct is not None else end_date)

    # 2. Build filtered query
    query = db.query(FeedbackItem)

    # Filter by platform
    if platform is not None:
        normalized_platform = "play_store" if platform == "google_play" else platform
        query = query.filter(FeedbackItem.platform == normalized_platform)

    # Filter by source_type
    if source_type is not None:
        query = query.filter(FeedbackItem.source_type == source_type)

    if has_mixed_sentiment is not None:
        query = query.filter(FeedbackItem.has_mixed_sentiment == has_mixed_sentiment)

    # Filter by sentiment
    if sentiment is not None:
        if sentiment == "positive":
            query = query.filter(
                or_(
                    FeedbackItem.sentiment == "positive",
                    and_(
                        FeedbackItem.sentiment.is_(None),
                        FeedbackItem.rating_or_score >= 4.0
                    )
                )
            )
        elif sentiment == "negative":
            query = query.filter(
                or_(
                    FeedbackItem.sentiment == "negative",
                    and_(
                        FeedbackItem.sentiment.is_(None),
                        FeedbackItem.rating_or_score <= 2.0
                    )
                )
            )
        elif sentiment == "neutral":
            query = query.filter(
                or_(
                    FeedbackItem.sentiment == "neutral",
                    and_(
                        FeedbackItem.sentiment.is_(None),
                        FeedbackItem.rating_or_score == 3.0
                    )
                )
            )
        elif sentiment in ("unclear", "unknown"):
            query = query.filter(
                or_(
                    FeedbackItem.sentiment.in_(["unclear", "unknown"]),
                    and_(
                        FeedbackItem.sentiment.is_(None),
                        FeedbackItem.rating_or_score.is_(None)
                    )
                )
            )

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

    # Filter by issue_category or primary_theme (with legacy fallback)
    if primary_theme is not None and primary_theme.strip():
        val = primary_theme.strip()
        query = query.filter(
            or_(
                FeedbackItem.primary_theme == val,
                and_(FeedbackItem.primary_theme.is_(None), FeedbackItem.issue_category == val)
            )
        )
    elif issue_category is not None and issue_category.strip():
        val = issue_category.strip()
        query = query.filter(
            or_(
                FeedbackItem.primary_theme == val,
                and_(FeedbackItem.primary_theme.is_(None), FeedbackItem.issue_category == val)
            )
        )

    # Filter by secondary_tag
    if secondary_tag is not None and secondary_tag.strip():
        secondary_tag_lower = secondary_tag.strip().lower()
        query = query.filter(func.lower(FeedbackItem.secondary_tags).like(f'%"{secondary_tag_lower}"%'))

    # Filter by date range
    if actual_from is not None:
        query = query.filter(FeedbackItem.created_at >= actual_from)
    if actual_to is not None:
        query = query.filter(FeedbackItem.created_at <= actual_to)

    # Filter by case-insensitive text search
    if q is not None and q.strip():
        q_lower = q.strip().lower()
        query = query.filter(
            func.lower(FeedbackItem.text).like(f"%{q_lower}%")
            | func.coalesce(func.lower(FeedbackItem.title), "").like(f"%{q_lower}%")
        )

    items = query.filter(FeedbackItem.analysis_status == "complete").all()
    comparison = {}

    for item in items:
        key_val = item.source_type if compare_by == "source_type" else item.platform
        if not key_val:
            continue

        category = item.primary_theme or item.issue_category or "Unidentified"
        if key_val not in comparison:
            comparison[key_val] = {}
        comparison[key_val][category] = comparison[key_val].get(category, 0) + 1

    return InsightsCompareResponse(compare_by=compare_by, comparison=comparison)


@router.get("/{theme}/evidence", response_model=list[EvidenceItemResponse])
def get_insights_evidence(
    theme: str,
    db: Session = Depends(get_db),
) -> list[EvidenceItemResponse]:
    items = db.query(FeedbackItem).filter(FeedbackItem.analysis_status == "complete").all()
    evidence_list = []

    theme_lower = theme.lower().strip()

    for item in items:
        matches = False

        # Check topics
        if item.topics:
            try:
                topics_list = json.loads(item.topics)
                if isinstance(topics_list, list) and any(
                    t.lower().strip() == theme_lower for t in topics_list
                ):
                    matches = True
            except Exception:
                pass

        # Check unmet needs
        if not matches and item.unmet_needs:
            try:
                needs_list = json.loads(item.unmet_needs)
                if isinstance(needs_list, list) and any(
                    n.lower().strip() == theme_lower for n in needs_list
                ):
                    matches = True
            except Exception:
                pass

        if matches:
            quotes = []
            if item.analysis_evidence:
                try:
                    evidence_data = json.loads(item.analysis_evidence)
                    if isinstance(evidence_data, list):
                        for ev in evidence_data:
                            if isinstance(ev, dict):
                                quote_text = ev.get("quote")
                                if quote_text:
                                    quotes.append(quote_text)
                except Exception:
                    pass

            if not quotes:
                quotes = [item.text]

            for quote in quotes:
                evidence_list.append(
                    EvidenceItemResponse(
                        feedback_id=item.id,
                        source_type=item.source_type,
                        platform=item.platform,
                        text=item.text,
                        author=item.author,
                        quote=quote,
                        confidence=item.analysis_confidence,
                    )
                )

    return evidence_list


def consolidate_terms(term_counts: dict[str, int]) -> dict[str, int]:
    """
    Consolidates semantically similar or spelling variations of terms (topics or unmet needs)
    using predefined Voice of Customer taxonomy rules and singularization heuristics.
    """
    consolidated = {}
    display_map = {}
    
    rules = {
        "repetitive recommendations": ["same songs", "repetitive", "repeat", "looping", "same track", "repeating", "old songs again", "stale mixes", "loops"],
        "discovery friction": ["can't discover", "hard to find new", "no variety", "stale algorithm", "discover new music", "finding new", "stale recommendation", "unmet recommendation", "no discovery"],
        "wrong taste alignment": ["wrong recommendation", "not my taste", "don't like", "unrelated", "taste profile mismatch", "bad mix"],
        "missing customization": ["want more control", "can't tune", "cannot customize", "hide song", "block artist", "filter recommendation", "dislike button"]
    }
    
    for term, count in term_counts.items():
        if not term or not term.strip():
            continue
        cleaned = term.strip().lower()
        
        # Check rule mapping
        mapped = None
        for canonical, variations in rules.items():
            if cleaned == canonical or any(v in cleaned for v in variations):
                mapped = canonical
                break
                
        if not mapped:
            # Singularization heuristics
            if cleaned.endswith("ies"):
                cleaned = cleaned[:-3] + "y"
            elif cleaned.endswith("es") and cleaned[:-2] in ("crash", "freeze", "glitch", "box", "bus"):
                cleaned = cleaned[:-2]
            elif cleaned.endswith("s") and not cleaned.endswith("ss") and not cleaned.endswith("us") and len(cleaned) > 3:
                cleaned = cleaned[:-1]
            mapped = cleaned
            
        consolidated[mapped] = consolidated.get(mapped, 0) + count
        
        # Select best formatting for display
        if mapped not in display_map or count > term_counts.get(display_map[mapped], 0):
            display_map[mapped] = term
            
    result = {}
    for key, count in consolidated.items():
        if key in rules:
            display_name = key.title()
        else:
            display_name = display_map.get(key, key)
        result[display_name] = result.get(display_name, 0) + count
        
    return result


@router.post("/chat", response_model=ChatResponse)
def chat_about_feedback(
    req: ChatRequest,
    db: Session = Depends(get_db)
) -> ChatResponse:
    from app.config import get_settings
    settings = get_settings()
    
    # Calculate coverage metrics
    total_ingested = db.query(FeedbackItem).count()
    total_analyzed = db.query(FeedbackItem).filter(FeedbackItem.analysis_status == "complete").count()
    percent_analyzed = (total_analyzed / total_ingested * 100.0) if total_ingested > 0 else 0.0
    
    pending = db.query(FeedbackItem).filter(
        FeedbackItem.analysis_status.in_(["pending", "processing"])
    ).count()
    is_analysis_in_progress = worker.is_running and (pending > 0)

    # 1. Build filtered query using canonical filters
    query = db.query(FeedbackItem).filter(FeedbackItem.analysis_status == "complete")

    if req.platform is not None:
        query = query.filter(FeedbackItem.platform == req.platform)
    if req.source_type is not None:
        query = query.filter(FeedbackItem.source_type == req.source_type)

    if req.sentiment is not None:
        if req.sentiment == "positive" or req.sentiment == "User Satisfaction":
            query = query.filter(
                or_(
                    FeedbackItem.sentiment == "positive",
                    FeedbackItem.sentiment == "User Satisfaction",
                    and_(
                        FeedbackItem.sentiment.is_(None),
                        FeedbackItem.rating_or_score >= 4.0
                    )
                )
            )
        elif req.sentiment == "negative" or req.sentiment == "User Frustration":
            query = query.filter(
                or_(
                    FeedbackItem.sentiment == "negative",
                    FeedbackItem.sentiment == "User Frustration",
                    and_(
                        FeedbackItem.sentiment.is_(None),
                        FeedbackItem.rating_or_score <= 2.0
                    )
                )
            )
        elif req.sentiment == "neutral" or req.sentiment == "Neutral":
            query = query.filter(
                or_(
                    FeedbackItem.sentiment == "neutral",
                    FeedbackItem.sentiment == "Neutral",
                    and_(
                        FeedbackItem.sentiment.is_(None),
                        FeedbackItem.rating_or_score == 3.0
                    )
                )
            )
        elif req.sentiment in ("unknown", "unclear"):
            query = query.filter(
                or_(
                    FeedbackItem.sentiment.in_(["unknown", "unclear"]),
                    and_(
                        FeedbackItem.sentiment.is_(None),
                        FeedbackItem.rating_or_score.is_(None)
                    )
                )
            )

    if req.has_mixed_sentiment is not None:
        query = query.filter(FeedbackItem.has_mixed_sentiment == req.has_mixed_sentiment)

    if req.primary_theme is not None:
        query = query.filter(FeedbackItem.primary_theme == req.primary_theme)
    elif req.issue_category is not None:
        query = query.filter(FeedbackItem.primary_theme == req.issue_category)

    if req.secondary_tag is not None and req.secondary_tag.strip():
        secondary_tag_lower = req.secondary_tag.strip().lower()
        query = query.filter(func.lower(FeedbackItem.secondary_tags).like(f'%"{secondary_tag_lower}"%'))

    if req.topic is not None and req.topic.strip():
        topic_lower = req.topic.strip().lower()
        query = query.filter(func.lower(FeedbackItem.topics).like(f"%{topic_lower}%"))

    if req.user_segment is not None and req.user_segment.strip():
        segment_lower = req.user_segment.strip().lower()
        query = query.filter(func.lower(FeedbackItem.user_segment).like(f"%{segment_lower}%"))

    if req.rating is not None:
        query = query.filter(FeedbackItem.rating_or_score == req.rating)
    else:
        if req.rating_min is not None:
            query = query.filter(FeedbackItem.rating_or_score >= req.rating_min)
        if req.rating_max is not None:
            query = query.filter(FeedbackItem.rating_or_score <= req.rating_max)

    if req.from_date is not None:
        query = query.filter(FeedbackItem.created_at >= req.from_date)
    if req.to_date is not None:
        query = query.filter(FeedbackItem.created_at <= req.to_date)

    if req.q is not None and req.q.strip():
        q_lower = req.q.strip().lower()
        query = query.filter(
            func.lower(FeedbackItem.text).like(f"%{q_lower}%")
            | func.coalesce(func.lower(FeedbackItem.title), "").like(f"%{q_lower}%")
        )

    total_count = query.count()

    # Zero results handling
    if total_count == 0:
        disclaimer = ""
        if percent_analyzed < 100.0:
            disclaimer = f"\n\n*Note: This analysis is synthesized from the {percent_analyzed:.2f}% of the corpus that has been analyzed so far.*"
        
        return ChatResponse(
            answer="No feedback records found matching the active filters. Please adjust your criteria and try again." + disclaimer,
            total_count=0,
            source_breakdown={},
            evidence_snippets=[],
            llm_used=False,
            mode="fallback",
            percent_analyzed=round(percent_analyzed, 2),
            is_analysis_in_progress=is_analysis_in_progress,
        )

    # 2. Database Aggregations
    # Source type counts
    source_rows = (
        query.with_entities(FeedbackItem.source_type, func.count(FeedbackItem.id))
        .group_by(FeedbackItem.source_type)
        .all()
    )
    source_breakdown = {row[0]: row[1] for row in source_rows if row[0] is not None}

    # Issue Category Counts
    category_rows = (
        query.with_entities(FeedbackItem.issue_category, func.count(FeedbackItem.id))
        .group_by(FeedbackItem.issue_category)
        .order_by(func.count(FeedbackItem.id).desc())
        .all()
    )
    category_counts = [(row[0] or "Unidentified", row[1]) for row in category_rows]

    # Recommendation Pain Type Counts
    pain_rows = (
        query.with_entities(FeedbackItem.recommendation_pain_type, func.count(FeedbackItem.id))
        .group_by(FeedbackItem.recommendation_pain_type)
        .order_by(func.count(FeedbackItem.id).desc())
        .all()
    )
    pain_counts = [(row[0] or "none", row[1]) for row in pain_rows]

    # Blocked Goal Counts
    goal_rows = (
        query.with_entities(FeedbackItem.blocked_goal, func.count(FeedbackItem.id))
        .group_by(FeedbackItem.blocked_goal)
        .order_by(func.count(FeedbackItem.id).desc())
        .limit(10).all()
    )
    goal_counts = [(row[0] or "unknown", row[1]) for row in goal_rows if row[0] is not None]

    # Root Cause Counts
    cause_rows = (
        query.with_entities(FeedbackItem.root_cause, func.count(FeedbackItem.id))
        .group_by(FeedbackItem.root_cause)
        .order_by(func.count(FeedbackItem.id).desc())
        .limit(10).all()
    )
    cause_counts = [(row[0] or "unknown", row[1]) for row in cause_rows if row[0] is not None]

    # Platform Counts
    platform_rows = (
        query.with_entities(FeedbackItem.platform, func.count(FeedbackItem.id))
        .group_by(FeedbackItem.platform)
        .order_by(func.count(FeedbackItem.id).desc())
        .all()
    )
    platform_counts = [(row[0], row[1]) for row in platform_rows]

    # Rating Band Counts
    rating_band_counts = {"High (4-5)": 0, "Medium (3)": 0, "Low (1-2)": 0, "Unknown": 0}
    rating_rows = query.with_entities(FeedbackItem.rating_or_score).all()
    for (rating,) in rating_rows:
        if rating is None:
            rating_band_counts["Unknown"] += 1
        elif rating >= 4.0:
            rating_band_counts["High (4-5)"] += 1
        elif rating <= 2.0:
            rating_band_counts["Low (1-2)"] += 1
        else:
            rating_band_counts["Medium (3)"] += 1

    # Sample items for Topics, Unmet Needs, Segment Signals, Secondary Tags, and Aspects
    sample_rows = (
        query.with_entities(
            FeedbackItem.topics,
            FeedbackItem.unmet_needs,
            FeedbackItem.user_segment_signals,
            FeedbackItem.secondary_tags,
            FeedbackItem.has_mixed_sentiment,
            FeedbackItem.sentiment_profile
        )
        .order_by(FeedbackItem.created_at.desc())
        .limit(5000).all()
    )
    sample_total = max(1, len(sample_rows))

    raw_topics = {}
    raw_needs = {}
    raw_secondary_tags = {}
    raw_pos_aspects = {}
    raw_neg_aspects = {}
    mixed_count = 0
    premium_vs_free = {"premium_subscriber": 0, "free_tier": 0, "unknown": 0}
    co_occurrences = {}

    for topics_json, needs_json, signals_json, secondary_tags_json, has_mixed, profile_json in sample_rows:
        topics_list = []
        needs_list = []
        
        if topics_json:
            try:
                topics_list = json.loads(topics_json)
                if isinstance(topics_list, list):
                    for t in topics_list:
                        raw_topics[t] = raw_topics.get(t, 0) + 1
            except Exception:
                pass
                
        if needs_json:
            try:
                needs_list = json.loads(needs_json)
                if isinstance(needs_list, list):
                    for n in needs_list:
                        raw_needs[n] = raw_needs.get(n, 0) + 1
            except Exception:
                pass

        if secondary_tags_json:
            try:
                tags_list = json.loads(secondary_tags_json)
                if isinstance(tags_list, list):
                    for tag in tags_list:
                        raw_secondary_tags[tag] = raw_secondary_tags.get(tag, 0) + 1
            except Exception:
                pass

        if has_mixed:
            mixed_count += 1

        if profile_json:
            try:
                prof = json.loads(profile_json)
                if isinstance(prof, dict):
                    pos_list = prof.get("positive_aspects", [])
                    if isinstance(pos_list, list):
                        for pa in pos_list:
                            raw_pos_aspects[pa] = raw_pos_aspects.get(pa, 0) + 1
                    neg_list = prof.get("negative_aspects", [])
                    if isinstance(neg_list, list):
                        for na in neg_list:
                            raw_neg_aspects[na] = raw_neg_aspects.get(na, 0) + 1
            except Exception:
                pass

        if signals_json:
            try:
                signals = json.loads(signals_json)
                if isinstance(signals, list):
                    if "premium_subscriber" in signals:
                        premium_vs_free["premium_subscriber"] += 1
                    if "free_tier" in signals:
                        premium_vs_free["free_tier"] += 1
                    if "premium_subscriber" not in signals and "free_tier" not in signals:
                        premium_vs_free["unknown"] += 1
            except Exception:
                pass

        for t in topics_list:
            for n in needs_list:
                pair = tuple(sorted([t.strip(), n.strip()]))
                co_occurrences[pair] = co_occurrences.get(pair, 0) + 1

    consolidated_topics = consolidate_terms(raw_topics)
    consolidated_needs = consolidate_terms(raw_needs)

    sorted_topics = sorted(consolidated_topics.items(), key=lambda x: x[1], reverse=True)
    sorted_needs = sorted(consolidated_needs.items(), key=lambda x: x[1], reverse=True)
    sorted_secondary_tags = sorted(raw_secondary_tags.items(), key=lambda x: x[1], reverse=True)
    sorted_co_occurrences = sorted(co_occurrences.items(), key=lambda x: x[1], reverse=True)

    # 3. Retrieve Representative Evidence Quotes
    evidence_rows = (
        query.order_by(FeedbackItem.created_at.desc())
        .limit(10).all()
    )
    evidence_quotes = []
    for item in evidence_rows:
        quote_text = item.evidence_quote or item.text
        if quote_text:
            evidence_quotes.append({
                "quote": quote_text,
                "author": item.author or "Anonymous",
                "category": item.issue_category or "Unidentified",
                "pain_type": item.recommendation_pain_type or "none"
            })

    # Pull in semantic search results if query is specific and embedding enabled
    selected_items = []
    evidence_snippets = []
    semantic_mode = False
    
    from app.services.embedding_service import EmbeddingService
    embedding_service = EmbeddingService(settings)
    if embedding_service.enabled:
        active_filters = {
            "platform": req.platform,
            "sentiment": req.sentiment,
            "start_date": req.from_date.isoformat() if req.from_date else None,
            "end_date": req.to_date.isoformat() if req.to_date else None,
        }
        try:
            semantic_results = embedding_service.retrieve_relevant_reviews(db, req.query, active_filters=active_filters)
            if semantic_results:
                semantic_mode = True
                selected_items = [item for item, chunk_text, score in semantic_results[:3]]
                evidence_snippets = [chunk_text for item, chunk_text, score in semantic_results[:3]]
        except Exception:
            pass

    # 4. Generate LLM Answer
    category_summary_text = "\n".join([f"- {cat}: {cnt} mentions ({cnt/total_count*100.0:.1f}%)" for cat, cnt in category_counts[:5]])
    secondary_tags_summary_text = "\n".join([f"- {tag}: {cnt} mentions ({cnt/sample_total*100.0:.1f}% of sample)" for tag, cnt in sorted_secondary_tags[:10]])
    pain_summary_text = "\n".join([f"- {pain}: {cnt} mentions ({cnt/total_count*100.0:.1f}%)" for pain, cnt in pain_counts if pain != "none"])
    goal_summary_text = "\n".join([f"- {goal}: {cnt} mentions" for goal, cnt in goal_counts[:5]])
    cause_summary_text = "\n".join([f"- {cause}: {cnt} mentions" for cause, cnt in cause_counts[:5]])
    
    topic_summary_text = "\n".join([f"- {top}: {cnt} mentions ({cnt/sample_total*100.0:.1f}% of sample)" for top, cnt in sorted_topics[:5]])
    need_summary_text = "\n".join([f"- {need}: {cnt} mentions ({cnt/sample_total*100.0:.1f}% of sample)" for need, cnt in sorted_needs[:5]])
    
    co_occur_text = "\n".join([f"- {pair[0]} + {pair[1]}: {cnt} co-occurrences" for pair, cnt in sorted_co_occurrences[:5]])
    
    platform_summary_text = "\n".join([f"- {plat}: {cnt} mentions" for plat, cnt in platform_counts])
    rating_summary_text = "\n".join([f"- {band}: {cnt} reviews" for band, cnt in rating_band_counts.items()])
    premium_summary_text = f"- Premium Subscriber: {premium_vs_free['premium_subscriber']} reviews\n- Free Tier: {premium_vs_free['free_tier']} reviews"
    
    pos_aspects_summary_text = "\n".join([f"- {asp}: {cnt} mentions" for asp, cnt in sorted(raw_pos_aspects.items(), key=lambda x: x[1], reverse=True)[:10]])
    neg_aspects_summary_text = "\n".join([f"- {asp}: {cnt} mentions" for asp, cnt in sorted(raw_neg_aspects.items(), key=lambda x: x[1], reverse=True)[:10]])

    quotes_text = ""
    for idx, eq in enumerate(evidence_quotes[:5]):
        quotes_text += f'{idx+1}. "{eq["quote"]}" (Category: {eq["category"]}, Pain Segment: {eq["pain_type"]}, User: {eq["author"]})\n'

    specific_reviews_text = ""
    if selected_items:
        specific_reviews_text += "\n[Semantically Relevant Reviews]\n"
        for idx, item in enumerate(selected_items[:3]):
            snippet = evidence_snippets[idx] if idx < len(evidence_snippets) else item.text[:200]
            specific_reviews_text += f"Review #{idx+1} (Category: {item.primary_theme or item.issue_category or 'N/A'}, Rating: {item.rating_or_score or 'N/A'}):\n"
            specific_reviews_text += f'  "{snippet}"\n'

    llm_success = False
    answer_text = ""

    try:
        from app.services.llm_service import LLMService
        llm = LLMService(settings)
        has_key = bool(settings.gemini_api_key or settings.groq_api_key)
        if not has_key:
            raise ValueError("No API key configured")

        llm_prompt = f"""You are Sonic AI, the dataset-grounded Voice of Customer analytics assistant for the Spotify Review Discovery Engine.
Your job is to answer the user's strategic aggregate question using only the structured dataset analysis provided below.

The user is asking: "{req.query}"

Here are the structured metrics and aggregations for the matching feedback dataset:
Total matching feedback records: {total_count}
Total mixed sentiment reviews in sample: {mixed_count}

[Top Standardized Positive Aspects]
{pos_aspects_summary_text or "No standardized positive aspects."}

[Top Standardized Negative Aspects]
{neg_aspects_summary_text or "No standardized negative aspects."}

[Top Primary Themes (Ranked by Frequency)]
{category_summary_text or "No primary themes detected."}

[Top Secondary Tags (Themes) (Ranked by Frequency)]
{secondary_tags_summary_text or "No secondary tags detected."}

[Top Recommendation Frustrations (Pain Types)]
{pain_summary_text or "No recommendation pain types detected."}

[Top Blocked User Goals (Ranked by Frequency)]
{goal_summary_text or "No blocked goals detected."}

[Top Root Causes (Ranked by Frequency)]
{cause_summary_text or "No root causes detected."}

[Top Topics/Themes (Ranked by Frequency, Consolidated)]
{topic_summary_text or "No topics detected."}

[Top Unmet Needs (Ranked by Frequency, Consolidated)]
{need_summary_text or "No unmet needs detected."}

[Top Topic/Need Co-occurrences]
{co_occur_text or "No co-occurrences detected."}

[Segment & Demographics Breakdowns]
Platform/Source:
{platform_summary_text}
Rating Band:
{rating_summary_text}
Premium vs Free:
{premium_summary_text}

[Representative Evidence Quotes]
{quotes_text or "No quotes available."}
{specific_reviews_text}

Format your response in markdown matching this structure:
### 1. Direct Answer
A 1-2 sentence direct summary answering the query.

### 2. Key Findings
Ranked findings with counts and percentages, referencing specific categories, topics, or goals. Cite numbers explicitly (e.g. "Playback Reliability (45 mentions)").

### 3. Segment Differences
Detailed comparison of subgroups (e.g., premium vs free, mobile vs CarPlay) if relevant.

### 4. Representative Quotes
Include 2 to 5 direct evidence quotes from the evidence list above to illustrate findings.

### 5. Caveats & Limitations
Confidence caveats (e.g., noting that this represents user-reported perceptions in reviews rather than telemetry logs).

Provide your response in JSON format matching this schema:
{{
  "answer": "The full formatted markdown string following the 5-part structure above.",
  "evidence_snippets": ["Direct quote or excerpt from the evidence list that serves as support."]
}}

Enforce valid JSON. Return ONLY the JSON object and nothing else."""

        result_text, provider_used, model_used, was_fallback = llm.generate_text(llm_prompt, response_mime_type="application/json")
        parsed = llm._clean_and_parse_json(result_text)

        if "answer" in parsed:
            answer_text = parsed["answer"]
            if parsed.get("evidence_snippets"):
                evidence_snippets = parsed["evidence_snippets"][:5]
            llm_success = True

    except Exception:
        pass

    if not llm_success:
        # Structured Local Heuristic Fallback
        cats_desc = "\n".join([f"- **{cat}**: {cnt} mentions ({cnt/total_count*100.0:.1f}%)" for cat, cnt in category_counts[:3]])
        top_topics_desc = "\n".join([f"- **{top}**: {cnt} mentions ({cnt/sample_total*100.0:.1f}% of sample)" for top, cnt in sorted_topics[:3]])
        top_needs_desc = "\n".join([f"- **{need}**: {cnt} mentions ({cnt/sample_total*100.0:.1f}% of sample)" for need, cnt in sorted_needs[:3]])
        
        fallback_quotes = [q["quote"] for q in evidence_quotes[:3]]
        quotes_markdown = "\n".join([f'- *"{q}"*' for q in fallback_quotes])

        answer_text = f"""### 1. Direct Answer
Based on {total_count} feedback entries, the top issues are centered around category distributions and user frustration metrics.

### 2. Key Findings
**Top Issue Categories**:
{cats_desc or "None"}

**Top Themes**:
{top_topics_desc or "None"}

**Top Unmet Needs**:
{top_needs_desc or "None"}

### 3. Segment Differences
**Platform Distribution**:
{platform_summary_text or "None"}

**Premium vs Free**:
{premium_summary_text or "None"}

### 4. Representative Quotes
{quotes_markdown or "No quotes available."}

### 5. Caveats & Limitations
This aggregation is based on user perceptions from reviews and may not represent backend behavioral telemetry.
"""
        evidence_snippets = fallback_quotes

    if percent_analyzed < 100.0:
        answer_text += f"\n\n*Note: This analysis is synthesized from the {percent_analyzed:.2f}% of the corpus that has been analyzed so far.*"

    return ChatResponse(
        answer=answer_text,
        total_count=total_count,
        source_breakdown=source_breakdown,
        evidence_snippets=evidence_snippets,
        llm_used=llm_success,
        mode="llm" if llm_success else "fallback",
        percent_analyzed=round(percent_analyzed, 2),
        is_analysis_in_progress=is_analysis_in_progress,
    )
