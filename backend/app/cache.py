"""Redis-backed query result caching for frequently accessed data.

Provides helper functions for caching API responses using the existing
redis_client module. Falls back gracefully when Redis is unavailable
(returns uncached results via the in-memory fallback in redis_client).

Cache Strategy:
- Market Summary: 30s TTL (changes frequently)
- Market Prices: 15s TTL (real-time data)
- Signal Analysis: 60s TTL (AI computation expensive)
- Scorecard: 5min TTL (rarely changes)
- Fund Risk Limits: 10min TTL (static config)
- Feature Flags: 30s TTL
- NAV: 60s TTL
- Compliance Score: 10min TTL
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Cache TTLs (seconds)
CACHE_TTLS = {
    "market_summary": 30,
    "market_prices": 15,
    "signal_analysis": 60,
    "scorecard": 300,
    "risk_limits": 600,
    "feature_flags": 30,
    "nav": 60,
    "compliance_score": 600,
}

# Key prefix to namespace cache entries
_PREFIX = "cache:"


async def cache_get(key: str) -> Optional[dict]:
    """Get a cached JSON value from Redis (or in-memory fallback).

    Args:
        key: Cache key (will be auto-prefixed with 'cache:').

    Returns:
        Parsed dict/list, or None if not found / expired.
    """
    try:
        from app.redis_client import cache_get_json
        return await cache_get_json(f"{_PREFIX}{key}")
    except Exception as e:
        logger.debug("Cache miss for %s: %s", key, e)
    return None


async def cache_set(key: str, value: Any, ttl: int = 60) -> None:
    """Set a cached JSON value with TTL.

    Args:
        key: Cache key (will be auto-prefixed with 'cache:').
        value: Value to cache (must be JSON-serializable).
        ttl: Time-to-live in seconds (default 60).
    """
    try:
        from app.redis_client import cache_set_json
        await cache_set_json(f"{_PREFIX}{key}", value, ttl)
    except Exception as e:
        logger.debug("Cache set failed for %s: %s", key, e)


async def cache_delete(pattern: str) -> int:
    """Delete cached values matching a key.

    Note: For the in-memory fallback, only exact key deletion is supported.
    For Redis, this deletes the exact key. Use cache_delete_pattern for
    pattern-based deletion when Redis is available.

    Args:
        pattern: Exact cache key to delete (auto-prefixed with 'cache:').

    Returns:
        Number of keys deleted (0 if unavailable or key not found).
    """
    try:
        from app.redis_client import cache_delete as _redis_delete
        await _redis_delete(f"{_PREFIX}{pattern}")
        return 1
    except Exception:
        pass
    return 0


def cache_key(*parts: str) -> str:
    """Build a deterministic cache key from parts.

    Example:
        cache_key("scorecard", "BTC/USDT", "composite") -> "scorecard:BTC/USDT:composite"
    """
    return ":".join(str(p) for p in parts)
