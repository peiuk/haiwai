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
    # 每日 AI 资讯用的模型（PRD 附录同名变量）。LLM_API_BASE 留空用 Claude；
    # 填了就走 OpenAI 兼容接口（OpenAI、DeepSeek、通义千问等，填到 /v1 为止），此时 LLM_MODEL 必填。
    llm_api_base: str = ""
    llm_api_key: str = ""
    llm_model: str = ""  # 留空且用 Claude 时默认 claude-opus-5-5
    # 发帖、转发、建房间等是否要求先验证手机。测试期间可在 .env 里写 REQUIRE_PHONE_VERIFICATION=false 临时关掉。
    require_phone_verification: bool = True
    upload_dir: str = "data/uploads"
    # 对象存储（S3 协议：MinIO、Cloudflare R2、AWS S3 等）。s3_endpoint 留空就用上面的本地磁盘。
    s3_endpoint: str = ""  # 例：https://s3.example.com（MinIO 的 API 地址）
    s3_bucket: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = "us-east-1"  # MinIO 不关心区域，保持默认即可
    # 用户浏览器取图片 / 视频的地址前缀（桶要允许匿名读）。留空时用 {s3_endpoint}/{s3_bucket}。
    media_public_url: str = ""
    # 跑单元测试时为 True（tests/conftest.py 设置）：跳过外网检查和开发库自动初始化。
    testing: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
