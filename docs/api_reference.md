# API Reference Guide

This document lists all the FastAPI backend endpoints available in the Spotify Review Discovery Engine.

---

## 1. Health & Status

### `GET /health`
* **Purpose**: Verify backend service and database connectivity.
* **Response (JSON)**:
  ```json
  {
    "status": "ok",
    "app_name": "Spotify Review Discovery Engine",
    "environment": "development",
    "database": "connected",
    "version": "0.1.0"
  }
  ```

---

## 2. Ingestion Routes

### `POST /ingestion/reviews`
* **Purpose**: Ingest Play Store and App Store reviews from the local CSV file.
* **Response**: Details of processed, inserted, and skipped rows.

### `POST /ingestion/product_hunt`
* **Purpose**: Trigger Product Hunt API ingestion. Supports optional `slug` override.
* **Query Parameters**: `slug` (optional, default: `spotify`).

### `POST /ingestion/youtube`
* **Purpose**: Trigger YouTube search and comment ingestion. Supports optional query override.
* **Query Parameters**: `q` (optional).

### `GET /ingestion/status`
* **Purpose**: Retrieve ingestion history, total records, and details of last successful runs.

---

## 3. Raw Data Previews

### `GET /raw/reviews`
### `GET /raw/product_hunt/posts`
### `GET /raw/product_hunt/comments`
### `GET /raw/youtube/videos`
### `GET /raw/youtube/comments`
* **Purpose**: Preview cached raw ingestion tables.
* **Parameters**: `limit` (default: 10), `offset` (default: 0).

---

## 4. Unified Feedback & Normalization

### `POST /feedback/normalize`
* **Purpose**: Process raw records into target `feedback_items` database.
* **Response (JSON)**:
  ```json
  {
    "status": "success",
    "processed": 113,
    "inserted": 113,
    "skipped": 0,
    "dropped": 0,
    "failed": 0
  }
  ```

### `GET /feedback`
* **Purpose**: Query normalized and categorized feedback items.
* **Query Parameters**:
  * `limit` / `per_page`: Pagination limit (default: 10).
  * `offset` / `page`: Pagination offset/page number.
  * `platform`: Filter by platform (`app_store`, `play_store`, `product_hunt`, `youtube`).
  * `source_type`: Filter by source type (`app_review`, `producthunt_comment`, etc.).
  * `sentiment`: Filter by sentiment (`positive`, `neutral`, `negative`, `unknown`).
  * `rating`, `rating_min`, `rating_max`: Filter rating ranges.
  * `from_date`, `to_date`: ISO-8601 timestamps for date range bounds.
  * `q`: Text search query.
  * `user_segment`: Filter by segment.
  * `sort_by`: Sort field (`created_at`, `rating`, `id`).
  * `sort_order`: Sort order (`asc`, `desc`).

### `GET /feedback/stats/overview`
* **Purpose**: Return total records, platform distributions, source type counts, and date-bucket aggregates for charts.

### `GET /feedback/stats/compare`
* **Purpose**: Return cross-source metrics (counts and average ratings) grouped by `source_type`.

---

## 5. AI Analysis Engine

### `POST /analysis/run`
* **Purpose**: Trigger a background AI analysis batch job on unanalyzed feedback items.
* **Query Parameters**: `limit` (default: 10).
* **Response**:
  ```json
  {
    "run_id": "a67666a3-35bc-48ac-9905-dd691942950a",
    "status": "running"
  }
  ```

### `GET /analysis/status`
* **Purpose**: Check status and metrics of a running or completed analysis job.
* **Query Parameters**: `run_id` (required).

---

## 6. Insights & Themes

### `GET /insights/summary`
* **Purpose**: Surface top categories, topics, segments, and unmet needs aggregated across analyzed items.

### `GET /insights/compare`
* **Purpose**: Return category distributions grouped by `source_type` or `platform`.
* **Query Parameters**: `compare_by` (`source_type` or `platform`).

### `GET /insights/{theme}/evidence`
* **Purpose**: Drill down and retrieve highlighted quotes and feedback details for a specific theme or unmet need.

---

## 7. Export Endpoints

### `GET /export/summary`
* **Purpose**: Download insights summary metrics.
* **Query Parameters**: `format` (`json` or `csv`).

### `GET /export/feedback`
* **Purpose**: Download feedback records.
* **Query Parameters**:
  * `format`: Export format (`csv` or `json`).
  * `labeled_only`: If `true`, exports only AI-analyzed items.
