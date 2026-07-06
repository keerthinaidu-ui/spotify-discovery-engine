import logging
import os
import sys
import time

# Ensure backend directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SessionLocal, engine
from app.services.normalization_service import run_normalization
from scripts.backfill_taxonomy import run_backfill
from app.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("process_all_feedback")

def main():
    settings = get_settings()
    db_path = settings.database_url.replace("sqlite:///", "")
    if not os.path.isabs(db_path):
        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", db_path))

    logger.info("=== STEP 1: RUNNING DATA NORMALIZATION ===")
    db = SessionLocal()
    try:
        counts = run_normalization(db)
        logger.info(f"Normalization completed: {counts}")
    except Exception as e:
        logger.exception(f"Normalization failed: {e}")
        sys.exit(1)
    finally:
        db.close()

    logger.info("=== STEP 2: RUNNING ISSUE CATEGORY TAXONOMY BACKFILL ===")
    try:
        # Mock sys.argv for argparse inside run_backfill
        sys.argv = ["scripts.backfill_taxonomy", "--db-path", db_path, "--force"]
        run_backfill()
        logger.info("Backfill and classification completed successfully.")
    except Exception as e:
        logger.exception(f"Backfill and classification failed: {e}")
        sys.exit(1)

    logger.info("=== STEP 3: COMPUTING CATEGORY STATS ===")
    db = SessionLocal()
    try:
        from app.models.feedback_item import FeedbackItem
        from sqlalchemy import func
        stats = db.query(FeedbackItem.issue_category, func.count()).group_by(FeedbackItem.issue_category).all()
        logger.info("Final categorized distribution:")
        for category, count in stats:
            logger.info(f"  - {category or 'Uncategorized'}: {count} items")
    except Exception as e:
        logger.exception(f"Failed to query stats: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
