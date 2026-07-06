import os
import sys
import json
import logging
import argparse
import time
import sqlite3
import re

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("backfill_taxonomy")

# Add backend directory to path if needed to resolve database imports
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Canonical Multi-dimensional Taxonomy
PRIMARY_THEMES = [
    "Music Discovery",
    "Recommendations",
    "Playlists",
    "Shuffle Experience",
    "Radio",
    "Search & Browse",
    "Library Management",
    "Social Discovery",
    "Podcast vs Music",
    "Premium vs Free Experience",
    "Unidentified"
]

SECONDARY_TAGS = [
    "Artist Discovery",
    "Genre Exploration",
    "Mood-Based Listening",
    "Activity-Based Listening",
    "Personalization",
    "Recommendation Accuracy",
    "Content Variety",
    "Listening Habits",
    "New Releases",
    "Feature Requests",
    "Recommendation Trust",
    "Discovery Features",
    "Repetitive Listening"
]

# Rule Definitions
PRIMARY_RULES = {
    "Music Discovery": [
        "discover", "discovery", "explore", "exploring", "new music", "new songs", 
        "new artist", "new artists", "find songs", "find artists", "hidden gems", 
        "fresh music", "find new", "discover weekly", "unheard"
    ],
    "Recommendations": [
        "recommendation", "recommendations", "recommend", "suggested", "suggestion", 
        "suggestions", "personalized", "algorithm", "ai dj", "dj", "feed", "mixes", 
        "algorithmic", "recommended", "taste"
    ],
    "Playlists": [
        "playlist", "playlists", "daily mix", "discover weekly", "release radar", 
        "blend", "liked songs", "liked song", "mix feed", "curated", "my playlist"
    ],
    "Shuffle Experience": [
        "shuffle", "shuffling", "smart shuffle", "random", "randomizing", "randomizer"
    ],
    "Radio": [
        "radio", "station", "stations", "autoplay", "song radio", "artist radio"
    ],
    "Search & Browse": [
        "search", "searches", "searching", "browse", "browsing", "find", "query", 
        "genres", "categories", "search results"
    ],
    "Library Management": [
        "library", "save", "saving", "queue", "queueing", "add to queue", "delete playlist", 
        "reorder", "organize", "folders", "saved"
    ],
    "Social Discovery": [
        "friend", "friends", "social", "share", "sharing", "collaborative", "blend"
    ],
    "Podcast vs Music": [
        "podcast", "podcasts", "episodes", "show", "shows", "video podcast", "overlap"
    ],
    "Premium vs Free Experience": [
        "premium", "subscription", "subscribe", "ads", "ad", "pay", "bill", "billing", 
        "free tier", "free version", "payment", "membership", "price", "charge"
    ]
}

SECONDARY_RULES = {
    "Artist Discovery": [
        "similar artist", "new artist", "new artists", "discover artist", "discover artists", 
        "find artist", "artist recommendations", "artist discovery", "underground artist", 
        "indie artist"
    ],
    "Genre Exploration": [
        "genre", "genres", "style", "styles", "jazz", "rock", "pop", "rap", "metal", 
        "classical", "hip hop", "edm", "music style", "exploration", "expand my taste"
    ],
    "Mood-Based Listening": [
        "mood", "moods", "happy", "sad", "chill", "relax", "relaxing", "angry", 
        "emotional", "hype", "energetic", "melancholy", "depressed", "calm"
    ],
    "Activity-Based Listening": [
        "run", "running", "gym", "workout", "sleep", "sleeping", "commute", "commuting", 
        "drive", "driving", "study", "studying", "work", "working", "commute", "car"
    ],
    "Personalization": [
        "personalize", "personalized", "personalisation", "my taste", "my liking", 
        "custom", "tailored", "algorithm fits", "knows my", "taste profile"
    ],
    "Recommendation Accuracy": [
        "wrong song", "not what i like", "garbage recommendations", "bad recs", 
        "mismatch", "accurate", "inaccurate", "wrong suggestions", "don't match"
    ],
    "Content Variety": [
        "variety", "diverse", "diversity", "catalog", "selection", "mix it up", 
        "different songs", "different artists"
    ],
    "Listening Habits": [
        "habit", "habits", "daily", "weekly", "wrapped", "listening stats", 
        "stat", "stats", "year in review", "history"
    ],
    "New Releases": [
        "new release", "new releases", "release radar", "latest", "new track", 
        "new tracks", "new song", "new songs", "just released", "fresh out"
    ],
    "Feature Requests": [
        "add", "feature", "request", "suggestion", "option", "settings", 
        "bring back", "please", "would love", "wish there was", "should add", "i want"
    ],
    "Recommendation Trust": [
        "trust", "rely", "unreliable", "algorithm sucks", "stop using", "downhill", 
        "recommendation trust", "worse"
    ],
    "Discovery Features": [
        "discover weekly", "release radar", "smart shuffle", "ai dj", "dj", "daily mix"
    ],
    "Repetitive Listening": [
        "repeat", "repetitive", "repeat song", "same song", "same songs", "same artist", 
        "same artists", "loop", "loops", "looping", "over and over", "keeps playing same"
    ]
}

def classify_review(text: str | None, title: str | None, rating: float | None):
    combined = []
    if title:
        combined.append(title.lower())
    if text:
        combined.append(text.lower())
    full_text = " ".join(combined).strip()

    # 1. Determine Primary Theme
    theme_scores = {theme: 0 for theme in PRIMARY_THEMES if theme != "Unidentified"}
    for theme, keywords in PRIMARY_RULES.items():
        for kw in keywords:
            theme_scores[theme] += full_text.count(kw)
            
    best_theme = "Unidentified"
    max_score = 0
    for theme, score in theme_scores.items():
        if score > max_score:
            max_score = score
            best_theme = theme
        elif score == max_score and score > 0:
            # Simple tie-break: keep first matched or use Unidentified
            pass

    # 2. Determine Secondary Tags (Multi-label)
    matched_tags = []
    for tag, keywords in SECONDARY_RULES.items():
        for kw in keywords:
            if kw in full_text:
                matched_tags.append(tag)
                break # Matched this tag, move to next

    # 3. Determine Sentiment Tag based on keyword lists as initial indicators
    positive_keywords = [
        "love", "like", "amazing", "awesome", "excellent", "fantastic", "great", "perfect",
        "best", "wonderful", "brilliant", "impressive", "helpful", "easy", "smooth", "fast",
        "accurate", "personalized", "refreshing", "enjoy", "enjoying", "favorite", "happy",
        "satisfied", "recommend", "worth it", "works well", "finally", "thank you", "improved",
        "pleasant", "reliable", "useful", "cool", "nice"
    ]
    neutral_keywords = [
        "okay", "ok", "fine", "average", "decent", "acceptable", "normal",
        "standard", "basic", "fair", "sometimes", "occasionally", "usually",
        "generally", "mostly", "noticed", "observed", "using", "trying",
        "updated", "changed", "feature", "option", "available", "works",
        "can", "could", "would"
    ]
    negative_keywords = [
        "hate", "disappointed", "disappointing", "annoying", "frustrating", "frustrated",
        "terrible", "awful", "bad", "poor", "worst", "broken", "bug", "issue", "problem",
        "error", "crash", "fails", "stuck", "boring", "repetitive", "repeat", "same songs",
        "same artists", "useless", "irrelevant", "inaccurate", "confusing", "slow", "lag",
        "missing", "can't", "cannot", "never", "waste", "refund", "regret"
    ]
    strong_negative_keywords = [
        "uninstall", "cancel", "cancelled", "unsubscribe", "switching", "moving to",
        "leaving", "fed up", "ridiculous", "pathetic", "garbage", "trash", "useless", "scam",
        "hate this app", "never again", "wasted money"
    ]

    def count_hits(keywords):
        hits = 0
        for kw in keywords:
            if kw.isalnum():
                pattern = r'\b' + re.escape(kw) + r'\b'
                matches = re.findall(pattern, full_text)
                hits += len(matches)
            else:
                hits += full_text.count(kw)
        return hits

    pos_hits = count_hits(positive_keywords)
    neu_hits = count_hits(neutral_keywords)
    neg_hits = count_hits(negative_keywords) + count_hits(strong_negative_keywords)

    has_mixed = False
    pos_aspects = []
    neg_aspects = []

    # Map matched tags/keywords to standard aspect categories
    if pos_hits > 0:
        for tag in matched_tags:
            if tag in ("Artist Discovery", "Genre Exploration", "Mood-Based Listening"):
                pos_aspects.append("music_discovery")
            elif tag in ("Personalization", "Recommendation Trust"):
                pos_aspects.append("recommendation_accuracy")
            elif tag in ("Discovery Features", "New Releases"):
                pos_aspects.append("playlist_experience")
        if not pos_aspects:
            pos_aspects.append("other")

    if neg_hits > 0:
        for tag in matched_tags:
            if tag in ("Recommendation Accuracy", "Repetitive Listening"):
                neg_aspects.append("recommendation_accuracy")
            elif tag in ("Discovery Features"):
                neg_aspects.append("playlist_experience")
        if "slow" in full_text or "lag" in full_text or "crash" in full_text or "bug" in full_text:
            neg_aspects.append("app_performance")
        if "ad" in full_text or "premium" in full_text:
            neg_aspects.append("premium_ads")
        if "shuffle" in full_text:
            neg_aspects.append("shuffle_experience")
        if "search" in full_text or "browse" in full_text:
            neg_aspects.append("search_browse")
        if not neg_aspects:
            neg_aspects.append("other")

    pos_aspects = list(set(pos_aspects))
    neg_aspects = list(set(neg_aspects))

    if pos_hits > 0 and neg_hits > 0:
        has_mixed = True

    if pos_hits > neg_hits:
        sentiment = "positive"
    elif neg_hits > pos_hits:
        sentiment = "negative"
    else:
        # Mixed-sentiment or no hits
        if rating is not None:
            if rating >= 4.0:
                sentiment = "positive"
            elif rating <= 2.0:
                sentiment = "negative"
            elif rating == 3.0:
                if has_mixed:
                    sentiment = "positive"
                else:
                    sentiment = "neutral"
            else:
                sentiment = "unclear"
        else:
            if pos_hits > 0:
                sentiment = "unclear"
            elif neu_hits > 0:
                sentiment = "neutral"
            else:
                sentiment = "unclear"

    sentiment_profile = {
        "positive_aspects": pos_aspects,
        "negative_aspects": neg_aspects
    }

    return best_theme, matched_tags, sentiment, has_mixed, sentiment_profile

def run_backfill():
    parser = argparse.ArgumentParser(description="Spotify Review Engine - Multi-Dimensional Taxonomy Migration & Backfill")
    parser.add_argument("--batch-size", type=int, default=1000, help="Batch chunk size for database operations")
    parser.add_argument("--db-path", type=str, default="", help="Custom database file path")
    args = parser.parse_args()

    # Determine database path
    db_file = args.db_path
    if not db_file:
        db_file = os.path.abspath(os.path.join(backend_dir, "..", "data", "spotify_review_engine.db"))
        if not os.path.exists(db_file):
            db_file = os.path.abspath(os.path.join(backend_dir, "..", "test_temp.db"))

    logger.info(f"Connecting to database at {db_file}...")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='feedback_items'")
    if not cursor.fetchone():
        logger.error("feedback_items table does not exist. Aborting.")
        conn.close()
        return

    # Check and add new mixed sentiment columns if missing
    cursor.execute("PRAGMA table_info(feedback_items)")
    columns = [col[1] for col in cursor.fetchall()]
    if "has_mixed_sentiment" not in columns:
        logger.info("Altering database table to add has_mixed_sentiment column...")
        cursor.execute("ALTER TABLE feedback_items ADD COLUMN has_mixed_sentiment BOOLEAN")
        conn.commit()
    if "sentiment_profile" not in columns:
        logger.info("Altering database table to add sentiment_profile column...")
        cursor.execute("ALTER TABLE feedback_items ADD COLUMN sentiment_profile TEXT")
        conn.commit()

    # Fetch all item IDs to build the processing queue
    logger.info("Building queue of feedback items...")
    cursor.execute("SELECT id FROM feedback_items ORDER BY id")
    all_ids = [row[0] for row in cursor.fetchall()]
    total_records = len(all_ids)
    logger.info(f"Found {total_records} records in database.")

    # Process loop
    start_time = time.time()
    processed = 0
    updated = 0
    failed = 0
    
    primary_distribution = {}
    secondary_distribution = {}
    sentiment_distribution = {}

    last_idx = 0
    while last_idx < total_records:
        batch_ids = all_ids[last_idx : last_idx + args.batch_size]
        if not batch_ids:
            break

        logger.info(f"Processing batch: index range [{last_idx} to {last_idx + len(batch_ids)}] of {total_records}...")
        
        placeholders = ",".join("?" for _ in batch_ids)
        cursor.execute(f"SELECT id, text, title, rating_or_score FROM feedback_items WHERE id IN ({placeholders})", batch_ids)
        batch_rows = cursor.fetchall()
        
        row_dict = {row[0]: (row[1], row[2], row[3]) for row in batch_rows}
        batch_updates = []
        
        for item_id in batch_ids:
            if item_id not in row_dict:
                failed += 1
                continue
                
            text, title, rating = row_dict[item_id]
            processed += 1

            try:
                theme, tags, sentiment, has_mixed, profile = classify_review(text, title, rating)
                tags_str = json.dumps(tags)
                
                # dual-write theme into issue_category
                batch_updates.append((
                    theme, 
                    tags_str, 
                    "2.0.0", 
                    "rule_backfill", 
                    0.90, 
                    sentiment, 
                    theme, 
                    "complete", 
                    1 if has_mixed else 0, 
                    json.dumps(profile), 
                    item_id
                ))
                updated += 1

                # Update distributions
                primary_distribution[theme] = primary_distribution.get(theme, 0) + 1
                sentiment_distribution[sentiment] = sentiment_distribution.get(sentiment, 0) + 1
                for tag in tags:
                    secondary_distribution[tag] = secondary_distribution.get(tag, 0) + 1
            except Exception as ex:
                logger.error(f"Failed to classify item {item_id}: {ex}")
                failed += 1

        # Execute batch updates in a transaction
        if batch_updates:
            try:
                cursor.executemany(
                    """UPDATE feedback_items 
                       SET primary_theme = ?, 
                           secondary_tags = ?, 
                           taxonomy_version = ?, 
                           classification_source = ?, 
                           classification_confidence = ?, 
                           sentiment = ?,
                           issue_category = ?,
                           analysis_status = ?,
                           has_mixed_sentiment = ?,
                           sentiment_profile = ?
                       WHERE id = ?""", 
                    batch_updates
                )
                conn.commit()
            except Exception as dberr:
                conn.rollback()
                logger.error(f"Database batch update transaction failed: {dberr}")
                failed += len(batch_updates)
                updated -= len(batch_updates)

        # Advance checkpoint index
        last_idx += len(batch_ids)
        time.sleep(0.01)

    duration = time.time() - start_time
    logger.info("=========================================")
    logger.info("       BACKFILL JOB COMPLETION REPORT    ")
    logger.info("=========================================")
    logger.info(f"Total reviews in database: {total_records}")
    logger.info(f"Total processed:           {processed}")
    logger.info(f"Total updated:             {updated}")
    logger.info(f"Total failed:              {failed}")
    logger.info(f"Total execution time:      {duration:.2f} seconds")
    logger.info(f"Average processing speed:  {processed / max(duration, 0.1):.1f} reviews/sec")
    logger.info(f"Primary Theme Distribution: {json.dumps(primary_distribution, indent=2)}")
    logger.info(f"Secondary Tag Distribution: {json.dumps(secondary_distribution, indent=2)}")
    logger.info(f"Sentiment Distribution:    {json.dumps(sentiment_distribution, indent=2)}")
    logger.info("=========================================")

if __name__ == "__main__":
    run_backfill()
