from datetime import datetime

from app.models.feedback_item import FeedbackItem


def test_query_validation(client):
    # Test that rating cannot be combined with rating_min or rating_max
    response = client.get("/feedback?rating=5.0&rating_min=4.0")
    assert response.status_code == 400
    assert "Cannot specify 'rating' together with" in response.json()["detail"]

    response = client.get("/feedback?rating=5.0&rating_max=4.0")
    assert response.status_code == 400

    # Test invalid sorting params
    response = client.get("/feedback?sort_by=invalid")
    assert response.status_code == 400
    assert "Invalid sort_by parameter" in response.json()["detail"]

    response = client.get("/feedback?sort_order=invalid")
    assert response.status_code == 400
    assert "Invalid sort_order parameter" in response.json()["detail"]


def test_query_filtering_and_search(db, client):
    # Setup test data
    items = [
        FeedbackItem(
            id="item-1",
            source_type="app_review",
            platform="app_store",
            rating_or_score=5.0,
            title="Great App",
            text="I love Spotify",
            created_at=datetime(2026, 6, 1, 12, 0, 0),
            raw_id="raw-1",
        ),
        FeedbackItem(
            id="item-2",
            source_type="app_review",
            platform="play_store",
            rating_or_score=4.0,
            title="Good app",
            text="Spotify is nice but slow",
            created_at=datetime(2026, 6, 2, 12, 0, 0),
            raw_id="raw-2",
        ),
        FeedbackItem(
            id="item-3",
            source_type="app_review",
            platform="app_store",
            rating_or_score=3.0,
            title=None,
            text="It is okay.",
            created_at=datetime(2026, 6, 3, 12, 0, 0),
            raw_id="raw-3",
        ),
        FeedbackItem(
            id="item-4",
            source_type="app_review",
            platform="play_store",
            rating_or_score=2.0,
            title="Bad experience",
            text="Terrible search engine",
            created_at=datetime(2026, 6, 4, 12, 0, 0),
            raw_id="raw-4",
        ),
        FeedbackItem(
            id="item-5",
            source_type="app_review",
            platform="app_store",
            rating_or_score=1.0,
            title="Terrible",
            text="Hate this layout",
            created_at=datetime(2026, 6, 5, 12, 0, 0),
            raw_id="raw-5",
        ),
    ]
    db.add_all(items)
    db.commit()

    # 1. Platform filter
    response = client.get("/feedback?platform=play_store")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    ids = [item["id"] for item in data["items"]]
    assert "item-2" in ids
    assert "item-4" in ids

    # 2. Rating filter (exact match)
    response = client.get("/feedback?rating=3.0")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == "item-3"

    # 3. Rating range filter (min and max)
    response = client.get("/feedback?rating_min=3.0&rating_max=4.0")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    ids = [item["id"] for item in data["items"]]
    assert "item-2" in ids
    assert "item-3" in ids

    # 4. Date range filter
    response = client.get("/feedback?start_date=2026-06-02T00:00:00&end_date=2026-06-04T23:59:59")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    ids = [item["id"] for item in data["items"]]
    assert "item-2" in ids
    assert "item-3" in ids
    assert "item-4" in ids

    # 5. Case-insensitive text search (in text body)
    response = client.get("/feedback?q=spotiFY")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    ids = [item["id"] for item in data["items"]]
    assert "item-1" in ids
    assert "item-2" in ids

    # 6. Case-insensitive text search (in title)
    response = client.get("/feedback?q=terriBLE")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    ids = [item["id"] for item in data["items"]]
    assert "item-4" in ids  # title: "Bad experience", text: "Terrible search engine"
    assert "item-5" in ids  # title: "Terrible", text: "Hate this layout"

    # 7. Sorting by rating ASC
    response = client.get("/feedback?sort_by=rating&sort_order=asc")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 5
    assert data["items"][0]["id"] == "item-5"  # 1.0
    assert data["items"][4]["id"] == "item-1"  # 5.0

    # 8. Sorting by created_at DESC (default behavior)
    response = client.get("/feedback?sort_by=created_at&sort_order=desc")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 5
    assert data["items"][0]["id"] == "item-5"  # June 5
    assert data["items"][4]["id"] == "item-1"  # June 1


def test_query_phase3_features(db, client):
    # 1. Clean existing items in DB to avoid collisions or interference
    db.query(FeedbackItem).delete()
    db.commit()

    # 2. Setup test data with long IDs, null/set sentiments, various sources
    long_youtube_id = (
        "UgzD-V_V6T_B9z2w1Jt4AaABAg.9xOa-h-jV3s9xOa_oG4fAa_very_long_youtube_comment_id_"
        + "x" * 150
    )
    long_ph_id = "producthunt_comment_id_base64_hash_" + "y" * 150

    items = [
        FeedbackItem(
            id="item-ph-1",
            source_type="producthunt_post",
            platform="product_hunt",
            rating_or_score=None,
            title="Spotify Playlist Feature",
            text="They added a new playlist feature, it is awesome!",
            created_at=datetime(2026, 6, 10, 10, 0, 0),
            raw_id=long_ph_id,
            sentiment="positive",
        ),
        FeedbackItem(
            id="item-yt-1",
            source_type="youtube_comment",
            platform="youtube",
            rating_or_score=4.0,
            title=None,
            text="Pretty neat but could be faster.",
            created_at=datetime(2026, 6, 11, 15, 30, 0),
            raw_id=long_youtube_id,
            sentiment="neutral",
        ),
        FeedbackItem(
            id="item-csv-1",
            source_type="app_review",
            platform="play_store",
            rating_or_score=1.0,
            title="Terrible update",
            text="Crash on start! Please fix.",
            created_at=datetime(2026, 6, 12, 9, 0, 0),
            raw_id="csv-id-101",
            sentiment="negative",
        ),
        FeedbackItem(
            id="item-csv-2",
            source_type="app_review",
            platform="app_store",
            rating_or_score=5.0,
            title="Love it",
            text="Works perfectly for me.",
            created_at=datetime(2026, 6, 12, 18, 0, 0),
            raw_id="csv-id-102",
            sentiment=None,  # Null sentiment
        ),
    ]
    db.add_all(items)
    db.commit()

    # --- Test Long IDs ---
    retrieved_ph = db.query(FeedbackItem).filter(FeedbackItem.id == "item-ph-1").first()
    assert retrieved_ph.raw_id == long_ph_id
    assert len(retrieved_ph.raw_id) > 180

    retrieved_yt = db.query(FeedbackItem).filter(FeedbackItem.id == "item-yt-1").first()
    assert retrieved_yt.raw_id == long_youtube_id
    assert len(retrieved_yt.raw_id) > 200

    # Test via API
    response = client.get("/feedback")
    assert response.status_code == 200
    res_items = response.json()["items"]
    assert len(res_items) == 4
    api_yt = next(item for item in res_items if item["id"] == "item-yt-1")
    assert api_yt["raw_id"] == long_youtube_id

    # --- Test Pagination with page / per_page ---
    response = client.get("/feedback?page=1&per_page=2")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 4
    assert len(data["items"]) == 2
    assert data["items"][0]["id"] == "item-csv-2"
    assert data["items"][1]["id"] == "item-csv-1"

    response = client.get("/feedback?page=2&per_page=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["items"][0]["id"] == "item-yt-1"
    assert data["items"][1]["id"] == "item-ph-1"

    # --- Test Filters Combos ---
    response = client.get("/feedback?source_type=app_review&platform=app_store")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == "item-csv-2"

    response = client.get("/feedback?sentiment=negative")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == "item-csv-1"

    response = client.get("/feedback?sentiment=invalid")
    assert response.status_code == 400

    response = client.get("/feedback?from=2026-06-11T00:00:00&to=2026-06-12T12:00:00")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    ids = [item["id"] for item in data["items"]]
    assert "item-yt-1" in ids
    assert "item-csv-1" in ids

    response = client.get("/feedback?q=spotify&sentiment=positive")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == "item-ph-1"

    # --- Test Stats Overview API ---
    response = client.get("/feedback/stats/overview")
    assert response.status_code == 200
    stats = response.json()
    assert stats["total_records"] == 4
    assert stats["platform_counts"]["youtube"] == 1
    assert stats["platform_counts"]["product_hunt"] == 1
    assert stats["platform_counts"]["play_store"] == 1
    assert stats["platform_counts"]["app_store"] == 1
    assert stats["source_type_counts"]["youtube_comment"] == 1
    assert stats["source_type_counts"]["producthunt_post"] == 1
    assert stats["source_type_counts"]["app_review"] == 2

    buckets = stats["date_buckets"]
    assert len(buckets) == 3
    assert buckets[0]["date"] == "2026-06-10"
    assert buckets[0]["count"] == 1
    assert buckets[1]["date"] == "2026-06-11"
    assert buckets[1]["count"] == 1
    assert buckets[2]["date"] == "2026-06-12"
    assert buckets[2]["count"] == 2

    response = client.get("/feedback/stats/overview?from=2026-06-11T00:00:00")
    assert response.status_code == 200
    stats_filtered = response.json()
    assert stats_filtered["total_records"] == 3
    assert stats_filtered["platform_counts"].get("product_hunt", 0) == 0

    # --- Test Stats Compare API ---
    response = client.get("/feedback/stats/compare")
    assert response.status_code == 200
    compare = response.json()
    sources = compare["sources"]
    
    assert sources["youtube_comment"]["count"] == 1
    assert sources["youtube_comment"]["avg_rating"] == 4.0

    assert sources["app_review"]["count"] == 2
    assert sources["app_review"]["avg_rating"] == 3.0

    assert sources["producthunt_post"]["count"] == 1
    assert sources["producthunt_post"]["avg_rating"] is None

    # --- Test Sentiment Fallback ---
    # item-csv-2 has sentiment=None, rating_or_score=5.0 (positive fallback)
    # item-ph-1 has sentiment="positive", rating_or_score=None (explicit)
    # item-yt-1 has sentiment="neutral", rating_or_score=4.0 (explicit)
    # item-csv-1 has sentiment="negative", rating_or_score=1.0 (explicit)
    response = client.get("/feedback?sentiment=positive")
    assert response.status_code == 200
    data = response.json()
    # Should match item-ph-1 (explicit) and item-csv-2 (fallback from rating 5.0)
    assert data["total"] == 2
    ids = [item["id"] for item in data["items"]]
    assert "item-ph-1" in ids
    assert "item-csv-2" in ids
    
    # Assert serialization resolved sentiment correctly
    item_csv_2_res = next(item for item in data["items"] if item["id"] == "item-csv-2")
    assert item_csv_2_res["sentiment"] == "positive"


def test_query_app_version_filter(db, client):
    # Setup test data with app versions
    items = [
        FeedbackItem(
            id="item-v1",
            source_type="app_review",
            platform="app_store",
            rating_or_score=5.0,
            text="Version 1",
            app_version="1.0.0",
            raw_id="raw-v1",
        ),
        FeedbackItem(
            id="item-v2",
            source_type="app_review",
            platform="play_store",
            rating_or_score=4.0,
            text="Version 2",
            app_version="2.0.0",
            raw_id="raw-v2",
        ),
        FeedbackItem(
            id="item-v3",
            source_type="app_review",
            platform="app_store",
            rating_or_score=3.0,
            text="Version 2 duplicate",
            app_version="2.0.0",
            raw_id="raw-v3",
        ),
    ]
    db.add_all(items)
    db.commit()

    # Filter by app_version=2.0.0
    response = client.get("/feedback?app_version=2.0.0")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    ids = [item["id"] for item in data["items"]]
    assert "item-v2" in ids
    assert "item-v3" in ids

    # Filter by app_version=1.0.0
    response = client.get("/feedback?app_version=1.0.0")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == "item-v1"


def test_insights_rating_and_app_version_filtering(db, client):
    # Setup completed feedback items for insights
    items = [
        FeedbackItem(
            id="insight-item-1",
            source_type="app_review",
            platform="app_store",
            rating_or_score=5.0,
            text="Love this!",
            app_version="9.1.0",
            raw_id="raw-i1",
            analysis_status="complete",
            issue_category="Stability",
        ),
        FeedbackItem(
            id="insight-item-2",
            source_type="app_review",
            platform="app_store",
            rating_or_score=1.0,
            text="Crashes constantly",
            app_version="9.2.0",
            raw_id="raw-i2",
            analysis_status="complete",
            issue_category="Stability",
        ),
        FeedbackItem(
            id="insight-item-3",
            source_type="app_review",
            platform="play_store",
            rating_or_score=1.0,
            text="UX is bad",
            app_version="9.1.0",
            raw_id="raw-i3",
            analysis_status="complete",
            issue_category="Navigation & UX",
        ),
    ]
    db.add_all(items)
    db.commit()

    # 1. Test /insights/summary filter by rating
    response = client.get("/insights/summary?rating=1.0")
    assert response.status_code == 200
    data = response.json()
    assert data["total_analyzed"] == 2
    # Ensure categories count matches: Stability=1, Navigation & UX=1
    cats = {c["name"]: c["count"] for c in data["top_categories"]}
    assert cats.get("Stability") == 1
    assert cats.get("Navigation & UX") == 1

    # 2. Test /insights/summary filter by app_version
    response = client.get("/insights/summary?app_version=9.1.0")
    assert response.status_code == 200
    data = response.json()
    assert data["total_analyzed"] == 2
    cats = {c["name"]: c["count"] for c in data["top_categories"]}
    assert cats.get("Stability") == 1
    assert cats.get("Navigation & UX") == 1

    # 3. Test /insights/summary filter by rating and app_version combo
    response = client.get("/insights/summary?rating=5.0&app_version=9.1.0")
    assert response.status_code == 200
    data = response.json()
    assert data["total_analyzed"] == 1
    cats = {c["name"]: c["count"] for c in data["top_categories"]}
    assert cats.get("Stability") == 1
    assert cats.get("Navigation & UX") is None

    # 4. Test /insights/compare filter by rating
    response = client.get("/insights/compare?compare_by=platform&rating=1.0")
    assert response.status_code == 200
    data = response.json()
    comparison = data["comparison"]
    assert comparison["app_store"]["Stability"] == 1
    assert comparison["play_store"]["Navigation & UX"] == 1
    assert "app_store" in comparison
    assert "play_store" in comparison

    # 5. Test /insights/compare filter by app_version
    response = client.get("/insights/compare?compare_by=platform&app_version=9.2.0")
    assert response.status_code == 200
    data = response.json()
    comparison = data["comparison"]
    assert comparison["app_store"]["Stability"] == 1
    assert "play_store" not in comparison


def test_insights_issue_category_and_google_play_mapping(db, client):
    # Clean database before testing
    db.query(FeedbackItem).delete()
    db.commit()

    items = [
        FeedbackItem(
            id="test-cat-1",
            source_type="app_review",
            platform="play_store",
            rating_or_score=5.0,
            text="Playback is perfect",
            app_version="9.1.0",
            raw_id="raw-c1",
            analysis_status="complete",
            issue_category="Playback Reliability",
        ),
        FeedbackItem(
            id="test-cat-2",
            source_type="app_review",
            platform="app_store",
            rating_or_score=1.0,
            text="Buffering constantly",
            app_version="9.1.0",
            raw_id="raw-c2",
            analysis_status="complete",
            issue_category="Playback Reliability",
        ),
        FeedbackItem(
            id="test-cat-3",
            source_type="app_review",
            platform="play_store",
            rating_or_score=2.0,
            text="App crashed",
            app_version="9.1.0",
            raw_id="raw-c3",
            analysis_status="complete",
            issue_category="Stability",
        ),
    ]
    db.add_all(items)
    db.commit()

    # 1. Test /insights/summary filter by issue_category (e.g. Playback Reliability)
    response = client.get("/insights/summary?issue_category=Playback%20Reliability")
    assert response.status_code == 200
    data = response.json()
    assert data["total_analyzed"] == 2
    cats = {c["name"]: c["count"] for c in data["top_categories"]}
    assert cats.get("Playback Reliability") == 2
    assert cats.get("Stability") is None

    # 2. Test /insights/compare filter by issue_category
    response = client.get("/insights/compare?compare_by=platform&issue_category=Playback%20Reliability")
    assert response.status_code == 200
    data = response.json()
    comparison = data["comparison"]
    assert comparison["play_store"]["Playback Reliability"] == 1
    assert comparison["app_store"]["Playback Reliability"] == 1
    assert "Stability" not in comparison["play_store"]

    # 3. Test /insights/summary platform parameter mapping of google_play -> play_store
    response = client.get("/insights/summary?platform=google_play")
    assert response.status_code == 200
    data = response.json()
    assert data["total_analyzed"] == 2
    cats = {c["name"]: c["count"] for c in data["top_categories"]}
    assert cats.get("Playback Reliability") == 1
    assert cats.get("Stability") == 1

    # 4. Test /insights/compare platform parameter mapping of google_play -> play_store
    response = client.get("/insights/compare?compare_by=platform&platform=google_play")
    assert response.status_code == 200
    data = response.json()
    comparison = data["comparison"]
    assert "play_store" in comparison
    assert comparison["play_store"]["Playback Reliability"] == 1
    assert comparison["play_store"]["Stability"] == 1
    assert "app_store" not in comparison


