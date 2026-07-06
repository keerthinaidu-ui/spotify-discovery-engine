import re
import json
import time
import signal
import atexit
from pathlib import Path
from datetime import datetime, UTC

import pandas as pd
import appstorescraper

APP_ID = "324684580"
COUNTRY = "us"
TARGET_PER_THEME = 1000
BATCH_SIZE = 100
SAVE_EVERY = 200
SLEEP_SECONDS = 1.2

DESKTOP = Path.home() / "Desktop"
BASE_NAME = "spotify4theme appstore review scrape"

PROGRESS_JSON = DESKTOP / f"{BASE_NAME}_progress.json"
MASTER_CSV = DESKTOP / f"{BASE_NAME}.csv"
DEBUG_JSON = DESKTOP / f"{BASE_NAME}_debug.json"

THEME_FILES = {
    "discovery": DESKTOP / "app discovery review.csv",
    "repetitive": DESKTOP / "app repetitive review.csv",
    "playlist": DESKTOP / "app playlist review.csv",
    "recommendation": DESKTOP / "app recommendation review.csv",
}

THEMES = {
    "recommendation": [
        "recommendation", "recommend", "recommended",
        "algorithm", "suggestions", "suggested songs"
    ],
    "discovery": [
        "discover", "discovery", "find new music",
        "new songs", "explore music", "hidden gems",
        "new artists"
    ],
    "playlist": [
        "discover weekly", "daily mix", "release radar",
        "ai dj", "smart shuffle", "radio", "autoplay",
        "made for you"
    ],
    "repetitive": [
        "same songs", "same artists", "repetitive",
        "repeats", "stuck", "plays the same music"
    ],
}

THEME_REGEX = {
    theme: re.compile("|".join(re.escape(k) for k in keywords), re.I)
    for theme, keywords in THEMES.items()
}

collected = {theme: [] for theme in THEMES}
seen_ids = set()
new_since_last_save = 0
stop_requested = False
current_offset = 0
debug_samples = []

def now_utc():
    return datetime.now(UTC).isoformat()

def normalize_text(text):
    return re.sub(r"\s+", " ", str(text or "").strip())

def make_review_uid(review):
    parts = [
        str(review.get("id", "")),
        str(review.get("userName", "")),
        str(review.get("date", "")),
        str(review.get("rating", "")),
        normalize_text(review.get("title", ""))[:150],
        normalize_text(review.get("review", ""))[:300],
    ]
    return " || ".join(parts)

def classify_review(text):
    matches = []
    for theme, pattern in THEME_REGEX.items():
        if pattern.search(text):
            matches.append(theme)
    return matches

def theme_counts():
    return {theme: len(rows) for theme, rows in collected.items()}

def targets_met():
    return all(len(collected[t]) >= TARGET_PER_THEME for t in collected)

def flatten_reviews(obj):
    flat = []

    def _walk(x):
        if isinstance(x, dict):
            flat.append(x)
        elif isinstance(x, (list, tuple)):
            for item in x:
                _walk(item)
        elif x is not None:
            debug_samples.append({
                "type": str(type(x)),
                "value_preview": str(x)[:500],
                "saved_at": now_utc()
            })

    _walk(obj)
    return flat

def load_progress():
    global current_offset, collected, seen_ids, debug_samples

    if not PROGRESS_JSON.exists():
        return

    with open(PROGRESS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    current_offset = data.get("current_offset", 0)

    for theme in THEMES:
        collected[theme] = data.get("collected", {}).get(theme, [])

    seen_ids = set(data.get("seen_ids", []))
    debug_samples = data.get("debug_samples", [])

    print(f"Resumed from progress file. Offset={current_offset}")
    print("Current counts:", theme_counts())

def save_csv(path, rows):
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=[
            "theme", "app_id", "country", "review_id", "author",
            "title", "review", "rating", "date", "matched_keywords",
            "source_offset", "saved_at"
        ])
    df.to_csv(path, index=False, encoding="utf-8-sig")

def save_all():
    payload = {
        "current_offset": current_offset,
        "seen_ids": list(seen_ids),
        "collected": collected,
        "debug_samples": debug_samples[-50:],
        "saved_at": now_utc()
    }

    with open(PROGRESS_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    with open(DEBUG_JSON, "w", encoding="utf-8") as f:
        json.dump(debug_samples[-50:], f, ensure_ascii=False, indent=2)

    all_rows = []
    for theme, rows in collected.items():
        capped = rows[:TARGET_PER_THEME]
        save_csv(THEME_FILES[theme], capped)
        all_rows.extend(capped)

    save_csv(MASTER_CSV, all_rows)
    print("Progress saved.")
    print("Counts:", theme_counts())

def save_and_exit(signum=None, frame=None):
    global stop_requested
    if stop_requested:
        return
    stop_requested = True
    print("\nStopping... saving everything collected so far.")
    save_all()
    raise SystemExit(0)

def setup_exit_handlers():
    signal.signal(signal.SIGINT, save_and_exit)
    signal.signal(signal.SIGTERM, save_and_exit)
    atexit.register(save_all)

def get_app():
    return appstorescraper.get_app(app_id=APP_ID, country=COUNTRY)

def extract_reviews(app, count=100, offset=0):
    raw = app.get_reviews(count=count, offset=offset)
    flat = flatten_reviews(raw)
    return flat, raw

def enrich_review(raw_review, theme, matched_keywords, source_offset):
    date_val = raw_review.get("date", "")
    if hasattr(date_val, "isoformat"):
        date_val = date_val.isoformat()
    else:
        date_val = str(date_val)

    return {
        "theme": theme,
        "app_id": APP_ID,
        "country": COUNTRY,
        "review_id": make_review_uid(raw_review),
        "author": raw_review.get("userName", ""),
        "title": normalize_text(raw_review.get("title", "")),
        "review": normalize_text(raw_review.get("review", "")),
        "rating": raw_review.get("rating", ""),
        "date": date_val,
        "matched_keywords": ", ".join(matched_keywords),
        "source_offset": source_offset,
        "saved_at": now_utc()
    }

def main():
    global current_offset, new_since_last_save

    setup_exit_handlers()
    load_progress()

    app = get_app()

    print("Starting collection...")
    print("Target counts:", {k: TARGET_PER_THEME for k in THEMES})
    print("Current counts:", theme_counts())

    while not targets_met():
        batch, raw_response = extract_reviews(app, count=BATCH_SIZE, offset=current_offset)

        if not batch:
            debug_samples.append({
                "type": "empty_batch",
                "raw_type": str(type(raw_response)),
                "raw_preview": str(raw_response)[:1000],
                "offset": current_offset,
                "saved_at": now_utc()
            })
            print("No more reviews returned from source.")
            break

        added_this_batch = 0

        for raw in batch:
            if not isinstance(raw, dict):
                debug_samples.append({
                    "type": "non_dict_review_item",
                    "item_type": str(type(raw)),
                    "item_preview": 