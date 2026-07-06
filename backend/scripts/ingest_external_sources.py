"""CLI script to ingest, normalize, and merge reviews from YouTube and Product Hunt.

This script runs external-source ingestion, merges the new reviews with the existing
spotify_reviews.csv, deduplicates them, and writes the updated CSV back to disk.
"""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Add backend directory to sys.path to allow module imports when run directly as a script
current_dir = Path(__file__).resolve().parent
backend_dir = current_dir.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.config import get_settings  # noqa: E402
from app.services.youtube_connector import fetch_youtube_reviews  # noqa: E402
from app.services.product_hunt_connector import fetch_product_hunt_reviews  # noqa: E402

CSV_HEADERS = [
    "source",
    "review_id",
    "user_name",
    "rating",
    "title",
    "review_text",
    "review_date",
    "spotify_version",
    "country",
]


def parse_date(date_str: str) -> datetime:
    """Helper to parse ISO-8601-like date strings for sorting and deduplication.

    Returns datetime.min if unparseable.
    """
    if not date_str or not date_str.strip():
        return datetime.min

    cleaned = date_str.strip()
    # Remove 'Z' offset if present for simplified parsing
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        # Try custom formats
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(cleaned, fmt)
            except ValueError:
                continue

    return datetime.min


def read_existing_csv(csv_path: Path) -> List[Dict[str, str]]:
    """Reads existing records from the target CSV file.

    If the file does not exist, creates it with proper headers and returns an empty list.
    """
    if not csv_path.exists():
        print(f"Target CSV file not found. Creating a new one at: {csv_path}")
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADERS)
        return []

    records: List[Dict[str, str]] = []
    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames:
                # Validate columns
                missing = set(CSV_HEADERS) - set(reader.fieldnames)
                if missing:
                    print(
                        f"Warning: Existing CSV missing expected headers: {missing}. Aligning schema."
                    )

            for row in reader:
                # Strip and clean row
                cleaned_row = {col: (row.get(col) or "").strip() for col in CSV_HEADERS}
                records.append(cleaned_row)
    except Exception as exc:
        print(f"Error reading existing CSV at {csv_path}: {exc}")
        print("Starting with empty records.")
    return records


def normalize_record(record: Dict[str, Any]) -> Dict[str, str]:
    """Ensures every row matches the required schema exactly.

    Strips whitespace and converts missing values to empty strings.
    """
    normalized = {}
    for col in CSV_HEADERS:
        val = record.get(col)
        if val is None:
            normalized[col] = ""
        else:
            normalized[col] = str(val).strip()
    return normalized


def merge_deduplicate_records(
    existing: List[Dict[str, str]], new: List[Dict[str, str]]
) -> List[Dict[str, str]]:
    """Combines records and deduplicates using key (source, review_id).

    If duplicate rows conflict, keeps the most complete (longest text) or latest one.
    """
    merged_dict: Dict[Tuple[str, str], Dict[str, str]] = {}

    # Populate with existing records
    for record in existing:
        source = record.get("source", "").strip()
        review_id = record.get("review_id", "").strip()

        if not review_id:
            continue  # Skip invalid rows

        key = (source, review_id)
        merged_dict[key] = record

    # Merge new records
    for record in new:
        source = record.get("source", "").strip()
        review_id = record.get("review_id", "").strip()

        if not review_id:
            continue  # Skip invalid rows

        key = (source, review_id)
        if key not in merged_dict:
            merged_dict[key] = record
        else:
            # Conflict resolution: keep the one with longer text or later date
            existing_rec = merged_dict[key]
            existing_text = existing_rec.get("review_text", "")
            new_text = record.get("review_text", "")

            existing_date = parse_date(existing_rec.get("review_date", ""))
            new_date = parse_date(record.get("review_date", ""))

            # Prefer the later date. If dates are unparseable/identical, prefer the longer text.
            if new_date > existing_date:
                merged_dict[key] = record
            elif new_date == existing_date:
                if len(new_text) > len(existing_text):
                    merged_dict[key] = record

    # Convert back to list
    merged_list = list(merged_dict.values())

    # Sort final records by review_date descending
    # To handle naive vs aware datetime comparison, we handle dates carefully
    # String comparison of ISO timestamps is also a reliable fallback for descending sorting.
    def sort_key(rec: Dict[str, str]) -> Tuple[datetime, str]:
        date_str = rec.get("review_date", "")
        dt = parse_date(date_str)
        # Ensure aware vs naive comparisons don't fail by returning a tuple with parsed dt and string date
        # If dt parsing returns datetime.min, fallback sorting will use the string representation.
        # Strip timezone offset from datetime for safe relative ordering if needed,
        # but in Python fromisoformat handles offsets. We make it naive to avoid TypeError if any are naive
        if dt != datetime.min and dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt, date_str

    merged_list.sort(key=sort_key, reverse=True)
    return merged_list


def write_csv(csv_path: Path, records: List[Dict[str, str]]) -> None:
    """Writes the full records list to the target CSV file using UTF-8."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(records)


def main() -> None:
    """CLI orchestrator main function."""
    parser = argparse.ArgumentParser(
        description="Ingest reviews/feedback from YouTube and Product Hunt and merge with local CSV."
    )
    parser.add_argument(
        "--youtube-only",
        action="store_true",
        help="Only run the YouTube comments connector",
    )
    parser.add_argument(
        "--product-hunt-only",
        action="store_true",
        help="Only run the Product Hunt discussions connector",
    )
    parser.add_argument(
        "--youtube-max-comments",
        type=int,
        default=100,
        help="Maximum comments to fetch per YouTube video",
    )
    parser.add_argument(
        "--youtube-max-videos",
        type=int,
        default=5,
        help="Maximum YouTube videos to fetch comments from",
    )
    parser.add_argument(
        "--product-hunt-max-records",
        type=int,
        default=100,
        help="Maximum Product Hunt records to fetch",
    )
    parser.add_argument(
        "--csv-path",
        type=str,
        default=None,
        help="Target CSV path (overrides config path)",
    )

    args = parser.parse_args()

    print("Step 1: Loading settings...")
    settings = get_settings()
    print(f"Settings loaded for: '{settings.app_name}'")

    # Determine targets
    csv_path_str = args.csv_path or settings.reviews_csv_path
    # Make sure path is absolute relative to REPO_ROOT if it's relative
    csv_path = Path(csv_path_str)
    if not csv_path.is_absolute():
        from app.config import REPO_ROOT

        csv_path = REPO_ROOT / csv_path

    run_youtube = not args.product_hunt_only
    run_product_hunt = not args.youtube_only

    new_records: List[Dict[str, str]] = []

    # 1. YouTube Ingestion
    if run_youtube:
        print("\nStep 2: Starting YouTube Ingestion...")
        api_key = settings.youtube_api_key
        if not api_key:
            print("Error: YOUTUBE_API_KEY is missing/empty.")
            if args.youtube_only:
                print("Exiting because YouTube-only run was requested.")
                sys.exit(1)
        else:
            print("YouTube API key validated. Starting fetch...")
            try:
                # Call connector
                yt_reviews = fetch_youtube_reviews(
                    api_key=api_key,
                    video_ids=None,  # Fallback to search
                    max_videos=args.youtube_max_videos,
                    max_comments=args.youtube_max_comments,
                )
                print(f"Successfully fetched {len(yt_reviews)} raw YouTube records.")

                # Normalize
                for rec in yt_reviews:
                    norm = normalize_record(rec)
                    if norm.get("review_id"):
                        new_records.append(norm)

            except Exception as exc:
                print(f"YouTube ingestion failed: {exc}")
                if args.youtube_only:
                    sys.exit(1)

    # 2. Product Hunt Ingestion
    if run_product_hunt:
        print("\nStep 3: Starting Product Hunt Ingestion...")
        token = settings.product_hunt_token
        if not token:
            print("Error: PRODUCT_HUNT_TOKEN is missing/empty.")
            if args.product_hunt_only:
                print("Exiting because Product-Hunt-only run was requested.")
                sys.exit(1)
        else:
            print("Product Hunt token validated. Starting fetch...")
            try:
                # Call connector
                ph_reviews = fetch_product_hunt_reviews(
                    token=token,
                    slugs=None,  # Use defaults
                    max_records=args.product_hunt_max_records,
                )
                print(f"Successfully fetched {len(ph_reviews)} raw Product Hunt records.")

                # Normalize
                for rec in ph_reviews:
                    norm = normalize_record(rec)
                    if norm.get("review_id"):
                        new_records.append(norm)

            except Exception as exc:
                print(f"Product Hunt ingestion failed: {exc}")
                if args.product_hunt_only:
                    sys.exit(1)

    print(f"\nFetched total of {len(new_records)} new normalized records.")

    # 3. Read existing CSV
    print(f"\nStep 4: Reading existing CSV at {csv_path}...")
    existing_records = read_existing_csv(csv_path)
    initial_count = len(existing_records)
    print(f"Existing CSV has {initial_count} rows.")

    # 4. Merge and Deduplicate
    print("Step 5: Merging and deduplicating records...")
    merged_records = merge_deduplicate_records(existing_records, new_records)
    final_count = len(merged_records)
    removed_duplicates = (initial_count + len(new_records)) - final_count
    print(f"Deduplication summary: removed {removed_duplicates} duplicate records.")
    print(f"Final row count to save: {final_count} rows.")

    # 5. Save back to disk
    print(f"Step 6: Writing updated CSV back to {csv_path}...")
    try:
        write_csv(csv_path, merged_records)
        print("Success! CSV file updated successfully.")
    except Exception as exc:
        print(f"Failed to write CSV: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
