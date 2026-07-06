from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DB_PATH = (REPO_ROOT / "data" / "spotify_review_engine.db").as_posix()

(REPO_ROOT / "data").mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", REPO_ROOT / "data" / "raw" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Spotify Review Discovery Engine"
    app_env: str = "development"
    debug: bool = True
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    database_url: str = f"sqlite:///{_DEFAULT_DB_PATH}"

    reviews_csv_path: str = "data/raw/spotify_reviews.csv"

    youtube_api_key: str = ""
    product_hunt_token: str = ""
    product_hunt_access_token: str = ""
    product_hunt_slug: str = "spotify"
    gemini_api_key: str = ""
    groq_api_key: str = ""
    llm_provider: str = "gemini"
    gemini_models: str = "gemini-2.5-flash,gemini-3.1-flash-lite,gemini-3.5-flash,gemini-2.5-flash-lite,gemini-3-flash"
    gemini_embedding_model: str = "gemini-embedding-2"
    embedding_enabled: bool = True
    embedding_top_k: int = 10
    embedding_min_score: float = 0.0
    embedding_output_dimensionality: int | None = None




    log_level: str = "INFO"

    # Worker Settings
    worker_enabled: bool = True
    worker_batch_size: int = 10
    worker_throttle_delay: float = 0.5
    worker_max_retries: int = 3


    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def reviews_csv_absolute(self) -> Path:
        path = Path(self.reviews_csv_path)
        return path if path.is_absolute() else REPO_ROOT / path

    @property
    def gemini_model_list(self) -> list[str]:
        return [m.strip() for m in self.gemini_models.split(",") if m.strip()]



@lru_cache
def get_settings() -> Settings:
    return Settings()
