from datetime import datetime, timezone
from unittest.mock import patch

from app.models.raw_product_hunt import RawProductHuntPost, RawProductHuntComment
from app.models.raw_youtube import RawYouTubeVideo, RawYouTubeComment
from app.models.ingestion_run import IngestionRun


def test_ingestion_env_validation(client):
    # If API keys are missing in config settings, ingestion should raise 400
    with patch("app.services.ingestion_service.validate_ingestion_env") as mock_validate:
        mock_validate.side_effect = ValueError("Missing required keys")

        response = client.post("/ingestion/product_hunt")
        assert response.status_code == 400
        assert "Missing required keys" in response.json()["detail"]

        response = client.post("/ingestion/youtube")
        assert response.status_code == 400
        assert "Missing required keys" in response.json()["detail"]


@patch("app.services.product_hunt_ingestion.ProductHuntClient.fetch_spotify_data")
def test_product_hunt_ingestion_flow(mock_fetch, db, client):
    # Mock GraphQL payload
    mock_fetch.return_value = {
        "data": {
            "post": {
                "id": "ph-post-100",
                "name": "Spotify Premium Duo",
                "tagline": "A new plan for two people",
                "description": "Two premium accounts for one discount price.",
                "votesCount": 150,
                "url": "https://www.producthunt.com/posts/spotify-premium-duo",
                "createdAt": "2026-06-25T12:00:00Z",
                "user": {"name": "PH Curator A"},
                "comments": {
                    "edges": [
                        {
                            "node": {
                                "id": "ph-comment-500",
                                "body": "This is great value!",
                                "votesCount": 5,
                                "createdAt": "2026-06-25T12:30:00Z",
                                "user": {"name": "PH User B"},
                            }
                        }
                    ]
                },
            }
        }
    }

    # Override validate_ingestion_env so we don't need real keys
    with patch("app.services.ingestion_service.validate_ingestion_env") as _:
        # Trigger Ingestion
        response = client.post("/ingestion/product_hunt?slug=spotify")
        assert response.status_code == 200
        data = response.json()
        assert data["run"]["source"] == "product_hunt"
        assert data["run"]["status"] == "success"
        assert data["run"]["rows_read"] == 2
        assert data["run"]["rows_inserted"] == 2

        # Verify DB Post
        post = db.query(RawProductHuntPost).filter_by(ph_post_id="ph-post-100").first()
        assert post is not None
        assert post.title == "Spotify Premium Duo"
        assert "A new plan for two people" in post.text
        assert post.votes_count == 150
        assert post.author == "PH Curator A"

        # Verify DB Comment
        comment = db.query(RawProductHuntComment).filter_by(ph_comment_id="ph-comment-500").first()
        assert comment is not None
        assert comment.text == "This is great value!"
        assert comment.author == "PH User B"

        # Verify Idempotency on rerun
        response_again = client.post("/ingestion/product_hunt?slug=spotify")
        assert response_again.status_code == 200
        data_again = response_again.json()
        assert data_again["run"]["rows_read"] == 2
        assert data_again["run"]["rows_inserted"] == 0
        assert data_again["run"]["rows_skipped"] == 2


@patch("app.services.youtube_ingestion.YouTubeClient.search_videos")
@patch("app.services.youtube_ingestion.YouTubeClient.fetch_video_details")
@patch("app.services.youtube_ingestion.YouTubeClient.fetch_video_comments")
def test_youtube_ingestion_flow(mock_comments, mock_details, mock_search, db, client):
    # Mock Search items
    mock_search.return_value = [
        {"id": {"videoId": "yt-video-123"}, "snippet": {"title": "Spotify Search Video"}}
    ]
    # Mock Video Details
    mock_details.return_value = [
        {
            "id": "yt-video-123",
            "snippet": {
                "title": "Spotify Recommendations Explained",
                "description": "How the Discover Weekly algorithm works.",
                "publishedAt": "2026-06-25T14:00:00Z",
                "channelTitle": "Tech Insights Channel",
                "channelId": "chan-xyz-987",
            },
            "statistics": {
                "viewCount": "50000",
                "likeCount": "2500",
                "commentCount": "45",
            },
        }
    ]
    # Mock Comment threads
    mock_comments.return_value = [
        {
            "id": "yt-thread-999",
            "snippet": {
                "topLevelComment": {
                    "id": "yt-comment-888",
                    "snippet": {
                        "textOriginal": "Amazing explanation of discover weekly!",
                        "authorDisplayName": "Listener Bob",
                        "likeCount": 12,
                        "publishedAt": "2026-06-25T14:30:00Z",
                    },
                }
            },
        }
    ]

    with patch("app.services.ingestion_service.validate_ingestion_env") as _:
        # Trigger Ingestion
        response = client.post("/ingestion/youtube?q=spotify")
        assert response.status_code == 200
        data = response.json()
        assert data["run"]["source"] == "youtube"
        assert data["run"]["status"] == "success"
        assert data["run"]["rows_read"] == 2
        assert data["run"]["rows_inserted"] == 2

        # Verify DB Video
        video = db.query(RawYouTubeVideo).filter_by(video_id="yt-video-123").first()
        assert video is not None
        assert video.title == "Spotify Recommendations Explained"
        assert video.view_count == 50000
        assert video.like_count == 2500
        assert video.channel_id == "chan-xyz-987"
        assert video.author == "Tech Insights Channel"

        # Verify DB Comment
        comment = db.query(RawYouTubeComment).filter_by(comment_id="yt-comment-888").first()
        assert comment is not None
        assert comment.text == "Amazing explanation of discover weekly!"
        assert comment.author == "Listener Bob"
        assert comment.like_count == 12

        # Verify Idempotency on rerun
        response_again = client.post("/ingestion/youtube?q=spotify")
        assert response_again.status_code == 200
        data_again = response_again.json()
        assert data_again["run"]["rows_read"] == 2
        assert data_again["run"]["rows_inserted"] == 0
        assert data_again["run"]["rows_skipped"] == 2


def test_ingestion_status_endpoint(db, client):
    # Seed ingestion runs
    run_csv = IngestionRun(
        id="run-1",
        source="csv_reviews",
        status="success",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        rows_read=100,
        rows_inserted=100,
        rows_skipped=0,
    )
    run_ph = IngestionRun(
        id="run-2",
        source="product_hunt",
        status="success",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        rows_read=10,
        rows_inserted=10,
        rows_skipped=0,
    )
    run_yt = IngestionRun(
        id="run-3",
        source="youtube",
        status="failed",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        rows_read=0,
        rows_inserted=0,
        rows_skipped=0,
        error_message="API quota limit",
    )
    db.add_all([run_csv, run_ph, run_yt])
    db.commit()

    response = client.get("/ingestion/status")
    assert response.status_code == 200
    data = response.json()

    assert "csv_reviews" in data
    assert "product_hunt" in data
    assert "youtube" in data

    assert data["csv_reviews"]["last_run"]["id"] == "run-1"
    assert data["product_hunt"]["last_run"]["id"] == "run-2"
    assert data["youtube"]["last_run"]["id"] == "run-3"
    assert data["youtube"]["last_run"]["error_message"] == "API quota limit"


def test_raw_previews_endpoints(db, client):
    # Seed raw tables
    post = RawProductHuntPost(
        id="preview-post-uuid",
        ph_post_id="ph-preview-post",
        slug="spotify",
        title="Spotify Preview",
        text="A preview post.",
        votes_count=10,
        author="Preview User",
        url="https://preview.com",
        posted_at=datetime.now(timezone.utc),
        raw_payload="{}",
    )
    video = RawYouTubeVideo(
        id="preview-video-uuid",
        video_id="yt-preview-video",
        search_query="spotify",
        title="Spotify Preview Video",
        description="A preview video description.",
        view_count=100,
        like_count=10,
        comment_count=5,
        author="Preview Channel",
        channel_id="chan-preview",
        url="https://youtube.com/preview",
        posted_at=datetime.now(timezone.utc),
        raw_payload="{}",
    )
    db.add_all([post, video])
    db.commit()

    # Test Product Hunt Preview
    response = client.get("/raw/product_hunt?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["ph_post_id"] == "ph-preview-post"

    # Test YouTube Preview
    response = client.get("/raw/youtube?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["video_id"] == "yt-preview-video"
