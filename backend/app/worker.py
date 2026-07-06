import logging
import time
import json
import threading
import signal
import sys
from datetime import datetime, timezone
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.models.feedback_item import FeedbackItem
from app.models.analysis_run import AnalysisRun
from app.services.llm_service import LLMService, RateLimitException

logger = logging.getLogger("app.worker")

class AnalysisWorker:
    def __init__(self):
        self._thread = None
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self.is_running = False
        self.last_run_time = None
        self.settings = get_settings()
        self.llm = LLMService(self.settings)
        self.base_delay = 1.0
        self.current_backoff = 0.0

    def start(self):
        if not self.settings.worker_enabled:
            logger.info("Analysis worker is disabled in settings.")
            return
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._wake_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="AnalysisWorkerThread")
        self._thread.start()
        self.is_running = True
        logger.info("Analysis worker started in background thread.")

    def stop(self):
        self._stop_event.set()
        self.wake()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self.is_running = False
        logger.info("Analysis worker stopped.")

    def wake(self):
        self._wake_event.set()

    def run_forever(self):
        """Blocking method for standalone process execution."""
        logger.info("Running analysis worker in standalone process mode.")
        self._stop_event.clear()
        self._wake_event.clear()
        self.is_running = True
        
        # Setup signal handlers for clean exit
        def handler(signum, frame):
            logger.info("Termination signal received. Shutting down worker...")
            self._stop_event.set()
            self.wake()

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)
        
        self._run_loop()
        self.is_running = False
        logger.info("Analysis worker process exited cleanly.")

    def _recover_jobs(self, db: Session):
        """Clean up orphaned runs and reset stuck processing items."""
        try:
            # 1. Find all running jobs from previous sessions and mark them failed
            stuck_runs = db.query(AnalysisRun).filter(AnalysisRun.status == "running").all()
            if stuck_runs:
                logger.info(f"Worker recovery: found {len(stuck_runs)} stuck runs. Marking as failed.")
                for run in stuck_runs:
                    run.status = "failed"
                    run.finished_at = datetime.now(timezone.utc)
                    run.error_message = "Interrupted by system restart/shutdown"
                db.commit()

            # 2. Reset any items stuck in 'processing' back to 'pending'
            stuck_items = db.query(FeedbackItem).filter(FeedbackItem.analysis_status == "processing").all()
            if stuck_items:
                logger.info(f"Worker recovery: resetting {len(stuck_items)} stuck processing items to pending.")
                for item in stuck_items:
                    item.analysis_status = "pending"
                db.commit()
        except Exception as exc:
            db.rollback()
            logger.error(f"Error during job recovery: {exc}")

    def _run_loop(self):
        # Perform startup job recovery
        db_init = SessionLocal()
        try:
            self._recover_jobs(db_init)
        finally:
            db_init.close()

        while not self._stop_event.is_set():
            # Apply throttle backoff delay if any
            if self.current_backoff > 0:
                logger.info(f"Throttling worker for {self.current_backoff:.2f}s...")
                self._stop_event.wait(self.current_backoff)
                self.current_backoff = 0.0

            try:
                db = SessionLocal()
                try:
                    batch_size = self.settings.worker_batch_size
                    max_retries = self.settings.worker_max_retries

                    # Query items that are pending or failed with retry_count < max_retries
                    query = db.query(FeedbackItem).filter(
                        or_(
                            FeedbackItem.analysis_status == "pending",
                            and_(
                                FeedbackItem.analysis_status == "failed",
                                FeedbackItem.retry_count < max_retries
                            )
                        )
                    ).order_by(
                        # Prioritize pending over failed, then oldest first
                        FeedbackItem.analysis_status.desc(),
                        FeedbackItem.created_at.asc()
                    )

                    # Multi-process concurrency-safe locking on PostgreSQL using SKIP LOCKED
                    if db.bind.dialect.name == "postgresql":
                        items = query.with_for_update(skip_locked=True).limit(batch_size).all()
                    else:
                        items = query.limit(batch_size).all()


                    if not items:
                        # Clear wake event and wait
                        self._wake_event.clear()
                        self._wake_event.wait(5.0)
                        continue

                    logger.info(f"Analysis worker: processing batch of {len(items)} items.")

                    # Mark batch as processing (idempotency / lock)
                    item_ids = [item.id for item in items]
                    db.query(FeedbackItem).filter(FeedbackItem.id.in_(item_ids)).update(
                        {"analysis_status": "processing"}, synchronize_session=False
                    )
                    db.commit()

                    # Process each item in the batch
                    for item_id in item_ids:
                        if self._stop_event.is_set():
                            break

                        item = db.query(FeedbackItem).filter(FeedbackItem.id == item_id).first()
                        if not item:
                            continue

                        text = (item.text or "").strip()
                        if len(text) < 10:
                            item.analyzed_at = datetime.now(timezone.utc)
                            item.analysis_provider = "skipped"
                            item.analysis_error = "Text too short (< 10 chars)"
                            item.analysis_status = "complete"
                            self._update_active_run_progress(db, skipped_delta=1)
                            db.commit()
                            continue

                        metadata = {
                            "source_type": item.source_type,
                            "platform": item.platform,
                            "rating_or_score": item.rating_or_score,
                        }



                        try:
                            parsed_data, provider, model, was_fallback = self.llm.analyze_feedback(text, metadata)

                            prim_theme = parsed_data.get("primary_theme") or parsed_data.get("issue_category") or "Unidentified"
                            item.primary_theme = prim_theme
                            item.issue_category = prim_theme  # Dual-write for backward compatibility
                            item.secondary_tags = json.dumps(parsed_data.get("secondary_tags", []))
                            item.taxonomy_version = "2.0.0"
                            item.classification_source = provider
                            item.classification_confidence = parsed_data.get("confidence")

                            item.sentiment = parsed_data.get("sentiment")
                            item.has_mixed_sentiment = parsed_data.get("has_mixed_sentiment")
                            sentiment_prof = parsed_data.get("sentiment_profile")
                            if sentiment_prof:
                                item.sentiment_profile = json.dumps(sentiment_prof)
                            item.topics = json.dumps(parsed_data.get("topics", []))
                            item.user_segment = parsed_data.get("user_segment")
                            item.listening_intent = parsed_data.get("listening_intent")
                            item.loop_cause = parsed_data.get("loop_cause")
                            item.unmet_needs = json.dumps(parsed_data.get("unmet_needs", []))
                            item.listening_job = parsed_data.get("listening_job")
                            item.desired_outcome = parsed_data.get("desired_outcome")
                            item.blocked_goal = parsed_data.get("blocked_goal")
                            item.root_cause = parsed_data.get("root_cause")
                            item.user_segment_signals = json.dumps(parsed_data.get("user_segment_signals", []))
                            item.recommendation_pain_type = parsed_data.get("recommendation_pain_type")
                            item.evidence_quote = parsed_data.get("evidence_quote")
                            item.analysis_confidence = parsed_data.get("confidence")
                            item.analysis_version = "2.0.0"
                            item.analyzed_at = datetime.now(timezone.utc)
                            item.analysis_evidence = json.dumps(parsed_data.get("evidence", []))
                            item.analysis_provider = provider
                            item.analysis_model = model
                            item.analysis_error = None
                            item.analysis_status = "complete"
                            item.failure_reason = None

                            self.last_run_time = datetime.now(timezone.utc)

                            self._update_active_run_progress(db, processed_delta=1, fallback_delta=1 if was_fallback else 0)
                            db.commit()

                            # Throttle delay between calls
                            if self.settings.worker_throttle_delay > 0:
                                self._stop_event.wait(self.settings.worker_throttle_delay)

                        except RateLimitException as exc:
                            db.rollback()
                            logger.warning(f"Rate limit hit: {exc}. Retrying later.")
                            # Re-fetch item to update in new transaction
                            item = db.query(FeedbackItem).filter(FeedbackItem.id == item_id).first()
                            if item:
                                item.retry_count += 1
                                item.analysis_status = "failed"
                                item.failure_reason = f"RateLimitException: {str(exc)}"
                                item.analysis_error = str(exc)

                            self._update_active_run_progress(db, failed_delta=1)
                            db.commit()

                            # Pause worker
                            self.current_backoff = exc.retry_after

                        except Exception as exc:
                            db.rollback()
                            logger.error(f"Error analyzing item {item_id}: {exc}")
                            item = db.query(FeedbackItem).filter(FeedbackItem.id == item_id).first()
                            if item:
                                item.retry_count += 1
                                item.analysis_status = "failed"
                                item.failure_reason = str(exc)
                                item.analysis_error = str(exc)

                            self._update_active_run_progress(db, failed_delta=1)
                            db.commit()

                            # General exponential backoff
                            if item:
                                self.current_backoff = min(60.0, 2.0 * item.retry_count)
                            else:
                                self.current_backoff = 2.0

                    # Check if all runs are complete
                    self._check_and_complete_runs(db)

                except Exception as exc:
                    logger.error(f"Database error in worker loop: {exc}")
                finally:
                    db.close()

            except Exception as exc:
                logger.error(f"Critical error in worker thread: {exc}")
                self._stop_event.wait(5.0)

    def _update_active_run_progress(self, db: Session, processed_delta: int = 0, failed_delta: int = 0, skipped_delta: int = 0, fallback_delta: int = 0):
        try:
            # Find the active running run
            run = db.query(AnalysisRun).filter(AnalysisRun.status == "running").order_by(AnalysisRun.started_at.desc()).first()
            if run:
                run.processed_items += (processed_delta + failed_delta + skipped_delta)
                run.failed_items += failed_delta
                run.skipped_items += skipped_delta
                run.fallback_count += fallback_delta
        except Exception as e:
            logger.error(f"Failed to update run progress: {e}")

    def _check_and_complete_runs(self, db: Session):
        try:
            # If no more pending items exist, complete any running runs
            max_retries = self.settings.worker_max_retries
            pending_count = db.query(FeedbackItem).filter(
                or_(
                    FeedbackItem.analysis_status == "pending",
                    and_(
                        FeedbackItem.analysis_status == "failed",
                        FeedbackItem.retry_count < max_retries
                    )
                )
            ).count()

            if pending_count == 0:
                running_runs = db.query(AnalysisRun).filter(AnalysisRun.status == "running").all()
                for r in running_runs:
                    r.status = "completed"
                    r.finished_at = datetime.now(timezone.utc)
                if running_runs:
                    db.commit()
                    logger.info("All pending reviews processed. Analysis runs marked as completed.")
        except Exception as e:
            logger.error(f"Failed to check/complete runs: {e}")

# Global instance for lifespan management
worker = AnalysisWorker()

if __name__ == "__main__":
    # Setup standard logger output when run directly
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    worker.run_forever()
