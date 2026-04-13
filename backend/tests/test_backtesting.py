"""Tests for Signal Scorecard & Backtesting Engine.

All tests hit real database — no mocks.
"""

import json
import pytest
from datetime import datetime, timedelta, timezone

from app.database import get_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_prices(symbol="BTC/USDT", base_price=60000, hours=48):
    """Insert fake price_ticks for testing."""
    with get_db() as conn:
        cur = conn.cursor()
        for i in range(hours):
            ts = (datetime.now(timezone.utc) - timedelta(hours=hours - i)).isoformat()
            # Price oscillates ±2% around base
            price = base_price * (1 + 0.02 * ((-1) ** i))
            cur.execute(
                "INSERT INTO price_ticks (ts, symbol, price, volume_24h, change_pct_24h, exchange) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (ts, symbol, price, 1000000, 1.5 if i % 2 == 0 else -1.5, "test"),
            )
        conn.commit()


def _seed_signals(symbol="BTC/USDT", signal_type="composite", count=20):
    """Insert fake signal_scores for testing."""
    from app.ai.backtesting import store_signal
    for i in range(count):
        ts_offset = count - i  # oldest first
        score = 0.3 if i % 3 == 0 else (-0.3 if i % 3 == 1 else 0.0)
        store_signal(
            symbol=symbol,
            signal_type=signal_type,
            score=score,
            confidence=0.7,
            components={"test": True},
            reasoning=f"Test signal {i}",
        )
        # Backdate the signal in DB
        with get_db() as conn:
            cur = conn.cursor()
            ts = (datetime.now(timezone.utc) - timedelta(hours=ts_offset * 2)).isoformat()
            cur.execute(
                "UPDATE signal_scores SET ts = ? WHERE reasoning = ?",
                (ts, f"Test signal {i}"),
            )
            conn.commit()


# ---------------------------------------------------------------------------
# Tests: Signal Storage
# ---------------------------------------------------------------------------

class TestSignalStorage:
    def test_store_single_signal(self):
        from app.ai.backtesting import store_signal
        store_signal(
            symbol="BTC/USDT",
            signal_type="composite",
            score=0.45,
            confidence=0.82,
            components={"sentiment": 0.3, "technical": 0.6},
            reasoning="Test bullish signal",
        )

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM signal_scores WHERE symbol = 'BTC/USDT'")
            rows = [dict(r) for r in cur.fetchall()]

        assert len(rows) == 1
        assert rows[0]["score"] == 0.45
        assert rows[0]["confidence"] == 0.82
        assert rows[0]["signal_type"] == "composite"
        assert "sentiment" in rows[0]["components_json"]

    def test_store_composite_signal(self):
        from app.ai.backtesting import store_composite_signal

        result = {
            "symbol": "ETH/USDT",
            "overall_signal": "buy",
            "overall_score": 0.35,
            "confidence": 0.75,
            "reasoning": "Multi-agent bullish",
            "key_drivers": ["technical: bullish (+0.45)"],
            "risk_factors": ["No significant risks"],
            "agents": [
                {"agent": "sentiment", "signal": "bullish", "score": 0.2, "confidence": 0.6, "reasoning": "Positive news"},
                {"agent": "technical", "signal": "bullish", "score": 0.45, "confidence": 0.85, "reasoning": "Uptrend"},
            ],
        }
        store_composite_signal(result)

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM signal_scores WHERE symbol = 'ETH/USDT' ORDER BY id")
            rows = [dict(r) for r in cur.fetchall()]

        # Should store composite + 2 agent signals = 3 rows
        assert len(rows) == 3
        types = [r["signal_type"] for r in rows]
        assert "composite" in types
        assert "sentiment" in types
        assert "technical" in types


# ---------------------------------------------------------------------------
# Tests: Signal History
# ---------------------------------------------------------------------------

class TestSignalHistory:
    def test_get_signal_history(self):
        _seed_signals(count=10)
        from app.ai.backtesting import get_signal_history

        history = get_signal_history("BTC/USDT", "composite", days=30)
        assert len(history) == 10
        assert all(h["symbol"] == "BTC/USDT" for h in history)

    def test_history_filters_by_type(self):
        _seed_signals("BTC/USDT", "composite", count=5)
        _seed_signals("BTC/USDT", "sentiment", count=3)
        from app.ai.backtesting import get_signal_history

        composite = get_signal_history("BTC/USDT", "composite", days=30)
        sentiment = get_signal_history("BTC/USDT", "sentiment", days=30)
        assert len(composite) == 5
        assert len(sentiment) == 3

    def test_history_respects_limit(self):
        _seed_signals(count=20)
        from app.ai.backtesting import get_signal_history

        history = get_signal_history("BTC/USDT", "composite", days=90, limit=5)
        assert len(history) == 5


# ---------------------------------------------------------------------------
# Tests: Outcome Evaluation
# ---------------------------------------------------------------------------

class TestOutcomeEvaluation:
    def test_evaluate_signal_outcome_with_data(self):
        _seed_prices(hours=48)
        from app.ai.backtesting import evaluate_signal_outcome

        ts = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
        result = evaluate_signal_outcome(
            signal_ts=ts,
            symbol="BTC/USDT",
            signal_score=0.5,
            eval_hours=6,
        )

        assert result is not None
        assert "actual_return_pct" in result
        assert "correct" in result
        assert result["symbol"] == "BTC/USDT"
        assert result["eval_hours"] == 6

    def test_evaluate_returns_none_without_prices(self):
        from app.ai.backtesting import evaluate_signal_outcome

        ts = datetime.now(timezone.utc).isoformat()
        result = evaluate_signal_outcome(
            signal_ts=ts,
            symbol="FAKE/USDT",
            signal_score=0.5,
        )
        # No price data for FAKE → None
        assert result is None


# ---------------------------------------------------------------------------
# Tests: Scorecard
# ---------------------------------------------------------------------------

class TestScorecard:
    def test_scorecard_no_data(self):
        from app.ai.backtesting import compute_scorecard

        result = compute_scorecard("NOTHING/USDT", "composite", days=7)
        assert result["total_signals"] == 0

    def test_scorecard_with_data(self):
        _seed_prices(hours=48)
        _seed_signals(count=15)
        from app.ai.backtesting import compute_scorecard

        result = compute_scorecard("BTC/USDT", "composite", days=30, eval_hours=4)
        assert result["total_signals"] == 15
        assert "win_rate" in result
        assert 0 <= result.get("win_rate", 0) <= 1

    def test_scorecard_has_confidence_calibration(self):
        _seed_prices(hours=48)
        _seed_signals(count=10)
        from app.ai.backtesting import compute_scorecard

        result = compute_scorecard("BTC/USDT", "composite", days=30, eval_hours=4)
        assert "confidence_calibration" in result


# ---------------------------------------------------------------------------
# Tests: Agent Comparison
# ---------------------------------------------------------------------------

class TestAgentComparison:
    def test_compare_agents_empty(self):
        from app.ai.backtesting import compare_agents

        result = compare_agents("BTC/USDT", days=7)
        assert "agents" in result
        assert "ranking" in result

    def test_compare_agents_with_data(self):
        _seed_prices(hours=48)
        _seed_signals("BTC/USDT", "composite", 5)
        _seed_signals("BTC/USDT", "sentiment", 5)
        _seed_signals("BTC/USDT", "technical", 5)
        from app.ai.backtesting import compare_agents

        result = compare_agents("BTC/USDT", days=30, eval_hours=4)
        assert result["agents"]["composite"]["total_signals"] == 5
        assert result["agents"]["sentiment"]["total_signals"] == 5


# ---------------------------------------------------------------------------
# Tests: Backtester
# ---------------------------------------------------------------------------

class TestBacktester:
    def test_backtest_no_signals(self):
        from app.ai.backtesting import backtest_strategy

        result = backtest_strategy("BTC/USDT", days=7)
        assert "error" in result

    def test_backtest_with_signals(self):
        _seed_prices(hours=72)
        _seed_signals(count=20)
        from app.ai.backtesting import backtest_strategy

        result = backtest_strategy(
            symbol="BTC/USDT",
            days=30,
            buy_threshold=0.2,
            sell_threshold=-0.2,
            initial_capital=10000,
        )

        assert "final_capital" in result
        assert "total_return_pct" in result
        assert "max_drawdown_pct" in result
        assert "equity_curve" in result
        assert result["initial_capital"] == 10000
        assert isinstance(result["equity_curve"], list)


# ---------------------------------------------------------------------------
# Tests: API Endpoints
# ---------------------------------------------------------------------------

class TestScorecardAPI:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_performance_endpoint(self, client):
        resp = client.get("/api/scorecard/performance?symbol=BTC/USDT&days=7")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_signals" in data

    def test_agents_endpoint(self, client):
        resp = client.get("/api/scorecard/agents?symbol=BTC/USDT&days=7")
        assert resp.status_code == 200
        data = resp.json()
        assert "agents" in data

    def test_history_endpoint(self, client):
        resp = client.get("/api/scorecard/history?symbol=BTC/USDT&days=7")
        assert resp.status_code == 200
        data = resp.json()
        assert "signals" in data

    def test_backtest_endpoint(self, client):
        resp = client.get("/api/scorecard/backtest?symbol=BTC/USDT&days=7")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests: Portfolio API
# ---------------------------------------------------------------------------

class TestPortfolioAPI:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_analyze_endpoint(self, client):
        resp = client.post("/api/portfolio/analyze", json={
            "positions": [
                {"symbol": "BTC/USDT", "quantity": 1.5, "entry_price": 55000},
                {"symbol": "ETH/USDT", "quantity": 10, "entry_price": 3200},
            ]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "total_value" in data or "positions" in data

    def test_presets_endpoint(self, client):
        resp = client.get("/api/portfolio/scenarios/presets")
        assert resp.status_code == 200
        data = resp.json()
        assert "btc_crash_30" in data
        assert len(data) > 0

    def test_scenario_preset_endpoint(self, client):
        resp = client.post(
            "/api/portfolio/scenario/preset?preset=btc_crash_30",
            json={
                "positions": [
                    {"symbol": "BTC/USDT", "quantity": 1, "entry_price": 60000},
                ]
            },
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests: Chat API
# ---------------------------------------------------------------------------

class TestChatAPI:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_chat_endpoint(self, client):
        resp = client.post("/api/chat/", json={"message": "What is Bitcoin?"})
        assert resp.status_code == 200
        data = resp.json()
        assert "reply" in data
        assert len(data["reply"]) > 0

    def test_chat_price_query(self, client):
        resp = client.post("/api/chat/", json={"message": "What is the price of BTC?"})
        assert resp.status_code == 200
        data = resp.json()
        assert "reply" in data

    def test_chat_regime_query(self, client):
        resp = client.post("/api/chat/", json={"message": "What is the current market regime?"})
        assert resp.status_code == 200

    def test_chat_empty_message(self, client):
        resp = client.post("/api/chat/", json={"message": ""})
        # Should still return 200 with a default reply
        assert resp.status_code == 200
