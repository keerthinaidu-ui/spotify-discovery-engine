import json
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import pytest
from app.config import get_settings
from app.models.feedback_item import FeedbackItem
from app.models.feedback_embedding import FeedbackEmbedding
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import QuotaExhaustedException

@pytest.fixture
def mock_embedding_response():
    return {
        "embedding": {
            "values": [0.1, 0.2, 0.3, 0.4, 0.5]
        }
    }

def test_embedding_chunk_text():
    settings = get_settings()
    service = EmbeddingService(settings)
    
    text = "one two three four five six seven eight nine ten"
    chunks = service.chunk_text(text, max_words=4)
    assert len(chunks) == 3
    assert chunks[0] == "one two three four"
    assert chunks[1] == "five six seven eight"
    assert chunks[2] == "nine ten"

@patch("httpx.post")
def test_embedding_get_embedding(mock_post, mock_embedding_response):
    settings = get_settings()
    settings.gemini_api_key = "test_key"
    service = EmbeddingService(settings)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_embedding_response
    mock_post.return_value = mock_resp

    vector = service.get_embedding("hello", task_type="RETRIEVAL_QUERY")
    assert vector == [0.1, 0.2, 0.3, 0.4, 0.5]
    
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert "models/gemini-embedding-2" in kwargs["json"]["model"]
    assert kwargs["json"]["taskType"] == "RETRIEVAL_QUERY"

@patch.object(EmbeddingService, "get_embedding")
def test_embedding_index_reviews(mock_get_embedding, db):
    settings = get_settings()
    settings.embedding_enabled = True
    service = EmbeddingService(settings)
    mock_get_embedding.return_value = [0.1, 0.2, 0.3, 0.4, 0.5]

    item1 = FeedbackItem(
        id="item-idx-1",
        source_type="app_review",
        platform="app_store",
        text="This is a nice review that needs semantic indexing.",
        rating_or_score=5.0
    )
    db.add(item1)
    db.commit()

    res = service.index_reviews_with_embeddings(db)
    assert res["status"] == "success"
    assert res["indexed_count"] == 1

    emb_rec = db.query(FeedbackEmbedding).filter(FeedbackEmbedding.feedback_id == "item-idx-1").first()
    assert emb_rec is not None
    assert emb_rec.chunk_text == "This is a nice review that needs semantic indexing."
    assert json.loads(emb_rec.embedding) == [0.1, 0.2, 0.3, 0.4, 0.5]

    res_second = service.index_reviews_with_embeddings(db)
    assert res_second["indexed_count"] == 0

@patch.object(EmbeddingService, "get_embedding")
def test_embedding_retrieval(mock_get_embedding, db):
    settings = get_settings()
    settings.embedding_enabled = True
    service = EmbeddingService(settings)
    
    mock_get_embedding.return_value = [1.0, 0.0]

    item1 = FeedbackItem(
        id="item-ret-1",
        source_type="app_review",
        platform="app_store",
        text="App crashes constantly after loading list",
        sentiment="negative"
    )
    item2 = FeedbackItem(
        id="item-ret-2",
        source_type="app_review",
        platform="play_store",
        text="I love using the Spotify search tool",
        sentiment="positive"
    )
    db.add_all([item1, item2])
    db.commit()

    emb1 = FeedbackEmbedding(feedback_id="item-ret-1", chunk_text=item1.text, embedding=json.dumps([1.0, 0.0]))
    emb2 = FeedbackEmbedding(feedback_id="item-ret-2", chunk_text=item2.text, embedding=json.dumps([0.0, 1.0]))
    db.add_all([emb1, emb2])
    db.commit()

    results = service.retrieve_relevant_reviews(db, "crashes")
    assert len(results) == 2
    assert results[0][0].id == "item-ret-1"
    assert results[0][2] == pytest.approx(1.0)

    filtered = service.retrieve_relevant_reviews(db, "crashes", active_filters={"platform": "play_store"})
    assert len(filtered) == 1
    assert filtered[0][0].id == "item-ret-2"

@patch.object(EmbeddingService, "get_embedding")
def test_chat_route_semantic_retrieval(mock_get_embedding, db, client):
    settings = get_settings()
    settings.embedding_enabled = True
    settings.gemini_api_key = "valid_key"
    
    mock_get_embedding.return_value = [1.0, 0.0]

    item1 = FeedbackItem(
        id="item-chat-1",
        source_type="app_review",
        platform="app_store",
        text="Spotify crashes immediately when launching tracks.",
        rating_or_score=1.0,
        analyzed_at=datetime.now(timezone.utc)
    )
    db.add(item1)
    db.commit()

    emb1 = FeedbackEmbedding(feedback_id="item-chat-1", chunk_text=item1.text, embedding=json.dumps([1.0, 0.0]))
    db.add(emb1)
    db.commit()

    with patch("app.services.llm_service.LLMService._call_provider") as mock_llm_call:
        mock_llm_call.return_value = json.dumps({
            "answer": "The user complains that Spotify is crashing immediately on launch.",
            "evidence_snippets": ["Spotify crashes immediately when launching tracks."]
        })

        payload = {
            "query": "crashes startup",
            "platform": "app_store"
        }
        resp = client.post("/insights/chat", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "crashing immediately" in data["answer"]
        assert len(data["evidence_snippets"]) == 1
        assert data["evidence_snippets"][0] == "Spotify crashes immediately when launching tracks."
