import logging
import os
import sys
import time
from datetime import datetime, timezone
from sqlalchemy import create_engine, text

# Ensure backend directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("dual_run_monitor")

def get_pg_connection():
    pg_url = os.environ.get("POSTGRES_DATABASE_URL")
    if not pg_url:
        db_url = os.environ.get("DATABASE_URL")
        if db_url and db_url.startswith("postgresql"):
            pg_url = db_url
    if not pg_url:
        logger.error("POSTGRES_DATABASE_URL environment variable is not set.")
        sys.exit(1)
    return create_engine(pg_url)

def monitor_dual_run():
    settings = get_settings()
    sqlite_url = settings.database_url
    
    logger.info("=== STARTING DUAL-RUN POST-CUTOVER MONITORING ===")
    logger.info(f"Target Database (PostgreSQL): Connected")
    pg_engine = get_pg_connection()
    
    logger.info(f"Legacy Database (SQLite): {sqlite_url}")
    sqlite_engine = create_engine(sqlite_url)
    
    # 1. Structural drift check
    logger.info("Checking for structural drift between SQLite and Postgres...")
    sqlite_tables = sqlite_engine.execute(
        text("SELECT name FROM sqlite_master WHERE type='table'")
    ).fetchall()
    sqlite_table_names = {row[0] for row in sqlite_tables}
    
    pg_tables = pg_engine.execute(
        text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
    ).fetchall()
    pg_table_names = {row[0] for row in pg_tables}
    
    missing_in_pg = sqlite_table_names - pg_table_names
    if missing_in_pg:
        logger.error(f"DRIFT DETECTED: Postgres is missing tables from SQLite: {missing_in_pg}")
    else:
        logger.info("SUCCESS: No missing tables in PostgreSQL schema.")
        
    # 2. Performance and Latency checks (Read performance)
    logger.info("Measuring read latency (topics analytics filters) on PostgreSQL...")
    pg_analytics_sql = """
        SELECT COUNT(*), issue_category 
        FROM feedback_items 
        WHERE topics @> '["app_stability"]'::jsonb 
        GROUP BY issue_category
    """
    
    latencies = []
    for _ in range(5):
        t0 = time.perf_counter()
        pg_engine.execute(text(pg_analytics_sql)).fetchall()
        dur = (time.perf_counter() - t0) * 1000.0
        latencies.append(dur)
        
    avg_latency = sum(latencies) / len(latencies)
    logger.info(f"PostgreSQL average containment read latency: {avg_latency:.2f} ms")
    
    if avg_latency > 200.0:
        logger.warning(f"LATENCY ALERT: PostgreSQL containment read average latency is high ({avg_latency:.2f} ms)")
    else:
        logger.info(f"SUCCESS: Read performance is within stable boundaries (< 200ms).")

    # 3. Sequence Drift Checks
    logger.info("Checking sequence states in PostgreSQL...")
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
    for table_name, col_name, seq_name in sequences:
        if not seq_name:
            continue
        max_id = pg_engine.execute(text(f"SELECT COALESCE(MAX({col_name}), 0) FROM {table_name}")).scalar()
        curr_val = pg_engine.execute(text(f"SELECT last_value FROM {seq_name}")).scalar()
        if curr_val < max_id:
            logger.error(f"DRIFT DETECTED: Sequence {seq_name} is behind max id ({max_id}) in table {table_name}!")
        else:
            logger.info(f"Sequence {seq_name} is in sync (curr={curr_val}, max={max_id}).")

    # 4. Write validation on PostgreSQL
    logger.info("Verifying write stability on PostgreSQL...")
    test_id = "monitoring-write-test-" + str(int(time.time()))
    try:
        t0 = time.perf_counter()
        pg_engine.execute(text("""
            INSERT INTO feedback_items (id, source_type, platform, text, created_at, normalized_at) 
            VALUES (:id, 'app_review', 'play_store', 'Monitoring write test', NOW(), NOW())
        """), {"id": test_id})
        write_dur = (time.perf_counter() - t0) * 1000.0
        
        # Verify read back
        row = pg_engine.execute(
            text("SELECT text FROM feedback_items WHERE id = :id"), {"id": test_id}
        ).fetchone()
        assert row and row[0] == 'Monitoring write test'
        
        # Cleanup
        pg_engine.execute(text("DELETE FROM feedback_items WHERE id = :id"), {"id": test_id})
        
        logger.info(f"Write validation completed successfully in {write_dur:.2f} ms")
    except Exception as e:
        logger.error(f"CRITICAL: Write validation failed on PostgreSQL staging database: {e}")
        sys.exit(1)
        
    logger.info("=== DUAL-RUN MONITORING RUN COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    monitor_dual_run()
