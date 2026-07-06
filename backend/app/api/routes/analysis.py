from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.analysis_run import AnalysisRun
from app.models.feedback_item import FeedbackItem
from app.schemas.analysis import (
    AnalysisRunStatusResponse,
    AnalysisRunTriggerResponse,
    AnalysisCoverageResponse,
)
from app.services.analysis_service import trigger_analysis_run
from app.worker import worker

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/run", response_model=AnalysisRunTriggerResponse)
def trigger_analysis(
    background_tasks: BackgroundTasks = None,
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> AnalysisRunTriggerResponse:
    run_id = trigger_analysis_run(db, limit)
    
    # Query run record to return response
    run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=500, detail="Failed to initialize analysis run.")

    return AnalysisRunTriggerResponse(
        run_id=run.id,
        status=run.status,
        started_at=run.started_at,
    )


@router.get("/status", response_model=AnalysisRunStatusResponse)
def get_analysis_status(
    run_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> AnalysisRunStatusResponse:
    if run_id:
        run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
        if not run:
            raise HTTPException(status_code=404, detail=f"Analysis run {run_id} not found.")
    else:
        # Fetch the latest run
        run = db.query(AnalysisRun).order_by(AnalysisRun.started_at.desc()).first()
        if not run:
            raise HTTPException(status_code=404, detail="No analysis runs found.")

    return AnalysisRunStatusResponse.model_validate(run)


@router.get("/coverage", response_model=AnalysisCoverageResponse)
def get_analysis_coverage(db: Session = Depends(get_db)) -> AnalysisCoverageResponse:
    total_ingested = db.query(FeedbackItem).count()
    analyzed = db.query(FeedbackItem).filter(FeedbackItem.analysis_status == "complete").count()
    
    # pending count includes both pending and processing
    pending = db.query(FeedbackItem).filter(
        FeedbackItem.analysis_status.in_(["pending", "processing"])
    ).count()
    
    failed = db.query(FeedbackItem).filter(FeedbackItem.analysis_status == "failed").count()
    
    percent_analyzed = (analyzed / total_ingested * 100.0) if total_ingested > 0 else 0.0
    
    # Check if worker is actively running or has pending items to process
    active_run = db.query(AnalysisRun).filter(AnalysisRun.status == "running").first()
    is_active = (active_run is not None) or (pending > 0)
    active_job_status = "running" if (worker.is_running and is_active) else "idle"
    
    # Estimate remaining time based on ~1.5s per pending item
    estimated_remaining = pending * 1.5 if pending > 0 else 0.0
    
    return AnalysisCoverageResponse(
        total_ingested=total_ingested,
        analyzed=analyzed,
        pending=pending,
        failed=failed,
        percent_analyzed=round(percent_analyzed, 2),
        active_job_status=active_job_status,
        last_successful_run=worker.last_run_time,
        estimated_remaining_time_seconds=estimated_remaining,
    )

