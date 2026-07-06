import pandas as pd

files = [
    r"C:\Users\keert\Desktop\spotify app play keyword reviews\raw_appstore_reviews.csv",
    r"C:\Users\keert\Desktop\spotify app play keyword reviews\raw_playstore_reviews.csv",
    r"C:\Users\keert\Desktop\spotify app play keyword reviews\spotify app play keyword reviews.csv",
    r"C:\Users\keert\Desktop\spotify3theme appstore review scrape\spotify3theme appstore review scrape.csv",
    r"C:\Users\keert\Desktop\spotify4theme appstore review scrape\spotify4theme appstore review scrape.csv",
    r"C:\Users\keert\Desktop\spotify final playstore data reviews.csv"
]

def norm(c):
    return str(c).strip().lower().replace("\n", " ").replace("-", "_").replace(" ", "_")

alias_map = {
    "review_id": ["review_id", "reviewid", "id", "comment_id"],
    "review": ["review", "content", "review_text", "text", "body", "comment"],
    "date": ["date", "at", "created_at", "timestamp", "datetime"],
    "time": ["time"],
    "username": ["username", "user_name", "user", "author"],
    "country": ["country", "region"],
    "rating": ["rating", "score"],
    "title": ["title", "review_title"],
    "version": ["version", "appversion", "reviewcreatedversion", "app_version"],
    "app_id": ["app_id", "appid"],
    "store": ["store"],
}

standard_cols = [
    "review_id", "review", "date", "time", "username", "country",
    "rating", "title", "version", "app_id", "store"
]

def standardize(df):
    df = df.copy()
    df.columns = [norm(c) for c in df.columns]

    rename = {}
    for std_col, aliases in alias_map.items():
        for a in aliases:
            a = norm(a)
            if a in df.columns:
                rename[a] = std_col
                break

    df = df.rename(columns=rename)

    for col in standard_cols:
        if col not in df.columns:
            df[col] = pd.NA

    return df

all_dfs = []
for file in files:
    try:
        df = pd.read_csv(file)
        df = standardize(df)
        df["source_file"] = file
        all_dfs.append(df)
        print(f"Loaded: {file} -> {df.shape}")
    except Exception as e:
        print(f"Skipped: {file} -> {e}")

if not all_dfs:
    raise ValueError("No files were loaded. Check file paths and CSV formatting.")

combined = pd.concat(all_dfs, ignore_index=True, sort=False)

dedupe_cols = [
    "review_id", "review", "date", "time", "username",
    "country", "rating", "title", "version", "app_id", "store"
]

for col in dedupe_cols:
    combined[col] = (
        combined[col]
        .astype("string")
        .str.strip()
        .str.lower()
        .replace({"nan": pd.NA, "none": pd.NA, "": pd.NA})
    )

final_reviews = combined.drop_duplicates(subset=dedupe_cols, keep="first")

output_path = r"C:\Users\keert\Desktop\spotify final reviews dataset.csv"
final_reviews.to_csv(output_path, index=False, encoding="utf-8-sig")

print(f"Saved: {output_path}")
print(f"Rows before: {len(combined)}")
print(f"Rows after: {len(final_reviews)}")
print(f"Removed: {len(combined) - len(final_reviews)}")