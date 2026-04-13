"""Portfolio Intelligence API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.auth import get_current_user

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"], dependencies=[Depends(get_current_user)])


class PositionInput(BaseModel):
    symbol: str
    quantity: float
    entry_price: float


class PortfolioInput(BaseModel):
    positions: list[PositionInput]
    cash_usd: float = 0.0


class ScenarioInput(BaseModel):
    portfolio: PortfolioInput
    scenarios: dict[str, float]  # {symbol: pct_change}


def _build_portfolio(data: PortfolioInput):
    from app.ai.portfolio import Portfolio, Position, _get_latest_price
    positions = []
    for p in data.positions:
        current = _get_latest_price(p.symbol) or p.entry_price
        positions.append(Position(
            symbol=p.symbol,
            quantity=p.quantity,
            entry_price=p.entry_price,
            current_price=current,
        ))
    return Portfolio(positions=positions, cash_usd=data.cash_usd)


@router.post("/analyze")
async def analyze_portfolio(data: PortfolioInput):
    """Analyze portfolio with risk metrics (VaR, Sharpe, Max Drawdown)."""
    from app.ai.portfolio import portfolio_risk_metrics
    portfolio = _build_portfolio(data)
    return portfolio_risk_metrics(portfolio)


@router.post("/scenario")
async def run_scenario(data: ScenarioInput):
    """Simulate portfolio impact under a custom scenario."""
    from app.ai.portfolio import simulate_scenario
    portfolio = _build_portfolio(data.portfolio)
    return simulate_scenario(portfolio, data.scenarios)


@router.get("/scenarios/presets")
async def list_preset_scenarios():
    """List available preset market scenarios."""
    from app.ai.portfolio import PRESET_SCENARIOS
    return PRESET_SCENARIOS


@router.post("/scenario/preset")
async def run_preset_scenario(
    data: PortfolioInput,
    preset: str = Query(..., description="Preset: btc_crash_30, bull_run, mica_enforcement, etc."),
):
    """Run a preset scenario against a portfolio."""
    from app.ai.portfolio import simulate_scenario, PRESET_SCENARIOS
    if preset not in PRESET_SCENARIOS:
        return {"error": f"Unknown preset: {preset}. Available: {list(PRESET_SCENARIOS.keys())}"}

    portfolio = _build_portfolio(data)
    return simulate_scenario(portfolio, PRESET_SCENARIOS[preset]["changes"])
