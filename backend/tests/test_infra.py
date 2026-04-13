"""Tests for infrastructure: API versioning, feature flags, metrics, slow query logging."""

import os
import pytest
from app.database import init_db


@pytest.fixture(autouse=True)
def _init_db():
    init_db()


# ---------------------------------------------------------------------------
# API Versioning
# ---------------------------------------------------------------------------

class TestAPIVersioning:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_v1_market_summary(self, client):
        """v1 prefix routes to same handler."""
        resp = client.get("/api/v1/api/market/summary")
        # May return 200 or error depending on data, but should NOT be 404
        assert resp.status_code != 404

    def test_v1_fund_risk_limits(self, client):
        resp = client.get("/api/v1/api/fund/risk-limits")
        assert resp.status_code == 200
        data = resp.json()
        assert "limits" in data

    def test_v1_scorecard(self, client):
        resp = client.get("/api/v1/api/scorecard/performance?symbol=BTC/USDT&signal_type=composite&days=7")
        assert resp.status_code == 200

    def test_original_routes_still_work(self, client):
        """Backward compatibility — original paths must still work."""
        resp = client.get("/api/fund/risk-limits")
        assert resp.status_code == 200

        resp = client.get("/api/scorecard/performance?symbol=BTC/USDT&signal_type=composite&days=7")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Feature Flags
# ---------------------------------------------------------------------------

class TestFeatureFlags:
    def test_defaults_loaded(self):
        from app.feature_flags import get_all_flags, _DEFAULTS
        flags = get_all_flags()
        assert len(flags) == len(_DEFAULTS)
        # Default: trading_live should be off
        assert flags["trading_live"] is False
        # Default: paper_trading should be on
        assert flags["paper_trading"] is True

    def test_env_override(self):
        from app.feature_flags import is_enabled
        os.environ["SIGNALDACH_FF_TRADING_LIVE"] = "true"
        try:
            assert is_enabled("trading_live") is True
        finally:
            del os.environ["SIGNALDACH_FF_TRADING_LIVE"]

    def test_env_override_false(self):
        from app.feature_flags import is_enabled
        os.environ["SIGNALDACH_FF_PAPER_TRADING"] = "false"
        try:
            assert is_enabled("paper_trading") is False
        finally:
            del os.environ["SIGNALDACH_FF_PAPER_TRADING"]

    def test_unknown_flag_defaults_false(self):
        from app.feature_flags import is_enabled
        assert is_enabled("nonexistent_flag_xyz") is False

    def test_flag_info_structure(self):
        from app.feature_flags import get_flag_info
        info = get_flag_info()
        assert "trading_live" in info
        flag = info["trading_live"]
        assert "enabled" in flag
        assert "default" in flag
        assert "env_key" in flag
        assert flag["env_key"] == "SIGNALDACH_FF_TRADING_LIVE"

    def test_flags_api_endpoint(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        resp = client.get("/api/flags")
        assert resp.status_code == 200
        data = resp.json()
        assert "flags" in data
        assert "trading_live" in data["flags"]


# ---------------------------------------------------------------------------
# Prometheus Metrics
# ---------------------------------------------------------------------------

class TestMetrics:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_metrics_root_endpoint(self, client):
        resp = client.get("/metrics")
        assert resp.status_code == 200
        text = resp.text
        assert "signaldach_items_total" in text
        assert "signaldach_http_requests_total" in text
        assert "signaldach_ws_connections_active" in text
        assert "signaldach_signals_generated_total" in text

    def test_metrics_monitoring_endpoint(self, client):
        resp = client.get("/monitoring/metrics")
        assert resp.status_code == 200
        assert "signaldach_uptime_seconds" in resp.text

    def test_request_recording(self, client):
        """After hitting an endpoint, http_requests_total should increase."""
        from app.monitoring import metrics as app_metrics
        before = app_metrics.http_requests_total
        client.get("/health")
        after = app_metrics.http_requests_total
        assert after > before


# ---------------------------------------------------------------------------
# Slow Query Logging
# ---------------------------------------------------------------------------

class TestSlowQueryLogging:
    def test_threshold_configurable(self):
        from app.database import SLOW_QUERY_THRESHOLD_MS
        assert SLOW_QUERY_THRESHOLD_MS > 0

    def test_normal_query_no_warning(self, caplog):
        """Fast queries should not trigger slow query warning."""
        import logging
        with caplog.at_level(logging.WARNING, logger="app.database"):
            from app.database import get_db
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("SELECT 1")
        # Should not have slow query warning for a trivial query
        slow_warnings = [r for r in caplog.records if "Slow DB transaction" in r.message]
        assert len(slow_warnings) == 0
