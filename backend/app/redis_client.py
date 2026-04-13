"""Unified Redis client for SignalDACH.

Provides:
- Async Redis connection pool (redis[hiredis])
- Cache get/set with TTL
- Pub/Sub publish/subscribe
- Redis Streams for event bus
- Graceful degradation to in-memory fallback when Redis is unavailable

Configuration:
    SIGNALDACH_REDIS_URL  (default: redis://localhost:6379)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, AsyncIterator, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory fallback (used when Redis is not available)
# ---------------------------------------------------------------------------

class _InMemoryCache:
    """Minimal in-memory cache used as fallback when Redis is unavailable."""

    def __init__(self):
        self._store: dict[str, tuple[Any, float]] = {}  # key -> (value, expire_at)

    def get(self, key: str) -> Optional[str]:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expire_at = entry
        if expire_at and time.monotonic() > expire_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: str, ttl: int = 60) -> None:
        expire_at = time.monotonic() + ttl if ttl > 0 else 0
        self._store[key] = (value, expire_at)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def cleanup(self) -> None:
        now = time.monotonic()
        expired = [k for k, (_, exp) in self._store.items() if exp and now > exp]
        for k in expired:
            del self._store[k]


_fallback_cache = _InMemoryCache()

# ---------------------------------------------------------------------------
# Redis connection state
# ---------------------------------------------------------------------------

_redis_pool: Any = None  # redis.asyncio.Redis instance or None
_redis_available: bool = False


def _get_redis_url() -> str:
    return os.environ.get("SIGNALDACH_REDIS_URL", "redis://localhost:6379")


async def init_redis() -> None:
    """Initialize the async Redis connection pool. Call during FastAPI startup."""
    global _redis_pool, _redis_available

    try:
        import redis.asyncio as aioredis

        url = _get_redis_url()
        _redis_pool = aioredis.from_url(
            url,
            decode_responses=True,
            max_connections=20,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )
        # Test connectivity
        await _redis_pool.ping()
        _redis_available = True
        logger.info("Redis connected at %s", url)
    except ImportError:
        logger.warning("redis package not installed -- falling back to in-memory cache")
        _redis_pool = None
        _redis_available = False
    except Exception as e:
        logger.warning("Redis unavailable (%s) -- falling back to in-memory cache", e)
        _redis_pool = None
        _redis_available = False


async def shutdown_redis() -> None:
    """Close the Redis connection pool. Call during FastAPI shutdown."""
    global _redis_pool, _redis_available
    if _redis_pool is not None:
        try:
            await _redis_pool.aclose()
        except Exception as e:
            logger.debug("Error closing Redis: %s", e)
    _redis_pool = None
    _redis_available = False
    logger.info("Redis connection closed")


def is_redis_available() -> bool:
    """Check if Redis is currently connected and available."""
    return _redis_available


async def get_redis():
    """Return the async Redis client, or None if unavailable."""
    if _redis_available and _redis_pool is not None:
        try:
            await _redis_pool.ping()
            return _redis_pool
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

async def cache_get(key: str, ttl_fallback: Optional[int] = None) -> Optional[str]:
    """Get a cached value from Redis, falling back to in-memory.

    Args:
        key: Cache key.
        ttl_fallback: Not used for get, reserved for future use.

    Returns:
        The cached string value, or None if not found / expired.
    """
    r = await get_redis()
    if r is not None:
        try:
            return await r.get(key)
        except Exception as e:
            logger.debug("Redis cache_get error for key %s: %s", key, e)
    # Fallback to in-memory
    return _fallback_cache.get(key)


async def cache_set(key: str, value: str, ttl: int = 60) -> None:
    """Set a cached value with TTL in Redis, falling back to in-memory.

    Args:
        key: Cache key.
        value: String value to cache.
        ttl: Time-to-live in seconds (default 60).
    """
    r = await get_redis()
    if r is not None:
        try:
            await r.set(key, value, ex=ttl)
            return
        except Exception as e:
            logger.debug("Redis cache_set error for key %s: %s", key, e)
    # Fallback to in-memory
    _fallback_cache.set(key, value, ttl)


async def cache_delete(key: str) -> None:
    """Delete a cached value."""
    r = await get_redis()
    if r is not None:
        try:
            await r.delete(key)
            return
        except Exception as e:
            logger.debug("Redis cache_delete error for key %s: %s", key, e)
    _fallback_cache.delete(key)


async def cache_get_json(key: str) -> Optional[Any]:
    """Get and JSON-decode a cached value."""
    raw = await cache_get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


async def cache_set_json(key: str, value: Any, ttl: int = 60) -> None:
    """JSON-encode and cache a value."""
    await cache_set(key, json.dumps(value, default=str), ttl)


# ---------------------------------------------------------------------------
# Pub/Sub
# ---------------------------------------------------------------------------

async def publish(channel: str, message: Any) -> int:
    """Publish a message to a Redis Pub/Sub channel.

    Args:
        channel: Channel name.
        message: Message (will be JSON-encoded if not a string).

    Returns:
        Number of subscribers that received the message (0 if fallback).
    """
    if isinstance(message, str):
        payload = message
    else:
        payload = json.dumps(message, default=str)

    r = await get_redis()
    if r is not None:
        try:
            return await r.publish(channel, payload)
        except Exception as e:
            logger.debug("Redis publish error on channel %s: %s", channel, e)
    return 0


async def subscribe(channel: str) -> AsyncIterator[str]:
    """Subscribe to a Redis Pub/Sub channel and yield messages.

    Yields message strings as they arrive. Falls back gracefully if Redis
    is unavailable (yields nothing and returns).
    """
    r = await get_redis()
    if r is None:
        logger.debug("Redis unavailable, cannot subscribe to %s", channel)
        return

    try:
        pubsub = r.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for raw_msg in pubsub.listen():
                if raw_msg["type"] == "message":
                    yield raw_msg["data"]
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
    except Exception as e:
        logger.warning("Redis subscribe error on channel %s: %s", channel, e)


# ---------------------------------------------------------------------------
# Redis Streams (Event Bus)
# ---------------------------------------------------------------------------

# Standard stream names for the SignalDACH event bus
STREAM_PRICES = "signals:prices"
STREAM_NEWS = "signals:news"
STREAM_ONCHAIN = "signals:onchain"
STREAM_SOCIAL = "signals:social"
STREAM_DERIVATIVES = "signals:derivatives"

ALL_STREAMS = [STREAM_PRICES, STREAM_NEWS, STREAM_ONCHAIN, STREAM_SOCIAL, STREAM_DERIVATIVES]

# Consumer group name
CONSUMER_GROUP = "signaldach-workers"


async def ensure_stream_groups() -> None:
    """Create consumer groups for all signal streams (idempotent).

    Call during startup to ensure all streams and groups exist.
    """
    r = await get_redis()
    if r is None:
        logger.debug("Redis unavailable, skipping stream group setup")
        return

    for stream in ALL_STREAMS:
        try:
            await r.xgroup_create(stream, CONSUMER_GROUP, id="0", mkstream=True)
            logger.debug("Created consumer group %s on stream %s", CONSUMER_GROUP, stream)
        except Exception as e:
            # Group already exists is fine
            err_str = str(e)
            if "BUSYGROUP" in err_str:
                logger.debug("Consumer group %s already exists on %s", CONSUMER_GROUP, stream)
            else:
                logger.warning("Error creating stream group on %s: %s", stream, e)


async def stream_publish(stream: str, data: dict[str, Any], maxlen: int = 10000) -> Optional[str]:
    """Publish an event to a Redis Stream.

    Args:
        stream: Stream name (e.g. STREAM_PRICES).
        data: Dict of field-value pairs.
        maxlen: Approximate max stream length (auto-trimmed).

    Returns:
        The message ID, or None if Redis is unavailable.
    """
    r = await get_redis()
    if r is None:
        return None

    # Flatten nested values to JSON strings
    flat: dict[str, str] = {}
    for k, v in data.items():
        flat[k] = v if isinstance(v, str) else json.dumps(v, default=str)

    try:
        msg_id = await r.xadd(stream, flat, maxlen=maxlen, approximate=True)
        return msg_id
    except Exception as e:
        logger.warning("Redis stream_publish error on %s: %s", stream, e)
        return None


async def stream_read(
    stream: str,
    consumer_name: str,
    count: int = 10,
    block_ms: int = 2000,
) -> list[tuple[str, dict[str, str]]]:
    """Read events from a Redis Stream as a consumer in the group.

    Args:
        stream: Stream name.
        consumer_name: Unique consumer name within the group.
        count: Max events to read.
        block_ms: Block for this many ms waiting for new events (0 = don't block).

    Returns:
        List of (message_id, field_dict) tuples.
    """
    r = await get_redis()
    if r is None:
        return []

    try:
        results = await r.xreadgroup(
            CONSUMER_GROUP, consumer_name,
            {stream: ">"},
            count=count,
            block=block_ms,
        )
        if not results:
            return []
        # results = [[stream_name, [(msg_id, fields), ...]]]
        messages = []
        for _stream_name, entries in results:
            for msg_id, fields in entries:
                messages.append((msg_id, fields))
        return messages
    except Exception as e:
        logger.debug("Redis stream_read error on %s: %s", stream, e)
        return []


async def stream_ack(stream: str, *msg_ids: str) -> int:
    """Acknowledge processed messages in a stream.

    Returns:
        Number of messages acknowledged.
    """
    r = await get_redis()
    if r is None:
        return 0
    try:
        return await r.xack(stream, CONSUMER_GROUP, *msg_ids)
    except Exception as e:
        logger.debug("Redis stream_ack error on %s: %s", stream, e)
        return 0


# ---------------------------------------------------------------------------
# Rate limiting helpers (used by middleware)
# ---------------------------------------------------------------------------

async def rate_limit_check(key: str, limit: int, window_seconds: int = 60) -> bool:
    """Sliding-window rate limit check using Redis sorted sets.

    Args:
        key: Rate limit key (e.g. "rl:api:192.168.1.1").
        limit: Maximum requests allowed in the window.
        window_seconds: Sliding window size in seconds.

    Returns:
        True if the request is allowed, False if rate limit exceeded.
    """
    r = await get_redis()
    if r is None:
        return True  # Can't rate-limit without Redis; fallback handles it

    now = time.time()
    window_start = now - window_seconds

    pipe = r.pipeline()
    try:
        # Remove expired entries
        pipe.zremrangebyscore(key, 0, window_start)
        # Count current entries
        pipe.zcard(key)
        # Add current request
        pipe.zadd(key, {f"{now}": now})
        # Set expiry on the key
        pipe.expire(key, window_seconds + 1)

        results = await pipe.execute()
        current_count = results[1]  # zcard result

        return current_count < limit
    except Exception as e:
        logger.debug("Redis rate_limit_check error for %s: %s", key, e)
        return True  # Allow on error


# ---------------------------------------------------------------------------
# Circuit breaker helpers (used by error_handling)
# ---------------------------------------------------------------------------

_CB_PREFIX = "cb:"
_CB_TTL = 300  # 5 min expiry for circuit breaker state


async def cb_get_state(source_id: str) -> Optional[dict]:
    """Get circuit breaker state from Redis.

    Returns:
        Dict with keys: state, failure_count, last_failure_time, or None.
    """
    r = await get_redis()
    if r is None:
        return None

    key = f"{_CB_PREFIX}{source_id}"
    try:
        data = await r.hgetall(key)
        if not data:
            return None
        return {
            "state": data.get("state", "closed"),
            "failure_count": int(data.get("failure_count", 0)),
            "last_failure_time": float(data.get("last_failure_time", 0)),
        }
    except Exception as e:
        logger.debug("Redis cb_get_state error for %s: %s", source_id, e)
        return None


async def cb_set_state(
    source_id: str,
    state: str,
    failure_count: int,
    last_failure_time: float,
) -> None:
    """Set circuit breaker state in Redis."""
    r = await get_redis()
    if r is None:
        return

    key = f"{_CB_PREFIX}{source_id}"
    try:
        pipe = r.pipeline()
        pipe.hset(key, mapping={
            "state": state,
            "failure_count": str(failure_count),
            "last_failure_time": str(last_failure_time),
        })
        pipe.expire(key, _CB_TTL)
        await pipe.execute()
    except Exception as e:
        logger.debug("Redis cb_set_state error for %s: %s", source_id, e)


async def cb_delete(source_id: str) -> None:
    """Delete circuit breaker state from Redis."""
    r = await get_redis()
    if r is None:
        return
    try:
        await r.delete(f"{_CB_PREFIX}{source_id}")
    except Exception as e:
        logger.debug("Redis cb_delete error for %s: %s", source_id, e)
