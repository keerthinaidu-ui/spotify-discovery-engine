from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.feedback_item import FeedbackItem
from app.models.raw_review import RawReview
from app.models.raw_product_hunt import RawProductHuntPost, RawProductHuntComment
from app.models.raw_youtube import RawYouTubeVideo, RawYouTubeComment

logger = logging.getLogger(__name__)


def clean_whitespace(text: str | None) -> str | None:
    if text is None:
        return None
    # Strip leading/trailing whitespace
    text = text.strip()
    # Replace multiple spaces/tabs/carriage-returns with a single space
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    # Replace multiple consecutive newlines with a single newline
    text = re.sub(r"\n+", "\n", text)
    return text


def normalize_platform(platform: str | None) -> str:
    if not platform:
        return "app_store"
    platform_lower = platform.strip().lower()
    if platform_lower in ("appstore", "app_store", "ios", "apple"):
        return "app_store"
    elif platform_lower in ("playstore", "play_store", "android", "google"):
        return "play_store"
    return platform_lower


def check_and_truncate(val: str | None, max_len: int, table: str, column: str, row_id: str) -> str | None:
    if val is None:
        return None
    val_str = str(val)
    if len(val_str) > max_len:
        from app.services.etl_logger import tracker
        tracker.track_truncation(table, column, row_id, len(val_str), max_len)
        return val_str[:max_len]
    return val_str


def validate_json_string(val: str | None) -> bool:
    if not val:
        return True
    try:
        if isinstance(val, (dict, list)):
            return True
        json.loads(val)
        return True
    except Exception as e:
        logger.error(f"JSON validation error for value of type {type(val)}: {val!r}. Error: {e}")
        return False


def run_normalization(db: Session) -> dict[str, int]:
    processed = 0
    inserted = 0
    skipped = 0
    dropped = 0
    failed = 0

    try:
        # Fetch all existing raw_ids/tables from feedback_items
        existing_items = {
            (row[0], row[1])
            for row in db.query(FeedbackItem.raw_table, FeedbackItem.raw_id).all()
            if row[0] and row[1]
        }
    except Exception as e:
        logger.error(f"Failed to query existing feedback_items: {e}")
        raise

    chunk_size = 1000
    offset = 0

    # 1. Normalize raw_reviews
    while True:
        try:
            raw_reviews = (
                db.query(RawReview).order_by(RawReview.id).offset(offset).limit(chunk_size).all()
            )
        except Exception as e:
            logger.error(f"Failed to fetch raw_reviews at offset {offset}: {e}")
            break

        if not raw_reviews:
            break

        batch_to_insert = []
        for raw in raw_reviews:
            processed += 1
            try:
                # Deduplicate by raw_id
                if ("raw_reviews", raw.id) in existing_items:
                    skipped += 1
                    continue

                # Clean text/title whitespace
                cleaned_text = clean_whitespace(raw.text)
                if not cleaned_text:
                    dropped += 1
                    continue

                cleaned_title = clean_whitespace(raw.title)
                if cleaned_title == "":
                    cleaned_title = None

                # Normalize platform
                normalized_platform = normalize_platform(raw.platform)

                # Normalize date (consistently based on source date only)
                created_at = raw.review_date

                # Author
                cleaned_author = raw.author.strip() if raw.author else None
                if cleaned_author == "":
                    cleaned_author = None

                # Field validations and truncations
                cleaned_title = check_and_truncate(cleaned_title, 512, "feedback_items", "title", raw.id)
                cleaned_author = check_and_truncate(cleaned_author, 256, "feedback_items", "author", raw.id)
                app_version = check_and_truncate(raw.app_version, 64, "feedback_items", "app_version", raw.id)
                url = check_and_truncate(raw.url, 1024, "feedback_items", "url", raw.id)
                normalized_platform = check_and_truncate(normalized_platform, 32, "feedback_items", "platform", raw.id)

                item = FeedbackItem(
                    id=str(uuid.uuid4()),
                    source_type="app_review",
                    platform=normalized_platform,
                    text=cleaned_text,
                    title=cleaned_title,
                    rating_or_score=raw.rating,
                    author=cleaned_author,
                    created_at=created_at,
                    app_version=app_version,
                    url=url,
                    raw_table="raw_reviews",
                    raw_id=raw.id,
                    sentiment=None,
                    analysis_status="pending",
                    retry_count=0,
                    normalized_at=datetime.now(timezone.utc),
                )
                batch_to_insert.append(item)
            except Exception as e:
                logger.error(f"Error normalizing raw_review {raw.id}: {e}")
                failed += 1

        if batch_to_insert:
            try:
                db.add_all(batch_to_insert)
                db.commit()
                inserted += len(batch_to_insert)
                for item in batch_to_insert:
                    existing_items.add((item.raw_table, item.raw_id))
            except Exception as e:
                db.rollback()
                logger.warning(
                    f"Batch commit failed at offset {offset}: {e}. Retrying individually."
                )
                for item in batch_to_insert:
                    try:
                        db.add(item)
                        db.commit()
                        inserted += 1
                        existing_items.add((item.raw_table, item.raw_id))
                    except Exception as single_exc:
                        db.rollback()
                        logger.error(
                            f"Single insert failed for raw_review {item.raw_id}: {single_exc}"
                        )
                        failed += 1

        offset += chunk_size

    # 2. Normalize raw_product_hunt_posts
    try:
        ph_posts = db.query(RawProductHuntPost).all()
        batch_ph_posts = []
        for raw in ph_posts:
            processed += 1
            try:
                if ("raw_product_hunt_posts", raw.ph_post_id) in existing_items:
                    skipped += 1
                    continue
                
                # Audit JSON validity of raw_payload
                if not validate_json_string(raw.raw_payload):
                    logger.error(f"JSON validation failed for RawProductHuntPost ID {raw.id}")
                    failed += 1
                    continue

                cleaned_text = clean_whitespace(raw.text)
                if not cleaned_text:
                    dropped += 1
                    continue
                
                cleaned_title = clean_whitespace(raw.title) or None
                cleaned_author = raw.author.strip() if raw.author else None

                # Field validations and truncations
                cleaned_title = check_and_truncate(cleaned_title, 512, "feedback_items", "title", raw.id)
                cleaned_author = check_and_truncate(cleaned_author, 256, "feedback_items", "author", raw.id)
                url = check_and_truncate(raw.url, 1024, "feedback_items", "url", raw.id)

                item = FeedbackItem(
                    id=str(uuid.uuid4()),
                    source_type="producthunt_post",
                    platform="product_hunt",
                    text=cleaned_text,
                    title=cleaned_title,
                    rating_or_score=None,
                    author=cleaned_author,
                    created_at=raw.posted_at,
                    raw_table="raw_product_hunt_posts",
                    raw_id=raw.ph_post_id,
                    url=url,
                    sentiment=None,
                    analysis_status="pending",
                    retry_count=0,
                    normalized_at=datetime.now(timezone.utc),
                )
                batch_ph_posts.append(item)
            except Exception as e:
                logger.error(f"Error normalizing raw_product_hunt_post {raw.id}: {e}")
                failed += 1

        if batch_ph_posts:
            try:
                db.add_all(batch_ph_posts)
                db.commit()
                inserted += len(batch_ph_posts)
                for x in batch_ph_posts:
                    existing_items.add((x.raw_table, x.raw_id))
            except Exception as e:
                db.rollback()
                logger.error(f"Batch commit failed for product hunt posts: {e}")
                failed += len(batch_ph_posts)

    except Exception as e:
        logger.error(f"Error querying raw_product_hunt_posts: {e}")
        raise

    # 3. Normalize raw_product_hunt_comments
    try:
        ph_comments = db.query(RawProductHuntComment).all()
        batch_ph_comments = []
        for raw in ph_comments:
            processed += 1
            try:
                if ("raw_product_hunt_comments", raw.ph_comment_id) in existing_items:
                    skipped += 1
                    continue
                
                # Audit JSON validity of raw_payload
                if not validate_json_string(raw.raw_payload):
                    logger.error(f"JSON validation failed for RawProductHuntComment ID {raw.id}")
                    failed += 1
                    continue

                cleaned_text = clean_whitespace(raw.text)
                if not cleaned_text:
                    dropped += 1
                    continue
                
                cleaned_author = raw.author.strip() if raw.author else None
                cleaned_author = check_and_truncate(cleaned_author, 256, "feedback_items", "author", raw.id)

                item = FeedbackItem(
                    id=str(uuid.uuid4()),
                    source_type="producthunt_comment",
                    platform="product_hunt",
                    text=cleaned_text,
                    title=None,
                    rating_or_score=None,
                    author=cleaned_author,
                    created_at=raw.posted_at,
                    raw_table="raw_product_hunt_comments",
                    raw_id=raw.ph_comment_id,
                    url=None,
                    sentiment=None,
                    analysis_status="pending",
                    retry_count=0,
                    normalized_at=datetime.now(timezone.utc),
                )
                batch_ph_comments.append(item)
            except Exception as e:
                logger.error(f"Error normalizing raw_product_hunt_comment {raw.id}: {e}")
                failed += 1

        if batch_ph_comments:
            try:
                db.add_all(batch_ph_comments)
                db.commit()
                inserted += len(batch_ph_comments)
                for x in batch_ph_comments:
                    existing_items.add((x.raw_table, x.raw_id))
            except Exception as e:
                db.rollback()
                logger.error(f"Batch commit failed for product hunt comments: {e}")
                failed += len(batch_ph_comments)

    except Exception as e:
        logger.error(f"Error querying raw_product_hunt_comments: {e}")
        raise

    # 4. Normalize raw_youtube_videos
    try:
        yt_videos = db.query(RawYouTubeVideo).all()
        batch_yt_videos = []
        for raw in yt_videos:
            processed += 1
            try:
                if ("raw_youtube_videos", raw.video_id) in existing_items:
                    skipped += 1
                    continue

                # Audit JSON validity of raw_payload
                if not validate_json_string(raw.raw_payload):
                    logger.error(f"JSON validation failed for RawYouTubeVideo ID {raw.id}")
                    failed += 1
                    continue

                cleaned_text = clean_whitespace(raw.description)
                if not cleaned_text:
                    cleaned_text = clean_whitespace(raw.title) or "No description"
                
                cleaned_title = clean_whitespace(raw.title) or None
                cleaned_author = raw.author.strip() if raw.author else None

                # Field validations and truncations
                cleaned_title = check_and_truncate(cleaned_title, 512, "feedback_items", "title", raw.id)
                cleaned_author = check_and_truncate(cleaned_author, 256, "feedback_items", "author", raw.id)
                url = check_and_truncate(raw.url, 1024, "feedback_items", "url", raw.id)

                item = FeedbackItem(
                    id=str(uuid.uuid4()),
                    source_type="youtube_video",
                    platform="youtube",
                    text=cleaned_text,
                    title=cleaned_title,
                    rating_or_score=None,
                    author=cleaned_author,
                    created_at=raw.posted_at,
                    raw_table="raw_youtube_videos",
                    raw_id=raw.video_id,
                    url=url,
                    sentiment=None,
                    analysis_status="pending",
                    retry_count=0,
                    normalized_at=datetime.now(timezone.utc),
                )
                batch_yt_videos.append(item)
            except Exception as e:
                logger.error(f"Error normalizing raw_youtube_video {raw.id}: {e}")
                failed += 1

        if batch_yt_videos:
            try:
                db.add_all(batch_yt_videos)
                db.commit()
                inserted += len(batch_yt_videos)
                for x in batch_yt_videos:
                    existing_items.add((x.raw_table, x.raw_id))
            except Exception as e:
                db.rollback()
                logger.error(f"Batch commit failed for youtube videos: {e}")
                failed += len(batch_yt_videos)

    except Exception as e:
        logger.error(f"Error querying raw_youtube_videos: {e}")
        raise

    # 5. Normalize raw_youtube_comments
    try:
        yt_comments = db.query(RawYouTubeComment).all()
        batch_yt_comments = []
        for raw in yt_comments:
            processed += 1
            try:
                if ("raw_youtube_comments", raw.comment_id) in existing_items:
                    skipped += 1
                    continue

                # Audit JSON validity of raw_payload
                if not validate_json_string(raw.raw_payload):
                    logger.error(f"JSON validation failed for RawYouTubeComment ID {raw.id}")
                    failed += 1
                    continue

                cleaned_text = clean_whitespace(raw.text)
                if not cleaned_text:
                    dropped += 1
                    continue
                
                cleaned_author = raw.author.strip() if raw.author else None
                cleaned_author = check_and_truncate(cleaned_author, 256, "feedback_items", "author", raw.id)
                url = f"https://www.youtube.com/watch?v={raw.video_id}" if raw.video_id else None
                url = check_and_truncate(url, 1024, "feedback_items", "url", raw.id)

                item = FeedbackItem(
                    id=str(uuid.uuid4()),
                    source_type="youtube_comment",
                    platform="youtube",
                    text=cleaned_text,
                    title=None,
                    rating_or_score=None,
                    author=cleaned_author,
                    created_at=raw.posted_at,
                    raw_table="raw_youtube_comments",
                    raw_id=raw.comment_id,
                    url=url,
                    sentiment=None,
                    analysis_status="pending",
                    retry_count=0,
                    normalized_at=datetime.now(timezone.utc),
                )
                batch_yt_comments.append(item)
            except Exception as e:
                logger.error(f"Error normalizing raw_youtube_comment {raw.id}: {e}")
                failed += 1

        if batch_yt_comments:
            try:
                db.add_all(batch_yt_comments)
                db.commit()
                inserted += len(batch_yt_comments)
                for x in batch_yt_comments:
                    existing_items.add((x.raw_table, x.raw_id))
            except Exception as e:
                db.rollback()
                logger.error(f"Batch commit failed for youtube comments: {e}")
                failed += len(batch_yt_comments)

    except Exception as e:
        logger.error(f"Error querying raw_youtube_comments: {e}")
        raise

    # Row-Level Parity Check
    expected_total = inserted + skipped + dropped + failed
    if processed != expected_total:
        raise ValueError(
            f"Normalization row-level parity check failed: "
            f"processed ({processed}) does not match sum of states "
            f"(inserted={inserted}, skipped={skipped}, dropped={dropped}, failed={failed})"
        )

    return {
        "processed": processed,
        "inserted": inserted,
        "skipped": skipped,
        "dropped": dropped,
        "failed": failed,
    }

