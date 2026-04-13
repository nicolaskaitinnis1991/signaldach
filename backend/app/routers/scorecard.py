"""Signal Scorecard & Backtesting API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.auth import get_current_user

router = APIRouter(prefix="/api/scorecard", tags=["scorecard"])


@router.get("/performance")
async def signal_performance(
    symbol: str = Query("BTC/USDT"),
    signal_type: str = Query("composite", description="Signal type: composite, sentiment, technical, onchain, regulatory"),
    days: int = Query(30, ge=1, le=365),
    eval_hours: int = Query(24, ge=1, le=168),
):
    """Get performance scorecard for a signal type."""
    from app.cache import cache_get, cache_set, cache_key, CACHE_TTLS

    key = cache_key("scorecard", symbol, signal_type, str(days), str(eval_hours))
    cached = await cache_get(key)
    if cached:
        return cached

    from app.ai.backtesting import compute_scorecard
    result = compute_scorecard(symbol=symbol, signal_type=signal_type, days=days, eval_hours=eval_hours)
    await cache_set(key, result, CACHE_TTLS["scorecard"])
    return result


@router.get("/agents")
async def agent_comparison(
    symbol: str = Query("BTC/USDT"),
    days: int = Query(30, ge=1, le=365),
    eval_hours: int = Query(24, ge=1, le=168),
):
    """Compare performance across all agents."""
    from app.ai.backtesting import compare_agents
    return compare_agents(symbol=symbol, days=days, eval_hours=eval_hours)


@router.get("/history")
async def signal_history(
    symbol: str = Query("BTC/USDT"),
    signal_type: str = Query("composite"),
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(100, ge=1, le=500),
):
    """Get historical signal data."""
    from app.ai.backtesting import get_signal_history
    return {"signals": get_signal_history(symbol=symbol, signal_type=signal_type, days=days, limit=limit)}


@router.get("/backtest", dependencies=[Depends(get_current_user)])
async def backtest(
    symbol: str = Query("BTC/USDT"),
    signal_type: str = Query("composite"),
    days: int = Query(30, ge=1, le=365),
    buy_threshold: float = Query(0.2, ge=-1.0, le=1.0),
    sell_threshold: float = Query(-0.2, ge=-1.0, le=1.0),
    initial_capital: float = Query(10000.0, ge=100.0),
):
    """Run a backtest using historical signals."""
    from app.ai.backtesting import backtest_strategy
    return backtest_strategy(
        symbol=symbol,
        signal_type=signal_type,
        days=days,
        buy_threshold=buy_threshold,
        sell_threshold=sell_threshold,
        initial_capital=initial_capital,
    )
