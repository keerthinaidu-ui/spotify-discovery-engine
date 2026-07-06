import os
import sqlite3
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("run_migration")

def migrate_database(db_path):
    if not os.path.exists(db_path):
        logger.warning(f"Database file not found: {db_path}")
        return

    logger.info(f"Migrating database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    columns_to_add = [
        ("primary_theme", "TEXT"),
        ("secondary_tags", "TEXT"),
        ("taxonomy_version", "TEXT"),
        ("classification_source", "TEXT"),
        ("classification_confidence", "REAL"),
    ]

    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE feedback_items ADD COLUMN {col_name} {col_type}")
            conn.commit()
            logger.info(f"Successfully added column '{col_name}' to feedback_items.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                logger.info(f"Column '{col_name}' already exists in feedback_items. Skipping.")
            else:
                logger.error(f"Failed to add column '{col_name}': {e}")
                conn.rollback()

    conn.close()
    logger.info(f"Finished migration for: {db_path}")

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))

    db_paths = [
        os.path.join(project_root, "data", "spotify_review_engine.db"),
        os.path.join(project_root, "backend", "test_temp.db"),
        os.path.join(project_root, "test_temp.db"),
    ]

    for path in db_paths:
        migrate_database(path)

if __name__ == "__main__":
    main()
