"""CLI entry point for CSV review ingestion."""

from app.config import get_settings
from app.database import SessionLocal
from app.services.ingestion_service import run_reviews_ingestion


def main() -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        result = run_reviews_ingestion(db, settings)
        run = result.run
        print(
            f"Ingestion {run.status}: read={run.rows_read} "
            f"inserted={run.rows_inserted} skipped={run.rows_skipped}"
        )
        if run.error_message:
            print(f"Error: {run.error_message}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
