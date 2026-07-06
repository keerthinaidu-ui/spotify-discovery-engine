import sqlite3
import json
from datetime import datetime, timezone

def bulk_analyse():
    db_path = '../data/spotify_review_engine.db'
    print(f"Connecting to database at {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Retrieve all feedback items
    cursor.execute("SELECT id, text, rating_or_score FROM feedback_items")
    rows = cursor.fetchall()
    total_rows = len(rows)
    print(f"Found {total_rows} feedback items. Processing heuristic analysis...")

    now_str = datetime.now(timezone.utc).isoformat()
    updates = []
    
    for i, (item_id, text, rating) in enumerate(rows):
        text_lower = (text or "").lower()

        # 1. Sentiment classification
        sentiment = "neutral"
        if rating is not None:
            if rating >= 4.0:
                sentiment = "positive"
            elif rating <= 2.0:
                sentiment = "negative"
        else:
            if any(w in text_lower for w in ["good", "love", "great", "excellent", "fast", "best", "perfect", "awesome", "like"]):
                sentiment = "positive"
            elif any(w in text_lower for w in ["bad", "worst", "terrible", "hate", "slow", "fail", "broken", "annoying", "crap"]):
                sentiment = "negative"

        # 2. Category classification
        category = "general_feedback"
        if any(w in text_lower for w in ["crash", "bug", "freeze", "hang", "close", "restart", "shut", "quit"]):
            category = "crashes_and_bugs"
        elif any(w in text_lower for w in ["ui", "ux", "design", "layout", "color", "font", "button", "tab", "screen", "theme", "aesthetic"]):
            category = "ui_ux_design"
        elif any(w in text_lower for w in ["algo", "recommend", "suggest", "discover", "playlist", "feed", "shuffle", "smart"]):
            category = "recommendation_algorithm"
        elif any(w in text_lower for w in ["price", "pay", "bill", "cost", "charge", "card", "sub", "premium", "subscribe"]):
            category = "pricing_and_billing"
        elif any(w in text_lower for w in ["slow", "lag", "performance", "load", "buffer", "speed", "fast"]):
            category = "performance"
        elif any(w in text_lower for w in ["podcast", "show", "episode", "artist", "music", "song", "album", "content"]):
            category = "content_availability"

        # 3. User Segment classification
        segment = "unknown"
        if any(w in text_lower for w in ["premium", "subscribe", "pay", "billing", "sub"]):
            segment = "premium_subscriber"
        elif any(w in text_lower for w in ["free", "ad ", "ads", "advertising"]):
            segment = "free_tier"
        elif any(w in text_lower for w in ["artist", "upload", "creator"]):
            segment = "artist"
        elif any(w in text_lower for w in ["podcast", "episode", "show"]):
            segment = "podcast_listener"

        topics_json = json.dumps([category.replace("_", " ")])
        updates.append((sentiment, category, segment, topics_json, now_str, item_id))

    print("Writing updates to the database...")
    # Execute batch updates
    cursor.executemany("""
        UPDATE feedback_items
        SET sentiment = ?,
            issue_category = ?,
            user_segment = ?,
            topics = ?,
            analyzed_at = ?
        WHERE id = ?
    """, updates)

    conn.commit()
    conn.close()
    print("Bulk analysis migration completed successfully!")

if __name__ == "__main__":
    bulk_analyse()
