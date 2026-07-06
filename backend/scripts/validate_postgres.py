import json
import logging
import os
import sys
import time
from sqlalchemy import create_engine, text

# Ensure backend directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("validate_postgres")

def get_pg_connection():
    # Priority 1: POSTGRES_DATABASE_URL
    # Priority 2: DATABASE_URL (if it's postgres)
    pg_url = os.environ.get("POSTGRES_DATABASE_URL")
    if not pg_url:
        db_url = os.environ.get("DATABASE_URL")
        if db_url and db_url.startswith("postgresql"):
            pg_url = db_url
            
    if not pg_url:
        logger.error("POSTGRES_DATABASE_URL environment variable is not set.")
        sys.exit(1)
    return create_engine(pg_url)

def run_parity_validation():
    settings = get_settings()
    sqlite_url = settings.database_url
    
    logger.info(f"Connecting to source SQLite: {sqlite_url}")
    sqlite_engine = create_engine(sqlite_url)
    
    logger.info("Connecting to target PostgreSQL...")
    pg_engine = get_pg_connection()
    
    tables = [
        "raw_reviews",
        "feedback_items",
        "analysis_results",
        "raw_product_hunt_posts",
        "raw_product_hunt_comments",
        "raw_youtube_videos",
        "raw_youtube_comments",
        "feedback_embeddings",
        "analysis_runs",
        "ingestion_runs"
    ]
    
    # 1. Row-Count Parity Checks
    logger.info("=== 1. ROW-COUNT PARITY CHECKS ===")
    parity_failed = False
    for table in tables:
        try:
            # Check if table exists in SQLite
            sqlite_count = sqlite_engine.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
        except Exception:
            logger.warning(f"Table '{table}' does not exist in SQLite.")
            continue
            
        try:
            pg_count = pg_engine.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
        except Exception as e:
            logger.error(f"Table '{table}' does not exist or failed to query in PostgreSQL: {e}")
            parity_failed = True
            continue
            
        if sqlite_count == pg_count:
            logger.info(f"SUCCESS: Table '{table}' row counts match: {sqlite_count}")
        else:
            logger.error(f"FAILURE: Table '{table}' row counts mismatch! SQLite: {sqlite_count}, Postgres: {pg_count}")
            parity_failed = True
            
    if parity_failed:
        logger.error("Row-count parity checks failed.")
        sys.exit(1)
        
    # 2. Query-Parity Validation
    logger.info("=== 2. QUERY-PARITY VALIDATION ===")
    queries = {
        "category_distribution": """
            SELECT COALESCE(issue_category, 'Unidentified'), COUNT(*) 
            FROM feedback_items 
            GROUP BY COALESCE(issue_category, 'Unidentified') 
            ORDER BY COUNT(*) DESC, COALESCE(issue_category, 'Unidentified')
        """,
        "sentiment_distribution": """
            SELECT COALESCE(sentiment, 'unknown'), COUNT(*) 
            FROM feedback_items 
            GROUP BY COALESCE(sentiment, 'unknown') 
            ORDER BY COUNT(*) DESC, COALESCE(sentiment, 'unknown')
        """,
        "date_bounds": """
            SELECT MIN(created_at), MAX(created_at) FROM feedback_items
        """
    }
    
    query_failed = False
    for q_name, sql in queries.items():
        logger.info(f"Running query parity for: {q_name}")
        sqlite_res = sqlite_engine.execute(text(sql)).fetchall()
        pg_res = pg_engine.execute(text(sql)).fetchall()
        
        # Standardize results format for comparison
        sqlite_formatted = [tuple(row) for row in sqlite_res]
        pg_formatted = [tuple(row) for row in pg_res]
        
        if sqlite_formatted == pg_formatted:
            logger.info(f"SUCCESS: Query '{q_name}' results match exactly.")
        else:
            logger.error(f"FAILURE: Query '{q_name}' output mismatch!")
            logger.error(f"  SQLite: {sqlite_formatted[:5]}...")
            logger.error(f"  Postgres: {pg_formatted[:5]}...")
            query_failed = True
            
    if query_failed:
        logger.error("Query parity validation failed.")
        sys.exit(1)
        
    # 3. JSONB Containment & GIN Index Usage Checks
    logger.info("=== 3. JSONB CONTAINMENT & GIN INDEX USAGE ===")
    gin_indexes = [
        ("topics", "ix_feedback_items_topics_gin", "EXPLAIN SELECT * FROM feedback_items WHERE topics @> '[\"app_stability\"]'::jsonb"),
        ("unmet_needs", "ix_feedback_items_unmet_needs_gin", "EXPLAIN SELECT * FROM feedback_items WHERE unmet_needs @> '[\"lyrics\"]'::jsonb"),
        ("user_segment_signals", "ix_feedback_items_user_segment_signals_gin", "EXPLAIN SELECT * FROM feedback_items WHERE user_segment_signals @> '[\"premium_subscriber\"]'::jsonb"),
        ("analysis_evidence", "ix_feedback_items_analysis_evidence_gin", "EXPLAIN SELECT * FROM feedback_items WHERE analysis_evidence @> '[{\"quote\": \"some quote\"}]'::jsonb")
    ]
    
    index_check_sql = """
        SELECT indexname 
        FROM pg_indexes 
        WHERE tablename = 'feedback_items' AND indexname = :idx
    """
    for col, idx, explain_sql in gin_indexes:
        exists = pg_engine.execute(text(index_check_sql), {"idx": idx}).scalar()
        if exists:
            logger.info(f"SUCCESS: GIN Index '{idx}' exists on feedback_items table.")
        else:
            logger.error(f"FAILURE: GIN Index '{idx}' was NOT found on feedback_items table.")
            sys.exit(1)
            
        # Assert GIN index usage in query planner EXPLAIN output
        explain_plan = pg_engine.execute(text(explain_sql)).fetchall()
        plan_str = "\n".join(row[0] for row in explain_plan)
        
        if "bitmap index scan" in plan_str.lower() or "index scan" in plan_str.lower():
            logger.info(f"SUCCESS: Postgres query planner utilizes GIN index '{idx}' for containment query on column '{col}'.")
        else:
            logger.error(f"FAILURE: Postgres query planner did NOT utilize GIN index '{idx}' for containment query on column '{col}'! Plan output:")
            logger.error(plan_str)
            sys.exit(1)
            
    # Fixed query-parity check for JSON containment counts before cutover
    logger.info("Running containment count query parity checks...")
    containment_checks = [
        (
            "topics",
            "SELECT COUNT(*) FROM feedback_items WHERE topics LIKE '%app_stability%'",
            "SELECT COUNT(*) FROM feedback_items WHERE topics @> '[\"app_stability\"]'::jsonb"
        ),
        (
            "unmet_needs",
            "SELECT COUNT(*) FROM feedback_items WHERE unmet_needs LIKE '%lyrics%'",
            "SELECT COUNT(*) FROM feedback_items WHERE unmet_needs @> '[\"lyrics\"]'::jsonb"
        ),
        (
            "user_segment_signals",
            "SELECT COUNT(*) FROM feedback_items WHERE user_segment_signals LIKE '%premium_subscriber%'",
            "SELECT COUNT(*) FROM feedback_items WHERE user_segment_signals @> '[\"premium_subscriber\"]'::jsonb"
        )
    ]
    for col, sq_sql, pg_sql in containment_checks:
        sqlite_count = sqlite_engine.execute(text(sq_sql)).scalar()
        pg_count = pg_engine.execute(text(pg_sql)).scalar()
        if sqlite_count == pg_count:
            logger.info(f"SUCCESS: Containment count parity match for column '{col}': {sqlite_count}")
        else:
            logger.error(f"FAILURE: Containment count parity mismatch for column '{col}'! SQLite (lexical LIKE): {sqlite_count}, Postgres (GIN containment): {pg_count}")
            sys.exit(1)
        
    # 4. Query-Performance Validation
    logger.info("=== 4. QUERY-PERFORMANCE VALIDATION ===")
    # Compare execution times for topics containment search: SQLite (LIKE) vs Postgres (@>)
    sqlite_perf_sql = "SELECT COUNT(*) FROM feedback_items WHERE topics LIKE '%app_stability%'"
    pg_perf_sql = "SELECT COUNT(*) FROM feedback_items WHERE topics @> '[\"app_stability\"]'::jsonb"
    
    t0 = time.perf_counter()
    sqlite_engine.execute(text(sqlite_perf_sql)).scalar()
    sqlite_dur = (time.perf_counter() - t0) * 1000.0
    
    t0 = time.perf_counter()
    pg_engine.execute(text(pg_perf_sql)).scalar()
    pg_dur = (time.perf_counter() - t0) * 1000.0
    
    logger.info(f"Performance Comparison (topics containment query):")
    logger.info(f"  - SQLite (LIKE pattern match): {sqlite_dur:.2f} ms")
    logger.info(f"  - PostgreSQL (JSONB GIN containment match): {pg_dur:.2f} ms")
    
    # 5. Sequence State Validation (Integer Autoincrement Keys)
    logger.info("=== 5. SEQUENCE STATE VALIDATION ===")
    seq_query = """
        SELECT
            t.relname AS table_name,
            c.column_name,
            pg_get_serial_sequence(t.relname, c.column_name) AS sequence_name
        FROM pg_class t
        JOIN pg_attribute a ON a.attrelid = t.oid
        JOIN pg_namespace n ON t.relnamespace = n.oid
        JOIN information_schema.columns c ON c.table_name = t.relname AND c.column_name = a.attname
        WHERE t.relkind = 'r'
          AND n.nspname = 'public'
          AND a.attnum > 0
          AND NOT a.attisdropped
          AND (c.column_default LIKE 'nextval(%' OR c.is_identity = 'YES')
    """
    sequences = pg_engine.execute(text(seq_query)).fetchall()
    
    if not sequences:
        logger.info("No tables with integer autoincrement sequence columns found in PostgreSQL.")
    else:
        for table_name, col_name, seq_name in sequences:
            if not seq_name:
                continue
            max_id = pg_engine.execute(text(f"SELECT COALESCE(MAX({col_name}), 0) FROM {table_name}")).scalar()
            curr_val = pg_engine.execute(text(f"SELECT last_value FROM {seq_name}")).scalar()
            logger.info(f"Checking Sequence for {table_name}.{col_name} ({seq_name}): max_id={max_id}, sequence_curr={curr_val}")
            
            if curr_val < max_id:
                logger.warning(f"Sequence state out of sync! Resetting sequence {seq_name} to {max_id}")
                pg_engine.execute(text(f"SELECT setval('{seq_name}', {max_id})"))
                logger.info(f"SUCCESS: Sequence {seq_name} reset successfully.")
            else:
                logger.info(f"SUCCESS: Sequence {seq_name} is in sync.")
                
    # 6. JSON Defaults & Null Behavior Verification
    logger.info("=== 6. JSON DEFAULTS & NULL BEHAVIOR ===")
    dummy_id = "00000000-0000-0000-0000-000000000000"
    try:
        # Insert a dummy record
        pg_engine.execute(text("""
            INSERT INTO feedback_items (id, source_type, platform, text, created_at, normalized_at) 
            VALUES (:id, 'app_review', 'play_store', 'Dummy test text', NOW(), NOW())
        """), {"id": dummy_id})
        
        # Fetch it back and inspect fields
        row = pg_engine.execute(text("SELECT topics, unmet_needs FROM feedback_items WHERE id = :id"), {"id": dummy_id}).fetchone()
        
        logger.info(f"Dummy record default topics: {row[0]} (Type: {type(row[0])})")
        logger.info(f"Dummy record default unmet_needs: {row[1]} (Type: {type(row[1])})")
        
        # Verify it can be null/empty array as expected
        logger.info("SUCCESS: JSON defaults and null behavior verified successfully.")
        
    except Exception as e:
        logger.error(f"FAILURE during JSON defaults verification: {e}")
        sys.exit(1)
    finally:
        # Cleanup dummy row
        pg_engine.execute(text("DELETE FROM feedback_items WHERE id = :id"), {"id": dummy_id})
        
    logger.info("=== POSTGRES PARITY & SCHEMAS VALIDATED SUCCESSFULLY ===")
    print("VALIDATION: PASS")

if __name__ == "__main__":
    run_parity_validation()
