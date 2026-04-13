"""Fund Management API — risk assessment, position sizing, fund dashboard."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.auth import get_current_user, require_role

from app.ai.risk_manager import (
    FundPosition, FundState, SECTOR_MAP,
    run_risk_assessment, optimal_position_size,
    DEFAULT_RISK_LIMITS,
)

router = APIRouter(prefix="/api/fund", tags=["fund"])


class FundPositionInput(BaseModel):
    symbol: str = Field(..., max_length=20)
    quantity: float = Field(..., ge=0)
    entry_price: float = Field(..., ge=0)
    current_price: Optional[float] = Field(default=None, ge=0)
    sector: str = Field(default="", max_length=50)


class FundInput(BaseModel):
    positions: list[FundPositionInput] = Field(..., max_length=100)
    cash_usd: float = Field(default=0.0, ge=0, le=1_000_000_000)
    fund_name: str = Field(default="SignalDACH Fund", max_length=200)
    high_water_mark: float = Field(default=0.0, ge=0)


def _build_fund(data: FundInput) -> FundState:
    positions = []
    for p in data.positions:
        sym = p.symbol.split("/")[0] if "/" in p.symbol else p.symbol
        # Try to get live price if not provided
        current = p.current_price
        if current is None:
            try:
                from app.ai.portfolio import _get_latest_price
                current = _get_latest_price(p.symbol) or p.entry_price
            except Exception:
                current = p.entry_price

        positions.append(FundPosition(
            symbol=p.symbol,
            quantity=p.quantity,
            entry_price=p.entry_price,
            current_price=current,
            sector=p.sector or SECTOR_MAP.get(sym, "other"),
        ))

    fund = FundState(
        positions=positions,
        cash_usd=data.cash_usd,
        fund_name=data.fund_name,
        high_water_mark=data.high_water_mark,
    )
    # Auto-set HWM if not provided
    if fund.high_water_mark <= 0:
        fund.high_water_mark = fund.total_value

    return fund


@router.post("/risk-assessment", dependencies=[Depends(get_current_user)])
async def risk_assessment(data: FundInput):
    """Run comprehensive risk assessment against fund limits."""
    fund = _build_fund(data)
    result = run_risk_assessment(fund)
    try:
        from app.audit import log_risk
        log_risk("risk_assessment", detail={
            "fund": data.fund_name,
            "total_value": fund.total_value,
            "halt_trading": result.get("halt_trading", False),
            "breaches": len(result.get("breaches", [])),
        })
    except Exception:
        pass
    return result


@router.get("/risk-limits")
async def get_risk_limits():
    """Get current risk limit configuration."""
    from app.cache import cache_get, cache_set, CACHE_TTLS

    cached = await cache_get("risk_limits")
    if cached:
        return cached

    result = {"limits": DEFAULT_RISK_LIMITS}
    await cache_set("risk_limits", result, CACHE_TTLS["risk_limits"])
    return result


@router.post("/position-size", dependencies=[Depends(require_role("admin", "analyst"))])
async def calculate_position_size(
    fund_value: float = Query(..., ge=0, description="Total fund value in USD"),
    win_rate: float = Query(0.55, ge=0, le=1, description="Historical win rate"),
    avg_win_pct: float = Query(3.0, description="Average win size in %"),
    avg_loss_pct: float = Query(-2.0, description="Average loss size in %"),
    kelly_fraction: float = Query(0.5, ge=0.1, le=1.0, description="Kelly fraction (0.5 = half Kelly)"),
):
    """Calculate optimal position size using Kelly Criterion."""
    return optimal_position_size(
        win_rate=win_rate,
        avg_win_pct=avg_win_pct,
        avg_loss_pct=abs(avg_loss_pct),
        fund_value=fund_value,
        kelly_fraction=kelly_fraction,
    )


@router.post("/dashboard", dependencies=[Depends(get_current_user)])
async def fund_dashboard(data: FundInput):
    """Full fund dashboard with risk assessment, allocation, and signals."""
    fund = _build_fund(data)
    risk = run_risk_assessment(fund)

    # Get latest composite signal if available
    signal_summary = None
    try:
        from app.ai.backtesting import get_signal_history
        recent = get_signal_history("BTC/USDT", "composite", days=1, limit=1)
        if recent:
            signal_summary = {
                "latest_score": recent[0]["score"],
                "confidence": recent[0]["confidence"],
                "ts": recent[0]["ts"],
            }
    except Exception:
        pass

    # Get scorecard metrics if available
    scorecard_summary = None
    try:
        from app.ai.backtesting import compute_scorecard
        sc = compute_scorecard("BTC/USDT", "composite", days=30, eval_hours=24)
        if sc.get("evaluated", 0) > 0:
            scorecard_summary = {
                "win_rate": sc["win_rate"],
                "avg_return_pct": sc["avg_return_pct"],
                "signal_sharpe": sc["signal_sharpe"],
                "total_signals": sc["total_signals"],
            }
    except Exception:
        pass

    return {
        **risk,
        "signal_summary": signal_summary,
        "scorecard_summary": scorecard_summary,
    }
