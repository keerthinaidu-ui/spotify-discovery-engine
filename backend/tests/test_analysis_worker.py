import json
import time
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy.orm import Session

from app.models.feedback_item import FeedbackItem
from app.models.analysis_run import AnalysisRun
from app.services.llm_service import LLMService, RateLimitException
from app.worker import AnalysisWorker

MOCK_LLM_RESPONSE = {
    "issue_category": "Stability",
    "topics": ["crash"],
    "user_segment": "premium_subscriber",
    "listening_intent": "commute",
    "loop_cause": "app crash",
    "unmet_needs": ["stability"],
    "confidence": 0.95,
    "evidence": [{"quote": "crashes constantly", "topic": "crash"}]
}

@pytest.fixture
def test_worker():
    worker = AnalysisWorker()
    # Override settings for tests
    worker.settings.worker_enabled = True
    worker.settings.worker_throttle_delay = 0.01
    worker.settings.worker_batch_size = 5
    yield worker
    worker.stop()

@patch.object(LLMService, "analyze_feedback")
def test_worker_processing_flow(mock_analyze, db, test_worker):
    # Mock LLM success
    mock_analyze.return_value = (MOCK_LLM_RESPONSE, "gemini", "gemini-1.5-flash", False)

    # Insert pending feedback item
    item = FeedbackItem(
        id="worker-test-1",
        source_type="app_review",
        platform="play_store",
        text="App crashes constantly since the last update",
        rating_or_score=1.0,
        analysis_status="pending",
        retry_count=0
    )
    db.add(item)
    db.commit()

    # Start worker and wait for it to process
    test_worker.start()
    
    # Wait up to 2 seconds for status to change to complete
    for _ in range(20):
        time.sleep(0.1)
        db.rollback()
        item = db.query(FeedbackItem).filter(FeedbackItem.id == "worker-test-1").first()
        if item and item.analysis_status == "complete":
            break

    assert item is not None
    assert item.analysis_status == "complete"
    assert item.issue_category == "Stability"
    assert item.analysis_provider == "gemini"
    assert item.analysis_model == "gemini-1.5-flash"
    assert "crash" in json.loads(item.topics)
    assert item.retry_count == 0

@patch.object(LLMService, "analyze_feedback")
def test_worker_handles_rate_limit_exception(mock_analyze, db, test_worker):
    # Mock RateLimitException
    mock_analyze.side_effect = RateLimitException("Groq rate limit", retry_after=5.0, provider="groq")

    # Insert pending feedback item
    item = FeedbackItem(
        id="worker-test-429",
        source_type="app_review",
        platform="play_store",
        text="App is good but sometimes laggy",
        rating_or_score=4.0,
        analysis_status="pending",
        retry_count=0
    )
    db.add(item)
    db.commit()

    test_worker.start()

    # Wait for status to change to failed
    for i in range(40):
        time.sleep(0.1)
        db.rollback()
        item = db.query(FeedbackItem).filter(FeedbackItem.id == "worker-test-429").first()
        status = item.analysis_status if item else "None"
        print(f"Polled iteration {i}: status={status}, retry_count={item.retry_count if item else 0}")
        if item and item.analysis_status == "failed":
            break




    assert item.analysis_status == "failed"
    assert item.retry_count == 1
    assert "RateLimitException" in item.failure_reason

def test_worker_recovery_logic(db, test_worker):
    # Create stuck processing item and stuck run
    item = FeedbackItem(
        id="stuck-item",
        source_type="app_review",
        platform="play_store",
        text="Stuck processing review",
        rating_or_score=3.0,
        analysis_status="processing"
    )
    
    run = AnalysisRun(
        id="stuck-run",
        status="running",
        started_at=datetime.now(timezone.utc),
        total_items=10,
        provider_primary="gemini",
        provider_fallback="groq",
        model_primary="gemini-1.5-flash",
        model_fallback="llama-3.3-70b-versatile"
    )
    
    db.add_all([item, run])
    db.commit()

    # Call recover_jobs
    test_worker._recover_jobs(db)

    # Check recovery
    db.refresh(item)
    db.refresh(run)

    assert item.analysis_status == "pending"
    assert run.status == "failed"
    assert "Interrupted" in run.error_message
