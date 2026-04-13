"""Tests for Fund Risk Manager — no mocks, real calculations."""

import pytest
from app.ai.risk_manager import (
    FundPosition, FundState, SECTOR_MAP,
    check_position_limits, check_sector_concentration,
    check_cash_reserve, check_drawdown, check_capital_adequacy,
    run_risk_assessment, optimal_position_size,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_fund(cash=50000, hwm=0) -> FundState:
    """A sample fund with BTC, ETH, SOL and cash."""
    positions = [
        FundPosition("BTC/USDT", 1.0, 55000, 60000, "store_of_value"),
        FundPosition("ETH/USDT", 10.0, 3000, 3200, "smart_contract_platform"),
        FundPosition("SOL/USDT", 100.0, 150, 160, "smart_contract_platform"),
    ]
    fund = FundState(
        positions=positions,
        cash_usd=cash,
        fund_name="Test Fund",
        high_water_mark=hwm,
    )
    return fund


# ---------------------------------------------------------------------------
# Tests: Position Limits
# ---------------------------------------------------------------------------

class TestPositionLimits:
    def test_no_breach_balanced_fund(self):
        fund = _sample_fund(cash=50000)
        # BTC = 60000 / ~142000 = ~42% → breach at 25%
        checks = check_position_limits(fund)
        breaches = [c for c in checks if c.status == "breach"]
        assert len(breaches) >= 1  # BTC exceeds 25%

    def test_no_breach_with_high_limit(self):
        fund = _sample_fund()
        checks = check_position_limits(fund, {"max_position_pct": 50.0})
        breaches = [c for c in checks if c.status == "breach"]
        assert len(breaches) == 0  # 50% limit → BTC at 42% is ok


# ---------------------------------------------------------------------------
# Tests: Sector Concentration
# ---------------------------------------------------------------------------

class TestSectorConcentration:
    def test_sector_warning(self):
        fund = _sample_fund()
        # smart_contract_platform = ETH + SOL = 32000 + 16000 = 48000 / 142000 = ~33%
        checks = check_sector_concentration(fund)
        # With 40% limit, 33% should not breach
        breaches = [c for c in checks if c.status == "breach"]
        assert len(breaches) == 0

    def test_sector_breach_with_strict_limit(self):
        fund = _sample_fund()
        checks = check_sector_concentration(fund, {"max_sector_pct": 20.0})
        breaches = [c for c in checks if c.status == "breach"]
        # store_of_value (BTC ~42%) and smart_contract_platform (~33%) both breach 20%
        assert len(breaches) >= 2


# ---------------------------------------------------------------------------
# Tests: Cash Reserve
# ---------------------------------------------------------------------------

class TestCashReserve:
    def test_sufficient_cash(self):
        fund = _sample_fund(cash=50000)
        # cash_pct = 50000 / 142000 = ~35% > 10%
        checks = check_cash_reserve(fund)
        assert len(checks) == 0

    def test_insufficient_cash(self):
        fund = _sample_fund(cash=1000)
        # cash_pct = 1000 / 93000 ~ 1% < 10%
        checks = check_cash_reserve(fund)
        assert len(checks) == 1
        assert checks[0].status == "breach"


# ---------------------------------------------------------------------------
# Tests: Drawdown Circuit Breaker
# ---------------------------------------------------------------------------

class TestDrawdown:
    def test_no_drawdown(self):
        fund = _sample_fund(hwm=100000)
        # Fund value ~142000 > HWM → no drawdown
        checks = check_drawdown(fund)
        assert len(checks) == 0

    def test_drawdown_breach(self):
        # HWM = 200000, current ~142000 → drawdown ~29% > 15%
        fund = _sample_fund(hwm=200000)
        checks = check_drawdown(fund)
        assert len(checks) == 1
        assert checks[0].status == "breach"
        assert "HALT TRADING" in checks[0].message

    def test_drawdown_warning(self):
        # HWM = 155000, current ~142000 → drawdown ~8.4%, warning threshold = 15*0.7 = 10.5%
        fund = _sample_fund(hwm=155000)
        checks = check_drawdown(fund)
        # 8.4% < 10.5% → no warning yet
        assert len(checks) == 0


# ---------------------------------------------------------------------------
# Tests: Capital Adequacy
# ---------------------------------------------------------------------------

class TestCapitalAdequacy:
    def test_sufficient_capital(self):
        fund = _sample_fund()
        # ~142000 USD / 1.08 = ~131K EUR > 125K
        checks = check_capital_adequacy(fund)
        assert len(checks) == 0

    def test_insufficient_capital(self):
        # Small fund
        small = FundState(
            positions=[FundPosition("BTC/USDT", 0.01, 60000, 60000)],
            cash_usd=1000,
        )
        checks = check_capital_adequacy(small)
        assert len(checks) == 1
        assert checks[0].status == "breach"


# ---------------------------------------------------------------------------
# Tests: Full Risk Assessment
# ---------------------------------------------------------------------------

class TestRiskAssessment:
    def test_full_assessment_structure(self):
        fund = _sample_fund(cash=50000, hwm=142000)
        result = run_risk_assessment(fund)

        assert "risk_level" in result
        assert "halt_trading" in result
        assert "checks" in result
        assert "allocation" in result
        assert "sector_allocation" in result
        assert "positions" in result
        assert result["fund_name"] == "Test Fund"
        assert result["total_value_usd"] > 0

    def test_healthy_fund(self):
        # Well-balanced fund with strict limits
        fund = FundState(
            positions=[
                FundPosition("BTC/USDT", 0.5, 60000, 60000, "store_of_value"),
                FundPosition("ETH/USDT", 5.0, 3200, 3200, "smart_contract_platform"),
            ],
            cash_usd=100000,
            high_water_mark=130000,
        )
        result = run_risk_assessment(fund)
        # Large cash reserve, no breaches
        assert result["risk_level"] in ("normal", "elevated")


# ---------------------------------------------------------------------------
# Tests: Position Sizing (Kelly Criterion)
# ---------------------------------------------------------------------------

class TestPositionSizing:
    def test_positive_edge(self):
        result = optimal_position_size(
            win_rate=0.6,
            avg_win_pct=4.0,
            avg_loss_pct=2.0,
            fund_value=100000,
        )
        assert result["recommended_pct"] > 0
        assert result["recommended_usd"] > 0
        assert result["recommended_pct"] <= 25.0  # capped at max_position_pct

    def test_no_edge(self):
        result = optimal_position_size(
            win_rate=0.3,
            avg_win_pct=2.0,
            avg_loss_pct=3.0,
            fund_value=100000,
        )
        # Negative or zero Kelly → 0
        assert result["recommended_pct"] == 0

    def test_zero_loss(self):
        result = optimal_position_size(
            win_rate=0.5,
            avg_win_pct=5.0,
            avg_loss_pct=0,
            fund_value=100000,
        )
        assert result["recommended_pct"] == 0


# ---------------------------------------------------------------------------
# Tests: API Endpoints
# ---------------------------------------------------------------------------

class TestFundAPI:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_risk_assessment_endpoint(self, client):
        resp = client.post("/api/fund/risk-assessment", json={
            "positions": [
                {"symbol": "BTC/USDT", "quantity": 1.0, "entry_price": 55000, "current_price": 60000},
                {"symbol": "ETH/USDT", "quantity": 10.0, "entry_price": 3000, "current_price": 3200},
            ],
            "cash_usd": 50000,
            "high_water_mark": 150000,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "risk_level" in data
        assert "checks" in data

    def test_risk_limits_endpoint(self, client):
        resp = client.get("/api/fund/risk-limits")
        assert resp.status_code == 200
        data = resp.json()
        assert "limits" in data
        assert "max_position_pct" in data["limits"]

    def test_position_size_endpoint(self, client):
        resp = client.post(
            "/api/fund/position-size?fund_value=100000&win_rate=0.6&avg_win_pct=4.0&avg_loss_pct=-2.0"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "recommended_pct" in data
        assert "recommended_usd" in data

    def test_dashboard_endpoint(self, client):
        resp = client.post("/api/fund/dashboard", json={
            "positions": [
                {"symbol": "BTC/USDT", "quantity": 2.0, "entry_price": 55000, "current_price": 60000},
            ],
            "cash_usd": 100000,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "risk_level" in data
        assert "total_value_usd" in data
