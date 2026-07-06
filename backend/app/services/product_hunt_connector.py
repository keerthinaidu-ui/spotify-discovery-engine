"""Product Hunt GraphQL API Connector.

Fetches qualitative feedback/comments for Spotify-related posts/products from Product Hunt GraphQL API v2.
"""

import json
import logging
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default target slugs relevant to Spotify (configured for easy editing)
DEFAULT_CURATED_SLUGS = [
    "spotify",
    "spotify-wrapped",
    "spotify-lite",
    "spotify-kids",
    "spotify-for-podcasters",
]


def _call_product_hunt_api(token: str, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
    """Helper to perform POST requests to Product Hunt GraphQL API."""
    url = "https://api.producthunt.com/v2/api/graphql"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "spotify-review-engine-product-hunt-connector/0.1",
    }
    payload = {"query": query, "variables": variables}
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        logger.error(f"Product Hunt GraphQL request failed: {exc}")
        raise RuntimeError(f"Product Hunt API call failed: {exc}") from exc


def fetch_post_discussions(token: str, slug: str) -> List[Dict[str, Any]]:
    """Fetches a Product Hunt post and its nested comments/discussions by slug.

    If comments/discussions are empty or unavailable, returns a fallback post-level record.
    """
    if not token:
        raise ValueError("PRODUCT_HUNT_TOKEN is not configured.")

    query = """
    query GetPostComments($slug: String!, $cursor: String) {
      post(slug: $slug) {
        id
        name
        tagline
        description
        createdAt
        comments(first: 50, after: $cursor) {
          pageInfo {
            hasNextPage
            endCursor
          }
          edges {
            node {
              id
              body
              createdAt
              user {
                username
                name
              }
            }
          }
        }
      }
    }
    """

    comments: List[Dict[str, Any]] = []
    cursor: Optional[str] = None
    has_next = True
    post_data: Optional[Dict[str, Any]] = None

    while has_next:
        variables = {"slug": slug, "cursor": cursor}
        try:
            data = _call_product_hunt_api(token, query, variables)
            errors = data.get("errors")
            if errors:
                logger.error(f"GraphQL errors returned for slug '{slug}': {errors}")
                break

            post = data.get("data", {}).get("post")
            if not post:
                logger.warning(f"No Product Hunt post found for slug '{slug}'")
                break

            post_data = post  # Save metadata for fallback or context
            comments_conn = post.get("comments", {})
            edges = comments_conn.get("edges", [])

            for edge in edges:
                node = edge.get("node", {})
                comment_id = node.get("id")
                body = node.get("body")
                created_at = node.get("createdAt")
                user = node.get("user", {})
                username = user.get("username") or user.get("name") or "Anonymous"

                if not comment_id or not body:
                    continue

                body = body.strip()
                if not body:
                    continue

                comments.append(
                    {
                        "source": "product_hunt",
                        "review_id": comment_id,
                        "user_name": username.strip(),
                        "rating": "",
                        "title": f"{post.get('name', 'Product Hunt')} - {post.get('tagline', '')}",
                        "review_text": body,
                        "review_date": created_at,
                        "spotify_version": "",
                        "country": "",
                    }
                )

            page_info = comments_conn.get("pageInfo", {})
            has_next = page_info.get("hasNextPage", False)
            cursor = page_info.get("endCursor")

            # Safety throttle / page limit
            if len(comments) >= 100:
                break

        except Exception as exc:
            logger.error(f"Error fetching comments for Product Hunt slug '{slug}': {exc}")
            break

    # Fallback to post-level record if no comments were fetched
    if not comments and post_data:
        logger.info(
            f"No comments found for Product Hunt post '{slug}'. Creating post-level fallback record."
        )
        post_id = post_data.get("id")
        name = post_data.get("name", "Product Hunt")
        tagline = post_data.get("tagline", "")
        description = post_data.get("description", "")
        created_at = post_data.get("createdAt")

        # Map details to fallback record
        fallback_text = f"Tagline: {tagline}\nDescription: {description}".strip()
        comments.append(
            {
                "source": "product_hunt",
                "review_id": f"ph_fallback_{post_id}" if post_id else f"ph_fallback_{slug}",
                "user_name": "Product Hunt Community",
                "rating": "",
                "title": f"{name} - {tagline}".strip(),
                "review_text": fallback_text or f"Product discussion for {name}",
                "review_date": created_at,
                "spotify_version": "",
                "country": "",
            }
        )

    return comments


def fetch_product_hunt_reviews(
    token: str,
    slugs: Optional[List[str]] = None,
    max_records: int = 100,
) -> List[Dict[str, Any]]:
    """Main entry point for fetching Product Hunt reviews/discussions."""
    if not token:
        raise ValueError("PRODUCT_HUNT_TOKEN is not configured.")

    target_slugs = slugs or DEFAULT_CURATED_SLUGS
    all_records: List[Dict[str, Any]] = []

    logger.info(f"Targeting Product Hunt slugs for ingestion: {target_slugs}")

    for idx, slug in enumerate(target_slugs, 1):
        logger.info(f"Ingesting Product Hunt discussion for slug {idx}/{len(target_slugs)}: {slug}")
        try:
            slug_comments = fetch_post_discussions(token, slug)
            all_records.extend(slug_comments)
            logger.info(f"Fetched {len(slug_comments)} records from Product Hunt slug: {slug}")
        except Exception as exc:
            logger.error(
                f"Failed to fetch Product Hunt slug '{slug}': {exc}. Continuing with other slugs."
            )

        if len(all_records) >= max_records:
            logger.info(f"Reached configured limit of {max_records} Product Hunt records.")
            break

    return all_records[:max_records]
