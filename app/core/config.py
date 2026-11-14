from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    database_url: str = ""
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    app_secret_key: str = "dev-only-change-me-32b-secret-key"
    jwt_access_ttl_minutes: int = 15
    jwt_refresh_ttl_days: int = 7
    llm_api_key: str = ""
    upload_dir: str = "data/uploads"


@lru_cache
def get_settings() -> Settings:
    return Settings()
