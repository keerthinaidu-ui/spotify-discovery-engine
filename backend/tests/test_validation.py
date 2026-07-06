from datetime import datetime
import pytest
from sqlalchemy.exc import IntegrityError
from app.models.feedback_item import FeedbackItem
from app.models.raw_review import RawReview
from app.models.raw_product_hunt import RawProductHuntPost, RawProductHuntComment
from app.models.raw_youtube import RawYouTubeVideo, RawYouTubeComment

def test_health_smoke(client):
    """Smoke test: Verify that the API is active and returns database connectivity status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "database" in data


def test_dashboard_stats_overview_consistency_smoke(db, client):
    """Smoke test: Verify overview stats and overall consistency of counts across different platforms."""
    db.query(FeedbackItem).delete()
    db.commit()

    # Insert mock feedback items
    items = [
        FeedbackItem(
            id="item-1",
            source_type="app_review",
            platform="app_store",
            text="Feedback 1",
            rating_or_score=4.0,
            raw_id="raw-1",
            created_at=datetime(2026, 6, 1, 12, 0, 0),
        ),
        FeedbackItem(
            id="item-2",
            source_type="app_review",
            platform="play_store",
            text="Feedback 2",
            rating_or_score=5.0,
            raw_id="raw-2",
            created_at=datetime(2026, 6, 1, 13, 0, 0),
        ),
        FeedbackItem(
            id="item-3",
            source_type="producthunt_post",
            platform="product_hunt",
            text="Feedback 3",
            rating_or_score=None,
            raw_id="raw-3",
            created_at=datetime(2026, 6, 2, 12, 0, 0),
        ),
        FeedbackItem(
            id="item-4",
            source_type="youtube_comment",
            platform="youtube",
            text="Feedback 4",
            rating_or_score=None,
            raw_id="raw-4",
            created_at=datetime(2026, 6, 2, 14, 0, 0),
        ),
    ]
    db.add_all(items)
    db.commit()

    response = client.get("/feedback/stats/overview")
    assert response.status_code == 200
    data = response.json()
    assert data["total_records"] == 4
    assert data["platform_counts"]["app_store"] == 1
    assert data["platform_counts"]["play_store"] == 1
    assert data["platform_counts"]["product_hunt"] == 1
    assert data["platform_counts"]["youtube"] == 1
    assert data["source_type_counts"]["app_review"] == 2
    assert data["source_type_counts"]["producthunt_post"] == 1
    assert data["source_type_counts"]["youtube_comment"] == 1

    # Verify count consistency
    assert sum(data["platform_counts"].values()) == 4
    assert sum(data["source_type_counts"].values()) == 4
    assert len(data["date_buckets"]) == 2


def test_database_uniqueness_constraints_uat(db):
    """Staging validation: Verify uniqueness constraints at DB level for FeedbackItem."""
    db.query(FeedbackItem).delete()
    db.commit()

    item1 = FeedbackItem(
        id="u-1",
        source_type="app_review",
        platform="app_store",
        text="Feedback 1",
        raw_id="raw-dup",
    )
    item2 = FeedbackItem(
        id="u-2",
        source_type="app_review",
        platform="app_store",
        text="Feedback 2",
        raw_id="raw-dup",
    )

    db.add(item1)
    db.commit()

    db.add(item2)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()



def test_normalization_idempotency_uat(db, client):
    """Staging validation: Verify that the normalization process is idempotent across CSV, Product Hunt, and YouTube."""
    # 1. Clear database
    db.query(FeedbackItem).delete()
    db.query(RawReview).delete()
    db.query(RawProductHuntPost).delete()
    db.query(RawProductHuntComment).delete()
    db.query(RawYouTubeVideo).delete()
    db.query(RawYouTubeComment).delete()
    db.commit()

    # 2. Insert mock raw items
    raw_rev = RawReview(
        id="rev-1",
        review_id="rev-id-1",
        text="Loved the lyrics sync feature on Spotify!",
        rating=5.0,
        platform="playstore",
        review_date=datetime(2026, 6, 1, 10, 0, 0)
    )
    ph_post = RawProductHuntPost(
        id="ph-post-1",
        ph_post_id="ph-id-post",
        slug="spotify",
        title="Spotify Product Hunt",
        text="A new release of Spotify with DJ AI.",
        votes_count=120,
        posted_at=datetime(2026, 6, 2, 10, 0, 0),
        raw_payload="{}"
    )
    yt_comment = RawYouTubeComment(
        id="yt-comment-1",
        comment_id="yt-id-comment",
        video_id="video-123",
        thread_id="thread-123",
        text="This recommendation algorithm is great.",
        author="User A",
        like_count=3,
        posted_at=datetime(2026, 6, 3, 12, 0, 0),
        raw_payload="{}"
    )
    db.add_all([raw_rev, ph_post, yt_comment])
    db.commit()

    # 3. Trigger normalization first time
    response = client.post("/feedback/normalize")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["inserted"] == 3
    assert data["skipped"] == 0

    # 4. Trigger normalization second time (idempotency check)
    response_again = client.post("/feedback/normalize")
    assert response_again.status_code == 200
    data_again = response_again.json()
    assert data_again["status"] == "success"
    assert data_again["inserted"] == 0
    assert data_again["skipped"] == 3

    # 5. Check count in feedback_items
    total_feedback = db.query(FeedbackItem).count()
    assert total_feedback == 3


def test_sentiment_fallback_and_serialization_uat(db, client):
    """UAT-01: Verify that sentiment resolves to fallback ratings correctly in filters and serialization."""
    db.query(FeedbackItem).delete()
    db.commit()

    item_pos = FeedbackItem(
        id="pos-1",
        source_type="app_review",
        platform="play_store",
        text="Amazing music player!",
        rating_or_score=5.0,
        raw_id="raw-p",
        sentiment=None  # triggers positive fallback
    )
    item_neg = FeedbackItem(
        id="neg-1",
        source_type="app_review",
        platform="app_store",
        text="Crashes constantly.",
        rating_or_score=1.0,
        raw_id="raw-n",
        sentiment=None  # triggers negative fallback
    )
    db.add_all([item_pos, item_neg])
    db.commit()

    # Query for positive
    response = client.get("/feedback?sentiment=positive")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == "pos-1"
    assert data["items"][0]["sentiment"] == "positive"  # dynamically serialized

    # Query for negative
    response = client.get("/feedback?sentiment=negative")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == "neg-1"
    assert data["items"][0]["sentiment"] == "negative"  # dynamically serialized


def test_zero_result_states_safety_uat(db, client):
    """UAT-02: Verify that zero-result states handle counts safely without NaN/Infinity or div-by-zero crashes."""
    db.query(FeedbackItem).delete()
    db.commit()

    # 1. Fetch overview statistics
    response = client.get("/feedback/stats/overview")
    assert response.status_code == 200
    data = response.json()
    assert data["total_records"] == 0
    assert len(data["platform_counts"]) == 0
    assert len(data["source_type_counts"]) == 0

    # 2. Fetch comparison statistics
    response = client.get("/feedback/stats/compare")
    assert response.status_code == 200
    compare_data = response.json()
    assert len(compare_data["sources"]) == 0


def test_user_segment_filtering_uat(db, client):
    """UAT-03 & UAT-04: Verify that user_segment filters return correct records."""
    db.query(FeedbackItem).delete()
    db.commit()

    item = FeedbackItem(
        id="seg-1",
        source_type="app_review",
        platform="play_store",
        text="Premium user feedback",
        user_segment="premium_subscriber",
        raw_id="raw-s"
    )
    db.add(item)
    db.commit()

    response = client.get("/feedback?user_segment=premium_subscriber")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == "seg-1"


def test_source_platform_filtering_uat(db, client):
    """UAT-05 & UAT-06: Verify that Product Hunt and YouTube source filtering works correctly."""
    db.query(FeedbackItem).delete()
    db.commit()

    ph_item = FeedbackItem(
        id="ph-1",
        source_type="producthunt_post",
        platform="product_hunt",
        text="New Product Hunt release description",
        raw_id="raw-ph"
    )
    yt_item = FeedbackItem(
        id="yt-1",
        source_type="youtube_comment",
        platform="youtube",
        text="Video comment on Youtube",
        raw_id="raw-yt"
    )
    db.add_all([ph_item, yt_item])
    db.commit()

    # Filter Product Hunt
    response = client.get("/feedback?source_type=producthunt_post")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == "ph-1"

    # Filter YouTube
    response = client.get("/feedback?platform=youtube")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == "yt-1"


def test_drilldown_theme_evidence_uat(db, client):
    """UAT-07: Verify that the theme evidence endpoint matches quotes appropriately."""
    db.query(FeedbackItem).delete()
    db.commit()

    item = FeedbackItem(
        id="drill-1",
        source_type="youtube_comment",
        platform="youtube",
        text="I really need a lyrics feature in the desktop client.",
        topics='["lyrics_feature", "desktop_app"]',
        raw_id="raw-d",
        analyzed_at=datetime.now(),
        analysis_evidence='[{"quote": "lyrics feature", "topic": "lyrics_feature"}]'
    )
    db.add(item)
    db.commit()

    response = client.get("/insights/lyrics_feature/evidence")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["quote"] == "lyrics feature"
    assert data[0]["feedback_id"] == "drill-1"


def test_export_summary_and_feedback_uat(db, client):
    """UAT: Verify `/export/summary` and `/export/feedback` downloads in JSON/CSV formats."""
    db.query(FeedbackItem).delete()
    db.commit()

    item = FeedbackItem(
        id="exp-1",
        source_type="app_review",
        platform="play_store",
        text="Clean UI and fast player.",
        rating_or_score=5.0,
        raw_id="raw-exp-1",
        user_segment="premium_subscriber",
        issue_category="ui_ux_design",
        topics='["ui_ux_design"]',
        unmet_needs='["theme_engine"]',
        analyzed_at=datetime.now(),
        analysis_evidence='[{"quote": "Clean UI", "topic": "ui_ux_design"}]'
    )
    db.add(item)
    db.commit()

    # 1. Export summary (JSON)
    resp = client.get("/export/summary?format=json")
    assert resp.status_code == 200
    assert "application/json" in resp.headers["content-type"]
    assert "insights_summary.json" in resp.headers["content-disposition"]
    data = resp.json()
    assert data["total_analyzed"] == 1
    assert data["categories"]["ui_ux_design"] == 1

    # 2. Export summary (CSV)
    resp = client.get("/export/summary?format=csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "insights_summary.csv" in resp.headers["content-disposition"]
    content = resp.text
    assert "Metric Type,Name,Count" in content
    assert "Category,ui_ux_design,1" in content

    # 3. Export feedback (JSON, labeled_only=True)
    resp = client.get("/export/feedback?format=json&labeled_only=true")
    assert resp.status_code == 200
    assert "application/json" in resp.headers["content-type"]
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == "exp-1"
    assert data[0]["user_segment"] == "premium_subscriber"

    # 4. Export feedback (CSV, labeled_only=True)
    resp = client.get("/export/feedback?format=csv&labeled_only=true")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    content = resp.text
    assert "id,source_type,platform" in content
    assert "exp-1,app_review,play_store" in content


def test_export_empty_result_safety_uat(db, client):
    """UAT: Verify zero-result safety of `/export/summary` and `/export/feedback` downloads."""
    db.query(FeedbackItem).delete()
    db.commit()

    # 1. Summary empty (JSON)
    resp = client.get("/export/summary?format=json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_analyzed"] == 0
    assert len(data["categories"]) == 0

    # 2. Summary empty (CSV)
    resp = client.get("/export/summary?format=csv")
    assert resp.status_code == 200
    content = resp.text
    assert "Metric Type,Name,Count" in content

    # 3. Feedback empty (JSON)
    resp = client.get("/export/feedback?format=json")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 0

    # 4. Feedback empty (CSV)
    resp = client.get("/export/feedback?format=csv")
    assert resp.status_code == 200
    content = resp.text
    assert "id,source_type,platform" in content

