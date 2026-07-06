import json
import logging
import os
import sys
from sqlalchemy import text

# Ensure backend directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import get_settings
from app.database import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("audit_json_data")

THRESHOLD_PERCENT = 1.0  # Max allowable malformed row percentage

def try_repair_json(val: str) -> str | None:
    """Attempts to repair common JSON malformations in text columns."""
    if not val or not val.strip():
        return "[]"
    
    cleaned = val.strip()
    
    # Heuristic 1: If it's already valid JSON, return it
    try:
        json.loads(cleaned)
        return cleaned
    except json.JSONDecodeError:
        pass

    # Heuristic 2: Python single-quoted representations (e.g. ['a', 'b'])
    # Replace single quotes with double quotes
    try:
        # replace single quotes not preceded by backslashes
        replaced = cleaned.replace("'", '"')
        json.loads(replaced)
        return replaced
    except json.JSONDecodeError:
        pass

    # Heuristic 3: Double double quotes or unescaped quotes inside list elements
    # Try surrounding string with brackets if it looks like a comma-separated list
    if not cleaned.startswith("[") and not cleaned.startswith("{"):
        try:
            wrapped = "[" + ",".join(f'"{x.strip()}"' for x in cleaned.split(",")) + "]"
            json.loads(wrapped)
            return wrapped
        except json.JSONDecodeError:
            pass

    return None

def audit_json_fields():
    settings = get_settings()
    logger.info(f"Connecting to source database: {settings.database_url}")
    
    db = SessionLocal()
    
    total_checked = 0
    total_malformed = 0
    total_repaired = 0
    total_nullified = 0
    
    quarantine = []
    
    # Audit target: (table_name, column_name, pk_name)
    targets = [
        ("feedback_items", "topics", "id"),
        ("feedback_items", "unmet_needs", "id"),
        ("feedback_items", "user_segment_signals", "id"),
        ("feedback_items", "analysis_evidence", "id"),
        ("analysis_results", "payload_json", "id"),
    ]
    
    try:
        for table, col, pk in targets:
            logger.info(f"Auditing column '{col}' in table '{table}'...")
            
            # Fetch all rows where the column is not NULL and not empty
            query = text(f"SELECT {pk}, {col} FROM {table} WHERE {col} IS NOT NULL AND {col} != ''")
            rows = db.execute(query).fetchall()
            
            for row in rows:
                row_id = row[0]
                val = row[1]
                total_checked += 1
                
                try:
                    json.loads(val)
                except json.JSONDecodeError:
                    total_malformed += 1
                    repaired_val = try_repair_json(val)
                    
                    if repaired_val is not None:
                        logger.info(f"SUCCESS: Repaired malformed JSON in {table}.{col} for ID {row_id}")
                        db.execute(
                            text(f"UPDATE {table} SET {col} = :val WHERE {pk} = :id"),
                            {"val": repaired_val, "id": row_id}
                        )
                        total_repaired += 1
                    else:
                        logger.warning(f"FAILED: Malformed JSON in {table}.{col} for ID {row_id}: {val[:100]}...")
                        # Fallback Strategy: Nullify field and log to quarantine list
                        db.execute(
                            text(f"UPDATE {table} SET {col} = NULL WHERE {pk} = :id"),
                            {"id": row_id}
                        )
                        quarantine.append({
                            "table": table,
                            "column": col,
                            "id": row_id,
                            "original_value": val
                        })
                        total_nullified += 1
                        
        db.commit()
        
        # Write quarantine records to a file for developer inspection
        if quarantine:
            quarantine_path = os.path.join(settings.reviews_csv_absolute.parent, "quarantine_records.json")
            with open(quarantine_path, "w", encoding="utf-8") as f:
                json.dump(quarantine, f, indent=2)
            logger.warning(f"Quarantined {len(quarantine)} records to: {quarantine_path}")
            
        logger.info("=== JSON DATA AUDIT SUMMARY ===")
        logger.info(f"Total JSON fields checked: {total_checked}")
        logger.info(f"Total malformed JSON fields found: {total_malformed}")
        logger.info(f"Total fields successfully repaired: {total_repaired}")
        logger.info(f"Total fields nullified/quarantined: {total_nullified}")
        
        malformed_rate = (total_malformed / total_checked * 100.0) if total_checked > 0 else 0.0
        logger.info(f"Malformed Rate: {malformed_rate:.2f}% (Limit: {THRESHOLD_PERCENT}%)")
        
        if malformed_rate > THRESHOLD_PERCENT:
            logger.error("AUDIT GATE FAILURE: Malformed JSON rate exceeds allowable threshold.")
            sys.exit(1)
        else:
            logger.info("AUDIT GATE SUCCESS: JSON data is clean or within acceptable thresholds.")
            
    except Exception as e:
        db.rollback()
        logger.error(f"Error during JSON data audit: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    audit_json_fields()
