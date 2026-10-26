"""Integration tests for Redis client.

Tests run against a REAL Redis instance. Skipped automatically if Redis is not available.
NO MOCKS — ever.
"""

from __future__ import annotations

import asyncio
import json
import time

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Skip entire module if Redis is not reachable
# ---------------------------------------------------------------------------

_redis_reachable = False

try:
    import redis.asyncio as aioredis

    _r = aioredis.from_url("redis://localhost:6379", socket_connect_timeout=2)
    asyncio.run(_r.ping())
    asyncio.run(_r.aclose())
    _redis_reachable = True
except Exception:
    pass

pytestmark = pytest.mark.skipif(not _redis_reachable, reason="Redis not available at localhost:6379")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(autouse=True)
async def _init_redis():
    """Initialize and tear down the Redis connection for each test."""
    from app.redis_client import init_redis, shutdown_redis
    await init_redis()
    yield
    await shutdown_redis()


@pytest_asyncio.fixture
async def _flush_test_keys():
    """Clean up any test keys after each test."""
    keys_to_clean: list[str] = []
    yield keys_to_clean
    from app.redis_client import get_redis
    r = await get_redis()
    if r and keys_to_clean:
        await r.delete(*keys_to_clean)


# ---------------------------------------------------------------------------
# Connection tests
# ---------------------------------------------------------------------------

class TestConnection:
    @pytest.mark.asyncio
    async def test_redis_is_available(self):
        from app.redis_client import is_redis_available
        assert is_redis_available() is True

    @pytest.mark.asyncio
    async def test_get_redis_returns_client(self):
        from app.redis_client import get_redis
        r = await get_redis()
        assert r is not None
        pong = await r.ping()
        assert pong is True


# ---------------------------------------------------------------------------
# Cache tests
# ---------------------------------------------------------------------------

class TestCache:
    @pytest.mark.asyncio
    async def test_set_and_get(self, _flush_test_keys):
        from app.redis_client import cache_set, cache_get
        key = "test:cache:set_get"
        _flush_test_keys.append(key)

        await cache_set(key, "hello", ttl=30)
        result = await cache_get(key)
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_get_missing_key_returns_none(self):
        from app.redis_client import cache_get
        result = await cache_get("test:cache:nonexistent_key_abc123")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self, _flush_test_keys):
        from app.redis_client import cache_set, cache_get, cache_delete
        key = "test:cache:delete"
        _flush_test_keys.append(key)

        await cache_set(key, "to_delete", ttl=30)
        assert await cache_get(key) == "to_delete"
        await cache_delete(key)
        assert await cache_get(key) is None

    @pytest.mark.asyncio
    async def test_json_roundtrip(self, _flush_test_keys):
        from app.redis_client import cache_set_json, cache_get_json
        key = "test:cache:json"
        _flush_test_keys.append(key)

        data = {"prices": [100.5, 200.3], "symbol": "BTC", "nested": {"a": 1}}
        await cache_set_json(key, data, ttl=30)
        result = await cache_get_json(key)
        assert result == data

    @pytest.mark.asyncio
    async def test_ttl_expiry(self, _flush_test_keys):
        from app.redis_client import cache_set, cache_get
        key = "test:cache:ttl"
        _flush_test_keys.append(key)

        await cache_set(key, "expires_fast", ttl=1)
        assert await cache_get(key) == "expires_fast"
        await asyncio.sleep(1.5)
        assert await cache_get(key) is None


# ---------------------------------------------------------------------------
# Pub/Sub tests
# ---------------------------------------------------------------------------

class TestPubSub:
    @pytest.mark.asyncio
    async def test_publish_returns_int(self):
        from app.redis_client import publish
        # Even with no subscribers, publish should return 0
        count = await publish("test:pubsub:noop", {"msg": "hello"})
        assert isinstance(count, int)

    @pytest.mark.asyncio
    async def test_publish_and_subscribe(self):
        from app.redis_client import publish, subscribe

        channel = "test:pubsub:roundtrip"
        received: list[str] = []

        async def listener():
            async for msg in subscribe(channel):
                received.append(msg)
                if len(received) >= 2:
                    break

        # Start listener in background
        task = asyncio.create_task(listener())
        await asyncio.sleep(0.3)  # Let subscriber connect

        await publish(channel, {"seq": 1})
        await publish(channel, {"seq": 2})

        try:
            await asyncio.wait_for(task, timeout=5.0)
        except asyncio.TimeoutError:
            task.cancel()

        assert len(received) >= 2
        parsed = [json.loads(m) for m in received[:2]]
        assert parsed[0]["seq"] == 1
        assert parsed[1]["seq"] == 2


# ---------------------------------------------------------------------------
# Rate limiting tests
# ---------------------------------------------------------------------------

class TestRateLimiting:
    @pytest.mark.asyncio
    async def test_allows_under_limit(self, _flush_test_keys):
        from app.redis_client import rate_limit_check
        key = "rl:test:under_limit"
        _flush_test_keys.append(key)

        # 5 requests under limit of 10
        for _ in range(5):
            assert await rate_limit_check(key, limit=10, window_seconds=60) is True

    @pytest.mark.asyncio
    async def test_blocks_over_limit(self, _flush_test_keys):
        from app.redis_client import rate_limit_check
        key = "rl:test:over_limit"
        _flush_test_keys.append(key)

        # Fill up the limit
        for _ in range(5):
            await rate_limit_check(key, limit=5, window_seconds=60)

        # 6th request should be blocked
        assert await rate_limit_check(key, limit=5, window_seconds=60) is False

    @pytest.mark.asyncio
    async def test_window_expires(self, _flush_test_keys):
        from app.redis_client import rate_limit_check
        key = "rl:test:window_expire"
        _flush_test_keys.append(key)

        # Fill up with window of 1 second
        for _ in range(3):
            await rate_limit_check(key, limit=3, window_seconds=1)

        assert await rate_limit_check(key, limit=3, window_seconds=1) is False
        await asyncio.sleep(1.5)
        assert await rate_limit_check(key, limit=3, window_seconds=1) is True


# ---------------------------------------------------------------------------
# Circuit breaker state tests
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self):
        from app.redis_client import cb_get_state
        result = await cb_get_state("test:cb:nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_and_get_state(self, _flush_test_keys):
        from app.redis_client import cb_set_state, cb_get_state
        source = "test:cb:roundtrip"
        _flush_test_keys.append(f"cb:{source}")

        await cb_set_state(source, "open", failure_count=5, last_failure_time=12345.67)
        state = await cb_get_state(source)
        assert state is not None
        assert state["state"] == "open"
        assert state["failure_count"] == 5
        assert state["last_failure_time"] == 12345.67

    @pytest.mark.asyncio
    async def test_delete_state(self, _flush_test_keys):
        from app.redis_client import cb_set_state, cb_get_state, cb_delete
        source = "test:cb:delete"
        _flush_test_keys.append(f"cb:{source}")

        await cb_set_state(source, "closed", 0, 0.0)
        assert await cb_get_state(source) is not None
        await cb_delete(source)
        assert await cb_get_state(source) is None


# ---------------------------------------------------------------------------
# Redis Streams tests
# ---------------------------------------------------------------------------

class TestStreams:
    @pytest.mark.asyncio
    async def test_stream_publish_and_read(self, _flush_test_keys):
        from app.redis_client import (
            stream_publish, stream_read, stream_ack, get_redis,
            CONSUMER_GROUP,
        )

        stream = "test:stream:roundtrip"
        _flush_test_keys.append(stream)

        # Create consumer group for test stream
        r = await get_redis()
        try:
            await r.xgroup_create(stream, CONSUMER_GROUP, id="0", mkstream=True)
        except Exception:
            pass  # Group may already exist

        # Publish
        msg_id = await stream_publish(stream, {"symbol": "BTC", "price": "67000"}, maxlen=100)
        assert msg_id is not None

        # Read
        messages = await stream_read(stream, consumer_name="test-worker", count=10, block_ms=500)
        assert len(messages) >= 1
        mid, fields = messages[0]
        assert fields["symbol"] == "BTC"
        assert fields["price"] == "67000"

        # Acknowledge
        acked = await stream_ack(stream, mid)
        assert acked == 1

        # Clean up stream
        await r.delete(stream)

    @pytest.mark.asyncio
    async def test_ensure_stream_groups(self):
        from app.redis_client import ensure_stream_groups, get_redis, ALL_STREAMS, CONSUMER_GROUP

        await ensure_stream_groups()

        r = await get_redis()
        for stream in ALL_STREAMS:
            groups = await r.xinfo_groups(stream)
            group_names = [g["name"] for g in groups]
            assert CONSUMER_GROUP in group_names

        # Clean up test streams
        for stream in ALL_STREAMS:
            await r.delete(stream)
