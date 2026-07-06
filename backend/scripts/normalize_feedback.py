"""CLI entry point for running the review normalization job."""

from app.database import SessionLocal
from app.services.normalization_service import run_normalization


def main() -> None:
    db = SessionLocal()
    try:
        print("Starting normalization job...")
        counts = run_normalization(db)
        print("Normalization job completed!")
        print(f"Processed: {counts['processed']}")
        print(f"Inserted:  {counts['inserted']}")
        print(f"Skipped:   {counts['skipped']}")
        print(f"Dropped:   {counts['dropped']}")
        print(f"Failed:    {counts['failed']}")
    except Exception as exc:
        print(f"Normalization job failed: {exc}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
