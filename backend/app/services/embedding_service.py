import json
import logging
import math
from datetime import datetime
from typing import Any, List, Dict, Tuple
import httpx
from sqlalchemy.orm import Session
from app.config import Settings
from app.models.feedback_item import FeedbackItem
from app.models.feedback_embedding import FeedbackEmbedding
from app.services.llm_service import InvalidAPIKeyException, QuotaExhaustedException, LLMException

logger = logging.getLogger(__name__)

class EmbeddingService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.model = settings.gemini_embedding_model
        self.enabled = settings.embedding_enabled
        self.top_k = settings.embedding_top_k
        self.min_score = settings.embedding_min_score

    def get_embedding(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> List[float]:
        """
        Gets embedding vector for a given text using Gemini Embedding API.
        """
        if not self.settings.gemini_api_key:
            raise InvalidAPIKeyException("GEMINI_API_KEY is not configured for embeddings")
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:embedContent?key={self.settings.gemini_api_key}"
        
        # Prepare payload
        model_payload_name = f"models/{self.model}" if not self.model.startswith("models/") else self.model
        payload = {
            "model": model_payload_name,
            "content": {
                "parts": [{"text": text}]
            },
            "taskType": task_type
        }
        if self.settings.embedding_output_dimensionality:
            payload["outputDimensionality"] = self.settings.embedding_output_dimensionality

        headers = {"Content-Type": "application/json"}
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=10.0)
            if resp.status_code == 400:
                err_body = resp.text
                if "API key not valid" in err_body or "API_KEY_INVALID" in err_body:
                    raise InvalidAPIKeyException("Gemini API key is invalid for embeddings")
                raise LLMException(f"Gemini embedding malformed request: {err_body}")
            elif resp.status_code == 404:
                raise LLMException(f"Gemini embedding model not found: {resp.text}")
            elif resp.status_code == 429:
                raise QuotaExhaustedException("Gemini embedding quota exhausted / rate limit exceeded")
            
            resp.raise_for_status()
            data = resp.json()
            return data["embedding"]["values"]
        except httpx.HTTPStatusError as e:
            raise LLMException(f"Gemini embedding API error: {e}")
        except Exception as e:
            raise LLMException(f"Gemini embedding unexpected error: {e}")

    def chunk_text(self, text: str, max_words: int = 250) -> List[str]:
        """
        Splits text into chunks of maximum words.
        """
        words = text.split()
        if len(words) <= max_words:
            return [text]
        
        chunks = []
        for i in range(0, len(words), max_words):
            chunk = " ".join(words[i:i + max_words])
            chunks.append(chunk)
        return chunks

    def index_reviews_with_embeddings(self, db: Session) -> Dict[str, Any]:
        """
        Scans database for unindexed reviews, chunks them, generates embeddings, and saves them.
        """
        if not self.enabled:
            logger.info("Embeddings are disabled. Skipping index build.")
            return {"indexed_count": 0, "status": "disabled"}

        # Find items that have no embeddings using LEFT OUTER JOIN (extremely fast and database-native)
        unindexed_items = (
            db.query(FeedbackItem)
            .outerjoin(FeedbackEmbedding, FeedbackItem.id == FeedbackEmbedding.feedback_id)
            .filter(FeedbackEmbedding.feedback_id.is_(None))
            .limit(50)
            .all()
        )
        
        logger.info(f"Found {len(unindexed_items)} feedback items requiring embedding indexing.")
        
        indexed_count = 0
        should_stop = False
        for item in unindexed_items:
            if should_stop:
                break
            chunks = self.chunk_text(item.text)
            for idx, chunk in enumerate(chunks):
                try:
                    vector = self.get_embedding(chunk, task_type="RETRIEVAL_DOCUMENT")
                    emb_obj = FeedbackEmbedding(
                        feedback_id=item.id,
                        chunk_index=idx,
                        chunk_text=chunk,
                        embedding=json.dumps(vector)
                    )
                    db.add(emb_obj)
                    indexed_count += 1
                except Exception as e:
                    logger.error(f"Failed to index feedback item {item.id} chunk {idx}: {e}")
                    db.rollback()
                    should_stop = True
                    break
            else:
                db.commit()

        status = "partial_error" if should_stop else "success"
        logger.info(f"Index run completed: indexed {indexed_count} vector chunks. Status: {status}")
        return {"indexed_count": indexed_count, "status": status}

    def cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        """
        Computes cosine similarity between two vectors.
        """
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0
        dot_product = sum(a * b for a, b in zip(v1, v2))
        norm_a = math.sqrt(sum(a * a for a in v1))
        norm_b = math.sqrt(sum(b * b for b in v2))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot_product / (norm_a * norm_b)

    def retrieve_relevant_reviews(self, db: Session, query: str, active_filters: Dict[str, Any] = None) -> List[Tuple[FeedbackItem, str, float]]:
        """
        Retrieves top_k most relevant feedback chunks/items for a query using embeddings.
        Applies active metadata filtering (platform, sentiment, date, etc.) to match search criteria.
        """
        if not self.enabled:
            logger.info("Embeddings are disabled. Skipping semantic retrieval.")
            return []

        try:
            query_vector = self.get_embedding(query, task_type="RETRIEVAL_QUERY")
        except Exception as e:
            logger.warning(f"Failed to generate query embedding: {e}. Falling back to lexical search.")
            return []

        # Query all candidates matching filters
        query_items = db.query(FeedbackItem)
        if active_filters:
            platform = active_filters.get("platform")
            if platform:
                platforms = [p.strip() for p in platform.split(",") if p.strip()]
                query_items = query_items.filter(FeedbackItem.platform.in_(platforms))
            
            sentiment = active_filters.get("sentiment")
            if sentiment:
                sentiments = [s.strip() for s in sentiment.split(",") if s.strip()]
                query_items = query_items.filter(FeedbackItem.sentiment.in_(sentiments))

            start_date = active_filters.get("start_date")
            if start_date:
                try:
                    dt = datetime.fromisoformat(start_date)
                    query_items = query_items.filter(FeedbackItem.created_at >= dt)
                except ValueError:
                    pass

            end_date = active_filters.get("end_date")
            if end_date:
                try:
                    dt = datetime.fromisoformat(end_date)
                    query_items = query_items.filter(FeedbackItem.created_at <= dt)
                except ValueError:
                    pass

        candidates = query_items.all()
        candidate_ids = {c.id for c in candidates}
        if not candidate_ids:
            return []

        # Retrieve embeddings for these candidates
        embeddings = db.query(FeedbackEmbedding).filter(FeedbackEmbedding.feedback_id.in_(candidate_ids)).all()
        if not embeddings:
            logger.warning("No embeddings found for candidate reviews. Run indexing first.")
            return []

        candidate_map = {c.id: c for c in candidates}

        # Calculate similarities
        scored_chunks = []
        for emb in embeddings:
            try:
                vector = json.loads(emb.embedding)
                score = self.cosine_similarity(query_vector, vector)
                if score >= self.min_score:
                    item = candidate_map.get(emb.feedback_id)
                    if item:
                        scored_chunks.append((item, emb.chunk_text, score))
            except Exception as e:
                logger.error(f"Error parsing embedding {emb.id}: {e}")

        # Sort by score descending
        scored_chunks.sort(key=lambda x: x[2], reverse=True)

        # Apply diversity and deduplication (keep best chunk per feedback item, return top_k)
        unique_feedback_chunks = []
        seen_feedback_ids = set()
        for item, chunk_text, score in scored_chunks:
            if item.id not in seen_feedback_ids:
                seen_feedback_ids.add(item.id)
                unique_feedback_chunks.append((item, chunk_text, score))
            if len(unique_feedback_chunks) >= self.top_k:
                break

        logger.info(f"Retrieved {len(unique_feedback_chunks)} relevant review chunks using semantic search.")
        return unique_feedback_chunks
