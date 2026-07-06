from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel


class AnalysisRunTriggerResponse(BaseModel):
    run_id: str
    status: str
    started_at: datetime


class AnalysisRunStatusResponse(BaseModel):
    id: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    total_items: int
    processed_items: int
    skipped_items: int
    failed_items: int
    fallback_count: int
    provider_primary: str
    provider_fallback: str
    model_primary: str
    model_fallback: str
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


class MetricCount(BaseModel):
    name: str
    count: int


class InsightsSummaryResponse(BaseModel):
    total_analyzed: int
    top_categories: List[MetricCount]
    top_topics: List[MetricCount]
    top_segments: List[MetricCount]
    top_unmet_needs: List[MetricCount]
    top_secondary_tags: Optional[List[MetricCount]] = []
    is_analyzing: Optional[bool] = False


class InsightsCompareResponse(BaseModel):
    compare_by: str
    comparison: Dict[str, Dict[str, int]]


class EvidenceItemResponse(BaseModel):
    feedback_id: str
    source_type: str
    platform: str
    text: str
    author: Optional[str] = None
    quote: str
    confidence: Optional[float] = None


class ChatRequest(BaseModel):
    query: str
    q: Optional[str] = None
    platform: Optional[str] = None
    source_type: Optional[str] = None
    sentiment: Optional[str] = None
    rating: Optional[float] = None
    rating_min: Optional[float] = None
    rating_max: Optional[float] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    issue_category: Optional[str] = None
    primary_theme: Optional[str] = None
    secondary_tag: Optional[str] = None
    topic: Optional[str] = None
    user_segment: Optional[str] = None
    has_mixed_sentiment: Optional[bool] = None


class ChatResponse(BaseModel):
    answer: str
    total_count: int
    source_breakdown: Dict[str, int]
    evidence_snippets: List[str]
    llm_used: bool
    mode: str
    percent_analyzed: float = 0.0
    is_analysis_in_progress: bool = False


class AnalysisCoverageResponse(BaseModel):
    total_ingested: int
    analyzed: int
    pending: int
    failed: int
    percent_analyzed: float
    active_job_status: str
    last_successful_run: Optional[datetime] = None
    estimated_remaining_time_seconds: Optional[float] = None


