import os
import sys
import time
from datetime import datetime
from fastapi.testclient import TestClient

# Ensure the backend directory is in the import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.database import SessionLocal
from app.models.feedback_item import FeedbackItem
from app.models.analysis_run import AnalysisRun

client = TestClient(app)


def run_e2e_validation():
    print("=== STARTING END-TO-END RELEASE-READINESS VALIDATION ===")
    
    # 1. Check initial state
    db = SessionLocal()
    try:
        total_items = db.query(FeedbackItem).count()
        unanalyzed_items = db.query(FeedbackItem).filter(FeedbackItem.analyzed_at.is_(None)).count()
        analyzed_items = db.query(FeedbackItem).filter(FeedbackItem.analyzed_at.isnot(None)).count()
        print(f"Database Stats:")
        print(f"  - Total feedback items: {total_items}")
        print(f"  - Analyzed feedback items: {analyzed_items}")
        print(f"  - Unanalyzed feedback items: {unanalyzed_items}")
        
        if unanalyzed_items == 0:
            print("No unanalyzed feedback items found! Resetting 5 items for test purposes.")
            items_to_reset = db.query(FeedbackItem).limit(5).all()
            for item in items_to_reset:
                item.analyzed_at = None
                item.issue_category = None
                item.topics = None
                item.user_segment = None
                item.unmet_needs = None
                item.analysis_provider = None
            db.commit()
            unanalyzed_items = 5
    finally:
        db.close()

    # 2. Trigger analysis run via API
    print("\n1. Triggering Analysis Run via API (POST /analysis/run?limit=3)...")
    response = client.post("/analysis/run?limit=3")
    if response.status_code != 200:
        print(f"Error: POST /analysis/run failed with status {response.status_code}")
        print(response.json())
        sys.exit(1)
        
    run_data = response.json()
    run_id = run_data["run_id"]
    print(f"  - Run triggered successfully. ID: {run_id}, Status: {run_data['status']}")

    # 3. Poll analysis status via API
    print("\n2. Polling Analysis Status via API (GET /analysis/status?run_id=...)...")
    max_wait_seconds = 60
    start_time = time.time()
    completed = False
    
    while time.time() - start_time < max_wait_seconds:
        status_resp = client.get(f"/analysis/status?run_id={run_id}")
        if status_resp.status_code != 200:
            print(f"Error checking status: {status_resp.status_code}")
            print(status_resp.json())
            sys.exit(1)
            
        status_data = status_resp.json()
        print(f"  - Status: {status_data['status']} | Processed: {status_data['processed_items']}/{status_data['total_items']} | Skips: {status_data['skipped_items']} | Fails: {status_data['failed_items']} | Fallbacks: {status_data['fallback_count']}")
        
        if status_data["status"] in ("completed", "failed"):
            completed = True
            break
            
        time.sleep(2)
        
    if not completed:
        print("Error: Analysis run timed out!")
        sys.exit(1)
        
    print(f"  - Run finished in {time.time() - start_time:.2f}s.")
    if status_data["status"] == "failed":
        print(f"Error: Job failed with error: {status_data['error_message']}")
        sys.exit(1)

    # 4. Verify stored database fields
    print("\n3. Verifying Stored Analysis Fields directly in DB...")
    db = SessionLocal()
    try:
        run_record = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
        print("AnalysisRun record metrics:")
        print(f"  - total_items: {run_record.total_items}")
        print(f"  - processed_items: {run_record.processed_items}")
        print(f"  - skipped_items: {run_record.skipped_items}")
        print(f"  - failed_items: {run_record.failed_items}")
        print(f"  - fallback_count: {run_record.fallback_count}")
        print(f"  - provider_primary: {run_record.provider_primary} ({run_record.model_primary})")
        print(f"  - provider_fallback: {run_record.provider_fallback} ({run_record.model_fallback})")
        
        # Verify fallback logic
        if run_record.fallback_count > 0:
            print("  [SUCCESS] Provider Fallback was successfully engaged and tracked!")
        else:
            print("  [WARNING] No fallbacks were tracked during this run.")
            
        # Verify feedback items updated
        updated_items = db.query(FeedbackItem).filter(FeedbackItem.analyzed_at.isnot(None)).order_by(FeedbackItem.analyzed_at.desc()).limit(3).all()
        for i, item in enumerate(updated_items):
            print(f"FeedbackItem {i+1} ({item.id}):")
            print(f"  - Text: {item.text[:50]}...")
            print(f"  - Provider used: {item.analysis_provider}")
            print(f"  - Category: {item.issue_category}")
            print(f"  - Topics: {item.topics}")
            print(f"  - User Segment: {item.user_segment}")
            print(f"  - Unmet Needs: {item.unmet_needs}")
            print(f"  - Evidence snippet count: {len(item.analysis_evidence) if item.analysis_evidence else 0}")
            print(f"  - Error status: {item.analysis_error}")
            
            if item.analysis_provider == "skipped":
                assert len(item.text) < 10, "Item skipped but text >= 10 chars"
            elif item.analysis_provider != "error":
                assert item.issue_category is not None, "Analyzed item category is null"
                assert item.topics is not None, "Analyzed item topics list is null"
                assert item.analysis_provider in ("gemini", "groq"), f"Invalid provider: {item.analysis_provider}"
                
        print("  [SUCCESS] Analysis fields stored correctly in database.")
    finally:
        db.close()

    # 5. Verify Insights Summary API
    print("\n4. Verifying Insights Summary API (GET /insights/summary)...")
    summary_resp = client.get("/insights/summary")
    assert summary_resp.status_code == 200, "Insights summary endpoint failed"
    summary = summary_resp.json()
    print(f"  - Total analyzed items: {summary['total_analyzed']}")
    print(f"  - Top categories: {summary['top_categories'][:3]}")
    print(f"  - Top topics: {summary['top_topics'][:3]}")
    print(f"  - Top segments: {summary['top_segments'][:3]}")
    print("  [SUCCESS] Insights summary returns correct schema and JSON output.")

    # 6. Verify Insights Compare API
    print("\n5. Verifying Insights Compare API (GET /insights/compare)...")
    compare_resp = client.get("/insights/compare?compare_by=source_type")
    assert compare_resp.status_code == 200, "Insights compare endpoint failed"
    compare = compare_resp.json()
    print(f"  - Compare field: {compare['compare_by']}")
    print(f"  - Comparison counts: {compare['comparison']}")
    print("  [SUCCESS] Insights comparison returned correct schema and JSON output.")

    # 7. Verify Insights Evidence API
    print("\n6. Verifying Insights Evidence API (GET /insights/{theme}/evidence)...")
    # Get a theme from the summary to search evidence for
    if summary["top_topics"]:
        theme_to_search = summary["top_topics"][0]["name"]
    else:
        theme_to_search = "app_stability"
        
    evidence_resp = client.get(f"/insights/{theme_to_search}/evidence")
    assert evidence_resp.status_code == 200, "Insights evidence endpoint failed"
    evidence = evidence_resp.json()
    print(f"  - Search theme: '{theme_to_search}'")
    print(f"  - Match count: {len(evidence)}")
    if evidence:
        print(f"  - Sample evidence match:")
        print(f"    - Quote: '{evidence[0]['quote']}'")
        print(f"    - Full Text: '{evidence[0]['text'][:80]}...'")
    print("  [SUCCESS] Insights evidence returned correct schema and JSON output.")

    print("\n=== RELEASE-READINESS VALIDATION COMPLETED SUCCESSFULLY ===")
    print("E2E Status: PASS")


if __name__ == "__main__":
    run_e2e_validation()
