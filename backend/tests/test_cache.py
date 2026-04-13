"""Tests for Redis query result caching layer and cached endpoints.

All tests work without a running Redis instance — they exercise the
in-memory fallback path and verify endpoints return correct data.
"""

import pytest
from fastapi.testclient import TestClient

from app.database import init_db


@pytest.fixture(autouse=True)
def _init_db():
    init_db()


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# Cache utility functions
# ---------------------------------------------------------------------------

class TestCacheUtilities:
    def test_cache_key_deterministic(self):
        """Same inputs always produce the same cache key."""
        from app.cache import cache_key
        k1 = cache_key("scorecard", "BTC/USDT", "composite")
        k2 = cache_key("scorecard", "BTC/USDT", "composite")
        assert k1 == k2
        assert k1 == "scorecard:BTC/USDT:composite"

    def test_cache_key_different_inputs(self):
        """Different inputs produce different cache keys."""
        from app.cache import cache_key
        k1 = cache_key("scorecard", "BTC/USDT", "composite")
        k2 = cache_key("scorecard", "ETH/USDT", "composite")
        assert k1 != k2

    @pytest.mark.asyncio
    async def test_cache_set_and_get_without_redis(self):
        """cache_get returns None when Redis is unavailable (in-memory fallback
        in redis_client still works, but the cache_get wrapper handles it)."""
        from app.cache import cache_get, cache_set

        # Set a value — will use in-memory fallback
        await cache_set("test_key", {"hello": "world"}, ttl=60)

        # Get it back
        result = await cache_get("test_key")
        # With the in-memory fallback in redis_client, this should work
        assert result is not None
        assert result["hello"] == "world"

    @pytest.mark.asyncio
    async def test_cache_delete_without_redis(self):
        """cache_delete works gracefully without Redis."""
        from app.cache import cache_delete

        # Should not raise and should return an int
        result = await cache_delete("nonexistent_key")
        assert isinstance(result, int)

    def test_cache_ttls_defined(self):
        """All expected TTL keys are present in CACHE_TTLS."""
        from app.cache import CACHE_TTLS

        expected_keys = {
            "market_summary",
            "market_prices",
            "signal_analysis",
            "scorecard",
            "risk_limits",
            "feature_flags",
            "nav",
            "compliance_score",
        }
        assert expected_keys.issubset(set(CACHE_TTLS.keys()))
        # All TTLs should be positive integers
        for key, ttl in CACHE_TTLS.items():
            assert isinstance(ttl, int), f"TTL for {key} is not int: {type(ttl)}"
            assert ttl > 0, f"TTL for {key} must be positive, got {ttl}"


# ---------------------------------------------------------------------------
# Cached API endpoints
# ---------------------------------------------------------------------------

class TestCachedEndpoints:
    def test_market_summary_endpoint(self, client):
        """GET /api/market/summary returns valid data (may be empty initially)."""
        resp = client.get("/api/market/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_risk_limits_cached_response(self, client):
        """GET /api/fund/risk-limits returns data with 'limits' key."""
        resp = client.get("/api/fund/risk-limits")
        assert resp.status_code == 200
        data = resp.json()
        assert "limits" in data
        limits = data["limits"]
        assert isinstance(limits, dict)
        # Should have standard risk limit keys
        assert "max_position_pct" in limits

    def test_risk_limits_second_call_still_works(self, client):
        """Second call should work (tests cache-hit path)."""
        resp1 = client.get("/api/fund/risk-limits")
        assert resp1.status_code == 200
        resp2 = client.get("/api/fund/risk-limits")
        assert resp2.status_code == 200
        assert resp1.json() == resp2.json()

    def test_scorecard_endpoint(self, client):
        """GET /api/scorecard/performance returns valid data."""
        resp = client.get(
            "/api/scorecard/performance",
            params={"symbol": "BTC/USDT", "signal_type": "composite", "days": 7},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_health_cache_endpoint(self, client):
        """GET /health/cache returns a status field."""
        resp = client.get("/health/cache")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        # Without Redis running, status will be "unavailable" or "error" — both OK
        assert data["status"] in ("ok", "unavailable", "error")
