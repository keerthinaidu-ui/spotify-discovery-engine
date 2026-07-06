from datetime import datetime
from pydantic import BaseModel


class IngestionRunResponse(BaseModel):
    id: str
    source: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    rows_read: int
    rows_inserted: int
    rows_skipped: int
    error_message: str | None

    model_config = {"from_attributes": True}


class SourceStatus(BaseModel):
    total_records: int
    last_run: IngestionRunResponse | None


class IngestionStatusResponse(BaseModel):
    csv_reviews: SourceStatus
    product_hunt: SourceStatus
    youtube: SourceStatus


class IngestReviewsResponse(BaseModel):
    run: IngestionRunResponse


# CSV Reviews Previews
class RawReviewResponse(BaseModel):
    id: str
    review_id: str
    text: str
    rating: float | None
    title: str | None
    author: str | None
    platform: str | None
    review_date: datetime | None
    app_version: str | None
    country: str | None
    url: str | None
    raw_payload: str | None
    ingested_at: datetime

    model_config = {"from_attributes": True}


class RawReviewListResponse(BaseModel):
    items: list[RawReviewResponse]
    total: int


# Product Hunt Previews
class RawProductHuntPostResponse(BaseModel):
    id: str
    ph_post_id: str
    slug: str
    title: str
    text: str
    votes_count: int
    author: str | None
    url: str | None
    posted_at: datetime
    raw_payload: str
    ingested_at: datetime

    model_config = {"from_attributes": True}


class RawProductHuntListResponse(BaseModel):
    items: list[RawProductHuntPostResponse]
    total: int


# YouTube Previews
class RawYouTubeVideoResponse(BaseModel):
    id: str
    video_id: str
    search_query: str
    title: str
    description: str
    view_count: int | None
    like_count: int | None
    comment_count: int | None
    author: str
    channel_id: str
    url: str
    posted_at: datetime
    raw_payload: str
    ingested_at: datetime

    model_config = {"from_attributes": True}


class RawYouTubeListResponse(BaseModel):
    items: list[RawYouTubeVideoResponse]
    total: int
