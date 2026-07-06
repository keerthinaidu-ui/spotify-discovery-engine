import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, JSONTextCompat


class FeedbackItem(Base):
    __tablename__ = "feedback_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    rating_or_score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    author: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    app_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    raw_table: Mapped[str | None] = mapped_column(String(32), nullable=True)
    raw_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    sentiment: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    issue_category: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    topics: Mapped[str | None] = mapped_column(JSONTextCompat, nullable=True)  # JSON array
    user_segment: Mapped[str | None] = mapped_column(String(128), nullable=True)
    listening_intent: Mapped[str | None] = mapped_column(String(128), nullable=True)
    loop_cause: Mapped[str | None] = mapped_column(String(128), nullable=True)
    unmet_needs: Mapped[str | None] = mapped_column(JSONTextCompat, nullable=True)  # JSON array
    analysis_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    analysis_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    analysis_evidence: Mapped[str | None] = mapped_column(JSONTextCompat, nullable=True)  # JSON array of quote dicts
    analysis_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    analysis_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Voice of Customer Enrichment Fields
    listening_job: Mapped[str | None] = mapped_column(String(256), nullable=True)
    desired_outcome: Mapped[str | None] = mapped_column(String(256), nullable=True)
    blocked_goal: Mapped[str | None] = mapped_column(String(256), nullable=True)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_segment_signals: Mapped[str | None] = mapped_column(JSONTextCompat, nullable=True)  # JSON array
    recommendation_pain_type: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    evidence_quote: Mapped[str | None] = mapped_column(Text, nullable=True)

    # New Taxonomy Fields
    primary_theme: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    secondary_tags: Mapped[str | None] = mapped_column(JSONTextCompat, nullable=True)  # JSON array
    taxonomy_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    classification_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    classification_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Mixed Sentiment Enrichment Fields
    has_mixed_sentiment: Mapped[bool | None] = mapped_column(Boolean, nullable=True, index=True)
    sentiment_profile: Mapped[str | None] = mapped_column(JSONTextCompat, nullable=True)

    # New Durable Analysis fields
    analysis_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default="pending", index=True
    )
    analysis_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    normalized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __init__(self, **kwargs):
        if "analyzed_at" in kwargs and kwargs["analyzed_at"] is not None and "analysis_status" not in kwargs:
            kwargs["analysis_status"] = "complete"
        super().__init__(**kwargs)


