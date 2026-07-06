# # pip install google-play-scraper pandas

# from google_play_scraper import reviews, Sort
# import pandas as pd
# import time
# import re

# APP_ID = "com.spotify.music"

# # Your target: change to 22000 if needed
# TARGET_MATCHES = 20000

# # "Global" approximation: add more countries if you want broader coverage
# COUNTRIES = [
#     "us", "gb", "in", "ca", "au", "de", "fr", "br", "mx", "jp",
#     "id", "es", "it", "nl", "se", "no", "za", "sg", "ph", "tr"
# ]

# # Main language setting for request; reviews may still contain mixed content
# LANG = "en"

# KEYWORDS = [
#     "recommendation",
#     "recommend",
#     "suggested songs",
#     "suggested artists",
#     "suggested playlists",
#     "personalized",
#     "ai dj",
#     "discover weekly",
#     "release radar",
#     "daily mix",
#     "autoplay",
#     "radio"
# ]

# OUTPUT_FILE = "spotify_recommendation_reviews_latest.csv"

# def clean_text(text):
#     if text is None:
#         return ""
#     return re.sub(r"\s+", " ", str(text).strip()).lower()

# def keyword_match(text, keywords):
#     t = clean_text(text)
#     matched = [kw for kw in keywords if kw.lower() in t]
#     return matched

# all_matches = []
# seen_review_ids = set()

# for country in COUNTRIES:
#     print(f"\nFetching country: {country}")
#     token = None
#     country_pages = 0

#     while len(all_matches) < TARGET_MATCHES:
#         try:
#             result, token = reviews(
#                 APP_ID,
#                 lang=LANG,
#                 country=country,
#                 sort=Sort.NEWEST,
#                 count=200,
#                 continuation_token=token
#             )
#         except Exception as e:
#             print(f"Error in country {country}: {e}")
#             break

#         if not result:
#             print(f"No more reviews for {country}")
#             break

#         country_pages += 1
#         print(f"Country {country} | page {country_pages} | fetched {len(result)} reviews")

#         for r in result:
#             review_id = r.get("reviewId")
#             content = r.get("content", "")
#             matched_keywords = keyword_match(content, KEYWORDS)

#             if matched_keywords and review_id not in seen_review_ids:
#                 seen_review_ids.add(review_id)
#                 all_matches.append({
#                     "reviewId": review_id,
#                     "userName": r.get("userName"),
#                     "score": r.get("score"),
#                     "at": r.get("at"),
#                     "content": r.get("content"),
#                     "country": country,
#                     "appVersion": r.get("appVersion"),
#                     "reviewCreatedVersion": r.get("reviewCreatedVersion"),
#                     "thumbsUpCount": r.get("thumbsUpCount"),
#                     "matched_keywords": ", ".join(matched_keywords)
#                 })

#                 if len(all_matches) % 100 == 0:
#                     print(f"Matched reviews so far: {len(all_matches)}")

#                 if len(all_matches) >= TARGET_MATCHES:
#                     break

#         if len(all_matches) >= TARGET_MATCHES:
#             break

#         if token is None:
#             print(f"No continuation token left for {country}")
#             break

#         time.sleep(0.5)

#     if len(all_matches) >= TARGET_MATCHES:
#         break

# df = pd.DataFrame(all_matches)

# if not df.empty:
#     df["at"] = pd.to_datetime(df["at"], errors="coerce")
#     df = df.sort_values("at", ascending=False)
#     df = df.head(TARGET_MATCHES)
#     df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

#     print(f"\nTotal matched ad reviews: {len(df)}")
#     print(f"Saved latest filtered set: {len(df)}")
#     print(f"Output file: {OUTPUT_FILE}")
# else:
#     print("No matching reviews found.")


# pip install pandas

import pandas as pd
import re

INPUT_FILE = "spotify_reviews_cleaned.csv"
OUTPUT_FILE = "spotify_personalization_latest_22000.csv"
TARGET_MATCHES = 22000

PERSONALIZATION_KEYWORDS = [
    "personalized",
    "knows my taste",
    "doesn't understand me",
    "doesnt understand me",
    "irrelevant",
    "similar music",
    "mood",
    "preferences"
]

def normalize_text(text):
    if pd.isna(text):
        return ""
    text = str(text).lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text

def find_matches(text, keywords):
    t = normalize_text(text)
    return [kw for kw in keywords if kw.lower() in t]

df = pd.read_csv(INPUT_FILE)

if "content" not in df.columns:
    raise ValueError("The input CSV must have a 'content' column.")

if "at" in df.columns:
    df["at"] = pd.to_datetime(df["at"], errors="coerce")

df["matched_keywords"] = df["content"].apply(lambda x: find_matches(x, PERSONALIZATION_KEYWORDS))
filtered = df[df["matched_keywords"].apply(len) > 0].copy()

filtered["theme"] = "Personalization"
filtered["matched_keywords"] = filtered["matched_keywords"].apply(lambda x: ", ".join(x))

if "at" in filtered.columns:
    filtered = filtered.sort_values("at", ascending=False)

filtered = filtered.head(TARGET_MATCHES)
filtered.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

print("Done.")
print(f"Total matched personalization reviews: {len(filtered)}")
print(f"Saved latest filtered set: {len(filtered)}")
print(f"Output file: {OUTPUT_FILE}")