import os
import sys
import json
import sqlite3
import logging
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("backfill_voc")

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
db_file = os.path.abspath(os.path.join(backend_dir, "..", "data", "spotify_review_engine.db"))

def map_voc_fields(text, title, category, rating):
    text_lower = (text or "").lower()
    title_lower = (title or "").lower()
    combined = f"{title_lower} {text_lower}"
    
    # Defaults
    listening_job = "general music playback"
    desired_outcome = "satisfactory listening experience"
    blocked_goal = "unspecified issue"
    root_cause = "unknown product limitation"
    user_segment_signals = []
    recommendation_pain_type = "none"
    evidence_quote = text[:100] + "..." if len(text) > 100 else text
    
    # Sentiment calculation
    sentiment = "unknown"
    if rating is not None:
        if rating >= 4.0:
            sentiment = "positive"
        elif rating <= 2.0:
            sentiment = "negative"
        else:
            sentiment = "neutral"
            
    # 1. User Segment Signals
    if "premium" in combined or "subscri" in combined or "pay" in combined:
        user_segment_signals.append("premium_subscriber")
    elif "free" in combined or "ad " in combined or "ads" in combined:
        user_segment_signals.append("free_tier")
    if "car" in combined or "drive" in combined or "play" in combined:
        user_segment_signals.append("carplay_user")
    if "bluetooth" in combined or "speaker" in combined or "headphone" in combined:
        user_segment_signals.append("bluetooth_user")
    if not user_segment_signals:
        user_segment_signals.append("unknown")

    # 2. Heuristics based on issue_category
    if category == "Discovery & Recommendation":
        listening_job = "discovering new music and artists"
        if any(w in combined for w in ["same", "repetitive", "repeat", "loop", "stale", "again"]):
            recommendation_pain_type = "repetitive_recommendations"
            desired_outcome = "diverse and fresh recommendation queue"
            blocked_goal = "getting trapped in a repetitive playlist loop"
            root_cause = "recommendation algorithm over-indexing on recent history"
        elif any(w in combined for w in ["taste", "wrong", "not my", "like", "profile"]):
            recommendation_pain_type = "wrong_taste_alignment"
            desired_outcome = "taste-aligned music recommendations"
            blocked_goal = "receiving irrelevant recommendation mixes"
            root_cause = "poor profile mapping or algorithm misalignment"
        elif any(w in combined for w in ["control", "customize", "hide", "block", "filter"]):
            recommendation_pain_type = "missing_customization"
            desired_outcome = "greater control over discovery feeds"
            blocked_goal = "inability to block or tune recommendations"
            root_cause = "lack of user-facing recommendation controls"
        else:
            recommendation_pain_type = "stale_recommendations"
            desired_outcome = "regular updates to personalized mixes"
            blocked_goal = "encountering stagnant recommendations"
            root_cause = "recommendation database refresh lag"
            
    elif category == "Playback Reliability":
        listening_job = "uninterrupted background listening"
        desired_outcome = "continuous and smooth audio playback"
        if "pause" in combined:
            blocked_goal = "random playback pausing"
            root_cause = "buffer underflow or bluetooth connection drop"
        elif "skip" in combined:
            blocked_goal = "unwanted song skipping"
            root_cause = "audio decoder failure or playlist control lag"
        else:
            blocked_goal = "audio stuttering or buffering"
            root_cause = "network socket timeout or media player lag"
            
    elif category == "Stability":
        listening_job = "stable application usage"
        desired_outcome = "crash-free app operation"
        if "crash" in combined:
            blocked_goal = "app crashes on startup or launch"
            root_cause = "fatal null pointer exception or system incompatibility"
        else:
            blocked_goal = "app freezing or locking up"
            root_cause = "main UI thread block or deadlock"
            
    elif category == "Ads & Free Tier":
        listening_job = "free music streaming"
        desired_outcome = "non-intrusive ad breaks"
        blocked_goal = "excessive or loud advertisement interruptions"
        root_cause = "aggressive ad-server dispatch frequency policy"
        
    elif category == "Offline Access":
        listening_job = "offline song playback"
        desired_outcome = "listening to music without cellular data"
        blocked_goal = "downloaded songs failing to play offline"
        root_cause = "local database cache validation or DRM token expiration"
        
    elif category == "Library & Playlists":
        listening_job = "playlist organization and library management"
        desired_outcome = "easy management of saved tracks"
        blocked_goal = "songs disappearing from playlist or reordering failure"
        root_cause = "local cache synchronization lag with remote servers"

    # Find a good sentence from text for evidence_quote
    sentences = [s.strip() for s in text.split(".") if s.strip()]
    if sentences:
        for s in sentences:
            if any(w in s.lower() for w in ["crashes", "crash", "pause", "skip", "recommend", "premium", "ads"]):
                evidence_quote = s
                break
        else:
            evidence_quote = sentences[0]
            
    return sentiment, listening_job, desired_outcome, blocked_goal, root_cause, json.dumps(user_segment_signals), recommendation_pain_type, evidence_quote

def run_backfill():
    logger.info(f"Connecting to database at {db_file}...")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # 1. Fetch all items lacking listening_job
    logger.info("Fetching items requiring VoC enrichment backfill...")
    cursor.execute("SELECT id, text, title, issue_category, rating_or_score FROM feedback_items WHERE listening_job IS NULL")
    rows = cursor.fetchall()
    total_records = len(rows)
    logger.info(f"Found {total_records} feedback items to process.")
    
    batch_size = 5000
    batch_updates = []
    
    start_time = time.time()
    processed = 0
    
    for idx, (item_id, text, title, category, rating) in enumerate(rows):
        sentiment, job, outcome, goal, cause, signals, pain_type, quote = map_voc_fields(text, title, category, rating)
        batch_updates.append((sentiment, job, outcome, goal, cause, signals, pain_type, quote, item_id))
        processed += 1
        
        if len(batch_updates) >= batch_size:
            cursor.executemany("""
                UPDATE feedback_items 
                SET sentiment = ?, 
                    listening_job = ?, 
                    desired_outcome = ?, 
                    blocked_goal = ?, 
                    root_cause = ?, 
                    user_segment_signals = ?, 
                    recommendation_pain_type = ?, 
                    evidence_quote = ? 
                WHERE id = ?
            """, batch_updates)
            conn.commit()
            logger.info(f"Processed {processed} / {total_records} items...")
            batch_updates = []
            
    if batch_updates:
        cursor.executemany("""
            UPDATE feedback_items 
            SET sentiment = ?, 
                listening_job = ?, 
                desired_outcome = ?, 
                blocked_goal = ?, 
                root_cause = ?, 
                user_segment_signals = ?, 
                recommendation_pain_type = ?, 
                evidence_quote = ? 
            WHERE id = ?
        """, batch_updates)
        conn.commit()
        
    logger.info(f"VoC historical backfill completed. Total processed: {processed} in {time.time() - start_time:.2f} seconds.")
    conn.close()

if __name__ == "__main__":
    run_backfill()
