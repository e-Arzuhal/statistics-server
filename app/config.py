from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "e-Arzuhal Statistics Service"
    app_version: str = "1.0.0"

    database_url: str = "sqlite:///./statistics.db"

    recommendation_threshold: float = 30.0  # % usage to recommend a feature
    recommendation_top_n: int = 5

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
