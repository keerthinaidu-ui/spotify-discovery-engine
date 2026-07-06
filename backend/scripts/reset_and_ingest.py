import os
import sys
import json
import logging
import time
import sqlite3

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("reset_and_ingest")

# Add backend directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.config import get_settings
from app.database import SessionLocal
from app.services.csv_ingestion import ingest_reviews_csv
from app.services.normalization_service import run_normalization
from scripts.backfill_taxonomy import classify_review

def main():
    settings = get_settings()
    db_file = os.path.abspath(os.path.join(backend_dir, "..", "data", "spotify_review_engine.db"))

    logger.info(f"Resetting database tables at: {db_file}")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    tables_to_clear = [
        "raw_reviews",
        "feedback_items",
        "feedback_embeddings",
        "analysis_runs",
        "ingestion_runs",
        "analysis_results"
    ]

    for table in tables_to_clear:
        try:
            cursor.execute(f"DELETE FROM {table}")
            logger.info(f"Cleared table '{table}'.")
        except sqlite3.OperationalError as e:
            logger.warning(f"Could not clear table '{table}': {e}")
            
    conn.commit()
    conn.close()

    # 1. Ingest reviews from CSV
    logger.info("Starting ingestion of updated spotify_reviews.csv...")
    db = SessionLocal()
    try:
        csv_path = settings.reviews_csv_absolute
        rows_read, rows_inserted, rows_skipped = ingest_reviews_csv(db, csv_path)
        logger.info(f"CSV Ingestion complete: read={rows_read}, inserted={rows_inserted}, skipped={rows_skipped}")

        # 2. Run normalization
        logger.info("Running normalization service...")
        run_normalization(db)
        logger.info("Normalization complete.")

    finally:
        db.close()

    # 3. Classify all feedback items using new taxonomy
    logger.info("Re-connecting to database to run taxonomy classification on feedback_items...")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    cursor.execute("SELECT id, text, title, rating_or_score FROM feedback_items")
    rows = cursor.fetchall()
    total_records = len(rows)
    logger.info(f"Fetched {total_records} feedback items for classification.")

    batch_updates = []
    primary_distribution = {}
    secondary_distribution = {}
    sentiment_distribution = {}

    start_time = time.time()
    for idx, (item_id, text, title, rating) in enumerate(rows):
        theme, tags, sentiment = classify_review(text, title, rating)
        tags_str = json.dumps(tags)
        
        batch_updates.append((theme, tags_str, "2.0.0", "rule_backfill", 0.90, sentiment, theme, "complete", item_id))
        
        primary_distribution[theme] = primary_distribution.get(theme, 0) + 1
        sentiment_distribution[sentiment] = sentiment_distribution.get(sentiment, 0) + 1
        for tag in tags:
            secondary_distribution[tag] = secondary_distribution.get(tag, 0) + 1

        if len(batch_updates) >= 1000:
            cursor.executemany(
                """UPDATE feedback_items 
                   SET primary_theme = ?, 
                       secondary_tags = ?, 
                       taxonomy_version = ?, 
                       classification_source = ?, 
                       classification_confidence = ?, 
                       sentiment = ?,
                       issue_category = ?,
                       analysis_status = ?
                   WHERE id = ?""", 
                batch_updates
            )
            conn.commit()
            batch_updates = []

    if batch_updates:
        cursor.executemany(
            """UPDATE feedback_items 
               SET primary_theme = ?, 
                   secondary_tags = ?, 
                   taxonomy_version = ?, 
                   classification_source = ?, 
                   classification_confidence = ?, 
                   sentiment = ?,
                   issue_category = ?,
                   analysis_status = ?
               WHERE id = ?""", 
            batch_updates
        )
        conn.commit()

    duration = time.time() - start_time
    logger.info("=========================================")
    logger.info("       RESET & INGEST COMPLETION REPORT  ")
    logger.info("=========================================")
    logger.info(f"Total reviews in database: {total_records}")
    logger.info(f"Total classified:          {total_records}")
    logger.info(f"Total execution time:      {duration:.2f} seconds")
    logger.info(f"Primary Theme Distribution: {json.dumps(primary_distribution, indent=2)}")
    logger.info(f"Secondary Tag Distribution: {json.dumps(secondary_distribution, indent=2)}")
    logger.info(f"Sentiment Distribution:    {json.dumps(sentiment_distribution, indent=2)}")
    logger.info("=========================================")
    
    conn.close()

if __name__ == "__main__":
    main()
