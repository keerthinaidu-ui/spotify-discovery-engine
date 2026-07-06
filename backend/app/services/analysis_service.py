from datetime import datetime, timezone
import json
import logging
import uuid
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.models.analysis_run import AnalysisRun
from app.models.feedback_item import FeedbackItem
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


def run_batch_analysis_job(
    run_id: str,
    limit: int,
    db_session: Session = None,
    platform: str | None = None,
    source_type: str | None = None,
    sentiment: str | None = None,
    q: str | None = None,
    user_segment: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
):
    """
    Background job that executes LLM analysis on feedback items.
    Uses a fresh DB session to ensure thread safety (unless db_session is provided).
    """
    db = db_session if db_session is not None else SessionLocal()
    close_db = db_session is None
    try:
        # Retrieve the run
        run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
        if not run:
            logger.error(f"Analysis run {run_id} not found in database.")
            return

        settings = get_settings()
        llm = LLMService(settings)

        # Get unanalyzed items matching filters
        query = db.query(FeedbackItem).filter(FeedbackItem.analyzed_at.is_(None))

        if platform is not None:
            query = query.filter(FeedbackItem.platform == platform)
        if source_type is not None:
            query = query.filter(FeedbackItem.source_type == source_type)
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
            elif sentiment == "unknown":
                query = query.filter(
                    or_(
                        FeedbackItem.sentiment == "unknown",
                        and_(
                            FeedbackItem.sentiment.is_(None),
                            FeedbackItem.rating_or_score.is_(None)
                        )
                    )
                )

        if user_segment is not None and user_segment.strip():
            segment_lower = user_segment.strip().lower()
            query = query.filter(func.lower(FeedbackItem.user_segment).like(f"%{segment_lower}%"))

        if start_date is not None:
            query = query.filter(FeedbackItem.created_at >= start_date)
        if end_date is not None:
            query = query.filter(FeedbackItem.created_at <= end_date)

        if q is not None and q.strip():
            q_lower = q.strip().lower()
            query = query.filter(
                func.lower(FeedbackItem.text).like(f"%{q_lower}%")
                | func.coalesce(func.lower(FeedbackItem.title), "").like(f"%{q_lower}%")
            )

        items = query.limit(limit).all()

        run.total_items = len(items)
        db.commit()

        processed = 0
        skipped = 0
        failed = 0
        fallbacks = 0

        for item in items:
            text = (item.text or "").strip()
            # Skip items with text under 10 characters
            if len(text) < 10:
                item.analyzed_at = datetime.now(timezone.utc)
                item.analysis_provider = "skipped"
                item.analysis_error = "Text too short (< 10 chars)"
                skipped += 1
                run.skipped_items = skipped
                run.processed_items = processed + skipped + failed
                db.commit()
                continue

            metadata = {
                "source_type": item.source_type,
                "platform": item.platform,
                "rating_or_score": item.rating_or_score,
            }

            try:
                parsed_data, provider, model, was_fallback = llm.analyze_feedback(text, metadata)

                # Store labels & evidence directly on feedback_item
                prim_theme = parsed_data.get("primary_theme") or parsed_data.get("issue_category") or "Unidentified"
                item.primary_theme = prim_theme
                item.issue_category = prim_theme  # Dual-write for backward compatibility
                item.secondary_tags = json.dumps(parsed_data.get("secondary_tags", []))
                item.taxonomy_version = "2.0.0"
                item.classification_source = provider
                item.classification_confidence = parsed_data.get("confidence")

                item.sentiment = parsed_data.get("sentiment")
                item.has_mixed_sentiment = parsed_data.get("has_mixed_sentiment")
                sentiment_prof = parsed_data.get("sentiment_profile")
                if sentiment_prof:
                    item.sentiment_profile = json.dumps(sentiment_prof)
                item.topics = json.dumps(parsed_data.get("topics", []))
                item.user_segment = parsed_data.get("user_segment")
                item.listening_intent = parsed_data.get("listening_intent")
                item.loop_cause = parsed_data.get("loop_cause")
                item.unmet_needs = json.dumps(parsed_data.get("unmet_needs", []))
                item.listening_job = parsed_data.get("listening_job")
                item.desired_outcome = parsed_data.get("desired_outcome")
                item.blocked_goal = parsed_data.get("blocked_goal")
                item.root_cause = parsed_data.get("root_cause")
                item.user_segment_signals = json.dumps(parsed_data.get("user_segment_signals", []))
                item.recommendation_pain_type = parsed_data.get("recommendation_pain_type")
                item.evidence_quote = parsed_data.get("evidence_quote")
                item.analysis_confidence = parsed_data.get("confidence")
                item.analysis_version = "2.0.0"
                item.analyzed_at = datetime.now(timezone.utc)
                item.analysis_evidence = json.dumps(parsed_data.get("evidence", []))
                item.analysis_provider = provider
                item.analysis_error = None

                processed += 1
                if was_fallback:
                    fallbacks += 1

            except Exception as exc:
                logger.error(f"Failed to analyze feedback item {item.id}: {exc}")
                item.analyzed_at = datetime.now(timezone.utc)
                item.analysis_provider = "error"
                item.analysis_error = str(exc)
                failed += 1

            # Update run metrics
            run.processed_items = processed + skipped + failed
            run.failed_items = failed
            run.fallback_count = fallbacks
            db.commit()

        run.status = "completed"
        run.finished_at = datetime.now(timezone.utc)
        db.commit()

    except Exception as exc:
        logger.exception(f"Background analysis task {run_id} failed: {exc}")
        try:
            run.status = "failed"
            run.finished_at = datetime.now(timezone.utc)
            run.error_message = str(exc)
            db.commit()
        except Exception:
            pass
    finally:
        if close_db:
            db.close()


def trigger_analysis_run(
    db: Session,
    limit: int,
    background_tasks = None,
    platform: str | None = None,
    source_type: str | None = None,
    sentiment: str | None = None,
    q: str | None = None,
    user_segment: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> str:
    """
    Finds unanalyzed items matching filters, sets their status to pending,
    records a new AnalysisRun, and wakes the background worker.
    """
    settings = get_settings()
    llm = LLMService(settings)

    # 1. Query unanalyzed items matching the active filters
    query = db.query(FeedbackItem).filter(FeedbackItem.analysis_status != "complete")

    if platform is not None:
        query = query.filter(FeedbackItem.platform == platform)
    if source_type is not None:
        query = query.filter(FeedbackItem.source_type == source_type)
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
        elif sentiment == "unknown":
            query = query.filter(
                or_(
                    FeedbackItem.sentiment == "unknown",
                    and_(
                        FeedbackItem.sentiment.is_(None),
                        FeedbackItem.rating_or_score.is_(None)
                    )
                )
            )

    if user_segment is not None and user_segment.strip():
        segment_lower = user_segment.strip().lower()
        query = query.filter(func.lower(FeedbackItem.user_segment).like(f"%{segment_lower}%"))

    if start_date is not None:
        query = query.filter(FeedbackItem.created_at >= start_date)
    if end_date is not None:
        query = query.filter(FeedbackItem.created_at <= end_date)

    if q is not None and q.strip():
        q_lower = q.strip().lower()
        query = query.filter(
            func.lower(FeedbackItem.text).like(f"%{q_lower}%")
            | func.coalesce(func.lower(FeedbackItem.title), "").like(f"%{q_lower}%")
        )

    # Limit the number of items we enqueue in this run
    items_to_enqueue = query.limit(limit).all()
    total_items = len(items_to_enqueue)

    run_id = str(uuid.uuid4())
    run = AnalysisRun(
        id=run_id,
        status="running" if total_items > 0 else "completed",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc) if total_items == 0 else None,
        total_items=total_items,
        processed_items=0,
        skipped_items=0,
        failed_items=0,
        fallback_count=0,
        provider_primary=llm.primary_provider,
        provider_fallback=llm.fallback_provider,
        model_primary=llm.primary_model,
        model_fallback=llm.fallback_model,
    )
    db.add(run)

    if total_items > 0:
        # Mark all selected items as pending and reset retries so the worker picks them up
        item_ids = [item.id for item in items_to_enqueue]
        db.query(FeedbackItem).filter(FeedbackItem.id.in_(item_ids)).update(
            {"analysis_status": "pending", "retry_count": 0}, synchronize_session=False
        )
    
    db.commit()

    if total_items > 0:
        # Wake the worker thread to start processing immediately
        from app.worker import worker
        worker.wake()

    return run_id

