from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.feedback_item import FeedbackItem
from app.models.raw_review import RawReview
from app.models.raw_product_hunt import RawProductHuntPost, RawProductHuntComment
from app.models.raw_youtube import RawYouTubeVideo, RawYouTubeComment


def test_normalization_idempotency(db, client):
    # 1. Setup raw reviews
    raw_1 = RawReview(
        id="raw-1",
        review_id="rev-101",
        text="  Awesome music discovery app!  ",
        title="  Love it!  ",
        rating=5.0,
        author="User A",
        platform="appstore",
        review_date=datetime(2026, 6, 1, 12, 0, 0),
    )
    raw_2 = RawReview(
        id="raw-2",
        review_id="rev-102",
        text="Too many bugs after update.",
        title=None,
        rating=2.0,
        author="User B",
        platform="playstore",
        review_date=datetime(2026, 6, 2, 14, 30, 0),
    )
    # This raw review has empty text after stripping, so it should be dropped
    raw_3 = RawReview(
        id="raw-3",
        review_id="rev-103",
        text="   ",
        title="Empty",
        rating=3.0,
        author="User C",
        platform="android",
        review_date=datetime(2026, 6, 3, 10, 0, 0),
    )
    db.add_all([raw_1, raw_2, raw_3])
    db.commit()

    # 2. Run normalization via API POST
    response = client.post("/feedback/normalize")
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "success"
    assert res_data["processed"] == 3
    assert res_data["inserted"] == 2
    assert res_data["skipped"] == 0
    assert res_data["dropped"] == 1
    assert res_data["failed"] == 0

    # Verify database contents
    items = db.query(FeedbackItem).all()
    assert len(items) == 2

    # Check item 1 normalization
    item_1 = db.query(FeedbackItem).filter(FeedbackItem.raw_id == "raw-1").first()
    assert item_1 is not None
    assert item_1.text == "Awesome music discovery app!"
    assert item_1.title == "Love it!"
    assert item_1.platform == "app_store"
    assert item_1.rating_or_score == 5.0
    assert item_1.created_at == datetime(2026, 6, 1, 12, 0, 0)
    assert item_1.raw_table == "raw_reviews"

    # Check item 2 normalization
    item_2 = db.query(FeedbackItem).filter(FeedbackItem.raw_id == "raw-2").first()
    assert item_2 is not None
    assert item_2.text == "Too many bugs after update."
    assert item_2.title is None
    assert item_2.platform == "play_store"
    assert item_2.created_at == datetime(2026, 6, 2, 14, 30, 0)

    # 3. Run normalization again and verify idempotency
    response_again = client.post("/feedback/normalize")
    assert response_again.status_code == 200
    res_data_again = response_again.json()
    assert res_data_again["status"] == "success"
    assert res_data_again["processed"] == 3
    assert res_data_again["inserted"] == 0
    assert res_data_again["skipped"] == 2
    assert res_data_again["dropped"] == 1
    assert res_data_again["failed"] == 0

    # Ensure no duplicates in DB
    items_again = db.query(FeedbackItem).all()
    assert len(items_again) == 2

    # 4. Enforce unique constraint at DB level (attempt direct duplicate insert)
    duplicate_item = FeedbackItem(
        id="some-new-uuid",
        source_type="app_review",
        platform="app_store",
        text="Some text",
        raw_id="raw-1",  # duplicate raw_id
    )
    db.add(duplicate_item)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_feedback_pagination_and_ordering(db, client):
    # Create 5 normalized items with different dates
    items = []
    for i in range(5):
        items.append(
            FeedbackItem(
                id=f"item-{i}",
                source_type="app_review",
                platform="app_store",
                text=f"Feedback number {i}",
                rating_or_score=float(i),
                created_at=datetime(2026, 6, i + 1, 12, 0, 0),
                raw_id=f"raw-id-{i}",
            )
        )
    db.add_all(items)
    db.commit()

    # Query GET /feedback limit=2, offset=0
    # Expected ordering: newest first (item-4, then item-3)
    response = client.get("/feedback?limit=2&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2
    assert data["items"][0]["id"] == "item-4"
    assert data["items"][1]["id"] == "item-3"

    # Query GET /feedback limit=2, offset=2
    # Expected: item-2, then item-1
    response = client.get("/feedback?limit=2&offset=2")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2
    assert data["items"][0]["id"] == "item-2"
    assert data["items"][1]["id"] == "item-1"

    # Query GET /feedback limit=2, offset=4
    # Expected: item-0
    response = client.get("/feedback?limit=2&offset=4")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == "item-0"


def test_product_hunt_youtube_normalization(db, client):
    # Setup raw Product Hunt post/comment and YouTube video/comment
    ph_post = RawProductHuntPost(
        id="ph-post-uuid",
        ph_post_id="ph-post-1",
        slug="spotify",
        title="Spotify Product Hunt Post",
        text="Check this new version of Spotify!",
        votes_count=100,
        author="PH User",
        url="https://producthunt.com/posts/spotify",
        posted_at=datetime(2026, 6, 1, 10, 0, 0),
        raw_payload="{}",
    )
    ph_comment = RawProductHuntComment(
        id="ph-comment-uuid",
        ph_comment_id="ph-comment-1",
        ph_post_id="ph-post-1",
        text="Really interesting feature update",
        author="Commenter PH",
        votes_count=5,
        posted_at=datetime(2026, 6, 1, 11, 0, 0),
        raw_payload="{}",
    )
    yt_video = RawYouTubeVideo(
        id="yt-video-uuid",
        video_id="yt-video-1",
        search_query="spotify recommendation",
        title="Spotify Review Video",
        description="A detailed video review of Spotify's engine.",
        author="Youtuber A",
        channel_id="chan-1",
        url="https://youtube.com/watch?v=yt-video-1",
        posted_at=datetime(2026, 6, 2, 15, 0, 0),
        raw_payload="{}",
    )
    yt_comment = RawYouTubeComment(
        id="yt-comment-uuid",
        comment_id="yt-comment-1",
        video_id="yt-video-1",
        thread_id="thread-1",
        text="I love this video, the engine is great",
        author="Viewer B",
        like_count=10,
        posted_at=datetime(2026, 6, 2, 16, 0, 0),
        raw_payload="{}",
    )
    
    db.add_all([ph_post, ph_comment, yt_video, yt_comment])
    db.commit()

    # Run normalization
    response = client.post("/feedback/normalize")
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "success"
    assert res_data["inserted"] >= 4

    # Verify normalization mapping in FeedbackItem
    items = db.query(FeedbackItem).filter(FeedbackItem.platform.in_(["product_hunt", "youtube"])).all()
    assert len(items) == 4

    # Check PH post
    ph_post_normalized = db.query(FeedbackItem).filter(FeedbackItem.source_type == "producthunt_post").first()
    assert ph_post_normalized is not None
    assert ph_post_normalized.title == "Spotify Product Hunt Post"
    assert ph_post_normalized.text == "Check this new version of Spotify!"
    assert ph_post_normalized.platform == "product_hunt"
    assert ph_post_normalized.url == "https://producthunt.com/posts/spotify"
    assert ph_post_normalized.raw_table == "raw_product_hunt_posts"

    # Check PH comment
    ph_comment_normalized = db.query(FeedbackItem).filter(FeedbackItem.source_type == "producthunt_comment").first()
    assert ph_comment_normalized is not None
    assert ph_comment_normalized.text == "Really interesting feature update"
    assert ph_comment_normalized.platform == "product_hunt"
    assert ph_comment_normalized.raw_table == "raw_product_hunt_comments"

    # Check YT video
    yt_video_normalized = db.query(FeedbackItem).filter(FeedbackItem.source_type == "youtube_video").first()
    assert yt_video_normalized is not None
    assert yt_video_normalized.title == "Spotify Review Video"
    assert yt_video_normalized.text == "A detailed video review of Spotify's engine."
    assert yt_video_normalized.platform == "youtube"
    assert yt_video_normalized.url == "https://youtube.com/watch?v=yt-video-1"
    assert yt_video_normalized.raw_table == "raw_youtube_videos"

    # Check YT comment
    yt_comment_normalized = db.query(FeedbackItem).filter(FeedbackItem.source_type == "youtube_comment").first()
    assert yt_comment_normalized is not None
    assert yt_comment_normalized.text == "I love this video, the engine is great"
    assert yt_comment_normalized.platform == "youtube"
    assert yt_comment_normalized.url == "https://www.youtube.com/watch?v=yt-video-1"
    assert yt_comment_normalized.raw_table == "raw_youtube_comments"

    # Run again to verify idempotency
    response_again = client.post("/feedback/normalize")
    assert response_again.status_code == 200

