"""Environment validation -- startup checks for all required configuration.

Validates that critical secrets and connection URLs are set before the app starts.
In production (SIGNALDACH_ENV=production), fails hard on missing secrets.
In development, logs warnings but continues with defaults.
"""

import os
import logging
import sys

logger = logging.getLogger(__name__)

# The dev default from config.py -- used to detect unchanged secrets
_DEV_JWT_SECRET = "CHANGE-ME-IN-PRODUCTION-signaldach-dev-secret-key-do-not-use"


class EnvValidationError(Exception):
    """Raised when required environment variables are missing in production."""
    pass


def _get_env() -> str:
    """Return the current environment: 'production' or 'development'."""
    raw = os.environ.get("SIGNALDACH_ENV", "development").lower().strip()
    if raw in ("production", "prod"):
        return "production"
    return "development"


def _is_set(var_name: str) -> bool:
    """Check if an env var is set and non-empty."""
    val = os.environ.get(var_name, "").strip()
    return bool(val)


def _redact(val: str) -> str:
    """Redact a value for safe logging: show first 4 chars + '***'."""
    if not val:
        return ""
    if len(val) <= 6:
        return "***"
    return val[:4] + "***"


def validate_environment() -> dict:
    """Validate all environment variables. Returns a summary dict.

    In production: raises EnvValidationError for missing critical vars.
    In development: logs warnings but continues.

    Returns:
        dict with keys: environment, critical, warnings, info, valid
    """
    env = _get_env()
    is_prod = env == "production"
    critical = {}
    warnings = []
    info = []
    errors = []

    # --- Critical variables (MUST be set in production) ---

    # JWT secret
    jwt_val = os.environ.get("SIGNALDACH_JWT_SECRET_KEY", "").strip()
    if not jwt_val or jwt_val == _DEV_JWT_SECRET:
        critical["SIGNALDACH_JWT_SECRET_KEY"] = "missing_or_default"
        if is_prod:
            errors.append(
                "SIGNALDACH_JWT_SECRET_KEY is not set or uses the dev default. "
                "Generate one: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
    else:
        critical["SIGNALDACH_JWT_SECRET_KEY"] = "set"

    # Database URL
    db_url = os.environ.get("SIGNALDACH_DATABASE_URL", "").strip()
    if not db_url:
        critical["SIGNALDACH_DATABASE_URL"] = "missing"
        if is_prod:
            errors.append("SIGNALDACH_DATABASE_URL must be set in production (no SQLite).")
    elif "sqlite" in db_url.lower() and is_prod:
        critical["SIGNALDACH_DATABASE_URL"] = "sqlite_in_prod"
        errors.append("SQLite is not suitable for production. Use PostgreSQL.")
    else:
        critical["SIGNALDACH_DATABASE_URL"] = "set"

    # Redis URL
    redis_url = os.environ.get("SIGNALDACH_REDIS_URL", "").strip()
    if not redis_url:
        critical["SIGNALDACH_REDIS_URL"] = "missing"
        if is_prod:
            errors.append("SIGNALDACH_REDIS_URL must be set in production.")
    else:
        critical["SIGNALDACH_REDIS_URL"] = "set"
        info.append(f"Redis URL: {_redact(redis_url)}")

    # --- Important variables (SHOULD be set) ---

    has_openai = _is_set("SIGNALDACH_OPENAI_API_KEY")
    has_anthropic = _is_set("SIGNALDACH_ANTHROPIC_API_KEY")
    if not has_openai and not has_anthropic:
        warnings.append("No AI provider key set (OPENAI_API_KEY / ANTHROPIC_API_KEY). Signal analysis will use rule-based fallback.")

    if not _is_set("SIGNALDACH_SENTRY_DSN"):
        warnings.append("Sentry DSN not configured -- no error tracking in production.")

    cors_val = os.environ.get("SIGNALDACH_CORS_ORIGINS", "").strip()
    if cors_val == "*":
        warnings.append("CORS_ORIGINS is set to wildcard '*'. Use explicit origins in production.")

    # --- Optional variables (info only) ---

    if not _is_set("SIGNALDACH_RESEND_API_KEY"):
        info.append("Resend API key not set -- email alerts disabled.")

    if not _is_set("SIGNALDACH_TWITTER_BEARER_TOKEN"):
        info.append("Twitter bearer token not set -- social scraping disabled.")

    reddit_id = _is_set("SIGNALDACH_REDDIT_CLIENT_ID")
    reddit_secret = _is_set("SIGNALDACH_REDDIT_CLIENT_SECRET")
    if not reddit_id or not reddit_secret:
        info.append("Reddit credentials not set -- Reddit scraping disabled.")

    # --- Auth status ---
    auth_enabled = os.environ.get("SIGNALDACH_AUTH_ENABLED", "true").lower().strip()
    info.append(f"Auth enabled: {auth_enabled}")

    # --- Determine validity ---
    valid = len(errors) == 0

    if is_prod and not valid:
        for err in errors:
            logger.error("ENV CRITICAL: %s", err)
        raise EnvValidationError(
            f"Missing {len(errors)} critical environment variable(s) for production:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    # In dev mode, log warnings but always valid
    result = {
        "environment": env,
        "critical": critical,
        "warnings": warnings,
        "info": info,
        "valid": valid,
    }

    return result
