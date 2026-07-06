from datetime import datetime
import pytest
from unittest.mock import patch
from app.models.feedback_item import FeedbackItem
from app.services.llm_service import LLMService

@pytest.fixture(autouse=True)
def mock_llm():
    with patch.object(LLMService, "_call_provider", side_effect=Exception("Mock LLM Failure")):
        yield


def test_chat_schema_correctness_and_fallback(db, client):
    # Insert mock records
    item1 = FeedbackItem(
        id="item-1",
        source_type="app_review",
        platform="app_store",
        rating_or_score=4.0,
        text="Spotify recommendation algorithm is repetitive and monotonous.",
        created_at=datetime(2026, 6, 1, 10, 0, 0),
        raw_id="raw-1",
        issue_category="recommendation_algorithm",
        sentiment="negative",
        analyzed_at=datetime.now()
    )
    db.add(item1)
    db.commit()

    # Call with a query
    payload = {
        "query": "Is the recommendation system monotone?",
        "platform": "app_store"
    }
    response = client.post("/insights/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Verify schema fields are present and correct types
    assert "answer" in data
    assert "total_count" in data
    assert "source_breakdown" in data
    assert "evidence_snippets" in data
    assert "llm_used" in data
    assert "mode" in data

    # Verify formal consistency: fallback mode because API key is invalid/mock
    assert data["total_count"] == 1
    assert data["source_breakdown"] == {"app_review": 1}
    assert len(data["evidence_snippets"]) == 1
    assert data["evidence_snippets"][0] == "Spotify recommendation algorithm is repetitive and monotonous."
    assert data["llm_used"] is False
    assert data["mode"] == "fallback"

def test_chat_filter_parity(db, client):
    # Insert multiple items
    item1 = FeedbackItem(
        id="item-1",
        source_type="app_review",
        platform="app_store",
        rating_or_score=5.0,
        text="Awesome premium audio quality and UI",
        created_at=datetime(2026, 6, 1, 10, 0, 0),
        raw_id="raw-1",
        sentiment="positive",
        analyzed_at=datetime.now()
    )
    item2 = FeedbackItem(
        id="item-2",
        source_type="youtube_comment",
        platform="youtube",
        rating_or_score=1.0,
        text="App keeps crashing on startup when I play songs",
        created_at=datetime(2026, 6, 2, 10, 0, 0),
        raw_id="raw-2",
        sentiment="negative",
        analyzed_at=datetime.now()
    )
    db.add_all([item1, item2])
    db.commit()

    # Query for positive sentiment
    response_pos = client.post("/insights/chat", json={
        "query": "Audio quality",
        "sentiment": "positive"
    })
    assert response_pos.status_code == 200
    data_pos = response_pos.json()
    assert data_pos["total_count"] == 1
    assert data_pos["evidence_snippets"][0] == "Awesome premium audio quality and UI"

    # Query for youtube platform
    response_yt = client.post("/insights/chat", json={
        "query": "crash",
        "platform": "youtube"
    })
    assert response_yt.status_code == 200
    data_yt = response_yt.json()
    assert data_yt["total_count"] == 1
    assert data_yt["evidence_snippets"][0] == "App keeps crashing on startup when I play songs"

def test_chat_zero_result_shape(db, client):
    payload = {
        "query": "Does it crash?",
        "platform": "google_play"
    }
    response = client.post("/insights/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 0
    assert data["source_breakdown"] == {}
    assert data["evidence_snippets"] == []
    assert data["llm_used"] is False
    assert data["mode"] == "fallback"
    assert "No feedback records found" in data["answer"]

def test_chat_deterministic_evidence_sorting_and_diversity(db, client):
    # Insert multiple items with different sources to verify diversity and sorting
    item1 = FeedbackItem(
        id="item-1",
        source_type="app_review",
        platform="app_store",
        rating_or_score=4.0,
        text="Text from app store older",
        created_at=datetime(2026, 6, 1, 10, 0, 0),
        raw_id="raw-1",
        analyzed_at=datetime.now()
    )
    item2 = FeedbackItem(
        id="item-2",
        source_type="app_review",
        platform="app_store",
        rating_or_score=4.0,
        text="Text from app store newer",
        created_at=datetime(2026, 6, 2, 10, 0, 0),
        raw_id="raw-2",
        analyzed_at=datetime.now()
    )
    item3 = FeedbackItem(
        id="item-3",
        source_type="youtube_comment",
        platform="youtube",
        rating_or_score=4.0,
        text="Text from youtube newer",
        created_at=datetime(2026, 6, 2, 12, 0, 0),
        raw_id="raw-3",
        analyzed_at=datetime.now()
    )
    db.add_all([item1, item2, item3])
    db.commit()

    # Query for all items
    response = client.post("/insights/chat", json={"query": "Spotify features"})
    assert response.status_code == 200
    data = response.json()

    # Verify we matched 3 items
    assert data["total_count"] == 3

    # Verification of stable sorting:
    # item3 (June 2, 12:00) is the newest.
    # item2 (June 2, 10:00) is second.
    # item1 (June 1, 10:00) is oldest.
    # Verification of diversity:
    # 3 items exist: two app_reviews (item1, item2), one youtube_comment (item3).
    # Since we want to select 3 items, all of them are selected.
    # The stable sort order of selection: item3, item2, item1.
    # Let's check that snippets are exact matches for the texts in that order.
    assert len(data["evidence_snippets"]) == 3
    assert data["evidence_snippets"][0] == "Text from youtube newer"
    assert data["evidence_snippets"][1] == "Text from app store newer"
    assert data["evidence_snippets"][2] == "Text from app store older"
