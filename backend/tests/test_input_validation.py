"""Input validation and SQL injection hardening tests for SignalDACH backend.

Tests cover:
- Query parameter validation (max_length, patterns, enums)
- SQL injection prevention (tenant_id, symbol, etc.)
- Pydantic model validation (alerts, fund positions)
- Password policy enforcement
- Account lockout mechanism
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth import (
    validate_password,
    PasswordError,
    check_lockout,
    record_failed_attempt,
    clear_failed_attempts,
    _failed_attempts,
    create_user,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. Items query validation
# ---------------------------------------------------------------------------

def test_items_query_max_length():
    """q param rejects strings > 200 chars."""
    long_q = "a" * 201
    resp = client.get("/items", params={"q": long_q})
    assert resp.status_code == 422


def test_items_category_enum():
    """Invalid category returns 422."""
    resp = client.get("/items", params={"category": "INVALID_CATEGORY"})
    assert resp.status_code == 422


def test_items_urgency_enum():
    """Invalid urgency returns 422."""
    resp = client.get("/items", params={"urgency": "super_mega_urgent"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 2. Sources tenant_id validation
# ---------------------------------------------------------------------------

def test_sources_tenant_id_valid():
    """Valid tenant_id works."""
    resp = client.get("/sources", params={"tenant_id": "my-tenant_01"})
    assert resp.status_code == 200


def test_sources_tenant_id_injection():
    """SQL injection in tenant_id rejected."""
    resp = client.get("/sources", params={"tenant_id": "'; DROP TABLE sources;--"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 3. Market data symbol validation
# ---------------------------------------------------------------------------

def test_market_symbol_validation():
    """Invalid symbol format rejected."""
    resp = client.get("/api/market/prices/history", params={"symbol": "'; DROP TABLE--"})
    assert resp.status_code in (400, 422)


def test_market_symbol_valid():
    """Valid symbol accepted (may return empty data but no error)."""
    resp = client.get("/api/market/prices/history", params={"symbol": "BTC/USDT"})
    assert resp.status_code == 200


def test_market_summary_no_injection():
    """Summary endpoint uses parameterized queries, not string interpolation."""
    # This just verifies the endpoint runs without SQL errors
    resp = client.get("/api/market/summary")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 4. Alert config validation
# ---------------------------------------------------------------------------

def test_alert_name_max_length():
    """Alert name > 200 chars rejected."""
    resp = client.post("/alerts", json={
        "name": "x" * 201,
        "tenant_id": "default",
        "conditions": {},
        "channels": {},
    })
    assert resp.status_code == 422


def test_alert_conditions_invalid_key():
    """Unknown condition key rejected."""
    resp = client.post("/alerts", json={
        "name": "Test Alert",
        "tenant_id": "default",
        "conditions": {"invalid_key_xyz": "value"},
        "channels": {},
    })
    assert resp.status_code == 422


def test_alert_channels_invalid_key():
    """Unknown channel key rejected."""
    resp = client.post("/alerts", json={
        "name": "Test Alert",
        "tenant_id": "default",
        "conditions": {},
        "channels": {"telegram": True},
    })
    assert resp.status_code == 422


def test_alert_valid_create():
    """Valid alert config creation succeeds."""
    resp = client.post("/alerts", json={
        "name": "My Alert",
        "tenant_id": "default",
        "conditions": {"category": "regulation", "urgency": "high"},
        "channels": {"email": True, "slack": True},
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "created"


def test_alert_tenant_id_injection():
    """SQL injection in alert tenant_id rejected."""
    resp = client.post("/alerts", json={
        "name": "Test",
        "tenant_id": "'; DROP TABLE alert_configs;--",
        "conditions": {},
        "channels": {},
    })
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 5. Fund position validation
# ---------------------------------------------------------------------------

def test_fund_positions_max_100():
    """> 100 positions rejected."""
    positions = [
        {"symbol": "BTC/USDT", "quantity": 1.0, "entry_price": 50000.0}
        for _ in range(101)
    ]
    resp = client.post("/api/fund/risk-assessment", json={
        "positions": positions,
        "cash_usd": 10000.0,
    })
    assert resp.status_code == 422


def test_fund_cash_max_value():
    """Absurd cash value (> 1B USD) rejected."""
    resp = client.post("/api/fund/risk-assessment", json={
        "positions": [{"symbol": "BTC/USDT", "quantity": 1.0, "entry_price": 50000.0}],
        "cash_usd": 2_000_000_000.0,
    })
    assert resp.status_code == 422


def test_fund_name_max_length():
    """Fund name > 200 chars rejected."""
    resp = client.post("/api/fund/risk-assessment", json={
        "positions": [{"symbol": "BTC/USDT", "quantity": 1.0, "entry_price": 50000.0}],
        "fund_name": "x" * 201,
    })
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 6. Password policy
# ---------------------------------------------------------------------------

def test_password_too_short():
    """Password < 12 chars fails."""
    with pytest.raises(PasswordError, match="at least 12"):
        validate_password("Short1!a")


def test_password_too_long():
    """Password > 128 chars fails."""
    with pytest.raises(PasswordError, match="at most 128"):
        validate_password("Aa1!" * 33)  # 132 chars


def test_password_no_uppercase():
    """Missing uppercase fails."""
    with pytest.raises(PasswordError, match="uppercase"):
        validate_password("alllowercase1!")


def test_password_no_lowercase():
    """Missing lowercase fails."""
    with pytest.raises(PasswordError, match="lowercase"):
        validate_password("ALLUPPERCASE1!")


def test_password_no_digit():
    """Missing digit fails."""
    with pytest.raises(PasswordError, match="digit"):
        validate_password("NoDigitsHere!!!")


def test_password_no_special():
    """Missing special character fails."""
    with pytest.raises(PasswordError, match="special"):
        validate_password("NoSpecial1234Abc")


def test_password_valid():
    """Valid password passes."""
    validate_password("SecureP@ss1234")  # Should not raise


# ---------------------------------------------------------------------------
# 7. Account lockout
# ---------------------------------------------------------------------------

def test_account_lockout():
    """5 failed attempts triggers lockout."""
    email = "lockout-test@example.com"
    # Clean up any previous state
    clear_failed_attempts(email)

    assert check_lockout(email) is False

    for _ in range(5):
        record_failed_attempt(email)

    assert check_lockout(email) is True

    # Cleanup
    clear_failed_attempts(email)


def test_lockout_clears_after_success():
    """Successful login clears lockout."""
    email = "lockout-clear@example.com"
    clear_failed_attempts(email)

    for _ in range(4):
        record_failed_attempt(email)

    # Not yet locked out
    assert check_lockout(email) is False

    # Clear on success
    clear_failed_attempts(email)
    assert check_lockout(email) is False

    # Verify counter was actually reset
    record_failed_attempt(email)
    assert check_lockout(email) is False

    # Cleanup
    clear_failed_attempts(email)
