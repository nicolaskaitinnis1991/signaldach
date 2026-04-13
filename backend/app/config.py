import logging
import os
from typing import List
from pydantic_settings import BaseSettings

_logger = logging.getLogger(__name__)

# Fixed default for development — MUST be overridden via SIGNALDACH_JWT_SECRET_KEY in production
_DEV_JWT_SECRET = "CHANGE-ME-IN-PRODUCTION-signaldach-dev-secret-key-do-not-use"


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite:///signaldach.db"

    # LLM providers (set one or both)
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    llm_provider: str = "auto"  # "openai", "anthropic", or "auto" (tries anthropic first)
    llm_model_openai: str = "gpt-4o-mini"
    llm_model_anthropic: str = "claude-sonnet-4-20250514"

    # External APIs
    resend_api_key: str = ""
    twitter_bearer_token: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "SignalDACH/0.1"

    # Auth
    jwt_secret_key: str = _DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_minutes: int = 10080  # 7 days
    auth_enabled: bool = True

    # Security — override with SIGNALDACH_CORS_ORIGINS="https://app.signaldach.com,https://signaldach.com"
    cors_origins: List[str] = [
        "http://localhost:3002",
        "http://localhost:3000",
    ]
    rate_limit_per_minute: int = 100
    rate_limit_auth_per_minute: int = 20
    rate_limit_user_per_minute: int = 200  # per-user limit (higher than per-IP)
    trusted_proxy_ips: List[str] = ["127.0.0.1", "::1"]

    # Monitoring
    sentry_dsn: str = ""

    # Redis
    redis_url: str = "redis://localhost:6379"
    redis_cache_ttl: int = 60

    # Scraping
    scrape_on_startup: bool = False
    log_level: str = "INFO"
    log_format: str = "text"  # "text" for development, "json" for production

    model_config = {"env_prefix": "SIGNALDACH_", "env_file": ".env"}


settings = Settings()

# Validate jwt_secret_key in production
_is_production = os.environ.get("SIGNALDACH_ENV", "").lower() in ("production", "prod")
if _is_production and settings.jwt_secret_key == _DEV_JWT_SECRET:
    raise RuntimeError(
        "FATAL: SIGNALDACH_JWT_SECRET_KEY must be set to a secure value in production. "
        "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )
