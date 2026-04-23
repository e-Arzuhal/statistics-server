from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    app_name: str = "e-Arzuhal Statistics Service"
    app_version: str = "1.0.0"
    debug: bool = True
    app_env: str = "development"

    database_url: str = "sqlite:///./statistics.db"

    recommendation_threshold: float = 30.0  # % usage to recommend a feature
    recommendation_top_n: int = 5

    # Security
    allowed_origins: str = "http://localhost:8080"
    internal_api_key: str = ""

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    settings = Settings()

    if settings.app_env.lower() == "production" and "*" in settings.allowed_origins_list:
        raise ValueError("In production, ALLOWED_ORIGINS cannot include '*'.")

    if settings.app_env.lower() == "production" and not settings.database_url.startswith("postgresql"):
        raise ValueError("In production, DATABASE_URL must use PostgreSQL.")

    if settings.app_env.lower() == "production" and not settings.internal_api_key:
        raise ValueError("In production, INTERNAL_API_KEY must be set.")

    return settings
