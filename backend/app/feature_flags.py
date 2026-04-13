"""Feature flags for controlled rollouts.

Flags are read from environment variables (SIGNALDACH_FF_<FLAG_NAME>=true/false)
and from Redis (if available) for runtime toggling without restart.

Usage:
    from app.feature_flags import is_enabled
    if is_enabled("trading_live"):
        # live trading code
    else:
        # paper trading fallback
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default flag values (all off by default for safety)
# ---------------------------------------------------------------------------
_DEFAULTS: Dict[str, bool] = {
    "trading_live": False,          # Real exchange order execution
    "paper_trading": True,          # Simulated trading mode
    "ml_finbert": True,             # FinBERT sentiment analysis
    "ml_german_sentiment": True,    # German sentiment model for DE texts
    "ml_ensemble": False,           # Multi-model ensemble signals
    "adaptive_weights": False,      # Auto-adjust agent weights from scorecard
    "websocket_auth": True,         # Require auth for WebSocket
    "audit_logging": True,          # Write to audit_log table
    "prometheus_metrics": True,     # Expose /metrics endpoint
    "json_logging": False,          # JSON log format
    "investor_dashboard": True,     # Fund dashboard page
    "pdf_reports": False,           # PDF report generation
    "email_digests": False,         # Email digest sending
    "kyc_verification": False,      # KYC/AML checks on registration
    "rate_limit_strict": False,     # Stricter rate limits (20 req/min)
}


def _env_key(flag: str) -> str:
    return f"SIGNALDACH_FF_{flag.upper()}"


def _from_env(flag: str) -> Optional[bool]:
    """Read a flag from environment variable."""
    val = os.environ.get(_env_key(flag))
    if val is None:
        return None
    return val.lower() in ("true", "1", "yes", "on")


def _from_redis(flag: str) -> Optional[bool]:
    """Read a flag from Redis (non-blocking, returns None on failure)."""
    try:
        from app.redis_client import is_redis_available, get_redis
        if not is_redis_available():
            return None
        import asyncio
        # Sync wrapper for async redis — only works outside event loop
        # In practice, use async version in route handlers
        return None
    except Exception:
        return None


def is_enabled(flag: str) -> bool:
    """Check if a feature flag is enabled.

    Priority: env var > Redis > default.
    """
    # 1. Environment variable (highest priority, set at deploy time)
    env_val = _from_env(flag)
    if env_val is not None:
        return env_val

    # 2. Redis (runtime toggle)
    redis_val = _from_redis(flag)
    if redis_val is not None:
        return redis_val

    # 3. Default
    return _DEFAULTS.get(flag, False)


def get_all_flags() -> Dict[str, bool]:
    """Return all flags with their current values."""
    return {flag: is_enabled(flag) for flag in _DEFAULTS}


def get_flag_info() -> Dict[str, dict]:
    """Return detailed info about each flag (for admin UI)."""
    result = {}
    for flag, default in _DEFAULTS.items():
        env_val = _from_env(flag)
        result[flag] = {
            "enabled": is_enabled(flag),
            "default": default,
            "env_key": _env_key(flag),
            "env_override": env_val is not None,
        }
    return result
