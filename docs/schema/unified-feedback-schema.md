# Database Schema (Phase 0)

Phase 0 creates empty tables. This document is the field contract for later ingestion, normalization, and analysis phases.

## `raw_reviews` (Phase 1)

Ingested rows from the merged App Store / Play Store CSV.

| Field | Type | Purpose |
|-------|------|---------|
| `id` | UUID string (36) | Primary key |
| `review_id` | string (64) | External review id from CSV (unique per platform) |
| `text` | text | Review body |
| `rating` | float, optional | Star rating |
| `title` | string (512), optional | Review title |
| `author` | string (256), optional | Reviewer name |
| `platform` | string (64), optional | `app_store` or `play_store` |
| `review_date` | datetime (TZ), optional | Original review date |
| `app_version` | string (64), optional | App version at review time |
| `country` | string (8), optional | Country code from CSV |
| `url` | string (1024), optional | Store review URL |
| `ingested_at` | datetime (TZ) | When the row was ingested |

## `feedback_items` (Phase 2)

Unified schema merging direct and secondary feedback data for analysis.

| Field | Type | Purpose |
|-------|------|---------|
| `id` | UUID string (36) | Primary key |
| `source_type` | string (32) | `app_review`, `producthunt_post`, `producthunt_comment`, `youtube_video`, `youtube_comment` |
| `platform` | string (32) | `app_store`, `play_store`, `product_hunt`, `youtube` |
| `text` | text | Primary feedback body |
| `title` | string (512), optional | Review or post title |
| `rating_or_score` | float, optional | Star rating or score |
| `author` | string (256), optional | Username or reviewer name |
| `created_at` | datetime (TZ), optional | Original feedback date |
| `app_version` | string (64), optional | App version (reviews only) |
| `url` | string (1024), optional | Source context URL |
| `raw_table` | string (32), optional | `raw_reviews`, `raw_product_hunt_posts`, `raw_product_hunt_comments`, etc. |
| `raw_id` | UUID string (36), optional | Link to raw ingestion row |
| `sentiment` | string (16), optional | Baseline sentiment (Phase 3) |
| `normalized_at` | datetime (TZ) | When normalized |

### Source mapping (Phase 2)

| Unified field | App / Play Store review | Secondary sources (PH/YT) |
|---------------|-------------------------|---------------------------|
| `source_type` | `app_review` | `producthunt_post`, `producthunt_comment`, `youtube_video`, `youtube_comment` |
| `platform` | `app_store` or `play_store` | `product_hunt` or `youtube` |
| `text` | review text | text content or description |
| `title` | review title | post/video title |
| `rating_or_score` | star rating | null |
| `author` | reviewer name | username |
| `created_at` | review date | posted_at |
| `app_version` | app version | null |
| `url` | store URL | context URL |
| `raw_table` | `raw_reviews` | raw source table name |
| `raw_id` | `raw_reviews.id` | raw source table id |

## `analysis_results` (Phase 4)

LLM and derived analysis outputs linked to normalized feedback.

| Field | Type | Purpose |
|-------|------|---------|
| `id` | UUID string (36) | Primary key |
| `feedback_item_id` | UUID string (36), optional | FK to `feedback_items.id` |
| `result_type` | string (64) | e.g. `theme`, `complaint`, `segment`, `unmet_need`, `summary` |
| `label` | string (256), optional | Short classification label |
| `payload_json` | text, optional | JSON blob for flexible LLM output |
| `model` | string (128), optional | Model used for analysis |
| `analyzed_at` | datetime (TZ) | When analysis was run |

## Phase ownership

| Table | Populated in |
|-------|----------------|
| `raw_reviews` | Phase 1 |
| `feedback_items` | Phase 2 |
| `analysis_results` | Phase 4 |
