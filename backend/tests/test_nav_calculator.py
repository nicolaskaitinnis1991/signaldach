"""NAV Calculator -- integration tests with real DB."""

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
from app.trading.nav_calculator import (
    calculate_nav,
    record_nav_snapshot,
    get_nav_history,
    calculate_management_fee,
    calculate_performance_fee,
    calculate_all_fees,
)
from app.trading.kill_switch import _reset_kill_switch


@pytest.fixture(autouse=True)
def _init():
    init_db()
    init_paper_tables()
    reset_paper_portfolio()
    _reset_kill_switch()
    yield


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
# Test 1: NAV of empty portfolio equals initial cash
# ---------------------------------------------------------------------------


class TestCalculateNavEmptyPortfolio:
    def test_calculate_nav_empty_portfolio(self):
        nav = calculate_nav()
        assert nav["nav"] == 100_000.0
        assert nav["positions_value"] == 0.0
        assert nav["cash"] == 100_000.0
        assert "timestamp" in nav


# ---------------------------------------------------------------------------
# Test 2: NAV with positions = positions_value + cash
# ---------------------------------------------------------------------------


class TestCalculateNavWithPositions:
    def test_calculate_nav_with_positions(self, portfolio_with_btc):
        p = portfolio_with_btc
        # Buy 0.2 BTC at 50000 = $10000 cost, 10% of portfolio
        order = p.submit_order("BTC/USDT", OrderSide.BUY, OrderType.MARKET, 0.2)
        assert order.status == OrderStatus.FILLED

        nav = calculate_nav()
        # positions_value = 0.2 * 50000 = 10000
        # cash = 100000 - 10000 = 90000
        # nav = 100000
        assert nav["positions_value"] == pytest.approx(10000.0)
        assert nav["cash"] == pytest.approx(90000.0)
        assert nav["nav"] == pytest.approx(100000.0)


# ---------------------------------------------------------------------------
# Test 3: Management fee calculation
# ---------------------------------------------------------------------------


class TestManagementFeeCalculation:
    def test_management_fee_calculation(self):
        fee = calculate_management_fee(aum=1_000_000.0, annual_rate=0.02)

        assert fee["annual_rate"] == 0.02
        assert fee["annual_fee"] == 20_000.0
        # Daily: 20000 / 365 = ~54.79
        assert fee["daily_fee"] == pytest.approx(54.79, abs=0.01)
        # Monthly: 20000 / 12 = ~1666.67
        assert fee["monthly_fee"] == pytest.approx(1666.67, abs=0.01)
        assert fee["aum"] == 1_000_000.0


# ---------------------------------------------------------------------------
# Test 4: Performance fee below HWM -- no fee
# ---------------------------------------------------------------------------


class TestPerformanceFeeBelowHWM:
    def test_performance_fee_below_hwm(self):
        fee = calculate_performance_fee(
            current_nav=90_000.0,
            high_water_mark=100_000.0,
            fee_rate=0.20,
        )

        assert fee["fee_rate"] == 0.20
        assert fee["hwm"] == 100_000.0
        assert fee["profit_above_hwm"] == 0.0
        assert fee["performance_fee"] == 0.0
        # HWM should not decrease
        assert fee["new_hwm"] == 100_000.0


# ---------------------------------------------------------------------------
# Test 5: Performance fee above HWM -- 20% of profit
# ---------------------------------------------------------------------------


class TestPerformanceFeeAboveHWM:
    def test_performance_fee_above_hwm(self):
        fee = calculate_performance_fee(
            current_nav=120_000.0,
            high_water_mark=100_000.0,
            fee_rate=0.20,
        )

        assert fee["profit_above_hwm"] == 20_000.0
        assert fee["performance_fee"] == 4_000.0  # 20% of 20000
        assert fee["new_hwm"] == 120_000.0


# ---------------------------------------------------------------------------
# Test 6: Record NAV snapshot
# ---------------------------------------------------------------------------


class TestRecordNavSnapshot:
    def test_record_nav_snapshot(self):
        snapshot = record_nav_snapshot()

        assert "nav" in snapshot
        assert "positions_value" in snapshot
        assert "cash" in snapshot
        assert "management_fee" in snapshot
        assert "performance_fee" in snapshot
        assert "high_water_mark" in snapshot
        assert "snapshot_date" in snapshot
        assert snapshot["nav"] == 100_000.0


# ---------------------------------------------------------------------------
# Test 7: NAV history returns list of snapshots
# ---------------------------------------------------------------------------


class TestNavHistory:
    def test_nav_history(self):
        # Record a snapshot
        record_nav_snapshot()

        history = get_nav_history(days=30)
        assert isinstance(history, list)
        assert len(history) >= 1

        entry = history[0]
        assert "nav" in entry
        assert "positions_value" in entry
        assert "cash" in entry
        assert "snapshot_date" in entry


# ---------------------------------------------------------------------------
# Test 8: NAV API endpoint
# ---------------------------------------------------------------------------


class TestNavAPIEndpoint:
    def test_nav_api_endpoint(self):
        from fastapi.testclient import TestClient
        from app.main import app

        reset_paper_portfolio()
        client = TestClient(app)

        resp = client.get("/api/paper/nav")
        assert resp.status_code == 200
        data = resp.json()
        assert "nav" in data
        assert "positions_value" in data
        assert "cash" in data
        assert data["nav"] == 100_000.0


# ---------------------------------------------------------------------------
# Test 9: Fees API endpoint
# ---------------------------------------------------------------------------


class TestFeesAPIEndpoint:
    def test_fees_api_endpoint(self):
        from fastapi.testclient import TestClient
        from app.main import app

        reset_paper_portfolio()
        client = TestClient(app)

        resp = client.get("/api/paper/fees")
        assert resp.status_code == 200
        data = resp.json()
        assert "management_fee" in data
        assert "performance_fee" in data
        assert "total_daily_fees" in data


# ---------------------------------------------------------------------------
# Test 10: Calculate all fees combines management + performance
# ---------------------------------------------------------------------------


class TestCalculateAllFees:
    def test_calculate_all_fees(self):
        fees = calculate_all_fees()

        assert "portfolio_id" in fees
        assert "nav" in fees
        assert "management_fee" in fees
        assert "performance_fee" in fees
        assert "total_daily_fees" in fees
        assert fees["nav"] == 100_000.0

        # Management fee on 100k at 2% annual
        mgmt = fees["management_fee"]
        assert mgmt["annual_rate"] == 0.02
        assert mgmt["daily_fee"] == pytest.approx(5.48, abs=0.01)

        # No performance fee (NAV == HWM for fresh portfolio)
        perf = fees["performance_fee"]
        assert perf["performance_fee"] == 0.0
