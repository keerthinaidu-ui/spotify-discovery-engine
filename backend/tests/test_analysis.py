import json
from datetime import datetime, timezone
from unittest.mock import patch

from app.config import get_settings
from app.models.analysis_run import AnalysisRun
from app.models.feedback_item import FeedbackItem
from app.services.analysis_service import run_batch_analysis_job
from app.services.llm_service import (
    LLMService,
    InvalidAPIKeyException,
    QuotaExhaustedException,
    ModelNotFoundException,
)

# Mock LLM responses
MOCK_SUCCESS_JSON = {
    "issue_category": "crashes_and_bugs",
    "topics": ["app_launch_crash", "stability"],
    "user_segment": "premium_subscriber",
    "listening_intent": "commute",
    "loop_cause": "app freezes immediately on launch",
    "unmet_needs": ["offline_playback_stability"],
    "confidence": 0.95,
    "evidence": [{"quote": "Crashing on startup since yesterday", "topic": "app_launch_crash"}],
}


def test_llm_service_clean_and_parse_json():
    # Test JSON cleaning functionality in LLMService
    settings = get_settings()
    llm = LLMService(settings)

    raw_response = "```json\n" + json.dumps(MOCK_SUCCESS_JSON) + "\n```"
    parsed = llm._clean_and_parse_json(raw_response)
    assert parsed["issue_category"] == "crashes_and_bugs"

    raw_response_curly = 'some text before {"confidence": 0.95} some text after'
    parsed_curly = llm._clean_and_parse_json(raw_response_curly)
    assert parsed_curly["confidence"] == 0.95


@patch.object(LLMService, "_call_provider")
def test_llm_service_success(mock_call):
    # Mock successful Gemini call
    settings = get_settings()
    mock_call.return_value = json.dumps(MOCK_SUCCESS_JSON)

    llm = LLMService(settings)
    parsed, provider, model, was_fallback = llm.analyze_feedback(
        "I love this application!", {"source_type": "app_review"}
    )

    assert provider == "gemini"
    assert model == "gemini-2.5-flash"
    assert not was_fallback
    assert parsed["issue_category"] == "crashes_and_bugs"


@patch.object(LLMService, "_call_provider")
def test_llm_service_fallback(mock_call):
    # Simulate all 5 Gemini models failing, then Groq succeeding
    settings = get_settings()
    mock_call.side_effect = [
        Exception("Rate limit exceeded"),  # gemini-2.5-flash
        Exception("Rate limit exceeded"),  # gemini-3.1-flash-lite
        Exception("Rate limit exceeded"),  # gemini-3.5-flash
        Exception("Rate limit exceeded"),  # gemini-2.5-flash-lite
        Exception("Rate limit exceeded"),  # gemini-3-flash
        json.dumps(MOCK_SUCCESS_JSON),     # groq
    ]

    llm = LLMService(settings)
    parsed, provider, model, was_fallback = llm.analyze_feedback(
        "Crashing on startup since yesterday", {"source_type": "app_review"}
    )

    assert provider == "groq"
    assert model == "llama-3.3-70b-versatile"
    assert was_fallback
    assert parsed["issue_category"] == "crashes_and_bugs"


@patch.object(LLMService, "_call_provider")
def test_gemini_ladder_fallback_to_second_model(mock_call):
    settings = get_settings()
    # First model fails, second model succeeds
    mock_call.side_effect = [
        QuotaExhaustedException("429 Rate limit"),
        json.dumps(MOCK_SUCCESS_JSON),
    ]

    llm = LLMService(settings)
    parsed, provider, model, was_fallback = llm.analyze_feedback(
        "Hello", {"source_type": "app_review"}
    )

    assert provider == "gemini"
    assert model == "gemini-3.1-flash-lite"
    assert was_fallback
    assert parsed["issue_category"] == "crashes_and_bugs"


@patch.object(LLMService, "_call_provider")
def test_gemini_ladder_multiple_failures(mock_call):
    settings = get_settings()
    # First three models fail, fourth model succeeds
    mock_call.side_effect = [
        QuotaExhaustedException("429"),
        ModelNotFoundException("404"),
        Exception("Timeout"),
        json.dumps(MOCK_SUCCESS_JSON),
    ]

    llm = LLMService(settings)
    parsed, provider, model, was_fallback = llm.analyze_feedback(
        "Hello", {"source_type": "app_review"}
    )

    assert provider == "gemini"
    assert model == "gemini-2.5-flash-lite"
    assert was_fallback
    assert parsed["issue_category"] == "crashes_and_bugs"


@patch.object(LLMService, "_call_provider")
def test_gemini_ladder_non_fallback_error(mock_call):
    import pytest
    settings = get_settings()
    # InvalidAPIKeyException should abort the ladder immediately and NOT trigger fallback
    mock_call.side_effect = InvalidAPIKeyException("Invalid API key")

    llm = LLMService(settings)
    with pytest.raises(InvalidAPIKeyException):
        llm.analyze_feedback("Hello", {"source_type": "app_review"})



@patch.object(LLMService, "analyze_feedback")
def test_batch_runner_persistence(mock_analyze, db, client):
    # Clear DB first
    db.query(FeedbackItem).delete()
    db.query(AnalysisRun).delete()
    db.commit()

    # Create test items (one normal, one short to skip)
    item_normal = FeedbackItem(
        id="item-normal",
        source_type="app_review",
        platform="play_store",
        text="This is a normal review with more than 10 characters.",
        rating_or_score=4.0,
    )
    item_short = FeedbackItem(
        id="item-short",
        source_type="app_review",
        platform="play_store",
        text="short",  # Under 10 chars -> should be skipped
        rating_or_score=3.0,
    )
    db.add_all([item_normal, item_short])
    db.commit()

    # Mock analyze_feedback return value
    mock_analyze.return_value = (MOCK_SUCCESS_JSON, "gemini", "gemini-1.5-flash", False)

    # Trigger analysis run via API
    response = client.post("/analysis/run?limit=10")
    assert response.status_code == 200
    run_id = response.json()["run_id"]
    assert response.json()["status"] == "running"

    # Wait for background tasks by executing the job function directly for test purposes
    run_batch_analysis_job(run_id, limit=10, db_session=db)

    # Verify run record in DB
    run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
    assert run.status == "completed"
    assert run.total_items == 2
    assert run.processed_items == 2
    assert run.skipped_items == 1
    assert run.failed_items == 0

    # Verify FeedbackItem updates
    item_normal_db = db.query(FeedbackItem).filter(FeedbackItem.id == "item-normal").first()
    assert item_normal_db.analyzed_at is not None
    assert item_normal_db.issue_category == "crashes_and_bugs"
    assert item_normal_db.analysis_provider == "gemini"
    assert "app_launch_crash" in json.loads(item_normal_db.topics)
    assert item_normal_db.analysis_error is None

    item_short_db = db.query(FeedbackItem).filter(FeedbackItem.id == "item-short").first()
    assert item_short_db.analyzed_at is not None
    assert item_short_db.analysis_provider == "skipped"
    assert "too short" in item_short_db.analysis_error.lower()


def test_insights_endpoints(db, client):
    # Setup analyzed items in DB
    db.query(FeedbackItem).delete()
    db.commit()

    item1 = FeedbackItem(
        id="item-ins-1",
        source_type="app_review",
        platform="play_store",
        text="App is crashing a lot after update",
        analyzed_at=datetime.now(timezone.utc),
        issue_category="crashes_and_bugs",
        topics=json.dumps(["crash", "update"]),
        user_segment="premium_subscriber",
        unmet_needs=json.dumps(["stability"]),
        analysis_confidence=0.9,
        analysis_evidence=json.dumps([{"quote": "crashing a lot", "topic": "crash"}]),
    )
    item2 = FeedbackItem(
        id="item-ins-2",
        source_type="youtube_comment",
        platform="youtube",
        text="Layout is confusing",
        analyzed_at=datetime.now(timezone.utc),
        issue_category="ui_ux_design",
        topics=json.dumps(["ui", "layout"]),
        user_segment="free_tier",
        unmet_needs=json.dumps(["simplicity"]),
        analysis_confidence=0.8,
        analysis_evidence=json.dumps([{"quote": "confusing", "topic": "ui"}]),
    )
    db.add_all([item1, item2])
    db.commit()

    # Test /insights/summary
    response = client.get("/insights/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["total_analyzed"] == 2
    assert len(data["top_categories"]) == 2
    assert data["top_categories"][0]["name"] in ("crashes_and_bugs", "ui_ux_design")
    assert data["top_categories"][0]["count"] == 1

    # Test /insights/compare
    response = client.get("/insights/compare?compare_by=source_type")
    assert response.status_code == 200
    data = response.json()
    assert data["compare_by"] == "source_type"
    assert "app_review" in data["comparison"]
    assert "youtube_comment" in data["comparison"]
    assert data["comparison"]["app_review"]["crashes_and_bugs"] == 1

    # Test /insights/{theme}/evidence
    response = client.get("/insights/crash/evidence")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["feedback_id"] == "item-ins-1"
    assert data[0]["quote"] == "crashing a lot"


@patch.object(LLMService, "_call_provider")
def test_mixed_sentiment_analysis_normalization(mock_call):
    # Test that llm_service properly extracts has_mixed_sentiment and normalizes sentiment_profile aspects
    settings = get_settings()
    
    mock_llm_json = {
        "issue_category": "Recommendations",
        "sentiment": "positive",
        "has_mixed_sentiment": True,
        "sentiment_profile": {
            "positive_aspects": ["music_discovery", "completely unrelated text"],
            "negative_aspects": ["recommendation_accuracy", "app performance issues"]
        },
        "topics": ["discovery", "bugs"],
        "confidence": 0.95,
        "evidence": [{"quote": "Discovery weekly is great but sometimes recommendation is wrong", "topic": "discovery"}]
    }
    mock_call.return_value = json.dumps(mock_llm_json)

    llm = LLMService(settings)
    parsed, provider, model, was_fallback = llm.analyze_feedback(
        "Discovery weekly is great but sometimes recommendation is wrong", {"source_type": "app_review"}
    )

    assert parsed["has_mixed_sentiment"] is True
    # Verify strict aspects normalization mapping
    pos_asps = parsed["sentiment_profile"]["positive_aspects"]
    neg_asps = parsed["sentiment_profile"]["negative_aspects"]
    assert "music_discovery" in pos_asps
    assert "other" in pos_asps
    assert "recommendation_accuracy" in neg_asps
    assert "app_performance" in neg_asps
