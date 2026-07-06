from datetime import datetime
import json
from pydantic import BaseModel, model_validator
from typing import Literal, Any


class FeedbackItemResponse(BaseModel):
    id: str
    source_type: str
    platform: str
    text: str
    title: str | None = None
    rating_or_score: float | None = None
    author: str | None = None
    created_at: datetime | None = None
    app_version: str | None = None
    url: str | None = None
    raw_table: str | None = None
    raw_id: str | None = None
    sentiment: Literal["positive", "neutral", "negative", "unclear", "unknown", "User Satisfaction", "User Frustration", "Neutral"] | None = None
    normalized_at: datetime

    # New Taxonomy fields
    primary_theme: str | None = None
    issue_category: str | None = None
    secondary_tags: Any = None
    taxonomy_version: str | None = None
    classification_source: str | None = None
    classification_confidence: float | None = None
    has_mixed_sentiment: bool | None = None
    sentiment_profile: Any = None

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def resolve_sentiment(self) -> "FeedbackItemResponse":
        if self.sentiment is not None:
            s_lower = str(self.sentiment).lower().strip()
            if s_lower in ("positive", "user satisfaction"):
                self.sentiment = "positive"
            elif s_lower in ("negative", "user frustration"):
                self.sentiment = "negative"
            elif s_lower in ("neutral",):
                self.sentiment = "neutral"
            elif s_lower in ("unclear", "unknown"):
                self.sentiment = "unclear"
            else:
                self.sentiment = "unclear"
        else:
            if self.rating_or_score is not None:
                if self.rating_or_score >= 4.0:
                    self.sentiment = "positive"
                elif self.rating_or_score <= 2.0:
                    self.sentiment = "negative"
                elif self.rating_or_score == 3.0:
                    self.sentiment = "neutral"
                else:
                    self.sentiment = "unclear"
            else:
                self.sentiment = "unclear"

        # Deserialize secondary_tags if it's a string
        if isinstance(self.secondary_tags, str):
            try:
                self.secondary_tags = json.loads(self.secondary_tags)
            except Exception:
                self.secondary_tags = []
        elif self.secondary_tags is None:
            self.secondary_tags = []

        # Deserialize sentiment_profile if it's a string
        if isinstance(self.sentiment_profile, str):
            try:
                self.sentiment_profile = json.loads(self.sentiment_profile)
            except Exception:
                self.sentiment_profile = {"positive_aspects": [], "negative_aspects": []}
        elif self.sentiment_profile is None:
            self.sentiment_profile = {"positive_aspects": [], "negative_aspects": []}

        return self


class FeedbackItemListResponse(BaseModel):
    items: list[FeedbackItemResponse]
    total: int


class DateBucket(BaseModel):
    date: str
    count: int


class FeedbackStatsOverviewResponse(BaseModel):
    total_records: int
    platform_counts: dict[str, int]
    source_type_counts: dict[str, int]
    date_buckets: list[DateBucket]


class SourceCompareMetric(BaseModel):
    count: int
    avg_rating: float | None = None


class FeedbackStatsCompareResponse(BaseModel):
    sources: dict[str, SourceCompareMetric]


class NormalizationResponse(BaseModel):
    status: str
    processed: int
    inserted: int
    skipped: int
    dropped: int
    failed: int
