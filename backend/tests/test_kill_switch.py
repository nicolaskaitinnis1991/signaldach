"""Kill Switch -- integration tests with real DB."""

import pytest
from app.database import init_db
from app.trading.paper_db import init_paper_tables
from app.trading.paper_engine import (
    OrderSide,
    OrderType,
    OrderStatus,
    PaperPortfolio,
    reset_paper_portfolio,
)
from app.trading.kill_switch import (
    activate_kill_switch,
    deactivate_kill_switch,
    is_kill_switch_active,
    get_kill_switch_status,
    _reset_kill_switch,
)


@pytest.fixture(autouse=True)
def _init():
    init_db()
    init_paper_tables()
    reset_paper_portfolio()
    _reset_kill_switch()
    yield
    _reset_kill_switch()


@pytest.fixture
def portfolio_with_btc():
    """Singleton portfolio with a BTC price seeded."""
    from app.trading.paper_engine import get_paper_portfolio
    from app.database import get_db
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO price_ticks (symbol, exchange, price) VALUES (?, ?, ?)",
            ("BTC/USDT", "test", 50000.0),
        )
    return get_paper_portfolio()


# ---------------------------------------------------------------------------
# Test 1: Kill switch initially inactive
# ---------------------------------------------------------------------------


class TestKillSwitchInitiallyInactive:
    def test_kill_switch_initially_inactive(self):
        assert is_kill_switch_active() is False


# ---------------------------------------------------------------------------
# Test 2: Activate kill switch
# ---------------------------------------------------------------------------


class TestActivateKillSwitch:
    def test_activate_kill_switch(self):
        state = activate_kill_switch("admin", "Emergency halt")
        assert state.active is True
        assert state.activated_by == "admin"
        assert state.reason == "Emergency halt"
        assert state.activated_at is not None
        assert is_kill_switch_active() is True


# ---------------------------------------------------------------------------
# Test 3: Deactivate kill switch
# ---------------------------------------------------------------------------


class TestDeactivateKillSwitch:
    def test_deactivate_kill_switch(self):
        activate_kill_switch("admin", "Test")
        assert is_kill_switch_active() is True

        state = deactivate_kill_switch("admin")
        assert state.active is False
        assert is_kill_switch_active() is False


# ---------------------------------------------------------------------------
# Test 4: Kill switch blocks paper orders
# ---------------------------------------------------------------------------


class TestKillSwitchBlocksOrders:
    def test_kill_switch_blocks_orders(self, portfolio_with_btc):
        """Orders submitted via API should be rejected when kill switch is active."""
        from fastapi.testclient import TestClient
        from app.main import app

        reset_paper_portfolio()
        _reset_kill_switch()

        client = TestClient(app)

        # Activate kill switch
        activate_kill_switch("admin", "Testing block")

        # Try to submit an order via API
        resp = client.post("/api/paper/order", json={
            "symbol": "BTC/USDT",
            "side": "buy",
            "type": "market",
            "quantity": 0.1,
        })
        assert resp.status_code == 403
        assert "kill switch" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Test 5: Kill switch status structure
# ---------------------------------------------------------------------------


class TestKillSwitchStatusStructure:
    def test_kill_switch_status_structure(self):
        activate_kill_switch("admin", "Status test")
        status = get_kill_switch_status()

        assert "active" in status
        assert "activated_at" in status
        assert "activated_by" in status
        assert "reason" in status
        assert "history" in status
        assert status["active"] is True
        assert status["activated_by"] == "admin"
        assert status["reason"] == "Status test"


# ---------------------------------------------------------------------------
# Test 6: Kill switch history tracks activations/deactivations
# ---------------------------------------------------------------------------


class TestKillSwitchHistory:
    def test_kill_switch_history(self):
        activate_kill_switch("admin", "First activation")
        deactivate_kill_switch("admin")
        activate_kill_switch("admin", "Second activation")

        status = get_kill_switch_status()
        history = status["history"]

        assert len(history) == 3
        assert history[0]["action"] == "activated"
        assert history[0]["reason"] == "First activation"
        assert history[1]["action"] == "deactivated"
        assert history[2]["action"] == "activated"
        assert history[2]["reason"] == "Second activation"


# ---------------------------------------------------------------------------
# Test 7: Kill switch API activate endpoint
# ---------------------------------------------------------------------------


class TestKillSwitchAPIActivate:
    def test_kill_switch_api_activate(self):
        from fastapi.testclient import TestClient
        from app.main import app

        _reset_kill_switch()
        client = TestClient(app)

        resp = client.post("/api/paper/kill-switch/activate?reason=API+test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "activated"
        assert data["active"] is True
        assert data["reason"] == "API test"


# ---------------------------------------------------------------------------
# Test 8: Kill switch API status endpoint
# ---------------------------------------------------------------------------


class TestKillSwitchAPIStatus:
    def test_kill_switch_api_status(self):
        from fastapi.testclient import TestClient
        from app.main import app

        _reset_kill_switch()
        client = TestClient(app)

        resp = client.get("/api/paper/kill-switch/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "active" in data
        assert "history" in data
        assert data["active"] is False


# ---------------------------------------------------------------------------
# Test 9: Kill switch cancels pending orders on activation
# ---------------------------------------------------------------------------


class TestKillSwitchCancelsPendingOrders:
    def test_kill_switch_cancels_pending(self, portfolio_with_btc):
        p = portfolio_with_btc

        # Submit a limit order that stays pending (price below market)
        order = p.submit_order("BTC/USDT", OrderSide.BUY, OrderType.LIMIT, 0.1, price=40000.0)
        assert order.status == OrderStatus.PENDING

        # Activate kill switch
        activate_kill_switch("admin", "Cancel test")

        # Check that the order was cancelled
        for o in p.order_history:
            if o.id == order.id:
                assert o.status == OrderStatus.CANCELLED
                assert o.reason == "Kill switch activated"
                break
        else:
            pytest.fail("Order not found in history")


# ---------------------------------------------------------------------------
# Test 10: Kill switch deactivate then order succeeds
# ---------------------------------------------------------------------------


class TestKillSwitchDeactivateThenOrderSucceeds:
    def test_deactivate_then_order_succeeds(self):
        from fastapi.testclient import TestClient
        from app.main import app

        reset_paper_portfolio()
        _reset_kill_switch()

        client = TestClient(app)

        # Seed price
        from app.database import get_db
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO price_ticks (symbol, exchange, price) VALUES (?, ?, ?)",
                ("BTC/USDT", "test", 50000.0),
            )

        # Activate then deactivate
        activate_kill_switch("admin", "Temporary halt")
        deactivate_kill_switch("admin")

        # Order should succeed
        resp = client.post("/api/paper/order", json={
            "symbol": "BTC/USDT",
            "side": "buy",
            "type": "market",
            "quantity": 0.1,
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "filled"
