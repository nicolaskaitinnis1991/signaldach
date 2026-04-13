"""Paper Trading Engine -- integration tests with real DB."""

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


@pytest.fixture(autouse=True)
def _init_db():
    init_db()
    init_paper_tables()
    # Reset singleton between tests
    reset_paper_portfolio()


@pytest.fixture
def portfolio():
    """Fresh paper portfolio with 100k USD."""
    return PaperPortfolio(initial_cash=100_000.0, portfolio_id="test")


@pytest.fixture
def portfolio_with_btc_price(portfolio):
    """Portfolio with a BTC price tick seeded in DB."""
    from app.database import get_db
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO price_ticks (symbol, exchange, price) VALUES (?, ?, ?)",
            ("BTC/USDT", "test", 50000.0),
        )
    return portfolio


# ---------------------------------------------------------------------------
# Test 1: Market buy fills immediately
# ---------------------------------------------------------------------------

class TestSubmitMarketBuy:
    def test_submit_market_buy(self, portfolio_with_btc_price):
        p = portfolio_with_btc_price
        order = p.submit_order("BTC/USDT", OrderSide.BUY, OrderType.MARKET, 0.3)

        assert order.status == OrderStatus.FILLED
        assert order.fill_price == 50000.0
        assert order.fill_quantity == 0.3
        assert order.filled_at is not None
        assert p.cash == 100_000.0 - (0.3 * 50000.0)
        assert "BTC/USDT" in p.positions


# ---------------------------------------------------------------------------
# Test 2: Market sell without position is rejected
# ---------------------------------------------------------------------------

class TestMarketSellNoPosition:
    def test_submit_market_sell_no_position(self, portfolio_with_btc_price):
        p = portfolio_with_btc_price
        order = p.submit_order("BTC/USDT", OrderSide.SELL, OrderType.MARKET, 1.0)

        assert order.status == OrderStatus.REJECTED
        assert "No position" in order.reason


# ---------------------------------------------------------------------------
# Test 3: Buy then sell with correct cash tracking
# ---------------------------------------------------------------------------

class TestBuyThenSell:
    def test_buy_then_sell(self, portfolio_with_btc_price):
        p = portfolio_with_btc_price
        # Buy 0.3 BTC at 50000 = $15000 (15% of portfolio, under 20% limit)
        buy = p.submit_order("BTC/USDT", OrderSide.BUY, OrderType.MARKET, 0.3)
        assert buy.status == OrderStatus.FILLED
        cash_after_buy = p.cash
        assert cash_after_buy == 85_000.0  # 100k - 15k

        # Sell 0.3 BTC at 50000
        sell = p.submit_order("BTC/USDT", OrderSide.SELL, OrderType.MARKET, 0.3)
        assert sell.status == OrderStatus.FILLED
        assert p.cash == 100_000.0  # back to original
        assert "BTC/USDT" not in p.positions


# ---------------------------------------------------------------------------
# Test 4: Position P&L calculation with price updates
# ---------------------------------------------------------------------------

class TestPositionPnl:
    def test_position_pnl_calculation(self, portfolio_with_btc_price):
        p = portfolio_with_btc_price
        # Buy 0.2 BTC at 50000 = $10000 (10% of portfolio, under 20% limit)
        order = p.submit_order("BTC/USDT", OrderSide.BUY, OrderType.MARKET, 0.2)
        assert order.status == OrderStatus.FILLED

        # Price goes up to 55000
        p.update_prices({"BTC/USDT": 55000.0})
        pos = p.positions["BTC/USDT"]

        assert pos.unrealized_pnl == pytest.approx(1000.0)  # 0.2 * (55000 - 50000)
        assert pos.unrealized_pnl_pct == pytest.approx(10.0, rel=0.01)
        assert pos.market_value == pytest.approx(11000.0)

        # Price drops to 45000
        p.update_prices({"BTC/USDT": 45000.0})
        pos = p.positions["BTC/USDT"]
        assert pos.unrealized_pnl == pytest.approx(-1000.0)  # 0.2 * (45000 - 50000)
        assert pos.unrealized_pnl_pct == pytest.approx(-10.0, rel=0.01)


# ---------------------------------------------------------------------------
# Test 5: Max position size limit (20%)
# ---------------------------------------------------------------------------

class TestMaxPositionSize:
    def test_max_position_size_limit(self, portfolio_with_btc_price):
        p = portfolio_with_btc_price
        # Try to buy 0.5 BTC at 50000 = $25,000 = 25% of 100k portfolio -> rejected
        order = p.submit_order("BTC/USDT", OrderSide.BUY, OrderType.MARKET, 0.5)
        assert order.status == OrderStatus.REJECTED
        assert "Position size limit" in order.reason


# ---------------------------------------------------------------------------
# Test 6: Max total exposure limit (90%)
# ---------------------------------------------------------------------------

class TestMaxExposure:
    def test_max_exposure_limit(self):
        """Cannot exceed 90% total exposure."""
        p = PaperPortfolio(initial_cash=100_000.0, portfolio_id="test_exposure")

        # Seed multiple prices
        from app.database import get_db
        with get_db() as conn:
            cur = conn.cursor()
            for sym, px in [("AAA", 100.0), ("BBB", 100.0), ("CCC", 100.0), ("DDD", 100.0), ("EEE", 100.0)]:
                cur.execute(
                    "INSERT INTO price_ticks (symbol, exchange, price) VALUES (?, ?, ?)",
                    (sym, "test", px),
                )

        # Buy 5 positions at $19,000 each = $95,000 total (95% > 90%)
        # First 4 should fill (each 19% of portfolio, total 76%)
        for sym in ["AAA", "BBB", "CCC", "DDD"]:
            order = p.submit_order(sym, OrderSide.BUY, OrderType.MARKET, 190.0)
            assert order.status == OrderStatus.FILLED, f"{sym} should fill: {order.reason}"

        # 5th should be rejected (would push to ~95%)
        order = p.submit_order("EEE", OrderSide.BUY, OrderType.MARKET, 190.0)
        assert order.status == OrderStatus.REJECTED
        assert "exposure limit" in order.reason.lower()


# ---------------------------------------------------------------------------
# Test 7: Cancel pending order
# ---------------------------------------------------------------------------

class TestCancelPendingOrder:
    def test_cancel_pending_order(self, portfolio_with_btc_price):
        p = portfolio_with_btc_price
        # Submit a limit buy below current price (won't fill)
        order = p.submit_order("BTC/USDT", OrderSide.BUY, OrderType.LIMIT, 0.1, price=40000.0)
        assert order.status == OrderStatus.PENDING

        result = p.cancel_order(order.id)
        assert result is True

        # Verify order is cancelled
        cancelled = [o for o in p.order_history if o.id == order.id]
        assert cancelled[0].status == OrderStatus.CANCELLED


# ---------------------------------------------------------------------------
# Test 8: Cannot cancel filled order
# ---------------------------------------------------------------------------

class TestCancelFilledFails:
    def test_cancel_filled_order_fails(self, portfolio_with_btc_price):
        p = portfolio_with_btc_price
        order = p.submit_order("BTC/USDT", OrderSide.BUY, OrderType.MARKET, 0.1)
        assert order.status == OrderStatus.FILLED

        result = p.cancel_order(order.id)
        assert result is False


# ---------------------------------------------------------------------------
# Test 9: Close position creates sell order
# ---------------------------------------------------------------------------

class TestClosePosition:
    def test_close_position(self, portfolio_with_btc_price):
        p = portfolio_with_btc_price
        # Buy first
        p.submit_order("BTC/USDT", OrderSide.BUY, OrderType.MARKET, 0.1)
        assert "BTC/USDT" in p.positions

        # Close
        sell_order = p.close_position("BTC/USDT")
        assert sell_order.status == OrderStatus.FILLED
        assert sell_order.side == OrderSide.SELL
        assert sell_order.fill_quantity == 0.1
        assert "BTC/USDT" not in p.positions


# ---------------------------------------------------------------------------
# Test 10: Portfolio snapshot structure
# ---------------------------------------------------------------------------

class TestPortfolioSnapshot:
    def test_portfolio_snapshot(self, portfolio_with_btc_price):
        p = portfolio_with_btc_price
        p.submit_order("BTC/USDT", OrderSide.BUY, OrderType.MARKET, 0.1)

        snap = p.get_portfolio_snapshot()
        assert "cash" in snap
        assert "total_value" in snap
        assert "positions" in snap
        assert "position_count" in snap
        assert "high_water_mark" in snap
        assert "portfolio_id" in snap
        assert snap["position_count"] == 1
        assert len(snap["positions"]) == 1

        pos = snap["positions"][0]
        assert "symbol" in pos
        assert "quantity" in pos
        assert "avg_entry_price" in pos
        assert "current_price" in pos
        assert "market_value" in pos
        assert "unrealized_pnl" in pos
        assert "unrealized_pnl_pct" in pos


# ---------------------------------------------------------------------------
# Test 11: Performance metrics after trades
# ---------------------------------------------------------------------------

class TestPerformanceMetrics:
    def test_performance_metrics(self, portfolio_with_btc_price):
        p = portfolio_with_btc_price
        # Buy 0.1 BTC at 50000, sell at 50000 (break-even)
        p.submit_order("BTC/USDT", OrderSide.BUY, OrderType.MARKET, 0.1)
        p.submit_order("BTC/USDT", OrderSide.SELL, OrderType.MARKET, 0.1)

        perf = p.get_performance()
        assert "total_value" in perf
        assert "total_return_pct" in perf
        assert "win_rate" in perf
        assert "total_trades" in perf
        assert "max_drawdown" in perf
        assert "sharpe_ratio" in perf
        assert "open_positions" in perf
        assert perf["total_trades"] == 1  # one closed trade
        assert perf["open_positions"] == 0


# ---------------------------------------------------------------------------
# Test 12: Reset portfolio
# ---------------------------------------------------------------------------

class TestResetPortfolio:
    def test_reset_portfolio(self, portfolio_with_btc_price):
        p = portfolio_with_btc_price
        p.submit_order("BTC/USDT", OrderSide.BUY, OrderType.MARKET, 0.1)
        assert len(p.positions) > 0
        assert len(p.order_history) > 0

        p.reset()
        assert p.cash == 100_000.0
        assert len(p.positions) == 0
        assert len(p.order_history) == 0


# ---------------------------------------------------------------------------
# Test 13: Order history filter by status
# ---------------------------------------------------------------------------

class TestOrderHistoryFilter:
    def test_order_history_filter(self, portfolio_with_btc_price):
        p = portfolio_with_btc_price
        # Create a filled order
        p.submit_order("BTC/USDT", OrderSide.BUY, OrderType.MARKET, 0.1)
        # Create a rejected order (sell without position for ETH)
        p.submit_order("ETH/USDT", OrderSide.SELL, OrderType.MARKET, 1.0)

        all_orders = p.order_history
        assert len(all_orders) == 2

        filled = [o for o in all_orders if o.status == OrderStatus.FILLED]
        rejected = [o for o in all_orders if o.status == OrderStatus.REJECTED]
        assert len(filled) == 1
        assert len(rejected) == 1


# ---------------------------------------------------------------------------
# Test 14: Multiple simultaneous positions
# ---------------------------------------------------------------------------

class TestMultiplePositions:
    def test_multiple_positions(self):
        """Can hold BTC and ETH simultaneously."""
        p = PaperPortfolio(initial_cash=100_000.0, portfolio_id="test_multi")

        from app.database import get_db
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO price_ticks (symbol, exchange, price) VALUES (?, ?, ?)",
                ("BTC/USDT", "test", 50000.0),
            )
            cur.execute(
                "INSERT INTO price_ticks (symbol, exchange, price) VALUES (?, ?, ?)",
                ("ETH/USDT", "test", 3000.0),
            )

        btc_order = p.submit_order("BTC/USDT", OrderSide.BUY, OrderType.MARKET, 0.2)
        eth_order = p.submit_order("ETH/USDT", OrderSide.BUY, OrderType.MARKET, 3.0)

        assert btc_order.status == OrderStatus.FILLED
        assert eth_order.status == OrderStatus.FILLED
        assert "BTC/USDT" in p.positions
        assert "ETH/USDT" in p.positions
        assert len(p.positions) == 2

        expected_cash = 100_000.0 - (0.2 * 50000.0) - (3.0 * 3000.0)
        assert p.cash == pytest.approx(expected_cash)


# ---------------------------------------------------------------------------
# Test 15: FastAPI POST /api/paper/order
# ---------------------------------------------------------------------------

class TestPaperTradingAPIOrder:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        reset_paper_portfolio()
        return TestClient(app)

    def test_paper_trading_api_order(self, client):
        # Seed a price
        from app.database import get_db
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO price_ticks (symbol, exchange, price) VALUES (?, ?, ?)",
                ("BTC/USDT", "test", 50000.0),
            )

        resp = client.post("/api/paper/order", json={
            "symbol": "BTC/USDT",
            "side": "buy",
            "type": "market",
            "quantity": 0.1,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "filled"
        assert data["symbol"] == "BTC/USDT"
        assert data["fill_price"] == 50000.0


# ---------------------------------------------------------------------------
# Test 16: FastAPI GET /api/paper/portfolio
# ---------------------------------------------------------------------------

class TestPaperTradingAPIPortfolio:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        reset_paper_portfolio()
        return TestClient(app)

    def test_paper_trading_api_portfolio(self, client):
        resp = client.get("/api/paper/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert "cash" in data
        assert "total_value" in data
        assert "positions" in data
        assert data["total_value"] == 100_000.0
