"""YouTube API Connector.

Fetches qualitative feedback/comments for Spotify-related videos using the YouTube Data API v3.
"""

import json
import logging
import urllib.request
import urllib.parse
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default curated list of Spotify-related video IDs for demo/MVP purposes
CURATED_VIDEO_IDS = [
    "M5D3Dxp0i8c",  # Spotify vs Apple Music
    "2D4K5Y-vWsk",  # Spotify's recommendation algorithm explained
    "L_LUpnjgPso",  # How Spotify knows what you want to hear
]

DEFAULT_FALLBACK_QUERIES = [
    "Spotify review",
    "Spotify recommendations",
    "Spotify update",
]


def _call_youtube_api(url: str) -> Dict[str, Any]:
    """Helper to perform GET requests to the YouTube API."""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "spotify-review-engine-youtube-connector/0.1",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        logger.error(f"YouTube API request failed for URL {url}: {exc}")
        raise RuntimeError(f"YouTube API call failed: {exc}") from exc


def get_video_title(api_key: str, video_id: str) -> str:
    """Fetches the title of a specific video."""
    if not api_key:
        raise ValueError("YOUTUBE_API_KEY is not configured.")

    params = {
        "part": "snippet",
        "id": video_id,
        "key": api_key,
    }
    url = f"https://www.googleapis.com/youtube/v3/videos?{urllib.parse.urlencode(params)}"
    try:
        data = _call_youtube_api(url)
        items = data.get("items", [])
        if items:
            return items[0].get("snippet", {}).get("title", f"YouTube Video {video_id}")
    except Exception as exc:
        logger.warning(f"Could not fetch video title for {video_id}: {exc}")
    return f"YouTube Video {video_id}"


def search_videos(api_key: str, queries: List[str], max_results: int = 5) -> List[Dict[str, str]]:
    """Searches YouTube for videos matching queries and returns video info dicts."""
    if not api_key:
        raise ValueError("YOUTUBE_API_KEY is not configured.")

    videos: Dict[str, str] = {}
    for query in queries:
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "key": api_key,
            "maxResults": max_results,
        }
        url = f"https://www.googleapis.com/youtube/v3/search?{urllib.parse.urlencode(params)}"
        try:
            logger.info(f"Searching YouTube for: '{query}'")
            data = _call_youtube_api(url)
            for item in data.get("items", []):
                v_id = item.get("id", {}).get("videoId")
                v_title = item.get("snippet", {}).get("title")
                if v_id and v_title:
                    videos[v_id] = v_title
        except Exception as exc:
            logger.error(f"Search query '{query}' failed: {exc}")

        if len(videos) >= max_results:
            break

    # Format return list
    return [{"video_id": vid, "title": title} for vid, title in videos.items()][:max_results]


def fetch_comments_for_video(
    api_key: str, video_id: str, max_comments: int = 100
) -> List[Dict[str, Any]]:
    """Fetches comment threads for a given video ID with pagination."""
    if not api_key:
        raise ValueError("YOUTUBE_API_KEY is not configured.")

    comments: List[Dict[str, Any]] = []
    page_token: Optional[str] = None
    video_title = get_video_title(api_key, video_id)

    while len(comments) < max_comments:
        params = {
            "part": "snippet",
            "videoId": video_id,
            "key": api_key,
            "maxResults": min(100, max_comments - len(comments)),
            "order": "time",
            "textFormat": "plainText",
        }
        if page_token:
            params["pageToken"] = page_token

        url = (
            f"https://www.googleapis.com/youtube/v3/commentThreads?{urllib.parse.urlencode(params)}"
        )
        try:
            data = _call_youtube_api(url)
            items = data.get("items", [])
            if not items:
                break

            for item in items:
                snippet = item.get("snippet", {})
                top_comment = snippet.get("topLevelComment", {})
                comment_snippet = top_comment.get("snippet", {})

                comment_id = top_comment.get("id") or item.get("id")
                author = comment_snippet.get("authorDisplayName")
                text = comment_snippet.get("textOriginal") or comment_snippet.get("textDisplay")
                published_at = comment_snippet.get("publishedAt")

                if not comment_id or not text:
                    continue

                # Strip whitespace and check if text is empty
                text = text.strip()
                if not text:
                    continue

                comments.append(
                    {
                        "source": "youtube",
                        "review_id": comment_id,
                        "user_name": (author or "Anonymous").strip(),
                        "rating": "",
                        "title": video_title,
                        "review_text": text,
                        "review_date": published_at,
                        "spotify_version": "",
                        "country": "",
                        "video_id": video_id,
                        "like_count": comment_snippet.get("likeCount", 0),
                        "reply_count": snippet.get("totalReplyCount", 0),
                    }
                )

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        except Exception as exc:
            logger.error(f"Error fetching comments for video {video_id}: {exc}")
            break

    return comments[:max_comments]


def fetch_youtube_reviews(
    api_key: str,
    video_ids: Optional[List[str]] = None,
    fallback_queries: Optional[List[str]] = None,
    max_videos: int = 5,
    max_comments: int = 100,
) -> List[Dict[str, Any]]:
    """Main entry point for fetching YouTube reviews."""
    if not api_key:
        raise ValueError("YOUTUBE_API_KEY is not configured.")

    if not video_ids:
        # Fallback to searching
        queries = fallback_queries or DEFAULT_FALLBACK_QUERIES
        logger.info(
            f"No curated video IDs provided. Falling back to search mode with queries: {queries}"
        )
        found_videos = search_videos(api_key, queries, max_results=max_videos)
        video_targets = [v["video_id"] for v in found_videos]
    else:
        video_targets = video_ids[:max_videos]

    all_reviews: List[Dict[str, Any]] = []
    logger.info(f"Targeting YouTube videos for ingestion: {video_targets}")

    for idx, video_id in enumerate(video_targets, 1):
        logger.info(f"Ingesting video comments for video {idx}/{len(video_targets)}: {video_id}")
        try:
            video_comments = fetch_comments_for_video(api_key, video_id, max_comments=max_comments)
            all_reviews.extend(video_comments)
            logger.info(f"Fetched {len(video_comments)} comments from video {video_id}")
        except Exception as exc:
            logger.error(
                f"Failed to fetch comments for video {video_id}: {exc}. Continuing with other videos."
            )

    return all_reviews
