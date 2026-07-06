import csv
import io
import json
from datetime import datetime
from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.feedback_item import FeedbackItem

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/summary")
def export_summary(
    format: str = Query(default="json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db)
):
    # Query summary metrics (reusing insights logic)
    items = db.query(FeedbackItem).filter(FeedbackItem.analyzed_at.isnot(None)).all()
    total_analyzed = len(items)

    categories_map = {}
    segments_map = {}
    topics_map = {}
    unmet_needs_map = {}

    for item in items:
        if item.issue_category:
            categories_map[item.issue_category] = categories_map.get(item.issue_category, 0) + 1
        if item.user_segment:
            segments_map[item.user_segment] = segments_map.get(item.user_segment, 0) + 1
        if item.topics:
            try:
                topics_list = json.loads(item.topics)
                if isinstance(topics_list, list):
                    for t in topics_list:
                        topics_map[t] = topics_map.get(t, 0) + 1
            except Exception:
                pass
        if item.unmet_needs:
            try:
                needs_list = json.loads(item.unmet_needs)
                if isinstance(needs_list, list):
                    for n in needs_list:
                        unmet_needs_map[n] = unmet_needs_map.get(n, 0) + 1
            except Exception:
                pass

    summary_data = {
        "total_analyzed": total_analyzed,
        "categories": categories_map,
        "segments": segments_map,
        "topics": topics_map,
        "unmet_needs": unmet_needs_map
    }

    if format == "json":
        content = json.dumps(summary_data, indent=2)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=insights_summary.json"}
        )
    else:
        # Export as CSV
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Metric Type", "Name", "Count"])
        for cat, cnt in categories_map.items():
            writer.writerow(["Category", cat, cnt])
        for seg, cnt in segments_map.items():
            writer.writerow(["Segment", seg, cnt])
        for top, cnt in topics_map.items():
            writer.writerow(["Topic", top, cnt])
        for need, cnt in unmet_needs_map.items():
            writer.writerow(["Unmet Need", need, cnt])

        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=insights_summary.csv"}
        )


@router.get("/feedback")
def export_feedback(
    format: str = Query(default="csv", pattern="^(json|csv)$"),
    labeled_only: bool = Query(default=False),
    db: Session = Depends(get_db)
):
    query = db.query(FeedbackItem)
    if labeled_only:
        query = query.filter(FeedbackItem.analyzed_at.isnot(None))

    items = query.all()

    if format == "json":
        feedback_list = []
        for item in items:
            feedback_list.append({
                "id": item.id,
                "source_type": item.source_type,
                "platform": item.platform,
                "text": item.text,
                "title": item.title,
                "rating_or_score": item.rating_or_score,
                "author": item.author,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "app_version": item.app_version,
                "url": item.url,
                "sentiment": item.sentiment,
                "issue_category": item.issue_category,
                "topics": json.loads(item.topics) if item.topics else None,
                "user_segment": item.user_segment,
                "unmet_needs": json.loads(item.unmet_needs) if item.unmet_needs else None,
                "analyzed_at": item.analyzed_at.isoformat() if item.analyzed_at else None
            })
        content = json.dumps(feedback_list, indent=2)
        filename = "labeled_feedback.json" if labeled_only else "all_feedback.json"
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    else:
        # Export as CSV
        output = io.StringIO()
        writer = csv.writer(output)
        headers = [
            "id", "source_type", "platform", "text", "title", "rating_or_score",
            "author", "created_at", "app_version", "url", "sentiment",
            "issue_category", "topics", "user_segment", "unmet_needs", "analyzed_at"
        ]
        writer.writerow(headers)
        for item in items:
            writer.writerow([
                item.id,
                item.source_type,
                item.platform,
                item.text,
                item.title,
                item.rating_or_score,
                item.author,
                item.created_at.isoformat() if item.created_at else "",
                item.app_version,
                item.url,
                item.sentiment,
                item.issue_category,
                item.topics or "",
                item.user_segment,
                item.unmet_needs or "",
                item.analyzed_at.isoformat() if item.analyzed_at else ""
            ])

        output.seek(0)
        filename = "labeled_feedback.csv" if labeled_only else "all_feedback.csv"
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
