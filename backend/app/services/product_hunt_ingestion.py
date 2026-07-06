from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
import uuid

from sqlalchemy.orm import Session
import httpx

from app.models.raw_product_hunt import RawProductHuntPost, RawProductHuntComment

logger = logging.getLogger(__name__)


class ProductHuntClient:
    def __init__(self, token: str, slug: str = "spotify"):
        self.token = token
        self.slug = slug
        self.api_url = "https://api.producthunt.com/v2/api/graphql"

    def fetch_spotify_data(self) -> dict:
        """Queries Product Hunt GraphQL API v2 for post details and comments."""
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        query = """
        query GetPost($slug: String!) {
          post(slug: $slug) {
            id
            name
            tagline
            description
            votesCount
            url
            createdAt
            user {
              name
            }
            comments(first: 100) {
              edges {
                node {
                  id
                  body
                  votesCount
                  createdAt
                  user {
                    name
                  }
                }
              }
            }
          }
        }
        """
        payload = {"query": query, "variables": {"slug": self.slug}}

        try:
            with httpx.Client() as client:
                r = client.post(self.api_url, json=payload, headers=headers, timeout=15.0)
                r.raise_for_status()
                return r.json()
        except Exception as e:
            logger.error(f"Product Hunt GraphQL query failed: {e}")
            raise RuntimeError(f"Product Hunt GraphQL connection failed: {e}") from e


def parse_iso_datetime(dt_str: str | None) -> datetime:
    if not dt_str:
        return datetime.now(timezone.utc)
    try:
        # Standard ISO format parsing, handling 'Z' suffix
        cleaned = dt_str.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except Exception:
        return datetime.now(timezone.utc)


def ingest_product_hunt(db: Session, token: str, slug: str = "spotify") -> tuple[int, int, int]:
    """Runs Product Hunt ingestion, inserts raw items, and returns (read, inserted, skipped)."""
    client = ProductHuntClient(token=token, slug=slug)
    raw_res = client.fetch_spotify_data()

    if "errors" in raw_res:
        raise ValueError(f"Product Hunt GraphQL returned errors: {raw_res['errors']}")

    post_data = raw_res.get("data", {}).get("post")
    if not post_data:
        logger.warning(f"No Product Hunt post found for slug '{slug}'")
        return 0, 0, 0

    rows_read = 0
    rows_inserted = 0
    rows_skipped = 0

    # 1. Process Post
    rows_read += 1
    ph_post_id = str(post_data.get("id"))

    # Text = description + tagline for maximum detail completeness
    desc = post_data.get("description") or ""
    tagline = post_data.get("tagline") or ""
    combined_text = f"{tagline}\n\n{desc}".strip() or "No description"

    existing_post = (
        db.query(RawProductHuntPost).filter(RawProductHuntPost.ph_post_id == ph_post_id).first()
    )

    if not existing_post:
        post_author = post_data.get("user", {}).get("name") if post_data.get("user") else None

        post_item = RawProductHuntPost(
            id=str(uuid.uuid4()),
            ph_post_id=ph_post_id,
            slug=slug,
            title=post_data.get("name") or "Spotify on Product Hunt",
            text=combined_text,
            votes_count=post_data.get("votesCount") or 0,
            author=post_author,
            url=post_data.get("url"),
            posted_at=parse_iso_datetime(post_data.get("createdAt")),
            raw_payload=json.dumps(post_data),
        )
        db.add(post_item)
        rows_inserted += 1
    else:
        rows_skipped += 1

    # 2. Process Comments
    comment_edges = post_data.get("comments", {}).get("edges", [])
    for edge in comment_edges:
        node = edge.get("node")
        if not node:
            continue

        rows_read += 1
        ph_comment_id = str(node.get("id"))

        existing_comment = (
            db.query(RawProductHuntComment)
            .filter(RawProductHuntComment.ph_comment_id == ph_comment_id)
            .first()
        )

        if not existing_comment:
            comment_author = node.get("user", {}).get("name") if node.get("user") else None

            comment_item = RawProductHuntComment(
                id=str(uuid.uuid4()),
                ph_comment_id=ph_comment_id,
                ph_post_id=ph_post_id,
                text=node.get("body") or "",
                author=comment_author,
                votes_count=node.get("votesCount") or 0,
                posted_at=parse_iso_datetime(node.get("createdAt")),
                raw_payload=json.dumps(node),
            )
            db.add(comment_item)
            rows_inserted += 1
        else:
            rows_skipped += 1

    db.commit()
    logger.info(
        f"PH Ingestion complete: read={rows_read}, inserted={rows_inserted}, skipped={rows_skipped}"
    )
    return rows_read, rows_inserted, rows_skipped
