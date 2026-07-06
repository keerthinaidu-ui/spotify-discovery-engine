from __future__ import annotations

import csv
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.raw_review import RawReview

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = {
    "source",
    "review_id",
    "user_name",
    "rating",
    "title",
    "review_text",
    "review_date",
    "spotify_version",
    "country",
}

BATCH_SIZE = 500


def normalize_platform(source: str) -> str:
    mapping = {"appstore": "app_store", "playstore": "play_store"}
    return mapping.get(source.strip().lower(), source.strip().lower())


def parse_review_date(value: str) -> datetime | None:
    if not value or not value.strip():
        return None

    cleaned = value.strip()
    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError:
        parsed = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(cleaned, fmt)
                break
            except ValueError:
                continue

    if parsed is None:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def parse_rating(value: str) -> float | None:
    if value is None or not str(value).strip():
        return None
    try:
        return float(value)
    except ValueError:
        return None


def check_and_truncate(val: str | None, max_len: int, table: str, column: str, row_id: str) -> str | None:
    if val is None:
        return None
    val_str = str(val)
    if len(val_str) > max_len:
        from app.services.etl_logger import tracker
        tracker.track_truncation(table, column, row_id, len(val_str), max_len)
        return val_str[:max_len]
    return val_str


def row_to_raw_review(row: dict[str, str]) -> RawReview | None:
    text_val = (row.get("review_text") or "").strip()
    if not text_val:
        text_val = (row.get("content") or "").strip()
    if not text_val:
        return None

    raw_review_id = (row.get("review_id") or "").strip()
    if not raw_review_id:
        raw_review_id = (row.get("reviewId") or "").strip()
    if not raw_review_id:
        return None

    # Track truncation for review_id if needed
    review_id = check_and_truncate(raw_review_id, 255, "raw_reviews", "review_id", raw_review_id)

    source_val = row.get("source") or ""
    if source_val:
        platform = normalize_platform(source_val)
    else:
        platform = "play_store"
    platform = check_and_truncate(platform, 64, "raw_reviews", "platform", review_id)

    rating_val = row.get("rating")
    if rating_val is None or str(rating_val).strip() == "":
        rating_val = row.get("score")
    rating = parse_rating(rating_val)

    author = (row.get("user_name") or "").strip()
    if not author:
        author = (row.get("userName") or "").strip()
    author = check_and_truncate(author, 256, "raw_reviews", "author", review_id)

    title = (row.get("title") or "").strip() or None
    title = check_and_truncate(title, 512, "raw_reviews", "title", review_id)

    date_val = row.get("review_date")
    if not date_val or not str(date_val).strip():
        date_val = row.get("at")
    review_date = parse_review_date(date_val)

    app_ver = (row.get("spotify_version") or "").strip()
    if not app_ver:
        app_ver = (row.get("app_version") or "").strip()
    if not app_ver:
        app_ver = (row.get("appVersion") or "").strip()
    app_ver = check_and_truncate(app_ver, 64, "raw_reviews", "app_version", review_id)

    country = (row.get("country") or "").strip() or None
    country = check_and_truncate(country, 8, "raw_reviews", "country", review_id)

    return RawReview(
        review_id=review_id,
        text=text_val,
        rating=rating,
        title=title,
        author=author,
        platform=platform,
        review_date=review_date,
        app_version=app_ver,
        country=country,
        url=None,
    )


def ingest_reviews_csv(db: Session, csv_path: Path) -> tuple[int, int, int]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Review CSV not found: {csv_path}")

    existing_keys = {
        (platform, review_id)
        for platform, review_id in db.query(RawReview.platform, RawReview.review_id).all()
    }

    rows_read = 0
    rows_inserted = 0
    rows_skipped = 0
    batch: list[RawReview] = []

    header_mapping = {
        "source": ["source", "store"],
        "review_id": ["review_id", "reviewid", "reviewId"],
        "user_name": ["username", "user_name", "userName"],
        "rating": ["rating", "score"],
        "title": ["title"],
        "review_text": ["review", "review_text", "content"],
        "review_date": ["review_date", "date", "at"],
        "spotify_version": ["spotify_version", "version", "app_version", "appVersion", "reviewcreatedversion"],
        "country": ["country"],
    }

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("CSV has no header row")

        # Resolve headers mapping
        resolved_headers = {}
        missing = []
        for req_col, alternatives in header_mapping.items():
            found = False
            for alt in alternatives:
                if alt in reader.fieldnames:
                    resolved_headers[req_col] = alt
                    found = True
                    break
            if not found:
                if req_col in ["title", "country", "source"]:
                    resolved_headers[req_col] = req_col
                else:
                    missing.append(req_col)

        if missing:
            raise ValueError(f"CSV missing required columns: {', '.join(sorted(missing))}")

        seen_5tuples = set()
        import uuid
        for row in reader:
            rows_read += 1

            # Map the row keys to standardized column names
            mapped_row = {}
            for target_col, source_col in resolved_headers.items():
                mapped_row[target_col] = row.get(source_col)
            for k, v in row.items():
                if k not in mapped_row:
                    mapped_row[k] = v

            # 5-field uniqueness check: username, text, date, source_file, store
            u_name = (mapped_row.get("user_name") or "").strip()
            r_text = (mapped_row.get("review_text") or "").strip()
            r_date = (mapped_row.get("review_date") or "").strip()
            s_file = (row.get("source_file") or "").strip()
            store_val = (mapped_row.get("source") or "").strip().lower()

            five_tuple = (u_name, r_text, r_date, s_file, store_val)

            if not r_text:
                rows_skipped += 1
                continue

            if five_tuple in seen_5tuples:
                rows_skipped += 1
                continue
            seen_5tuples.add(five_tuple)

            review = row_to_raw_review(mapped_row)
            if review is None:
                rows_skipped += 1
                continue

            key = (review.platform, review.review_id)
            if key in existing_keys:
                # Suffix key to avoid DB constraint failure since the 5-tuple is unique
                review.review_id = f"{review.review_id}_{uuid.uuid4().hex[:6]}"
                key = (review.platform, review.review_id)

            existing_keys.add(key)
            batch.append(review)
            if len(batch) >= BATCH_SIZE:
                inserted, skipped = _flush_batch(db, batch)
                rows_inserted += inserted
                rows_skipped += skipped
                batch = []

    if batch:
        inserted, skipped = _flush_batch(db, batch)
        rows_inserted += inserted
        rows_skipped += skipped

    logger.info(
        "CSV ingest complete: read=%s inserted=%s skipped=%s path=%s",
        rows_read,
        rows_inserted,
        rows_skipped,
        csv_path,
    )
    return rows_read, rows_inserted, rows_skipped


def _flush_batch(db: Session, batch: list[RawReview]) -> tuple[int, int]:
    db.add_all(batch)
    db.commit()
    return len(batch), 0
