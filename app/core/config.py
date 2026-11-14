from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_SECRET_KEY = "dev-only-change-me-32b-secret-key"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 默认 prod：忘了设环境变量时宁可功能受限，也不要开着开发后门上线。本地开发在 .env 里写 APP_ENV=dev。
    app_env: str = "prod"
    database_url: str = ""
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    app_secret_key: str = DEFAULT_SECRET_KEY
    jwt_access_ttl_minutes: int = 15
    jwt_refresh_ttl_days: int = 7
    llm_api_key: str = ""
    upload_dir: str = "data/uploads"


@lru_cache
def get_settings() -> Settings:
    return Settings()
