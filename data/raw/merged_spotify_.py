import pandas as pd
from pathlib import Path

current_folder = Path(__file__).resolve().parent
file_path = current_folder / "spotify_reviews.csv"

df = pd.read_csv(file_path)

print("Columns:", df.columns.tolist())

platform_counts = df["platform"].value_counts()

print("App Store reviews:", platform_counts.get("App Store", 0))
print("Play Store reviews:", platform_counts.get("Play Store", 0))
print("Total reviews:", len(df))