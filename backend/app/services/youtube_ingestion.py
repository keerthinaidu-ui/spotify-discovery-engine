from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
import uuid

from sqlalchemy.orm import Session
import httpx

from app.models.raw_youtube import RawYouTubeVideo, RawYouTubeComment

logger = logging.getLogger(__name__)


class YouTubeClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://www.googleapis.com/youtube/v3"

    def search_videos(self, query: str, max_results: int = 5) -> list[dict]:
        """Queries search.list for videos matching the query."""
        url = f"{self.base_url}/search"
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": max_results,
            "key": self.api_key,
        }
        try:
            with httpx.Client() as client:
                r = client.get(url, params=params, timeout=15.0)
                r.raise_for_status()
                return r.json().get("items", [])
        except Exception as e:
            logger.error(f"YouTube video search failed: {e}")
            raise RuntimeError(f"YouTube search failed: {e}") from e

    def fetch_video_details(self, video_ids: list[str]) -> list[dict]:
        """Queries videos.list to fetch detailed metadata and statistics in batch."""
        if not video_ids:
            return []
        url = f"{self.base_url}/videos"
        params = {
            "part": "snippet,statistics",
            "id": ",".join(video_ids),
            "key": self.api_key,
        }
        try:
            with httpx.Client() as client:
                r = client.get(url, params=params, timeout=15.0)
                r.raise_for_status()
                return r.json().get("items", [])
        except Exception as e:
            logger.error(f"YouTube batch video details fetch failed: {e}")
            raise RuntimeError(f"YouTube video details query failed: {e}") from e

    def fetch_video_comments(self, video_id: str, max_results: int = 20) -> list[dict]:
        """Queries commentThreads.list to fetch top-level comments under the video."""
        url = f"{self.base_url}/commentThreads"
        params = {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": max_results,
            "textFormat": "plainText",
            "key": self.api_key,
        }
        try:
            with httpx.Client() as client:
                r = client.get(url, params=params, timeout=15.0)
                # If comments are disabled, YouTube returns 403. We should handle this gracefully.
                if r.status_code == 403:
                    logger.warning(f"Comments are disabled for YouTube video {video_id}.")
                    return []
                r.raise_for_status()
                return r.json().get("items", [])
        except Exception as e:
            logger.error(f"YouTube comment fetch failed for video {video_id}: {e}")
            return []


def parse_youtube_datetime(dt_str: str | None) -> datetime:
    if not dt_str:
        return datetime.now(timezone.utc)
    try:
        cleaned = dt_str.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except Exception:
        return datetime.now(timezone.utc)


def ingest_youtube(
    db: Session,
    api_key: str,
    query: str,
    max_videos: int = 5,
    max_comments: int = 20,
) -> tuple[int, int, int]:
    """Runs YouTube Search + Detail Enrichment + Comment Threads Ingestion."""
    client = YouTubeClient(api_key=api_key)

    # 1. Search for matching videos
    search_items = client.search_videos(query=query, max_results=max_videos)
    video_ids = [
        item["id"]["videoId"] for item in search_items if item.get("id", {}).get("videoId")
    ]

    if not video_ids:
        logger.info(f"No YouTube videos found for search query '{query}'")
        return 0, 0, 0

    # 2. Batch-enrich details (statistics + description + channel ID)
    details_items = client.fetch_video_details(video_ids)
    details_map = {item["id"]: item for item in details_items}

    rows_read = 0
    rows_inserted = 0
    rows_skipped = 0

    # 3. Process each video and its comments
    for video_id in video_ids:
        rows_read += 1
        video_data = details_map.get(video_id)
        if not video_data:
            logger.warning(f"Could not retrieve video details for {video_id}")
            continue

        snippet = video_data.get("snippet", {})
        stats = video_data.get("statistics", {})

        # Check if video already exists in db
        existing_video = (
            db.query(RawYouTubeVideo).filter(RawYouTubeVideo.video_id == video_id).first()
        )

        if not existing_video:
            # Parse stats
            def parse_int_stat(val):
                return int(val) if val is not None else None

            video_item = RawYouTubeVideo(
                id=str(uuid.uuid4()),
                video_id=video_id,
                search_query=query,
                title=snippet.get("title") or "YouTube Video",
                description=snippet.get("description") or "",
                view_count=parse_int_stat(stats.get("viewCount")),
                like_count=parse_int_stat(stats.get("likeCount")),
                comment_count=parse_int_stat(stats.get("commentCount")),
                author=snippet.get("channelTitle") or "Unknown Channel",
                channel_id=snippet.get("channelId") or "Unknown ID",
                url=f"https://www.youtube.com/watch?v={video_id}",
                posted_at=parse_youtube_datetime(snippet.get("publishedAt")),
                raw_payload=json.dumps(video_data),
            )
            db.add(video_item)
            rows_inserted += 1
        else:
            rows_skipped += 1

        # 4. Fetch Top-Level Comments
        comment_threads = client.fetch_video_comments(video_id, max_results=max_comments)
        for thread in comment_threads:
            thread_snippet = thread.get("snippet", {})
            top_comment = thread_snippet.get("topLevelComment", {})
            c_snippet = top_comment.get("snippet", {})
            comment_id = top_comment.get("id")

            if not comment_id:
                continue

            rows_read += 1

            existing_comment = (
                db.query(RawYouTubeComment)
                .filter(RawYouTubeComment.comment_id == comment_id)
                .first()
            )

            if not existing_comment:
                comment_item = RawYouTubeComment(
                    id=str(uuid.uuid4()),
                    comment_id=comment_id,
                    video_id=video_id,
                    thread_id=thread.get("id") or comment_id,
                    parent_comment_id=None,  # We default to top-level comments
                    text=c_snippet.get("textOriginal") or c_snippet.get("textDisplay") or "",
                    author=c_snippet.get("authorDisplayName") or "Unknown Author",
                    like_count=c_snippet.get("likeCount") or 0,
                    posted_at=parse_youtube_datetime(c_snippet.get("publishedAt")),
                    raw_payload=json.dumps(thread),
                )
                db.add(comment_item)
                rows_inserted += 1
            else:
                rows_skipped += 1

    db.commit()
    logger.info(
        f"YouTube Ingestion complete: read={rows_read}, inserted={rows_inserted}, skipped={rows_skipped}"
    )
    return rows_read, rows_inserted, rows_skipped
