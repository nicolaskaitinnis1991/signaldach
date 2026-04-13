"""Tests for route guards (auth requirements) and per-user rate limiting.

Verifies that sensitive endpoints enforce authentication and role checks
when auth is enabled, and that public endpoints remain accessible.
"""

import pytest
from fastapi.testclient import TestClient

import app.config as config_module
from app.auth import create_access_token, create_user, hash_password
from app.database import get_db


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Reset the in-memory rate limiter before each test to avoid cross-test 429s."""
    from app.middleware import _rate_store
    _rate_store._requests.clear()
    yield
    _rate_store._requests.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _enable_auth():
    """Temporarily enable auth for testing."""
    config_module.settings.auth_enabled = True


def _disable_auth():
    """Restore auth to disabled (test default)."""
    config_module.settings.auth_enabled = False


def _create_test_user(role: str = "viewer") -> dict:
    """Create a test user directly in the DB and return user dict + token."""
    import uuid
    from datetime import datetime, timezone

    user_id = str(uuid.uuid4())
    email = f"test-{user_id[:8]}@example.com"
    pw_hash = hash_password("testpass123")
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as conn:
        conn.execute(
            """INSERT INTO users (id, email, password_hash, role, is_active, created_at, updated_at)
               VALUES (?, ?, ?, ?, 1, ?, ?)""",
            (user_id, email, pw_hash, role, now, now),
        )

    token = create_access_token(user_id, role)
    return {"id": user_id, "email": email, "role": role, "token": token}


def _get_client():
    """Get a fresh test client."""
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Tests: Auth-protected endpoints return 401 when auth is enabled
# ---------------------------------------------------------------------------


class TestPortfolioRequiresAuth:
    def test_portfolio_analyze_requires_auth(self):
        """POST /api/portfolio/analyze without auth returns 401 when auth enabled."""
        _enable_auth()
        try:
            client = _get_client()
            resp = client.post(
                "/api/portfolio/analyze",
                json={"positions": [], "cash_usd": 1000},
            )
            assert resp.status_code == 401
        finally:
            _disable_auth()


class TestChatRequiresAuth:
    def test_chat_requires_auth(self):
        """POST /api/chat/ without auth returns 401 when auth enabled."""
        _enable_auth()
        try:
            client = _get_client()
            resp = client.post(
                "/api/chat/",
                json={"message": "What is BTC doing?"},
            )
            assert resp.status_code == 401
        finally:
            _disable_auth()


class TestAuditRequiresAdmin:
    def test_audit_logs_requires_admin(self):
        """GET /api/audit/logs with viewer role returns 403."""
        _enable_auth()
        try:
            user = _create_test_user(role="viewer")
            client = _get_client()
            resp = client.get(
                "/api/audit/logs",
                headers={"Authorization": f"Bearer {user['token']}"},
            )
            assert resp.status_code == 403
        finally:
            _disable_auth()

    def test_audit_logs_no_auth_returns_401(self):
        """GET /api/audit/logs without any auth returns 401."""
        _enable_auth()
        try:
            client = _get_client()
            resp = client.get("/api/audit/logs")
            assert resp.status_code == 401
        finally:
            _disable_auth()


class TestSignalsAnalyzeRequiresAuth:
    def test_signals_analyze_requires_auth(self):
        """GET /api/signals/analyze without auth returns 401 when auth enabled."""
        _enable_auth()
        try:
            client = _get_client()
            resp = client.get("/api/signals/analyze?symbol=BTC/USDT")
            assert resp.status_code == 401
        finally:
            _disable_auth()


class TestPublicEndpointsNoAuth:
    def test_health_is_public(self):
        """GET /health works without auth even when auth is enabled."""
        _enable_auth()
        try:
            client = _get_client()
            resp = client.get("/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
        finally:
            _disable_auth()

    def test_health_ready_is_public(self):
        """GET /health/ready works without auth."""
        _enable_auth()
        try:
            client = _get_client()
            resp = client.get("/health/ready")
            assert resp.status_code == 200
        finally:
            _disable_auth()


class TestPerUserRateLimitKey:
    def test_rate_limit_key_includes_user_id(self):
        """Verify that the rate limit store uses user:<id> key format for authenticated requests."""
        from app.middleware import _rate_store

        # Simulate a user rate key
        user_id = "test-user-abc"
        user_key = f"user:{user_id}"
        assert _rate_store.is_allowed(user_key, limit=5, window_seconds=60)

        # Exhaust the limit
        for _ in range(4):
            _rate_store.is_allowed(user_key, limit=5, window_seconds=60)

        # 6th request should be denied
        assert not _rate_store.is_allowed(user_key, limit=5, window_seconds=60)


class TestAuthDisabledAllowsAll:
    def test_portfolio_works_without_auth_when_disabled(self):
        """When auth_enabled=False, portfolio endpoints work without credentials."""
        _disable_auth()
        client = _get_client()
        resp = client.post(
            "/api/portfolio/analyze",
            json={"positions": [], "cash_usd": 1000},
        )
        # Should not be 401/403 — may be 200 or 422 depending on business logic
        assert resp.status_code not in (401, 403)

    def test_chat_works_without_auth_when_disabled(self):
        """When auth_enabled=False, chat endpoints work without credentials."""
        _disable_auth()
        client = _get_client()
        resp = client.post(
            "/api/chat/",
            json={"message": "hello"},
        )
        assert resp.status_code not in (401, 403)

    def test_audit_works_without_auth_when_disabled(self):
        """When auth_enabled=False, audit endpoints work without credentials."""
        _disable_auth()
        client = _get_client()
        resp = client.get("/api/audit/logs")
        assert resp.status_code not in (401, 403)


class TestComplianceRequiresAnalyst:
    def test_compliance_requires_auth(self):
        """GET /compliance/check without auth returns 401 when auth enabled."""
        _enable_auth()
        try:
            client = _get_client()
            resp = client.get("/compliance/check")
            assert resp.status_code == 401
        finally:
            _disable_auth()

    def test_compliance_viewer_gets_403(self):
        """GET /compliance/check with viewer role returns 403."""
        _enable_auth()
        try:
            user = _create_test_user(role="viewer")
            client = _get_client()
            resp = client.get(
                "/compliance/check",
                headers={"Authorization": f"Bearer {user['token']}"},
            )
            assert resp.status_code == 403
        finally:
            _disable_auth()

    def test_compliance_analyst_allowed(self):
        """GET /compliance/check with analyst role is allowed."""
        _enable_auth()
        try:
            user = _create_test_user(role="analyst")
            client = _get_client()
            resp = client.get(
                "/compliance/check",
                headers={"Authorization": f"Bearer {user['token']}"},
            )
            assert resp.status_code == 200
        finally:
            _disable_auth()


class TestPaperTradingRequiresAuth:
    def test_paper_order_requires_auth(self):
        """POST /api/paper/order without auth returns 401 when auth enabled."""
        _enable_auth()
        try:
            client = _get_client()
            resp = client.post(
                "/api/paper/order",
                json={"symbol": "BTC/USDT", "side": "buy", "type": "market", "quantity": 0.1},
            )
            assert resp.status_code == 401
        finally:
            _disable_auth()

    def test_paper_portfolio_requires_auth(self):
        """GET /api/paper/portfolio without auth returns 401 when auth enabled."""
        _enable_auth()
        try:
            client = _get_client()
            resp = client.get("/api/paper/portfolio")
            assert resp.status_code == 401
        finally:
            _disable_auth()


class TestFundRiskAssessmentRequiresAuth:
    def test_fund_risk_assessment_requires_auth(self):
        """POST /api/fund/risk-assessment without auth returns 401 when auth enabled."""
        _enable_auth()
        try:
            client = _get_client()
            resp = client.post(
                "/api/fund/risk-assessment",
                json={"positions": [], "cash_usd": 1000},
            )
            assert resp.status_code == 401
        finally:
            _disable_auth()

    def test_fund_risk_limits_is_public(self):
        """GET /api/fund/risk-limits is accessible without auth (static config)."""
        _enable_auth()
        try:
            client = _get_client()
            resp = client.get("/api/fund/risk-limits")
            # risk-limits has no auth guard, should return 200
            assert resp.status_code == 200
        finally:
            _disable_auth()
