import pandas as pd

file1 = r"C:\Users\keert\spotify-review-engine\data\filtered\1stcombined_cleaned.csv"
file2 = r"C:\Users\keert\spotify-review-engine\spotify_recommendation_reviews_latest20k_cleaned.csv"

df1 = pd.read_csv(file1)
df2 = pd.read_csv(file2)

common_cols = sorted(set(df1.columns) & set(df2.columns))
df1_common = df1[common_cols].copy()
df2_common = df2[common_cols].copy()

combined = pd.concat([df1_common, df2_common], ignore_index=True)

combined["review_text"] = combined.get("review_text", combined["content"])
combined["user_name"] = combined.get("user_name", combined["userName"])
combined["review_id"] = combined.get("review_id", combined["reviewId"])

combined["_dedupe_key"] = (
    combined["review_id"].astype(str).fillna("") + "|" +
    combined["user_name"].astype(str).fillna("") + "|" +
    combined["review_text"].astype(str).fillna("") + "|" +
    combined["score"].astype(str).fillna("") + "|" +
    combined["at"].astype(str).fillna("")
)

combined = combined.drop_duplicates(subset=["_dedupe_key"]).drop(columns=["_dedupe_key"])

output_file = r"C:\Users\keert\spotify-review-engine\data\filtered\spotify_combined_unique.csv"
combined.to_csv(output_file, index=False, encoding="utf-8-sig")

print(f"Saved: {output_file}")
print(f"Rows after merge and dedupe: {len(combined)}")