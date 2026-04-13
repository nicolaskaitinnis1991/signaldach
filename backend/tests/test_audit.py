"""Tests for Audit Trail and Structured Error Codes — no mocks, real DB."""

import json
import pytest

from app.database import init_db, get_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _init_db():
    """Ensure DB is initialized before each test."""
    init_db()


# ---------------------------------------------------------------------------
# Tests: Audit Logging
# ---------------------------------------------------------------------------

class TestAuditLog:
    def test_log_event_writes_to_db(self):
        from app.audit import log_event

        log_event(
            "auth",
            "login",
            user_id="user-123",
            detail={"email": "test@test.com"},
            ip_address="127.0.0.1",
            request_id="req-abc",
        )

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM audit_log WHERE user_id = 'user-123' ORDER BY ts DESC LIMIT 1")
            row = cur.fetchone()

        assert row is not None
        if isinstance(row, dict):
            assert row["category"] == "auth"
            assert row["action"] == "login"
            assert row["ip_address"] == "127.0.0.1"
            assert "test@test.com" in row["detail"]
        else:
            # sqlite3.Row
            assert row[2] == "auth"  # category
            assert row[3] == "login"  # action

    def test_log_auth_helper(self):
        from app.audit import log_auth

        log_auth("failed_login", email="bad@example.com", ip="10.0.0.1")

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM audit_log WHERE action = 'failed_login' ORDER BY ts DESC LIMIT 1"
            )
            row = cur.fetchone()

        assert row is not None

    def test_log_risk_helper(self):
        from app.audit import log_risk

        log_risk("risk_assessment", user_id="admin-1", detail={"breaches": 2, "halt": False})

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM audit_log WHERE action = 'risk_assessment' ORDER BY ts DESC LIMIT 1"
            )
            row = cur.fetchone()

        assert row is not None

    def test_log_signal_helper(self):
        from app.audit import log_signal

        log_signal("signal_generated", detail={"symbol": "BTC/USDT", "score": 0.72})

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM audit_log WHERE category = 'signal' ORDER BY ts DESC LIMIT 1"
            )
            row = cur.fetchone()

        assert row is not None

    def test_log_system_helper(self):
        from app.audit import log_system

        log_system("scraper_error", detail={"source": "coingecko", "error": "timeout"})

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM audit_log WHERE category = 'system' ORDER BY ts DESC LIMIT 1"
            )
            row = cur.fetchone()

        assert row is not None

    def test_log_event_never_raises(self):
        """Even with bad data, log_event should never raise."""
        from app.audit import log_event

        # This should not raise, just silently fail or succeed
        log_event("test", "test_action", detail={"nested": {"deep": True}})


# ---------------------------------------------------------------------------
# Tests: Audit API
# ---------------------------------------------------------------------------

class TestAuditAPI:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_audit_logs_endpoint(self, client):
        # First insert some audit data
        from app.audit import log_event
        log_event("auth", "test_api_login", user_id="user-api-test")

        resp = client.get("/api/audit/logs?category=auth&limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "logs" in data
        assert "total" in data
        assert isinstance(data["logs"], list)

    def test_audit_summary_endpoint(self, client):
        from app.audit import log_event
        log_event("auth", "summary_test")

        resp = client.get("/api/audit/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "period" in data
        assert "by_category" in data

    def test_audit_logs_with_pagination(self, client):
        resp = client.get("/api/audit/logs?limit=2&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert "limit" in data
        assert data["limit"] == 2
        assert "offset" in data
        assert data["offset"] == 0


# ---------------------------------------------------------------------------
# Tests: Structured Error Codes
# ---------------------------------------------------------------------------

class TestErrorCodes:
    def test_error_response_structure(self):
        from app.error_handling import error_response, ErrorCode

        resp = error_response(
            429, ErrorCode.RATE_LIMITED, "Too many requests", path="/api/test"
        )
        body = json.loads(resp.body)
        assert body["error_code"] == "RATE_LIMITED"
        assert body["message"] == "Too many requests"
        assert body["retryable"] is True
        assert body["path"] == "/api/test"

    def test_non_retryable_error(self):
        from app.error_handling import error_response, ErrorCode

        resp = error_response(
            401, ErrorCode.AUTH_REQUIRED, "Authentication required"
        )
        body = json.loads(resp.body)
        assert body["error_code"] == "AUTH_REQUIRED"
        assert body["retryable"] is False

    def test_retryable_errors(self):
        from app.error_handling import ErrorCode, _RETRYABLE

        retryable_codes = {
            ErrorCode.RATE_LIMITED,
            ErrorCode.SCRAPER_TIMEOUT,
            ErrorCode.SIGNAL_TIMEOUT,
            ErrorCode.DATABASE_ERROR,
            ErrorCode.REDIS_UNAVAILABLE,
            ErrorCode.INTERNAL_ERROR,
        }
        for code in retryable_codes:
            assert code in _RETRYABLE, f"{code} should be retryable"

    def test_non_retryable_errors(self):
        from app.error_handling import ErrorCode, _RETRYABLE

        non_retryable = {
            ErrorCode.AUTH_REQUIRED,
            ErrorCode.AUTH_INVALID_TOKEN,
            ErrorCode.VALIDATION_ERROR,
            ErrorCode.RISK_LIMIT_BREACH,
            ErrorCode.NOT_FOUND,
        }
        for code in non_retryable:
            assert code not in _RETRYABLE, f"{code} should NOT be retryable"

    def test_error_response_with_details(self):
        from app.error_handling import error_response, ErrorCode

        resp = error_response(
            422,
            ErrorCode.VALIDATION_ERROR,
            "Bad input",
            details={"field": "email", "issue": "invalid format"},
        )
        body = json.loads(resp.body)
        assert body["details"]["field"] == "email"

    def test_404_returns_structured_error(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        resp = client.get("/nonexistent-route-xyz")
        assert resp.status_code == 404
        data = resp.json()
        assert data["error_code"] == "NOT_FOUND"
        assert data["retryable"] is False
